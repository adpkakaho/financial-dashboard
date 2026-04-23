"""
collector.py
============
금융상품 판매동향 데이터 수집 모듈

데이터 출처:
  [KOFIA]   공공데이터포털 · GetKofiaStatisticsInfoService
  [ISA]     공공데이터포털 · GetISAInfoService_V2
  [ECOS]    한국은행 ECOS API
  [YF]      yfinance (VIX, S&P500, KOSPI, 미국채10Y)
  [KRX]     KRX Open API (POST + JSON + AUTH_KEY header)
"""

import time
import requests
import pandas as pd
import yfinance as yf
from dataclasses import dataclass

from utils import get_logger, date_range, today_str, last_bizday, months_ago_str, to_float

logger = get_logger("collector")

# ── API 엔드포인트 상수 ────────────────────────────────────────
_BASE_KOFIA = "https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService"
_BASE_ISA   = "https://apis.data.go.kr/1160100/GetISAInfoService_V2"
_BASE_ECOS  = "https://ecos.bok.or.kr/api/StatisticSearch"
_BASE_KRX   = "https://data-dbg.krx.co.kr/svc/apis"

# ── API 키 컨테이너 (전역 변수 대신 dataclass 사용) ────────────
@dataclass(frozen=True)
class ApiKeys:
    kofia: str
    krx: str
    ecos: str

    def validate(self) -> list[str]:
        """빈 키 목록 반환 (경고용)"""
        missing = []
        if not self.kofia: missing.append("KOFIA_KEY")
        if not self.krx:   missing.append("KRX_KEY")
        if not self.ecos:  missing.append("ECOS_KEY")
        return missing


# ══════════════════════════════════════════════════════════════
# 공통 헬퍼 (키를 인자로 명시적 전달)
# ══════════════════════════════════════════════════════════════

def _kofia_get(keys: ApiKeys, operation: str, extra: dict | None = None) -> pd.DataFrame:
    """공공데이터포털 KOFIA API 호출"""
    start_dt, end_dt = date_range(60)
    params = {
        "serviceKey": keys.kofia,
        "pageNo":     "1",
        "numOfRows":  "1000",
        "resultType": "json",
        "beginBasDt": start_dt,
        "endBasDt":   end_dt,
    }
    if extra:
        params.update(extra)
    try:
        r = requests.get(f"{_BASE_KOFIA}/{operation}", params=params, timeout=15)
        r.raise_for_status()
        body  = r.json()["response"]["body"]
        items = body.get("items", {})
        rows  = items.get("item", items) if isinstance(items, dict) else items
        return pd.DataFrame(rows if isinstance(rows, list) else [rows])
    except Exception as e:
        logger.warning("[KOFIA] %s 오류: %s", operation, e)
        return pd.DataFrame()


def _isa_get(keys: ApiKeys, operation: str, extra: dict | None = None) -> pd.DataFrame:
    """ISA API 호출"""
    params = {
        "serviceKey": keys.kofia,
        "pageNo":     "1",
        "numOfRows":  "1000",
        "resultType": "json",
        "beginBasDt": "20200101",          # 하드코딩 제거 → 충분히 넓은 범위
        "endBasDt":   today_str(),
    }
    if extra:
        params.update(extra)
    try:
        r = requests.get(f"{_BASE_ISA}/{operation}", params=params, timeout=15)
        r.raise_for_status()
        body  = r.json()["response"]["body"]
        items = body.get("items", {})
        rows  = items.get("item", items) if isinstance(items, dict) else items
        return pd.DataFrame(rows if isinstance(rows, list) else [rows])
    except Exception as e:
        logger.warning("[ISA] %s 오류: %s", operation, e)
        return pd.DataFrame()


def _ecos_get(keys: ApiKeys, stat_code: str, item_code: str,
              freq: str = "D", days_back: int = 60) -> pd.DataFrame:
    """한국은행 ECOS API 호출 — 키를 URL 경로 대신 별도 처리"""
    end_dt   = today_str()
    start_dt = date_range(days_back)[0]
    # ECOS는 키를 경로에 포함하는 구조이나, 로그 시 마스킹
    url = f"{_BASE_ECOS}/{keys.ecos}/json/kr/1/100/{stat_code}/{freq}/{start_dt}/{end_dt}/{item_code}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json().get("StatisticSearch", {}).get("row", [])
        df   = pd.DataFrame(data)
        if not df.empty and "DATA_VALUE" in df.columns:
            df["DATA_VALUE"] = pd.to_numeric(df["DATA_VALUE"], errors="coerce")
            df["date"] = pd.to_datetime(df["TIME"], format="%Y%m%d", errors="coerce")
        return df
    except Exception as e:
        logger.warning("[ECOS] %s/%s 오류: %s", stat_code, item_code, e)
        return pd.DataFrame()


def _krx_post(keys: ApiKeys, endpoint: str, base_dt: str) -> pd.DataFrame:
    """KRX Open API 호출"""
    url     = f"{_BASE_KRX}/{endpoint}"
    headers = {"AUTH_KEY": keys.krx, "Content-Type": "application/json"}
    body    = {"basDd": base_dt}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=15)
        r.raise_for_status()
        payload = r.json()
        # KRX 응답 구조 유연하게 처리 (OutBlock_1 없는 경우 대비)
        rows = payload.get("OutBlock_1") or payload.get("output") or []
        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning("[KRX] %s 오류: %s", endpoint, e)
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
# 채권 분류 (별도 함수로 분리)
# ══════════════════════════════════════════════════════════════

def _classify_bond(name: str) -> str:
    name = str(name)
    if "국민주택" in name:
        return "국민주택채권"
    if any(x in name for x in ["은행", "금융", "카드", "캐피탈"]):
        return "금융채"
    if any(x in name for x in ["공사", "공단", "도로", "수자원", "국채"]):
        return "특수채"
    return "기타"


# ══════════════════════════════════════════════════════════════
# DAILY 수집 함수
# ══════════════════════════════════════════════════════════════

def get_fund_nav(keys: ApiKeys) -> pd.DataFrame:
    """[KOFIA-D] 펀드 유형별 순자산"""
    df = _kofia_get(keys, "getFundTotalNetEssetInfo", {"numOfRows": "500"})
    if df.empty:
        return df
    df["nPptTotAmt"] = pd.to_numeric(df["nPptTotAmt"], errors="coerce")
    df["basDt"]      = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    return df[df["ctg"] != "합계"]


def get_market_funds(keys: ApiKeys) -> pd.DataFrame:
    """[KOFIA-D] 증시 대기자금 합산
    - 4개 항목(예탁금/RP/CMA/MMF) 모두 있는 날짜만 합계 표시
    - 호버 시 세부 구성 확인 가능하도록 항목별 컬럼 유지
    """
    df_dep  = _kofia_get(keys, "getSecuritiesMarketTotalCapitalInfo")
    df_cma  = _kofia_get(keys, "getCMAStatus")
    df_fund = get_fund_nav(keys)
    result: dict = {}

    if not df_dep.empty:
        df_dep["invrDpsgAmt"]           = pd.to_numeric(df_dep["invrDpsgAmt"], errors="coerce")
        df_dep["toCstRpchCndBndSlgBal"] = pd.to_numeric(df_dep["toCstRpchCndBndSlgBal"], errors="coerce")
        df_dep["basDt"] = pd.to_datetime(df_dep["basDt"], format="%Y%m%d", errors="coerce")
        for _, row in df_dep.iterrows():
            dt = row["basDt"]
            result.setdefault(dt, {})
            result[dt]["예탁금"] = round(to_float(row["invrDpsgAmt"]) / 1e12, 1)
            result[dt]["RP"]    = round(to_float(row["toCstRpchCndBndSlgBal"]) / 1e12, 1)

    if not df_cma.empty:
        df_cma["actBal"] = pd.to_numeric(df_cma["actBal"], errors="coerce")
        df_cma["basDt"]  = pd.to_datetime(df_cma["basDt"], format="%Y%m%d", errors="coerce")
        df_cma = df_cma[df_cma["mngInvTgt"] == "합계"]
        cma_daily = df_cma.groupby("basDt")["actBal"].sum()
        for dt, val in cma_daily.items():
            result.setdefault(dt, {})
            result[dt]["CMA"] = round(val / 1e12, 1)

    if not df_fund.empty:
        mmf = df_fund[df_fund["ctg"] == "단기금융"].groupby("basDt")["nPptTotAmt"].sum()
        for dt, val in mmf.items():
            result.setdefault(dt, {})
            result[dt]["MMF"] = round(val / 1e12, 1)

    if not result:
        return pd.DataFrame()

    df_out = pd.DataFrame(result).T.sort_index()

    # 영업일 기준 날짜 gap forward-fill (각 항목 독립적으로)
    df_out.index = pd.to_datetime(df_out.index)
    biz_idx = pd.bdate_range(df_out.index.min(), df_out.index.max())
    df_out = df_out.reindex(biz_idx).ffill()

    # 합계: 4개 항목 모두 존재하는 날짜만 계산 (일부 누락 날짜는 NaN → 그래프 공백)
    cols = ["예탁금", "RP", "CMA", "MMF"]
    for col in cols:
        if col not in df_out.columns:
            df_out[col] = pd.NA
    all_present = df_out[cols].notna().all(axis=1)
    df_out["합계"] = df_out[cols].sum(axis=1).where(all_present).round(1)

    return df_out.reset_index().rename(columns={"index": "basDt"})


def get_credit(keys: ApiKeys) -> pd.DataFrame:
    """[KOFIA-D] 신용융자 잔고"""
    df = _kofia_get(keys, "getGrantingOfCreditBalanceInfo")
    if df.empty:
        return df
    df["crdTrFingWhl"] = pd.to_numeric(df["crdTrFingWhl"], errors="coerce")
    df["basDt"]        = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    df["신용융자"]      = (df["crdTrFingWhl"] / 1e12).round(2)
    return df[["basDt", "신용융자"]].sort_values("basDt")


def get_market_rates(keys: ApiKeys) -> dict:
    """[ECOS] 금리 시계열 · 817Y002"""
    items = {
        "국고채3Y":  ("817Y002", "010200000"),
        "국고채10Y": ("817Y002", "010210000"),
        "CD금리":    ("817Y002", "010502000"),
    }
    result = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(keys, stat, item)
        if not df.empty and "date" in df.columns:
            result[name] = (df[["date", "DATA_VALUE"]]
                            .rename(columns={"DATA_VALUE": "value"})
                            .dropna().sort_values("date"))
        time.sleep(0.2)
    return result


def get_exchange_rates(keys: ApiKeys) -> dict:
    """[ECOS] 환율 시계열 · 731Y001"""
    items = {
        "원달러": ("731Y001", "0000001"),
        "원엔":   ("731Y001", "0000002"),
    }
    result = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(keys, stat, item)
        if not df.empty and "date" in df.columns:
            result[name] = (df[["date", "DATA_VALUE"]]
                            .rename(columns={"DATA_VALUE": "value"})
                            .dropna().sort_values("date"))
        time.sleep(0.2)
    return result


def get_market_indices() -> dict:
    """[YF] 글로벌 지수 현재값"""
    tickers = {
        "KOSPI": "^KS11",
        "VIX":   "^VIX",
        "SP500": "^GSPC",
        "US10Y": "^TNX",
    }
    result = {}
    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            if not data.empty and len(data) >= 2:
                last = float(data["Close"].iloc[-1])
                prev = float(data["Close"].iloc[-2])
                result[name] = {
                    "last": round(last, 2),
                    "chg":  round(last - prev, 2),
                    "pct":  round((last - prev) / prev * 100, 2),
                }
        except Exception as e:
            logger.warning("[YF] %s 오류: %s", ticker, e)
    return result


def get_kospi_history() -> pd.DataFrame:
    """[YF] KOSPI 30일 시계열"""
    try:
        df = yf.Ticker("^KS11").history(period="1mo", auto_adjust=True)
        if not df.empty:
            df = df.reset_index()[["Date", "Close"]].rename(
                columns={"Date": "date", "Close": "value"})
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            return df.sort_values("date")
    except Exception as e:
        logger.warning("[YF] KOSPI history 오류: %s", e)
    return pd.DataFrame()


def get_etf_top10(keys: ApiKeys) -> pd.DataFrame:
    """[KRX-ETF] ETF 거래대금 TOP10 — 영업일 최대 3일 소급"""
    df = pd.DataFrame()
    bizday = last_bizday()
    # 데이터 없는 날 대비 최대 3일 소급
    from datetime import datetime, timedelta
    d = datetime.strptime(bizday, "%Y%m%d")
    for _ in range(3):
        df = _krx_post(keys, "etp/etf_bydd_trd", d.strftime("%Y%m%d"))
        if not df.empty:
            break
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)

    if df.empty:
        return df
    df["ACC_TRDVAL"] = pd.to_numeric(df.get("ACC_TRDVAL", pd.Series(dtype=float)), errors="coerce")
    df["FLUC_RT"]    = pd.to_numeric(df.get("FLUC_RT",    pd.Series(dtype=float)), errors="coerce")
    top10 = (df.dropna(subset=["ACC_TRDVAL"])
               .sort_values("ACC_TRDVAL", ascending=False)
               .head(10)[["ISU_NM", "ACC_TRDVAL", "FLUC_RT", "IDX_IND_NM"]]
               .reset_index(drop=True))
    top10["거래대금(억)"] = (top10["ACC_TRDVAL"] / 1e8).round(0).astype(int)
    return top10


def _krx_range(keys: ApiKeys, endpoint: str, days_back: int = 30) -> pd.DataFrame:
    """KRX API를 days_back 일치 반복 호출해 시계열 DataFrame 반환"""
    from datetime import datetime, timedelta
    frames = []
    end = datetime.strptime(last_bizday(), "%Y%m%d")
    start = end - timedelta(days=days_back)
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            df = _krx_post(keys, endpoint, cur.strftime("%Y%m%d"))
            if not df.empty:
                df["_date"] = cur
                frames.append(df)
            time.sleep(0.05)
        cur += timedelta(days=1)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def get_bond_market(keys: ApiKeys) -> pd.DataFrame:
    """[KRX-BON] 채권 거래 유형별 집계 — 당일 스냅샷 (최대 3일 소급)"""
    from datetime import datetime, timedelta
    df = pd.DataFrame()
    d = datetime.strptime(last_bizday(), "%Y%m%d")
    for _ in range(3):
        df = _krx_post(keys, "bon/bnd_bydd_trd", d.strftime("%Y%m%d"))
        if not df.empty:
            break
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    if df.empty:
        return df
    df["ACC_TRDVAL"] = pd.to_numeric(df.get("ACC_TRDVAL", pd.Series(dtype=float)), errors="coerce")
    df["유형"] = df["ISU_NM"].apply(_classify_bond)
    result = (df.groupby("유형")["ACC_TRDVAL"].sum()
                .reset_index().sort_values("ACC_TRDVAL", ascending=False))
    result["거래대금(억)"] = (result["ACC_TRDVAL"] / 1e8).round(1)
    return result


def get_bond_history(keys: ApiKeys, days_back: int = 30) -> pd.DataFrame:
    """[KRX-BON] 채권 유형별 거래대금 시계열"""
    df_all = _krx_range(keys, "bon/bnd_bydd_trd", days_back)
    if df_all.empty:
        return pd.DataFrame()
    df_all["ACC_TRDVAL"] = pd.to_numeric(df_all.get("ACC_TRDVAL", pd.Series(dtype=float)), errors="coerce")
    df_all["유형"] = df_all["ISU_NM"].apply(_classify_bond)
    result = (df_all.groupby(["_date", "유형"])["ACC_TRDVAL"].sum()
                    .reset_index().rename(columns={"_date": "date"}))
    result["거래대금(억)"] = (result["ACC_TRDVAL"] / 1e8).round(1)
    return result.sort_values("date")


def get_gold(keys: ApiKeys) -> dict:
    """[KRX-GLD] 금 현물 시세 — 최대 3일 소급"""
    from datetime import datetime, timedelta
    df = pd.DataFrame()
    d = datetime.strptime(last_bizday(), "%Y%m%d")
    for _ in range(3):
        df = _krx_post(keys, "gen/gold_bydd_trd", d.strftime("%Y%m%d"))
        if not df.empty:
            break
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    if df.empty:
        return {}
    row = df[df["ISU_CD"] == "04020000"] if "ISU_CD" in df.columns else pd.DataFrame()
    if row.empty:
        row = df.iloc[[0]]
    row = row.iloc[0]
    return {
        "price": to_float(row.get("TDD_CLSPRC", 0)),
        "chg":   to_float(row.get("CMPPREVDD_PRC", 0)),
        "fluc":  to_float(row.get("FLUC_RT", 0)),
        "val":   round(to_float(row.get("ACC_TRDVAL", 0)) / 1e8, 1),
    }


def get_gold_history(keys: ApiKeys, days_back: int = 30) -> pd.DataFrame:
    """[KRX-GLD] 금 시세 시계열"""
    df_all = _krx_range(keys, "gen/gold_bydd_trd", days_back)
    if df_all.empty:
        return pd.DataFrame()
    target = df_all[df_all["ISU_CD"] == "04020000"] if "ISU_CD" in df_all.columns else df_all
    if target.empty:
        target = df_all
    rows = []
    for date, grp in target.groupby("_date"):
        row = grp.iloc[0]
        rows.append({
            "date":  date,
            "price": to_float(row.get("TDD_CLSPRC", 0)),
            "fluc":  to_float(row.get("FLUC_RT", 0)),
            "val":   round(to_float(row.get("ACC_TRDVAL", 0)) / 1e8, 1),
        })
    return pd.DataFrame(rows).sort_values("date")


# ══════════════════════════════════════════════════════════════
# MONTHLY 수집 함수
# ══════════════════════════════════════════════════════════════

def get_trust(keys: ApiKeys) -> pd.DataFrame:
    """[KOFIA-M] 신탁 업권별 수탁총액"""
    return _kofia_get(keys, "getTrustScaleInfo", {
        "beginBasDt": months_ago_str(7),
        "endBasDt":   today_str(),
        "numOfRows":  "1000",
    })


def get_els(keys: ApiKeys) -> pd.DataFrame:
    """[KOFIA-M] ELS/ELB 발행·상환"""
    df = _kofia_get(keys, "getELSAndELBInfo", {
        "beginBasDt": months_ago_str(7),
        "endBasDt":   today_str(),
        "numOfRows":  "200",
    })
    if df.empty:
        return df
    for col in df.select_dtypes(include="object").columns:
        if col != "basDt":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_isa_trend(keys: ApiKeys) -> pd.DataFrame:
    """[ISA] 투자중개형 월별 잔고"""
    df = _isa_get(keys, "getJoinStatus_V2")
    if df.empty:
        return df
    df = df[df["isaForm"] == "투자중개형 ISA"].copy()
    df["jnpnCnt"] = pd.to_numeric(df["jnpnCnt"], errors="coerce")
    df["invAmt"]  = pd.to_numeric(df["invAmt"],  errors="coerce")
    df["basDt"]   = pd.to_datetime(df["basDt"],  format="%Y%m%d", errors="coerce")
    result = df.groupby("basDt").agg(
        잔고=("invAmt", "sum"), 가입자=("jnpnCnt", "sum")
    ).reset_index()
    result["잔고(조)"]    = (result["잔고"]   / 1e12).round(2)
    result["가입자(만명)"] = (result["가입자"] / 1e4).round(1)
    result["순증(조)"]    = result["잔고(조)"].diff().round(2)
    return result.sort_values("basDt")


def get_isa_assets(keys: ApiKeys) -> pd.DataFrame:
    """[ISA] 투자중개형 편입자산 시계열"""
    df = _isa_get(keys, "getManagementStatus_V2", {
        "isaForm":    "투자중개형 ISA",
        "ctg":        "비중",
        "beginBasDt": "20250101",
        "endBasDt":   today_str(),
    })
    if df.empty:
        return df
    df = df[df["bzds"] == "증권"].copy()
    df["amt"]   = pd.to_numeric(df["amt"],  errors="coerce")
    df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    return (df.pivot_table(index="basDt", columns="incAstCtg", values="amt", aggfunc="mean")
              .round(1).reset_index().sort_values("basDt"))


# ══════════════════════════════════════════════════════════════
# 전체 수집 진입점
# ══════════════════════════════════════════════════════════════

def collect_all(kofia_key: str, krx_key: str, ecos_key: str) -> dict:
    """모든 데이터를 수집하여 dict로 반환"""
    keys = ApiKeys(kofia=kofia_key, krx=krx_key, ecos=ecos_key)

    missing = keys.validate()
    if missing:
        logger.warning("누락된 API 키: %s — 해당 데이터는 수집되지 않습니다.", missing)

    logger.info("📡 데이터 수집 시작...")
    data: dict = {}

    steps = [
        ("fund_nav",      "펀드 유형별 순자산",      lambda: get_fund_nav(keys)),
        ("market_funds",  "증시 대기자금",            lambda: get_market_funds(keys)),
        ("credit",        "신용융자",                 lambda: get_credit(keys)),
        ("rates",         "금리 (ECOS)",              lambda: get_market_rates(keys)),
        ("fx",            "환율 (ECOS)",              lambda: get_exchange_rates(keys)),
        ("indices",       "글로벌 지수 (yfinance)",   lambda: get_market_indices()),
        ("kospi_history", "KOSPI 시계열 (yfinance)",  lambda: get_kospi_history()),
        ("etf_top10",     "KRX ETF TOP10",            lambda: get_etf_top10(keys)),
        ("bond_market",   "KRX 채권",                 lambda: get_bond_market(keys)),
        ("bond_history",  "KRX 채권 시계열",             lambda: get_bond_history(keys)),
        ("gold",          "KRX 금",                   lambda: get_gold(keys)),
        ("gold_history",  "KRX 금 시계열",               lambda: get_gold_history(keys)),
        ("isa_trend",     "ISA 잔고 추이",             lambda: get_isa_trend(keys)),
        ("isa_assets",    "ISA 편입자산",              lambda: get_isa_assets(keys)),
        ("trust",         "신탁",                     lambda: get_trust(keys)),
        ("els",           "ELS/DLS",                  lambda: get_els(keys)),
    ]

    for key, label, fn in steps:
        logger.info("  [%s] 수집 중...", label)
        try:
            data[key] = fn()
        except Exception as e:
            logger.error("  [%s] 수집 실패: %s", label, e)
            data[key] = pd.DataFrame() if key != "indices" else {}

    from datetime import datetime
    data["collected_at"] = datetime.now().strftime("%Y.%m.%d %H:%M")
    logger.info("✅ 수집 완료: %s", data["collected_at"])
    return data
