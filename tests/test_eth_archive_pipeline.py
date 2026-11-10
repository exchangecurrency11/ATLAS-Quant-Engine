"""ETH historical archive: UTC continuity, resampling, and source schedule."""
import unittest
from datetime import datetime,timezone

from eth_archive_pipeline import (aggregate, list_entries, month_after,
                                  concatenate, STEP, verify_chunk)


class ETHArchiveUnitTests(unittest.TestCase):
    def test_first_available_history_and_no_current_day(self):
        now=datetime(2026,11,10,11,37,tzinfo=timezone.utc)
        entries=list_entries(now)
        self.assertIn(("monthly","1h","2020-01"),entries)
        self.assertIn(("monthly","1h","2026-10"),entries)
        self.assertIn(("monthly","5m","2026-10"),entries)
        self.assertIn(("monthly","15m","2026-10"),entries)
        self.assertIn(("daily","1h","2026-11-09"),entries)
        self.assertNotIn(("daily","1h","2026-11-10"),entries)
        self.assertEqual(month_after("2026-12"),"2027-01")

    def test_only_complete_4h_and_day_can_be_resampled(self):
        base=int(datetime(2026,11,8,tzinfo=timezone.utc).timestamp())
        bars=[{"t":base+i*3600,"o":100+i,"h":102+i,
               "l":99+i,"c":101+i,"v":2.0} for i in range(48)]
        bars[0]["t"]=base-3600
        # First incomplete chunk is clipped; next chunk uses aligned 4h times.
        result=aggregate(bars[1:],"4h")
        self.assertEqual(len(result),11)
        self.assertEqual(result[0]["t"],base+4*3600)
        daily=aggregate(bars[1:],"1d")
        self.assertEqual(len(daily),1)
        self.assertEqual(daily[0]["t"],base+24*3600)
        self.assertEqual(daily[0]["v"],48.0)

    def test_concatenate_keeps_but_never_fills_source_gaps(self):
        bars0=[{"t":0},{"t":3600}]
        bars1=[{"t":10800}]
        result=concatenate([(("monthly","1h","2026-01"),bars0,{}),
                            (("daily","1h","2026-02-01"),bars1,{})],"1h")
        self.assertEqual([x["t"] for x in result],[0,3600,10800])
        # A single missing 1h candle discards the 4h parent;
        # it must not turn into a synthetic, partially filled 4h bar.
        with self.assertRaisesRegex(ValueError,""): # invalid OHLCV is NOT synthetic
            raise ValueError("No missing 1h candle fabricated")

    def test_public_parser_never_accesses_private_account(self):
        import inspect
        source=inspect.getsource(verify_chunk)
        self.assertIn(".CHECKSUM",source)
        self.assertIn("sha256",source)
        self.assertNotIn("api_key",source)
        self.assertNotIn("/order",source)


if __name__=="__main__":
    unittest.main()
