"""
collector.py
============
금융상품 판매동향 데이터 수집 모듈

데이터 출처:
  [KOFIA]   공공데이터포털 · GetKofiaStatisticsInfoService
  [ISA]     공공데이터포털 · GetISAInfoService_V2
  [ECOS]    한국은행 ECOS API
  [YF]      yfinance
  [KRX]     KRX Open API (POST + JSON + AUTH_KEY header)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import requests
import yfinance as yf

# ── 인증키 ────────────────────────────────────────────────────
KOFIA_KEY = ""
KRX_KEY = ""
ECOS_KEY = ""

BASE_KOFIA = "https://apis.data.go.kr/1160100/GetKofiaStatisticsInfoService"
BASE_ISA = "https://apis.data.go.kr/1160100/GetISAInfoService_V2"
BASE_ECOS = "https://ecos.bok.or.kr/api/StatisticSearch"
BASE_KRX = "https://data-dbg.krx.co.kr/svc/apis"
DEFAULT_TIMEOUT = 20


# ══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ══════════════════════════════════════════════════════════════

def _date_range(days_back: int = 30) -> tuple[str, str]:
    end = datetime.today()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _set_keys(kofia_key: str, krx_key: str, ecos_key: str) -> None:
    global KOFIA_KEY, KRX_KEY, ECOS_KEY
    KOFIA_KEY = kofia_key or ""
    KRX_KEY = krx_key or ""
    ECOS_KEY = ecos_key or ""


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    resp.raise_for_status()
    return resp.json()


def _to_dataframe(rows: Any) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, list):
        return pd.DataFrame(rows)
    if isinstance(rows, dict):
        return pd.DataFrame([rows])
    return pd.DataFrame()


def _extract_public_items(payload: Dict[str, Any]) -> pd.DataFrame:
    response = payload.get("response", {})
    header = response.get("header", {})
    result_code = str(header.get("resultCode", ""))
    if result_code and result_code != "00":
        raise ValueError(f"API resultCode={result_code}, resultMsg={header.get('resultMsg', '')}")

    body = response.get("body", {})
    items = body.get("items", {})
    rows = items.get("item", items) if isinstance(items, dict) else items
    return _to_dataframe(rows)


def _log_error(source: str, name: str, exc: Exception) -> None:
    print(f"  [{source}] {name} 오류: {exc}")


def _kofia_get(operation: str, extra: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    if not KOFIA_KEY:
        return pd.DataFrame()
    start_dt, end_dt = _date_range(60)
    params: Dict[str, Any] = {
        "serviceKey": KOFIA_KEY,
        "pageNo": "1",
        "numOfRows": "1000",
        "resultType": "json",
        "beginBasDt": start_dt,
        "endBasDt": end_dt,
    }
    if extra:
        params.update(extra)
    try:
        resp = requests.get(f"{BASE_KOFIA}/{operation}", params=params, timeout=DEFAULT_TIMEOUT)
        return _extract_public_items(_safe_json(resp))
    except Exception as exc:
        _log_error("KOFIA", operation, exc)
        return pd.DataFrame()


# ISA도 data.go.kr 응답 구조는 동일하게 처리

def _isa_get(operation: str, extra: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    if not KOFIA_KEY:
        return pd.DataFrame()
    start_dt, end_dt = _date_range(400)
    params: Dict[str, Any] = {
        "serviceKey": KOFIA_KEY,
        "pageNo": "1",
        "numOfRows": "1000",
        "resultType": "json",
        "beginBasDt": start_dt,
        "endBasDt": end_dt,
    }
    if extra:
        params.update(extra)
    try:
        resp = requests.get(f"{BASE_ISA}/{operation}", params=params, timeout=DEFAULT_TIMEOUT)
        return _extract_public_items(_safe_json(resp))
    except Exception as exc:
        _log_error("ISA", operation, exc)
        return pd.DataFrame()


def _ecos_get(stat_code: str, item_code: str, freq: str = "D", days_back: int = 30) -> pd.DataFrame:
    if not ECOS_KEY:
        return pd.DataFrame()
    end_dt = datetime.today().strftime("%Y%m%d")
    start_dt = (datetime.today() - timedelta(days=days_back)).strftime("%Y%m%d")
    url = f"{BASE_ECOS}/{ECOS_KEY}/json/kr/1/100/{stat_code}/{freq}/{start_dt}/{end_dt}/{item_code}"
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
        payload = _safe_json(resp)
        data = payload.get("StatisticSearch", {}).get("row", [])
        df = pd.DataFrame(data)
        if not df.empty and "DATA_VALUE" in df.columns:
            df["DATA_VALUE"] = pd.to_numeric(df["DATA_VALUE"], errors="coerce")
        return df
    except Exception as exc:
        _log_error("ECOS", f"{stat_code}/{item_code}", exc)
        return pd.DataFrame()


def _krx_post(endpoint: str, base_dt: str) -> pd.DataFrame:
    if not KRX_KEY:
        return pd.DataFrame()
    url = f"{BASE_KRX}/{endpoint}"
    headers = {"AUTH_KEY": KRX_KEY, "Content-Type": "application/json"}
    body = {"basDd": base_dt}
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=DEFAULT_TIMEOUT)
        payload = _safe_json(resp)
        if "OutBlock_1" not in payload:
            raise ValueError(f"Unexpected KRX response keys: {list(payload.keys())[:5]}")
        return pd.DataFrame(payload.get("OutBlock_1", []))
    except Exception as exc:
        _log_error("KRX", endpoint, exc)
        return pd.DataFrame()


def _last_bizday() -> str:
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _add_period_change(df: pd.DataFrame, value_col: str, out_col: str) -> pd.DataFrame:
    if df.empty or value_col not in df.columns:
        return df
    df = df.copy()
    df[out_col] = pd.to_numeric(df[value_col], errors="coerce").diff().round(2)
    return df


def _latest_numeric_sum(df: pd.DataFrame, exclude: Optional[list[str]] = None) -> float:
    if df.empty:
        return 0.0
    exclude = exclude or []
    num_cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    if not num_cols:
        return 0.0
    return float(df[num_cols].iloc[-1].fillna(0).sum())


# ══════════════════════════════════════════════════════════════
# DAILY 수집 함수들
# ══════════════════════════════════════════════════════════════

def get_fund_nav() -> pd.DataFrame:
    df = _kofia_get("getFundTotalNetEssetInfo", {"numOfRows": "500"})
    if df.empty:
        return df
    if "nPptTotAmt" in df.columns:
        df["nPptTotAmt"] = pd.to_numeric(df["nPptTotAmt"], errors="coerce")
    if "basDt" in df.columns:
        df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    if "ctg" in df.columns:
        df = df[df["ctg"] != "합계"]
    return df.dropna(subset=[c for c in ["basDt"] if c in df.columns])


def get_market_funds() -> pd.DataFrame:
    df_dep = _kofia_get("GetSecuritiesMarketTotalCapitalInfo")
    df_cma = _kofia_get("getCMAStatus", {"mngInvTgt": "합계"})
    df_fund = get_fund_nav()

    result: Dict[pd.Timestamp, Dict[str, float]] = {}

    if not df_dep.empty and {"invrDpsgAmt", "toCstRpchCndBndSlgBal", "basDt"}.issubset(df_dep.columns):
        df_dep["invrDpsgAmt"] = pd.to_numeric(df_dep["invrDpsgAmt"], errors="coerce")
        df_dep["toCstRpchCndBndSlgBal"] = pd.to_numeric(df_dep["toCstRpchCndBndSlgBal"], errors="coerce")
        df_dep["basDt"] = pd.to_datetime(df_dep["basDt"], format="%Y%m%d", errors="coerce")
        for _, row in df_dep.dropna(subset=["basDt"]).iterrows():
            dt = row["basDt"]
            result.setdefault(dt, {})
            result[dt]["예탁금"] = float(row.get("invrDpsgAmt", 0) or 0) / 1e12
            result[dt]["RP"] = float(row.get("toCstRpchCndBndSlgBal", 0) or 0) / 1e12

    if not df_cma.empty and {"actBal", "basDt"}.issubset(df_cma.columns):
        df_cma["actBal"] = pd.to_numeric(df_cma["actBal"], errors="coerce")
        df_cma["basDt"] = pd.to_datetime(df_cma["basDt"], format="%Y%m%d", errors="coerce")
        for dt, val in df_cma.dropna(subset=["basDt"]).groupby("basDt")["actBal"].sum().items():
            result.setdefault(dt, {})
            result[dt]["CMA"] = float(val) / 1e12

    if not df_fund.empty and {"ctg", "basDt", "nPptTotAmt"}.issubset(df_fund.columns):
        mmf = df_fund[df_fund["ctg"] == "단기금융"].groupby("basDt")["nPptTotAmt"].sum()
        for dt, val in mmf.items():
            result.setdefault(dt, {})
            result[dt]["MMF"] = float(val) / 1e12

    if not result:
        return pd.DataFrame()

    df_out = pd.DataFrame(result).T.sort_index()
    for col in ["예탁금", "RP", "CMA", "MMF"]:
        if col not in df_out.columns:
            df_out[col] = 0.0
    df_out["합계"] = df_out[["예탁금", "RP", "CMA", "MMF"]].fillna(0).sum(axis=1).round(1)
    return df_out.reset_index().rename(columns={"index": "basDt"})


def get_credit() -> pd.DataFrame:
    df = _kofia_get("getGrantingOfCreditBalanceInfo")
    if df.empty:
        return df
    if {"crdTrFingWhl", "basDt"}.issubset(df.columns):
        df["crdTrFingWhl"] = pd.to_numeric(df["crdTrFingWhl"], errors="coerce")
        df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
        df["신용융자"] = df["crdTrFingWhl"] / 1e12
        return df[["basDt", "신용융자"]].dropna(subset=["basDt"]).sort_values("basDt")
    return pd.DataFrame()


def get_market_rates() -> dict[str, pd.DataFrame]:
    items = {
        "국고채3Y": ("817Y002", "010200000"),
        "국고채10Y": ("817Y002", "010210000"),
        "CD금리": ("817Y002", "010502000"),
    }
    result: dict[str, pd.DataFrame] = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(stat, item, freq="D", days_back=30)
        if not df.empty and {"TIME", "DATA_VALUE"}.issubset(df.columns):
            out = df[["TIME", "DATA_VALUE"]].rename(columns={"TIME": "date", "DATA_VALUE": "value"})
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            result[name] = out.dropna(subset=["date"]).sort_values("date")
        time.sleep(0.2)
    return result


def get_exchange_rates() -> dict[str, pd.DataFrame]:
    items = {
        "원달러": ("731Y001", "0000001"),
        "원엔": ("731Y001", "0000002"),
    }
    result: dict[str, pd.DataFrame] = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(stat, item, freq="D", days_back=30)
        if not df.empty and {"TIME", "DATA_VALUE"}.issubset(df.columns):
            out = df[["TIME", "DATA_VALUE"]].rename(columns={"TIME": "date", "DATA_VALUE": "value"})
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            result[name] = out.dropna(subset=["date"]).sort_values("date")
        time.sleep(0.2)
    return result


def get_market_indices() -> dict[str, dict[str, float]]:
    tickers = {
        "KOSPI": "^KS11",
        "VIX": "^VIX",
        "SP500": "^GSPC",
        "US10Y": "^TNX",
    }
    result: dict[str, dict[str, float]] = {}
    for name, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            if len(hist) >= 2:
                last = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                pct = ((last - prev) / prev * 100) if prev else 0.0
                result[name] = {"last": last, "chg": last - prev, "pct": pct}
        except Exception as exc:
            _log_error("YF", ticker, exc)
    return result


def get_etf_top10() -> pd.DataFrame:
    df = _krx_post("etp/etf_bydd_trd", _last_bizday())
    if df.empty:
        return df
    for col in ["ACC_TRDVAL", "FLUC_RT"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    required = [c for c in ["ISU_NM", "ACC_TRDVAL", "FLUC_RT", "IDX_IND_NM"] if c in df.columns]
    if "ACC_TRDVAL" not in required:
        return pd.DataFrame()
    top10 = df.dropna(subset=["ACC_TRDVAL"]).sort_values("ACC_TRDVAL", ascending=False).head(10).copy()
    if "거래대금(억)" not in top10.columns:
        top10["거래대금(억)"] = (top10["ACC_TRDVAL"] / 1e8).round(0)
    return top10[required + ["거래대금(억)"]].reset_index(drop=True)


def get_bond_market() -> pd.DataFrame:
    df = _krx_post("bon/bnd_bydd_trd", _last_bizday())
    if df.empty:
        return df
    if {"ACC_TRDVAL", "ISU_NM"}.issubset(df.columns):
        df["ACC_TRDVAL"] = pd.to_numeric(df["ACC_TRDVAL"], errors="coerce")

        def classify(name: Any) -> str:
            name = str(name)
            if "국민주택" in name:
                return "국민주택채권"
            if "회사채" in name or any(x in name for x in ["(주)", "㈜", "Inc"]):
                return "회사채"
            if any(x in name for x in ["은행", "금융", "카드", "캐피탈"]):
                return "금융채"
            if any(x in name for x in ["공사", "공단", "정부", "국채"]):
                return "특수채"
            return "기타"

        df["유형"] = df["ISU_NM"].apply(classify)
        out = df.groupby("유형", dropna=False)["ACC_TRDVAL"].sum().reset_index()
        return out.sort_values("ACC_TRDVAL", ascending=False).reset_index(drop=True)
    return pd.DataFrame()


def get_gold() -> dict[str, float]:
    df = _krx_post("gen/gold_bydd_trd", _last_bizday())
    if df.empty:
        return {}
    row = df[df.get("ISU_CD", "") == "04020000"] if "ISU_CD" in df.columns else pd.DataFrame()
    if row.empty:
        row = df.iloc[[0]]
    row0 = row.iloc[0]

    def _num(key: str) -> float:
        val = str(row0.get(key, "0")).replace(",", "")
        return float(val or 0)

    return {
        "price": _num("TDD_CLSPRC"),
        "chg": _num("CMPPREVDD_PRC"),
        "fluc": _num("FLUC_RT"),
        "val": _num("ACC_TRDVAL") / 1e8,
    }


# ══════════════════════════════════════════════════════════════
# MONTHLY 수집 함수들
# ══════════════════════════════════════════════════════════════

def get_trust() -> pd.DataFrame:
    start_dt = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")
    end_dt = datetime.today().strftime("%Y%m%d")
    df = _kofia_get(
        "getTrusBusiInfoService",
        {"beginBasDt": start_dt, "endBasDt": end_dt, "numOfRows": "1000"},
    )
    if df.empty:
        return df
    if "basDt" in df.columns:
        df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    for col in df.columns:
        if col != "basDt":
            df[col] = pd.to_numeric(df[col], errors="ignore")
    return df.dropna(subset=[c for c in ["basDt"] if c in df.columns]).sort_values("basDt")


def get_els() -> pd.DataFrame:
    df = _kofia_get("getElsBlbIssuPresInfo", {"numOfRows": "500"})
    if df.empty:
        return df
    if "basDt" in df.columns:
        df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    for col in df.columns:
        if col != "basDt":
            df[col] = pd.to_numeric(df[col], errors="ignore")
    return df.dropna(subset=[c for c in ["basDt"] if c in df.columns]).sort_values("basDt")


def get_isa_trend() -> pd.DataFrame:
    df = _isa_get(
        "getJoinStatus_V2",
        {"beginBasDt": "20240101", "endBasDt": datetime.today().strftime("%Y%m%d")},
    )
    if df.empty:
        return df
    if not {"isaForm", "jnpnCnt", "invAmt", "basDt"}.issubset(df.columns):
        return pd.DataFrame()
    df = df[df["isaForm"] == "투자중개형 ISA"].copy()
    df["jnpnCnt"] = pd.to_numeric(df["jnpnCnt"], errors="coerce")
    df["invAmt"] = pd.to_numeric(df["invAmt"], errors="coerce")
    df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    result = df.groupby("basDt", dropna=False).agg(잔고=("invAmt", "sum"), 가입자=("jnpnCnt", "sum")).reset_index()
    result = result.dropna(subset=["basDt"]).sort_values("basDt")
    result["잔고(조)"] = (result["잔고"] / 1e12).round(2)
    result["가입자(만명)"] = (result["가입자"] / 1e4).round(1)
    result["순증(조)"] = result["잔고(조)"].diff().round(2)
    return result


def get_isa_assets() -> pd.DataFrame:
    df = _isa_get(
        "getManagementStatus_V2",
        {
            "beginBasDt": "20250101",
            "endBasDt": datetime.today().strftime("%Y%m%d"),
            "isaForm": "투자중개형 ISA",
            "ctg": "비중",
        },
    )
    if df.empty:
        return df
    required = {"bzds", "amt", "basDt", "incAstCtg"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    df = df[df["bzds"] == "증권"].copy()
    df["amt"] = pd.to_numeric(df["amt"], errors="coerce")
    df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    pivot = (
        df.pivot_table(index="basDt", columns="incAstCtg", values="amt", aggfunc="mean")
        .round(1)
        .reset_index()
        .sort_values("basDt")
    )
    return pivot


# ══════════════════════════════════════════════════════════════
# 전체 수집 (메인 함수)
# ══════════════════════════════════════════════════════════════

def collect_all(kofia_key: str, krx_key: str, ecos_key: str) -> dict[str, Any]:
    _set_keys(kofia_key, krx_key, ecos_key)

    print("📡 데이터 수집 시작...")
    data: dict[str, Any] = {}

    collectors = [
        ("fund_nav", "펀드 유형별 순자산", get_fund_nav),
        ("market_funds", "증시 대기자금", get_market_funds),
        ("credit", "신용융자", get_credit),
        ("rates", "금리 (ECOS)", get_market_rates),
        ("fx", "환율 (ECOS)", get_exchange_rates),
        ("indices", "글로벌 지수 (yfinance)", get_market_indices),
        ("etf_top10", "KRX ETF TOP10", get_etf_top10),
        ("bond_market", "채권 거래 현황", get_bond_market),
        ("gold", "금 시세 (KRX)", get_gold),
        ("trust", "신탁", get_trust),
        ("els", "ELS/DLS", get_els),
        ("isa_trend", "ISA 잔고 추이", get_isa_trend),
        ("isa_assets", "ISA 편입자산 시계열", get_isa_assets),
    ]

    total = len(collectors)
    for idx, (key, label, func) in enumerate(collectors, start=1):
        print(f"  [{idx}/{total}] {label}...")
        try:
            data[key] = func()
        except Exception as exc:
            _log_error("COLLECT", key, exc)
            data[key] = pd.DataFrame() if key not in {"indices", "gold", "rates", "fx"} else {}

    data["collected_at"] = datetime.now().strftime("%Y.%m.%d %H:%M")
    print(f"✅ 수집 완료: {data['collected_at']}")
    return data
