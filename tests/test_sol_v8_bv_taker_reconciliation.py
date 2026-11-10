"""Retrospective read-only SOL V8 data source comparison tests."""
import unittest
from sol_v8_bv_taker_reconciliation import provider_rows,compare
from sol_v8_derivatives_probe import SYMBOL

START=1793491200  # Nov 1 2026 UTC
HOUR=3600

def fake_provider(n=3,share=0.4):
    return [{"symbol":SYMBOL,"history":[{"t":START+i*HOUR,"v":100,
             "bv":100*share,"c":100.0} for i in range(n)]}]

def fake_reference(n=3):
    return {START+i*HOUR:{"v":100,"takerBuyBase":40,"c":100.0}
            for i in range(n)}

class CompareTests(unittest.TestCase):
    def test_identical_data_reconciled(self):
        p=provider_rows(fake_provider(),START,START+3*HOUR)
        r=compare(p,fake_reference(),START,3)
        self.assertEqual((r["matchedHours"],r["missingHours"]),(3,0))
        self.assertEqual(r["shareAbs"]["median"],0)

    def test_wrong_bv_does_not_pass_even_if_total_volume_matches(self):
        p=provider_rows(fake_provider(share=.62),START,START+3*HOUR)
        r=compare(p,fake_reference(),START,3)
        self.assertEqual(r["matchedHours"],0)
        self.assertEqual(r["mismatchedHours"],3)

    def test_missing_does_not_become_zero_or_valid(self):
        p=provider_rows(fake_provider(2),START,START+3*HOUR)
        r=compare(p,fake_reference(),START,3)
        self.assertEqual(r["missingHours"],1)
        self.assertEqual(r["pairedHours"],2)

    def test_wrong_symbol_rejected(self):
        z=fake_provider()
        z[0]["symbol"]="SOLUSD_SPOT"
        with self.assertRaisesRegex(ValueError,"WRONG_SOL_PERPETUAL"):
            provider_rows(z,START,START+3*HOUR)

    def test_unfinished_hour_is_excluded(self):
        z=fake_provider(4)
        p=provider_rows(z,START,START+3*HOUR)
        self.assertEqual(len(p),3)

    def test_duplicate_time_rejected(self):
        z=fake_provider()
        z[0]["history"][2]["t"]=START+HOUR
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            provider_rows(z,START,START+3*HOUR)

    def test_buy_above_total_rejected(self):
        z=fake_provider(share=1.1)
        with self.assertRaisesRegex(ValueError,"IMPOSSIBLE"):
            provider_rows(z,START,START+3*HOUR)

if __name__=="__main__":
    unittest.main()
