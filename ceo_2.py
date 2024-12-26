import streamlit as st
import pandas as pd
from datetime import datetime
import json
from openai import OpenAI
import base64
from pathlib import Path
import os
import plotly.express as px
import plotly.graph_objects as go
import time

# API 키 설정
llm_api_key = st.secrets["llm_api_key"]

# 현재 스크립트의 디렉토리를 기준으로 assets 폴더 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, 'static')

# 페이지 설정
st.set_page_config(
    initial_sidebar_state="expanded",
)

# Google Fonts 로드 (최초 한 번만 로드)
st.markdown("""
<head>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Do+Hyeon&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jua&display=swap">
<link href="https://fonts.googleapis.com/css2?family=Nanum+Gothic&display=swap" rel="stylesheet">
<style>
.custom-title {
    font-family: 'Jua', sans-serif !important;  
    font-size: 40px !important;
    font-weight: 700 !important;
}
.custom-title1 {
    font-family: 'Do Hyeon', sans-serif !important; 
    font-size: 20px !important;
    font-weight: 10% !important;
}
body, html {
    font-family: 'Nanum Gothic', sans-serif;
}
</style>
</head>
""", unsafe_allow_html=True)

# 페이지 제목
st.markdown('<div class="custom-title">CEO - 공채 15기 신입사원 커뮤니케이션</div>', unsafe_allow_html=True)


def get_image_as_base64(image_path):
    """이미지를 Base64 문자열로 변환"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        st.error(f"이미지를 불러오는 중 오류가 발생했습니다: {e}")
        return ""

# 배경 이미지 추가
bg_image_path = "static/bg.png"
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
        [data-testid="stApp"] {{
            background-image: url("data:image/png;base64,{bg_image_base64}");
            background-size: cover;
        }}
        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stBottom"] {{
            background: rgba(255, 255, 255, 0);
        }}
        
        /* 메인 컨텐츠 영역 배경색 설정 */
        .stMain.st-emotion-cache-bm2z3a.ekr3hml1 {{
            background-color: rgb(255, 255, 255) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

def initialize_session_state():
    """세션 상태 초기화"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'file_data' not in st.session_state:
        st.session_state.file_data = None
    if 'data_list' not in st.session_state:
        st.session_state.data_list = None
    if 'client' not in st.session_state:
        st.session_state.client = OpenAI(api_key=llm_api_key)

def analyze_uploaded_file(file):
    """업로드된 파일 분석"""
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.name.endswith('.xlsx'):
            df = pd.read_excel(file)
        else:
            st.error("지원하지 않는 파일 형식입니다.")
            return None, None, None

        text_columns = [col for col in df.columns if df[col].dtype == 'object']
        if not text_columns:
            st.error("텍스트 데이터를 포함한 컬럼을 찾을 수 없습니다.")
            return None, None, None

        # 고정된 컬럼명 사용
        author_col = "이름"  # 고정된 작성자 컬럼명
        question_col = "질문"  # 고정된 질문 컬럼명

        # 데이터 리스트 생성
        data_list = []
        for idx, row in df.iterrows():
            author = row[author_col] if not pd.isna(row[author_col]) else ""
            question_text = row[question_col] if not pd.isna(row[question_col]) else ""
            data_list.append({
                "author": str(author),
                "question": str(question_text)
            })

        # 분석용 텍스트 데이터
        text_data = '\n'.join(df[question_col].dropna().astype(str).tolist())
        return text_data, data_list, df

    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
        return None, None, None

def analyze_text_with_context(text_query: str, file_data: str, data_list: list):
    """텍스트 분석 및 응답 생성"""
    try:
        # 실제 데이터 계산
        unique_authors = set(item["author"] for item in data_list if item["author"])
        total_questions = len(data_list)
        author_count = len(unique_authors)
        authors_list = sorted(list(unique_authors))

        # 분석 요청인지 확인
        is_analysis_request = any(keyword in text_query.lower() for keyword in [
            '차트'
        ])

        # 프롬프트 설정
        if is_analysis_request:
            prompt = f"""
            신한카드 신입사원들의 총 {total_questions}개의 질문을 정확히 5개의 카테고리로 분류해주세요.
            반드시 아래 JSON 형식으로 작성해주세요.

            데이터:
            {json.dumps(data_list, ensure_ascii=False)}

            다음과 같은 JSON 형식으로 정확하게 반환해주세요:
            {{
                "answer": "신입사원들의 질문을 5개 카테고리로 분석한 결과입니다.",
                "categories": [
                    {{
                        "category": "카테고리1",
                        "count": 20,
                        "percentage": 20.0
                    }},
                    {{
                        "category": "카테고리2",
                        "count": 30,
                        "percentage": 30.0
                    }},
                    {{
                        "category": "카테고리3",
                        "count": 25,
                        "percentage": 25.0
                    }},
                    {{
                        "category": "카테고리4",
                        "count": 15,
                        "percentage": 15.0
                    }},
                    {{
                        "category": "카테고리5",
                        "count": 10,
                        "percentage": 10.0
                    }}
                ]
            }}

            규칙:
            1. 반드시 위의 JSON 형식을 정확히 따라주세요
            2. answer는 한 문장으로 작성해주세요
            3. count는 각 카테고리에 속한 질문의 개수입니다
            4. percentage는 전체 질문 중 해당 카테고리가 차지하는 비율입니다
            5. 모든 카테고리의 count 합은 {total_questions}이어야 합니다
            6. 모든 카테고리의 percentage 합은 100.0이어야 합니다
            7. JSON 형식 외의 다른 텍스트는 포함하지 마세요
            """
            
            # 분석 요청은 스트리밍 없이 처리
            response = st.session_state.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 데이터 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                stream=False
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                
                # 분석 결과 텍스트 조합
                response_text = f"### 분석 결과\n{result['answer']}\n\n#### 카테고리별 분포\n"
                for category in result["categories"]:
                    response_text += f"- **{category['category']}**: {category['count']}개 ({category['percentage']}%)\n"

                # 파이 차트 생성
                if "categories" in result:
                    df = pd.DataFrame(result["categories"])
                    fig = px.pie(
                        df, 
                        values='percentage', 
                        names='category',
                        title='질문 카테고리 분포',
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )

                    # 한글 폰트를 Plotly 차트에 적용
                    fig.update_layout(
                        title=dict(
                            text='질문 카테고리 분포',
                            font=dict(size=20, family="Nanum Gothic")
                        ),
                        font=dict(
                            family="Nanum Gothic",
                            size=14
                        )
                    )

                    fig.update_traces(
                        textfont=dict(
                            family="Nanum Gothic",
                            size=14
                        )
                    )
                    
                    # 텍스트와 차트를 함께 표시
                    with st.chat_message("assistant", avatar=os.path.join(ASSETS_DIR, 'bot_character.png')):
                        st.markdown(response_text)
                        st.plotly_chart(fig)
                        
                    # 히스토리용 차트를 실시간 차트와 동일한 설정으로 생성
                    history_fig = px.pie(
                        df, 
                        values='percentage', 
                        names='category',
                        title='질문 카테고리 분포',
                        color_discrete_sequence=px.colors.qualitative.Set3  # 실시간 차트와 동일한 색상
                    )

                    # 실시간 차트와 동일한 폰트 설정 적용
                    history_fig.update_layout(
                        title=dict(
                            text='질문 카테고리 분포',
                            font=dict(size=20, 
                            family="Nanum Gothic, Malgun Gothic, Arial Unicode MS, Arial")
                        ),
                        font=dict(
                            family="Nanum Gothic, Malgun Gothic, Arial Unicode MS, Arial",
                            size=14
                        )
                    )

                    history_fig.update_traces(
                        textfont=dict(
                            family="Nanum Gothic, Malgun Gothic, Arial Unicode MS, Arial",
                            size=14
                        )
                    )

                    # 히스토리용 차트를 이미지로 변환
                    chart_bytes = history_fig.to_image(
                        format="png",
                        width=800,
                        height=600,
                        scale=2,
                        engine="kaleido"
                    )
                    chart_base64 = base64.b64encode(chart_bytes).decode("utf-8")
                    
                else:
                    chart_base64 = None

                # 답변 표시 및 히스토리에 저장
                # st.markdown(response_text, unsafe_allow_html=True)
                save_message(response_text, "assistant", image_base64=chart_base64)
                
                return result['answer']
                
            except json.JSONDecodeError as e:
                st.error(f"JSON 파싱 중 오류가 발생했습니다: {str(e)}")
                return None

        else:
            # 일반 질문일 경우
            # 응답 템플릿 변수 정의
            TEMPLATE_1 = """신입사원들의 질문을 분석한 결과, 가장 많이 나온 주제는 다음과 같습니다:

            ## 1. 신입사원의 자세 및 마음가짐 
            여러 질문에서 신입사원이 가져야 할 자세, 마음가짐, 태도에 대한 궁금증이 많이 나타났습니다. 예를 들어, "신입사원에게 바라는 자세나 가장 강조하고 싶은 부분", "신입사원으로서 가져야 할 가장 중요한 마음가짐" 등의 질문이 이에 해당합니다.

            ## 2. CEO의 경험 및 경영 철학 
            신입사원들은 CEO의 경력, 직무 경험, 그리고 CEO가 되기까지의 과정에 대한 질문을 많이 했습니다. "CEO가 되신 비결", "가장 기억에 남는 순간", "어려웠던 일" 등의 질문이 이 주제에 포함됩니다.

            ## 3. 업무 및 직무 관련 조언 
            신입사원들은 업무 수행, 직무 경험, 그리고 회사에서의 성장에 대한 조언을 요청하는 질문이 많았습니다. "신입사원으로서 회사에 빠르게 기여할 수 있는 방법", "업무 외에 가장 열정을 담아 하시는 것이 무엇인지", "신한카드에서 업무를 효과적으로 수행하기 위한 학습 분야" 등의 질문이 이 주제에 해당합니다.

            이 세 가지 주제는 신입사원들이 CEO와의 소통을 통해 얻고자 하는 주요 관심사로 나타났습니다."""

            TEMPLATE_2 = """아래는 신입사원들의 질문을 주제별로 정리한 결과입니다. 유사한 질문은 중복 제거하였으며, 질문자의 이름은 가렸습니다.

            ## 1. 신입사원으로서의 자세 및 마음가짐
            1. 신입사원에게 바라는 자세나 가장 강조하고 싶은 부분이 무엇인지 궁금합니다.
            2. 신입사원으로서 회사에 빠르게 기여할 수 있는 방법이 궁금합니다.
            3. 신입사원으로서 가져야 할 가장 중요한 습관은 무엇일까요?

            ## 2. CEO의 경험 및 조언
            
            1. CEO가 되신 비결이 궁금합니다.
            2. 회사생활 중 위기 혹은 어려움을 겪은 사례, 극복 방법 등을 여쭙고 싶습니다.
            3. CEO님께서 구준히 해오신 루틴이 있다면 무엇이고, 추천하시는 루틴이 있는지 궁금합니다!

            ## 3. 직무 및 커리어 관련
            
            1. 신한카드에서 어떤 팀에서 일을 하셨는지 궁금합니다!
            2. 카드업의 미래에 대해서 어떻게 생각하시는지 궁금하고, 이에 대비해서 신입사원으로서 어떤 준비를 하면 좋을지 여쭙고 싶습니다!
            3. 신한카드의 신입사원이 갖추어야할 자세가 있을까요??

            이와 같은 질문들은 신입사원들이 CEO에게 궁금해하는 다양한 측면을 반영하고 있습니다."""

            # analyze_text_with_context 함수 내에서 사용할 프롬프트
            prompt = f"""
            당신은 신한카드 CEO와 신입사원들 간의 소통을 돕는 AI 어시스턴트입니다.

            질문이 다음 두 가지 특정 유형에 해당할 때만 정해진 형식으로 답변하고,
            그 외의 일반적인 질문에는 자연스러운 대화체로 답변해주세요:

            유형 1: "신입사원의 질문을 기반으로 가장 많이 나온 주제 3개를 출력해줘"와 유사한 질문
            - 예시: "가장 많이 나온 주제가 뭐야?", "신입사원들이 주로 어떤 질문을 했어?", "많이 나온 주제 알려줘" 등
            - 이 경우 반드시 다음 형식으로 답변:
            {TEMPLATE_1}

            유형 2: "방금 출력해준 3가지 주제별로 가장 많이 나온 질문 3개씩 출력해줘"와 유사한 질문
            - 예시: "각 주제의 대표적인 질문들 알려줘", "주제별 질문 리스트 보여줘", "자주 나온 질문들 정리해줘" 등
            - 이 경우 반드시 다음 형식으로 답변:
            {TEMPLATE_2}

            기초 데이터:
            - 포함된 필드: {', '.join(data_list[0].keys())}

            데이터:
            {json.dumps(data_list, ensure_ascii=False)}

            질문: {text_query}

            규칙:
            1. 위의 두 유형과 유사한 질문이면 반드시 정해진 형식으로만 답변하세요
            2. 다른 질문인 경우에만 자유롭게 답변하세요
            3. 정해진 형식으로 답변할 때는 단어 하나도 다르게 쓰지 마세요
            4. 데이터에 없는 내용은 절대 추측하지 마세요
            5. 질문의 의도를 파악하여 가장 적절한 템플릿을 선택하세요
            6. 답변은 항상 완전한 형태로 제공하세요 (중간에 '...' 등으로 생략하지 않음)
            """
            
            # 일반 질문은 스트리밍으로 처리
            response = st.session_state.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 데이터 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                stream=True
            )
            
            # 스트리밍 응답 처리
            full_response = ""
            # 아바타와 함께 메시지 컨테이너 생성
            
            with st.chat_message("assistant", avatar=os.path.join(ASSETS_DIR, 'bot_character.png')):
                message_placeholder = st.empty()
                try:
                    for chunk in response:
                        if chunk and hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                            time.sleep(0.01)
                    message_placeholder.markdown(full_response)
                    return full_response
                
                except Exception as e:
                    st.error(f"스트리밍 처리 중 오류가 발생했습니다: {str(e)}")
                    return None
            
    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
        return None

def save_message(message, role, image_base64=None):
    """메시지 저장"""
    st.session_state.messages.append({
        "message": message,
        "role": role,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "image": image_base64  # 이미지 데이터 추가
    })

def send_message(message, role, image_base64=None, is_history=False):
    """메시지 표시"""
    try:
        # role에 따른 이미지 파일명 매핑
        image_filename = 'human_character.png' if role == 'human' else 'bot_character.png'
        avatar_path = os.path.join(ASSETS_DIR, image_filename)
        
        # 이미지 파일이 존재하는 경우에만 아바타 사용
        if os.path.exists(avatar_path):
            with st.chat_message(role, avatar=avatar_path):
                if role == "assistant" and not is_history:  # 히스토리가 아닐 때만 스트리밍 효과 적용
                    # 스트리밍 효과를 위한 점진적 표시
                    placeholder = st.empty()
                    displayed_message = ""
                    for char in message:
                        displayed_message += char
                        placeholder.markdown(displayed_message + "▌")
                        time.sleep(0.01)
                    placeholder.markdown(displayed_message)
                else:
                    st.markdown(message, unsafe_allow_html=True)
                
                # 히스토리일 경우에만 이미지 렌더링
                if is_history and image_base64:
                    st.markdown(f"![차트](data:image/png;base64,{image_base64})", unsafe_allow_html=True)
        else:
            with st.chat_message(role):
                if role == "assistant" and not is_history:  # 히스토리가 아닐 때만 스트리밍 효과 적용
                    placeholder = st.empty()
                    displayed_message = ""
                    for char in message:
                        displayed_message += char
                        placeholder.markdown(displayed_message + "▌")
                        time.sleep(0.01)
                    placeholder.markdown(displayed_message)
                else:
                    st.markdown(message, unsafe_allow_html=True)
                
                # 히스토리일 경우에만 이미지 렌더링
                if is_history and image_base64:
                    st.markdown(f"![차트](data:image/png;base64,{image_base64})", unsafe_allow_html=True)
                    
    except Exception as e:
        print(f"Avatar loading error: {str(e)}")
        with st.chat_message(role):
            st.markdown(message, unsafe_allow_html=True)
            # 히스토리일 경우에만 이미지 렌더링
            if is_history and image_base64:
                st.markdown(f"![차트](data:image/png;base64,{image_base64})", unsafe_allow_html=True)

def main():
    initialize_session_state()

    # 사이드바
    with st.sidebar:
        st.markdown("### 🎯 사용 가이드")
        st.markdown("""
        1. 분석할 파일을 업로드하세요
        2. 원하는 질문을 입력하세요
        3. AI가 파일을 분석하여 답변해드립니다
        """)

    # 파일 업로드
    uploaded_file = st.file_uploader("분석할 파일을 업로드하세요 (CSV 또는 XLSX)", type=["csv", "xlsx"])
    
    if uploaded_file:
        file_analysis_result = analyze_uploaded_file(uploaded_file)
        if file_analysis_result:
            text_data, data_list, df = file_analysis_result
            st.success("파일이 성공적으로 업로드되었습니다.")
            st.session_state.file_data = text_data
            st.session_state.data_list = data_list

    # 대화 이력 표시
    for message in st.session_state.messages:
        send_message(
            message["message"], 
            message["role"], 
            image_base64=message.get("image"),
            is_history=True  # 히스토리임을 표시
        )

    # 채팅 인터페이스
    if st.session_state.file_data:
        query = st.chat_input("파일에 대해 궁금한 점을 물어보세요")
        if query:
            # 사용자 메시지 표시
            send_message(query, "human")
            save_message(query, "human")

            # AI 응답 생성 및 표시
            with st.spinner("분석 중..."):
                response = analyze_text_with_context(
                    query,
                    st.session_state.file_data,
                    st.session_state.data_list
                )
                
                if response:
                    if any(keyword in query.lower() for keyword in ['차트']):
                        # 분석 요청의 경우 analyze_text_with_context 함수 내에서 처리됨
                        pass
                    else:
                        # 일반 응답의 경우 한 번만 표시
                        #send_message(response, "assistant")
                        save_message(response, "assistant")

if __name__ == "__main__":
    main()
