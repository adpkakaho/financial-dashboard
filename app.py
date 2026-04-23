"""
app.py
======
금융상품 판매동향 대시보드 — Streamlit 메인 진입점
"""

import streamlit as st
import pandas as pd

from collector import collect_all
from pages import summary, strategy, daily, monthly, market

st.set_page_config(
    page_title="금융상품 판매동향",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .stApp { background-color: #F8FAFC; }
  section[data-testid="stSidebar"] { background-color: #fff; border-right: 1px solid #E2E8F0; }
  header[data-testid="stHeader"] { background: transparent; }
  .kpi-card {
    background: #fff; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 16px 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .kpi-value { font-size: 22px; font-weight: 700; font-family: 'DM Mono', monospace; }
  .kpi-label { font-size: 11px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.07em; }
  .kpi-sub   { font-size: 11px; color: #94A3B8; margin-top: 2px; }
  .src-badge {
    display: inline-block; background: #F1F5F9; color: #94A3B8;
    border-radius: 4px; padding: 1px 6px; font-size: 9px; font-weight: 700;
    font-family: monospace;
  }
</style>
""", unsafe_allow_html=True)


# ── API 키 로드 (Streamlit Secrets) ───────────────────────────
def _load_keys() -> tuple[str, str, str]:
    """Secrets에서 키를 읽고, 없으면 빈 문자열 반환 + 경고 로그"""
    try:
        return (
            st.secrets["KOFIA_KEY"],
            st.secrets["KRX_KEY"],
            st.secrets["ECOS_KEY"],
        )
    except KeyError as e:
        st.sidebar.warning(f"⚠️ Secrets 누락: {e} — 해당 데이터는 수집되지 않습니다.")
        return "", "", ""
    except Exception:
        return "", "", ""


# ── 데이터 수집 (24시간 캐시) — 키를 인자로 전달하여 캐시 키 고정 ──
@st.cache_data(ttl=86400, show_spinner="📡 데이터 수집 중...")
def load_data(kofia_key: str, krx_key: str, ecos_key: str) -> dict:
    return collect_all(kofia_key, krx_key, ecos_key)


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════
def main() -> None:
    kofia_key, krx_key, ecos_key = _load_keys()
    data = load_data(kofia_key, krx_key, ecos_key)

    # ── 사이드바 ──
    with st.sidebar:
        st.markdown("### 📊 금융상품 판매동향")
        st.caption(f"최종 수집: {data.get('collected_at', '—')}")
        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        page = st.radio("메뉴", [
            "📊 전체요약", "🎯 상품전략", "📅 데일리", "🗓 먼슬리", "📈 시장",
        ], label_visibility="hidden")
        st.divider()
        st.markdown("**DATA SOURCE**")
        for tag, desc in [
            ("KOFIA", "공공데이터포털"), ("ISA", "금융위 ISA"),
            ("ECOS",  "한국은행"),       ("YF",  "yfinance"),
            ("KRX",   "KRX Open API"),
        ]:
            st.markdown(f"`{tag}` {desc}")

    # ── 페이지 라우팅 ──
    if "전체요약" in page:
        summary.render(data)
    elif "상품전략" in page:
        strategy.render(data)
    elif "데일리" in page:
        daily.render(data)
    elif "먼슬리" in page:
        monthly.render(data)
    elif "시장" in page:
        market.render(data)


if __name__ == "__main__":
    main()
