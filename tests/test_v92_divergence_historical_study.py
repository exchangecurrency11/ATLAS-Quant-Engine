"""Research-only no-lookahead divergence and Binance taker-base tests."""
import copy
import unittest

from v92_divergence_historical_study import (
    divergence_at, indicators, pivot_index, features_at, sweep_at,
    volume_spike_at, HOUR, RIGHT, VOLUME_SPIKE_RATIO,
)

def candles():
    rows=[{"t":i*HOUR,"o":100.,"h":101.,"l":99.,"c":100.,
           "v":100.,"tbv":60.} for i in range(130)]
    rows[96]["l"]=95.
    rows[106]["l"]=94.
    rows[96]["o"]=99.;rows[96]["c"]=99.
    rows[106]["o"]=99.;rows[106]["c"]=99.
    return rows

class DivergenceNoLookaheadTests(unittest.TestCase):
    def test_two_consecutive_closed_bars_required_to_confirm_pivot(self):
        rows=candles()
        osc=[20.]*len(rows)
        osc[96]=10.
        osc[106]=15.
        self.assertTrue(pivot_index(rows,106,"bullish"))
        self.assertFalse(divergence_at(rows,osc,107,"bullish"))
        self.assertTrue(divergence_at(rows,osc,108,"bullish"))
        self.assertFalse(divergence_at(rows,osc,108,"bearish"))

    def test_future_candle_mutation_cannot_change_past_divergence(self):
        rows=candles()
        osc=[20.]*len(rows)
        osc[96]=10.;osc[106]=15.
        before=divergence_at(rows,osc,108,"bullish")
        modified=copy.deepcopy(rows)
        for i in range(109,len(modified)):
            modified[i].update({"l":1.,"h":250.,"c":105.,"tbv":0.})
        after=divergence_at(modified,osc,108,"bullish")
        self.assertTrue(before)
        self.assertEqual(before,after)

    def test_taker_cvd_fields_real_not_inferred_from_price_direction(self):
        rows=candles()
        ind=indicators(rows)
        self.assertAlmostEqual(ind["cvd"][1],40.)
        self.assertEqual(len(ind["rsi"]),len(rows))
        self.assertEqual(len(ind["macd_hist"]),len(rows))
        rows[80].pop("tbv")
        with self.assertRaisesRegex(ValueError,"TAKER_OR_PRICE_FIELD_MISSING"):
            indicators(rows)

    def test_zero_future_price_for_sweep_and_spike(self):
        rows=candles()
        rows[110]["l"]=97.
        rows[110]["c"]=99.
        rows[110]["v"]=180.
        self.assertTrue(sweep_at(rows,110,"bullish"))
        self.assertTrue(volume_spike_at(rows,110))
        self.assertFalse(sweep_at(rows,110,"bearish"))
        rows[111]["l"]=1.
        rows[111]["h"]=1000.
        self.assertTrue(sweep_at(rows,110,"bullish"))

    def test_retest_close_is_hourly_closed_not_next_open(self):
        rows=candles()
        ind=indicators(rows)
        indices={b["t"]+HOUR:i for i,b in enumerate(rows)}
        at=109*HOUR
        actual=features_at(rows,ind,indices,at,"bullish")
        self.assertEqual(set(actual),{"cvd","rsi","macd","sweep","volumeSpike"})
        with self.assertRaisesRegex(ValueError,"MISSING_CONFIRMED_CLOSE"):
            features_at(rows,ind,indices,999*HOUR,"bullish")

if __name__=="__main__":
    unittest.main()
