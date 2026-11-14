"""Synthetic tests for official BTC SOL daily smoke: tamper/gap/freeze."""
import unittest
from io import BytesIO,StringIO
import csv
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
from unittest.mock import patch
from datetime import date
import btc_sol_official_daily_smoke_20261114 as m

def fixture(sym,day,gap=None):
    out=StringIO();wr=csv.writer(out)
    from datetime import datetime,timezone
    start=int(datetime(day.year,day.month,day.day,tzinfo=timezone.utc).timestamp())*1000
    for hour in range(24):
        if hour==gap:continue
        t=start+hour*3600000
        wr.writerow([t,100,101,99,100,10,t+3599999,1000,20,5,500,0])
    z=BytesIO()
    with ZipFile(z,"w",ZIP_DEFLATED) as f:
        f.writestr(f"{sym}-1h-{day.isoformat()}.csv",out.getvalue())
    return z.getvalue()

class OfficialDataSmoketest(unittest.TestCase):
    def setUp(self):
        self.d=date(2026,11,13)
    def test_exact_24h_daily(self):
        for sym in m.SYMBOLS:
            self.assertEqual(len(m.decode_one_day(sym,self.d,fixture(sym,self.d))),24)
    def test_bad_day_missing_hour_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"GAP_DUPLICATE_OR_INCOMPLETE"):
            m.decode_one_day("SOLUSDT",self.d,fixture("SOLUSDT",self.d,gap=12))
    def test_vendor_checksum_is_verified(self):
        data=fixture("BTCUSDT",self.d);proof=sha256(data).hexdigest()
        with patch.object(m.archive,"get",side_effect=lambda url,max_size=0:
                          proof.encode() if url.endswith(".CHECKSUM") else data):
            _,sig=m.check_sha_zip("https://example.test/day.zip")
            self.assertEqual(sig,proof)
    def test_mismatch_vendor_hash_is_error(self):
        data=fixture("BTCUSDT",self.d)
        with patch.object(m.archive,"get",side_effect=lambda url,max_size=0:
                          ("0"*64).encode() if url.endswith(".CHECKSUM") else data):
            with self.assertRaisesRegex(ValueError,"SHA256_FAILED"):
                m.check_sha_zip("https://example.test/day.zip")
    def test_strict_prefreeze_and_source_count(self):
        self.assertLess(m.CUTOFF,m.CANDIDATE_FREEZE)
        self.assertEqual(m.TOTAL_HOURS,2520)
        self.assertEqual(len(m.DAYS),13)
        self.assertEqual(m.SYMBOLS,("BTCUSDT","SOLUSDT"))
    def test_frozen_source_hashes_currently_unchanged(self):
        proofs=m.frozen_guards()
        self.assertEqual(len(proofs),161) # 159 sealed through Sep + independent V9.3 Oct BTC/SOL
    def test_prevent_name_mismatch(self):
        with self.assertRaisesRegex(ValueError,"CSV_NAME"):
            m.decode_one_day("BTCUSDT",self.d,fixture("SOLUSDT",self.d))

if __name__=="__main__":unittest.main()
