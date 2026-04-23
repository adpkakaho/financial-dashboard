"""
app.py
======
금융상품 판매동향 대시보드 — Streamlit 메인 진입점
"""

import streamlit as st

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
  /* pages/ 폴더 자동 감지로 생기는 상단 네비게이션 메뉴 숨김 */
  [data-testid="stSidebarNav"] { display: none; }

  .stApp { background-color: #F8FAFC; }
  section[data-testid="stSidebar"] {
    background-color: #fff;
    border-right: 1px solid #E2E8F0;
  }
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

  /* 사이드바 라디오 버튼을 탭처럼 스타일링 */
  div[data-testid="stSidebar"] .stRadio > div {
    gap: 4px;
  }
  div[data-testid="stSidebar"] .stRadio label {
    display: block;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
  }
  div[data-testid="stSidebar"] .stRadio label:hover {
    background: #F1F5F9;
  }
</style>
""", unsafe_allow_html=True)


# ── API 키 로드 ────────────────────────────────────────────────
def _load_keys() -> tuple[str, str, str]:
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


# ── 데이터 수집 (24시간 캐시) ──────────────────────────────────
@st.cache_data(ttl=86400, show_spinner="📡 데이터 수집 중...")
def load_data(kofia_key: str, krx_key: str, ecos_key: str) -> dict:
    return collect_all(kofia_key, krx_key, ecos_key)


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════
def main() -> None:
    kofia_key, krx_key, ecos_key = _load_keys()
    data = load_data(kofia_key, krx_key, ecos_key)

    # ── 사이드바: 메뉴 최상단 배치 ──
    with st.sidebar:
        # 메뉴를 가장 먼저 배치 (사용성 개선)
        page = st.radio(
            "메뉴",
            ["📊 전체요약", "🎯 상품전략", "📅 데일리", "🗓 먼슬리", "📈 시장"],
            label_visibility="hidden",
        )
        st.divider()
        st.markdown("### 📊 금융상품 판매동향")
        st.caption(f"최종 수집: {data.get('collected_at', '—')}")
        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
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
