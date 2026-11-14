"""Causal evidence gates; test without network or any live account access."""
import unittest
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from collections import Counter
import btc_sol_v93_causal_regime_20261114 as m

class CausalBTCAndSOL(unittest.TestCase):
    def day(self,i):
        t=int(datetime(2026,5,1,tzinfo=timezone.utc).timestamp())+86400*i
        return {"t":t,"c":100.+i*0.1}
    def bars(self):
        return [self.day(i) for i in range(90)]
    def retest(self,ts):
        return {"t":ts-3600}
    def test_only_completed_daily_candles(self):
        bars=self.bars()
        close=[b["t"]+86400 for b in bars]
        ts=bars[65]["t"]+3600
        with patch.object(m.full,"volatility_asof",return_value="high") as f:
            self.assertEqual(m.decision(bars,close,self.retest(ts)),"high")
            self.assertEqual(f.call_args.args[1],65)
        # 65th daily candle not yet closed; only first 65 are eligible.
    def test_prev_close_included_but_no_current_partial(self):
        bars=self.bars()
        close=[b["t"]+86400 for b in bars]
        ts=bars[65]["t"]
        with patch.object(m.full,"volatility_asof",return_value="low") as f:
            self.assertEqual(m.decision(bars,close,self.retest(ts)),"low")
            self.assertEqual(f.call_args.args[1],65)
    def test_no_future_volatility_from_more_recent_candles(self):
        bars=self.bars()
        close=[b["t"]+86400 for b in bars]
        t=bars[70]["t"]+12*3600
        with patch.object(m.full,"volatility_asof",return_value="insufficient") as f:
            m.decision(bars,close,self.retest(t))
            self.assertEqual(f.call_args.args[1],70)
    def test_btc_short_always_unmodified(self):
        f,a=m.gate("BTCUSDT","CANDIDATE",self.bars(),[])
        with patch.object(m,"decision",side_effect=AssertionError("short should not query volatility")):
            x=f([],{"side":"bearish"},self.retest(self.bars()[70]["t"]))
        self.assertTrue(x["passed"])
        self.assertEqual(a["BTCShortUnchanged"],1)
    def test_btc_long_high_pass_low_reject(self):
        f,a=m.gate("BTCUSDT","CANDIDATE",self.bars(),[])
        with patch.object(m,"decision",return_value="low"):
            x=f([],{"side":"bullish"},self.retest(self.bars()[70]["t"]))
        self.assertFalse(x["passed"])
        with patch.object(m,"decision",return_value="high"):
            x=f([],{"side":"bullish"},self.retest(self.bars()[70]["t"]))
        self.assertTrue(x["passed"])
        self.assertEqual(a["regimeVeto"],1)
    def test_sol_original_reversal_veto_must_stay(self):
        with patch.object(m.old,"make_selective_gate",return_value=lambda bars,a,r:
                          {"passed":False,"reasons":["EXISTING_SOL_REVERSAL"]}):
            f,a=m.gate("SOLUSDT","CANDIDATE",self.bars(),[])
            with patch.object(m,"decision",side_effect=AssertionError("original veto first")):
                x=f([],{"side":"bullish"},self.retest(self.bars()[70]["t"]))
        self.assertFalse(x["passed"])
        self.assertEqual(a["originalSOLReversalVeto"],1)
    def test_sol_high_vol_applies_both_sides(self):
        with patch.object(m.old,"make_selective_gate",return_value=lambda bars,a,r:
                          {"passed":True,"reasons":[]}):
            f,a=m.gate("SOLUSDT","CANDIDATE",self.bars(),[])
            for side in ("bullish","bearish"):
                with patch.object(m,"decision",return_value="low"):
                    self.assertFalse(f([],{"side":side},self.retest(self.bars()[70]["t"]))["passed"])
                with patch.object(m,"decision",return_value="high"):
                    self.assertTrue(f([],{"side":side},self.retest(self.bars()[70]["t"]))["passed"])
        self.assertEqual(a["regimeVeto"],2)
    def test_no_forward_claim_and_pinned_event_dates(self):
        self.assertEqual(m.FREEZE,"2026-11-15T00:00:00Z")
        self.assertEqual(m.SYMBOLS,("BTCUSDT","SOLUSDT"))
        self.assertEqual(len(m.EVENTS),5)
        self.assertTrue(all(x[1]<x[2] and x[3].startswith("https://") for x in m.EVENTS))
    def test_event_window_boundaries_and_no_causality_claim(self):
        trade=lambda stamp:{"entryUTC":stamp,"riskPct":1.,"netR9Bps":1.}
        a=m.event_matches([trade("2024-02-05T00:00:00Z"),
                           trade("2024-02-11T00:00:00Z")])
        sol=[x for x in a if x["event"]=="SOL_OUTAGE_2024"][0]
        self.assertEqual(sol["n"],1)
        self.assertTrue(sol["onlyContextNotCausal"])

if __name__=="__main__":
    unittest.main()
