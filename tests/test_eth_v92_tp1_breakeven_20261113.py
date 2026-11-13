"""Research-only TP1-then-next-bar stop-to-entry tests, stop first always."""
import unittest
import eth_v92_tp1_breakeven_20261113 as m
import backtest_retest_long_v4 as orig

class ExitBE(unittest.TestCase):
    def position(self,side="bullish"):
        entry=100.
        return {"side":side,"entry":entry,"risk":1.,
                "stop":99 if side=="bullish" else 101,
                "targets":[101,102,103] if side=="bullish" else [99,98,97],
                "targetCount":0,"realizedR":0.}
    def bar(self,o=100,h=100.5,l=99.5,c=100):
        return {"o":o,"h":h,"l":l,"c":c}
    def test_tp1_first_bar_not_protected_until_next_bar(self):
        pos=self.position()
        c,reason=m.be_after_prior_tp1(pos,self.bar(o=100,h=101.5,l=99.5,c=101))
        self.assertFalse(c)
        self.assertEqual(pos["targetCount"],1)
        self.assertTrue(pos["_be_armed"])
        self.assertAlmostEqual(pos["realizedR"],1/3)
    def test_same_first_hour_stop_beats_tp1(self):
        pos=self.position()
        closed,reason=m.be_after_prior_tp1(pos,self.bar(o=100,h=102,l=98,c=99))
        self.assertTrue(closed)
        self.assertEqual(reason,"STOP_FIRST_OR_AFTER_TP")
        self.assertEqual(pos["targetCount"],0)
        self.assertNotIn("_be_armed",pos)
    def test_next_hour_stop_to_entry_protects_remaining(self):
        p=self.position()
        m.be_after_prior_tp1(p,self.bar(h=101.5,l=99.5))
        closed,reason=m.be_after_prior_tp1(p,self.bar(o=101.3,h=101.5,l=99.5))
        self.assertTrue(closed)
        self.assertEqual(reason,"TP1_PRIOR_CLOSE_BE_PROTECT")
        self.assertAlmostEqual(p["realizedR"],1/3)
    def test_next_hour_stop_first_though_tp2_hits(self):
        p=self.position()
        m.be_after_prior_tp1(p,self.bar(h=101.5,l=99.5))
        closed,reason=m.be_after_prior_tp1(p,self.bar(o=101.1,h=103,l=99.8))
        self.assertTrue(closed)
        self.assertEqual(reason,"TP1_PRIOR_CLOSE_BE_PROTECT")
        self.assertEqual(p["targetCount"],1)
    def test_gap_down_long_not_falsely_assume_no_loss(self):
        p=self.position()
        m.be_after_prior_tp1(p,self.bar(h=101.5,l=99.5))
        closed,reason=m.be_after_prior_tp1(p,self.bar(o=98.5,h=99,l=97))
        self.assertTrue(closed)
        self.assertEqual(reason,"TP1_PRIOR_CLOSE_BE_PROTECT")
        self.assertAlmostEqual(p["realizedR"],(1/3)-1.5*(2/3))
    def test_short_gap_up_not_falsely_assume_no_loss(self):
        p=self.position(side="bearish")
        m.be_after_prior_tp1(p,self.bar(o=100,h=100.5,l=98.5))
        closed,reason=m.be_after_prior_tp1(p,self.bar(o=102,h=103,l=101))
        self.assertTrue(closed)
        self.assertEqual(reason,"TP1_PRIOR_CLOSE_BE_PROTECT")
        self.assertAlmostEqual(p["realizedR"],(1/3)-2*(2/3))
    def test_original_global_function_not_monkeypatched(self):
        self.assertIs(orig.assess_candle,m.ORIG_ASSESS)
        self.assertEqual(m.EXITS,("ORIGINAL","TP1_NEXT_1H_BREAK_EVEN"))
        self.assertEqual(m.MODES,(
            "BASELINE","PAIR_NO_BREAK_ATR_AND_EMA_EXT",
            "PAIR__bos_break_atr__retest_window"))
    def test_same_entry_change_with_new_sequence_is_allowed(self):
        def tr(ts,side,exit_ts,ret):
            return {"entryOpenUTC":ts,"side":side,"exitKnownUTC":exit_ts,
                    "entry":100.,"risk":1.,"netRIllustrative":ret}
        base=[tr(3600,"bullish",7200,.5)]
        alt=[tr(3600,"bullish",10800,.7),tr(7200,"bearish",14400,-.1)]
        p=m.paired_replay(base,alt)
        self.assertEqual(p["sameEntryCount"],1)
        self.assertEqual(p["sameEntryModifiedExitCount"],1)
        self.assertEqual(p["addedEntryCount"],1)

if __name__=="__main__":
    unittest.main()
