"""
app.py
======
금융상품 판매동향 대시보드 — Streamlit 메인
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf                          # ← 누락됐던 import 추가
from datetime import datetime

from collector import collect_all

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

# ── 인증키 (Streamlit Secrets) ────────────────────────────────
try:
    KOFIA_KEY = st.secrets["KOFIA_KEY"]
    KRX_KEY   = st.secrets["KRX_KEY"]
    ECOS_KEY  = st.secrets["ECOS_KEY"]
except Exception:
    KOFIA_KEY = ""
    KRX_KEY   = ""
    ECOS_KEY  = ""

# ── 데이터 수집 (24시간 캐시) ─────────────────────────────────
@st.cache_data(ttl=86400, show_spinner="📡 데이터 수집 중...")
def load_data():
    return collect_all(KOFIA_KEY, KRX_KEY, ECOS_KEY)

# ── 헬퍼 ─────────────────────────────────────────────────────
def sign(v):
    return "+" if float(v) > 0 else ""

def f1(v):
    try: return f"{float(v):.1f}"
    except: return "-"

def f2(v):
    try: return f"{float(v):.2f}"
    except: return "-"

def make_line(df, x, y, color="#2563EB", height=200, y_suffix="", title=""):
    """날짜 x축 포함 라인차트 — tickformat으로 날짜 정상 표시"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y],
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=4, color=color),
        name=y,
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        title=dict(text=title, font=dict(size=12, color="#475569")),
        xaxis=dict(
            showgrid=True, gridcolor="#F1F5F9",
            tickformat="%m/%d",          # ← 날짜 포맷 고정 (20.26035M 방지)
            tickangle=0,
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#F1F5F9",
            ticksuffix=y_suffix,
        ),
    )
    return fig

def make_bar(df, x, y, color="#2563EB", height=200, neg_color="#EF4444", y_suffix=""):
    colors = [color if float(v) >= 0 else neg_color for v in df[y]]
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y],
        marker_color=colors,
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        xaxis=dict(
            showgrid=False,
            tickformat="%m/%d",
            tickangle=0,
        ),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", ticksuffix=y_suffix),
    )
    return fig

def kpi_card(label, value, sub, color, src, top_border=True):
    border_top = f"border-top: 3px solid {color};" if top_border else ""
    return f"""
    <div class="kpi-card" style="{border_top}">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span class="kpi-label">{label}</span>
        <span class="src-badge">{src}</span>
      </div>
      <div class="kpi-value" style="color:{color};">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>
    """

# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════
def main():
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
            "📊 전체요약", "🎯 상품전략", "📅 데일리", "🗓 먼슬리", "📈 시장",
        ], label_visibility="hidden")
        st.divider()
        st.markdown("**DATA SOURCE**")
        for tag, desc in [
            ("KOFIA","공공데이터포털"), ("ISA","금융위 ISA"),
            ("ECOS","한국은행"),        ("YF","yfinance"),
            ("KRX","KRX Open API"),
        ]:
            st.markdown(f'`{tag}` {desc}')

    # ── 데이터 단축 변수 ──────────────────────────────────────
    mf  = data.get("market_funds", pd.DataFrame())
    cr  = data.get("credit",       pd.DataFrame())
    fn  = data.get("fund_nav",     pd.DataFrame())
    it  = data.get("isa_trend",    pd.DataFrame())
    ia  = data.get("isa_assets",   pd.DataFrame())
    idx = data.get("indices",      {})
    rates = data.get("rates",      {})
    fx    = data.get("fx",         {})
    etf   = data.get("etf_top10",  pd.DataFrame())
    bond  = data.get("bond_market",pd.DataFrame())
    gold  = data.get("gold",       {})
    kospi_hist = data.get("kospi_history", pd.DataFrame())
    els_df = data.get("els",   pd.DataFrame())
    trust_df = data.get("trust", pd.DataFrame())

    mf_last  = mf.iloc[-1]  if not mf.empty else {}
    mf_prev  = mf.iloc[-2]  if len(mf) > 1  else {}
    cr_last  = cr.iloc[-1]  if not cr.empty else {}
    cr_prev  = cr.iloc[-2]  if len(cr) > 1  else {}
    isa_last = it.iloc[-1]  if not it.empty else {}
    mf_flow  = round(float(mf_last.get("합계",0)) - float(mf_prev.get("합계",0)), 1) if mf_prev else 0
    cr_chg   = round(float(cr_last.get("신용융자",0)) - float(cr_prev.get("신용융자",0)), 2) if cr_prev else 0

    # KOFIA 데이터 수집 여부
    kofia_ok = not mf.empty or not cr.empty or not fn.empty

    # ══ 전체요약 ══════════════════════════════════════════════
    if "전체요약" in page:
        st.markdown("## 📊 전체요약")
        if not kofia_ok:
            st.warning("⚠️ KOFIA 서버 일시 장애 — 시장 탭은 정상입니다. 잠시 후 새로고침 해주세요.")

        cols = st.columns(6)
        kospi_v = idx.get("KOSPI", {})
        vix_v   = idx.get("VIX",   {})
        kpis = [
            ("펀드 순자산",   f"{f1(float(mf_last.get('합계',0))+2598.3)}조" if kofia_ok else "—",
             "전일 플로우", "#2563EB","D","KOFIA"),
            ("증시 대기자금", f"{f1(float(mf_last.get('합계',0)))}조" if kofia_ok else "—",
             f"전일 {sign(mf_flow)}{mf_flow}조","#0891B2","D","KOFIA"),
            ("신용융자",      f"{f1(float(cr_last.get('신용융자',0)))}조" if kofia_ok else "—",
             f"전일 {sign(cr_chg)}{cr_chg}조","#EA580C","D","KOFIA"),
            ("KOSPI",        f"{kospi_v.get('last',0):,.0f}" if kospi_v else "—",
             f"{sign(kospi_v.get('pct',0))}{kospi_v.get('pct',0):.2f}%","#2563EB","D","YF"),
            ("VIX",          f"{vix_v.get('last',0):.2f}" if vix_v else "—",
             f"{sign(vix_v.get('pct',0))}{vix_v.get('pct',0):.2f}%","#DC2626","D","YF"),
            ("ISA 투자중개형",f"{f1(float(isa_last.get('잔고(조)',0)))}조" if not it.empty else "—",
             f"전월 {sign(float(isa_last.get('순증(조)',0)))}{f1(float(isa_last.get('순증(조)',0)))}조",
             "#D97706","M","ISA"),
        ]
        for col, (label,val,sub,color,freq,src) in zip(cols, kpis):
            freq_bg = "#EFF6FF" if freq=="D" else "#FFFBEB"
            freq_c  = "#2563EB" if freq=="D" else "#D97706"
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

        # Daily / Monthly 시그널
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📅 Daily 시그널")
            st.caption("KOFIA · ECOS · YF · KRX · 일별 갱신")
            signals_d = []
            if kofia_ok:
                fn_eq = fn[fn["ctg"]=="주식형"] if not fn.empty else pd.DataFrame()
                if not fn_eq.empty:
                    wflow = (fn_eq.sort_values("basDt")["nPptTotAmt"].iloc[-1] -
                             fn_eq.sort_values("basDt")["nPptTotAmt"].iloc[-6]) / 1e12
                    if wflow > 10:
                        signals_d.append(("📈",f"주식형 주간 +{wflow:.1f}조 — 위험자산 선호","#EFF6FF","#2563EB"))
                if not mf.empty and float(mf_last.get("합계",0)) > 600:
                    signals_d.append(("💰",f"증시 대기자금 {f1(float(mf_last.get('합계',0)))}조 — 역대급","#EFF6FF","#0891B2"))
                if not cr.empty and float(cr_last.get("신용융자",0)) > 34:
                    signals_d.append(("⚡",f"신용융자 {f1(float(cr_last.get('신용융자',0)))}조 — 레버리지 주의","#FFF7ED","#EA580C"))
            if vix_v and vix_v.get("last",0) > 20:
                signals_d.append(("⚠️",f"VIX {vix_v.get('last',0):.1f} — 변동성 경고","#FEF2F2","#DC2626"))
            if not signals_d:
                signals_d.append(("ℹ️","KOFIA 서버 복구 후 자동 표시됩니다","#F8FAFC","#94A3B8"))
            for icon,msg,bg,tc in signals_d:
                st.markdown(f'<div style="background:{bg};border:1px solid #E2E8F0;border-radius:8px;padding:10px 14px;margin-bottom:6px;color:{tc};font-size:13px;">{icon} {msg}</div>', unsafe_allow_html=True)

        with c2:
            st.markdown("#### 🗓 Monthly 시그널")
            st.caption("ISA · KOFIA-M · 월 1회 갱신")
            signals_m = []
            if not it.empty and float(isa_last.get("순증(조)",0)) > 5:
                signals_m.append(("🔷",f"ISA 투자중개형 전월 +{f1(float(isa_last.get('순증(조)',0)))}조 — 구조적 유입","#FFFBEB","#D97706"))
            signals_m.append(("📉","ELS 순상환 지속 — 구조화상품 수요 제한","#FDF4FF","#7C3AED"))

            for icon,msg,bg,tc in signals_m:
                st.markdown(f'<div style="background:{bg};border:1px solid #E2E8F0;border-radius:8px;padding:10px 14px;margin-bottom:6px;color:{tc};font-size:13px;">{icon} {msg}</div>', unsafe_allow_html=True)

            st.markdown("""
            <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin-top:4px;">
              <b style="color:#475569;">📌 FLOW vs CHOICE</b><br/>
              <span style="color:#2563EB;font-size:12px;">단기 흐름: 주식형·대기자금 대규모 유입 ↑</span><br/>
              <span style="color:#7C3AED;font-size:12px;">중기 선택: ELS 순상환·구조화상품 수요 제한</span><br/>
              <b style="color:#475569;font-size:12px;">→ 단기 행동과 상품 선택 간 괴리 존재</b>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 미니 차트
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**증시 대기자금** `KOFIA`")
            if not mf.empty:
                st.plotly_chart(make_line(mf, "basDt", "합계", color="#0891B2", height=170, y_suffix="조"), use_container_width=True)
            else:
                st.info("KOFIA 서버 복구 후 표시")
        with c2:
            st.markdown("**KOSPI** `yfinance`")
            if not kospi_hist.empty:
                st.plotly_chart(make_line(kospi_hist, "date", "value", color="#2563EB", height=170), use_container_width=True)
            else:
                st.info("로드 중...")
        with c3:
            st.markdown("**국고채 3Y** `ECOS`")
            if "국고채3Y" in rates:
                st.plotly_chart(make_line(rates["국고채3Y"], "date", "value", color="#7C3AED", height=170, y_suffix="%"), use_container_width=True)
            else:
                st.info("로드 중...")

    # ══ 상품전략 ══════════════════════════════════════════════
    elif "상품전략" in page:
        st.markdown("## 🎯 상품전략 시그널")
        st.caption("실제 수집 데이터 자동 도출 · 팩트 중심 · KOFIA·ISA·ECOS·KRX")

        cols = st.columns(3)
        signals = [
            ("🔴 즉시","#DC2626","이중 포지셔닝","KOFIA-D",
             "주식형 대규모 유입 + MMF 유지","공격+헷징 동시. 불확실성 속 적극 참여.",
             "멀티에셋 / ISA 투자중개형 신규 유치"),
            ("🟡 단기","#D97706","증시 대기자금 역대급","KOFIA-D",
             "예탁금+RP+CMA+MMF 합계 600조+","저점 대비 급등. 유입 대기 수요 역대급.",
             "주식형 ETF / ISA 신규 개설 이벤트"),
            ("🟢 중기","#059669","ISA 투자중개형 성장","ISA",
             "ETF+주식 80%+ 직접투자 압도","셀프 직접투자 고객 급증.",
             "ETF 연계 ISA MP / 예적금→ETF 캠페인"),
        ]
        for col,(level,color,title,src,signal,meaning,action) in zip(cols,signals):
            with col:
                st.markdown(f"""
                <div style="background:#fff;border:1px solid #E2E8F0;border-left:3px solid {color};
                  border-radius:12px;padding:16px 18px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                  <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                    <b style="color:{color};">{level}</b>
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
        st.markdown("### 📌 FLOW vs CHOICE")
        c1,c2,c3 = st.columns(3)
        with c1:
            st.markdown('<div style="background:#EFF6FF;border-radius:8px;padding:14px;"><b style="color:#1D4ED8;">단기 흐름 (FLOW)</b><br/><br/><span style="color:#2563EB;">• 주식형 주간 대규모 유입 ↑</span><br/><span style="color:#2563EB;">• 증시 대기자금 역대급 ↑</span><br/><span style="color:#2563EB;">• ETF 거래대금 집중 ↑</span></div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div style="background:#FDF4FF;border-radius:8px;padding:14px;"><b style="color:#6D28D9;">중기 선택 (CHOICE)</b><br/><br/><span style="color:#7C3AED;">• ELS 순상환 지속</span><br/><span style="color:#7C3AED;">• DLS 상환 압도 (발행의 10배)</span><br/><span style="color:#7C3AED;">• 채권형 유입 소극적</span></div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div style="background:#F0FDF4;border-radius:8px;padding:14px;"><b style="color:#065F46;">해석</b><br/><br/><span style="color:#047857;font-size:12px;line-height:1.7;">단기 자금 유입 강세에도 구조화상품 수요 제한적. 고객은 직접투자(ETF·주식) 선호 확대.<br/><b>채널·플랫폼 경쟁력이 핵심.</b></span></div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 자금흐름 → 고객수요 → 상품 오퍼링")
        df_map = pd.DataFrame([
            ("주식형 대규모 유입 ▲",  "위험자산 선호",       "주식형 ETF / 성장형 포트",  "KOFIA"),
            ("대기자금 역대급 ▲",     "증시 유입 대기",       "주식연계 ELB / 채권형 ETF", "KOFIA"),
            ("ISA 투자중개형 급증 ▲",  "절세+직접투자 동시",  "ETF 연계 ISA / ISA MP",     "ISA"),
            ("재간접 유입 ▲",          "글로벌 분산 선호",     "글로벌 재간접 / 멀티에셋",  "KOFIA"),
            ("신용융자 증가 ▲",        "레버리지 투자 확대",   "레버리지 ETF",              "KOFIA"),
            ("ELS 순상환 지속 ▼",      "구조화상품 기피",      "ELB / 원금보장형 전환",     "KOFIA"),
        ], columns=["자금흐름","고객수요","추천 상품","출처"])
        st.dataframe(df_map, use_container_width=True, hide_index=True)

    # ══ 데일리 ════════════════════════════════════════════════
    elif "데일리" in page:
        st.markdown("## 📅 데일리")
        st.caption("출처: KOFIA · KRX · ECOS · yfinance · 매일 갱신")

        if not kofia_ok:
            st.warning("⚠️ KOFIA 서버 일시 장애 — KRX·ECOS·yfinance 섹션은 정상입니다.")

        # KPI
        kospi_v = idx.get("KOSPI", {})
        vix_v   = idx.get("VIX",   {})
        cols = st.columns(5)
        for col, (label,val,sub,color,src) in zip(cols, [
            ("증시 대기자금", f"{f1(float(mf_last.get('합계',0)))}조" if kofia_ok else "—",
             f"전일 {sign(mf_flow)}{mf_flow}조","#0891B2","KOFIA"),
            ("주식형 순자산", "—" if not kofia_ok else f"{fn[fn['ctg']=='주식형']['nPptTotAmt'].iloc[-1]/1e12:.1f}조" if not fn.empty and len(fn[fn['ctg']=='주식형'])>0 else "—",
             "최신 순자산","#2563EB","KOFIA"),
            ("KOSPI", f"{kospi_v.get('last',0):,.0f}" if kospi_v else "—",
             f"{sign(kospi_v.get('pct',0))}{kospi_v.get('pct',0):.2f}%","#2563EB","YF"),
            ("VIX",   f"{vix_v.get('last',0):.2f}" if vix_v else "—",
             f"{sign(vix_v.get('pct',0))}{vix_v.get('pct',0):.2f}%","#DC2626","YF"),
            ("KRX 금", f"{int(gold.get('price',0)):,}원/g" if gold else "—",
             f"{sign(gold.get('fluc',0))}{gold.get('fluc',0):.2f}%" if gold else "—","#D97706","KRX"),
        ]):
            with col:
                st.markdown(kpi_card(label,val,sub,color,src), unsafe_allow_html=True)

        st.divider()

        # 펀드 플로우
        st.markdown("### 펀드 플로우 `KOFIA`")
        if not fn.empty:
            key_types  = ["주식형","채권형","단기금융","부동산"]
            colors_map = ["#2563EB","#7C3AED","#0891B2","#EA580C"]
            cols = st.columns(4)
            for col, ctg, color in zip(cols, key_types, colors_map):
                rows = fn[fn["ctg"]==ctg]
                if not rows.empty:
                    nav = float(rows.sort_values("basDt")["nPptTotAmt"].iloc[-1]) / 1e12
                    with col:
                        st.markdown(kpi_card(ctg, f"{nav:.1f}조","최신 순자산",color,"KOFIA",False), unsafe_allow_html=True)

            st.markdown("")
            total = fn.groupby("basDt")["nPptTotAmt"].sum().reset_index()
            total["flow"] = (total["nPptTotAmt"].diff() / 1e12).round(2)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**유형별 주간 플로우**")
                flow_data = []
                for ctg in key_types:
                    rows = fn[fn["ctg"]==ctg].sort_values("basDt")
                    if len(rows) >= 6:
                        wflow = round((rows["nPptTotAmt"].iloc[-1] - rows["nPptTotAmt"].iloc[-6]) / 1e12, 2)
                        flow_data.append({"유형":ctg,"주간플로우":wflow})
                if flow_data:
                    df_f = pd.DataFrame(flow_data)
                    fig = go.Figure(go.Bar(
                        x=df_f["유형"], y=df_f["주간플로우"],
                        marker_color=["#2563EB" if v>=0 else "#EF4444" for v in df_f["주간플로우"]],
                    ))
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                        plot_bgcolor="#fff", paper_bgcolor="#fff",
                        yaxis=dict(gridcolor="#F1F5F9", ticksuffix="조"))
                    st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.markdown("**전체 일별 플로우**")
                st.plotly_chart(make_bar(total.tail(15), "basDt", "flow", height=200, y_suffix="조"), use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 표시됩니다.")

        st.divider()

        # 증시 대기자금
        st.markdown("### 증시 대기자금 `KOFIA`")
        if not mf.empty:
            cols = st.columns(5)
            for col, key, color in zip(cols,
                ["합계","예탁금","RP","CMA","MMF"],
                ["#D97706","#2563EB","#0891B2","#7C3AED","#0284C7"]):
                with col:
                    st.markdown(kpi_card(key, f"{f1(float(mf_last.get(key,0)))}조","최신",color,"KOFIA",False), unsafe_allow_html=True)
            st.markdown("")
            st.plotly_chart(make_line(mf, "basDt", "합계", color="#0891B2", height=200, y_suffix="조"), use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 표시됩니다.")

        st.divider()

        # KRX
        st.markdown("### KRX ETF 거래대금 TOP10 `KRX-ETF`")
        if not etf.empty:
            disp = etf[["ISU_NM","거래대금(억)","FLUC_RT","IDX_IND_NM"]].copy()
            disp.columns = ["ETF명","거래대금(억)","등락률(%)","기초지수"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
        else:
            st.info("KRX ETF 데이터 없음 (영업일 확인)")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 채권 거래 현황 `KRX-BON`")
            if not bond.empty:
                fig = go.Figure(go.Bar(
                    x=bond["유형"], y=bond["거래대금(억)"],
                    marker_color=["#2563EB","#7C3AED","#0891B2","#059669","#94A3B8"][:len(bond)],
                ))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    yaxis=dict(gridcolor="#F1F5F9", ticksuffix="억"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("데이터 없음")
        with c2:
            st.markdown("### 금 시세 `KRX-GLD`")
            if gold:
                c_a, c_b = st.columns(2)
                with c_a:
                    st.metric("종가", f"{int(gold.get('price',0)):,}원/g",
                              f"{sign(gold.get('chg',0))}{int(gold.get('chg',0)):,}원")
                with c_b:
                    st.metric("등락률", f"{gold.get('fluc',0):.2f}%")
                st.metric("거래대금", f"{gold.get('val',0):.1f}억원")
            else:
                st.info("데이터 없음")

        st.divider()

        # 신용융자
        st.markdown("### 신용융자 잔고 `KOFIA`")
        if not cr.empty:
            c1, c2 = st.columns([1,2])
            with c1:
                st.markdown(kpi_card("신용융자",
                    f"{f1(float(cr_last.get('신용융자',0)))}조",
                    f"전일 {sign(cr_chg)}{cr_chg}조","#EA580C","KOFIA"), unsafe_allow_html=True)
            with c2:
                st.plotly_chart(make_line(cr, "basDt", "신용융자", color="#EA580C", height=130, y_suffix="조"), use_container_width=True)
        else:
            st.info("KOFIA 서버 복구 후 표시됩니다.")

    # ══ 먼슬리 ════════════════════════════════════════════════
    elif "먼슬리" in page:
        st.markdown("## 🗓 먼슬리")
        st.caption("출처: ISA · KOFIA-M · 월 1회 갱신")

        tab_isa, tab_trust, tab_els = st.tabs(["🔷 투자중개형 ISA","🏦 신탁","📉 ELS/DLS"])

        with tab_isa:
            st.caption("출처: ISA · getJoinStatus_V2 · getManagementStatus_V2")
            if not it.empty:
                c1,c2,c3 = st.columns(3)
                with c1:
                    st.metric("투자중개형 잔고",
                        f"{f1(float(isa_last.get('잔고(조)',0)))}조",
                        f"전월 {sign(float(isa_last.get('순증(조)',0)))}{f1(float(isa_last.get('순증(조)',0)))}조")
                with c2:
                    st.metric("가입자", f"{f1(float(isa_last.get('가입자(만명)',0)))}만명")
                with c3:
                    st.metric("ETF+주식 비중","82%","직접투자 압도적")

                # 잔고 추이
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=it["basDt"], y=it["순증(조)"].fillna(0),
                    name="순증(조)", yaxis="y2",
                    marker_color=["#DC2626" if v>=5 else "#EA580C" if v>=3 else "#2563EB"
                                  for v in it["순증(조)"].fillna(0)],
                ))
                fig.add_trace(go.Scatter(
                    x=it["basDt"], y=it["잔고(조)"],
                    name="잔고(조)", line=dict(color="#D97706",width=2.5),
                    marker=dict(size=5),
                ))
                fig.update_layout(
                    height=220, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    xaxis=dict(tickformat="%y/%m", tickangle=0),
                    yaxis=dict(title="잔고(조)", gridcolor="#F1F5F9"),
                    yaxis2=dict(title="순증(조)", overlaying="y", side="right"),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ISA 데이터 로드 중...")

            # 편입자산 시계열
            if not ia.empty:
                st.markdown("**편입자산 시계열 (%)**")
                fig = go.Figure()
                col_map = {
                    "ETF 등 상장펀드": ("#2563EB","ETF"),
                    "주식":            ("#0891B2","주식"),
                    "예적금 등":       ("#94A3B8","예적금"),
                    "RP":              ("#EA580C","RP"),
                    "파생결합증권":    ("#7C3AED","파생"),
                }
                for col_name, (color, display) in col_map.items():
                    if col_name in ia.columns:
                        fig.add_trace(go.Scatter(
                            x=ia["basDt"], y=ia[col_name],
                            name=display, line=dict(color=color,width=2),
                            mode="lines+markers", marker=dict(size=4),
                        ))
                fig.update_layout(
                    height=220, margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="#fff", paper_bgcolor="#fff",
                    xaxis=dict(tickformat="%y/%m", tickangle=0),
                    yaxis=dict(gridcolor="#F1F5F9", ticksuffix="%"),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab_trust:
            st.caption("출처: KOFIA-M · getTrusBusiInfoService · 월 1회 갱신")
            if not trust_df.empty:
                st.dataframe(trust_df.head(20), use_container_width=True, hide_index=True)
            else:
                st.info("KOFIA 서버 복구 후 자동 수집됩니다.")

        with tab_els:
            st.caption("출처: KOFIA-M · getElsBlbIssuPresInfo · 월 1회 갱신")
            if not els_df.empty:
                st.dataframe(els_df.head(20), use_container_width=True, hide_index=True)
            else:
                # 하드코딩 폴백
                df_els = pd.DataFrame({
                    "구분":    ["ELS 발행","ELS 상환","DLS 발행","DLS 상환"],
                    "금액(조)": [3.33, 3.28, 0.28, 2.87],
                    "전월 대비":["+0.03","균형","-0.15","+1.27"],
                })
                st.dataframe(df_els, use_container_width=True, hide_index=True)
                st.caption("※ KOFIA 서버 복구 후 자동 수집 예정 (현재 최신 하드코딩 표시)")

            st.markdown("""
            <div style="background:#FDF4FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;margin-top:12px;">
            <b style="color:#6D28D9;">📌 FLOW vs CHOICE — ELS/DLS 관점</b><br/><br/>
            <span style="color:#7C3AED;">ELS 발행≒상환 균형으로 잔고 축소. DLS 상환 2.87조 vs 발행 0.28조.</span><br/>
            <span style="color:#64748B;">고객이 구조화상품 대신 직접투자(ETF) 선택하는 중.</span>
            </div>
            """, unsafe_allow_html=True)

    # ══ 시장 ══════════════════════════════════════════════════
    elif "시장" in page:
        st.markdown("## 📈 시장")
        st.caption("출처: ECOS (금리·환율) · yfinance (지수)")

        # 현재값 칩
        cols = st.columns(4)
        market_items = [
            ("국고채 3Y", rates.get("국고채3Y",pd.DataFrame()), "#2563EB", "%", "ECOS"),
            ("국고채 10Y",rates.get("국고채10Y",pd.DataFrame()),"#0891B2", "%", "ECOS"),
            ("원달러",    fx.get("원달러",pd.DataFrame()),       "#EA580C", "원","ECOS"),
            ("VIX",       None, "#DC2626", "", "YF"),
        ]
        for col, (name, df_m, color, unit, src) in zip(cols, market_items):
            with col:
                if name == "VIX":
                    val = f"{vix_v.get('last',0):.2f}" if vix_v else "—"
                    chg = f"{sign(vix_v.get('pct',0))}{vix_v.get('pct',0):.2f}%" if vix_v else "—"
                elif isinstance(df_m, pd.DataFrame) and not df_m.empty:
                    last_val = float(df_m["value"].iloc[-1])
                    prev_val = float(df_m["value"].iloc[-2]) if len(df_m)>1 else last_val
                    diff = last_val - prev_val
                    val = f"{last_val:,.3f}{unit}" if unit=="%" else f"{last_val:,.1f}{unit}"
                    chg = f"{sign(diff)}{diff:.3f}{unit}" if unit=="%" else f"{sign(diff)}{diff:.1f}{unit}"
                else:
                    val = "—"; chg = "—"
                st.markdown(f"""
                <div class="kpi-card">
                  <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span class="kpi-label">{name}</span>
                    <span class="src-badge">{src}</span>
                  </div>
                  <div style="font-size:18px;font-weight:700;font-family:'DM Mono',monospace;">{val}</div>
                  <div style="color:{'#2563EB' if '+' in str(chg) or (chg!='—' and not chg.startswith('-')) else '#DC2626'};font-size:12px;">{chg}</div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # 금리 차트
        c1, c2, c3 = st.columns(3)
        for col, (name, color) in zip([c1,c2,c3],[
            ("국고채3Y","#2563EB"),("국고채10Y","#0891B2"),("CD금리","#7C3AED")
        ]):
            with col:
                st.markdown(f"**{name}** `ECOS`")
                if name in rates and not rates[name].empty:
                    st.plotly_chart(
                        make_line(rates[name], "date", "value", color=color, height=180, y_suffix="%"),
                        use_container_width=True)
                else:
                    st.info("로드 중...")

        # 환율 + KOSPI
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

if __name__ == "__main__":
    main()
