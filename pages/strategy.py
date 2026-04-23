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
    """수집 데이터를 바탕으로 100자 이내 데일리 코멘트 자동 생성"""
    mf  = data.get("market_funds", pd.DataFrame())
    cr  = data.get("credit",       pd.DataFrame())
    idx = data.get("indices",      {})
    it  = data.get("isa_trend",    pd.DataFrame())

    mf_val   = float(mf.iloc[-1].get("합계", 0))  if not mf.empty else 0
    cr_val   = float(cr.iloc[-1].get("신용융자", 0)) if not cr.empty else 0
    vix_val  = idx.get("VIX", {}).get("last", 0)
    isa_inc  = float(it.iloc[-1].get("순증(조)", 0)) if not it.empty else 0

    today = datetime.today().strftime("%m/%d")

    # 시나리오별 코멘트 (우선순위 순)
    if vix_val > 25:
        return f"[{today}] VIX {vix_val:.0f} 급등. 대기자금 {mf_val:.0f}조 유지 중 — 변동성 장세, 단기 ETF·현금 비중 확대 권고."
    if mf_val > 650:
        return f"[{today}] 대기자금 {mf_val:.0f}조 역대급. 신용융자 {cr_val:.1f}조 — 유입 대기 수요 강, 주식형·ISA 신규 유치 적기."
    if cr_val > 36:
        return f"[{today}] 신용융자 {cr_val:.1f}조 고점권. 레버리지 과열 신호 — 원금보장형·채권ETF 리밸런싱 제안 시점."
    if isa_inc > 5:
        return f"[{today}] ISA 투자중개형 전월 +{isa_inc:.1f}조 유입. ETF 직접투자 선호 확대 — ISA 연계 ETF MP 캠페인 추진."
    # 기본 코멘트
    return f"[{today}] 대기자금 {mf_val:.0f}조·융자 {cr_val:.1f}조 안정권. 주식형 플로우 모니터링 지속 — 방향성 확인 후 액션."


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
      <span style="color:#1E293B;font-size:13px;line-height:1.7;">{comment}</span>
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
