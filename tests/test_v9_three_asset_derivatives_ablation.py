"""V9 BTC ETH SOL Coinalyze OI/funding/CVD audit unit tests (no orders)."""
import copy
import json
import unittest
from v9_three_asset_derivatives_ablation import (
    HOUR,FOUR,CONTRACTS,get_group,features,variants,metric,evaluate_one,run
)


def make(days=10):
    source={name:[] for name in ("ohlcv-history","open-interest-history",
                                "funding-rate-history")}
    for i in range(days*24):
        t=i*HOUR
        base=100+i*.03
        ohl={"t":t,"o":base,"h":base+1,"l":base-1,
             "c":base+.1,"v":100,"bv":60 if i%12<6 else 40}
        oi={"t":t,"o":10000+2*i,"h":10003+2*i,"l":9999+2*i,
            "c":10002+2*i}
        funding={"t":t,"o":.0001,"h":.0002,"l":-.0002,
                 "c":.0001 if i%8 else -.0001}
        source["ohlcv-history"].append(ohl)
        source["open-interest-history"].append(oi)
        source["funding-rate-history"].append(funding)
    return source


def source_fetch(data,invalid_symbol=False):
    def fake(endpoint,params):
        rows=data[endpoint]
        return json.dumps([{"symbol":symbol if not invalid_symbol else "WRONG",
                 "history":rows} for symbol in CONTRACTS]).encode()
    return fake


class DerivativeAblationTests(unittest.TestCase):
    def test_btc_eth_sol_three_sources_4h_ablation(self):
        data=make()
        report=run(10*24*HOUR,"test-key",fetch=source_fetch(data))
        self.assertEqual(list(report["contracts"]),list(CONTRACTS))
        for asset in CONTRACTS:
            z=report["contracts"][asset]
            self.assertEqual(z["intended4HCheckpoints"],42)
            self.assertGreater(z["fullyAlignedEvaluable"],20)
            self.assertEqual(z["fullyAlignedEvaluable"]+
                             z["rejectedMissingOrIncomplete"],42)
            self.assertEqual(len(z["results"]),5)
            self.assertFalse(report["liveTradingApproved"])
        self.assertFalse(report["brokerOrders"])

    def test_only_closed_data_used_at_checkpoint(self):
        d=make()
        t=8*24*HOUR
        before=features(d["ohlcv-history"],d["open-interest-history"],
                        d["funding-rate-history"],t)
        self.assertTrue(before["sourceAlignedComplete28Hours"])
        modified=copy.deepcopy(d)
        for endpoint in modified:
            for row in modified[endpoint]:
                if row["t"]+HOUR>t:
                    row["c"]*=123
                    if "bv" in row:row["bv"]=0
        after=features(modified["ohlcv-history"],
                       modified["open-interest-history"],
                       modified["funding-rate-history"],t)
        self.assertEqual(before,after)

    def test_cvd_agree_and_oi_positive_required(self):
        d=make()
        t=8*24*HOUR
        r=features(d["ohlcv-history"],d["open-interest-history"],
                   d["funding-rate-history"],t)
        self.assertEqual(r["momentumSide"],"LONG")
        self.assertTrue(r["OIAdded"])
        self.assertIn(r["takerPressureSide"],("LONG","SHORT"))
        z=variants(r)
        self.assertEqual(z["A_priceMomentum"],"LONG")
        # fixed filter C cannot trigger without B
        self.assertEqual(bool(z["C_BplusRisingOI"]),bool(z["B_momentumAndCVD"]))

    def test_flat_funding_history_abstains_instead_of_confirming(self):
        d=make()
        t=8*24*HOUR
        for row in d["funding-rate-history"]:
            row["o"]=row["h"]=row["l"]=row["c"]=0.01
        f=features(d["ohlcv-history"],d["open-interest-history"],
                   d["funding-rate-history"],t)
        self.assertFalse(f["fundingVariationSufficient"])
        self.assertEqual(f["fundingPrior24UniqueValues"],1)
        self.assertIsNone(f["fundingPercentileRelativePrior24"])
        self.assertIsNone(variants(f)["D_CplusFundingContext"])

    def test_matched_baseline_for_oi_subset_and_funding_counts(self):
        d=make()
        x=evaluate_one(d["ohlcv-history"],d["open-interest-history"],
                       d["funding-rate-history"])
        for name,comparison in x["matchedBaselineComparisons"].items():
            self.assertEqual(comparison["baselineCorrectSameEvents"],
                             comparison["filteredCorrectSameEvents"])
            self.assertTrue(comparison["noDirectionalEdgeInferredFromSelection"])
        self.assertLessEqual(x["fundingCheckpointsWithMeaningfulVariation"],
                             x["intended4HCheckpoints"])

    def test_missing_one_hour_in_oi_rejects_checkpoint(self):
        d=make()
        t=8*24*HOUR
        d["open-interest-history"]=[r for r in d["open-interest-history"] if r["t"]!=t-HOUR]
        self.assertIsNone(features(d["ohlcv-history"],
                        d["open-interest-history"],
                        d["funding-rate-history"],t))

    def test_bad_source_symbol_fails_closed(self):
        d=make()
        with self.assertRaisesRegex(ValueError,"WRONG_SYMBOL_GROUP"):
            run(10*24*HOUR,"test",fetch=source_fetch(d,True))

    def test_not_treat_funding_as_cash_settlement(self):
        d=make()
        z=run(10*24*HOUR,"key",fetch=source_fetch(d))
        self.assertIn("not certified",z["fundingFieldSemantics"])
        self.assertTrue(z["previousHistoricalAnalysesMakeThisExploratoryNotProspective"])
        self.assertTrue(z["samplesAcrossBTCETHSOLCorrelated"])

    def test_zero_predictions_wont_claim_performance(self):
        z=metric([{"prediction":None,"correct":None}])
        self.assertIsNone(z["hitRatePct"])
        self.assertEqual(z["noSignal"],1)
        self.assertEqual(z["predictions"],0)

    def test_75_pct_from_4_does_not_become_large_research_sample(self):
        z=metric([{"prediction":"LONG","correct":x} for x in (1,1,1,0)])
        self.assertEqual(z["hitRatePct"],75.)
        self.assertLess(z["wilson95LowerBoundPct"],50)

    def test_incomplete_current_1h_removed_by_provider_filter(self):
        d=make()
        for endpoint in d:
            d[endpoint].append({**d[endpoint][-1],"t":10*24*HOUR})
        out,hash_=get_group("ohlcv-history",CONTRACTS,"key",0,10*24*HOUR,
                            fetch=source_fetch(d))
        self.assertEqual(out["BTCUSDT_PERP.A"][-1]["t"],(10*24-1)*HOUR)
        self.assertEqual(len(hash_),64)


if __name__=="__main__":
    unittest.main()
