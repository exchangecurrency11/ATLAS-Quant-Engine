"""V9 independent Binance vs Coinalyze fields: never certify mismatched tx/bv."""
import unittest,json,io,csv
from zipfile import ZipFile
from hashlib import sha256
from datetime import datetime,timezone
from v9_binance_coinalyze_seven_field_parity import (
  compare_pair,audit,checked_official_zip,day_bound,FIELDS)

DAY="2026-10-29"
START,_=day_bound(DAY)


def sample():
    official=[]
    for j in range(24):
        a=100+j*.1
        official.append({"t":START+j*3600,"o":a,"h":a+1,
                        "l":a-1,"c":a+.3,"v":1000.,
                        "tbv":480.,"trades":150})
    return official


class V9ParityTests(unittest.TestCase):
    def test_exact_source_seven_fields_matches(self):
        a=sample()
        m=compare_pair(a,[dict(x) for x in a])
        self.assertTrue(m["allSevenFieldsParity"])
        self.assertEqual(m["barsCompared"],24)
        self.assertTrue(m["coinalyzeTxEqualsOfficialNumberOfTrades"])

    def test_tx_mismatch_only_means_tx_unverified_not_ohlcv(self):
        a=sample()
        b=[dict(x) for x in a]
        for x in b:x["trades"]*=2
        z=compare_pair(a,b)
        self.assertFalse(z["coinalyzeTxEqualsOfficialNumberOfTrades"])
        self.assertTrue(z["priceOHLCParity"])
        self.assertTrue(z["totalVolumeParity"])
        self.assertTrue(z["takerBuyBaseParity"])
        self.assertFalse(z["allSevenFieldsParity"])
        self.assertEqual(z["mismatchesByField"]["trades"],24)

    def test_bv_mismatch_critical_even_if_prices_match(self):
        a=sample();b=[dict(x) for x in a]
        b[0]["tbv"]=200.
        z=compare_pair(a,b)
        self.assertFalse(z["takerBuyBaseParity"])
        self.assertEqual(z["mismatchesByField"]["tbv"],1)
        self.assertTrue(z["priceOHLCParity"])
        self.assertFalse(z["allSevenFieldsParity"])

    def test_time_shift_rejected(self):
        a=sample();b=[dict(x) for x in a]
        b[-1]["t"]+=3600
        with self.assertRaisesRegex(ValueError,"SAME_HOUR"):
            compare_pair(a,b)

    def test_archive_checksum_and_full_trade_fields(self):
        out=io.BytesIO()
        with ZipFile(out,"w") as z:
            lines=[]
            for i in range(24):
                t=(START+i*3600)*1000
                lines.append([str(t),"100","101","99","100.3","1000",
                             str(t+3599999),"100000","150","480",
                             "48000","0"])
            writer=io.StringIO()
            w=csv.writer(writer);w.writerows(lines)
            z.writestr(f"BTCUSDT-1h-{DAY}.csv",writer.getvalue())
        data=out.getvalue()
        digest=sha256(data).hexdigest()
        def fetch(url,max_size=1000000):
            return (digest+"  file.zip").encode() if url.endswith(".CHECKSUM") else data
        rows,meta=checked_official_zip("BTCUSDT",DAY,download=fetch)
        self.assertEqual(meta["sha256Verified"],digest)
        self.assertEqual(len(rows),24)
        self.assertEqual(rows[-1]["trades"],150)
        self.assertEqual(rows[-1]["tbv"],480.)
        def wrong(url,max_size=1000000):
            return b"f"*64 if url.endswith(".CHECKSUM") else data
        with self.assertRaisesRegex(ValueError,"SHA256_MISMATCH"):
            checked_official_zip("BTCUSDT",DAY,download=wrong)


if __name__=="__main__":
    unittest.main()
