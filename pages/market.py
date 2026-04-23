"""
pages/market.py
===============
시장 페이지 렌더러 — 금리·환율·지수
"""

import pandas as pd
import streamlit as st
from pages.charts import make_line
from utils import sign


def render(data: dict) -> None:
    idx        = data.get("indices",       {})
    rates      = data.get("rates",         {})
    fx         = data.get("fx",            {})
    kospi_hist = data.get("kospi_history", pd.DataFrame())

    vix_m   = idx.get("VIX",   {})
    kospi_m = idx.get("KOSPI", {})

    st.markdown("## 📈 시장")
    st.caption("출처: ECOS (금리·환율) · yfinance (지수)")

    # ── 현재값 칩 4개 ──
    cols = st.columns(4)
    market_items = [
        ("국고채 3Y",  rates.get("국고채3Y",  pd.DataFrame()), "#2563EB", "%",  "ECOS"),
        ("국고채 10Y", rates.get("국고채10Y", pd.DataFrame()), "#0891B2", "%",  "ECOS"),
        ("원달러",     fx.get("원달러",        pd.DataFrame()), "#EA580C", "원", "ECOS"),
        ("VIX",        None,                                    "#DC2626", "",   "YF"),
    ]
    for col, (name, df_m, color, unit, src) in zip(cols, market_items):
        with col:
            if name == "VIX":
                val = f"{vix_m.get('last', 0):.2f}" if vix_m else "—"
                chg = f"{sign(vix_m.get('pct', 0))}{vix_m.get('pct', 0):.2f}%" if vix_m else "—"
            elif isinstance(df_m, pd.DataFrame) and not df_m.empty:
                last_val = float(df_m["value"].iloc[-1])
                prev_val = float(df_m["value"].iloc[-2]) if len(df_m) > 1 else last_val
                diff = last_val - prev_val
                val = f"{last_val:,.3f}{unit}" if unit == "%" else f"{last_val:,.1f}{unit}"
                chg = f"{sign(diff)}{diff:.3f}{unit}" if unit == "%" else f"{sign(diff)}{diff:.1f}{unit}"
            else:
                val = "—"; chg = "—"

            chg_color = "#2563EB" if (chg != "—" and not chg.startswith("-")) else "#DC2626"
            st.markdown(f"""
            <div class="kpi-card">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span class="kpi-label">{name}</span>
                <span class="src-badge">{src}</span>
              </div>
              <div style="font-size:18px;font-weight:700;font-family:'DM Mono',monospace;">{val}</div>
              <div style="color:{chg_color};font-size:12px;">{chg}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── 금리 차트 3개 ──
    c1, c2, c3 = st.columns(3)
    for col, (name, color) in zip([c1, c2, c3], [
        ("국고채3Y", "#2563EB"), ("국고채10Y", "#0891B2"), ("CD금리", "#7C3AED")
    ]):
        with col:
            st.markdown(f"**{name}** `ECOS`")
            if name in rates and not rates[name].empty:
                st.plotly_chart(
                    make_line(rates[name], "date", "value", color=color, height=180, y_suffix="%"),
                    use_container_width=True)
            else:
                st.info("로드 중...")

    # ── 환율 + KOSPI ──
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**원달러** `ECOS`")
        if "원달러" in fx and not fx["원달러"].empty:
            st.plotly_chart(
                make_line(fx["원달러"], "date", "value", color="#EA580C", height=200, y_suffix="원"),
                use_container_width=True)
        else:
            st.info("로드 중...")
    with c2:
        st.markdown("**KOSPI** `yfinance`")
        if not kospi_hist.empty:
            st.plotly_chart(
                make_line(kospi_hist, "date", "value", color="#2563EB", height=200),
                use_container_width=True)
        else:
            st.info("로드 중...")
