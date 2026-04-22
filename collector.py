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

import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time

# ── 인증키 ────────────────────────────────────────────────────
# Streamlit Secrets 또는 환경변수로 관리
# st.secrets["KOFIA_KEY"] / os.environ["KOFIA_KEY"]
KOFIA_KEY = ""   # 공공데이터포털 인증키
KRX_KEY   = ""   # KRX Open API 인증키

BASE_KOFIA = "https://apis.data.go.kr/1160100/GetKofiaStatisticsInfoService"
BASE_ISA   = "https://apis.data.go.kr/1160100/GetISAInfoService_V2"
BASE_ECOS  = "https://ecos.bok.or.kr/api/StatisticSearch"
BASE_KRX   = "https://data-dbg.krx.co.kr/svc/apis"

# ══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ══════════════════════════════════════════════════════════════

def _date_range(days_back=30):
    end   = datetime.today()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

def _month_range(months_back=12):
    end   = datetime.today()
    start = end - timedelta(days=months_back*30)
    return start.strftime("%Y%m"), end.strftime("%Y%m")

def _kofia_get(operation, extra={}):
    """공공데이터포털 KOFIA API 호출 (GET + params)"""
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
        r    = requests.get(f"{BASE_KOFIA}/{operation}", params=params, timeout=15)
        body = r.json()["response"]["body"]
        items = body.get("items", {})
        rows  = items.get("item", items) if isinstance(items, dict) else items
        df    = pd.DataFrame(rows if isinstance(rows, list) else [rows])
        return df
    except Exception as e:
        print(f"  [KOFIA] {operation} 오류: {e}")
        return pd.DataFrame()

def _isa_get(operation, extra={}):
    """ISA API 호출 (GET + params · 방법1만 작동)"""
    start_dt, end_dt = _date_range(400)
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
        r    = requests.get(f"{BASE_ISA}/{operation}", params=params, timeout=15)
        body = r.json()["response"]["body"]
        items = body.get("items", {})
        rows  = items.get("item", items) if isinstance(items, dict) else items
        return pd.DataFrame(rows if isinstance(rows, list) else [rows])
    except Exception as e:
        print(f"  [ISA] {operation} 오류: {e}")
        return pd.DataFrame()

def _ecos_get(stat_code, item_code, freq="D", days_back=30):
    """한국은행 ECOS API 호출"""
    end_dt   = datetime.today().strftime("%Y%m%d")
    start_dt = (datetime.today() - timedelta(days=days_back)).strftime("%Y%m%d")
    url = f"{BASE_ECOS}/{KOFIA_KEY}/json/kr/1/100/{stat_code}/{freq}/{start_dt}/{end_dt}/{item_code}"
    try:
        r    = requests.get(url, timeout=15)
        data = r.json().get("StatisticSearch", {}).get("row", [])
        df   = pd.DataFrame(data)
        if not df.empty:
            df["DATA_VALUE"] = pd.to_numeric(df["DATA_VALUE"], errors="coerce")
        return df
    except Exception as e:
        print(f"  [ECOS] {stat_code}/{item_code} 오류: {e}")
        return pd.DataFrame()

def _krx_post(endpoint, base_dt):
    """KRX Open API 호출 (POST + JSON body + AUTH_KEY header)"""
    url     = f"{BASE_KRX}/{endpoint}"
    headers = {"AUTH_KEY": KRX_KEY, "Content-Type": "application/json"}
    body    = {"basDd": base_dt}
    try:
        r  = requests.post(url, json=body, headers=headers, timeout=15)
        df = pd.DataFrame(r.json().get("OutBlock_1", []))
        return df
    except Exception as e:
        print(f"  [KRX] {endpoint} 오류: {e}")
        return pd.DataFrame()

def _last_bizday():
    """최근 영업일 (주말 제외)"""
    d = datetime.today()
    while d.weekday() >= 5:  # 토=5, 일=6
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")

# ══════════════════════════════════════════════════════════════
# DAILY 수집 함수들
# ══════════════════════════════════════════════════════════════

def get_fund_nav():
    """
    [KOFIA-D] 펀드 유형별 순자산 · getFundTotalNetEssetInfo
    반환: DataFrame [basDt, ctg, tstMthdCtg, nPptTotAmt]
    """
    df = _kofia_get("getFundTotalNetEssetInfo", {"numOfRows": "500"})
    if df.empty:
        return df
    df["nPptTotAmt"] = pd.to_numeric(df["nPptTotAmt"], errors="coerce")
    df["basDt"]      = pd.to_datetime(df["basDt"], format="%Y%m%d")
    df = df[df["ctg"] != "합계"]
    return df

def get_market_funds():
    """
    [KOFIA-D] 증시 대기자금
      - 예탁금 + RP: GetSecuritiesMarketTotalCapitalInfo
      - CMA: getCMAStatus
      - MMF: getFundTotalNetEssetInfo (단기금융)
    반환: DataFrame [basDt, 예탁금, RP, CMA, MMF, 합계] (조원)
    """
    # 예탁금 + RP
    df_dep = _kofia_get("GetSecuritiesMarketTotalCapitalInfo")
    # CMA 합계
    df_cma = _kofia_get("getCMAStatus", {"mngInvTgt": "합계"})
    # MMF (단기금융)
    df_fund = get_fund_nav()

    result = {}

    if not df_dep.empty:
        df_dep["invrDpsgAmt"]          = pd.to_numeric(df_dep["invrDpsgAmt"],          errors="coerce")
        df_dep["toCstRpchCndBndSlgBal"] = pd.to_numeric(df_dep["toCstRpchCndBndSlgBal"], errors="coerce")
        df_dep["basDt"]                = pd.to_datetime(df_dep["basDt"], format="%Y%m%d")
        for _, row in df_dep.iterrows():
            dt = row["basDt"]
            result.setdefault(dt, {})
            result[dt]["예탁금"] = row["invrDpsgAmt"] / 1e12
            result[dt]["RP"]    = row["toCstRpchCndBndSlgBal"] / 1e12

    if not df_cma.empty:
        df_cma["actBal"] = pd.to_numeric(df_cma["actBal"], errors="coerce")
        df_cma["basDt"]  = pd.to_datetime(df_cma["basDt"], format="%Y%m%d")
        cma_daily = df_cma.groupby("basDt")["actBal"].sum()
        for dt, val in cma_daily.items():
            result.setdefault(dt, {})
            result[dt]["CMA"] = val / 1e12

    if not df_fund.empty:
        mmf = df_fund[df_fund["ctg"]=="단기금융"].groupby("basDt")["nPptTotAmt"].sum()
        for dt, val in mmf.items():
            result.setdefault(dt, {})
            result[dt]["MMF"] = val / 1e12

    if not result:
        return pd.DataFrame()

    df_out = pd.DataFrame(result).T.sort_index()
    df_out["합계"] = df_out[["예탁금","RP","CMA","MMF"]].sum(axis=1).round(1)
    return df_out.reset_index().rename(columns={"index":"basDt"})

def get_credit():
    """
    [KOFIA-D] 신용융자 잔고 · getGrantingOfCreditBalanceInfo
    반환: DataFrame [basDt, 신용융자(조)]
    """
    df = _kofia_get("getGrantingOfCreditBalanceInfo")
    if df.empty:
        return df
    df["crdTrFingWhl"] = pd.to_numeric(df["crdTrFingWhl"], errors="coerce")
    df["basDt"]        = pd.to_datetime(df["basDt"], format="%Y%m%d")
    df["신용융자"]      = df["crdTrFingWhl"] / 1e12
    return df[["basDt","신용융자"]].sort_values("basDt")

def get_market_rates():
    """
    [ECOS] 금리 시계열
    반환: dict {
      '국고채3Y': DataFrame,
      '국고채10Y': DataFrame,
      'CD금리': DataFrame,
    }
    """
    items = {
        "국고채3Y":  ("817Y002", "010200000"),
        "국고채10Y": ("817Y002", "010210000"),
        "CD금리":    ("817Y002", "010502000"),
    }
    result = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(stat, item, freq="D", days_back=30)
        if not df.empty:
            result[name] = df[["TIME","DATA_VALUE"]].rename(
                columns={"TIME":"date","DATA_VALUE":"value"})
        time.sleep(0.3)
    return result

def get_exchange_rates():
    """
    [ECOS] 환율 시계열
    반환: dict { '원달러': DataFrame, '원엔': DataFrame }
    """
    items = {
        "원달러": ("731Y001", "0000001"),
        "원엔":   ("731Y001", "0000002"),
    }
    result = {}
    for name, (stat, item) in items.items():
        df = _ecos_get(stat, item, freq="D", days_back=30)
        if not df.empty:
            result[name] = df[["TIME","DATA_VALUE"]].rename(
                columns={"TIME":"date","DATA_VALUE":"value"})
        time.sleep(0.3)
    return result

def get_market_indices():
    """
    [YF] 글로벌 지수
    반환: dict { 'KOSPI': float, 'VIX': float, 'SP500': float, 'US10Y': float }
    """
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
                last  = float(data["Close"].iloc[-1])
                prev  = float(data["Close"].iloc[-2])
                result[name] = {
                    "last": last,
                    "chg":  last - prev,
                    "pct":  (last - prev) / prev * 100,
                }
        except Exception as e:
            print(f"  [YF] {ticker} 오류: {e}")
    return result

def get_etf_top10():
    """
    [KRX-ETF] ETF 거래대금 TOP10 · etp/etf_bydd_trd
    반환: DataFrame [ISU_NM, ACC_TRDVAL, FLUC_RT, IDX_IND_NM]
    """
    base_dt = _last_bizday()
    df = _krx_post("etp/etf_bydd_trd", base_dt)
    if df.empty:
        return df
    df["ACC_TRDVAL"] = pd.to_numeric(df["ACC_TRDVAL"], errors="coerce")
    df["FLUC_RT"]    = pd.to_numeric(df["FLUC_RT"],    errors="coerce")
    df = df.dropna(subset=["ACC_TRDVAL"])
    top10 = (df.sort_values("ACC_TRDVAL", ascending=False)
               .head(10)[["ISU_NM","ACC_TRDVAL","FLUC_RT","IDX_IND_NM"]]
               .reset_index(drop=True))
    top10["거래대금(억)"] = (top10["ACC_TRDVAL"] / 1e8).round(0).astype(int)
    return top10

def get_bond_market():
    """
    [KRX-BON] 채권 거래 · bon/bnd_bydd_trd
    반환: DataFrame (유형별 거래대금 집계)
    """
    base_dt = _last_bizday()
    df = _krx_post("bon/bnd_bydd_trd", base_dt)
    if df.empty:
        return df
    df["ACC_TRDVAL"] = pd.to_numeric(df["ACC_TRDVAL"], errors="coerce")

    def classify(name):
        if "국민주택" in name: return "국민주택채권"
        if "회사채" in name or any(x in name for x in ["(주)","㈜","Inc"]): return "회사채"
        if any(x in name for x in ["은행","금융","카드","캐피탈"]): return "금융채"
        if any(x in name for x in ["공사","공단","정부","국채"]): return "특수채"
        return "기타"

    df["유형"] = df["ISU_NM"].apply(classify)
    return df.groupby("유형")["ACC_TRDVAL"].sum().reset_index().sort_values("ACC_TRDVAL", ascending=False)

def get_gold():
    """
    [KRX-GLD] 금 시세 · gen/gold_bydd_trd
    반환: dict { price, chg, fluc, val }
    """
    base_dt = _last_bizday()
    df = _krx_post("gen/gold_bydd_trd", base_dt)
    if df.empty:
        return {}
    row = df[df["ISU_CD"]=="04020000"]  # 금 99.99_1kg
    if row.empty:
        row = df.iloc[[0]]
    row = row.iloc[0]
    return {
        "price": float(str(row["TDD_CLSPRC"]).replace(",","")),
        "chg":   float(str(row["CMPPREVDD_PRC"]).replace(",","")),
        "fluc":  float(str(row["FLUC_RT"]).replace(",","")),
        "val":   float(str(row["ACC_TRDVAL"]).replace(",","")) / 1e8,  # 억원
    }

# ══════════════════════════════════════════════════════════════
# MONTHLY 수집 함수들
# ══════════════════════════════════════════════════════════════

def get_trust():
    """
    [KOFIA-M] 신탁 업권별 수탁총액 · getTrusBusiInfoService
    반환: DataFrame [basDt, 증권, 은행, 보험, 부동산] (억원)
    """
    start_ym = (datetime.today() - timedelta(days=180)).strftime("%Y%m%d")
    end_ym   = datetime.today().strftime("%Y%m%d")
    df = _kofia_get("getTrusBusiInfoService", {
        "beginBasDt": start_ym,
        "endBasDt":   end_ym,
        "numOfRows":  "500",
    })
    if df.empty:
        return df
    # 업권별 피벗
    df["sucsc"] = pd.to_numeric(df.get("sucsc", 0), errors="coerce")
    return df

def get_els():
    """
    [KOFIA-M] ELS/DLS 발행·상환 · getElsBlbIssuPresInfo
    반환: DataFrame [basDt, ELS발행, ELS상환, DLS발행, DLS상환] (조원)
    """
    df = _kofia_get("getElsBlbIssuPresInfo", {"numOfRows": "200"})
    if df.empty:
        return df
    for col in df.select_dtypes(include="object").columns:
        if col != "basDt":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def get_isa_trend():
    """
    [ISA] 투자중개형 월별 잔고 · getJoinStatus_V2
    반환: DataFrame [basDt, 잔고(조), 가입자(만명)]
    """
    df = _isa_get("getJoinStatus_V2", {
        "beginBasDt": "20240101",
        "endBasDt":   datetime.today().strftime("%Y%m%d"),
    })
    if df.empty:
        return df
    df = df[df["isaForm"]=="투자중개형 ISA"].copy()
    df["jnpnCnt"] = pd.to_numeric(df["jnpnCnt"], errors="coerce")
    df["invAmt"]  = pd.to_numeric(df["invAmt"],  errors="coerce")
    df["basDt"]   = pd.to_datetime(df["basDt"],  format="%Y%m%d")

    result = df.groupby("basDt").agg(
        잔고=("invAmt",  "sum"),
        가입자=("jnpnCnt", "sum"),
    ).reset_index()
    result["잔고(조)"]    = (result["잔고"]  / 1e12).round(2)
    result["가입자(만명)"] = (result["가입자"] / 1e4).round(1)
    result["순증(조)"]    = result["잔고(조)"].diff().round(2)
    return result.sort_values("basDt")

def get_isa_assets():
    """
    [ISA] 투자중개형 편입자산 시계열 · getManagementStatus_V2
    반환: DataFrame [basDt, ETF, 주식, 예적금, RP, 파생, ...]
    """
    df = _isa_get("getManagementStatus_V2", {
        "beginBasDt": "20250101",
        "endBasDt":   datetime.today().strftime("%Y%m%d"),
        "isaForm":    "투자중개형 ISA",
        "ctg":        "비중",
    })
    if df.empty:
        return df
    df = df[df["bzds"]=="증권"].copy()
    df["amt"]   = pd.to_numeric(df["amt"], errors="coerce")
    df["basDt"] = pd.to_datetime(df["basDt"], format="%Y%m%d")

    pivot = (df.pivot_table(index="basDt", columns="incAstCtg", values="amt", aggfunc="mean")
               .round(1)
               .reset_index()
               .sort_values("basDt"))
    return pivot

# ══════════════════════════════════════════════════════════════
# 전체 수집 (메인 함수)
# ══════════════════════════════════════════════════════════════

def collect_all(kofia_key: str, krx_key: str) -> dict:
    """
    모든 데이터 수집 후 딕셔너리 반환
    Streamlit app.py에서 호출
    """
    global KOFIA_KEY, KRX_KEY
    KOFIA_KEY = kofia_key
    KRX_KEY   = krx_key

    print("📡 데이터 수집 시작...")
    data = {}

    print("  [1/10] 펀드 유형별 순자산...")
    data["fund_nav"]    = get_fund_nav()

    print("  [2/10] 증시 대기자금...")
    data["market_funds"] = get_market_funds()

    print("  [3/10] 신용융자...")
    data["credit"]      = get_credit()

    print("  [4/10] 금리 (ECOS)...")
    data["rates"]       = get_market_rates()

    print("  [5/10] 환율 (ECOS)...")
    data["fx"]          = get_exchange_rates()

    print("  [6/10] 글로벌 지수 (yfinance)...")
    data["indices"]     = get_market_indices()

    print("  [7/10] KRX ETF TOP10...")
    data["etf_top10"]   = get_etf_top10()

    print("  [8/10] 금 시세 (KRX)...")
    data["gold"]        = get_gold()

    print("  [9/10] ISA 잔고 추이...")
    data["isa_trend"]   = get_isa_trend()

    print("  [10/10] ISA 편입자산 시계열...")
    data["isa_assets"]  = get_isa_assets()

    data["collected_at"] = datetime.now().strftime("%Y.%m.%d %H:%M")
    print(f"✅ 수집 완료: {data['collected_at']}")
    return data
