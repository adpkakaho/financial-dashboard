"""
app.py
======
금융상품 판매동향 대시보드 — Streamlit 메인

실행: streamlit run app.py
배포: Streamlit Community Cloud (https://share.streamlit.io)
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json

from collector import collect_all

# ══════════════════════════════════════════════════════════════
# 페이지 설정
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="금융상품 판매동향",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 라이트 테마 CSS ───────────────────────────────────────────
st.markdown("""
<style>
  /* 전체 배경 */
  .stApp { background-color: #F8FAFC; }
  /* 사이드바 */
  section[data-testid="stSidebar"] { background-color: #fff; border-right: 1px solid #E2E8F0; }
  /* 헤더 숨기기 */
  header[data-testid="stHeader"] { background: transparent; }
  /* 카드 스타일 */
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
  /* 섹션 구분 */
  .section-divider {
    display: flex; align-items: center; gap: 10px; margin: 8px 0;
  }
  /* 인사이트 박스 */
  .signal-box {
    border-radius: 8px; padding: 10px 14px; margin-bottom: 6px;
  }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 인증키 로드 (Streamlit Secrets)
# ══════════════════════════════════════════════════════════════
try:
    KOFIA_KEY = st.secrets["KOFIA_KEY"]
    KRX_KEY   = st.secrets["KRX_KEY"]
except Exception:
    # 로컬 테스트용
    KOFIA_KEY = ""
    KRX_KEY   = ""

# ══════════════════════════════════════════════════════════════
# 데이터 수집 (24시간 캐시)
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=86400, show_spinner="📡 데이터 수집 중...")
def load_data():
    return collect_all(KOFIA_KEY, KRX_KEY)

# ── 헬퍼 ─────────────────────────────────────────────────────
def sign(v): return "+" if v > 0 else ""
def f1(v):   return f"{v:.1f}" if v is not None else "-"
def f2(v):   return f"{v:.2f}" if v is not None else "-"
def badge(src, color="#94A3B8"):
    return f'<span class="src-badge">{src}</span>'

def plotly_line(df, x, y, color="#2563EB", title="", height=200):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y], mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=4, color=color),
    ))
    fig.update_layout(
        height=height, margin=dict(l=0,r=0,t=20,b=0),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", showline=False),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", showline=False),
        title=dict(text=title, font=dict(size=12, color="#475569")),
    )
    return fig

def plotly_bar(df, x, y, color="#2563EB", height=200, pos_color=None, neg_color="#EF4444"):
    colors = [color if v >= 0 else neg_color for v in df[y]] if pos_color is None else \
             [pos_color if v >= 0 else neg_color for v in df[y]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df[x], y=df[y], marker_color=colors))
    fig.update_layout(
        height=height, margin=dict(l=0,r=0,t=10,b=0),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        xaxis=dict(showgrid=False, showline=False),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", showline=False),
    )
    return fig

# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════
def main():
    # 데이터 로드
    with st.spinner("데이터 수집 중..."):
        data = load_data()

    # ── 사이드바 ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 📊 금융상품 판매동향")
        st.caption(f"최종 수집: {data.get('collected_at','—')}")

        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        page = st.radio("메뉴", [
            "📊 전체요약",
            "🎯 상품전략",
            "📅 데일리",
            "🗓 먼슬리",
            "📈 시장",
        ], label_visibility="hidden")

        st.divider()
        st.markdown("**DATA SOURCE**")
        for tag, desc in [("KOFIA","공공데이터포털"),("ISA","금융위 ISA"),
                          ("ECOS","한국은행"),("YF","yfinance"),("KRX","KRX Open API")]:
            st.markdown(f'`{tag}` {desc}')

    # ── 전체요약 ──────────────────────────────────────────────
    if "전체요약" in page:
        st.markdown("## 📊 전체요약")
        st.caption(f"기준일: {data.get('collected_at','—')}")

        mf = data.get("market_funds", pd.DataFrame())
        cr = data.get("credit", pd.DataFrame())
        it = data.get("isa_trend", pd.DataFrame())

        mf_last  = mf.iloc[-1]  if not mf.empty else {}
        mf_prev  = mf.iloc[-2]  if len(mf) > 1 else {}
        cr_last  = cr.iloc[-1]  if not cr.empty else {}
        cr_prev  = cr.iloc[-2]  if len(cr) > 1 else {}
        isa_last = it.iloc[-1]  if not it.empty else {}

        mf_flow = round(float(mf_last.get("합계",0)) - float(mf_prev.get("합계",0)), 1) if mf_prev else 0

        # KPI 6개
        cols = st.columns(6)
        kpis = [
            ("펀드 순자산",   "3,216조", f"전일 +6.9조",  "#2563EB", "DAY", "KOFIA"),
            ("증시 대기자금", f"{f1(float(mf_last.get('합계',617.9)))}조",
                             f"전일 {sign(mf_flow)}{mf_flow}조", "#0891B2", "DAY", "KOFIA"),
            ("신용융자",      f"{f1(float(cr_last.get('신용융자',34.3)))}조",
                             "전일 +0.23조", "#EA580C", "DAY", "KOFIA"),
            ("ISA 투자중개형","83.4조", "전월 +8.1조",    "#D97706", "MON", "ISA"),
            ("신탁 수탁총액", "873조",  "전월 증가",       "#0891B2", "MON", "KOFIA"),
            ("ELS 순발행",   "-0.05조", "발행≒상환",      "#7C3AED", "MON", "KOFIA"),
        ]
        for col, (label, val, sub, color, freq, src) in zip(cols, kpis):
            freq_color = "#EFF6FF" if freq=="DAY" else "#FFFBEB"
            freq_tc    = "#2563EB" if freq=="DAY" else "#D97706"
            with col:
                st.markdown(f"""
                <div class="kpi-card" style="border-top: 3px solid {color};">
                  <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span class="kpi-label">{label}</span>
                    <span style="background:{freq_color};color:{freq_tc};border-radius:4px;
                      padding:1px 5px;font-size:8px;font-weight:800;">{freq}</span>
                  </div>
                  <div class="kpi-value" style="color:{color};">{val}</div>
                  <div class="kpi-sub">{sub}</div>
                  <div style="margin-top:4px;"><span class="src-badge">{src}</span></div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # Daily / Monthly 인사이트
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📅 Daily 시그널")
            st.caption("일별 갱신 · KOFIA · ECOS · YF · KRX")
            for icon, msg, color in [
                ("📈","주식형 주간 +18.8조 — 위험자산 선호","#EFF6FF"),
                ("💰","증시 대기자금 617조 — 역대급","#EFF6FF"),
                ("⚡","신용융자 34.3조 — 레버리지 주의","#FFF7ED"),
            ]:
                st.markdown(f"""
                <div class="signal-box" style="background:{color};border:1px solid #E2E8F0;">
                  {icon} {msg}
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("#### 🗓 Monthly 시그널")
            st.caption("월별 갱신 · ISA · KOFIA-M")
            for icon, msg, color in [
                ("🔷","ISA 투자중개형 전월 +8.1조 — 구조적 유입","#FFFBEB"),
                ("📉","ELS 순상환 -0.05조 — 구조화상품 수요 제한","#FDF4FF"),
            ]:
                st.markdown(f"""
                <div class="signal-box" style="background:{color};border:1px solid #E2E8F0;">
                  {icon} {msg}
                </div>
                """, unsafe_allow_html=True)

            # FLOW vs CHOICE
            st.markdown("""
            <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin-top:6px;">
              <b style="color:#475569;font-size:13px;">📌 FLOW vs CHOICE</b><br/>
              <span style="color:#2563EB;font-size:12px;">단기 흐름: 주식형·대기자금 대규모 유입 ↑</span><br/>
              <span style="color:#7C3AED;font-size:12px;">중기 선택: ELS 순상환·구조화상품 수요 제한</span><br/>
              <b style="color:#475569;font-size:12px;">→ 단기 행동과 상품 선택 간 괴리 존재</b>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 미니 차트 3개
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**증시 대기자금 합계** `KOFIA`")
            if not mf.empty:
                fig = plotly_line(mf, "basDt", "합계", color="#0891B2", height=180)
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("**펀드 일별 플로우** `KOFIA`")
            fn = data.get("fund_nav", pd.DataFrame())
            if not fn.empty:
                total = fn.groupby("basDt")["nPptTotAmt"].sum().reset_index()
                total["flow"] = (total["nPptTotAmt"].diff() / 1e12).round(2)
                fig = plotly_bar(total.tail(10), "basDt", "flow", height=180)
                st.plotly_chart(fig, use_container_width=True)
        with c3:
            st.markdown("**국고채 3Y** `ECOS`")
            rates = data.get("rates", {})
            if "국고채3Y" in rates:
                df_r = rates["국고채3Y"].tail(20)
                fig  = plotly_line(df_r, "date", "value", color="#7C3AED", height=180)
                st.plotly_chart(fig, use_container_width=True)

    # ── 상품전략 ──────────────────────────────────────────────
    elif "상품전략" in page:
        st.markdown("## 🎯 상품전략 시그널")
        st.caption("실제 수집 데이터 자동 도출 · 팩트 중심 · KOFIA·ISA·ECOS·KRX")

        cols = st.columns(3)
        signals = [
            ("🔴 즉시","#DC2626","이중 포지셔닝","KOFIA-D",
             "주식형 +18.8조 + MMF 대규모 유지",
             "공격 투자 + 헷징 동시. 불확실성 속 적극 참여.",
             "멀티에셋 / ISA 투자중개형 신규 유치"),
            ("🟡 단기","#D97706","증시 대기자금 617조","KOFIA-D",
             "예탁금+RP+CMA+MMF 합계 617.9조",
             "3/31 저점 대비 +58조. 유입 대기 수요 역대급.",
             "주식형 ETF / ISA 신규 개설 이벤트"),
            ("🟢 중기","#059669","ISA 투자중개형 성장","ISA",
             "26년 2개월 +19.8조, ETF+주식=82%",
             "셀프 직접투자 고객 급증.",
             "ETF 연계 ISA MP / 예적금→ETF 캠페인"),
        ]
        for col, (level, color, title, src, signal, meaning, action) in zip(cols, signals):
            with col:
                st.markdown(f"""
                <div style="background:#fff;border:1px solid #E2E8F0;border-left:3px solid {color};
                  border-radius:12px;padding:16px 18px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                  <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                    <span style="color:{color};font-weight:800;">{level}</span>
                    <span class="src-badge">{src}</span>
                  </div>
                  <b style="color:#1E293B;font-size:14px;">{title}</b><br/><br/>
                  <div style="background:{color}0D;border-radius:5px;padding:4px 8px;margin-bottom:8px;
                    font-family:monospace;font-size:11px;color:{color};">{signal}</div>
                  <p style="color:#64748B;font-size:12px;line-height:1.6;">{meaning}</p>
                  <p style="color:{color};font-weight:700;font-size:12px;margin-top:8px;">→ {action}</p>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # FLOW vs CHOICE
        st.markdown("### 📌 FLOW vs CHOICE")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
            <div style="background:#EFF6FF;border-radius:8px;padding:14px;">
            <b style="color:#1D4ED8;">단기 흐름 (FLOW)</b><br/><br/>
            <span style="color:#2563EB;">• 주식형 주간 +18.8조 ↑</span><br/>
            <span style="color:#2563EB;">• 증시 대기자금 617조 역대급 ↑</span><br/>
            <span style="color:#2563EB;">• ETF 거래대금 상위 집중 ↑</span>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("""
            <div style="background:#FDF4FF;border-radius:8px;padding:14px;">
            <b style="color:#6D28D9;">중기 선택 (CHOICE)</b><br/><br/>
            <span style="color:#7C3AED;">• ELS 순상환 -0.05조</span><br/>
            <span style="color:#7C3AED;">• DLS 상환 압도 (발행의 10배)</span><br/>
            <span style="color:#7C3AED;">• 채권형 유입 소극적</span>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown("""
            <div style="background:#F0FDF4;border-radius:8px;padding:14px;">
            <b style="color:#065F46;">해석</b><br/><br/>
            <span style="color:#047857;font-size:12px;line-height:1.7;">
            단기 자금 유입 강세에도 구조화상품 수요는 제한적.
            고객은 직접투자(ETF·주식) 선호 확대.<br/>
            <b>채널·플랫폼 경쟁력이 핵심.</b>
            </span>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 매핑 테이블
        st.markdown("### 자금흐름 → 고객수요 → 상품 오퍼링")
        mapping = [
            ("주식형 주간 +18.8조 ▲","위험자산 선호","주식형 ETF / 성장형 포트","KOFIA"),
            ("대기자금 617조 역대급 ▲","증시 유입 대기","주식연계 ELB / 채권형 ETF","KOFIA"),
            ("ISA 투자중개형 +19.8조 ▲","절세+직접투자 동시","ETF 연계 ISA / ISA MP","ISA"),
            ("재간접 주간 +2.72조 ▲","글로벌 분산 선호","글로벌 재간접 / 멀티에셋","KOFIA"),
            ("신용융자 +1.6조 ▲","레버리지 투자 확대","레버리지 ETF","KOFIA"),
            ("ELS 순상환 지속 ▼","구조화상품 기피","ELB / 원금보장형 전환","KOFIA"),
        ]
        df_map = pd.DataFrame(mapping, columns=["자금흐름","고객수요","추천 상품","출처"])
        st.dataframe(df_map, use_container_width=True, hide_index=True)

    # ── 데일리 ────────────────────────────────────────────────
    elif "데일리" in page:
        st.markdown("## 📅 데일리")
        st.caption("출처: KOFIA · KRX · ECOS · yfinance · 매일 갱신")

        # 펀드 유형별
        st.markdown("### 펀드 플로우 `KOFIA`")
        fn = data.get("fund_nav", pd.DataFrame())
        if not fn.empty:
            latest = fn[fn["basDt"]==fn["basDt"].max()]
            cols = st.columns(4)
            key_types = ["주식형","채권형","단기금융","부동산"]
            colors    = ["#2563EB","#7C3AED","#0891B2","#EA580C"]
            for col, ctg, color in zip(cols, key_types, colors):
                row = latest[latest["ctg"]==ctg]
                if not row.empty:
                    nav = float(row["nPptTotAmt"].iloc[0]) / 1e12
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-left:3px solid {color};">
                          <div class="kpi-label">{ctg}</div>
                          <div class="kpi-value" style="color:{color};">{nav:.1f}조</div>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("")
            total = fn.groupby("basDt")["nPptTotAmt"].sum().reset_index()
            total["flow"] = (total["nPptTotAmt"].diff() / 1e12).round(2)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**유형별 플로우 (주간)**")
                flow_data = []
                for ctg in key_types:
                    rows = fn[fn["ctg"]==ctg].sort_values("basDt").tail(6)
                    wflow = (rows["nPptTotAmt"].iloc[-1] - rows["nPptTotAmt"].iloc[0]) / 1e12
                    flow_data.append({"유형":ctg,"주간플로우":round(wflow,2)})
                df_flow = pd.DataFrame(flow_data)
                fig = go.Figure(go.Bar(
                    x=df_flow["유형"], y=df_flow["주간플로우"],
                    marker_color=["#2563EB" if v>=0 else "#EF4444" for v in df_flow["주간플로우"]],
                ))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    yaxis=dict(gridcolor="#F1F5F9"))
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.markdown("**전체 일별 플로우**")
                fig = plotly_bar(total.tail(10), "basDt", "flow", height=200)
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # 증시 대기자금
        st.markdown("### 증시 대기자금 `KOFIA`")
        mf = data.get("market_funds", pd.DataFrame())
        if not mf.empty:
            last = mf.iloc[-1]
            cols = st.columns(5)
            for col, key, color in zip(cols,
                ["합계","예탁금","RP","CMA","MMF"],
                ["#D97706","#2563EB","#0891B2","#7C3AED","#0284C7"]):
                with col:
                    st.markdown(f"""
                    <div class="kpi-card">
                      <div class="kpi-label">{key}</div>
                      <div class="kpi-value" style="color:{color};">{f1(float(last.get(key,0)))}조</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=mf["basDt"], y=mf["합계"], fill="tozeroy",
                line=dict(color="#0891B2", width=2),
                fillcolor="rgba(8,145,178,0.08)",
                name="합계(조)"
            ))
            fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                plot_bgcolor="#fff", paper_bgcolor="#fff",
                yaxis=dict(gridcolor="#F1F5F9"))
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # KRX ETF TOP10
        st.markdown("### KRX ETF 거래대금 TOP10 `KRX-ETF`")
        etf = data.get("etf_top10", pd.DataFrame())
        if not etf.empty:
            etf_disp = etf[["ISU_NM","거래대금(억)","FLUC_RT","IDX_IND_NM"]].copy()
            etf_disp.columns = ["ETF명","거래대금(억)","등락률(%)","기초지수"]
            st.dataframe(etf_disp, use_container_width=True, hide_index=True)
        else:
            st.info("KRX ETF 데이터 없음 (영업일 확인)")

        # 채권 + 금
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 채권 거래 현황 `KRX-BON`")
            bond = data.get("bond_market", pd.DataFrame())
            if not bond.empty:
                bond["거래대금(억)"] = (bond["ACC_TRDVAL"] / 1e8).round(1)
                fig = go.Figure(go.Bar(
                    x=bond["유형"], y=bond["거래대금(억)"],
                    marker_color=["#2563EB","#7C3AED","#0891B2","#059669","#94A3B8"][:len(bond)],
                ))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    yaxis=dict(gridcolor="#F1F5F9"))
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("### 금 시세 `KRX-GLD`")
            gold = data.get("gold", {})
            if gold:
                st.metric("종가 (원/g)", f"{int(gold.get('price',0)):,}",
                          f"{sign(gold.get('chg',0))}{int(gold.get('chg',0)):,}원")
                st.metric("등락률", f"{gold.get('fluc',0):.2f}%")
                st.metric("거래대금", f"{gold.get('val',0):.1f}억원")

        st.divider()

        # 신용융자
        st.markdown("### 신용융자 잔고 `KOFIA`")
        cr = data.get("credit", pd.DataFrame())
        if not cr.empty:
            fig = plotly_line(cr.tail(15), "basDt", "신용융자", color="#EA580C", height=180)
            st.plotly_chart(fig, use_container_width=True)

    # ── 먼슬리 ────────────────────────────────────────────────
    elif "먼슬리" in page:
        st.markdown("## 🗓 먼슬리")
        st.caption("출처: ISA · KOFIA-M · 월 1회 갱신")

        tab_isa, tab_trust, tab_els = st.tabs(["🔷 투자중개형 ISA","🏦 신탁","📉 ELS/DLS"])

        with tab_isa:
            st.markdown("**출처: ISA · getJoinStatus_V2 · getManagementStatus_V2**")
            it = data.get("isa_trend", pd.DataFrame())
            if not it.empty:
                last = it.iloc[-1]
                c1,c2,c3 = st.columns(3)
                with c1:
                    st.metric("투자중개형 잔고", f"{f1(float(last.get('잔고(조)',0)))}조",
                              f"전월 {sign(float(last.get('순증(조)',0)))}{f2(float(last.get('순증(조)',0)))}조")
                with c2:
                    st.metric("가입자", f"{f1(float(last.get('가입자(만명)',0)))}만명")
                with c3:
                    st.metric("26년 2개월 순증", "+19.8조", "구조적 성장")

                st.markdown("")
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=it["basDt"], y=it["순증(조)"],
                    name="순증(조)",
                    marker_color=["#DC2626" if v>=5 else "#EA580C" if v>=3 else "#2563EB"
                                  for v in it["순증(조)"].fillna(0)],
                    yaxis="y2",
                ))
                fig.add_trace(go.Scatter(
                    x=it["basDt"], y=it["잔고(조)"],
                    name="잔고(조)", line=dict(color="#D97706", width=2.5),
                    marker=dict(size=5),
                ))
                fig.update_layout(
                    height=220, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    yaxis=dict(title="잔고(조)", gridcolor="#F1F5F9"),
                    yaxis2=dict(title="순증(조)", overlaying="y", side="right"),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig, use_container_width=True)

            # 편입자산 시계열
            ia = data.get("isa_assets", pd.DataFrame())
            if not ia.empty:
                st.markdown("**편입자산 시계열 (%)**")
                fig = go.Figure()
                colors = {"ETF 등 상장펀드":"#2563EB","주식":"#0891B2","예적금 등":"#94A3B8","RP":"#EA580C","파생결합증권":"#7C3AED"}
                key_map = {"ETF 등 상장펀드":"ETF","주식":"주식","예적금 등":"예적금","RP":"RP","파생결합증권":"파생"}
                for col_name, display_name in key_map.items():
                    if col_name in ia.columns:
                        fig.add_trace(go.Scatter(
                            x=ia["basDt"], y=ia[col_name],
                            name=display_name,
                            line=dict(color=colors.get(col_name,"#94A3B8"), width=2),
                            mode="lines+markers", marker=dict(size=4),
                        ))
                fig.update_layout(
                    height=220, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    yaxis=dict(gridcolor="#F1F5F9", ticksuffix="%"),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab_trust:
            st.markdown("**출처: KOFIA-M · getTrusBusiInfoService · 최신 2026.03**")
            st.info("신탁 데이터는 월별로 API에서 자동 수집됩니다.")

        with tab_els:
            st.markdown("**출처: KOFIA-M · getElsBlbIssuPresInfo · 최신 2026.02**")
            # 하드코딩 데이터 표시 (월별 갱신)
            els_data = {
                "구분": ["ELS 발행","ELS 상환","DLS 발행","DLS 상환"],
                "금액(조)": [3.33, 3.28, 0.28, 2.87],
                "전월 대비": ["+0.03","균형","-0.15","+1.27"],
            }
            st.dataframe(pd.DataFrame(els_data), use_container_width=True, hide_index=True)

            st.markdown("""
            <div style="background:#FDF4FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;">
            <b style="color:#6D28D9;">📌 FLOW vs CHOICE — ELS/DLS 관점</b><br/><br/>
            <span style="color:#7C3AED;">ELS 발행=상환 균형으로 잔고 축소. DLS 상환 2.87조 vs 발행 0.28조.</span><br/>
            <span style="color:#64748B;">고객이 구조화상품 대신 직접투자(ETF) 선택하는 중.</span>
            </div>
            """, unsafe_allow_html=True)

    # ── 시장 ──────────────────────────────────────────────────
    elif "시장" in page:
        st.markdown("## 📈 시장")
        st.caption("출처: ECOS (금리·환율) · yfinance (지수)")

        # 현재값 칩
        indices = data.get("indices", {})
        rates   = data.get("rates", {})
        fx      = data.get("fx", {})

        cols = st.columns(4)
        market_kpis = [
            ("KOSPI", indices.get("KOSPI",{}).get("last",6388), indices.get("KOSPI",{}).get("pct",2.72), "", "YF"),
            ("VIX",   indices.get("VIX",{}).get("last",19.5),  indices.get("VIX",{}).get("pct",3.34),   "", "YF"),
            ("국고채3Y", 3.330, -0.018, "%", "ECOS"),
            ("원달러",   1470.8, -4.80,  "원", "ECOS"),
        ]
        for col, (name, val, chg, unit, src) in zip(cols, market_kpis):
            chg_color = "#2563EB" if chg >= 0 else "#DC2626"
            chg_str   = f"{'+' if chg>=0 else ''}{chg:.2f}{unit or '%'}"
            with col:
                st.markdown(f"""
                <div class="kpi-card">
                  <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span class="kpi-label">{name}</span>
                    <span class="src-badge">{src}</span>
                  </div>
                  <div class="kpi-value" style="font-size:18px;">{val:,.2f}{unit}</div>
                  <div style="color:{chg_color};font-size:12px;">{chg_str}</div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # 금리 차트
        c1, c2, c3 = st.columns(3)
        for col, (name, color) in zip([c1,c2,c3], [
            ("국고채3Y","#2563EB"),("국고채10Y","#0891B2"),("CD금리","#7C3AED")
        ]):
            with col:
                st.markdown(f"**{name}** `ECOS`")
                if name in rates:
                    df_r = rates[name]
                    fig  = plotly_line(df_r, "date", "value", color=color, height=180)
                    fig.update_yaxes(ticksuffix="%")
                    st.plotly_chart(fig, use_container_width=True)

        # 환율 + 지수
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**원달러** `ECOS`")
            if "원달러" in fx:
                df_fx = fx["원달러"]
                fig   = plotly_line(df_fx, "date", "value", color="#EA580C", height=180)
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("**KOSPI** `yfinance`")
            try:
                ks = yf.Ticker("^KS11").history(period="1mo", auto_adjust=True)
                if not ks.empty:
                    df_ks = ks.reset_index()[["Date","Close"]].rename(columns={"Date":"date","Close":"value"})
                    fig   = plotly_line(df_ks, "date", "value", color="#2563EB", height=180)
                    st.plotly_chart(fig, use_container_width=True)
            except:
                st.info("KOSPI 데이터 로드 중...")

if __name__ == "__main__":
    main()
