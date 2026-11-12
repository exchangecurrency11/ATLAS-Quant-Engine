import unittest
from sol_div_01 import DivergenceIndex


def bars(kind):
    rows=[]
    for i in range(100):
        o=c=100.0
        h=101.0
        l=99.0
        if kind=="bull" and i in (30,50):
            l=90.0 if i==30 else 89.0
        if kind=="bear" and i in (30,50):
            h=110.0 if i==30 else 111.0
        tbv=6.0 if kind!="bear" else 4.0
        rows.append({"t":i*3600,"o":o,"h":h,"l":l,"c":c,"v":10.0,
                     "qv":1000.0,"trades":100,"tbv":tbv,
                     "tbq":tbv*100.0})
    return rows


class DivergenceIndexTests(unittest.TestCase):
    def test_bullish_lower_low_higher_cvd_after_pivot_confirmation(self):
        idx=DivergenceIndex(bars("bull"),3600)
        # Pivot at bar 50 is known only after bars 51 and 52 have closed.
        f=idx.at(53*3600)
        self.assertTrue(f["bullish"])
        self.assertFalse(f["bearish"])
        self.assertLess(f["bullishEvidence"]["latestPrice"],
                        f["bullishEvidence"]["priorPrice"])
        self.assertGreater(f["bullishEvidence"]["latestCVD"],
                           f["bullishEvidence"]["priorCVD"])

    def test_bearish_higher_high_lower_cvd_after_confirmation(self):
        idx=DivergenceIndex(bars("bear"),3600)
        f=idx.at(53*3600)
        self.assertTrue(f["bearish"])
        self.assertFalse(f["bullish"])
        self.assertGreater(f["bearishEvidence"]["latestPrice"],
                           f["bearishEvidence"]["priorPrice"])
        self.assertLess(f["bearishEvidence"]["latestCVD"],
                        f["bearishEvidence"]["priorCVD"])

    def test_unconfirmed_pivot_is_not_used(self):
        idx=DivergenceIndex(bars("bull"),3600)
        # At bar 51 close the right-hand confirmation bars are incomplete.
        f=idx.at(52*3600)
        self.assertFalse(f["bullish"])

    def test_expired_pivots_are_not_used(self):
        rows=bars("bull")
        idx=DivergenceIndex(rows,3600)
        f=idx.at(99*3600)
        self.assertFalse(f["bullish"])


if __name__=="__main__":
    unittest.main()
