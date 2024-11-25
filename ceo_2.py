# streamlit_app.py
import hashlib
import streamlit as st
import time
from pathlib import Path
import io
import requests
import sounddevice as sd
import soundfile as sf
import threading
from typing import List, Dict
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
import itertools
from openai import OpenAI

# API 키 기본값 설정
llm_api_key = st.secrets["llm_api_key"]
naver_client_id = st.secrets["naver_client_id"]
naver_client_secret = st.secrets["naver_client_secret"]
xi_api_key = st.secrets["xi_api_key"]
voice_id = st.secrets["voice_id"]
    
class StreamlitNewsSearchSystem:
    def __init__(self, naver_client_id: str, naver_client_secret: str, llm_api_key: str, xi_api_key: str, voice_id: str):
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret
        self.llm_api_key = llm_api_key
        self.xi_api_key = xi_api_key  # ElevenLabs API 키
        self.voice_id = voice_id  # ElevenLabs Voice ID
        self.client = OpenAI(api_key=llm_api_key)
    
    def extract_keywords(self, query: str, progress_bar) -> List[str]:
        """LLM을 사용하여 검색 키워드 추출"""
        try:
            progress_bar.progress(10)
            st.write("키워드 추출 중...")
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "입력된 질문에서 핵심 검색 키워드만 추출해주세요. 쉼표로 구분된 형태로 반환해주세요."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ]
            )
            
            keywords = response.choices[0].message.content.split(',')
            keywords = [keyword.strip() for keyword in keywords]
            
            if '문동권' not in keywords:
                keywords.insert(0, '문동권')
            
            progress_bar.progress(20)
            st.write(f"추출된 키워드: {', '.join(keywords)}")
            return keywords
            
        except Exception as e:
            st.error(f"키워드 추출 중 오류 발생: {str(e)}")
            raise e

    def clean_html_text(self, html_content: str) -> str:
        """HTML 태그 제거 및 텍스트 정제"""
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\.,!?"\'-]', '', text)
        return text.strip()

    def get_full_article_content(self, url: str) -> str:
        """기사 URL에서 전체 내용 크롤링"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            if 'news.naver.com' in url:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for selector in ['#articleBody', '#articleBodyContents', '#newsEndContents']:
                    article_content = soup.select_one(selector)
                    if article_content:
                        break
                        
            elif 'ceoscoredaily.com' in url:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                article_content = soup.select_one('.view_cont')
                
            if article_content:
                for unnecessary in article_content.select('script, style, header, footer'):
                    unnecessary.decompose()
                return self.clean_html_text(str(article_content))
                    
            return "기사 본문을 가져올 수 없습니다."
                
        except Exception as e:
            return "기사 본문을 가져올 수 없습니다."

    def search_naver_news(self, keywords: List[str], progress_bar, display: int = 5) -> List[Dict]:
        """네이버 뉴스 API로 뉴스 검색"""
        try:
            query = ' '.join(keywords)
            url = "https://openapi.naver.com/v1/search/news.json"
            headers = {
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret
            }
            params = {
                "query": query,
                "display": display,
                "sort": "date"
            }
            
            progress_bar.progress(30)
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            news_items = response.json()['items']
            
            filtered_items = []
            with st.spinner("관련 기사 분석 중..."):
                for item in news_items:
                    title = re.sub('<[^<]+?>', '', item['title'])
                    
                    shinhan_keywords = ['신한카드', '문동권']
                    has_shinhan_keyword = any(keyword in title for keyword in shinhan_keywords)
                    
                    pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900')
                    if pub_date.year >= 2023 and has_shinhan_keyword:
                        full_content = self.get_full_article_content(item['link'])
                        item['full_content'] = full_content
                        filtered_items.append(item)
            
            progress_bar.progress(40)
            return filtered_items
            
        except Exception as e:
            if '429' in str(e):
                # API 호출 한도 초과 시 간단한 메시지
                st.info("검색 중... 잠시만 기다려주세요.")
            return []

    def search_with_progressive_keywords(self, keywords: List[str], progress_bar, display: int = 5) -> List[Dict]:
        """키워드를 점진적으로 줄여가며 검색"""
        try:
            all_combinations = []
            other_keywords = [k for k in keywords if k != '문동권']
            
            # 검색 시작 알림
            with st.spinner("뉴스 검색 중..."):
                for i in range(len(other_keywords), 0, -1):
                    for combo in itertools.combinations(other_keywords, i):
                        keywords_combo = ['문동권'] + list(combo)
                        all_combinations.append(keywords_combo)
                    
                    for combo in all_combinations:
                        try:
                            news_items = self.search_naver_news(combo, progress_bar, display)
                            if news_items:
                                return news_items
                        except Exception as e:
                            continue
                
                # 검색 결과가 없을 때
                st.info("관련된 최신 기사를 찾을 수 없습니다. 다른 키워드로 검색해보세요.")
                return []
                
        except Exception as e:
            st.error("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            return []

    def analyze_news_content(self, news_items: List[Dict], original_query: str, progress_bar) -> str:
        """뉴스 내용 분석"""
        try:
            st.write("뉴스 내용 분석 중...")
            progress_bar.progress(60)
            
            news_texts = [
                f"제목: {item['title']}\n"
                f"날짜: {item['pubDate']}\n"
                f"전체 내용: {item['full_content']}\n"
                f"출처: {item['link']}"
                for item in news_items
            ]
            combined_text = "\n\n---\n\n".join(news_texts)
            
            prompt = f"""다음은 '{original_query}'에 관한 신한카드 관련 뉴스 기사들입니다:

            {combined_text}
            
            [문동권 사장님 말씀]
            (기사 내용을 바탕으로 30초 분량의 직접 발화 답변 작성
            - 실제 발언이 있다면 그대로 인용
            - 실제 발언이 없다면 기사 내용을 바탕으로 1인칭 시점에서 직접 설명
            - 신한카드의 주요 정책이나 방향성이 드러나도록 구성

            [참고 기사]
            - 제목: (기사 제목)
            - 날짜: (기사 날짜)
            - URL: (기사 링크)
            - 관련 내용: (핵심 내용)

            [신입사원 가이드]
            문동권 사장님의 경영 철학과 신한카드의 방향성을 고려한 분석입니다.
            (앞선 내용을 바탕으로 신입사원들이 참고할 수 있는 가이드라인 제시)

            주의사항: 
            1. 각 섹션은 명확히 구분되어야 합니다.
            2. 실제 발언처럼 자연스러운 어투를 사용합니다.
            3. 각 섹션의 형식을 정확히 지켜주세요.
            4. 섹션들이 서로 섞이지 않도록 해주세요."""
            
            st.write("GPT 분석 요청 중...")
            progress_bar.progress(70)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "신한카드 문동권 사장님의 발언과 관련 기사를 분석하여, 발언이 있으면 직접 인용하고 없으면 기사 내용을 바탕으로 관련 맥락을 파악하여 답변을 구성하는 assistant입니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2
            )
            
            progress_bar.progress(80)
            return response.choices[0].message.content
            
        except Exception as e:
            st.error(f"뉴스 내용 분석 중 오류 발생: {str(e)}")
            raise e

    def extract_tts_content(self, text: str) -> str:
        """TTS용 콘텐츠 추출"""
        try:
            if '[참고 기사]' in text:
                text = text.split('[참고 기사]')[0].strip()
            st.markdown(f"#### TTS용 텍스트:\n{text}")  # 텍스트를 UI에 출력
            return text
            
        except Exception as e:
            st.error(f"TTS 내용 추출 중 오류 발생: {str(e)}")
            return text
    @st.cache_data
    def generate_tts_with_elevenlabs(_self, text: str, xi_api_key: str, voice_id: str) -> str:
        """ElevenLabs API를 호출하여 TTS 생성"""
        try:
            # 텍스트의 고유 해시값 생성 (캐싱 키로 활용)
            text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            audio_file = f"output_{text_hash}.mp3"
            
            # 캐시된 파일이 이미 존재하면 해당 파일 경로 반환
            if Path(audio_file).exists():
                return audio_file
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": xi_api_key
            }
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.75,
                    "similarity_boost": 0.9,
                    "style": 0.2,
                    "use_speaker_boost": True,
                    "speaking_rate": 1.2
                     
                }
            }

            response = requests.post(url, json=data, headers=headers, stream=True)
            if response.status_code == 200:
                audio_file = "output.mp3"
                with open(audio_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                return audio_file
            else:
                st.error(f"ElevenLabs API 호출 실패: {response.status_code}, {response.text}")
                return None

        except Exception as e:
            st.error(f"ElevenLabs TTS 생성 중 오류 발생: {str(e)}")
            return None
    
    def speak_result(self, text: str) -> None:
        """결과 음성 출력"""
        try:
            # [문동권 사장님 말씀] 섹션만 추출
            if "[문동권 사장님 말씀]" in text:
                tts_content = text.split("[문동권 사장님 말씀]")[1].split("[참고 기사]")[0].strip()
            else:
                return

            # TTS 생성 호출
            audio_path = self.generate_tts_with_elevenlabs(tts_content, self.xi_api_key, self.voice_id)

            if audio_path and Path(audio_path).exists():
                # 파일 읽어서 Streamlit에 전달
                with open(audio_path, "rb") as audio_file:
                    audio_bytes = audio_file.read()
                    
                    st.audio(audio_bytes, format="audio/mp3")
            else:
                st.error("음성 파일을 생성하지 못했습니다.")
        except Exception as e:
            st.error(f"TTS 처리 중 오류 발생: {str(e)}")

# 페이지 기본 설정
st.set_page_config(
    page_title="신한카드ceo 뉴스 검색 시스템",
    page_icon="🔍",
    layout="wide"
)

def save_message(message, role):
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    st.session_state["messages"].append({"message": message, "role": role})

def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message, unsafe_allow_html=True)
    if save:
        save_message(message, role)

# 이전 채팅 기록 표시
def paint_history():
    if "messages" in st.session_state:
        for message in st.session_state["messages"]:
            send_message(
                message["message"],
                message["role"],
                save=False,
            )

def main(query):
    try:
        # 새로운 검색을 시작할 때 audio_played 상태 초기화
        if 'audio_played' in st.session_state:
            del st.session_state.audio_played
            
        # 키워드 추출
        keywords = st.session_state.search_system.extract_keywords(query, progress_bar)
        
        # 뉴스 검색
        news_items = st.session_state.search_system.search_with_progressive_keywords(
            keywords, progress_bar
        )
        
        if not news_items:
            st.warning("해당 주제와 관련된 신한카드 기사를 찾을 수 없습니다.")
            return 
        
        # 뉴스 분석
        result = st.session_state.search_system.analyze_news_content(
            news_items, query, progress_bar
        )
        
        if result:
            # 결과를 세션 상태에 저장
            st.session_state.current_result = result
            
            st.markdown("### 📊 분석 결과")
                        
            # # TTS 컨트롤
            # play_requested = False
            # col1, col2 = st.columns([1, 4])
            # with col1:
            #     if st.button("🔊 음성으로 듣기", key="play_audio"):
            #         play_requested = True
            
            # 섹션 표시
            def extract_section(text, start_marker, end_marker=None):
                try:
                    if start_marker not in text:
                        return None
                    
                    parts = text.split(start_marker, 1)
                    if len(parts) < 2:
                        return None
                        
                    content = parts[1]
                    
                    if end_marker:
                        if end_marker in content:
                            content = content.split(end_marker)[0]
                    
                    content = re.sub(r'^\s*\[.*?\]\s*', '', content)
                    return content.strip()
                except Exception:
                    return None
            
            # 각 섹션 추출
            speech_part = extract_section(result, "[문동권 사장님 말씀]", "[참고 기사]")
            ref_part = extract_section(result, "[참고 기사]", "[신입사원 가이드]")
            guide_part = extract_section(result, "[신입사원 가이드]")
            
            # 결과 컨테이너
            with st.container():
                
                if ref_part:
                    st.markdown("#### 📰 참고 기사")
                    lines = ref_part.split('\n')
                    formatted_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if "URL:" in line:
                            url_parts = line.split("URL:")
                            if len(url_parts) > 1:
                                url = url_parts[1].strip()
                                formatted_lines.append(f"- URL: <a href='{url}' target='_blank'>{url}</a>")
                        else:
                            formatted_lines.append(f"- {line}")

                    formatted_ref = '<br>'.join(formatted_lines)
                    st.markdown(f"""
                    <div style='background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;'>
                        {formatted_ref}
                    </div>
                    """, unsafe_allow_html=True)
                
                if guide_part:
                    st.markdown("#### 🎯 신입사원 가이드")
                    st.markdown(f"""
                    <div style='background-color: #e8f4f9; padding: 20px; border-radius: 10px;'>
                        {guide_part}
                    </div>
                    """, unsafe_allow_html=True)
                
                if speech_part:
                    st.markdown("#### 💬 AI문동권 사장님 말씀")
                    st.markdown(f"""
                    <div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px;'>
                        {speech_part}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # # 음성 버튼과 헤더를 여기에 한 번만 표시
                    # st.markdown("#### 🔊 음성으로 듣기")
                    # play_requested = st.button("재생", key="play_audio")
                    
                    
                    # # 음성 재생 컨트롤
                    # play_requested = False
                    # col1, col2 = st.columns([1, 4])
                    # with col1:
                    #     if st.button("🔊 음성으로 듣기", key="play_audio"):
                    #         play_requested = True
                    
                    # 음성으로 듣기 텍스트와 이모지 표시
                    st.markdown("#### 🔊 AI문동권 사장님 음성으로 듣기")
                            
                    # 음성 재생 처리
                    if st.session_state.tts_enabled and 'audio_played' not in st.session_state:
                        st.session_state.search_system.speak_result(result)
                        st.session_state.audio_played = True

            # 포맷된 결과 생성 (히스토리용)
            formatted_result = f"""### 📊 분석 결과

#### 📰 참고 기사
<div style='background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;'>
{formatted_ref}
</div>

#### 🎯 신입사원 가이드
<div style='background-color: #e8f4f9; padding: 20px; border-radius: 10px;'>
{guide_part}
</div>

#### 💬 문동권 사장님 말씀
<div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px;'>
{speech_part}
</div>"""
            
            # # 음성 재생 처리
            # if st.session_state.tts_enabled:
            #     if play_requested or 'audio_played' not in st.session_state:
            #         st.session_state.search_system.speak_result(result)
            #         st.session_state.audio_played = True
            
            # 검색 기록 저장
            st.session_state.search_history.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'query': query,
                'result': formatted_result
            })
            save_message(formatted_result, "ai")
            
    except Exception as e:
        st.error(f"검색 중 오류가 발생했습니다: {str(e)}")
    finally:
        if progress_bar is not None:
            progress_bar.empty()


paint_history()

query = st.chat_input("Ask anything...")
if query:
    send_message(query, "human")
    # 프로그레스 바 생성
    progress_bar = st.progress(0)
    
    # 검색 시스템 자동 초기화
    st.session_state.search_system = StreamlitNewsSearchSystem(
        naver_client_id=naver_client_id,
        naver_client_secret=naver_client_secret,
        llm_api_key=llm_api_key,
        xi_api_key=xi_api_key,
        voice_id=voice_id
    )
    
    with st.chat_message("ai"):
        main(query)

# 세션 상태 초기화
if 'search_system' not in st.session_state:
    # 안전하게 API 키를 가져오기
    llm_api_key = st.secrets["llm_api_key"]
    naver_client_id = st.secrets["naver_client_id"]
    naver_client_secret = st.secrets["naver_client_secret"]
    xi_api_key = st.secrets["xi_api_key"]
    voice_id = st.secrets["voice_id"]
    
    # 검색 시스템 자동 초기화
    st.session_state.search_system = StreamlitNewsSearchSystem(
        naver_client_id=naver_client_id,
        naver_client_secret=naver_client_secret,
        llm_api_key=llm_api_key,
        xi_api_key=xi_api_key,
        voice_id=voice_id
    )

if 'search_history' not in st.session_state:
    st.session_state.search_history = []


with st.sidebar:
        
    # TTS 설정
    with st.expander("TTS 설정", expanded=False):
        st.session_state.tts_enabled = st.checkbox(
            "음성 출력 활성화",
            value=True,
            help="검색 결과를 음성으로 들으실 수 있습니다"
        )
        st.session_state.tts_speed = st.slider(
            "음성 속도",
            min_value=0.5,
            max_value=2.0,
            value=1.3,
            step=0.1,
            help="음성 출력 속도를 조절합니다"
        )
    
# 세션 상태 초기화 후에 사이드바 추가
with st.sidebar:
    # 사용 가이드
    st.markdown("### 🎯 사용 가이드")
    st.markdown("""
    1. 검색하고 싶은 내용을 입력하세요
    2. 검색 버튼을 클릭하세요
    3. 분석 결과가 표시되며 음성으로도 들을 수 있습니다
    """)
    
    st.markdown("---")
    
    # 시스템 상태 표시
    st.markdown("### 🔄 시스템 상태")
    if st.session_state.search_system:
        st.success("시스템이 정상 작동 중입니다")
    else:
        st.warning("시스템이 초기화되지 않았습니다")
    
    # 검색 기록
    if st.session_state.search_history:
        st.markdown(f"총 검색 횟수: {len(st.session_state.search_history)}회")