"""
pages/daily.py
==============
데일리 페이지 렌더러
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pages.charts import make_line, make_bar, kpi_card
from utils import sign, fmt1


def render(data: dict) -> None:
    mf           = data.get("market_funds",  pd.DataFrame())
    cr           = data.get("credit",        pd.DataFrame())
    fn           = data.get("fund_nav",      pd.DataFrame())
    idx          = data.get("indices",       {})
    etf          = data.get("etf_top10",     pd.DataFrame())
    bond         = data.get("bond_market",   pd.DataFrame())
    bond_hist    = data.get("bond_history",  pd.DataFrame())
    gold         = data.get("gold",          {})
    gold_hist    = data.get("gold_history",  pd.DataFrame())

    mf_last = mf.iloc[-1].to_dict() if not mf.empty else {}
    mf_prev = mf.iloc[-2].to_dict() if len(mf) > 1  else {}
    cr_last = cr.iloc[-1].to_dict() if not cr.empty  else {}
    cr_prev = cr.iloc[-2].to_dict() if len(cr) > 1   else {}
    mf_flow = round(float(mf_last.get("합계", 0)) - float(mf_prev.get("합계", 0)), 1) if mf_prev else 0
    cr_chg  = round(float(cr_last.get("신용융자", 0)) - float(cr_prev.get("신용융자", 0)), 2) if cr_prev else 0
    kofia_ok = not mf.empty or not cr.empty or not fn.empty

    st.markdown("## 📅 데일리")
    st.caption("출처: KOFIA · KRX · ECOS · yfinance · 매일 갱신")

    if not kofia_ok:
        st.warning("⚠️ KOFIA 서버 일시 장애 — KRX·ECOS·yfinance 섹션은 정상입니다.")

    # ── KPI 5개 ──
    kospi_v = idx.get("KOSPI", {})
    vix_v   = idx.get("VIX",   {})

    # 주식형 순자산 안전 추출
    fn_stock_nav = "—"
    if kofia_ok and not fn.empty:
        fn_stock = fn[fn["ctg"] == "주식형"]
        if not fn_stock.empty:
            fn_stock_nav = f"{fn_stock.sort_values('basDt')['nPptTotAmt'].iloc[-1] / 1e12:.1f}조"

    cols = st.columns(5)
    kpi_items = [
        ("증시 대기자금", f"{fmt1(float(mf_last.get('합계', 0)))}조" if kofia_ok else "—",
         f"전일 {sign(mf_flow)}{mf_flow}조", "#0891B2", "KOFIA"),
        ("주식형 순자산", fn_stock_nav, "최신 순자산", "#2563EB", "KOFIA"),
        ("KOSPI", f"{kospi_v.get('last', 0):,.0f}" if kospi_v else "—",
         f"{sign(kospi_v.get('pct', 0))}{kospi_v.get('pct', 0):.2f}%", "#2563EB", "YF"),
        ("VIX",   f"{vix_v.get('last', 0):.2f}" if vix_v else "—",
         f"{sign(vix_v.get('pct', 0))}{vix_v.get('pct', 0):.2f}%", "#DC2626", "YF"),
        ("KRX 금", f"{int(gold.get('price', 0)):,}원/g" if gold else "—",
         f"{sign(gold.get('fluc', 0))}{gold.get('fluc', 0):.2f}%" if gold else "—", "#D97706", "KRX"),
    ]
    for col, (label, val, sub, color, src) in zip(cols, kpi_items):
        with col:
            st.markdown(kpi_card(label, val, sub, color, src), unsafe_allow_html=True)

    st.divider()

    # ── 펀드 플로우 ──
    st.markdown("### 펀드 플로우 `KOFIA`")
    if not fn.empty:
        key_types  = ["주식형", "채권형", "단기금융", "부동산"]
        colors_map = ["#2563EB", "#7C3AED", "#0891B2", "#EA580C"]
        cols = st.columns(4)
        for col, ctg, color in zip(cols, key_types, colors_map):
            rows = fn[fn["ctg"] == ctg]
            if not rows.empty:
                nav = float(rows.sort_values("basDt")["nPptTotAmt"].iloc[-1]) / 1e12
                with col:
                    st.markdown(kpi_card(ctg, f"{nav:.1f}조", "최신 순자산", color, "KOFIA", False),
                                unsafe_allow_html=True)

        st.markdown("")
        total = fn.groupby("basDt")["nPptTotAmt"].sum().reset_index()
        total["flow"] = (total["nPptTotAmt"].diff() / 1e12).round(2)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**유형별 주간 플로우**")
            flow_data = []
            for ctg in key_types:
                rows = fn[fn["ctg"] == ctg].sort_values("basDt")
                if len(rows) >= 6:
                    wflow = round((rows["nPptTotAmt"].iloc[-1] - rows["nPptTotAmt"].iloc[-6]) / 1e12, 2)
                    flow_data.append({"유형": ctg, "주간플로우": wflow})
            if flow_data:
                df_f = pd.DataFrame(flow_data)
                fig = go.Figure(go.Bar(
                    x=df_f["유형"], y=df_f["주간플로우"],
                    marker_color=["#2563EB" if v >= 0 else "#EF4444" for v in df_f["주간플로우"]],
                ))
                fig.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                                  plot_bgcolor="#fff", paper_bgcolor="#fff",
                                  yaxis=dict(gridcolor="#F1F5F9", ticksuffix="조"))
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("**전체 일별 플로우**")
            st.plotly_chart(make_bar(total.tail(15), "basDt", "flow", height=200, y_suffix="조"),
                            use_container_width=True)
    else:
        st.info("KOFIA 서버 복구 후 표시됩니다.")

    st.divider()

    # ── 증시 대기자금 ──
    st.markdown("### 증시 대기자금 `KOFIA`")
    if not mf.empty:
        cols = st.columns(5)
        for col, key, color in zip(cols,
            ["합계", "예탁금", "RP", "CMA", "MMF"],
            ["#D97706", "#2563EB", "#0891B2", "#7C3AED", "#0284C7"]):
            with col:
                st.markdown(kpi_card(key, f"{fmt1(float(mf_last.get(key, 0)))}조", "최신", color, "KOFIA", False),
                            unsafe_allow_html=True)
        st.markdown("")
        # 호버 시 세부 구성(예탁금/RP/CMA/MMF) 보이는 스택 영역 차트
        fig_mf = go.Figure()
        stack_items = [
            ("예탁금", "#2563EB"),
            ("RP",    "#0891B2"),
            ("CMA",   "#7C3AED"),
            ("MMF",   "#0284C7"),
        ]
        for col_name, color in stack_items:
            if col_name in mf.columns:
                fig_mf.add_trace(go.Scatter(
                    x=mf["basDt"], y=mf[col_name],
                    name=col_name, stackgroup="one",
                    mode="lines", line=dict(width=0.5, color=color),
                    hovertemplate=f"{col_name}: %{{y:.1f}}조<extra></extra>",
                ))
        fig_mf.update_layout(
            height=200, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="#fff", paper_bgcolor="#fff",
            xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickformat="%m/%d"),
            yaxis=dict(showgrid=True, gridcolor="#F1F5F9", ticksuffix="조"),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_mf, use_container_width=True)
    else:
        st.info("KOFIA 서버 복구 후 표시됩니다.")

    st.divider()

    # ── KRX ETF ──
    st.markdown("### KRX ETF 거래대금 TOP10 `KRX-ETF`")
    if not etf.empty:
        disp = etf[["ISU_NM", "거래대금(억)", "FLUC_RT", "IDX_IND_NM"]].copy()
        disp.columns = ["ETF명", "거래대금(억)", "등락률(%)", "기초지수"]
        st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.warning("📭 KRX ETF 데이터 없음 — 영업일이 아니거나 API 키를 확인해 주세요.")

    # ── 채권 거래 현황 (시계열 + 스냅샷) ──
    st.markdown("### 채권 거래 현황 `KRX-BON`")
    if not bond_hist.empty:
        # 유형별 라인 시계열
        fig_bh = go.Figure()
        bond_colors = {"국민주택채권": "#2563EB", "금융채": "#7C3AED",
                       "특수채": "#0891B2", "기타": "#94A3B8"}
        for 유형, grp in bond_hist.groupby("유형"):
            grp = grp.sort_values("date")
            fig_bh.add_trace(go.Scatter(
                x=grp["date"], y=grp["거래대금(억)"],
                name=str(유형), mode="lines+markers",
                line=dict(color=bond_colors.get(str(유형), "#94A3B8"), width=2),
                marker=dict(size=4),
            ))
        fig_bh.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                             plot_bgcolor="#fff", paper_bgcolor="#fff",
                             xaxis=dict(tickformat="%m/%d", gridcolor="#F1F5F9"),
                             yaxis=dict(gridcolor="#F1F5F9", ticksuffix="억"),
                             legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_bh, use_container_width=True)
    elif not bond.empty:
        fig = go.Figure(go.Bar(
            x=bond["유형"], y=bond["거래대금(억)"],
            marker_color=["#2563EB", "#7C3AED", "#0891B2", "#059669", "#94A3B8"][:len(bond)],
        ))
        fig.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                          plot_bgcolor="#fff", paper_bgcolor="#fff",
                          yaxis=dict(gridcolor="#F1F5F9", ticksuffix="억"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("📭 채권 거래 데이터 없음 — 영업일이 아니거나 API 키를 확인해 주세요.")

    # ── 금 시세 (시계열 + 현재값) ──
    st.markdown("### 금 시세 `KRX-GLD`")
    if gold:
        c_a, c_b, c_c = st.columns(3)
        with c_a:
            st.metric("종가", f"{int(gold.get('price', 0)):,}원/g",
                      f"{sign(gold.get('chg', 0))}{int(gold.get('chg', 0)):,}원")
        with c_b:
            st.metric("등락률", f"{gold.get('fluc', 0):.2f}%")
        with c_c:
            st.metric("거래대금", f"{gold.get('val', 0):.1f}억원")
    if not gold_hist.empty:
        fig_gh = go.Figure()
        fig_gh.add_trace(go.Scatter(
            x=gold_hist["date"], y=gold_hist["price"],
            mode="lines+markers", name="종가(원/g)",
            line=dict(color="#D97706", width=2), marker=dict(size=4),
        ))
        fig_gh.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                             plot_bgcolor="#fff", paper_bgcolor="#fff",
                             xaxis=dict(tickformat="%m/%d", gridcolor="#F1F5F9"),
                             yaxis=dict(gridcolor="#F1F5F9", ticksuffix="원"))
        st.plotly_chart(fig_gh, use_container_width=True)
    elif not gold:
        st.warning("📭 금 시세 데이터 없음 — 영업일이 아니거나 API 키를 확인해 주세요.")

    st.divider()

    # ── 신용융자 ──
    st.markdown("### 신용융자 잔고 `KOFIA`")
    if not cr.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(kpi_card("신용융자",
                f"{fmt1(float(cr_last.get('신용융자', 0)))}조",
                f"전일 {sign(cr_chg)}{cr_chg}조", "#EA580C", "KOFIA"), unsafe_allow_html=True)
        with c2:
            st.plotly_chart(make_line(cr, "basDt", "신용융자", color="#EA580C", height=130, y_suffix="조"),
                            use_container_width=True)
    else:
        st.info("KOFIA 서버 복구 후 표시됩니다.")
