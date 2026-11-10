#!/usr/bin/env python3
"""V8.6 BTC/ETH/SOL same-clock, source-verified contextual watchlist (no orders).

Use ONLY published immutable source JSONs pulled from authenticated repository
branches. TradingView's dynamically-rendered technicals show dashes via
web access, so do NOT claim independently inspected TradingView 4H values.
No back-filled 1H triggers, no alerts/automations and no broker orders.

BTC and SOL: main publisher's Coinalyze Binance perpetual 1H/4H/Daily.
ETH: independent ETH V7 Coinalyze source and 5 verified cross-TF checks.
SOL's SMA100/200: independent V8.5 read-only snapshot at SAME 4H close.
Everything else without SMA values stays CONTEXT_ONLY; never infer SMA.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import argparse,json,math

ALLOWED={"BTCUSDT_PERP.A":"BTC","ETHUSDT_PERP.A":"ETH","SOLUSDT_PERP.A":"SOL"}
TFS={"1hour":3600,"4hour":14400,"daily":86400}


def normalized(ts):
    if ts.endswith(".000Z"):ts=ts[:-5]+"Z"
    dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_istanbul(iso):
    d=datetime.fromisoformat(iso.replace("Z","+00:00"))
    return d.astimezone(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M TSİ")


def extract_main(data):
    if data.get("ok") is not True or data.get("provider")!="Coinalyze" or data.get("market")!="Perpetual Futures":
        raise ValueError("BTC_SOL_MAIN_SOURCE_NOT_VERIFIED")
    result={}
    for bar in data["results"]:
        sym=bar["symbol"];tf=bar["interval"]
        if sym not in ("BTCUSDT_PERP.A","SOLUSDT_PERP.A") or tf not in TFS:
            raise ValueError("MAIN_UNEXPECTED_SYMBOL_OR_TF")
        if bar["status"]!="READY":
            raise ValueError("MAIN_MISSING_READY_OHLCV")
        target=result.setdefault(sym,{})
        if tf in target:raise ValueError("MAIN_DUPLICATE_TF")
        target[tf]={"closeUTC":normalized(bar["closeTimeUTC"]),
                    "candle":bar["candle"],"indicators":bar["indicators"],
                    "source":"Main / Coinalyze Binance perpetual read-only"}
    for sym in ("BTCUSDT_PERP.A","SOLUSDT_PERP.A"):
        if set(result.get(sym,{}))!=set(TFS):
            raise ValueError("MAIN_BTC_SOL_MISSING_1H_4H_D")
    return result


def extract_eth(doc):
    if doc.get("status")!="VERIFIED_PAPER_OBSERVATION" or doc.get("symbol")!="ETHUSDT_PERP.A":
        raise ValueError("INDEPENDENT_ETH_SOURCE_NOT_READY")
    if doc.get("paperForwardObservation") is not True or doc.get("brokerOrders") is not False:
        raise ValueError("ETH_NON_PAPER")
    if doc.get("crossTimeframeOHLCVVerifiedLast5",{}).get("1H_matches_4H")!=5:
        raise ValueError("ETH_TIMEFRAME_OHLCV_NOT_CONFIRMED")
    if doc.get("crossTimeframeOHLCVVerifiedLast5",{}).get("1H_matches_daily")!=5:
        raise ValueError("ETH_DAILY_OHLCV_NOT_CONFIRMED")
    key="ETHUSDT_PERP.A"
    tf=doc["marketContext"][key]["timeframes"]
    if set(tf)!=set(TFS):raise ValueError("ETH_REQUIRED_TF_NOT_ALL_PRESENT")
    result={}
    for name,z in tf.items():
        result[name]={"closeUTC":normalized(z["closeTimeUTC"]),
                      "candle":z["candle"],"indicators":z["indicators"],
                      "source":doc["dataSource"]}
    return result


def validate_timestamp_and_candles(all_assets):
    target=None
    for sym,tf in all_assets.items():
        if set(tf)!=set(TFS):raise ValueError("MISSING_TIMEFRAME_"+sym)
        one=four=None
        for name,rec in tf.items():
            ts=datetime.fromisoformat(rec["closeUTC"].replace("Z","+00:00"))
            if name=="4hour":
                if target is None:target=rec["closeUTC"]
                if rec["closeUTC"]!=target:raise ValueError("MULTI_ASSET_4H_DIFFERENT_TIMES")
                four=rec
            elif name=="1hour":one=rec
            c=rec["candle"]
            if not all(isinstance(c.get(k), (int,float)) and math.isfinite(c[k])
                       for k in ("open","high","low","close","volume")):
                raise ValueError("INVALID_OHLCV_"+sym+"_"+name)
            if not (c["low"]<=min(c["open"],c["close"])<=max(c["open"],c["close"])<=c["high"]):
                raise ValueError("BAD_OHLCV_BOUNDS")
        if one["closeUTC"]!=four["closeUTC"]:
            raise ValueError("CLOSED_1H_4H_NOT_SAME_UTC_"+sym)
        if abs(one["candle"]["close"]-four["candle"]["close"])>max(1e-5,.000001*four["candle"]["close"]):
            raise ValueError("CLOSED_1H_4H_PRICE_MISMATCH_"+sym)
        day_end=datetime.fromisoformat(tf["daily"]["closeUTC"].replace("Z","+00:00"))
        if day_end>datetime.fromisoformat(target.replace("Z","+00:00")):
            raise ValueError("FUTURE_DAILY_CANDLE")
    return target


def regime(sym,timeframes,sol_shadow=None):
    f=timeframes["4hour"];d=timeframes["daily"];h=timeframes["1hour"]
    fr=f["indicators"]["RSI14"];dr=d["indicators"]["RSI14"]
    if not all(isinstance(a,(int,float)) and math.isfinite(a) for a in (fr,dr)):
        raise ValueError("RSI_NOT_VALID")
    spot=f["candle"]["close"]
    daily_close=d["candle"]["close"]
    fema=f["indicators"].get("EMA20")
    dema=d["indicators"].get("EMA20")
    if not isinstance(fema,(int,float)) or not isinstance(dema,(int,float)):
        raise ValueError("NO_EMA20_FOR_CONTEXT")
    falling=(spot<fema and daily_close<dema and fr<50 and dr<50)
    rising=(spot>fema and daily_close>dema and fr>50 and dr>50)
    if falling and (fr<32 or dr<=30):
        state="FALLING_TREND_WITH_BOUNCE_RISK"
        action="WAIT_NO_CHASE_SHORT"
    elif rising and (fr>68 or dr>=70):
        state="RISING_TREND_WITH_PULLBACK_RISK"
        action="WAIT_NO_CHASE_LONG"
    elif falling:
        state="FALLING_TREND_CONTINUATION_WATCH"
        action="WAIT_FOR_SEPARATE_1H_BOS_RETEST"
    elif rising:
        state="RISING_TREND_CONTINUATION_WATCH"
        action="WAIT_FOR_SEPARATE_1H_BOS_RETEST"
    else:
        state="MIXED_CONTEXT"
        action="ABSTAIN_NO_TRADE"
    record={
        "symbol":sym,"state":state,"decision":action,
        "sourceCloseUTC":f["closeUTC"],
        "4Hclose":spot,"DailyClose":daily_close,
        "4HRSI14":fr,"DailyRSI14":dr,
        "4HEMA20":fema,"DailyEMA20":dema,
        "4HEMA50":f["indicators"].get("EMA50"),
        "DailyEMA50":d["indicators"].get("EMA50"),
        "1Hclose":h["candle"]["close"],
        "independentClosed1HEntrySignalVerified":False,
        "MACDMandatory":False,
        "institutionalOrderbookVerified":False,
        "assetDifferentContractsThanTradingViewSpot":"Binance perpetual versus public TradingView spot page",
        "SMA100_200":None}
    if sym=="SOL":
        if sol_shadow is None:raise ValueError("MISSING_SOL_INDEPENDENT_SMA_SNAPSHOT")
        if sol_shadow.get("status")!="RESEARCH_SNAPSHOT_NO_ORDERS" or sol_shadow.get("symbol")!="SOLUSDT_PERP.A":
            raise ValueError("BAD_SOL_SMA_SOURCE")
        ctx=sol_shadow["readOnlyMarketContext"]
        if normalized(ctx["4HCloseUTC"])!=f["closeUTC"] or abs(ctx["4HClose"]-spot)>1e-5:
            raise ValueError("SOL_SMA_SNAPSHOT_MISALIGNED")
        record["SMA100_200"]={
            "4H100":ctx["4HSMA100"],"4H200":ctx["4HSMA200"],
            "Daily100":ctx["dailySMA100"],"Daily200":ctx["dailySMA200"],
            "4H100Above200":ctx["4HSMA100AboveSMA200"],
            "Daily100Above200":ctx["dailySMA100AboveSMA200"],
            "same4HCloseVerified":True}
        record["manualUserZone_87_50_95"]={"low":87.5,"high":95.0,
                  "priceUSDToLowerEdge":round(87.5-spot,5),
                  "role":"Historical HTF support-to-resistance candidate",
                  "retetstVerified":False,
                  "notAnAlgorithmicAutoTrade":True}
    return record


def render(data):
    a=data["assets"]
    lines=["# V8.6 BTC ETH SOL — Independent 23:00 TSİ perpetual watchlist",
           "",
           "**One-time historical/current snapshot, NOT an order or live 1H signal.**",
           f"Last synchronized 4H close: **{data['asOfTSI']}**.",
           "",
           "| Asset | 4H close | RSI(14) 4H | RSI(14) Daily | Context | Action |",
           "|---|---:|---:|---:|---|---|"]
    for name in ("BTC","ETH","SOL"):
        x=a[name]
        lines.append(f"| {name} | {x['4Hclose']:,.2f} | {x['4HRSI14']:.2f} | "
                     f"{x['DailyRSI14']:.2f} | {x['state']} | {x['decision']} |")
    lines+=["",
            "## Risk comments",
            "- The TradingView publicly renderable technical pages returned empty indicator values; this report does NOT invent TradingView 4H or Daily RSI.",
            "- Coinalyze read-only Binance perpetual OHLCV (BTC/SOL published main, ETH independent V7) is distinct from public Binance spot charts.",
            "- SOL SMA100/200 is verified from the independent same-close read-only V8.5 shadow; BTC/ETH SMA100/200 NOT available here and not inferred.",
            "- No new 1H BOS/retest is evidenced in this three-asset source reconciliation; watch means observe only.",
            "- SOL user-drawn 87.50–95.00 region is context only; no confirmed retest and no automatic SHORT.",
            "- No real trading, no production edits, no signal-engine activation.",
            ""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main-source",default="forward/v86_three_assets/input_main.json")
    p.add_argument("--eth-source",default="forward/v86_three_assets/input_eth.json")
    p.add_argument("--sol-sma",default="forward/v86_three_assets/input_sol_v85_sma.json")
    p.add_argument("--json",default="forward/v86_three_assets/latest.json")
    p.add_argument("--markdown",default="forward/v86_three_assets/latest.md")
    opts=p.parse_args()
    load=lambda f:json.loads(Path(f).read_text())
    main=extract_main(load(opts.main_source))
    main["ETHUSDT_PERP.A"]=extract_eth(load(opts.eth_source))
    target=validate_timestamp_and_candles(main)
    sol=load(opts.sol_sma)
    assets={name:regime(name,main[name+"USDT_PERP.A"],sol if name=="SOL" else None)
            for name in ("BTC","ETH","SOL")}
    out={
        "mode":"V86_THREE_ASSET_SAME_UTC_CLOSE_RESEARCH_WATCHLIST",
        "status":"VERIFIED_CROSS_ASSET_CONTEXT_NO_ORDER",
        "4HCloseUTC":target,
        "asOfTSI":as_istanbul(target),
        "btcSolSource":"Published main market_data.json (Coinalyze 1H/4H/Daily)",
        "ethSource":"Independent ETH V7 hourly snapshot with 5/5 OHLCV cross-timeframe checks",
        "solSMA":"Independent V8.5 same close confirmed Daily+4H SMA100/200",
        "tradingviewNumericalValuesUnavailable":True,
        "dataArePerpetualNotPublicTradingViewSpot":True,
        "assets":assets,
        "realOrders":False,"productionEdited":False,
        "approvedSignalCount":0,
        "automationsAdded":False}
    dest=Path(opts.json);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    Path(opts.markdown).write_text(render(out),encoding="utf-8")
    print("V86_BTC_ETH_SOL_WATCHLIST_DONE",target,
          json.dumps({k:{"close":v["4Hclose"],"state":v["state"]} for k,v in assets.items()}),
          flush=True)


if __name__=="__main__":
    main()
