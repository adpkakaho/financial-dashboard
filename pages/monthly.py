"""
pages/monthly.py
================
먼슬리 페이지 렌더러 — ISA / 신탁 / ELS/DLS
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pages.charts import make_line, make_dual_axis
from utils import sign, fmt1

_GRID  = "#F1F5F9"
_WHITE = "#fff"

# ── 신탁 업권별 색상 ──────────────────────────────────────────────────
_BIZ_COLORS = {
    "증권": "#2563EB", "은행": "#0891B2",
    "보험": "#7C3AED", "부동산": "#EA580C", "기타": "#94A3B8",
}

def _trust_charts(trust_df: pd.DataFrame):
    """
    신탁 데이터 시각화
    실제 컬럼: basYm, bzds(업권), tstCtg(신탁구분), iqBs(조회기준), val(값)
    - 업권별(증권/은행/보험/부동산) KPI + 꺾은선 추이 + 도넛
    """
    if trust_df.empty:
        return None, None, None

    df = trust_df.copy()
    date_col = "basYm" if "basYm" in df.columns else "basDt"
    biz_col  = "bzds"   if "bzds"  in df.columns else None
    iqbs_col = "iqBs"   if "iqBs"  in df.columns else None

    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str[:6], format="%Y%m", errors="coerce"
    )
    df["val"] = pd.to_numeric(df["val"], errors="coerce")

    # 수탁총액 행만 사용
    if iqbs_col:
        df = df[df[iqbs_col] == "수탁총액"].copy()

    # 업권별 집계 (합계 행 제외)
    if biz_col:
        df_biz = df[~df[biz_col].isin(["합계", ""])].copy()
    else:
        df_biz = df.copy()

    if df_biz.empty:
        return None, None, None

    # 월별 × 업권별 집계
    pivot = (df_biz.groupby([date_col, biz_col])["val"].sum()
                   .reset_index().sort_values(date_col))

    # ── 꺾은선 추이 (업권별 개별 라인, 가독성 우선) ──
    fig_line = go.Figure()
    biz_list = pivot[biz_col].unique()
    for biz in biz_list:
        sub = pivot[pivot[biz_col] == biz].sort_values(date_col)
        color = _BIZ_COLORS.get(str(biz), "#94A3B8")
        fig_line.add_trace(go.Scatter(
            x=sub[date_col], y=(sub["val"] / 1e12).round(1),
            name=str(biz), mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
            hovertemplate=f"{biz}: %{{y:.1f}}조<extra></extra>",
        ))
    fig_line.update_layout(
        height=240, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
        xaxis=dict(tickformat="%y/%m", gridcolor=_GRID),
        yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12),
    )

    # ── 도넛: 최신 월 업권별 구성 ──
    latest = pivot[date_col].max()
    latest_df = pivot[pivot[date_col] == latest].groupby(biz_col)["val"].sum()
    fig_donut = None
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
            height=240, margin=dict(l=0, r=0, t=10, b=10),
            paper_bgcolor=_WHITE,
            showlegend=False,
            annotations=[dict(
                text=f"{latest.strftime('%y/%m')}<br>기준",
                x=0.5, y=0.5, font_size=11, showarrow=False,
            )],
        )

    return pivot, fig_line, fig_donut


def _els_charts(els_df: pd.DataFrame):
    """
    ELS/DLS 시각화
    실제 컬럼: basDt(YYYYMM), ctgElbEls(합계/원금보장형 등), presCtg(발행실적/상환현황/미상환잔고), amt
    - KPI: presCtg 기준 발행/상환 합계
    - 바차트: 월별 발행 vs 상환
    """
    if els_df.empty:
        return None, None

    df = els_df.copy()
    date_col = "basDt" if "basDt" in df.columns else "basYm"
    pres_col = "presCtg" if "presCtg" in df.columns else None
    ctg_col  = "ctgElbEls" if "ctgElbEls" in df.columns else None

    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str[:6], format="%Y%m", errors="coerce"
    )
    df["amt"] = pd.to_numeric(df["amt"], errors="coerce")

    # 합계 행만 사용 (ctgElbEls == "합계")
    if ctg_col:
        df_total = df[df[ctg_col] == "합계"].copy()
        if df_total.empty:
            df_total = df.copy()
    else:
        df_total = df.copy()

    # 최신 월 KPI
    latest = df_total[date_col].max()
    latest_df = df_total[df_total[date_col] == latest]

    def get_amt_by_pres(keyword: str) -> float:
        """presCtg에서 keyword 포함 행의 amt 합계"""
        if pres_col is None:
            return 0.0
        mask = latest_df[pres_col].astype(str).str.contains(keyword, na=False)
        return latest_df[mask]["amt"].sum() / 1e12

    kpis = {
        "발행":  get_amt_by_pres("발행"),
        "상환":  get_amt_by_pres("상환"),
        "잔고":  get_amt_by_pres("잔고"),
    }

    # 월별 발행 vs 상환 바차트
    fig_bar = None
    if pres_col:
        # 발행실적 / 상환현황만 추출
        df_plot = df_total[df_total[pres_col].isin(["발행실적", "상환현황"])].copy()
        grp = (df_plot.groupby([date_col, pres_col])["amt"].sum()
                      .reset_index().sort_values(date_col))

        color_map = {"발행실적": "#2563EB", "상환현황": "#EF4444"}
        label_map = {"발행실적": "발행", "상환현황": "상환"}

        fig_bar = go.Figure()
        for pres_val, sub in grp.groupby(pres_col):
            fig_bar.add_trace(go.Bar(
                x=sub[date_col],
                y=(sub["amt"] / 1e12).round(2),
                name=label_map.get(str(pres_val), str(pres_val)),
                marker_color=color_map.get(str(pres_val), "#94A3B8"),
                hovertemplate=f"{label_map.get(str(pres_val), pres_val)}: %{{y:.2f}}조<extra></extra>",
            ))
        fig_bar.update_layout(
            barmode="group", height=260,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
            xaxis=dict(tickformat="%y/%m", gridcolor=_GRID),
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

    isa_last = it.iloc[-1].to_dict() if not it.empty else {}

    st.markdown("## 🗓 먼슬리")
    st.caption("출처: ISA · KOFIA-M · 월 1회 갱신")

    tab_isa, tab_trust, tab_els = st.tabs(["🔷 투자중개형 ISA", "🏦 신탁", "📉 ELS/DLS"])

    # ── ISA 탭 ───────────────────────────────────────────────────────
    with tab_isa:
        st.caption("출처: ISA · getJoinStatus_V2 · getManagementStatus_V2")
        if not it.empty:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("투자중개형 잔고",
                    f"{fmt1(float(isa_last.get('잔고(조)', 0)))}조",
                    f"전월 {sign(float(isa_last.get('순증(조)', 0)))}{fmt1(float(isa_last.get('순증(조)', 0)))}조")
            with c2:
                st.metric("가입자", f"{fmt1(float(isa_last.get('가입자(만명)', 0)))}만명")
            with c3:
                st.metric("ETF+주식 비중", "82%", "직접투자 압도적")

            bar_colors = ["#DC2626" if v >= 5 else "#EA580C" if v >= 3 else "#2563EB"
                          for v in it["순증(조)"].fillna(0)]
            fig = make_dual_axis(
                it, "basDt", "순증(조)", bar_colors,
                "basDt", "잔고(조)",
                bar_name="순증(조)", line_name="잔고(조)",
                line_color="#D97706", height=220,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ISA 데이터 로드 중...")

        if not ia.empty:
            st.markdown("**편입자산 시계열 (%)**")
            fig2 = go.Figure()
            col_map = {
                "ETF 등 상장펀드": ("#2563EB", "ETF"),
                "주식":            ("#0891B2", "주식"),
                "예적금 등":       ("#94A3B8", "예적금"),
                "RP":              ("#EA580C", "RP"),
                "파생결합증권":    ("#7C3AED", "파생"),
            }
            for col_name, (color, display) in col_map.items():
                if col_name in ia.columns:
                    fig2.add_trace(go.Scatter(
                        x=ia["basDt"], y=ia[col_name],
                        name=display, line=dict(color=color, width=2),
                        mode="lines+markers", marker=dict(size=4),
                    ))
            fig2.update_layout(
                height=220, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                xaxis=dict(tickformat="%y/%m", tickangle=0),
                yaxis=dict(gridcolor=_GRID, ticksuffix="%"),
                legend=dict(orientation="h", y=1.1),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── 신탁 탭 ──────────────────────────────────────────────────────
    with tab_trust:
        st.caption("출처: KOFIA-M · getTrustScaleInfo · 월 1회 갱신")
        if not trust_df.empty:
            pivot, fig_line, fig_donut = _trust_charts(trust_df)

            # 업권별 KPI 카드
            if pivot is not None and not pivot.empty:
                biz_col = "bzds" if "bzds" in trust_df.columns else None
                date_col = "basYm" if "basYm" in trust_df.columns else "basDt"
                if biz_col:
                    tmp = trust_df.copy()
                    tmp["_dt"] = pd.to_datetime(
                        tmp[date_col].astype(str).str[:6], format="%Y%m", errors="coerce"
                    )
                    tmp["val"] = pd.to_numeric(tmp["val"], errors="coerce")
                    # 수탁총액 기준
                    if "iqBs" in tmp.columns:
                        tmp = tmp[tmp["iqBs"] == "수탁총액"]
                    latest_m = tmp["_dt"].max()
                    latest_t = tmp[(tmp["_dt"] == latest_m) & (~tmp[biz_col].isin(["합계", ""]))]

                    biz_vals = {}
                    for biz in ["증권", "은행", "보험", "부동산"]:
                        sub = latest_t[latest_t[biz_col] == biz]["val"].sum()
                        biz_vals[biz] = round(sub / 1e12, 1)

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

            # 업권별 꺾은선 + 도넛 나란히
            ca, cb = st.columns([2, 1])
            with ca:
                if fig_line:
                    st.markdown("**업권별 수탁총액 추이**")
                    st.plotly_chart(fig_line, use_container_width=True)
            with cb:
                if fig_donut:
                    st.markdown("**유형별 구성**")
                    st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 자동 수집됩니다.")

    # ── ELS/DLS 탭 ───────────────────────────────────────────────────
    with tab_els:
        st.caption("출처: KOFIA-M · getELSAndELBInfo · 월 1회 갱신")
        if not els_df.empty:
            kpis, fig_els_bar = _els_charts(els_df)

            # KPI 카드 3개 (발행/상환/잔고)
            if kpis:
                kpi_styles = [
                    ("발행", "#2563EB"), ("상환", "#EF4444"), ("잔고", "#7C3AED"),
                ]
                kpi_cols = st.columns(3)
                for col, (label, color) in zip(kpi_cols, kpi_styles):
                    val = kpis.get(label, 0)
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-top:3px solid {color};">
                          <div class="kpi-label">ELS {label}</div>
                          <div class="kpi-value" style="color:{color};">{val:.2f}조</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("")

            if fig_els_bar:
                st.markdown("**발행 VS 상환 월별 추이**")
                st.plotly_chart(fig_els_bar, use_container_width=True)
        else:
            # 폴백 정적 데이터
            kpi_styles = [
                ("ELS 발행", "#2563EB", 3.33, "+0.03조"),
                ("ELS 상환", "#EF4444", 3.28, "발행=상환 균형"),
                ("DLS 발행", "#F59E0B", 0.28, "전월 대비 감소"),
                ("DLS 상환", "#F97316", 2.87, "발행의 10배 ↑"),
            ]
            kpi_cols = st.columns(4)
            for col, (label, color, val, sub) in zip(kpi_cols, kpi_styles):
                with col:
                    st.markdown(f"""
                    <div class="kpi-card" style="border-top:3px solid {color};">
                      <div class="kpi-label">{label}</div>
                      <div class="kpi-value" style="color:{color};">{val:.2f}조</div>
                      <div class="kpi-sub">{sub}</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("")
            df_fb = pd.DataFrame({
                "구분": ["ELS 발행", "ELS 상환", "DLS 발행", "DLS 상환"],
                "금액(조)": [3.33, 3.28, 0.28, 2.87],
            })
            fig_fb = go.Figure(go.Bar(
                x=df_fb["구분"], y=df_fb["금액(조)"],
                marker_color=["#2563EB", "#EF4444", "#F59E0B", "#F97316"],
            ))
            fig_fb.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                                 plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                                 yaxis=dict(gridcolor=_GRID, ticksuffix="조"))
            st.markdown("**발행 VS 상환 (최근 기준)**")
            st.plotly_chart(fig_fb, use_container_width=True)
            st.caption("※ KOFIA 서버 복구 후 자동 수집 예정")

        st.markdown("""
        <div style="background:#FDF4FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;margin-top:12px;">
        <b style="color:#6D28D9;">📌 FLOW vs CHOICE — ELS/DLS 관점</b><br/><br/>
        <span style="color:#7C3AED;">ELS 발행≒상환 균형으로 잔고 축소. DLS 상환 압도적 우위.</span><br/>
        <span style="color:#64748B;">고객이 구조화상품 대신 직접투자(ETF) 선택하는 중.</span>
        </div>
        """, unsafe_allow_html=True)
