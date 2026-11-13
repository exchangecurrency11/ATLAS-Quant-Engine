#!/usr/bin/env python3
"""Causal 4H chart geometry recognition, TRAIN ranking, later-period validation,
and independent frozen V9.2 BOS+retest overlay. Research only; no orders/alerts.

All chart patterns are deterministic geometric APPROXIMATIONS, not exact
discretionary classical chart readings:
* DOUBLE_TOP / DOUBLE_BOTTOM: two confirmed swing highs/lows, similar level,
  meaningful middle neckline, trend context, neckline closing breakout.
* ASC_TRIANGLE / DESC_TRIANGLE / SYMM_TRIANGLE: confirmed paired swing-high
  and swing-low trendlines with contraction, closing line breakout.
* BULL_FLAG / BEAR_FLAG: >=3-ATR six-bar impulse, six-bar bounded opposite
  pullback (10%-65% retrace), closing pullback breakout + relative volume.
* HEAD_SHOULDERS / INVERSE_HS: triple confirmed high/low swing, dominant
  head, near-equal shoulders, balanced neckline, closing breakdown/breakout.

Pivot is visible only after TWO subsequent 4H bars close. A pattern is
recognized only on a CLOSED 4H breakout, never earlier. Every parameter
is frozen before measuring results. Selection ONLY uses earlier 2022-2024
training outcomes; subsequent 2024-2026 is not used in selection.
A 24-hour 1R target-before-stop rate is NOT the system's win probability.
The separate overlay uses exact V7 + V9.1 max4H retest baseline and existing
V9.2 SOL-only Star/Harami/sweep veto. All 6 baselines must match prior
SHA256-verified research or abort. No backfilled prospective trades.
"""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from itertools import combinations
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from download_binance_um_history import aggregate
from market_structure import average_true_range
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import FOUR, HOUR, metrics, stamp
from v92_four_candle_models_20261113 import (
    SYMBOLS, PERIODS, download_all, parity_check, epoch)
from v92_selected_reversal_patterns import make_selective_gate

FAMILIES = (
    "DOUBLE_TOP","DOUBLE_BOTTOM","ASC_TRIANGLE","DESC_TRIANGLE",
    "SYMM_TRIANGLE","BULL_FLAG","BEAR_FLAG",
    "HEAD_SHOULDERS","INVERSE_HS",
)
COOLDOWN_BARS = 6
PATTERN_MAX_LOOKBACK_BARS = 50
OVERLAY_MAX_AGE_4H = 12
MIN_TRAIN_FOR_EXPLORATORY = 8
MIN_TRAIN_FOR_STRONG = 30
MAX_SELECTED_PER_SYMBOL = 2
HORIZON_4H_BARS = 6  # 24h
STANDALONE_STOP_ATR = 1.5
BASE_COST_BPS = 9
STRESS_COST_BPS = 25
MODEL_NAMES = ("A_V92_BASELINE","B_SELECTED_SAME_SIDE_ONLY",
               "C_SELECTED_OPPOSITE_VETO")
_SYMBOL_LABELS = {"BTCUSDT":"BTC","ETHUSDT":"ETH","SOLUSDT":"SOL"}


def _swing_marks(bars):
    n=len(bars);hi=[False]*n;lo=[False]*n
    for j in range(2,n-2):
        hi[j]=(all(bars[j]["h"]>bars[k]["h"]
                   for k in (j-2,j-1,j+1,j+2)))
        lo[j]=(all(bars[j]["l"]<bars[k]["l"]
                   for k in (j-2,j-1,j+1,j+2)))
    return hi,lo


def _base_event(bars,i,family,side,atr,level):
    return {
        "family":family,"side":side,
        "knownUTC":int(bars[i]["t"])+FOUR,
        "confirmed4HCloseUTC":stamp(int(bars[i]["t"])+FOUR),
        "index":i,"breakoutClose":round(float(bars[i]["c"]),8),
        "level":round(float(level),8),
        "ATR14_4H":round(float(atr),8),
        "onlyClosed4H":True,
        "pivotHas2RightBarConfirmation":True,
    }


def detect_at(bars,i,marks):
    """NO bar after i may influence this decision."""
    if i<65 or i>=len(bars):
        return []
    bar=bars[i];prev=bars[i-1]; atr=average_true_range(bars,i)
    if atr is None or atr<=0 or bar["c"]<=0:
        return []
    hi_mark,lo_mark=marks
    oldest=max(4,i-PATTERN_MAX_LOOKBACK_BARS)
    # Exclude k=i-2, i-1: right-pivot confirmation can ONLY use bars
    # already CLOSED strictly before the breakout bar i.
    highs=[k for k in range(oldest,i-2) if hi_mark[k]]
    lows=[k for k in range(oldest,i-2) if lo_mark[k]]
    found=[]

    # DOUBLE TOP/BOTTOM (last at most 6 prior CONFIRMED extrema).
    for side,piv,fam in (("bullish",lows,"DOUBLE_BOTTOM"),
                         ("bearish",highs,"DOUBLE_TOP")):
        matched=None
        for j,k in reversed(list(combinations(piv[-6:],2))):
            if not(3<=k-j<=22 and 3<=i-k<=20 and j>=5):
                continue
            pa=bars[j]["l" if side=="bullish" else "h"]
            pb=bars[k]["l" if side=="bullish" else "h"]
            if abs(pa-pb)>0.85*atr:
                continue
            if side=="bullish":
                neck=max(b["h"] for b in bars[j+1:k])
                depth=neck-min(pa,pb)
                trend=bars[j-5]["c"] > bars[j-1]["c"]+0.2*atr
                broke=(bar["c"]>neck+0.10*atr
                       and prev["c"]<=neck+0.10*atr)
            else:
                neck=min(b["l"] for b in bars[j+1:k])
                depth=max(pa,pb)-neck
                trend=bars[j-5]["c"] < bars[j-1]["c"]-0.2*atr
                broke=(bar["c"]<neck-0.10*atr
                       and prev["c"]>=neck-0.10*atr)
            if depth>=0.9*atr and trend and broke:
                matched=_base_event(bars,i,fam,side,atr,neck)
                break
        if matched:
            found.append(matched)

    # TRIANGLE, using two latest fully confirmed highs and lows
    # of the prior 30 4H bars. No lines fitted to future bars.
    hh=[k for k in highs if k>=i-32]
    ll=[k for k in lows if k>=i-32]
    if len(hh)>=2 and len(ll)>=2:
        a,b=hh[-2:];c,d=ll[-2:]
        if b-a>=3 and d-c>=3 and i-min(a,c)>=10:
            hs=(bars[b]["h"]-bars[a]["h"])/(b-a)
            ls=(bars[d]["l"]-bars[c]["l"])/(d-c)
            upper=lambda x:bars[b]["h"]+hs*(x-b)
            lower=lambda x:bars[d]["l"]+ls*(x-d)
            older=max(a,c)
            width0=upper(older)-lower(older)
            width1=upper(i-1)-lower(i-1)
            shrinking=(width0>=1.25*atr and
                       0.35*atr<=width1<width0-0.25*atr
                       and width1>0 and upper(i)>lower(i))
            asc=(abs(bars[b]["h"]-bars[a]["h"])<=0.65*atr
                 and bars[d]["l"]-bars[c]["l"]>=0.55*atr)
            desc=(bars[a]["h"]-bars[b]["h"]>=0.55*atr
                  and abs(bars[d]["l"]-bars[c]["l"])<=0.65*atr)
            sym=(bars[a]["h"]-bars[b]["h"]>=0.45*atr
                 and bars[d]["l"]-bars[c]["l"]>=0.45*atr)
            breakout_up=(prev["c"]<=upper(i-1)+0.1*atr
                         and bar["c"]>upper(i)+0.1*atr)
            breakout_dn=(prev["c"]>=lower(i-1)-0.1*atr
                         and bar["c"]<lower(i)-0.1*atr)
            if shrinking:
                if asc and breakout_up:
                    found.append(_base_event(
                        bars,i,"ASC_TRIANGLE","bullish",atr,upper(i)))
                if desc and breakout_dn:
                    found.append(_base_event(
                        bars,i,"DESC_TRIANGLE","bearish",atr,lower(i)))
                if sym and (breakout_up or breakout_dn):
                    found.append(_base_event(
                        bars,i,"SYMM_TRIANGLE",
                        "bullish" if breakout_up else "bearish",
                        atr,upper(i) if breakout_up else lower(i)))

    # 4H bullish / bearish flag. Six-bar impulse precedes six-bar
    # countertrend channel and current completed breakout.
    impulse=bars[i-7]["c"]-bars[i-13]["c"]
    pb=bars[i-6:i]
    mean_volume=sum(b["v"] for b in bars[i-20:i])/20
    width=max(z["h"] for z in pb)-min(z["l"] for z in pb)
    vol_ok=(bar["v"]>=1.10*mean_volume)
    if width<=0.80*abs(impulse) and vol_ok:
        if impulse>=3*atr:
            retrace=(bars[i-7]["c"]-pb[-1]["c"])/impulse
            upper=max(z["h"] for z in pb)
            if (0.1<=retrace<=0.65 and pb[0]["c"]>pb[-1]["c"]
                and prev["c"]<=upper+0.1*atr
                and bar["c"]>upper+0.1*atr):
                found.append(_base_event(
                    bars,i,"BULL_FLAG","bullish",atr,upper))
        if impulse<=-3*atr:
            retrace=(pb[-1]["c"]-bars[i-7]["c"])/(-impulse)
            lower=min(z["l"] for z in pb)
            if (0.1<=retrace<=0.65 and pb[0]["c"]<pb[-1]["c"]
                and prev["c"]>=lower-0.1*atr
                and bar["c"]<lower-0.1*atr):
                found.append(_base_event(
                    bars,i,"BEAR_FLAG","bearish",atr,lower))

    # HEAD-SHOULDERS / INVERSE, using three PRIOR confirmed pivots.
    for side,piv,fam in (("bearish",highs,"HEAD_SHOULDERS"),
                         ("bullish",lows,"INVERSE_HS")):
        matched=None
        for j,k,l in reversed(list(combinations(piv[-7:],3))):
            if not(3<=k-j<=16 and 3<=l-k<=16
                   and 3<=i-l<=24 and j>=5):
                continue
            v1=bars[j]["h" if side=="bearish" else "l"]
            v2=bars[k]["h" if side=="bearish" else "l"]
            v3=bars[l]["h" if side=="bearish" else "l"]
            if abs(v1-v3)>0.9*atr:
                continue
            if side=="bearish":
                head=v2-max(v1,v3)
                neck1=min(x["l"] for x in bars[j+1:k])
                neck2=min(x["l"] for x in bars[k+1:l])
                neck=(neck1+neck2)/2
                trend=bars[j-5]["c"]<bars[j-1]["c"]-0.20*atr
                broke=prev["c"]>=neck-0.10*atr and bar["c"]<neck-0.10*atr
                depth=v2-neck
            else:
                head=min(v1,v3)-v2
                neck1=max(x["h"] for x in bars[j+1:k])
                neck2=max(x["h"] for x in bars[k+1:l])
                neck=(neck1+neck2)/2
                trend=bars[j-5]["c"]>bars[j-1]["c"]+0.20*atr
                broke=prev["c"]<=neck+0.10*atr and bar["c"]>neck+0.10*atr
                depth=neck-v2
            if (head>=0.7*atr and abs(neck1-neck2)<=0.9*atr
                and depth>=1.5*atr and trend and broke):
                matched=_base_event(bars,i,fam,side,atr,neck)
                break
        if matched:
            found.append(matched)
    return found


def detect_all(bars):
    marks=_swing_marks(bars)
    events=[]
    last_by_family={}
    for i in range(65,len(bars)):
        for e in detect_at(bars,i,marks):
            if e["family"] not in FAMILIES:
                raise ValueError("UNREGISTERED_CHART_FAMILY")
            last=last_by_family.get(e["family"],-99999)
            if i-last<COOLDOWN_BARS:
                continue
            if e["knownUTC"]!=bars[i]["t"]+FOUR:
                raise ValueError("FUTURE_4H_BREAKOUT")
            events.append(e)
            last_by_family[e["family"]]=i
    return events


def urchin_eval(event,bars,end):
    """Fixed standalone chart signal: NEXT 4H open, ATR1.5 stop and 1R
    target, 6 already-closed 4H outcomes, stop first, fees stressed.
    Does not overlap with V7 fill or $1000 capped forward account."""
    i=event["index"]
    if i+HORIZON_4H_BARS>=len(bars) or (
        bars[i+HORIZON_4H_BARS]["t"]+FOUR>end):
        return None
    entry=bars[i+1]["o"]
    atr=event["ATR14_4H"]
    risk=STANDALONE_STOP_ATR*atr
    if risk<=0 or entry<=0:
        return None
    side=1 if event["side"]=="bullish" else -1
    stop=entry-side*risk
    target=entry+side*risk
    if stop<=0:
        return None
    exit_reason="TIME_EXIT"
    gross=0.
    for bar in bars[i+1:i+1+HORIZON_4H_BARS]:
        hit_stop=bar["l"]<=stop if side==1 else bar["h"]>=stop
        hit_target=bar["h"]>=target if side==1 else bar["l"]<=target
        if hit_stop:
            gross=-1.
            exit_reason="STOP_FIRST"
            break
        if hit_target:
            gross=1.
            exit_reason="TARGET_FIRST"
            break
    else:
        gross=side*(bars[i+HORIZON_4H_BARS]["c"]-entry)/risk
    return {
        "family":event["family"],"side":event["side"],
        "confirmedUTC":event["confirmed4HCloseUTC"],
        "targetHitBeforeStop":exit_reason=="TARGET_FIRST",
        "exitReason":exit_reason,
        "netR9Bps":gross-2*BASE_COST_BPS/10000*entry/risk,
        "netR25Bps":gross-2*STRESS_COST_BPS/10000*entry/risk,
        "riskPct":100*risk/entry,
    }


def wilson_lower(success,n,z=1.96):
    if n<=0:
        return 0.
    p=success/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n)) / (1+z*z/n)


def score_events(events,rows,start,end):
    groups=defaultdict(list)
    examples=defaultdict(list)
    for e in events:
        if not start<=e["knownUTC"]<end:
            continue
        out=urchin_eval(e,rows,end)
        if out is not None:
            groups[e["family"]].append(out)
            if len(examples[e["family"]])<7:
                examples[e["family"]].append({
                    "confirmedUTC":out["confirmedUTC"],
                    "side":out["side"],
                    "exitReason":out["exitReason"],
                    "netR9Bps":round(out["netR9Bps"],4),
                })
    scored={}
    for fam in FAMILIES:
        trades=groups[fam]
        n=len(trades)
        won=sum(x["targetHitBeforeStop"] for x in trades)
        normal=sum(x["netR9Bps"] for x in trades)
        stress=sum(x["netR25Bps"] for x in trades)
        scored[fam]={
            "signalsWith24hOutcome":n,
            "targetFirst":won,
            "hitRatePct":round(100*won/n,2) if n else None,
            "wilsonLower95Pct":round(100*wilson_lower(won,n),2) if n else None,
            "netR9Bps":round(normal,6),
            "netR25Bps":round(stress,6),
            "meanR9Bps":round(normal/n,5) if n else None,
            "stopFirst":sum(t["exitReason"]=="STOP_FIRST" for t in trades),
            "timeExit":sum(t["exitReason"]=="TIME_EXIT" for t in trades),
            "examples":examples[fam],
        }
    # rank by hit percentage, Wilson lower bound and 25bps mean result
    ordered=sorted(FAMILIES,
                   key=lambda f:(-(scored[f]["hitRatePct"] or -1),
                                 -(scored[f]["wilsonLower95Pct"] or -1),
                                 -scored[f]["signalsWith24hOutcome"],f))
    return scored,ordered


def choose_training_families(score):
    """Selection NEVER examines the later-period outcomes.
    Two ranks: eligibility for EXPLORATORY overlay >=8 training events,
    >0 stressed Net R, >=45% standalone 1R target-first rate.
    Strong threshold >=30 and profitable under stress; still not
    statistically validated or production-eligible."""
    eligible=[f for f in FAMILIES
              if (score[f]["signalsWith24hOutcome"]>=MIN_TRAIN_FOR_EXPLORATORY
                  and score[f]["netR25Bps"]>0
                  and score[f]["hitRatePct"] is not None
                  and score[f]["hitRatePct"]>=45)]
    order=sorted(eligible,
                 key=lambda f:(-score[f]["wilsonLower95Pct"],
                               -score[f]["netR25Bps"],f))
    selected=order[:MAX_SELECTED_PER_SYMBOL]
    return {
        "selectedExploratory":selected,
        "qualifyingUnderConservativeSampleGate":[
            f for f in selected
            if score[f]["signalsWith24hOutcome"]>=MIN_TRAIN_FOR_STRONG
        ],
        "selectionMadeOnlyUsing2022_2024":True,
        "selectionThreshold":{"minEvents":MIN_TRAIN_FOR_EXPLORATORY,
                              "positive25bpsTotalNetR":True,
                              "minHitRatePct":45,
                              "strongMinEvents":MIN_TRAIN_FOR_STRONG},
    }


class ClosedEventLookup:
    def __init__(self,events):
        self.events=sorted(events,key=lambda x:x["knownUTC"])
        self.times=[x["knownUTC"] for x in self.events]

    def at(self,as_of,side,chosen):
        if as_of%HOUR:
            raise ValueError("CHART_RETEST_NOT_CLOSED_HOUR")
        # read ONLY confirmed 4H events at/before current retest close
        end=bisect_right(self.times,as_of)
        recent=[]
        for j in range(end-1,-1,-1):
            e=self.events[j]
            if as_of-e["knownUTC"]>OVERLAY_MAX_AGE_4H*FOUR:
                break
            if e["family"] in chosen:
                if e["knownUTC"]>as_of:
                    raise ValueError("CHART_FUTURE_4H_USED")
                recent.append(e)
        same=[e for e in recent if e["side"]==side]
        opposite=[e for e in recent if e["side"]!=side]
        return same,opposite


def overlay_gate(symbol,mode,four,lookup,selected,audit):
    if mode not in MODEL_NAMES:
        raise ValueError("CHART_OVERLAY_BAD_MODE")
    from collections import Counter as _Counter
    sol_original=(make_selective_gate(
        symbol,four,"SELECTED_SOL_STRICT_SWEEP",
        _Counter(examples=[])) if symbol=="SOLUSDT" else None)

    def gate(one,active,retest):
        t=int(retest["t"])+HOUR
        if active["knownUTC"]>=t or one[-1]["t"]+HOUR!=t:
            raise ValueError("CHART_OVERLAY_CAUSALITY_BREACH")
        audit["retestDecisions"]+=1
        if sol_original is not None:
            base=sol_original(one,active,retest)
            if not base["passed"]:
                audit["originalV92SolVeto"]+=1
                return base
        same,opp=lookup.at(t,active["side"],selected)
        if mode=="B_SELECTED_SAME_SIDE_ONLY":
            if not same:
                audit["selectedSameAbsent"]+=1
                return {"passed":False,"reasons":["CHART_SELECTED_NO_ALIGNED_BREAKOUT"]}
            audit["selectedSamePassed"]+=1
        elif mode=="C_SELECTED_OPPOSITE_VETO":
            if opp:
                audit["selectedOppositeVeto"]+=1
                return {"passed":False,"reasons":["CHART_SELECTED_OPPOSING_BREAKOUT"]}
        return {"passed":True,"reasons":[]}
    return gate


def overlay_score(symbol,rows,events,chosen,start,end):
    four=aggregate(rows,FOUR)
    daily=aggregate(rows,24*HOUR)
    lookup=ClosedEventLookup(events)
    out={}
    for mode in MODEL_NAMES:
        audit=Counter()
        replay=replay_pair(
            rows,four,daily,as_of=end,retest_hours=4,
            bos_quality_filter=evaluate_bos_quality,
            retest_quality_filter=overlay_gate(
                symbol,mode,four,lookup,chosen,audit),
        )
        sc=metrics(replay,start,end)
        out[mode]={
            "trades":sc["trades"],"wins":sc["wins"],
            "winRatePct":sc["winRatePct"],
            "netR9Bps":sc["totalNetR9BpsPerSide"],
            "netR25Bps":sc["totalNetR25BpsPerSideStress"],
            "maxDrawdownR":sc["maxDrawdownR"],
            "audit":dict(audit),
            "tradeEvidence":sc["tradeEntryExitEvidence"],
            "researchOnly":True,
        }
        print("CHART_OVERLAY",symbol,mode,sc["trades"],
              sc["totalNetR9BpsPerSide"],
              sc["totalNetR25BpsPerSideStress"],flush=True)
    baseline=out["A_V92_BASELINE"]
    parity_check(
        "2022_2024" if start==epoch(PERIODS["2022_2024"]["start"])
        else "2024_2026",symbol,{
            "trades":baseline["trades"],
            "totalNetR9BpsPerSide":baseline["netR9Bps"],
            "totalNetR25BpsPerSideStress":baseline["netR25Bps"],
        })
    for mode,z in out.items():
        z["deltaR9BpsVsBaseline"]=round(
            z["netR9Bps"]-baseline["netR9Bps"],6)
        z["deltaR25BpsVsBaseline"]=round(
            z["netR25Bps"]-baseline["netR25Bps"],6)
    return out


def run(workers):
    hist,proof=download_all(workers)
    datasets={}
    for pname,period in PERIODS.items():
        start,end=epoch(period["start"]),epoch(period["end"])
        ds={}
        for sym in SYMBOLS:
            hrs=hist[pname][sym]
            bars=aggregate(hrs,FOUR)
            ev=detect_all(bars)
            scores,order=score_events(ev,bars,start,end)
            ds[sym]={
                "events":ev,"ranking":order,"scores":scores,
                "detected4HBreakouts":len(ev),
                "lastConfirmed4H":stamp(bars[-1]["t"]+FOUR),
            }
            print("CHART_DETECTION",pname,sym,len(ev),
                  [(f,scores[f]["signalsWith24hOutcome"],
                    scores[f]["hitRatePct"]) for f in order[:5]],
                  flush=True)
        datasets[pname]=ds

    selection={s:choose_training_families(
        datasets["2022_2024"][s]["scores"]) for s in SYMBOLS}
    report={
        "status":"V92_CHART_PATTERNS_TRAIN_RANK_HOLDOUT_OVERLAY_HISTORICAL",
        "chartFamilies":list(FAMILIES),
        "source":"Binance official USD-M 1H monthly ZIPs SHA256 verified",
        "monthlySHA256Total":sum(len(p) for p in proof.values()),
        "sourceProofByPeriod":proof,
        "geometryAndThresholdsFrozenBeforeOutcomeMeasurement":True,
        "pivotRightConfirmationBars4H":2,
        "detectorsNeedCompleted4HBreakout":True,
        "standaloneTarget":"Next 4H open, stop 1.5x ATR14, target 1R, max 6 closed 4H candles, stop-first, timeout close mark",
        "hitRateDefinition":"Percentage of all completed next-24h outcomes that hit +1R before the stop; timeouts count as not hit",
        "standaloneExecutionAssumptionsNotV92Stops":True,
        "costBpsPerSide":[9,25],
        "rankOnlyEarlier2022_2024":True,
        "later2024_2026SelectionNotChangedByFutureOutcomes":True,
        "earlierPeriodHistoricallyInspectedNotTrulyUntouchedHoldout":True,
        "selectedBySymbol":selection,
        "periods":{},
        "noProductionV7V92Changes":True,
        "noPaperAccountBackfills":True,
        "noOrdersAndNoAlerts":True,
        "historicalWinnersDoNotCountTowardsForward50":True,
        "noExecutionFundingLiquidationParity":True,
    }
    for pname,period in PERIODS.items():
        start,end=epoch(period["start"]),epoch(period["end"])
        result={
            "span":[period["start"],period["end"]],
            "warmupStart":period["warmup"],
            "verifiedMonthlyArchives":len(proof[pname]),
            "symbols":{},
        }
        for sym in SYMBOLS:
            raw=datasets[pname][sym]
            selected=selection[sym]["selectedExploratory"]
            overlay=overlay_score(
                sym,hist[pname][sym],raw["events"],selected,start,end)
            # Summary only; do not accidentally label 4H standalone as
            # actual V7/BOS performance or as $1000 capped-account results.
            result["symbols"][sym]={
                "detected4HBreakouts":raw["detected4HBreakouts"],
                "rankedByStandaloneTargetHitPct":raw["ranking"],
                "standaloneByFamily":raw["scores"],
                "trainingSelectedFamiliesUsedForOverlay":selected,
                "v92Overlay":overlay,
                "breakoutExampleEvidence":raw["events"][:15],
            }
        report["periods"][pname]=result
    return report


def markdown(data):
    lines=[
        "# V9.2 — 4H grafik formasyonları: tespit, başarı sıralaması, backtest",
        "",
        "**Research only; V7, V9.2 paper account, main and notifications untouched.**",
        "",
        "All 4H pivots confirmed by TWO additional CLOSED bars. Formations are recognized",
        "only upon 4H CLOSING neckline/trendline/flag breakout, with no future candles.",
        "Geometry is fixed, reproducible approximation, not subjective perfect shapes.",
        "159 SHA256-verified Binance USD-M monthly BTC/ETH/SOL 1H files over",
        "two scored periods: 2022-10..2024-09 and 2024-10..2026-09.",
        "2022-05..09 indicator warmup; late period also has in-period warmup.",
        "",
        "**Standalone success** = after next 4H open, +1R target reached BEFORE",
        "1.5×ATR14 stop, within 6 closed 4H bars (24h); stop-first collision.",
        "Timeouts count as unsuccessful for hit%, but mark-to-market contributes",
        "to Net R. Costs 9bps per direction or 25bps stress, roundtrip.",
        "These are *NOT* V9.2 trading outcomes.",
        "",
        "## Ranking — EARLIER train period only (sort by hit%)",
        "",
        "| Coin | Rank | Pattern | n | Target-first | Hit % | Wilson lower 95% | Net R 9bps | Net R 25bps |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for sym in SYMBOLS:
        v=data["periods"]["2022_2024"]["symbols"][sym]
        for rank,fam in enumerate(v["rankedByStandaloneTargetHitPct"],1):
            s=v["standaloneByFamily"][fam]
            lines.append(
                f"| {_SYMBOL_LABELS[sym]} | {rank} | {fam} | {s['signalsWith24hOutcome']} | "
                f"{s['targetFirst']} | {s['hitRatePct'] if s['hitRatePct'] is not None else '—'} | "
                f"{s['wilsonLower95Pct'] if s['wilsonLower95Pct'] is not None else '—'} | "
                f"{s['netR9Bps']:+.3f} | {s['netR25Bps']:+.3f} |")
    lines += [
        "", "## Later validation — SAME detector and earlier-only selection",
        "",
        "| Coin | Pattern | Earlier n / hit% | Later n / hit% | Earlier Net R25 | Later Net R25 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for sym in SYMBOLS:
        a=data["periods"]["2022_2024"]["symbols"][sym]["standaloneByFamily"]
        b=data["periods"]["2024_2026"]["symbols"][sym]["standaloneByFamily"]
        for fam in data["periods"]["2022_2024"]["symbols"][sym]["rankedByStandaloneTargetHitPct"]:
            x,y=a[fam],b[fam]
            lines.append(
                f"| {_SYMBOL_LABELS[sym]} | {fam} | "
                f"{x['signalsWith24hOutcome']} / {x['hitRatePct']} | "
                f"{y['signalsWith24hOutcome']} / {y['hitRatePct']} | "
                f"{x['netR25Bps']:+.3f} | {y['netR25Bps']:+.3f} |")
    lines += ["", "## Locked prior-period selection and V9.2 overlay backtest",
             "",
             "Selection uses **only 2022-2024**: >=8 independent completed pattern",
             "events, >=45% 1R target-first, positive 25bps stressed net R;",
             "rank eligible by Wilson lower 95%, select at most top two per symbol.",
             "A >=30 prior-period events is merely a conservative sample gate,",
             "not formal statistical significance; NONE is promoted live.",
             "A = V9.2 original, B = require same-direction selected prior breakout",
             "within 12 closed 4H bars, C = veto opposite selected breakout",
             "within 12 closed 4H bars. Original SOL Star/Harami strict veto retained.",
             "No selected family means B may be zero trades, NOT a profitable result.",
             "",
             "| Period | Coin | Earlier selected | Overlay | Trades | Wins | Net R9 | Net R25 | DeltaR9 vs A | DeltaR25 vs A |",
             "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for pname,p in data["periods"].items():
        for sym in SYMBOLS:
            d=p["symbols"][sym]
            chosen=",".join(d["trainingSelectedFamiliesUsedForOverlay"]) or "NONE"
            for mode,z in d["v92Overlay"].items():
                lines.append(
                    f"| {pname} | {_SYMBOL_LABELS[sym]} | {chosen} | {mode} | "
                    f"{z['trades']} | {z['wins']} | "
                    f"{z['netR9Bps']:+.3f} | {z['netR25Bps']:+.3f} | "
                    f"{z['deltaR9BpsVsBaseline']:+.3f} | "
                    f"{z['deltaR25BpsVsBaseline']:+.3f} |")
    lines += [
        "", "## Methodological constraints",
        "",
        "- Raw target hit% must never be read without n; 1/1 is not a reliable edge. Wilson lower 95% is shown for sample-size context, NOT multiple-testing-adjusted confidence.",
        "- Multiple families and same-date signals can overlap; 6-bar same-family cooldown reduces but does not make outcomes independent.",
        "- The earlier split and later period have both been studied in past work. The later test is time-separated but NOT truly unseen independent data.",
        "- V9.2 baseline must match all 6 earlier sealed references or the run fails; overlapping/cancelled trades can affect later opportunities in overlay.",
        "- BTC/ETH/SOL 4H breakout-only standalones have different entry/stop/horizon from V9.2 BOS + retest. Do NOT equate two win percentages.",
        "- None of the chart-family candidates are live validated; previous 50-forward-trade gate and $1000 paper caps remain intact.",
        "- Execution price, funding, variable spread, liquidity, exchange stop fills and broker leverage are not proven by historical OHLCV.",
        "",
    ]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default="forward/v92_chart_patterns_20261113")
    args=p.parse_args()
    if not 1<=args.workers<=6:
        p.error("workers must be 1..6")
    result=run(args.workers)
    folder=Path(args.out);folder.mkdir(parents=True,exist_ok=True)
    (folder/"historical.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (folder/"historical.md").write_text(markdown(result)+"\n")
    print("CHART_PATTERN_159_SHA256_RANK_TRAIN_HOLDOUT_SIX_BASELINES_OK",flush=True)

if __name__=="__main__":
    main()
