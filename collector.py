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

import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time

# ── 인증키 (collect_all 호출 시 주입) ────────────────────────
KOFIA_KEY = ""
KRX_KEY   = ""
ECOS_KEY  = ""

BASE_KOFIA = "https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService"
BASE_ISA   = "https://apis.data.go.kr/1160100/service/GetISAInfoService_V2"
BASE_ECOS  = "https://ecos.bok.or.kr/api/StatisticSearch"
BASE_KRX   = "https://data-dbg.krx.co.kr/svc/apis"

# ══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ══════════════════════════════════════════════════════════════

def _date_range(days_back=60):
    end   = datetime.today()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

def _last_bizday():
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")

def _kofia_get(operation, extra={}):
    """공공데이터포털 KOFIA API 호출"""
    start_dt, end_dt = _date_range(60)
    params = {
        "serviceKey": KOFIA_KEY,
        "pageNo":     "1",
        "numOfRows":  "1000",
        "resultType": "json",
        "beginBasDt": start_dt,
        "endBasDt":   end_dt,
    }
    params.update(extra)
    try:
        r = requests.get(f"{BASE_KOFIA}/{operation}", params=params, timeout=15)
        r.raise_for_status()
        body  = r.json()["response"]["body"]
        items = body.get("items", {})
        rows  = items.get("item", items) if isinstance(items, dict) else items
        return pd.DataFrame(rows if isinstance(rows, list) else [rows])
    except Exception as e:
        print(f"  [KOFIA] {operation} 오류: {e}")
        return pd.DataFrame()

def _isa_get(operation, extra={}):
    """ISA API 호출"""
    params = {
        "serviceKey": KOFIA_KEY,
        "pageNo":     "1",
        "numOfRows":  "1000",
        "resultType": "json",
        "beginBasDt": "20240101",
        "endBasDt":   datetime.today().strftime("%Y%m%d"),
    }
    params.update(extra)
    try:
        r = requests.get(f"{BASE_ISA}/{operation}", params=params, timeout=15)
        r.raise_for_status()
        body  = r.json()["response"]["body"]
        items = body.get("items", {})
        rows  = items.get("item", items) if isinstance(items, dict) else items
        return pd.DataFrame(rows if isinstance(rows, list) else [rows])
    except Exception as e:
        print(f"  [ISA] {operation} 오류: {e}")
        return pd.DataFrame()

def _ecos_get(stat_code, item_code, freq="D", days_back=60):
    """한국은행 ECOS API 호출"""
    end_dt   = datetime.today().strftime("%Y%m%d")
    start_dt = (datetime.today() - timedelta(days=days_back)).strftime("%Y%m%d")
    url = f"{BASE_ECOS}/{ECOS_KEY}/json/kr/1/100/{stat_code}/{freq}/{start_dt}/{end_dt}/{item_code}"
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
        print(f"  [ECOS] {stat_code}/{item_code} 오류: {e}")
        return pd.DataFrame()

def _krx_post(endpoint, base_dt):
    """KRX Open API 호출"""
    url     = f"{BASE_KRX}/{endpoint}"
    headers = {"AUTH_KEY": KRX_KEY, "Content-Type": "application/json"}
    body    = {"basDd": base_dt}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=15)
        r.raise_for_status()
        return pd.DataFrame(r.json().get("OutBlock_1", []))
    except Exception as e:
        print(f"  [KRX] {endpoint} 오류: {e}")
        return pd.DataFrame()

# ══════════════════════════════════════════════════════════════
# DAILY 수집
# ══════════════════════════════════════════════════════════════

def get_fund_nav():
    """[KOFIA-D] 펀드 유형별 순자산"""
    df = _kofia_get("getFundTotalNetEssetInfo", {"numOfRows": "500"})
    if df.empty:
        return df
    df["nPptTotAmt"] = pd.to_numeric(df["nPptTotAmt"], errors="coerce")
    df["basDt"]      = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    return df[df["ctg"] != "합계"]

def get_market_funds():
    """[KOFIA-D] 증시 대기자금 합산"""
    df_dep  = _kofia_get("GetSecuritiesMarketTotalCapitalInfo")
    df_cma  = _kofia_get("getCMAStatus")
    df_fund = get_fund_nav()
    result  = {}

    if not df_dep.empty:
        for col in ["invrDpsgAmt", "toCstRpchCndBndSlgBal"]:
            df_dep[col] = pd.to_numeric(df_dep[col], errors="coerce")
        df_dep["basDt"] = pd.to_datetime(df_dep["basDt"], format="%Y%m%d", errors="coerce")
        for _, row in df_dep.iterrows():
            dt = row["basDt"]
            result.setdefault(dt, {})
            result[dt]["예탁금"] = round(row["invrDpsgAmt"] / 1e12, 1)
            result[dt]["RP"]    = round(row["toCstRpchCndBndSlgBal"] / 1e12, 1)

    if not df_cma.empty:
        df_cma["actBal"] = pd.to_numeric(df_cma["actBal"], errors="coerce")
        df_cma["basDt"]  = pd.to_datetime(df_cma["basDt"], format="%Y%m%d", errors="coerce")
        if "mngInvTgt" in df_cma.columns:
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
    for col in ["예탁금", "RP", "CMA", "MMF"]:
        if col not in df_out.columns:
            df_out[col] = 0
    df_out["합계"] = df_out[["예탁금","RP","CMA","MMF"]].sum(axis=1).round(1)
    return df_out.reset_index().rename(columns={"index": "basDt"})

def get_credit():
    """[KOFIA-D] 신용융자 잔고"""
    df = _kofia_get("getGrantingOfCreditBalanceInfo")
    if df.empty:
        return df
    df["crdTrFingWhl"] = pd.to_numeric(df["crdTrFingWhl"], errors="coerce")
    df["basDt"]        = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    df["신용융자"]      = (df["crdTrFingWhl"] / 1e12).round(2)
    return df[["basDt","신용융자"]].sort_values("basDt")

def get_market_rates():
    """[ECOS] 금리 시계열 · 817Y002"""
    items = {
        "국고채3Y":  ("817Y002", "010200000"),
        "국고채10Y": ("817Y002", "010210000"),
        "CD금리":    ("817Y002", "010502000"),
    }
    result = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(stat, item)
        if not df.empty and "date" in df.columns:
            result[name] = df[["date","DATA_VALUE"]].rename(
                columns={"DATA_VALUE":"value"}).dropna().sort_values("date")
        time.sleep(0.2)
    return result

def get_exchange_rates():
    """[ECOS] 환율 시계열 · 731Y001"""
    items = {
        "원달러": ("731Y001", "0000001"),
        "원엔":   ("731Y001", "0000002"),
    }
    result = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(stat, item)
        if not df.empty and "date" in df.columns:
            result[name] = df[["date","DATA_VALUE"]].rename(
                columns={"DATA_VALUE":"value"}).dropna().sort_values("date")
        time.sleep(0.2)
    return result

def get_market_indices():
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
            if not data.empty:
                last = float(data["Close"].iloc[-1])
                prev = float(data["Close"].iloc[-2])
                result[name] = {
                    "last": round(last, 2),
                    "chg":  round(last - prev, 2),
                    "pct":  round((last - prev) / prev * 100, 2),
                }
        except Exception as e:
            print(f"  [YF] {ticker} 오류: {e}")
    return result

def get_kospi_history():
    """[YF] KOSPI 30일 시계열"""
    try:
        df = yf.Ticker("^KS11").history(period="1mo", auto_adjust=True)
        if not df.empty:
            df = df.reset_index()[["Date","Close"]].rename(
                columns={"Date":"date","Close":"value"})
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            return df.sort_values("date")
    except Exception as e:
        print(f"  [YF] KOSPI history 오류: {e}")
    return pd.DataFrame()

def get_etf_top10():
    """[KRX-ETF] ETF 거래대금 TOP10"""
    df = _krx_post("etp/etf_bydd_trd", _last_bizday())
    if df.empty:
        return df
    df["ACC_TRDVAL"] = pd.to_numeric(df["ACC_TRDVAL"], errors="coerce")
    df["FLUC_RT"]    = pd.to_numeric(df["FLUC_RT"],    errors="coerce")
    top10 = (df.dropna(subset=["ACC_TRDVAL"])
               .sort_values("ACC_TRDVAL", ascending=False)
               .head(10)[["ISU_NM","ACC_TRDVAL","FLUC_RT","IDX_IND_NM"]]
               .reset_index(drop=True))
    top10["거래대금(억)"] = (top10["ACC_TRDVAL"] / 1e8).round(0).astype(int)
    return top10

def get_bond_market():
    """[KRX-BON] 채권 거래 유형별 집계"""
    df = _krx_post("bon/bnd_bydd_trd", _last_bizday())
    if df.empty:
        return df
    df["ACC_TRDVAL"] = pd.to_numeric(df["ACC_TRDVAL"], errors="coerce")

    def classify(name):
        name = str(name)
        if "국민주택" in name: return "국민주택채권"
        if any(x in name for x in ["은행","금융","카드","캐피탈"]): return "금융채"
        if any(x in name for x in ["공사","공단","도로","수자원","국채"]): return "특수채"
        return "기타"

    df["유형"] = df["ISU_NM"].apply(classify)
    result = (df.groupby("유형")["ACC_TRDVAL"].sum()
                .reset_index().sort_values("ACC_TRDVAL", ascending=False))
    result["거래대금(억)"] = (result["ACC_TRDVAL"] / 1e8).round(1)
    return result

def get_gold():
    """[KRX-GLD] 금 현물 시세"""
    df = _krx_post("gen/gold_bydd_trd", _last_bizday())
    if df.empty:
        return {}
    row = df[df["ISU_CD"] == "04020000"]
    if row.empty:
        row = df.iloc[[0]]
    row = row.iloc[0]
    def to_float(v):
        try:
            return float(str(v).replace(",","").strip())
        except:
            return 0.0
    return {
        "price": to_float(row.get("TDD_CLSPRC", 0)),
        "chg":   to_float(row.get("CMPPREVDD_PRC", 0)),
        "fluc":  to_float(row.get("FLUC_RT", 0)),
        "val":   round(to_float(row.get("ACC_TRDVAL", 0)) / 1e8, 1),
    }

# ══════════════════════════════════════════════════════════════
# MONTHLY 수집
# ══════════════════════════════════════════════════════════════

def get_trust():
    """[KOFIA-M] 신탁 업권별 수탁총액"""
    start_dt = (datetime.today() - timedelta(days=210)).strftime("%Y%m%d")
    end_dt   = datetime.today().strftime("%Y%m%d")
    return _kofia_get("getTrusBusiInfoService", {
        "beginBasDt": start_dt,
        "endBasDt":   end_dt,
        "numOfRows":  "1000",
    })

def get_els():
    """[KOFIA-M] ELS/DLS 발행·상환"""
    start_dt = (datetime.today() - timedelta(days=210)).strftime("%Y%m%d")
    end_dt   = datetime.today().strftime("%Y%m%d")
    df = _kofia_get("getElsBlbIssuPresInfo", {
        "beginBasDt": start_dt,
        "endBasDt":   end_dt,
        "numOfRows":  "200",
    })
    if df.empty:
        return df
    for col in df.select_dtypes(include="object").columns:
        if col != "basDt":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def get_isa_trend():
    """[ISA] 투자중개형 월별 잔고"""
    df = _isa_get("getJoinStatus_V2")
    if df.empty:
        return df
    df = df[df["isaForm"] == "투자중개형 ISA"].copy()
    df["jnpnCnt"] = pd.to_numeric(df["jnpnCnt"], errors="coerce")
    df["invAmt"]  = pd.to_numeric(df["invAmt"],  errors="coerce")
    df["basDt"]   = pd.to_datetime(df["basDt"],  format="%Y%m%d", errors="coerce")
    result = df.groupby("basDt").agg(
        잔고=("invAmt","sum"), 가입자=("jnpnCnt","sum")
    ).reset_index()
    result["잔고(조)"]    = (result["잔고"]   / 1e12).round(2)
    result["가입자(만명)"] = (result["가입자"] / 1e4).round(1)
    result["순증(조)"]    = result["잔고(조)"].diff().round(2)
    return result.sort_values("basDt")

def get_isa_assets():
    """[ISA] 투자중개형 편입자산 시계열"""
    df = _isa_get("getManagementStatus_V2", {
        "isaForm":    "투자중개형 ISA",
        "ctg":        "비중",
        "beginBasDt": "20250101",
        "endBasDt":   datetime.today().strftime("%Y%m%d"),
    })
    if df.empty:
        return df
    df = df[df["bzds"] == "증권"].copy()
    df["amt"]   = pd.to_numeric(df["amt"],  errors="coerce")
    df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d", errors="coerce")
    return (df.pivot_table(index="basDt", columns="incAstCtg", values="amt", aggfunc="mean")
              .round(1).reset_index().sort_values("basDt"))

# ══════════════════════════════════════════════════════════════
# 전체 수집
# ══════════════════════════════════════════════════════════════

def collect_all(kofia_key: str, krx_key: str, ecos_key: str) -> dict:
    global KOFIA_KEY, KRX_KEY, ECOS_KEY
    KOFIA_KEY = kofia_key
    KRX_KEY   = krx_key
    ECOS_KEY  = ecos_key

    print("📡 데이터 수집 시작...")
    data = {}

    print("  [1/12] 펀드 유형별 순자산...")
    data["fund_nav"]      = get_fund_nav()

    print("  [2/12] 증시 대기자금...")
    data["market_funds"]  = get_market_funds()

    print("  [3/12] 신용융자...")
    data["credit"]        = get_credit()

    print("  [4/12] 금리 (ECOS)...")
    data["rates"]         = get_market_rates()

    print("  [5/12] 환율 (ECOS)...")
    data["fx"]            = get_exchange_rates()

    print("  [6/12] 글로벌 지수 (yfinance)...")
    data["indices"]       = get_market_indices()

    print("  [7/12] KOSPI 시계열 (yfinance)...")
    data["kospi_history"] = get_kospi_history()

    print("  [8/12] KRX ETF TOP10...")
    data["etf_top10"]     = get_etf_top10()

    print("  [9/12] KRX 채권...")
    data["bond_market"]   = get_bond_market()

    print("  [10/12] KRX 금...")
    data["gold"]          = get_gold()

    print("  [11/12] ISA 잔고 추이...")
    data["isa_trend"]     = get_isa_trend()

    print("  [12/12] ISA 편입자산...")
    data["isa_assets"]    = get_isa_assets()

    # Monthly (KOFIA 서버 복구 후 활성화)
    print("  [+] 신탁...")
    data["trust"]         = get_trust()
    print("  [+] ELS/DLS...")
    data["els"]           = get_els()

    data["collected_at"] = datetime.now().strftime("%Y.%m.%d %H:%M")
    print(f"✅ 수집 완료: {data['collected_at']}")
    return data
