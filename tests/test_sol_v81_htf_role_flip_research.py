"""V8.1 causal 4H role-flip, stop-first and manual-zone safety tests."""
import unittest
from unittest.mock import patch

from sol_v81_htf_role_flip_research import (
    USER_ZONE,TARGET,candidates,detect_break_and_retest,
    paper_outcome,summarize,user_zone_audit,validate_rows,
)


def bar(i, o, h, l, c, v=100):
    return {"t":i*14400,"o":o,"h":h,"l":l,"c":c,"v":v}


def mock_history():
    bars=[]
    for i in range(90):
        if i<37: bars.append(bar(i,103.7,105,102.7,104))
        elif i==37:bars.append(bar(i,103,103.8,98,98.8,500))
        elif i==38:bars.append(bar(i,100.8,101.5,98.7,99.4,180))
        elif i==39:bars.append(bar(i,99,99.2,95.7,96.8,180))
        else:bars.append(bar(i,96.7,97.7,95.8,96.5))
    return bars


class RoleFlipTests(unittest.TestCase):
    def test_zone_distinct_from_strict_ict_breaker(self):
        self.assertEqual(USER_ZONE,(87.5,95))
        self.assertEqual(TARGET,1794326400)

    def test_break_after_confirmation_and_retest_later(self):
        bars=mock_history()
        z={"knownIndex":25,"zoneLow":100.0,"zoneHigh":102.0}
        found=detect_break_and_retest(bars,z)
        self.assertEqual(found["state"],"BEARISH_RETEST_REJECTED")
        self.assertEqual(found["breakIndex"],37)
        self.assertEqual(found["retestIndex"],38)
        self.assertEqual(found["entryIndex"],39)
        self.assertLess(found["breakIndex"],found["retestIndex"])
        self.assertLess(found["retestIndex"],found["entryIndex"])

    def test_stop_first_if_same_4h_candle_hits_both(self):
        bars=mock_history()
        z={"knownIndex":25,"zoneLow":100.0,"zoneHigh":102.0}
        found=detect_break_and_retest(bars,z)
        at=found["entryIndex"]
        # deliberately hit both stop and 2R within the same candle
        bars[at]["h"]=120
        bars[at]["l"]=80
        ret=paper_outcome(bars,z,found)
        self.assertEqual(ret["status"],"COMPLETED_HYPOTHETICAL")
        self.assertEqual(ret["exitReason"],"STOP_FIRST")
        self.assertLess(ret["netR"],-1)
        self.assertGreaterEqual(ret["netPnLUSDT"],-0.500001)

    def test_reclaim_blocks_bearish_retest(self):
        bars=mock_history()
        bars[38]=bar(38,99,104,98,103)
        zone={"knownIndex":25,"zoneLow":100.0,"zoneHigh":102.0}
        found=detect_break_and_retest(bars,zone)
        self.assertEqual(found["state"],"RECLAIMED_NO_BEARISH_RETEST")

    def test_no_bos_before_known_index(self):
        bars=mock_history()
        zone={"knownIndex":75,"zoneLow":100.0,"zoneHigh":102.0}
        found=detect_break_and_retest(bars,zone)
        self.assertEqual(found["state"],"NO_QUALIFIED_BREAK")

    def test_gap_and_future_rows_rejected(self):
        rows=[bar(0,10,12,9,11),bar(1,11,13,10,12)]
        self.assertTrue(validate_rows(rows,14400,2*14400))
        with self.assertRaisesRegex(ValueError,"FUTURE_CANDLE_INCLUDED"):
            validate_rows(rows,14400,14400)
        rows[1]["t"]+=14400
        with self.assertRaisesRegex(ValueError,"DISCONTINUOUS_HISTORY"):
            validate_rows(rows,14400,3*14400)

    def test_zero_trades_does_not_report_fake_win_rate(self):
        x=summarize([],0,100)
        self.assertEqual(x["trades"],0)
        self.assertIsNone(x["winPct"])
        self.assertIsNone(x["profitFactorR"])

if __name__=="__main__":
    unittest.main()
