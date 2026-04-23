"""
pages/summary.py
================
전체요약 페이지 렌더러
"""

import streamlit as st
from pages.charts import make_line, kpi_card
from utils import sign, fmt1


def render(data: dict) -> None:
    mf         = data.get("market_funds", __import__("pandas").DataFrame())
    cr         = data.get("credit",       __import__("pandas").DataFrame())
    fn         = data.get("fund_nav",     __import__("pandas").DataFrame())
    it         = data.get("isa_trend",    __import__("pandas").DataFrame())
    idx        = data.get("indices",      {})
    rates      = data.get("rates",        {})
    kospi_hist = data.get("kospi_history", __import__("pandas").DataFrame())

    mf_last  = mf.iloc[-1].to_dict() if not mf.empty else {}
    mf_prev  = mf.iloc[-2].to_dict() if len(mf) > 1  else {}
    isa_last = it.iloc[-1].to_dict() if not it.empty  else {}
    mf_flow  = round(float(mf_last.get("합계", 0)) - float(mf_prev.get("합계", 0)), 1) if mf_prev else 0
    cr_last  = cr.iloc[-1].to_dict() if not cr.empty else {}
    cr_prev  = cr.iloc[-2].to_dict() if len(cr) > 1  else {}
    cr_chg   = round(float(cr_last.get("신용융자", 0)) - float(cr_prev.get("신용융자", 0)), 2) if cr_prev else 0
    kofia_ok = not mf.empty or not cr.empty or not fn.empty

    st.markdown("## 📊 전체요약")
    if not kofia_ok:
        st.warning("⚠️ KOFIA 서버 일시 장애 — 시장 탭은 정상입니다. 잠시 후 새로고침 해주세요.")

    # ── KPI 카드 6개 ──
    cols = st.columns(6)
    kospi_v = idx.get("KOSPI", {})
    vix_v   = idx.get("VIX",   {})
    kpis = [
        ("펀드 순자산",   f"{fmt1(float(mf_last.get('합계', 0)) + 2598.3)}조" if kofia_ok else "—",
         "전일 플로우", "#2563EB", "D", "KOFIA"),
        ("증시 대기자금", f"{fmt1(float(mf_last.get('합계', 0)))}조" if kofia_ok else "—",
         f"전일 {sign(mf_flow)}{mf_flow}조", "#0891B2", "D", "KOFIA"),
        ("신용융자",      f"{fmt1(float(cr_last.get('신용융자', 0)))}조" if kofia_ok else "—",
         f"전일 {sign(cr_chg)}{cr_chg}조", "#EA580C", "D", "KOFIA"),
        ("KOSPI",        f"{kospi_v.get('last', 0):,.0f}" if kospi_v else "—",
         f"{sign(kospi_v.get('pct', 0))}{kospi_v.get('pct', 0):.2f}%" if kospi_v else "—",
         "#2563EB", "D", "YF"),
        ("VIX",          f"{vix_v.get('last', 0):.2f}" if vix_v else "—",
         f"{sign(vix_v.get('pct', 0))}{vix_v.get('pct', 0):.2f}%" if vix_v else "—",
         "#DC2626", "D", "YF"),
        ("ISA 투자중개형", f"{fmt1(float(isa_last.get('잔고(조)', 0)))}조" if not it.empty else "—",
         f"전월 {sign(float(isa_last.get('순증(조)', 0)))}{fmt1(float(isa_last.get('순증(조)', 0)))}조",
         "#D97706", "M", "ISA"),
    ]
    for col, (label, val, sub, color, freq, src) in zip(cols, kpis):
        freq_bg = "#EFF6FF" if freq == "D" else "#FFFBEB"
        freq_c  = "#2563EB" if freq == "D" else "#D97706"
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="border-top:3px solid {color};">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span class="kpi-label">{label}</span>
                <span style="background:{freq_bg};color:{freq_c};border-radius:4px;
                  padding:1px 5px;font-size:8px;font-weight:800;">{freq}</span>
              </div>
              <div class="kpi-value" style="color:{color};">{val}</div>
              <div class="kpi-sub">{sub}</div>
              <div style="margin-top:4px;"><span class="src-badge">{src}</span></div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── 시그널 ──
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 📅 Daily 시그널")
        st.caption("KOFIA · ECOS · YF · KRX · 일별 갱신")
        signals_d = []
        if kofia_ok:
            fn_eq = fn[fn["ctg"] == "주식형"] if not fn.empty else __import__("pandas").DataFrame()
            if not fn_eq.empty and len(fn_eq) >= 6:
                wflow = (fn_eq.sort_values("basDt")["nPptTotAmt"].iloc[-1] -
                         fn_eq.sort_values("basDt")["nPptTotAmt"].iloc[-6]) / 1e12
                if wflow > 10:
                    signals_d.append(("📈", f"주식형 주간 +{wflow:.1f}조 — 위험자산 선호", "#EFF6FF", "#2563EB"))
            if not mf.empty and float(mf_last.get("합계", 0)) > 600:
                signals_d.append(("💰", f"증시 대기자금 {fmt1(float(mf_last.get('합계', 0)))}조 — 역대급", "#EFF6FF", "#0891B2"))
            if not cr.empty and float(cr_last.get("신용융자", 0)) > 34:
                signals_d.append(("⚡", f"신용융자 {fmt1(float(cr_last.get('신용융자', 0)))}조 — 레버리지 주의", "#FFF7ED", "#EA580C"))
        if vix_v and vix_v.get("last", 0) > 20:
            signals_d.append(("⚠️", f"VIX {vix_v.get('last', 0):.1f} — 변동성 경고", "#FEF2F2", "#DC2626"))
        if not signals_d:
            signals_d.append(("ℹ️", "KOFIA 서버 복구 후 자동 표시됩니다", "#F8FAFC", "#94A3B8"))
        for icon, msg, bg, tc in signals_d:
            st.markdown(
                f'<div style="background:{bg};border:1px solid #E2E8F0;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:6px;color:{tc};font-size:13px;">{icon} {msg}</div>',
                unsafe_allow_html=True)

    with c2:
        st.markdown("#### 🗓 Monthly 시그널")
        st.caption("ISA · KOFIA-M · 월 1회 갱신")
        signals_m = []
        if not it.empty and float(isa_last.get("순증(조)", 0)) > 5:
            signals_m.append(("🔷", f"ISA 투자중개형 전월 +{fmt1(float(isa_last.get('순증(조)', 0)))}조 — 구조적 유입", "#FFFBEB", "#D97706"))
        signals_m.append(("📉", "ELS 순상환 지속 — 구조화상품 수요 제한", "#FDF4FF", "#7C3AED"))
        for icon, msg, bg, tc in signals_m:
            st.markdown(
                f'<div style="background:{bg};border:1px solid #E2E8F0;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:6px;color:{tc};font-size:13px;">{icon} {msg}</div>',
                unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin-top:4px;">
          <b style="color:#475569;">📌 FLOW vs CHOICE</b><br/>
          <span style="color:#2563EB;font-size:12px;">단기 흐름: 주식형·대기자금 대규모 유입 ↑</span><br/>
          <span style="color:#7C3AED;font-size:12px;">중기 선택: ELS 순상환·구조화상품 수요 제한</span><br/>
          <b style="color:#475569;font-size:12px;">→ 단기 행동과 상품 선택 간 괴리 존재</b>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── 미니 차트 3개 ──
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**증시 대기자금** `KOFIA`")
        if not mf.empty:
            st.plotly_chart(make_line(mf, "basDt", "합계", color="#0891B2", height=170, y_suffix="조"),
                            use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 표시")
    with c2:
        st.markdown("**KOSPI** `yfinance`")
        if not kospi_hist.empty:
            st.plotly_chart(make_line(kospi_hist, "date", "value", color="#2563EB", height=170),
                            use_container_width=True)
        else:
            st.info("로드 중...")
    with c3:
        st.markdown("**국고채 3Y** `ECOS`")
        if "국고채3Y" in rates:
            st.plotly_chart(make_line(rates["국고채3Y"], "date", "value", color="#7C3AED", height=170, y_suffix="%"),
                            use_container_width=True)
        else:
            st.info("로드 중...")
