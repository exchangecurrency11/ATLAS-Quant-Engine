"""V9 drop SOURCE-MISMATCHED tx count fields, not cherry-picked outcomes."""
import unittest,math
from v9_no_provider_tx_ablation import (
    DROP_INDICES,KEEP_INDICES,strip_transaction_count,
    transform_observations,comparison,SYMBOLS)
class NoTXTests(unittest.TestCase):
    def test_removed_exact_two_tx_features_per_asset(self):
        self.assertEqual(DROP_INDICES,(20,27,50,57,80,87))
        self.assertEqual(len(KEEP_INDICES),88)
        self.assertEqual(strip_transaction_count(tuple(range(94))),
                         tuple(i for i in range(94) if i not in DROP_INDICES))

    def test_change_to_only_trade_features_cannot_change_model_inputs(self):
        a=[i/10 for i in range(94)]
        b=a[:]
        for k in DROP_INDICES:b[k]=-9999.
        self.assertEqual(strip_transaction_count(a),strip_transaction_count(b))
        for k in (0,20,27,30,50,57,60,80,87,93):
            if k not in DROP_INDICES:
                c=a[:];c[k]+=.1
                self.assertNotEqual(strip_transaction_count(a),strip_transaction_count(c))

    def test_no_future_labels_edited_in_projection(self):
        xs={s:[{"t":12345,"x":tuple(range(94)),"y":1,
                "actualOpen":100.,"actualClose":102.}] for s in SYMBOLS}
        z=transform_observations(xs)
        for s in SYMBOLS:
            self.assertEqual(z[s][0]["y"],xs[s][0]["y"])
            self.assertEqual(z[s][0]["actualClose"],102.)
            self.assertEqual(len(z[s][0]["x"]),88)
            self.assertEqual(len(xs[s][0]["x"]),94)

    def test_invalid_length_or_non_finite_refused(self):
        with self.assertRaisesRegex(ValueError,"EXACT_94"):
            strip_transaction_count([0.]*93)
        b=[0.]*94;b[93]=float("nan")
        with self.assertRaisesRegex(ValueError,"PROJECTION_INVALID"):
            strip_transaction_count(b)

    def test_exact_same_holdout_denominator_enforced(self):
        a={s:{"logisticAll":{"predictions":2,"hitRatePct":50.}}
           for s in SYMBOLS}
        b={s:{"logisticAll":{"predictions":3,"hitRatePct":53.}}
           for s in SYMBOLS}
        with self.assertRaisesRegex(ValueError,"DIFFERENT_FOLD_CANDLES"):
            comparison(a,b)


if __name__=="__main__":
    unittest.main()
