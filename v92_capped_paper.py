#!/usr/bin/env python3
"""V9.2 separate genuinely prospective 10/20 USDT capped shadow paper account.

One shared 1,000 USDT virtual book for BTC/ETH/SOL. Uses existing V9.2
selected V9.1-replayed pending retests, NOT retrospective V9.2 fills.

For each newly sealed V9.2 hour T:
  (1) At T+~20m seal the intent for a just-closed retest (if any).
  (2) Only after a DIFFERENT prior Git commit exists, at next T+1h
      observation, open the hypothetical paper position using its CLOSE.
  (3) Start assessing exits from T+2h onward, stop first on ambiguity.

Prices are post-close proxies, NOT proven executable fills. Even next close
is observed with processing delay. Never invent retro entries or real orders.
No changes to V7, V9.1, original V9.2 $100-risk paper book, or alerts.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

from backtest_retest_long_v4 import assess_candle
from v92_stable_hardening import (ASSETS, HOUR, POLICY, risk_gate,
                                 seconds, stamp, hour_file, parity_one_hour,
                                 read_reference_hour)

MODE="V92_INDEPENDENT_CAPPED_10_20_SHADOW_PAPER_FORWARD_ONLY"
FIRST="2026-11-13T03:00:00Z"  # after user opt-in; never replay earlier hours
SYMBOL_TO_SOURCE={"BTCUSDT":"BTCUSDT_PERP.A",
                  "ETHUSDT":"ETHUSDT_PERP.A",
                  "SOLUSDT":"SOLUSDT_PERP.A"}
BPS_BASE=9
BPS_STRESS=25
MAX_HOLD_BARS=24

def instant(t):
    return datetime.fromtimestamp(int(t),timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def source_candles(t, core, eth, v7_root):
    """Cross-check 1H/4H/Daily historical closes from already sealed V7."""
    if (seconds(core.get("targetClosed1HUTC"))!=t or
        seconds(eth.get("targetClosed1HUTC"))!=t or
        core.get("sourceV7AndV91RecomputedExactMatch") is not True or
        eth.get("verifiedSourceAndExactV7AndV91Replay") is not True):
        raise ValueError("CAPPED_NO_SAME_HOUR_V92_SOURCE_PARITY")
    btc=read_reference_hour(v7_root,t,"forward/snapshots")
    et=read_reference_hour(v7_root,t,"forward/eth/snapshots")
    if (btc.get("status")!="VERIFIED_PAPER_OBSERVATION" or
        et.get("status")!="VERIFIED_PAPER_OBSERVATION" or
        btc.get("brokerOrders") is not False or
        et.get("brokerOrders") is not False):
        raise ValueError("CAPPED_INVALID_ORIGINAL_V7_DATA")
    bars={}
    for sym in ASSETS:
        ref=SYMBOL_TO_SOURCE[sym]
        source=(et if sym=="ETHUSDT" else btc)
        context=source["marketContext"][ref]["timeframes"]
        for tf in ("1hour","4hour","daily"):
            raw_time=context[tf]["closeTimeUTC"].replace(".000Z","Z")
            expected=t if tf=="1hour" else (
                t//(4*HOUR)*(4*HOUR) if tf=="4hour"
                else t//(24*HOUR)*(24*HOUR))
            if seconds(raw_time)!=expected:
                raise ValueError("CAPPED_CANDLE_TIME_MISMATCH_"+sym+"_"+tf)
        one=context["1hour"]["candle"]
        data={k:one[x] for k,x in
             (("o","open"),("h","high"),("l","low"),
              ("c","close"),("v","volume"))}
        if (not all(finite(v) and v>0 for k,v in data.items() if k!="v")
            or not finite(data["v"]) or data["v"]<0
            or data["l"]>min(data["o"],data["c"])
            or data["h"]<max(data["o"],data["c"])):
            raise ValueError("CAPPED_INVALID_OHLCV_"+sym)
        if sym=="ETHUSDT":
            for tf in ("1hour","4hour","daily"):
                if eth["sourceIntegrity"][tf].get("verified") is not True:
                    raise ValueError("CAPPED_ETH_PARITY_UNVERIFIED")
        else:
            for tf in ("1hour","4hour","daily"):
                if core["originalV7_1H4HDailyCandleParity"][sym][tf].get(
                        "allOHLCVFieldsWithinIntegrityTolerances") is not True:
                    raise ValueError("CAPPED_BTC_SOL_PARITY_UNVERIFIED")
        bars[sym]=data
    return bars

def pending_retest(selected, t):
    state=selected["currentPaperState"]
    p=state.get("pendingNextOpenPaperEntry")
    if p is None:
        return None
    mandatory=("side","stop","retestKnownUTC","watchKnownUTC")
    if any(k not in p for k in mandatory):
        raise ValueError("CAPPED_INCOMPLETE_V92_PENDING_RETEST")
    if (p["side"] not in ("bullish","bearish")
        or type(p["retestKnownUTC"]) is not int
        or type(p["watchKnownUTC"]) is not int
        or p["retestKnownUTC"]!=t
        or p["watchKnownUTC"]>=t
        or not finite(p["stop"]) or p["stop"]<=0):
        raise ValueError("CAPPED_INVALID_OR_RETROACTIVE_V92_RETEST")
    return p

def original_intents(t,core,eth):
    by={}
    for sym in ASSETS:
        events=(eth["selectedV92"] if sym=="ETHUSDT"
                else core["assets"][sym]["selectedV92"])
        p=pending_retest(events,t)
        if p is not None:
            by[sym]={
                "symbol":sym,"side":p["side"],
                "stop":float(p["stop"]),
                "watchKnownUTC":p["watchKnownUTC"],
                "retestKnownUTC":p["retestKnownUTC"],
                "sourceV92SealedCloseUTC":stamp(t),
                "paperOnlyNoRealOrder":True,
                "notAnEntryOrActualFill":True,
            }
    return by

def current_original_open_positions(core,eth):
    """Original replay must STILL consider the precommitted V9.2 trade open."""
    result={}
    for sym in ASSETS:
        events=(eth["selectedV92"] if sym=="ETHUSDT"
                else core["assets"][sym]["selectedV92"])
        result[sym]=events["currentPaperState"].get("openHypotheticalPosition")
    return result

def still_valid_original_position(intent, original):
    if not isinstance(original,dict):
        return False
    for key in ("side","retestKnownUTC","watchKnownUTC"):
        if original.get(key)!=intent.get(key):
            return False
    if not finite(original.get("stop")):
        return False
    return math.isclose(float(original["stop"]),float(intent["stop"]),
                        rel_tol=1e-8,abs_tol=1e-7)

def empty_account():
    return {"paperInitialUSDT":1000.0,
            "realizedPaperPnL9BpsUSDT":0.0,
            "realizedPaperPnL25BpsUSDT":0.0,
            "openPositions":{},"intentNextObservation":{},
            "closedTrades":[],"historyFrozenByMissingHour":False,
            "firstEligibleHourUTC":FIRST,
            "noBrokerOrders":True}

def source_hash(core,eth,bar):
    def sha(d):
        return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":"),
                                      ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"coreV92Sha256":sha(core),
            "ethV92Sha256":sha(eth),
            "verifiedV7ClosedCandlesSha256":sha(bar)}

def step(previous, t, candles, new_intents, *,
         original_open_positions=None,
         prior_committed_before_this_close=False,
         verified=False, stable_ready=False, captured_at=None):
    """Pure deterministic forward paper transition; no lookahead, no APIs."""
    if t<seconds(FIRST) or t%HOUR:
        raise ValueError("CAPPED_NOT_FORWARD_OR_HOUR_ALIGNED")
    if set(candles)!=set(ASSETS) or set(new_intents)-set(ASSETS):
        raise ValueError("CAPPED_MISSING_THREE_ASSET_CANDLES")
    if original_open_positions is None or set(original_open_positions)!=set(ASSETS):
        raise ValueError("CAPPED_ORIGINAL_MODEL_OPEN_STATE_UNAVAILABLE")
    for sym,bar in candles.items():
        if set(("o","h","l","c","v"))-set(bar):
            raise ValueError("CAPPED_CANDLE_FIELDS_MISSING_"+sym)
        if (not all(finite(bar[z]) and bar[z]>0 for z in ("o","h","l","c"))
            or not finite(bar["v"]) or bar["v"]<0
            or bar["l"]>min(bar["o"],bar["c"])
            or bar["h"]<max(bar["o"],bar["c"])):
            raise ValueError("CAPPED_UNVERIFIED_BAR_"+sym)
    if previous is not None:
        if (previous.get("mode")!=MODE or
            previous.get("noBrokerOrders") is not True or
            previous.get("firstEligibleHourUTC")!=FIRST):
            raise ValueError("CAPPED_PRIOR_LEDGER_NOT_VERIFIED")
        last=seconds(previous["lastClosed1HUTC"])
        if last>=t:
            raise ValueError("CAPPED_DUPLICATE_OR_RETROACTIVE_HOUR")
        old=copy.deepcopy(previous)
    else:
        old=empty_account()
        last=None
    out=copy.deepcopy(old)
    events=[]
    contiguous=(last is None or t==last+HOUR)
    eligibility=bool(verified and stable_ready and contiguous and
                     not old["historyFrozenByMissingHour"])
    if not contiguous:
        out["intentNextObservation"]={}
        events.append({"type":"SOURCE_HOUR_GAP","prevUTC":stamp(last),
                       "nowUTC":stamp(t),"historicalHoursBackfilled":False})
        if out["openPositions"]:
            out["historyFrozenByMissingHour"]=True
            events.append({"type":"UNRESOLVED_POSITION_FREEZE",
                           "reason":"UNKNOWN_INTERVENING_STOP_OR_TP",
                           "requiresManualReview":True})
    if not verified:
        out["intentNextObservation"]={}
        events.append({"type":"UNVERIFIED_SOURCE_FAIL_CLOSED"})
    # Exit on this newly closed, verified 1H bar only for positions
    # already present at an EARLIER hour. Never assess the entry bar.
    if eligibility:
        for sym in ASSETS:
            pos=out["openPositions"].get(sym)
            if pos is None:
                continue
            if seconds(pos["paperEntryObservedCloseUTC"])>=t:
                raise ValueError("CAPPED_SAME_BAR_LOOKAHEAD")
            p=copy.deepcopy(pos)
            closed, reason=assess_candle(p,candles[sym],max_hold_bars=MAX_HOLD_BARS)
            if closed:
                qty=p["quantityHypothetical"]
                gross=p["realizedR"]*qty*p["risk"]
                cost9=2*BPS_BASE/10000*qty*p["entry"]
                cost25=2*BPS_STRESS/10000*qty*p["entry"]
                net9=gross-cost9
                net25=gross-cost25
                if not all(math.isfinite(z) for z in (net9,net25,gross)):
                    raise ValueError("CAPPED_NONFINITE_PNL")
                trade={
                    "symbol":sym,"side":p["side"],
                    "intentSealedHourUTC":p["intentSealedHourUTC"],
                    "paperEntryObservedCloseUTC":p["paperEntryObservedCloseUTC"],
                    "exitObservedCloseUTC":stamp(t),
                    "paperEntryPrice":p["entry"],"stop":p["stop"],
                    "quantityHypothetical":qty,
                    "targetCount":p["targetCount"],"exitReason":reason,
                    "realizedGrossR":round(p["realizedR"],9),
                    "netPaperPnL9BpsUSDT":round(net9,8),
                    "netPaperPnL25BpsUSDT":round(net25,8),
                    "noProvenExecutableExchangeFill":True}
                out["closedTrades"].append(trade)
                out["realizedPaperPnL9BpsUSDT"]+=net9
                out["realizedPaperPnL25BpsUSDT"]+=net25
                del out["openPositions"][sym]
                events.append({"type":"CAPPED_PAPER_EXIT",**trade})
            else:
                out["openPositions"][sym]=p
    # New paper position from an intent sealed in an EARLIER Git commit
    # only. Entry uses this fresh hour's CLOSED price. Outcome starts NEXT hour.
    old_intents=copy.deepcopy(old["intentNextObservation"])
    out["intentNextObservation"]={}
    for sym in ASSETS:
        intent=old_intents.get(sym)
        if intent is None:
            continue
        if not eligibility:
            events.append({"type":"CAPPED_INTENT_REJECTED","symbol":sym,
                           "reason":"UNSAFE_SOURCE_OR_NONCONSECUTIVE_HOUR"})
            continue
        if (seconds(intent["sourceV92SealedCloseUTC"])!=t-HOUR
            or not prior_committed_before_this_close):
            events.append({"type":"CAPPED_INTENT_REJECTED","symbol":sym,
                           "reason":"NO_PRIOR_COMMIT_BEFORE_FUTURE_CLOSE"})
            continue
        if not still_valid_original_position(intent,original_open_positions[sym]):
            events.append({"type":"CAPPED_INTENT_REJECTED","symbol":sym,
                           "reason":"ORIGINAL_V92_POSITION_ALREADY_EXITED_OR_CHANGED"})
            continue
        if sym in out["openPositions"]:
            events.append({"type":"CAPPED_INTENT_REJECTED","symbol":sym,
                           "reason":"SYMBOL_ALREADY_OPEN"})
            continue
        reserved=sum(p["reservedStopAndCostUSDT"]
                     for p in out["openPositions"].values())
        notional=sum(p["notionalUSDT"]
                     for p in out["openPositions"].values())
        gate=risk_gate(sym,intent["side"],candles[sym]["c"],intent["stop"],
                       already_reserved=reserved,already_notional=notional,
                       verified=True,precommitted=True,hour_synchronized=True)
        if not gate["allowed"]:
            events.append({"type":"CAPPED_INTENT_REJECTED","symbol":sym,
                           "reason":gate["reason"]})
            continue
        price=candles[sym]["c"];risk=abs(price-intent["stop"])
        direction=1 if intent["side"]=="bullish" else -1
        position={
            "symbol":sym,"side":intent["side"],
            "entry":price,"stop":intent["stop"],"risk":risk,
            "targets":[price+direction*risk*n for n in (1,2,3)],
            "targetCount":0,"realizedR":0.0,
            "heldBars":0,"quantityHypothetical":gate["quantityHypothetical"],
            "notionalUSDT":gate["notionalUSDT"],
            "reservedStopAndCostUSDT":gate["reservedStopAndCostUSDT"],
            "intentSealedHourUTC":intent["sourceV92SealedCloseUTC"],
            "paperEntryObservedCloseUTC":stamp(t),
            "entryPriceIsLateObservedCloseNotProvenExecutable":True}
        if min(position["targets"])<=0:
            events.append({"type":"CAPPED_INTENT_REJECTED","symbol":sym,
                           "reason":"INVALID_TARGETS"})
            continue
        out["openPositions"][sym]=position
        events.append({"type":"CAPPED_PAPER_ENTRY_NOT_REAL_FILL",
                       "symbol":sym,"side":intent["side"],
                       "observedCloseUTC":stamp(t),
                       "paperEntry":price,"stop":intent["stop"],
                       "reservedUSDT":gate["reservedStopAndCostUSDT"],
                       "quantityHypothetical":gate["quantityHypothetical"]})
    # At most one intent per coin; only if fresh enough, with no open paper
    # position, and V9.2 already knows the retest from the CLOSED hour.
    for sym in ASSETS:
        intent=new_intents.get(sym)
        if intent is None:
            continue
        if not eligibility or sym in out["openPositions"]:
            events.append({"type":"NEW_INTENT_BLOCKED","symbol":sym,
                           "reason":"SOURCE_UNREADY_OR_SYMBOL_ALREADY_OPEN"})
            continue
        if (intent.get("sourceV92SealedCloseUTC")!=stamp(t) or
            intent.get("retestKnownUTC")!=t or
            intent.get("watchKnownUTC",t)>=t or
            intent.get("paperOnlyNoRealOrder") is not True):
            raise ValueError("CAPPED_NEW_INTENT_NOT_CAUSAL_OR_UNVERIFIED")
        out["intentNextObservation"][sym]=copy.deepcopy(intent)
        events.append({"type":"CAPPED_PENDING_INTENT_BEFORE_FUTURE_PRICE",
                       "symbol":sym,"side":intent["side"],
                       "retestCloseUTC":stamp(t)})
    exposure=sum(p["reservedStopAndCostUSDT"]
                 for p in out["openPositions"].values())
    notional=sum(p["notionalUSDT"]
                 for p in out["openPositions"].values())
    if (exposure>POLICY["maxCombinedOpenRiskUSDT"]+1e-8 or
        notional>POLICY["paperInitialUSDT"]*POLICY["maxLeverageForNotionalCeiling"]+1e-6):
        raise ValueError("CAPPED_HARD_PORTFOLIO_LIMIT_BROKEN")
    out.update({
        "mode":MODE,"lastClosed1HUTC":stamp(t),
        "capturedAtUTC":instant(captured_at if captured_at is not None else t+1800),
        "firstEligibleHourUTC":FIRST,
        "noBrokerOrders":True,"noUserNotifications":True,
        "noLegacyV7V91OrV92Modification":True,
        "noHistoricalBackfill":True,
        "entryPriceIsLaterObservedCloseNotExecutableFill":True,
        "feeSlippageStressBpsPerSide":25,
        "feeSlippageBaseBpsPerSide":9,
        "riskPolicy":copy.deepcopy(POLICY),
        "openRiskReservationUSDT":round(exposure,6),
        "openNotionalUSDT":round(notional,6),
        "paperRealizedEquity9BpsUSDT":round(1000+out["realizedPaperPnL9BpsUSDT"],6),
        "paperRealizedEquityStress25BpsUSDT":round(1000+out["realizedPaperPnL25BpsUSDT"],6),
        "closedPaperTrades":len(out["closedTrades"]),
        "paperEntriesEverRecorded":len(out["closedTrades"])+len(out["openPositions"]),
        "entryEligibilityForThisHour":eligibility,
        "observedEvents":events,
    })
    return out

def git_first_added(path):
    """Require prior snapshot was already Git committed before next-hour close."""
    try:
        p=Path(path)
        r=subprocess.run(["git","log","--diff-filter=A","--format=%ct",
                         "--",str(p)],
                         check=True,capture_output=True,text=True,timeout=12)
        values=[int(s) for s in r.stdout.split() if s.isdecimal()]
        return min(values) if values else None
    except (OSError,ValueError,subprocess.SubprocessError):
        return None

def load_previous(folder,target):
    root=Path(folder)
    prior=list(sorted(root.glob("*.json"))) if root.is_dir() else []
    latest=None
    for path in prior:
        if path.name=="latest.json":
            continue
        try:
            t=seconds(datetime.strptime(path.name,"%Y-%m-%dT%H-00Z.json")
                .replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        except ValueError as e:
            raise ValueError("CAPPED_UNKNOWN_IMMUTABLE_HISTORY_FILENAME") from e
        if t>=target:
            raise ValueError("CAPPED_EXISTING_OR_FUTURE_SNAPSHOT_MUST_NOT_OVERWRITE")
        if latest is None or t>latest[0]:
            latest=(t,path)
    if latest is None:
        return None,None
    p=latest[1]
    x=json.loads(p.read_text())
    if seconds(x["lastClosed1HUTC"])!=latest[0]:
        raise ValueError("CAPPED_HISTORY_FILENAME_MISMATCH")
    return x,p

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v92-btcsol",required=True)
    p.add_argument("--v92-eth",required=True)
    p.add_argument("--v91-root",required=True)
    p.add_argument("--v7-root",required=True)
    p.add_argument("--audit",required=True)
    p.add_argument("--book-dir",default="forward/v92_capped_paper/hourly")
    p.add_argument("--latest",default="forward/v92_capped_paper/latest.json")
    p.add_argument("--md",default="forward/v92_capped_paper/latest.md")
    p.add_argument("--now",type=int,default=None)
    a=p.parse_args()
    now=int(a.now) if a.now is not None else int(time.time())
    target=now//HOUR*HOUR
    if target<seconds(FIRST):
        print("CAPPED_SKIP_BEFORE_POST_REQUEST_ELIGIBLE_HOUR",stamp(target),flush=True)
        return
    if not 12*60<=now-target<59*60:
        print("CAPPED_SKIP_OUTSIDE_NEW_SEALED_HOUR_CAPTURE_WINDOW",stamp(target),flush=True)
        return
    folder=Path(a.book_dir);outfile=folder/hour_file(target)
    if outfile.exists():
        print("CAPPED_SKIP_ALREADY_COMMITTED_IMMUTABLE_HOUR",stamp(target),flush=True)
        return
    cp=Path(a.v92_btcsol)/hour_file(target)
    ep=Path(a.v92_eth)/hour_file(target)
    if not cp.is_file() or not ep.is_file():
        print("CAPPED_SAFE_SKIP_MISSING_MATCHED_V92_SOURCE_HOUR",stamp(target),flush=True)
        return
    core=json.loads(cp.read_text());eth=json.loads(ep.read_text())
    audit=json.loads(Path(a.audit).read_text())
    if (audit.get("mode")!="V92_STABLE_SHADOW_HARDENING_ONLY" or
        audit.get("latestCommonHourUTC")!=stamp(target) or
        audit.get("parityErrors") or
        audit.get("newEntryAdmissionReadiness") is not True):
        print("CAPPED_SAFE_SKIP_STABLE_AUDIT_NOT_READY_FOR_SAME_HOUR",
              stamp(target),flush=True)
        return
    # Cross-check exactly same immutable signal and OHLCV from BOTH
    # prior versions + original V7 at the new 1H closure.
    parity_one_hour(target,core,eth,a.v91_root,a.v7_root)
    bars=source_candles(target,core,eth,a.v7_root)
    intents=original_intents(target,core,eth)
    previous,path=load_previous(folder,target)
    prior_sealed=False
    if previous is not None and path is not None:
        commit=git_first_added(path)
        prior_sealed=(commit is not None and commit<target
                      and seconds(previous["lastClosed1HUTC"])==target-HOUR)
    current=step(previous,target,bars,intents,
                 original_open_positions=current_original_open_positions(core,eth),
                 prior_committed_before_this_close=prior_sealed,
                 verified=True,stable_ready=True,captured_at=now)
    current["sourceHashes"]=source_hash(core,eth,bars)
    if path is not None:
        current["previousImmutableSnapshotSha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        current["previousImmutableSnapshotSha256"]=None
    folder.mkdir(parents=True,exist_ok=True)
    # Immutable new-hour write; never re-score or rewrite previous snapshots.
    with outfile.open("x",encoding="utf-8") as handle:
        json.dump(current,handle,indent=2,ensure_ascii=False)
        handle.write("\n")
    latest=Path(a.latest);latest.parent.mkdir(parents=True,exist_ok=True)
    latest.write_text(json.dumps(current,indent=2,ensure_ascii=False)+"\n")
    md=Path(a.md);md.parent.mkdir(parents=True,exist_ok=True)
    summary=[
        "# V9.2 — ayrı 10/20 USDT risk limitli paper hesap",
        "",
        f"**Doğrulanmış kapanış (UTC):** {current['lastClosed1HUTC']}",
        f"**Sanal gerçekleşmiş bakiye (9 bps/yön):** {current['paperRealizedEquity9BpsUSDT']:.4f} USDT",
        f"**25 bps stres bakiye:** {current['paperRealizedEquityStress25BpsUSDT']:.4f} USDT",
        f"**Kapanmış paper işlem:** {current['closedPaperTrades']}",
        f"**Açık hedef risk rezervi:** {current['openRiskReservationUSDT']} / 20 USDT",
        f"**Açık hipotetik pozisyon:** {len(current['openPositions'])}",
        f"**Bekleyen mühürlü retest niyeti:** {len(current['intentNextObservation'])}",
        f"**Yeni saatteki olaylar:** {len(current['observedEvents'])}",
        "",
        "Bu ayrı 1.000 USDT paper hesap; eski V9.2 100 USDT-risk hesabı, V7 ve V9.1 değişmez.",
        "Giriş fiyatı, önceki saatte Git'e mühürlenmiş retestten **sonraki** kapanışta görülen fiyatın paper karşılığıdır.",
        "**Borsa üzerinde uygulanabilir gerçek giriş ya da fill doğrulanmamıştır.**",
        "TP1–TP3 ve stop-first, 1H OHLCV ile önceki işlemin kapanışından sonraki saatlerde yürütülür.",
        "İşlem başına 10 USDT (25 bps/yön maliyet tamponuyla), toplam aynı anda 20 USDT hedef risk.",
        "Funding, değişken spread, stop kayması, likidasyon ve gerçek fill doğrulanmamıştır.",
        "",
        "| Coin | Açık pozisyon | Bekleyen sinyal |",
        "|---|---|---|",
    ]
    for sym in ASSETS:
        summary.append(f"| {sym} | {'Evet' if sym in current['openPositions'] else 'Hayır'} | "
                       f"{'Evet' if sym in current['intentNextObservation'] else 'Hayır'} |")
    summary.extend(["","## Bu saatteki audit olayları"])
    for e in current["observedEvents"]:
        summary.append(f"- {e['type']}: {e.get('symbol','')}, {e.get('reason','')}".rstrip(" ,"))
    md.write_text("\n".join(summary)+"\n")
    print("CAPPED_10_20_FORWARD_PAPER_HOUR_SEALED",stamp(target),
          "trades",current["closedPaperTrades"],
          "open",len(current["openPositions"]),
          "risk",current["openRiskReservationUSDT"],
          "intents",len(current["intentNextObservation"]),flush=True)

if __name__=="__main__":
    main()
