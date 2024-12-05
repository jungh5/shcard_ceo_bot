# streamlit_app.py
import hashlib
import streamlit as st
import time
from pathlib import Path
import io
import requests
import threading
from typing import List, Dict
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
import itertools
from openai import OpenAI
import os
import base64
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import openpyxl
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from matplotlib import rc
import matplotlib.font_manager as fm


# API 키 기본값 설정
llm_api_key = st.secrets["llm_api_key"]
naver_client_id = st.secrets["naver_client_id"]
naver_client_secret = st.secrets["naver_client_secret"]
xi_api_key = st.secrets["xi_api_key"]
voice_id = st.secrets["voice_id"]


st.set_page_config(
    initial_sidebar_state="collapsed",
    
)

# 커스텀 CSS 추가
st.markdown("""
    <style>
    @font-face {
        font-family: 'MaruBuBareun_hipiriBold';
         src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/naverfont_01@1.0/Bareun_hipi.woff') format('woff');
        font-weight: bold;
        font-style: normal;
    }
    .custom-title {
        font-family: 'MaruBuBareun_hipiriBold', sans-serif;
        font-size: 3em; /* 원하는 크기로 조정 */
        font-weight: bold;
    }
    .custom-title1 {
        font-family: 'MaruBuBareun_hipiriBold', sans-serif;
        font-size: 16px; /* 원하는 크기로 조정 */
        font-weight: bold
        font-style: normal;
    }
    fixed-title {
        position: fixed;
        top: 5;
        width: 100%;
        z-index: 9999;
        padding: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# 페이지 제목
st.markdown('<h1 class="custom-title"> 신한카드 신입사원 - CEO 커뮤니케이션  </h1>', unsafe_allow_html=True)
st.markdown('<h3 class="custom-title1"> 신입사원들은 궁금한 사항을 자유롭게 물어보세요 🙋‍♀️🙋‍♂️ </h3>', unsafe_allow_html=True)
    
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
            st.write("정보를 찾고 있습니다... 잠시만 기다려주세요")
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 신한카드 답변 관련 봇입니다. 회사 관련 문의나 질문이 들어왔을 때, 입력된 질문에서 핵심 검색 키워드만 추출해주세요. 쉼표로 구분된 형태로 반환해주세요."
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
                st.info("관련된 다른 키워드로 검색해보세요.")
                return []
                
        except Exception as e:
            st.error("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            return []

    def analyze_news_content(self, news_items: List[Dict], original_query: str, progress_bar) -> str:
        """뉴스 내용 분석 개선 버전"""
        try:
            st.write("뉴스 내용 분석 중...")
            progress_bar.progress(60)
            
            # 뉴스 메타데이터 추출 및 정리
            news_metadata = []
            news_contents = []
            
            for item in news_items:
                # 메타데이터와 콘텐츠 분리
                metadata = {
                    "title": item['title'],
                    "date": item['pubDate'],
                    "url": item['link']
                }
                news_metadata.append(metadata)
                
                # 전체 콘텐츠는 별도로 저장
                news_contents.append(item['full_content'])
            
            # 프롬프트 컨텍스트 강화
            system_prompt = """당신은 신한카드의 CEO와 신입사원의 소통을 돕는 챗봇입니다.
            주어진 뉴스 기사들을 분석하여 다음을 수행하세요:
            1. 사용자의 원본 질문에 직접적으로 관련된 내용을 우선적으로 찾습니다.
            2. 문동권 사장님의 실제 발언이 있다면 그대로 인용합니다.
            3. 실제 발언이 없다면 기사 내용을 바탕으로 일관된 메시지를 구성합니다.
            4. 신한카드의 전략과 방향성을 고려하여 답변합니다."""

            user_prompt = f"""원본 질문: {original_query}

    뉴스 기사 내용:
    {json.dumps(news_contents, ensure_ascii=False, indent=2)}

    기사 메타데이터:
    {json.dumps(news_metadata, ensure_ascii=False, indent=2)}

    다음 형식으로 응답해주세요:

    [문동권 사장님 말씀]
    (질문과 직접 관련된 30초 분량의 답변)

    [참고 기사]
    - 제목: (관련성 높은 순서대로)
    - 날짜: (기사 날짜)
    - URL: (기사 링크)
    - 관련 내용: (질문과 관련된 핵심 내용)

    [신입사원 가이드]
    (앞선 내용을 바탕으로 신입사원들이 참고할 수 있는 구체적인 가이드라인)"""

            progress_bar.progress(70)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
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
        """Streamlit을 사용하여 결과 음성 출력"""
        try:
            # [문동권 사장님 말씀] 섹션만 추출
            if "[문동권 사장님 말씀]" in text:
                tts_content = text.split("[문동권 사장님 말씀]")[1].split("[참고 기사]")[0].strip()
            else:
                return

            # TTS 생성 호출
            audio_path = self.generate_tts_with_elevenlabs(tts_content, self.xi_api_key, self.voice_id)

            if audio_path and Path(audio_path).exists():
                # Streamlit을 활용하여 오디오 재생
                with open(audio_path, "rb") as audio_file:
                    audio_bytes = audio_file.read()
                    st.audio(audio_bytes, format="audio/mp3")
            else:
                st.error("음성 파일을 생성하지 못했습니다.")
        except Exception as e:
            st.error(f"TTS 처리 중 오류 발생: {str(e)}")


def save_message(message_content, role, message_type="chat"):
    """
    Save message to unified history with additional metadata
    message_type can be "chat" or "analysis"
    """
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    message_entry = {
        "message": message_content,  # 메시지 내용
        "role": role,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "type": message_type
    }
    st.session_state.messages.append(message_entry)


# 현재 스크립트의 디렉토리를 기준으로 assets 폴더 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, 'static')

def get_avatar_path(role: str) -> str:
    """이미지 파일의 절대 경로를 반환"""
    image_path = os.path.join(ASSETS_DIR, f'{role}_character.png')
    if os.path.exists(image_path):
        return image_path
    print(f"Warning: Image not found at {image_path}")  # 디버깅용
    return None

def send_message(message, role, save=True):
    """Display message with appropriate avatar"""
    avatar_path = get_avatar_path('human' if role == 'human' else 'bot')
    try:
        with st.chat_message(role, avatar=avatar_path):
            st.markdown(message, unsafe_allow_html=True)
        if save:  # 메시지를 한 번만 저장
            save_message(message, role)
    except Exception as e:
        print(f"Error displaying message with avatar: {e}")
        with st.chat_message(role):
            st.markdown(message, unsafe_allow_html=True)
        if save:
            save_message(message, role)

def get_image_as_base64(image_path):
    """이미지를 Base64 문자열로 변환"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        st.error(f"이미지를 불러오는 중 오류가 발생했습니다: {e}")
        return ""

# 배경 이미지 추가
bg_image_path = "static/bg.png"  # 배경 이미지 경로
if Path(bg_image_path).exists():
    bg_image_base64 = get_image_as_base64(bg_image_path)
    st.markdown(
        f"""
        <style>
        /* 전체 페이지 배경 */
        html {{
            background-image: url("data:image/png;base64,{bg_image_base64}");
            background-size: cover;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }}

        /* 텍스트 입력창 하단 영역 (stChatInput) */
        [data-testid="stApp"]{{
            background-image: url("data:image/png;base64,{bg_image_base64}");
            background-size: cover;
    /       background: rgba(255, 255, 255, 0); /* 투명화 *
        }}
        
        /* 사이드바 배경 투명화 */
        [data-testid="stSidebar"] {{
            background: rgba(255, 255, 255, 0); /* 투명화 */
        }}
        
        /* 사이드바 배경 투명화 */
        [data-testid="stHeader"] {{
            background: rgba(255, 255, 255, 0); /* 투명화 */
        }}
        
        /* 사이드바 배경 투명화 */
        [data-testid="stBottom"] {{
            background: rgba(255, 255, 255, 0); /* 투명화 */
        }}
        
        /* 사이드바 배경 투명화 */
        [data-testid="stBottom"] > div {{
            background: rgba(255, 255, 255, 0); /* 투명화 */
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
else:
    st.warning("배경 이미지 파일이 존재하지 않습니다.")

def analyze_uploaded_file(file):
    """업로드된 파일을 처리하여 텍스트 데이터를 추출"""
    try:
        # 파일 읽기 시도
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.name.endswith('.xlsx'):
            df = pd.read_excel(file)
        else:
            st.error("지원하지 않는 파일 형식입니다.")
            return None, None

        # 데이터프레임 정보 출력
        st.write("### 업로드된 파일 정보")
        # 텍스트 데이터가 포함된 컬럼 찾기
        text_columns = []
        for col in df.columns:
            # 컬럼의 데이터 타입이 object이고 실제 텍스트가 포함된 경우 추가
            if df[col].dtype == 'object' and df[col].str.len().mean() > 10:
                text_columns.append(col)

        if not text_columns:
            st.error("텍스트 데이터를 포함한 컬럼을 찾을 수 없습니다.")
            return None, None

        # 사용자에게 분석할 컬럼 선택 옵션 제공
        selected_column = st.selectbox(
            "분석할 텍스트 컬럼을 선택하세요:",
            options=text_columns,
            help="질문 내용이 포함된 컬럼을 선택해주세요."
        )

        # 전체 텍스트 데이터 결합
        text_data = '\n'.join(df[selected_column].dropna().astype(str))

        return text_data, df

    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
        import traceback
        st.write("상세 오류:", traceback.format_exc())
        return None, None



def generate_wordcloud_from_keywords(keyword_data):
    """키워드 데이터를 기반으로 워드클라우드 생성 (한글 지원)"""
    try:
        # 키워드 데이터 확인
        if not keyword_data or not isinstance(keyword_data, list):
            st.error("유효한 키워드 데이터가 없습니다.")
            return

        # 워드 클라우드 입력 데이터 생성
        wordcloud_input = {item["keyword"]: item["count"] for item in keyword_data if "keyword" in item and "count" in item}

        if not wordcloud_input:
            st.error("키워드 데이터에 빈도가 포함되지 않았습니다.")
            return

        # 디버깅: 입력값 확인
        st.write("워드클라우드 데이터:", wordcloud_input)

        # 한글 폰트 설정 (시스템 폰트 자동 탐색)
        font_path = None
        for font in fm.findSystemFonts(fontpaths=None, fontext="ttf"):
            if "NanumGothic" in font or "Malgun" in font:  # 한글 지원 폰트 찾기
                font_path = font
                break

        if not font_path:
            st.error("한글 폰트를 찾을 수 없습니다. 시스템에 한글 폰트를 설치해주세요.")
            return

        # 워드클라우드 생성
        wordcloud = WordCloud(font_path=font_path, width=800, height=400, background_color="white").generate_from_frequencies(wordcloud_input)
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        st.pyplot(plt)

    except Exception as e:
        st.error(f"워드클라우드 생성 중 오류 발생: {e}")



def analyze_text(text_data, response_data=None):
    """텍스트 데이터를 분석하여 차트로 시각화"""
    # 키워드 빈도 분석 (텍스트 데이터로부터 생성)
    if text_data:
        word_list = text_data.split()
        word_freq = pd.Series(word_list).value_counts().head(10)
        freq_df = pd.DataFrame({"keyword": word_freq.index, "count": word_freq.values})
    elif response_data and "keyword_frequency" in response_data:
        freq_df = pd.DataFrame(response_data["keyword_frequency"])
    else:
        st.error("텍스트 데이터 또는 키워드 빈도 데이터를 찾을 수 없습니다.")
        return

    # 감성 분석 데이터
    if response_data and "sentiment_analysis" in response_data:
        sentiment_data = response_data["sentiment_analysis"]
    else:
        sentiment_data = {"positive_score": 70, "negative_score": 20, "neutral_score": 10}

    total_score = sum(sentiment_data.values())
    normalized_score = (sentiment_data["positive_score"] / total_score) * 100

    # 주제 분포 데이터
    if response_data and "topic_distribution" in response_data:
        topic_distribution = pd.DataFrame(response_data["topic_distribution"])
    else:
        topic_distribution = pd.DataFrame({
            "topic": ["주제1", "주제2", "주제3"],
            "percentage": [40, 30, 30]
        })

    # 결과 시각화
    st.markdown("### 📊 분석 결과")
    
    # 워드클라우드 생성
    st.markdown("#### 주요 키워드 워드클라우드")
    generate_wordcloud_from_keywords(freq_df.to_dict("records"))

    # 키워드 빈도수 차트
    st.markdown("#### 주요 키워드 분석")
    fig_freq = px.bar(freq_df, x="keyword", y="count", title="주요 키워드 Top 10")
    st.plotly_chart(fig_freq, use_container_width=True)
    
    # 감성 분석 게이지
    st.markdown("#### 감성 분석")
    fig_sentiment = go.Figure(go.Indicator(
        mode="gauge+number",
        value=normalized_score,
        title={'text': "긍정도 지수"},
        gauge={
            'axis': {'range': [0, 100]},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 100], 'color': "lightblue"}
            ]
        }
    ))
    st.plotly_chart(fig_sentiment, use_container_width=True)
    
    # 주제 분포 파이 차트
    st.markdown("#### 주제 분포")
    fig_topic = px.pie(topic_distribution, values="percentage", names="topic", title="주제 분포")
    st.plotly_chart(fig_topic, use_container_width=True)
    

def analyze_text_with_context(text_query: str, file_data: str, chat_history: list, search_system) -> dict:
    """파일 데이터와 채팅 이력을 활용하여 텍스트 분석 또는 일반 답변 생성"""
    try:
        # 질문 유형 분석
        query_type = analyze_query_type(text_query, search_system.client)
        
        # 파일 데이터 길이 제한 (모델의 토큰 제한 고려)
        shortened_file_data = file_data[:2000]  # 필요에 따라 조정

        # 질문에서 원하는 분석 종류 파악
        requested_analysis = determine_requested_analysis(text_query)
        st.write("요청된 분석 종류:", requested_analysis)

        # LLM에게 요청할 분석 종류를 프롬프트에 포함
        analysis_instructions = ""
        if 'keyword_frequency' in requested_analysis:
            analysis_instructions += "1. 키워드 빈도수 분석을 수행하고, 결과를 'keyword_frequency' 키에 JSON 배열로 반환하세요.\n"
        if 'sentiment_analysis' in requested_analysis:
            analysis_instructions += "2. 감성 분석을 수행하고, 결과를 'sentiment_analysis' 키에 JSON 객체로 반환하세요.\n"
        if 'topic_distribution' in requested_analysis:
            analysis_instructions += "3. 주제 분포 분석을 수행하고, 결과를 'topic_distribution' 키에 JSON 배열로 반환하세요.\n"

        if not analysis_instructions:
            analysis_instructions = "사용자의 질문에 답변하세요."

        # 파일 데이터를 항상 프롬프트에 포함
        analysis_prompt = f"""
        아래의 파일 내용과 이전 대화를 참고하여 사용자 질문에 답변해주세요.

        파일 내용:
        {shortened_file_data}

        이전 대화:
        {format_chat_history(chat_history)}

        사용자 질문:
        {text_query}

        {analysis_instructions}
        """

        # LLM 호출
        response = search_system.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 텍스트 분석 전문가이자 친절한 AI 어시스턴트입니다."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.7
        )

        raw_response = response.choices[0].message.content

        # 데이터 분석 결과가 포함된 경우 JSON 파싱 시도
        if query_type == 'data_analysis':
            # JSON 부분만 추출
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                json_content = json_match.group(0)
                try:
                    analysis_results = json.loads(json_content)
                except json.JSONDecodeError as e:
                    st.error(f"JSON 파싱 오류: {e}")
                    analysis_results = None
                return {
                    "query_type": query_type,
                    "answer": raw_response,
                    "analysis": analysis_results
                }
            else:
                # JSON이 없을 경우에도 'analysis' 키를 포함
                return {
                    "query_type": query_type,
                    "answer": raw_response,
                    "analysis": None  # 또는 빈 딕셔너리 {}
                }
        else:
            # 일반 텍스트 응답 반환
            return {
                "query_type": query_type,
                "answer": raw_response
            }

    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
        return None



def analyze_query_type(query: str, client) -> str:
    """사용자 쿼리의 유형을 분석하여 'data_analysis' 또는 'text_query'로 분류"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 질문을 'data_analysis' 또는 'text_query' 중 하나로 분류하는 전문가입니다. 질문이 데이터 파일의 내용을 기반으로 답변해야 하면 'data_analysis'로 분류하세요."},
                {"role": "user", "content": f"질문: '{query}'\n\n질문의 유형을 'data_analysis' 또는 'text_query'로만 답변해주세요."}
            ],
            temperature=0
        )
        result = response.choices[0].message.content.strip().lower()
        if 'data_analysis' in result:
            return 'data_analysis'
        else:
            return 'text_query'
    except Exception:
        return 'text_query'  # 기본값으로 'text_query' 반환


        
# 사이드바에서 텍스트 분석 챗봇 모드 추가
def create_sidebar_with_text_analysis():
    """사이드바에서 텍스트 분석 챗봇 모드를 추가합니다."""
    with st.sidebar:
        st.markdown("### 🤖 챗봇 모드 선택")
        
        # 모드 선택
        mode = st.radio(
            "원하시는 모드를 선택하세요:",
            ["기본 챗봇", "텍스트 분석 챗봇"],
            index=0,
            key="chat_mode_sidebar"  # 고유 키로 변경
        )
        
        # 세션 상태 업데이트
        st.session_state.analysis_mode = (mode == "텍스트 분석 챗봇")


def format_analysis_results(analysis_results):
    """분석 결과를 대화 이력에 저장하기 위한 포맷으로 변환"""
    formatted_result = "### 📊 텍스트 분석 결과\n\n"
    
    # 키워드 빈도수 포맷팅
    if 'keyword_frequency' in analysis_results:
        formatted_result += "#### 주요 키워드 분석\n"
        for keyword in analysis_results['keyword_frequency']:
            formatted_result += f"- {keyword['keyword']}: {keyword['count']}회\n"
        formatted_result += "\n"
    
    # 주제 분포 포맷팅
    if 'topic_distribution' in analysis_results:
        formatted_result += "#### 주제 분포\n"
        for topic in analysis_results['topic_distribution']:
            formatted_result += f"- {topic['topic']}: {topic['percentage']}%\n"
        formatted_result += "\n"
    
    # 감성 분석 포맷팅
    if 'sentiment_analysis' in analysis_results:
        sentiment = analysis_results['sentiment_analysis']
        total_score = sum(sentiment.values())
        formatted_result += "#### 감성 분석\n"
        formatted_result += f"- 긍정: {(sentiment['positive_score']/total_score)*100:.1f}%\n"
        formatted_result += f"- 부정: {(sentiment['negative_score']/total_score)*100:.1f}%\n"
        formatted_result += f"- 중립: {(sentiment['neutral_score']/total_score)*100:.1f}%\n\n"
    
    # 주요 인사이트 포맷팅
    if 'key_insights' in analysis_results:
        formatted_result += "#### 주요 인사이트\n"
        for insight in analysis_results['key_insights']:
            formatted_result += f"- {insight}\n"
    
    return formatted_result

def save_analysis_to_history(st_state, analysis_results, uploaded_filename):
    """분석 결과와 차트를 대화 이력에 저장"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 분석 결과 데이터 저장
    analysis_entry = {
        'timestamp': timestamp,
        'filename': uploaded_filename,
        'results': analysis_results,
        'type': 'analysis'  # 메시지 타입을 분석으로 표시
    }
    
    # 대화 이력에 저장
    if 'messages' not in st_state:
        st_state.messages = []
    st_state.messages.append({
        "message": analysis_entry,
        "role": "ai",
        "type": "analysis"  # 분석 타입 메시지임을 표시
    })
    
    # 검색 이력에도 저장
    if 'search_history' not in st_state:
        st_state.search_history = []
    st_state.search_history.append(analysis_entry)


def display_analysis_results(analysis_results, requested_analysis=None):
    """분석 결과를 차트와 함께 표시"""
    if requested_analysis is None:
        requested_analysis = ['keyword_frequency', 'sentiment_analysis', 'topic_distribution']
    try:
        st.markdown("### 📊 분석 결과")

        # 키워드 빈도수 분석
        if 'keyword_frequency' in requested_analysis and 'keyword_frequency' in analysis_results and analysis_results['keyword_frequency']:
            st.markdown("#### 주요 키워드 분석")
            keyword_data = analysis_results['keyword_frequency']
            if isinstance(keyword_data, list) and len(keyword_data) > 0:
                # 'frequency' 키를 'count' 키로 변경
                for item in keyword_data:
                    if 'frequency' in item:
                        item['count'] = item.pop('frequency')
                keyword_df = pd.DataFrame(keyword_data)
                # 차트 생성
                try:
                    fig_freq = px.bar(keyword_df, x='keyword', y='count', title="주요 키워드 Top 10", labels={'count': '빈도수', 'keyword': '키워드'})
                    st.plotly_chart(fig_freq, use_container_width=True)
                except Exception as e:
                    st.error("키워드 빈도수 차트를 생성하는 중 오류가 발생했습니다.")
                    print(f"키워드 빈도수 차트 생성 중 오류 발생: {str(e)}")
                    print("키워드 데이터:", keyword_df)

        # 감성 분석
        if 'sentiment_analysis' in requested_analysis and 'sentiment_analysis' in analysis_results:
            st.markdown("#### 감성 분석")
            try:
                sentiment = analysis_results['sentiment_analysis']
                total_score = sum(sentiment.values())
                if total_score > 0:
                    positive_ratio = (sentiment.get('positive_score', 0) / total_score) * 100
                    fig_sentiment = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=positive_ratio,
                        title={'text': "긍정도 비율"},
                        gauge={
                            'axis': {'range': [0, 100]},
                            'steps': [
                                {'range': [0, 50], 'color': "lightgray"},
                                {'range': [50, 100], 'color': "lightblue"}
                            ]
                        }
                    ))
                    st.plotly_chart(fig_sentiment, use_container_width=True)
                else:
                    st.error("감성 분석 결과의 총 점수가 0입니다.")
            except Exception as e:
                st.error("감성 분석 차트를 생성하는 중 오류가 발생했습니다.")
                print(f"감성 분석 차트 생성 중 오류 발생: {str(e)}")
                print("감성 분석 데이터:", sentiment)

        # 주제 분포 분석
        if 'topic_distribution' in requested_analysis and 'topic_distribution' in analysis_results and analysis_results['topic_distribution']:
            st.markdown("#### 주제 분포")
            try:
                topic_data = analysis_results['topic_distribution']
                if isinstance(topic_data, list) and len(topic_data) > 0:
                    # 'frequency' 또는 'count' 키를 'count'로 통일
                    for item in topic_data:
                        if 'frequency' in item:
                            item['count'] = item.pop('frequency')
                    topic_df = pd.DataFrame(topic_data)
                    # 'percentage' 계산
                    if 'count' in topic_df.columns:
                        total_count = topic_df['count'].sum()
                        topic_df['percentage'] = (topic_df['count'] / total_count) * 100
                    else:
                        st.error("주제 분포 데이터에 'count' 값이 없습니다.")
                        return
                    # 차트 생성
                    if not topic_df.empty and 'topic' in topic_df.columns and 'percentage' in topic_df.columns:
                        fig_topic = px.pie(topic_df, values='percentage', names='topic', title="주제별 분포")
                        st.plotly_chart(fig_topic, use_container_width=True)
                    else:
                        st.error("주제 분포 데이터에 필요한 열이 없습니다.")
                else:
                    st.error("주제 분포 데이터가 유효하지 않습니다.")
            except Exception as e:
                st.error("주제 분포 차트를 생성하는 중 오류가 발생했습니다.")
                print(f"주제 분포 차트 생성 중 오류 발생: {str(e)}")
                print("주제 분포 데이터:", topic_df)

        # 주요 인사이트 표시 (필요 시)
        if 'key_insights' in analysis_results:
            st.markdown("#### 주요 인사이트")
            insights = analysis_results['key_insights']
            if isinstance(insights, list):
                for insight in insights:
                    st.markdown(f"- {insight}")

    except Exception as e:
        st.error("분석 결과를 표시하는 중 오류가 발생했습니다.")
        print(f"분석 결과 표시 중 오류 발생: {str(e)}")
        print("분석 결과 데이터:", analysis_results)



def format_chat_history(history):
    """채팅 이력을 문자열로 포맷팅"""
    formatted = []
    for item in history:
        if isinstance(item, dict):
            role = item.get('role', '')
            message = item.get('message', '')
            formatted.append(f"{role}: {message}")
    return "\n".join(formatted)


def display_combined_analysis(result):
    if not result:
        return

    # 답변 표시
    st.markdown("### 💬 답변")
    st.markdown(result.get("answer", ""))

    # 분석 결과가 있는 경우 차트 표시
    if result.get("query_type") == "data_analysis" and "analysis" in result:
        st.markdown("### 📊 분석 결과")
        analysis_results = result["analysis"]

        # 키워드 빈도수 차트
        if 'keyword_frequency' in analysis_results:
            st.markdown("#### 주요 키워드 분석")
            keyword_df = pd.DataFrame(analysis_results['keyword_frequency'])
            fig = px.bar(keyword_df, x="keyword", y="count", 
                        title="키워드 빈도수",
                        labels={"count": "출현 횟수", "keyword": "키워드"})
            st.plotly_chart(fig, use_container_width=True)
        
        # 주제 분포 파이 차트
        if 'topic_distribution' in analysis_results:
            st.markdown("#### 주제 분포")
            topic_df = pd.DataFrame(analysis_results['topic_distribution'])
            fig = px.pie(topic_df, values="percentage", names="topic", 
                        title="주제별 분포")
            st.plotly_chart(fig, use_container_width=True)
        
        # 감성 분석 게이지
        if 'sentiment_analysis' in analysis_results:
            st.markdown("#### 감성 분석")
            sentiment = analysis_results['sentiment_analysis']
            total_score = sum(sentiment.values())
            positive_ratio = (sentiment["positive_score"] / total_score) * 100
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=positive_ratio,
                title={'text': "긍정도 비율"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 100], 'color': "lightblue"}
                    ]
                }
            ))
            st.plotly_chart(fig, use_container_width=True)
        
        # 주요 인사이트
        if 'key_insights' in analysis_results:
            st.markdown("#### 주요 인사이트")
            for insight in analysis_results['key_insights']:
                st.markdown(f"- {insight}")


def main_analysis_chat():
    """텍스트 분석 챗봇 메인 함수"""
    st.markdown("### 📂 파일 업로드")
    uploaded_file = st.file_uploader("분석할 텍스트 파일을 업로드하세요 (CSV 또는 XLSX)", 
                                   type=["csv", "xlsx"])
    
    # 파일 업로드 및 초기 분석
    if uploaded_file and "file_data" not in st.session_state:
        file_analysis_result = analyze_uploaded_file(uploaded_file)
        if file_analysis_result:
            text_data, df = file_analysis_result
            st.session_state.file_data = text_data
            st.session_state.file_df = df
            st.success("파일이 성공적으로 업로드되었습니다.")
    
        # 채팅 인터페이스
    if st.session_state.analysis_mode and "file_data" in st.session_state:
        # 텍스트 분석 챗봇 모드
        query = st.chat_input("분석 모드에서 질문을 입력하세요", key="analysis_input")
        if query:
            st.session_state.analysis_history.append({"role": "user", "content": query})
            send_message(query, "human")  # 사용자 메시지 출력
            with st.spinner("분석 중..."):
                result = analyze_text_with_context(
                    text_query=query,
                    file_data=st.session_state.file_data,
                    chat_history=st.session_state.messages,
                    search_system=st.session_state.search_system,
                )
                with st.chat_message("ai", avatar="static/bot_character.png"):
                    display_combined_analysis(result)
                save_message(result.get("answer", ""), "ai")  # 분석 결과 저장

        # 입력값 처리
        if query:
            save_message(query, "user")  # 히스토리 저장 자동화
            send_message(query, "human")  # 사용자 메시지 표시

            # 모드별 처리
            if st.session_state.analysis_mode:
                main_analysis_chat()  # 분석 모드
            else:
                process_regular_chat(query, progress_bar=None)  # 일반 모드


            
            # 분석 수행
            with st.spinner("분석 중..."):
                result = analyze_text_with_context(
                    text_query=query,
                    file_data=st.session_state.file_data,
                    chat_history=st.session_state.messages,
                    search_system=st.session_state.search_system
                )
                
                # 분석 결과 표시
                with st.chat_message("ai", avatar="static/bot_character.png"):
                    display_combined_analysis(result)
                
                # 대화 이력 저장
                save_message(result.get("answer", ""), "ai")
    else:
        st.info("파일을 업로드하면 대화를 시작할 수 있습니다.")
            

# Initialize session state with unified history
def initialize_session_state():
    if 'initialized' not in st.session_state:
        st.session_state.messages = []  # Unified message history
        st.session_state.search_history = []  # Unified search history
        st.session_state.file_data = None
        st.session_state.file_df = None
        st.session_state.tts_enabled = True
        st.session_state.audio_played = False
        st.session_state.query = None  # query 초기화 추가
        st.session_state.search_system = StreamlitNewsSearchSystem(
            naver_client_id=naver_client_id,
            naver_client_secret=naver_client_secret,
            llm_api_key=llm_api_key,
            xi_api_key=xi_api_key,
            voice_id=voice_id
        )
        st.session_state.analysis_mode = False
        st.session_state.initialized = True

# 초기화 함수를 스크립트 초기에 실행
initialize_session_state()
    
        
# 캐릭터 이미지 경로
user_img = "static/human_character.png"  # 사용자 캐릭터 이미지 파일 경로
bot_img = "static/bot_character.png"  # 챗봇 캐릭터 이미지 파일 경로

if not Path(user_img).exists():
    raise FileNotFoundError(f"File not found: {user_img}")

# 메시지를 이미지와 함께 출력하는 함수
def send_message_with_image(message, role, image_path, save=True):
    """이미지를 포함하여 메시지를 표시"""
    message_html = f"""
    <div style="display: flex; align-items: flex-start; margin-bottom: 10px;">
        <img src="{image_path}" alt="{role}" style="width: 50px; height: 50px; margin-right: 10px; border-radius: 50%;">
        <div style="background-color: #f1f1f1; padding: 10px; border-radius: 10px; max-width: 80%;">
            {message}
        </div>
    </div>
    """
    st.markdown(message_html, unsafe_allow_html=True)
    if save:
        save_message(message, role)

# 메시지 기록 표시 함수
def paint_history():
    """대화 이력 표시"""
    if "messages" in st.session_state:
        for message in st.session_state.messages:
            if isinstance(message, dict):
                role = message.get("role", "")
                content = message.get("message", "")
                
                # 메시지 타입에 따른 처리
                if message.get("type") == "analysis":
                    # st.chat_message 내부에서는 텍스트 메시지만 표시
                    if isinstance(content, dict):
                        # 답변 텍스트 표시
                        if "answer" in content and content["answer"]:
                            send_message(content["answer"], role, save=False)
                        # 분석 결과 표시 (st.chat_message 바깥에서)
                        if "analysis" in content and content["analysis"]:
                            # 이전에 요청된 분석 종류를 복원하거나 기본값 설정
                            requested_analysis = determine_requested_analysis(content.get("answer", ""))
                            display_analysis_results(content["analysis"], requested_analysis)
                    else:
                        # 일반 텍스트로 메시지 표시
                        send_message(content, role, save=False)
                else:
                    # 일반 채팅 메시지 표시
                    send_message(content, role, save=False)



def extract_section(text, start_marker, end_marker=None):
    """텍스트에서 특정 섹션을 추출하는 함수"""
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
        
        return content.strip()
    except Exception:
        return None
    

def process_regular_chat(query, progress_bar):
    """기존 챗봇 모드 처리"""
    try:
        if 'audio_played' in st.session_state:
            del st.session_state.audio_played
            
        keywords = st.session_state.search_system.extract_keywords(query, progress_bar)
        news_items = st.session_state.search_system.search_with_progressive_keywords(
            keywords, progress_bar
        )
        
        if not news_items:
            alt_response = st.session_state.search_system.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 신한카드의 CEO 문동권 사장입니다..."},
                    {"role": "user", "content": query}
                ],
                temperature=0.7
            ).choices[0].message.content

            st.markdown(f"#### 💬 AI답변\n{alt_response}")
            save_message(alt_response, "ai")
            st.session_state.search_history.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'query': query,
                'result': f"💬 AI답변: {alt_response}"
            })
            return

        result = st.session_state.search_system.analyze_news_content(
            news_items, query, progress_bar
        )
        
        if result:
            st.session_state.current_result = result
            st.markdown("### 📊 분석 결과")
            
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
                    st.markdown(formatted_ref, unsafe_allow_html=True)
                
                if guide_part:
                    st.markdown("#### 🎯 신입사원 가이드")
                    st.markdown(f"""
                    <div style='background-color: #e8f4f9; padding: 20px; border-radius: 10px;'>
                        {guide_part}
                    </div>
                    """, unsafe_allow_html=True)
                
                if speech_part:
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <img src="data:image/png;base64,{get_image_as_base64('static/bot_character.png')}" 
                            alt="Bot Icon" 
                            style="width: 30px; height: 30px; margin-right: 10px; border-radius: 50%;">
                        <h3 style="margin: 0; display: inline;">AI문동권 사장님 말씀</h3>
                    </div>
                    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px;">
                        {speech_part}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.session_state.tts_enabled and 'audio_played' not in st.session_state:
                        st.session_state.search_system.speak_result(result)
                        st.session_state.audio_played = True
            
            # 검색 기록 저장
            formatted_result = f"""### 📊 분석 결과\n\n"""
            if ref_part:
                formatted_result += f"""#### 📰 참고 기사\n{formatted_ref}\n\n"""
            if guide_part:
                formatted_result += f"""#### 🎯 신입사원 가이드\n{guide_part}\n\n"""
            if speech_part:
                formatted_result += f"""#### 💬 문동권 사장님 말씀\n{speech_part}"""
            
            # 대화 이력에 한 번만 저장
            st.session_state.search_history.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'query': query,
                'result': formatted_result
            })
            save_message(formatted_result, "ai")
            return formatted_result
            
    except Exception as e:
        st.error(f"처리 중 오류 발생: {str(e)}")
        return None


def display_bot_section_with_image(title, bot_image_path, content):
    """아이콘 대신 이미지를 사용하여 섹션을 표시"""
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <img src="{bot_image_path}" alt="Bot Icon" style="width: 30px; height: 30px; margin-right: 10px; border-radius: 50%;">
        <h3 style="margin: 0; display: inline;">{title}</h3>
    </div>
    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px;ƒ">
        {content}
    </div>
    """, unsafe_allow_html=True)

    if uploaded_file:
        file_analysis_result = analyze_uploaded_file(uploaded_file)
        if file_analysis_result:  # 유효한 파일만 처리
            text_data, df = file_analysis_result
            st.success("파일이 성공적으로 업로드되었습니다.")

            # 분석 버튼 추가
            if st.button("분석 시작"):
                with st.spinner("LLM을 통해 분석 중... 잠시만 기다려주세요."):
                    # LLM에 텍스트 데이터 전달
                    llm_prompt = f"""
                    아래 텍스트 데이터를 분석하고, 결과를 반드시 **JSON으로만** 반환하세요. 
                    JSON 외의 텍스트는 포함하지 마세요. 반환 값은 문자열이 아니며 JSON 형식이어야 합니다.

                    데이터:
                    {text_data[:1000]} 
                    
                    분석 요구사항:
                    1. 키워드 빈도수 분석: "keyword_frequency"에 JSON 배열 형태로 반환하세요.
                    2. 주제 분포: "topic_distribution"에 JSON 배열 형태로 반환하세요.
                    3. 감성 분석: "sentiment_analysis"에 JSON 객체로 긍정, 부정, 중립 비율을 반환하세요.
                    4. 주요 인사이트: 질문에서 영감을 얻을만한 것들을 "key_insights"에 JSON 배열로 반환하세요.

                    JSON 형식 예:
                    {{
                        "keyword_frequency": [
                            {{"keyword": "example", "count": 10}},
                            ...
                        ],
                        "topic_distribution": [
                            {{"topic": "example_topic", "percentage": 50}},
                            ...
                        ],
                        "sentiment_analysis": {{
                            "positive_score": 60,
                            "negative_score": 30,
                            "neutral_score": 10
                        }},
                        "key_insights": [
                            "Insight 1",
                            "Insight 2"
                        ]
                    }}
"""
                    try:
                        response = st.session_state.search_system.client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "당신은 텍스트 데이터를 분석하고 시각화하는 전문가입니다."},
                                {"role": "user", "content": llm_prompt}
                            ],
                            temperature=0.2
                        )
                        

                        # LLM 응답 처리
                        raw_response = response.choices[0].message.content
                        analysis_results = json.loads(raw_response)

                        # 결과 시각화 함수 호출
                        st.markdown("### 📊 분석 결과")
                        # 실시간 분석 결과 표시
                        display_analysis_results(analysis_results, uploaded_file.name)
                        
                        # 분석 결과를 대화 이력에 저장
                        save_analysis_to_history(
                            st_state=st.session_state,
                            analysis_results=analysis_results,
                            uploaded_filename=uploaded_file.name
                        )
                    
                        # 저장 완료 메시지
                        st.success("분석 결과가 대화 이력에 저장되었습니다.")

                    except json.JSONDecodeError as e:
                        st.error(f"JSON 파싱 오류: {e}")
                        st.write("LLM 응답 내용:", response.choices[0].message.content)
                    except Exception as e:
                        st.error(f"분석 중 오류가 발생했습니다: {e}")

                        # 결과 시각화
                        st.markdown("### 📊 텍스트 분석 결과")

                        # 키워드 빈도수
                        st.markdown("#### 주요 키워드 분석")
                        keyword_df = pd.DataFrame(analysis_results['keyword_frequency'])
                        keyword_chart = px.bar(keyword_df, x="keyword", y="count", title="키워드 빈도수")
                        st.plotly_chart(keyword_chart, use_container_width=True)

                        # 주제 분포
                        st.markdown("#### 주제 분포")
                        topic_df = pd.DataFrame(analysis_results['topic_distribution'])
                        topic_chart = px.pie(topic_df, values="percentage", names="topic", title="주제 분포")
                        st.plotly_chart(topic_chart, use_container_width=True)

                        # 감성 분석
                        st.markdown("#### 감성 분석")
                        sentiment = analysis_results['sentiment_analysis']
                        total_score = sum(sentiment.values())
                        positive_ratio = (sentiment["positive_score"] / total_score) * 100

                        sentiment_chart = go.Figure(go.Indicator(
                            mode="gauge+number",
                            value=positive_ratio,
                            title={'text': "긍정도 비율"},
                            gauge={
                                'axis': {'range': [0, 100]},
                                'steps': [
                                    {'range': [0, 50], 'color': "lightgray"},
                                    {'range': [50, 100], 'color': "lightblue"}
                                ]
                            }
                        ))
                        st.plotly_chart(sentiment_chart, use_container_width=True)

                        # 주요 인사이트
                        st.markdown("#### 주요 인사이트")
                        for insight in analysis_results['key_insights']:
                            st.markdown(f"- {insight}")

                    except Exception as e:  # 이 줄의 들여쓰기가 맞지 않아 오류 발생
                        st.error(f"LLM 분석 중 오류 발생: {e}")

        else:
            st.error("파일을 처리하지 못했습니다. 다시 시도해주세요.")

        
# 세션 상태 초기화 후에 사이드바 추가
with st.sidebar:
    # 사용 가이드
    st.markdown("### 🎯 사용 가이드")
    st.markdown("""
    1. 회사에 문의하고 싶은 내용을 입력하세요
    2. 검색 버튼을 클릭하세요
    3. 분석 결과가 표시되며 음성으로도 들을 수 있습니다
    """)
    
    st.markdown("---")
    
    # 검색 기록
    if st.session_state.search_history:
        st.markdown(f"총 검색 횟수: {len(st.session_state.search_history)}회")

def process_query(query, progress_bar):
    """
    사용자 입력(query)을 처리하여 키워드 추출, 뉴스 검색, 결과 분석 및 표시.
    """
    # 키워드 추출
    keywords = st.session_state.search_system.extract_keywords(query, progress_bar)

    # 뉴스 검색
    news_items = st.session_state.search_system.search_with_progressive_keywords(
        keywords, progress_bar
    )

    # 검색 결과가 없는 경우
    if not news_items:
        handle_no_results(query)
        return

    # 뉴스 내용 분석
    result = st.session_state.search_system.analyze_news_content(
        news_items, query, progress_bar
    )

    # 분석 결과 표시
    if result:
        display_analysis_results(result)

def handle_no_results(query):
    """검색 결과가 없을 때의 처리"""
    try:
        response = st.session_state.search_system.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 신한카드의 CEO 문동권 사장입니다. 질문에 일반적인 답변을 제공합니다."},
                {"role": "user", "content": query}
            ],
            temperature=0.4
        )
        
        alt_response = response.choices[0].message.content
        st.markdown(f"#### 💬 AI답변\n{alt_response}")
        
        # 검색 이력에 저장
        st.session_state.search_history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'query': query,
            'result': f"💬 AI답변: {alt_response}"
        })
        
        return alt_response
        
    except Exception as e:
        st.error(f"대체 답변 생성 중 오류 발생: {str(e)}")
        return None

def display_analysis_sections(result):
    """
    분석 결과를 UI에 표시.
    """
    # 섹션 추출
    speech_part = extract_section(result, "[문동권 사장님 말씀]", "[참고 기사]")
    ref_part = extract_section(result, "[참고 기사]", "[신입사원 가이드]")
    guide_part = extract_section(result, "[신입사원 가이드]")

    # 참고 기사 섹션
    if ref_part:
        display_reference_section(ref_part)

    # 가이드 섹션
    if guide_part:
        display_guide_section(guide_part)

    # 문동권 사장님 말씀
    if speech_part:
        display_speech_section(speech_part)

    # 결과 저장
    save_analysis_result(result, ref_part, guide_part, speech_part)

def display_reference_section(ref_part):
    """
    참고 기사 섹션 표시.
    """
    st.markdown("#### 📰 참고 기사")
    lines = ref_part.split('\n')
    formatted_lines = []
    for line in lines:
        if "URL:" in line:
            url_parts = line.split("URL:")
            if len(url_parts) > 1:
                url = url_parts[1].strip()
                formatted_lines.append(f"- URL: <a href='{url}' target='_blank'>{url}</a>")
        else:
            formatted_lines.append(f"- {line}")
    st.markdown('<br>'.join(formatted_lines), unsafe_allow_html=True)

def display_guide_section(guide_part):
    """
    신입사원 가이드 섹션 표시.
    """
    st.markdown("#### 🎯 신입사원 가이드")
    st.markdown(f"""
    <div style='background-color: #e8f4f9; padding: 20px; border-radius: 10px;'>
        {guide_part}
    </div>
    """, unsafe_allow_html=True)

def display_speech_section(speech_part):
    """
    문동권 사장님 말씀 섹션 표시 및 TTS 출력.
    """
    bot_image_path = os.path.join(ASSETS_DIR, 'bot_character.png')
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <img src="data:image/png;base64,{get_image_as_base64(bot_image_path)}" 
            alt="Bot Icon" 
            style="width: 30px; height: 30px; margin-right: 10px; border-radius: 50%;">
        <h3 style="margin: 0; display: inline;">AI문동권 사장님 말씀</h3>
    </div>
    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px;">
        {speech_part}
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.tts_enabled and 'audio_played' not in st.session_state:
        st.session_state.search_system.speak_result(speech_part)
        st.session_state.audio_played = True

def save_analysis_result(result, ref_part, guide_part, speech_part, query=None):
    """분석 결과를 세션 상태에 저장"""
    formatted_result = "### 📊 분석 결과\n\n"
    if ref_part:
        formatted_result += f"#### 📰 참고 기사\n{ref_part}\n\n"
    if guide_part:
        formatted_result += f"#### 🎯 신입사원 가이드\n{guide_part}\n\n"
    if speech_part:
        formatted_result += f"#### 💬 문동권 사장님 말씀\n{speech_part}"

    st.session_state.search_history.append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'query': query,  # query 파라미터 사용
        'result': formatted_result
    })
    save_message(formatted_result, "ai")

        
def main():
    initialize_session_state()
    create_sidebar_with_text_analysis()
    
    # 기존 대화 이력 표시
    paint_history()

    if st.session_state.analysis_mode:
        # 분석 모드 처리
        handle_analysis_mode()
    else:
        # 일반 모드 처리
        handle_regular_mode()
            
def handle_file_upload():
    """파일 업로드 UI 처리"""
    st.markdown("---")
    st.markdown("### 📂 파일 업로드")
    uploaded_file = st.file_uploader(
        "분석할 텍스트 파일을 업로드하세요 (CSV 또는 XLSX)", 
        type=["csv", "xlsx"],
        key="file_uploader_analysis"
    )
    if uploaded_file:
        process_uploaded_file(uploaded_file)
        

def handle_analysis_mode():
    """분석 모드 UI 및 로직 처리"""
    st.markdown("---")
    st.markdown("### 📂 파일 업로드")
    
    uploaded_file = st.file_uploader(
        "분석할 텍스트 파일을 업로드하세요 (CSV 또는 XLSX)", 
        type=["csv", "xlsx"],
        key="file_uploader_analysis"
    )

    if uploaded_file:
        file_analysis_result = analyze_uploaded_file(uploaded_file)
        if file_analysis_result:
            text_data, df = file_analysis_result
            st.success("파일이 성공적으로 업로드되었습니다.")
            st.session_state.file_data = text_data
            st.session_state.file_df = df

    # 파일이 업로드된 경우에만 채팅 입력 표시
    if st.session_state.get("file_data") is not None:
        query = st.chat_input(
            "파일에 대해 궁금한 점을 물어보세요",
            key="chat_input_analysis"
        )
        if query:
            # 사용자 메시지 표시
            send_message(query, "human")
            
            # 분석 수행 및 결과 표시
            with st.spinner("분석 중..."):
                result = analyze_text_with_context(
                    query,
                    st.session_state.file_data,
                    st.session_state.messages,
                    st.session_state.search_system
                )

            # 요청된 분석 종류 파악
            requested_analysis = determine_requested_analysis(query)

            # AI 응답 메시지 컨테이너
            with st.chat_message("ai", avatar="static/bot_character.png"):
                if result:
                    if result["query_type"] == "data_analysis":
                        if "analysis" in result and result["analysis"]:
                            display_analysis_results(result["analysis"], requested_analysis)
                        else:
                            st.markdown("### 답변")
                            st.markdown(result["answer"])
                            st.warning("분석 결과를 추출하지 못했습니다.")
                    else:
                        st.markdown("### 답변")
                        st.markdown(result["answer"])
                        if "key_points" in result:
                            st.markdown("### 주요 포인트")
                            for point in result["key_points"]:
                                st.markdown(f"- {point}")
                            
                if result:
                    # 결과를 대화 이력에 저장
                    # 메시지 내용으로 result['answer']와 result['analysis']를 포함한 딕셔너리를 저장합니다.
                    message_content = {
                        "answer": result.get("answer", ""),
                        "analysis": result.get("analysis", {})
                    }
                    save_message(message_content, "ai", "analysis")


def determine_requested_analysis(question: str) -> List[str]:
    """사용자의 질문을 기반으로 원하는 분석 종류를 반환"""
    analysis_types = []
    if any(word in question for word in ['키워드', '워드 클라우드', '단어', '빈도']):
        analysis_types.append('keyword_frequency')
    if any(word in question for word in ['긍정', '부정', '감정', '감성']):
        analysis_types.append('sentiment_analysis')
    if any(word in question for word in ['카테고리', '주제', '토픽', '분류']):
        analysis_types.append('topic_distribution')
    # 분석 종류를 명시적으로 요청하지 않은 경우 기본적으로 모두 포함
    if not analysis_types:
        analysis_types = ['keyword_frequency', 'sentiment_analysis', 'topic_distribution']
    return analysis_types


def process_analysis_query(query):
    """분석 모드 쿼리 처리"""
    send_message(query, "human")
    with st.spinner("분석 중..."):
        result = analyze_text_with_context(
            text_query=query,
            file_data=st.session_state.file_data,
            chat_history=st.session_state.messages,
            search_system=st.session_state.search_system
        )
        with st.chat_message("ai", avatar="static/bot_character.png"):
            display_combined_analysis(result)
        save_message(result, "ai", "analysis")

def process_regular_query(query):
    """일반 모드 쿼리 처리"""
    send_message(query, "human")  # 사용자 메시지 저장 및 표시
    
    progress_bar = st.progress(0)
    with st.chat_message("ai", avatar="static/bot_character.png"):
        process_regular_chat(query, progress_bar)  

def handle_regular_mode():
    """일반 모드 UI 및 로직 처리"""
    query = st.chat_input(
    "궁금한 사항을 자유롭게 물어보세요",
    key="chat_input_regular_mode"  # 고유한 키 사용
    )

    if query:
        process_regular_query(query)

if __name__ == "__main__":
    main()