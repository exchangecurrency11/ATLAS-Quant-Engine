"""V8.5 OHLCV one-shot: 1H->4H and no stale/repainting guard."""
import unittest
from sol_v85_current_closed_shadow import reconcile_h4_to_h1,HOUR,FOUR


def b(t,o,h,l,c,v):
    return {"t":t,"o":o,"h":h,"l":l,"c":c,"v":v}


class V85ClosedSourceTests(unittest.TestCase):
    def test_contiguous_1h_4h_bar_matches_actual_ohlcv(self):
        one=[b(i*HOUR,100+i,104+i,99+i,101+i,100+i) for i in range(4)]
        four=[b(0,100,107,99,104,406)]
        self.assertIsNone(reconcile_h4_to_h1(one,four))

    def test_disagreement_fails_closed_not_fake_last_4h(self):
        one=[b(i*HOUR,100+i,104+i,99+i,101+i,100+i) for i in range(4)]
        four=[b(0,100,107,99,104,999)]
        with self.assertRaisesRegex(ValueError,"DISAGREE_v"):
            reconcile_h4_to_h1(one,four)

    def test_missing_1h_constituent_invalid(self):
        one=[b(i*HOUR,100+i,104+i,99+i,101+i,100+i) for i in range(3)]
        four=[b(0,100,107,99,104,406)]
        with self.assertRaisesRegex(ValueError,"MISSING"):
            reconcile_h4_to_h1(one,four)


if __name__=="__main__":
    unittest.main()
