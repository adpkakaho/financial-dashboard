"""
pages/monthly.py — 먼슬리 페이지 렌더러 (ISA / 신탁 / ELS/DLS)
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pages.charts import make_line, make_dual_axis
from utils import sign, fmt1

_GRID  = "#F1F5F9"
_WHITE = "#fff"
_BIZ_COLORS = {"증권": "#2563EB", "은행": "#0891B2",
               "보험": "#7C3AED", "부동산": "#EA580C", "기타": "#94A3B8"}


def _trust_charts(trust_df: pd.DataFrame):
    """
    신탁 시각화
    실제 컬럼: basYm(YYYYMM), bzds(업권), tstCtg(신탁구분/상품명), iqBs(수탁총액), val
    - 상품별(tstCtg) 꺾은선 추이 + 업권별 도넛
    """
    if trust_df.empty:
        return None, None, None

    df = trust_df.copy()
    date_col = "basYm" if "basYm" in df.columns else "basDt"
    biz_col  = "bzds"   if "bzds"  in df.columns else None
    ctg_col  = "tstCtg" if "tstCtg" in df.columns else None
    iqbs_col = "iqBs"   if "iqBs"  in df.columns else None

    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str[:6], format="%Y%m", errors="coerce")
    df["val"] = pd.to_numeric(df["val"], errors="coerce")

    # 수탁총액 기준 필터
    if iqbs_col:
        df = df[df[iqbs_col] == "수탁총액"].copy()

    # ── 상품별(tstCtg) 꺾은선: 합계 행 기준 ──────────────────────────
    fig_line = None
    if ctg_col and biz_col:
        # 합계 업권 행에서 상품별 집계
        df_total = df[df[biz_col] == "합계"].copy() if biz_col else df.copy()
        if df_total.empty:
            df_total = df.copy()

        pivot_ctg = (df_total.groupby([date_col, ctg_col])["val"].sum()
                             .reset_index().sort_values(date_col))

        # 최근 6개월만 표시 (max 포함 6개 → DateOffset(months=5) + >= 사용)
        cutoff_6m = pivot_ctg[date_col].max() - pd.DateOffset(months=5)
        pivot_ctg = pivot_ctg[pivot_ctg[date_col] >= cutoff_6m]

        # 주요 상품 6개만 (금액 큰 순)
        top_ctgs = (pivot_ctg.groupby(ctg_col)["val"].sum()
                             .sort_values(ascending=False).head(6).index.tolist())
        pivot_ctg = pivot_ctg[pivot_ctg[ctg_col].isin(top_ctgs)]

        line_colors = ["#2563EB", "#0891B2", "#7C3AED", "#EA580C", "#059669", "#94A3B8"]
        fig_line = go.Figure()
        for i, ctg in enumerate(top_ctgs):
            sub = pivot_ctg[pivot_ctg[ctg_col] == ctg].sort_values(date_col)
            # 짧은 이름으로 legend 가독성 개선
            short = str(ctg).replace("재산신탁 ", "").replace("금전신탁 ", "")[:10]
            fig_line.add_trace(go.Scatter(
                x=sub[date_col], y=(sub["val"] / 1e12).round(1),
                name=short, mode="lines+markers",
                line=dict(color=line_colors[i % len(line_colors)], width=2),
                marker=dict(size=5),
                hovertemplate=f"{short}: %{{y:.1f}}조<extra></extra>",
            ))
        fig_line.update_layout(
            height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
            xaxis=dict(tickformat="%y/%m", gridcolor=_GRID),
            yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.15, font=dict(size=10)),
        )

    # ── 업권별 도넛: 최신 월 ────────────────────────────────────────
    fig_donut = None
    if biz_col:
        df_biz = df[~df[biz_col].isin(["합계", ""])].copy()
        latest = df_biz[date_col].max()
        latest_df = df_biz[df_biz[date_col] == latest].groupby(biz_col)["val"].sum()
        if not latest_df.empty:
            colors = [_BIZ_COLORS.get(b, "#94A3B8") for b in latest_df.index]
            fig_donut = go.Figure(go.Pie(
                labels=latest_df.index.tolist(),
                values=(latest_df / 1e12).round(1).tolist(),
                hole=0.5,
                marker_colors=colors,
                textinfo="label+percent",
                textfont_size=11,
            ))
            fig_donut.update_layout(
                height=260, margin=dict(l=0, r=0, t=10, b=10),
                paper_bgcolor=_WHITE, showlegend=False,
                annotations=[dict(
                    text=f"{latest.strftime('%y/%m')}<br>기준",
                    x=0.5, y=0.5, font_size=11, showarrow=False,
                )],
            )

    return df, fig_line, fig_donut


def _els_dls_charts(els_df: pd.DataFrame, dls_df: pd.DataFrame):
    """
    ELS + DLS 통합 시각화
    ELS: ctgElbEls, presCtg(발행실적/상환현황/미상환잔고)
    DLS: ctgDlbDls, presCtg(동일 구조)
    - 합계 행(ctgElbEls/ctgDlbDls == "합계")만 사용
    - 월별 발행 vs 상환 그룹 바차트
    """
    frames = []

    def _prep(df, ctg_col, label):
        if df.empty:
            return pd.DataFrame()
        d = df.copy()
        d["_date"] = pd.to_datetime(
            d["basDt"].astype(str).str[:6], format="%Y%m", errors="coerce")
        d["amt"] = pd.to_numeric(d["amt"], errors="coerce")
        d["_type"] = label
        if ctg_col in d.columns:
            d = d[d[ctg_col] == "합계"].copy()
        return d[["_date", "_type", "presCtg", "amt"]].dropna(subset=["_date", "amt"])

    els_prep = _prep(els_df, "ctgElbEls", "ELS")
    dls_prep = _prep(dls_df, "ctgDlbDls", "DLS")
    combined = pd.concat([els_prep, dls_prep], ignore_index=True)

    if combined.empty:
        return {}, None

    # KPI: 최신 월 ELS 발행/상환/잔고
    latest = combined["_date"].max()
    latest_els = combined[(combined["_date"] == latest) & (combined["_type"] == "ELS")]

    def get_amt(pres_kw):
        mask = latest_els["presCtg"].astype(str).str.contains(pres_kw, na=False)
        return latest_els[mask]["amt"].sum() / 1e12

    kpis = {
        "ELS 발행": get_amt("발행"),
        "ELS 상환": get_amt("상환"),
        "ELS 잔고": get_amt("잔고"),
    }

    # 발행 vs 상환 — ELS·DLS 각각 그룹 바
    plot_df = combined[combined["presCtg"].isin(["발행실적", "상환현황"])].copy()
    grp = (plot_df.groupby(["_date", "_type", "presCtg"])["amt"].sum()
                  .reset_index().sort_values("_date"))

    color_map = {
        ("ELS", "발행실적"): "#2563EB",
        ("ELS", "상환현황"): "#93C5FD",
        ("DLS", "발행실적"): "#D97706",
        ("DLS", "상환현황"): "#FDE68A",
    }
    label_map = {"발행실적": "발행", "상환현황": "상환"}

    fig_bar = go.Figure()
    for (tp, pres), sub in grp.groupby(["_type", "presCtg"]):
        fig_bar.add_trace(go.Bar(
            x=sub["_date"],
            y=(sub["amt"] / 1e12).round(2),
            name=f"{tp} {label_map.get(pres, pres)}",
            marker_color=color_map.get((str(tp), str(pres)), "#94A3B8"),
            hovertemplate=f"{tp} {label_map.get(pres,'')}: %{{y:.2f}}조<extra></extra>",
        ))
    # x축: 최근 4개월만 표시, timestamp→문자열 변환으로 포맷 문제 방지
    if not grp.empty:
        cutoff_4m = grp["_date"].max() - pd.DateOffset(months=4)
        grp = grp[grp["_date"] >= cutoff_4m]
        # x축 레이블을 %y/%m 문자열로 변환
        grp = grp.copy()
        grp["_label"] = grp["_date"].dt.strftime("%y/%m")
        # traces 재구성
        fig_bar = go.Figure()
        for (tp, pres), sub in grp.groupby(["_type", "presCtg"]):
            fig_bar.add_trace(go.Bar(
                x=sub["_label"],
                y=(sub["amt"] / 1e12).round(2),
                name=f"{tp} {label_map.get(pres, pres)}",
                marker_color=color_map.get((str(tp), str(pres)), "#94A3B8"),
                hovertemplate=f"{tp} {label_map.get(pres,'')}: %{{y:.2f}}조<extra></extra>",
            ))

    fig_bar.update_layout(
        barmode="group", height=260,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
        xaxis=dict(gridcolor=_GRID),
        yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
        legend=dict(orientation="h", y=1.1),
        hovermode="x unified",
    )
    return kpis, fig_bar


def render(data: dict) -> None:
    it       = data.get("isa_trend",  pd.DataFrame())
    ia       = data.get("isa_assets", pd.DataFrame())
    trust_df = data.get("trust",      pd.DataFrame())
    els_df   = data.get("els",        pd.DataFrame())
    dls_df   = data.get("dls",        pd.DataFrame())

    isa_last = it.iloc[-1].to_dict() if not it.empty else {}

    st.markdown("## 🗓 먼슬리")
    st.caption("출처: ISA · KOFIA-M · 월 1회 갱신")

    tab_isa, tab_trust, tab_els = st.tabs(["🔷 투자중개형 ISA", "🏦 신탁", "📉 ELS/DLS"])

    # ── ISA ─────────────────────────────────────────────────────────
    with tab_isa:
        st.caption("출처: ISA · getJoinStatus_V2 · getManagementStatus_V2")
        if not it.empty:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("투자중개형 잔고",
                    f"{fmt1(float(isa_last.get('잔고(조)',0)))}조",
                    f"전월 {sign(float(isa_last.get('순증(조)',0)))}{fmt1(float(isa_last.get('순증(조)',0)))}조")
            with c2:
                st.metric("가입자", f"{fmt1(float(isa_last.get('가입자(만명)',0)))}만명")
            with c3:
                st.metric("ETF+주식 비중", "82%", "직접투자 압도적")
            bar_colors = ["#DC2626" if v >= 5 else "#EA580C" if v >= 3 else "#2563EB"
                          for v in it["순증(조)"].fillna(0)]
            fig = make_dual_axis(it, "basDt", "순증(조)", bar_colors,
                                 "basDt", "잔고(조)", bar_name="순증(조)",
                                 line_name="잔고(조)", line_color="#D97706", height=220)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ISA 데이터 로드 중...")

        if not ia.empty:
            st.markdown("**편입자산 시계열 (%)**")
            fig2 = go.Figure()
            for col_name, (color, display) in {
                "ETF 등 상장펀드": ("#2563EB", "ETF"),
                "주식":            ("#0891B2", "주식"),
                "예적금 등":       ("#94A3B8", "예적금"),
                "RP":              ("#EA580C", "RP"),
                "파생결합증권":    ("#7C3AED", "파생"),
            }.items():
                if col_name in ia.columns:
                    fig2.add_trace(go.Scatter(
                        x=ia["basDt"], y=ia[col_name], name=display,
                        line=dict(color=color, width=2),
                        mode="lines+markers", marker=dict(size=4),
                    ))
            fig2.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                               plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                               xaxis=dict(tickformat="%y/%m"),
                               yaxis=dict(gridcolor=_GRID, ticksuffix="%"),
                               legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig2, use_container_width=True)

    # ── 신탁 ────────────────────────────────────────────────────────
    with tab_trust:
        st.caption("출처: KOFIA-M · getTrustScaleInfo · 월 1회 갱신 · 5개월치")
        if not trust_df.empty:
            df_trust, fig_line, fig_donut = _trust_charts(trust_df)

            # 업권별 KPI 카드
            if df_trust is not None and "bzds" in trust_df.columns and "iqBs" in trust_df.columns:
                tmp = trust_df.copy()
                tmp["_dt"] = pd.to_datetime(tmp["basYm" if "basYm" in tmp.columns else "basDt"]
                                            .astype(str).str[:6], format="%Y%m", errors="coerce")
                tmp["val"] = pd.to_numeric(tmp["val"], errors="coerce")
                tmp = tmp[tmp["iqBs"] == "수탁총액"]
                latest_m = tmp["_dt"].max()
                latest_t = tmp[(tmp["_dt"] == latest_m) & (~tmp["bzds"].isin(["합계", ""]))]
                biz_vals = {biz: round(latest_t[latest_t["bzds"] == biz]["val"].sum() / 1e12, 1)
                            for biz in ["증권", "은행", "보험", "부동산"]}
                kpi_cols = st.columns(4)
                for col, (biz, val) in zip(kpi_cols, biz_vals.items()):
                    color = _BIZ_COLORS.get(biz, "#94A3B8")
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-top:3px solid {color};">
                          <div class="kpi-label">{biz} 신탁</div>
                          <div class="kpi-value" style="color:{color};">{val}조</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("")

            ca, cb = st.columns([2, 1])
            with ca:
                if fig_line:
                    st.markdown("**상품별 수탁총액 추이** <span style='font-size:11px;color:#94A3B8;'>상위 6개 상품</span>",
                                unsafe_allow_html=True)
                    st.plotly_chart(fig_line, use_container_width=True)
            with cb:
                if fig_donut:
                    st.markdown("**업권별 구성**")
                    st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 자동 수집됩니다.")

    # ── ELS/DLS ──────────────────────────────────────────────────────
    with tab_els:
        st.caption("출처: KOFIA-M · getELSAndELBInfo · getDLSAndDLBInfo · 월 1회 갱신")
        has_data = not els_df.empty or not dls_df.empty
        if has_data:
            kpis, fig_bar = _els_dls_charts(els_df, dls_df)

            # KPI 카드
            if kpis:
                kpi_styles = [("ELS 발행","#2563EB"), ("ELS 상환","#EF4444"), ("ELS 잔고","#7C3AED")]
                kpi_cols = st.columns(3)
                for col, (label, color) in zip(kpi_cols, kpi_styles):
                    val = kpis.get(label, 0)
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-top:3px solid {color};">
                          <div class="kpi-label">{label}</div>
                          <div class="kpi-value" style="color:{color};">{val:.2f}조</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("")

            if fig_bar:
                st.markdown("**ELS·DLS 발행 VS 상환 월별 추이**")
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            # 폴백
            st.info("KOFIA 서버 복구 후 자동 수집됩니다.")
            df_fb = pd.DataFrame({"구분":["ELS 발행","ELS 상환","DLS 발행","DLS 상환"],
                                   "금액(조)":[3.33,3.28,0.28,2.87]})
            fig_fb = go.Figure(go.Bar(x=df_fb["구분"], y=df_fb["금액(조)"],
                                      marker_color=["#2563EB","#EF4444","#D97706","#FDE68A"]))
            fig_fb.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                                 plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                                 yaxis=dict(gridcolor=_GRID, ticksuffix="조"))
            st.plotly_chart(fig_fb, use_container_width=True)
            st.caption("※ KOFIA 서버 복구 후 자동 수집 예정")

        st.markdown("""
        <div style="background:#FDF4FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;margin-top:12px;">
        <b style="color:#6D28D9;">📌 FLOW vs CHOICE — ELS/DLS 관점</b><br/><br/>
        <span style="color:#7C3AED;">ELS 발행≒상환 균형으로 잔고 축소. DLS 상환 압도적 우위.</span><br/>
        <span style="color:#64748B;">고객이 구조화상품 대신 직접투자(ETF) 선택하는 중.</span>
        </div>
        """, unsafe_allow_html=True)
