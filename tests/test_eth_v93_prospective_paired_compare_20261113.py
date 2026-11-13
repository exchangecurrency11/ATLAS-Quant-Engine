"""ETH prospective two-branch comparison: no future leak, no fake edge."""
import copy
import json
import unittest
from pathlib import Path
import eth_v93_prospective_paired_compare_20261113 as c

class PairedETH(unittest.TestCase):
    def setUp(self):
        self.source=json.loads((c.SHADOW/"preflight.json").read_text())
        self.spec=json.loads((c.SHADOW/"frozen_spec.json").read_text())
    def make_trade(self,entry="2026-11-15T10:00:00Z",side="bullish",r=1.2):
        # Used only as unit-test input, never written to a forward account.
        return {"watchKnownUTC":"2026-11-15T08:00:00Z",
                "retestKnownUTC":"2026-11-15T09:00:00Z",
                "entryOpenUTC":entry,"exitKnownUTC":"2026-11-15T14:00:00Z",
                "side":side,"entry":1800.,"stop":1780.,
                "targets":[1820.,1840.,1860.],"netR9Bps":r,
                "netR25Bps":r-.32}
    def test_baseline_frozen_no_new_data(self):
        c.spec_guard(self.spec)
        out=c.compare(self.source,"PREFREEZE_NO_ELIGIBLE_TRADES",None)
        self.assertEqual(out["status"],"ETH_NO_NEW_DATA_BEFORE_FROZEN_START")
        self.assertIsNone(out["comparison"]["deltaR25Bps"])
        self.assertEqual(out["comparison"]["reference"]["metrics25Bps"]["trades"],0)
        self.assertFalse(out["review"]["candidateApprovedForPromotion"])
    def test_six_streams_and_frozen_spec_no_parameter_drifts(self):
        self.assertEqual(len(self.source["reportedStreams"]),6)
        self.assertTrue(c.guard_packet(self.source,self.spec))
        changed=copy.deepcopy(self.spec)
        changed["candidates"][c.ETH_CAND]["disabledGates"]=[]
        with self.assertRaisesRegex(ValueError,"FROZEN_RESEARCH_SPEC"):
            c.spec_guard(changed)
    def test_forged_prefreeze_trade_rejected(self):
        forged=copy.deepcopy(self.source)
        pair=forged["reportedStreams"][c.ETH_CAND]
        pair["closedProspectiveTrades"]=[self.make_trade()]
        pair["metrics9Bps"]["trades"]=1
        pair["metrics25Bps"]["trades"]=1
        with self.assertRaisesRegex(ValueError,"LOOKAHEAD|PREFREEZE"):
            c.compare(forged,"PREFREEZE_NO_ELIGIBLE_TRADES",None)
    def test_before_freeze_trade_never_credited(self):
        t=self.make_trade()
        t["watchKnownUTC"]="2026-11-13T21:00:00Z"
        with self.assertRaisesRegex(ValueError,"LOOKAHEAD"):
            c.validate_tape({"closedProspectiveTrades":[t],
                             "metrics9Bps":{"trades":1},
                             "metrics25Bps":{"trades":1}},
                            c.dt("2026-12-01T00:00:00Z"))
    def test_missing_trade_close_never_credited(self):
        t=self.make_trade()
        t["exitKnownUTC"]="2026-12-01T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"LOOKAHEAD"):
            c.validate_tape({"closedProspectiveTrades":[t],
                             "metrics9Bps":{"trades":1},
                             "metrics25Bps":{"trades":1}},
                            c.dt("2026-12-01T00:00:00Z"))
    def test_shared_entry_exit_drift_is_rejected(self):
        a=self.make_trade()
        b=copy.deepcopy(a)
        b["netR25Bps"]+=.1
        with self.assertRaisesRegex(ValueError,"SHARED"):
            c.paired([a],[b])
    def test_added_trades_are_not_fake_shared_win(self):
        b=self.make_trade()
        x=c.paired([],[b])
        self.assertEqual(x["common"],0)
        self.assertEqual(x["candidateOnly"],1)
        self.assertAlmostEqual(x["deltaFromIncrementalEntriesR25"],.88)
    def test_regime_and_coverage_not_claimed_from_zero(self):
        a=self.source["reportedStreams"][c.ETH_REF]
        b=self.source["reportedStreams"][c.ETH_CAND]
        v=c.verdict(a,b,c.dt("2026-11-01T00:00:00Z"))
        self.assertFalse(v["candidateApprovedForPromotion"])
        self.assertFalse(v["preliminaryCoverageGates"]["differentRegimesVerified"])
        self.assertFalse(v["preliminaryCoverageGates"]["atLeast180CalendarDays"])
    def test_no_presumed_notification(self):
        p=c.OUTPUT
        self.assertTrue("forward" in str(p))
        self.assertNotEqual(c.ETH_REF,c.ETH_CAND)
        self.assertEqual(c.FREEZE,"2026-11-14T00:00:00Z")

if __name__=="__main__":
    unittest.main()
