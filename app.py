"""다국어 번역기 - Streamlit 앱"""
import os

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-6-astra"
MAX_CHARS = 5000

# 코드: (한국어 이름, 원어 이름, 프롬프트용 영어 이름)
# 국기 이모지는 Windows에서 "US/JP/VN" 글자로 표시되므로 사용하지 않는다.
LANGUAGES = {
    "en": ("영어", "English", "English"),
    "ja": ("일본어", "日本語", "Japanese"),
    "vi": ("베트남어", "Tiếng Việt", "Vietnamese"),
}

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into {target_language}. "
    "Output only the translated text without explanations. "
    "Preserve line breaks, tone, and formatting."
)


class TranslationError(Exception):
    """사용자에게 보여줄 한국어 메시지를 담은 번역 오류."""


@st.cache_resource
def get_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def translate(text: str, target_language: str) -> str:
    """text를 target_language(영어 이름, 예: 'Japanese')로 번역해 반환한다."""
    client = get_client(OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
                {"role": "user", "content": text},
            ],
        )
    except openai.AuthenticationError:
        raise TranslationError("API 키가 올바르지 않습니다. .env 파일의 OPENAI_API_KEY를 확인해 주세요.")
    except openai.NotFoundError:
        raise TranslationError(
            f"모델 '{OPENAI_MODEL}'을(를) 찾을 수 없습니다. .env 파일의 OPENAI_MODEL을 확인해 주세요."
        )
    except openai.RateLimitError:
        raise TranslationError("사용량 한도를 초과했습니다. 잠시 후 다시 시도하거나 OpenAI 결제/한도를 확인해 주세요.")
    except openai.APIConnectionError:
        raise TranslationError("OpenAI 서버에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요.")
    except openai.APIError as e:
        raise TranslationError(f"번역 중 오류가 발생했습니다. ({type(e).__name__})")

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise TranslationError("번역 결과가 비어 있습니다. 다시 시도해 주세요.")
    return content.strip()


# ---------------- 화면 ----------------
st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")

st.markdown(
    """
    <style>
    .block-container { max-width: 760px; padding-top: 2.5rem; }
    h1 { word-break: keep-all; }
    .app-subtitle { color: var(--text-color); opacity: 0.7; margin-top: -0.75rem; margin-bottom: 1.25rem; }
    .char-count { text-align: right; font-size: 0.85rem; opacity: 0.65; margin-top: -0.5rem; }
    .char-count.over { color: #e5484d; opacity: 1; font-weight: 600; }
    .result-empty { opacity: 0.6; text-align: center; padding: 1.25rem 0; }
    @media (max-width: 560px) {
        h1 { font-size: 1.9rem !important; }
        .block-container { padding-top: 1.5rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("result", None)  # {"lang": code, "source": str, "text": str}
st.session_state.setdefault("pending", None)  # 이번 실행에서 처리할 버튼 클릭


def on_language_click(code: str) -> None:
    st.session_state.pending = code


def on_clear() -> None:
    st.session_state.source_text = ""
    st.session_state.result = None


st.title("🌐 다국어 번역기")
st.markdown('<p class="app-subtitle">글을 입력하고 번역할 언어 버튼을 누르세요.</p>', unsafe_allow_html=True)

has_key = bool(OPENAI_API_KEY)
if not has_key:
    st.error(
        "OpenAI API 키가 설정되지 않았습니다. 프로젝트 폴더의 `.env` 파일에 "
        "`OPENAI_API_KEY=sk-...` 를 추가한 뒤 앱을 다시 실행해 주세요."
    )

with st.container(border=True):
    # max_chars를 걸면 초과 입력 자체가 잘려 경고를 보여줄 수 없으므로 직접 검사한다.
    text = st.text_area(
        "번역할 글",
        key="source_text",
        height=180,
        placeholder="번역할 글을 입력하세요...",
        label_visibility="collapsed",
    )
    char_count = len(text)
    over_limit = char_count > MAX_CHARS
    st.markdown(
        f'<div class="char-count{" over" if over_limit else ""}">{char_count:,}/{MAX_CHARS:,}자</div>',
        unsafe_allow_html=True,
    )
    if over_limit:
        st.warning(f"입력은 최대 {MAX_CHARS:,}자까지 가능합니다. 현재 {char_count - MAX_CHARS:,}자를 초과했습니다.")

    # 버튼 자리를 먼저 잡아두고, 번역을 처리한 뒤에 버튼을 그린다.
    # 그래야 강조 표시가 "이번 실행에서 성공한 번역"을 바로 반영한다.
    buttons_slot = st.container()

    clicked = st.session_state.pending
    st.session_state.pending = None
    if clicked:
        if not text.strip():
            st.warning("번역할 글을 입력해 주세요.")
        elif over_limit:
            st.warning(f"{MAX_CHARS:,}자 이하로 줄인 뒤 다시 시도해 주세요.")
        else:
            try:
                with st.spinner("번역 중..."):
                    translated = translate(text, LANGUAGES[clicked][2])
                st.session_state.result = {"lang": clicked, "source": text, "text": translated}
            except TranslationError as e:
                st.error(str(e))

    result = st.session_state.result
    with buttons_slot:
        cols = st.columns(3)
        for col, (code, (ko, native, _)) in zip(cols, LANGUAGES.items()):
            col.button(
                f"{ko} · {native}",
                key=f"btn_{code}",
                # 현재 화면에 표시된 번역 결과의 언어만 강조한다.
                type="primary" if result and result["lang"] == code else "secondary",
                width="stretch",
                disabled=not has_key,
                on_click=on_language_click,
                args=(code,),
            )
        st.button("🧹 지우기", key="btn_clear", on_click=on_clear, type="tertiary")

with st.container(border=True):
    if result:
        ko, native, _ = LANGUAGES[result["lang"]]
        st.markdown(f"#### {ko} 번역 결과 · {native}")
        st.code(result["text"], language=None, wrap_lines=True)
    else:
        st.markdown('<div class="result-empty">아직 번역 결과가 없습니다.</div>', unsafe_allow_html=True)
