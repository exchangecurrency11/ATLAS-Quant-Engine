import unittest
from sol_div_02 import retest_sweep


class LiquiditySweepTests(unittest.TestCase):
    def setUp(self):
        self.bars=[]
        for i in range(25):
            self.bars.append({"t":i*3600,"o":100.0,"h":105.0,
                              "l":95.0,"c":100.0,"v":10.0})
    def test_bullish_sweep_and_reentry(self):
        retest={"t":24*3600,"o":96.0,"h":102.0,"l":94.0,"c":97.0,"v":15.0}
        ok,e=retest_sweep(self.bars+[retest],"bullish",retest)
        self.assertTrue(ok)
        self.assertTrue(e["sweptAndReentered"])
    def test_bearish_sweep_and_reentry(self):
        retest={"t":24*3600,"o":104.0,"h":106.0,"l":98.0,"c":103.0,"v":15.0}
        ok,e=retest_sweep(self.bars+[retest],"bearish",retest)
        self.assertTrue(ok)
        self.assertTrue(e["sweptAndReentered"])
    def test_wick_without_close_back_inside_fails(self):
        retest={"t":24*3600,"o":94.0,"h":100.0,"l":93.0,"c":94.0,"v":15.0}
        ok,_=retest_sweep(self.bars+[retest],"bullish",retest)
        self.assertFalse(ok)
    def test_no_sweep_fails(self):
        retest={"t":24*3600,"o":99.0,"h":102.0,"l":96.0,"c":100.0,"v":15.0}
        ok,_=retest_sweep(self.bars+[retest],"bullish",retest)
        self.assertFalse(ok)


if __name__=="__main__":
    unittest.main()
