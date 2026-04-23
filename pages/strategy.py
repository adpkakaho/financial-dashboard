"""
pages/strategy.py
=================
상품전략 시그널 페이지 — FLOW vs CHOICE + 데일리 코멘트
"""

import pandas as pd
import streamlit as st
from datetime import datetime
from utils import sign, fmt1


def _build_daily_comment(data: dict) -> str:
    """수집 데이터를 바탕으로 300자 이내 문장형 데일리 코멘트 자동 생성"""
    mf  = data.get("market_funds", pd.DataFrame())
    cr  = data.get("credit",       pd.DataFrame())
    idx = data.get("indices",      {})
    it  = data.get("isa_trend",    pd.DataFrame())
    fn  = data.get("fund_nav",     pd.DataFrame())

    mf_val   = float(mf.iloc[-1].get("합계", 0))    if not mf.empty else 0
    mf_prev  = float(mf.iloc[-2].get("합계", 0))    if len(mf) > 1  else mf_val
    cr_val   = float(cr.iloc[-1].get("신용융자", 0)) if not cr.empty else 0
    vix_val  = idx.get("VIX",   {}).get("last", 0)
    vix_pct  = idx.get("VIX",   {}).get("pct",  0)
    kospi    = idx.get("KOSPI", {}).get("last",  0)
    isa_inc  = float(it.iloc[-1].get("순증(조)", 0)) if not it.empty else 0

    mf_flow  = round(mf_val - mf_prev, 1)
    today    = datetime.today().strftime("%Y년 %m월 %d일")

    # 주식형 펀드 주간 플로우
    eq_wflow = 0.0
    if not fn.empty:
        eq = fn[fn["ctg"] == "주식형"].sort_values("basDt")
        if len(eq) >= 6:
            eq_wflow = round((eq["nPptTotAmt"].iloc[-1] - eq["nPptTotAmt"].iloc[-6]) / 1e12, 1)

    # 시나리오별 300자 문장형 코멘트
    if vix_val > 25:
        return (
            f"{today} 기준, VIX가 {vix_val:.1f}로 급등하며 글로벌 변동성이 고조되고 있습니다. "
            f"증시 대기자금은 {mf_val:.0f}조원 수준을 유지 중이나 신용융자 {cr_val:.1f}조원으로 "
            f"레버리지 포지션이 혼재합니다. 변동성 장세에서는 단기 ETF 및 현금성 자산 비중을 확대하고, "
            f"원금보장형 상품 중심의 포트폴리오 리밸런싱을 고객에게 적극 제안하는 것이 유효합니다."
        )
    if mf_val > 650:
        return (
            f"{today} 기준, 증시 대기자금(예탁금·RP·CMA·MMF 합계)이 {mf_val:.0f}조원으로 "
            f"역대급 수준을 기록 중이며 전일 대비 {'+' if mf_flow >= 0 else ''}{mf_flow:.1f}조원 변동했습니다. "
            f"신용융자 {cr_val:.1f}조원, 주식형 펀드 주간 유입 {'+' if eq_wflow >= 0 else ''}{eq_wflow:.1f}조원으로 "
            f"위험자산 선호가 확인됩니다. 주식형·ISA 투자중개형 신규 유치 캠페인의 적기로 판단됩니다."
        )
    if cr_val > 36:
        return (
            f"{today} 기준, 신용융자 잔고가 {cr_val:.1f}조원으로 고점권에 근접했습니다. "
            f"레버리지 과열 신호가 감지되는 만큼 신규 유입 자금의 리스크 관리가 필요한 시점입니다. "
            f"KOSPI {kospi:,.0f}pt, VIX {vix_val:.1f} 수준에서 채권형 ETF 또는 원금보장형 상품으로의 "
            f"리밸런싱을 고객에게 먼저 제안하는 선제적 대응이 권고됩니다."
        )
    if isa_inc > 5:
        return (
            f"{today} 기준, ISA 투자중개형 잔고가 전월 대비 +{isa_inc:.1f}조원 증가하며 구조적 성장세를 이어가고 있습니다. "
            f"ETF·주식 직접투자 비중이 80%를 상회하는 흐름 속에서, "
            f"증시 대기자금 {mf_val:.0f}조원의 절세 수요를 ISA로 연결하는 ETF 연계 MP 캠페인이 "
            f"가장 효과적인 접점 전략으로 분석됩니다."
        )
    # 기본 코멘트
    return (
        f"{today} 기준, 증시 대기자금 {mf_val:.0f}조원·신용융자 {cr_val:.1f}조원으로 전반적으로 안정권에 있습니다. "
        f"KOSPI {kospi:,.0f}pt, VIX {vix_val:.1f} 수준에서 방향성이 뚜렷하지 않은 만큼 "
        f"주식형 펀드 플로우({'+' if eq_wflow >= 0 else ''}{eq_wflow:.1f}조 주간)와 "
        f"외국인 수급 동향을 추가 확인한 뒤 액션 타이밍을 결정하는 것이 바람직합니다."
    )


def render(data: dict) -> None:
    st.markdown("## 🎯 상품전략 시그널")
    st.caption("실제 수집 데이터 자동 도출 · 팩트 중심 · KOFIA·ISA·ECOS·KRX")

    # ── 3대 시그널 카드 ──
    cols = st.columns(3)
    signals = [
        ("🔴 즉시", "#DC2626", "이중 포지셔닝", "KOFIA-D",
         "주식형 대규모 유입 + MMF 유지", "공격+헷징 동시. 불확실성 속 적극 참여.",
         "멀티에셋 / ISA 투자중개형 신규 유치"),
        ("🟡 단기", "#D97706", "증시 대기자금 역대급", "KOFIA-D",
         "예탁금+RP+CMA+MMF 합계 600조+", "저점 대비 급등. 유입 대기 수요 역대급.",
         "주식형 ETF / ISA 신규 개설 이벤트"),
        ("🟢 중기", "#059669", "ISA 투자중개형 성장", "ISA",
         "ETF+주식 80%+ 직접투자 압도", "셀프 직접투자 고객 급증.",
         "ETF 연계 ISA MP / 예적금→ETF 캠페인"),
    ]
    for col, (level, color, title, src, signal, meaning, action) in zip(cols, signals):
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

    # ── FLOW vs CHOICE ──
    st.markdown("### 📌 FLOW vs CHOICE")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div style="background:#EFF6FF;border-radius:8px;padding:14px;"><b style="color:#1D4ED8;">단기 흐름 (FLOW)</b><br/><br/>'
                    '<span style="color:#2563EB;">• 주식형 주간 대규모 유입 ↑</span><br/>'
                    '<span style="color:#2563EB;">• 증시 대기자금 역대급 ↑</span><br/>'
                    '<span style="color:#2563EB;">• ETF 거래대금 집중 ↑</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div style="background:#FDF4FF;border-radius:8px;padding:14px;"><b style="color:#6D28D9;">중기 선택 (CHOICE)</b><br/><br/>'
                    '<span style="color:#7C3AED;">• ELS 순상환 지속</span><br/>'
                    '<span style="color:#7C3AED;">• DLS 상환 압도 (발행의 10배)</span><br/>'
                    '<span style="color:#7C3AED;">• 채권형 유입 소극적</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div style="background:#F0FDF4;border-radius:8px;padding:14px;"><b style="color:#065F46;">해석</b><br/><br/>'
                    '<span style="color:#047857;font-size:12px;line-height:1.7;">단기 자금 유입 강세에도 구조화상품 수요 제한적. '
                    '고객은 직접투자(ETF·주식) 선호 확대.<br/><b>채널·플랫폼 경쟁력이 핵심.</b></span></div>',
                    unsafe_allow_html=True)

    # ── 데일리 코멘트 (신규 추가) ──
    comment = _build_daily_comment(data)
    st.markdown(f"""
    <div style="background:#F8FAFC;border:1px solid #CBD5E1;border-left:4px solid #2563EB;
      border-radius:8px;padding:12px 16px;margin-top:16px;">
      <span style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:0.08em;">📝 DAILY COMMENT</span><br/>
      <span style="color:#1E293B;font-size:13px;line-height:1.8;white-space:pre-line;">{comment}</span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── 자금흐름 매핑 테이블 ──
    st.markdown("### 자금흐름 → 고객수요 → 상품 오퍼링")
    df_map = pd.DataFrame([
        ("주식형 대규모 유입 ▲",  "위험자산 선호",       "주식형 ETF / 성장형 포트",  "KOFIA"),
        ("대기자금 역대급 ▲",     "증시 유입 대기",       "주식연계 ELB / 채권형 ETF", "KOFIA"),
        ("ISA 투자중개형 급증 ▲", "절세+직접투자 동시",  "ETF 연계 ISA / ISA MP",     "ISA"),
        ("재간접 유입 ▲",         "글로벌 분산 선호",     "글로벌 재간접 / 멀티에셋",  "KOFIA"),
        ("신용융자 증가 ▲",       "레버리지 투자 확대",   "레버리지 ETF",              "KOFIA"),
        ("ELS 순상환 지속 ▼",     "구조화상품 기피",      "ELB / 원금보장형 전환",     "KOFIA"),
    ], columns=["자금흐름", "고객수요", "추천 상품", "출처"])
    st.dataframe(df_map, use_container_width=True, hide_index=True)
