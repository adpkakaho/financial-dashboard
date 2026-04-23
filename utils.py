"""
utils.py
========
공통 유틸리티 — 날짜 계산, 숫자 포매팅, 로깅 설정
"""

import logging
from datetime import datetime, timedelta

# ── 로거 설정 ──────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

# ── 날짜 유틸 ──────────────────────────────────────────────────
def date_range(days_back: int = 60) -> tuple[str, str]:
    """(start_yyyymmdd, end_yyyymmdd) 반환"""
    end   = datetime.today()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

def today_str() -> str:
    return datetime.today().strftime("%Y%m%d")

def last_bizday() -> str:
    """직전 영업일 (주말 제외, 공휴일 미적용)"""
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")

def months_ago_str(months: int = 7) -> str:
    """오늘로부터 약 N개월 전 날짜 문자열 (일 단위 근사)"""
    d = datetime.today() - timedelta(days=30 * months)
    return d.strftime("%Y%m%d")

# ── 숫자 포매팅 ────────────────────────────────────────────────
def sign(v) -> str:
    try:
        return "+" if float(v) > 0 else ""
    except (TypeError, ValueError):
        return ""

def fmt1(v) -> str:
    try:
        return f"{float(v):.1f}"
    except (TypeError, ValueError):
        return "-"

def fmt2(v) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "-"

def to_float(v, default: float = 0.0) -> float:
    """콤마 포함 문자열도 안전하게 float 변환"""
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return default
