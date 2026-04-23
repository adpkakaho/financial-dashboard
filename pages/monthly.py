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


def _trust_chart(trust_df: pd.DataFrame) -> go.Figure | None:
    """신탁 업권별 수탁총액 시계열 차트"""
    if trust_df.empty:
        return None

    # 날짜 컬럼 확인 및 변환
    date_col = next((c for c in ["basDt", "basYm", "baseDate"] if c in trust_df.columns), None)
    amt_col  = next((c for c in ["entTrstPrncplAmt", "trstAmt", "amt"] if c in trust_df.columns), None)
    nm_col   = next((c for c in ["entTpNm", "bizTpNm", "trustType"] if c in trust_df.columns), None)

    if not date_col or not amt_col:
        return None

    trust_df = trust_df.copy()
    trust_df[date_col] = pd.to_datetime(trust_df[date_col], format="%Y%m%d", errors="coerce")
    trust_df[amt_col]  = pd.to_numeric(trust_df[amt_col], errors="coerce")
    trust_df = trust_df.dropna(subset=[date_col, amt_col])

    fig = go.Figure()
    if nm_col and trust_df[nm_col].nunique() > 1:
        colors = ["#2563EB", "#7C3AED", "#0891B2", "#EA580C", "#059669", "#94A3B8"]
        for i, grp in enumerate(trust_df[nm_col].unique()[:6]):
            sub = trust_df[trust_df[nm_col] == grp].sort_values(date_col)
            fig.add_trace(go.Scatter(
                x=sub[date_col], y=(sub[amt_col] / 1e12).round(1),
                name=str(grp), mode="lines+markers",
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=4),
            ))
    else:
        grp = trust_df.groupby(date_col)[amt_col].sum().reset_index()
        fig.add_trace(go.Scatter(
            x=grp[date_col], y=(grp[amt_col] / 1e12).round(1),
            name="수탁총액", mode="lines+markers",
            line=dict(color="#2563EB", width=2), marker=dict(size=5),
        ))

    fig.update_layout(
        height=240, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
        xaxis=dict(tickformat="%y/%m", tickangle=0),
        yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def _els_chart(els_df: pd.DataFrame) -> go.Figure | None:
    """ELS/DLS 발행·상환 바차트"""
    if els_df.empty:
        return None

    date_col = next((c for c in ["basDt", "basYm"] if c in els_df.columns), None)
    iss_col  = next((c for c in ["elsTotIssuAmt", "issAmt", "issuAmt"] if c in els_df.columns), None)
    red_col  = next((c for c in ["elsTotRdmpAmt", "rdmpAmt", "redeemAmt"] if c in els_df.columns), None)

    if not date_col or (not iss_col and not red_col):
        return None

    els_df = els_df.copy()
    els_df[date_col] = pd.to_datetime(els_df[date_col], format="%Y%m%d", errors="coerce")
    els_df = els_df.dropna(subset=[date_col]).sort_values(date_col)

    fig = go.Figure()
    if iss_col:
        els_df[iss_col] = pd.to_numeric(els_df[iss_col], errors="coerce")
        fig.add_trace(go.Bar(
            x=els_df[date_col], y=(els_df[iss_col] / 1e12).round(2),
            name="발행", marker_color="#2563EB",
        ))
    if red_col:
        els_df[red_col] = pd.to_numeric(els_df[red_col], errors="coerce")
        fig.add_trace(go.Bar(
            x=els_df[date_col], y=(els_df[red_col] / 1e12).round(2),
            name="상환", marker_color="#EF4444",
        ))

    fig.update_layout(
        barmode="group", height=240,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
        xaxis=dict(tickformat="%y/%m", tickangle=0),
        yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


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
            fig_trust = _trust_chart(trust_df)
            if fig_trust:
                st.markdown("**업권별 수탁총액 추이**")
                st.plotly_chart(fig_trust, use_container_width=True)
            st.markdown("**원본 데이터**")
            st.dataframe(trust_df.head(30), use_container_width=True, hide_index=True)
        else:
            st.info("KOFIA 서버 복구 후 자동 수집됩니다.")

    # ── ELS 탭 ──
    with tab_els:
        st.caption("출처: KOFIA-M · getELSAndELBInfo · 월 1회 갱신")
        if not els_df.empty:
            fig_els = _els_chart(els_df)
            if fig_els:
                st.markdown("**ELS/DLS 발행·상환 추이**")
                st.plotly_chart(fig_els, use_container_width=True)
            st.dataframe(els_df.head(20), use_container_width=True, hide_index=True)
        else:
            # 폴백 정적 데이터 (KOFIA 서버 장애 시)
            df_els = pd.DataFrame({
                "구분":     ["ELS 발행", "ELS 상환", "DLS 발행", "DLS 상환"],
                "금액(조)": [3.33, 3.28, 0.28, 2.87],
                "전월 대비": ["+0.03", "균형", "-0.15", "+1.27"],
            })
            # 폴백 바차트
            fig_fb = go.Figure(go.Bar(
                x=df_els["구분"], y=df_els["금액(조)"],
                marker_color=["#2563EB", "#EF4444", "#2563EB", "#EF4444"],
            ))
            fig_fb.update_layout(
                height=200, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor=_WHITE, paper_bgcolor=_WHITE,
                yaxis=dict(gridcolor=_GRID, ticksuffix="조"),
            )
            st.markdown("**ELS/DLS 발행·상환 (최근 하드코딩 기준)**")
            st.plotly_chart(fig_fb, use_container_width=True)
            st.dataframe(df_els, use_container_width=True, hide_index=True)
            st.caption("※ KOFIA 서버 복구 후 자동 수집 예정")

        st.markdown("""
        <div style="background:#FDF4FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;margin-top:12px;">
        <b style="color:#6D28D9;">📌 FLOW vs CHOICE — ELS/DLS 관점</b><br/><br/>
        <span style="color:#7C3AED;">ELS 발행≒상환 균형으로 잔고 축소. DLS 상환 2.87조 vs 발행 0.28조.</span><br/>
        <span style="color:#64748B;">고객이 구조화상품 대신 직접투자(ETF) 선택하는 중.</span>
        </div>
        """, unsafe_allow_html=True)
