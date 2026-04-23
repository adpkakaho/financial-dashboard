"""
pages/monthly.py
================
먼슬리 페이지 렌더러 — ISA / 신탁(그래프) / ELS(그래프)
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pages.charts import make_line, make_dual_axis
from utils import sign, fmt1

_GRID  = "#F1F5F9"
_WHITE = "#fff"


# ── 신탁 실제 컬럼 (스크린샷 기준): basYm, bzds, tstCtg, kind, iqBs, val ──
_TRUST_BIZ_MAP = {"증권": "#2563EB", "은행": "#0891B2", "보험": "#7C3AED", "부동산": "#EA580C", "기타": "#94A3B8"}

def _trust_charts(trust_df: pd.DataFrame):
    """신탁 — 업권별 KPI 카드 + 누적 바차트 + 도넛차트 반환"""
    if trust_df.empty:
        return None, None, None

    df = trust_df.copy()
    # 날짜: basYm(202601) 또는 basDt
    date_col = "basYm" if "basYm" in df.columns else "basDt"
    df[date_col] = pd.to_datetime(df[date_col].astype(str).str[:6], format="%Y%m", errors="coerce")
    df["val"] = pd.to_numeric(df.get("val", df.get("amt", 0)), errors="coerce")

    # 합계 행만 사용 (bzds=="합계")
    biz_col = "bzds" if "bzds" in df.columns else None
    if biz_col:
        df_sum = df[df[biz_col] == "합계"].copy()
        df_biz = df[df[biz_col] != "합계"].copy()
    else:
        df_sum = df.copy()
        df_biz = df.copy()

    # tstCtg 기준 그룹 (종합재산신탁, 재산신탁 등)
    ctg_col = "tstCtg" if "tstCtg" in df.columns else None

    # 최신 월 업권별 KPI용
    latest = df_sum[date_col].max() if not df_sum.empty else None

    # 누적 바차트 — 월별 × 업권별
    fig_bar = None
    if ctg_col and not df_sum.empty:
        pivot = (df_sum.groupby([date_col, ctg_col])["val"].sum()
                       .reset_index().sort_values(date_col))
        fig_bar = go.Figure()
        ctgs = pivot[ctg_col].unique()[:6]
        bar_colors = ["#2563EB", "#0891B2", "#7C3AED", "#EA580C", "#059669", "#94A3B8"]
        for i, ctg in enumerate(ctgs):
            sub = pivot[pivot[ctg_col] == ctg]
            fig_bar.add_trace(go.Bar(
                x=sub[date_col], y=(sub["val"] / 1e12).round(1),
                name=str(ctg), marker_color=bar_colors[i % len(bar_colors)],
            ))
        fig_bar.update_layout(
            barmode="stack", height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
            xaxis=dict(tickformat="%y/%m"), yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
            legend=dict(orientation="h", y=1.1),
        )

    # 도넛차트 — 최신 월 유형별 구성
    fig_donut = None
    if ctg_col and latest is not None:
        latest_df = df_sum[df_sum[date_col] == latest].groupby(ctg_col)["val"].sum()
        if not latest_df.empty:
            fig_donut = go.Figure(go.Pie(
                labels=latest_df.index.tolist(),
                values=(latest_df / 1e12).round(1).tolist(),
                hole=0.55,
                marker_colors=["#2563EB", "#0891B2", "#7C3AED", "#EA580C", "#059669", "#94A3B8"],
                textinfo="label+percent",
            ))
            fig_donut.update_layout(
                height=260, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor=_WHITE,
                legend=dict(orientation="v", x=1),
                annotations=[dict(text=f"{latest.strftime('%y/%m')}<br>기준", x=0.5, y=0.5,
                                  font_size=11, showarrow=False)],
            )

    return df_sum, fig_bar, fig_donut


# ── ELS 실제 컬럼 (스크린샷 기준): basDt, ctgElbEls, amt, ccnt ──
def _els_charts(els_df: pd.DataFrame):
    """ELS/DLS — KPI 카드 4개 + 그룹 바차트 반환"""
    if els_df.empty:
        return None, None

    df = els_df.copy()
    date_col = "basDt" if "basDt" in df.columns else "basYm"
    df[date_col] = pd.to_datetime(df[date_col].astype(str).str[:6], format="%Y%m", errors="coerce")
    df["amt"] = pd.to_numeric(df.get("amt", 0), errors="coerce")

    # ctgElbEls: ELS/ELB/DLS 구분 컬럼
    ctg_col = "ctgElbEls" if "ctgElbEls" in df.columns else None
    # presCtg: 발행/상환 구분
    pres_col = "presCtg" if "presCtg" in df.columns else None

    # 최신 월
    latest = df[date_col].max()
    latest_df = df[df[date_col] == latest] if latest else df

    # KPI 추출 (ctgElbEls × presCtg 조합)
    def get_amt(ctg_val, pres_val):
        if ctg_col and pres_col:
            mask = (latest_df[ctg_col].astype(str).str.contains(ctg_val, na=False) &
                    latest_df[pres_col].astype(str).str.contains(pres_val, na=False))
            return latest_df[mask]["amt"].sum() / 1e12
        return latest_df["amt"].sum() / 1e12

    kpis = {
        "ELS 발행": get_amt("ELS", "발행"),
        "ELS 상환": get_amt("ELS", "상환"),
        "DLS 발행": get_amt("DLS", "발행"),
        "DLS 상환": get_amt("DLS", "상환"),
    }

    # 시계열 그룹 바차트
    fig_bar = None
    if ctg_col and pres_col:
        grp = (df.groupby([date_col, ctg_col, pres_col])["amt"].sum()
                 .reset_index().sort_values(date_col))
        fig_bar = go.Figure()
        color_map = {("ELS","발행"): "#2563EB", ("ELS","상환"): "#EF4444",
                     ("DLS","발행"): "#F59E0B", ("DLS","상환"): "#F97316"}
        for (ctg, pres), sub in grp.groupby([ctg_col, pres_col]):
            fig_bar.add_trace(go.Bar(
                x=sub[date_col], y=(sub["amt"] / 1e12).round(2),
                name=f"{ctg}{pres}",
                marker_color=color_map.get((str(ctg), str(pres)), "#94A3B8"),
            ))
        fig_bar.update_layout(
            barmode="group", height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
            xaxis=dict(tickformat="%y/%m"), yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
            legend=dict(orientation="h", y=1.1),
        )
    else:
        # 컬럼 구분 없이 월별 합계만
        grp = df.groupby(date_col)["amt"].sum().reset_index()
        fig_bar = go.Figure(go.Bar(x=grp[date_col], y=(grp["amt"] / 1e12).round(2),
                                   marker_color="#2563EB", name="발행·상환 합계"))
        fig_bar.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                              plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                              xaxis=dict(tickformat="%y/%m"),
                              yaxis=dict(gridcolor=_GRID, ticksuffix="조"))

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

    # ── ISA 탭 ──
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

            # 잔고 + 순증 이중축 차트
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

        # 편입자산 시계열
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

    # ── 신탁 탭 ──
    with tab_trust:
        st.caption("출처: KOFIA-M · getTrustScaleInfo · 월 1회 갱신")
        if not trust_df.empty:
            df_sum, fig_bar, fig_donut = _trust_charts(trust_df)

            # 업권별 KPI 카드
            biz_latest = {}
            if df_sum is not None and not df_sum.empty:
                biz_col = "bzds" if "bzds" in trust_df.columns else None
                date_col = "basYm" if "basYm" in trust_df.columns else "basDt"
                if biz_col:
                    import pandas as _pd
                    tmp = trust_df.copy()
                    tmp["_dt"] = _pd.to_datetime(tmp[date_col].astype(str).str[:6], format="%Y%m", errors="coerce")
                    tmp["val"] = _pd.to_numeric(tmp.get("val", tmp.get("amt", 0)), errors="coerce")
                    latest_m = tmp["_dt"].max()
                    latest_t = tmp[(tmp["_dt"] == latest_m) & (tmp[biz_col] != "합계")]
                    for biz in ["증권", "은행", "보험", "부동산"]:
                        sub = latest_t[latest_t[biz_col] == biz]["val"].sum()
                        biz_latest[biz] = round(sub / 1e12, 1)

            if biz_latest:
                kpi_cols = st.columns(4)
                biz_colors = {"증권": "#2563EB", "은행": "#0891B2", "보험": "#7C3AED", "부동산": "#EA580C"}
                for col, (biz, val) in zip(kpi_cols, biz_latest.items()):
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-top:3px solid {biz_colors.get(biz,'#94A3B8')};">
                          <div class="kpi-label">{biz} 신탁</div>
                          <div class="kpi-value" style="color:{biz_colors.get(biz,'#94A3B8')};">{val}조</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("")

            # 누적 바 + 도넛 나란히
            if fig_bar or fig_donut:
                ca, cb = st.columns([2, 1])
                with ca:
                    if fig_bar:
                        st.markdown("**업권별 수탁총액 누적 (조원)**")
                        st.plotly_chart(fig_bar, use_container_width=True)
                with cb:
                    if fig_donut:
                        st.markdown("**유형별 구성**")
                        st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 자동 수집됩니다.")

    # ── ELS 탭 ──
    with tab_els:
        st.caption("출처: KOFIA-M · getELSAndELBInfo · 월 1회 갱신")
        if not els_df.empty:
            kpis, fig_els_bar = _els_charts(els_df)

            # KPI 카드 4개
            if kpis:
                kpi_cols = st.columns(4)
                kpi_styles = [
                    ("ELS 발행", "#2563EB"), ("ELS 상환", "#EF4444"),
                    ("DLS 발행", "#F59E0B"), ("DLS 상환", "#F97316"),
                ]
                for col, (label, color) in zip(kpi_cols, kpi_styles):
                    val = kpis.get(label, 0)
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-top:3px solid {color};">
                          <div class="kpi-label">{label}</div>
                          <div class="kpi-value" style="color:{color};">{val:.2f}조</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("")

            if fig_els_bar:
                st.markdown("**ELS/DLS 발행 VS 상환 (조원)**")
                st.plotly_chart(fig_els_bar, use_container_width=True)
        else:
            # 폴백 정적 데이터
            df_fb = pd.DataFrame({
                "구분":     ["ELS 발행", "ELS 상환", "DLS 발행", "DLS 상환"],
                "금액(조)": [3.33, 3.28, 0.28, 2.87],
            })
            kpi_cols = st.columns(4)
            kpi_styles = [
                ("ELS 발행", "#2563EB", 3.33, "+0.03조"), ("ELS 상환", "#EF4444", 3.28, "발행=상환 균형"),
                ("DLS 발행", "#F59E0B", 0.28, "전월 대비 감소"), ("DLS 상환", "#F97316", 2.87, "발행의 10배 ↑"),
            ]
            for col, (label, color, val, sub) in zip(kpi_cols, kpi_styles):
                with col:
                    st.markdown(f"""
                    <div class="kpi-card" style="border-top:3px solid {color};">
                      <div class="kpi-label">{label}</div>
                      <div class="kpi-value" style="color:{color};">{val:.2f}조</div>
                      <div class="kpi-sub">{sub}</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("")
            fig_fb = go.Figure(go.Bar(
                x=df_fb["구분"], y=df_fb["금액(조)"],
                marker_color=["#2563EB", "#EF4444", "#F59E0B", "#F97316"],
            ))
            fig_fb.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                                 plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                                 yaxis=dict(gridcolor=_GRID, ticksuffix="조"))
            st.markdown("**ELS/DLS 발행 VS 상환 (최근 기준)**")
            st.plotly_chart(fig_fb, use_container_width=True)
            st.caption("※ KOFIA 서버 복구 후 자동 수집 예정")

        st.markdown("""
        <div style="background:#FDF4FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;margin-top:12px;">
        <b style="color:#6D28D9;">📌 FLOW vs CHOICE — ELS/DLS 관점</b><br/><br/>
        <span style="color:#7C3AED;">ELS 발행≒상환 균형으로 잔고 축소. DLS 상환 2.87조 vs 발행 0.28조.</span><br/>
        <span style="color:#64748B;">고객이 구조화상품 대신 직접투자(ETF) 선택하는 중.</span>
        </div>
        """, unsafe_allow_html=True)
