"""ETH V7 read-only forward observer: no stale, spot, fake or unclosed signals."""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

import eth_v7_hourly_observer as eth

TARGET=int(datetime(2026,11,10,11,tzinfo=timezone.utc).timestamp())
NOW=TARGET+28*60


def kline(t,seconds,o=100,h=101,l=99,c=100,v=100):
    return [t*1000,str(o),str(h),str(l),str(c),str(v),
            (t+seconds)*1000-1,"0",10,"0","0","0"]


def raw_feed():
    h=[]
    for i in range(750):
        t=TARGET-(750-i)*eth.HOUR
        h.append(kline(t,eth.HOUR))
    # Include ongoing candle: it must NOT enter the verification, BOS or trades.
    h.append(kline(TARGET,eth.HOUR,c=999999))
    h_by_t={int(k[0])//1000:k for k in h[:-1]}

    def tf_rows(seconds,n):
        close=(TARGET//seconds)*seconds
        out=[]
        for i in range(n):
            start=close-(n-i)*seconds
            hours=[h_by_t.get(start+j*eth.HOUR) for j in range(seconds//eth.HOUR)]
            if all(x is not None for x in hours):
                oo=float(hours[0][1]);high=max(float(x[2]) for x in hours)
                low=min(float(x[3]) for x in hours)
                cc=float(hours[-1][4]);vol=sum(float(x[5]) for x in hours)
                out.append(kline(start,seconds,oo,high,low,cc,vol))
            else:
                parts=seconds//eth.HOUR
                out.append(kline(start,seconds,100,101,99,100,100*parts))
        return out

    return {
        "1hour":(h,"test-1h-source-sha"),
        "4hour":(tf_rows(14400,300),"test-4h-source-sha"),
        "daily":(tf_rows(86400,300),"test-day-source-sha")
    }


class ETHV7ForwardTests(unittest.TestCase):
    def test_valid_closed_ohlcv_three_timeframes_and_no_live_orders(self):
        raw=raw_feed()
        b,_,cross=eth.validate_sources(raw,TARGET,NOW)
        self.assertEqual(b["1hour"][-1]["t"]+eth.HOUR,TARGET)
        self.assertEqual(cross["1H_matches_4H"],5)
        self.assertEqual(cross["1H_matches_daily"],5)
        obs=eth.build_observation(raw,TARGET,NOW)
        self.assertEqual(obs["status"],"VERIFIED_PAPER_OBSERVATION")
        self.assertEqual(len(obs["results"][eth.RESEARCH_PAIR]),3)
        self.assertEqual(obs["marketContext"][eth.RESEARCH_PAIR]["newBOSCount"],0)
        self.assertIn("ETH",eth.format_report({
            **obs,"targetClosed1HUTC":eth.iso(TARGET),
            "observedAtUTC":eth.iso(NOW)}))

    def test_gapped_1h_fails_even_when_old_data_exists(self):
        feed=raw_feed()
        rows=feed["1hour"][0]
        del rows[-16]
        with self.assertRaisesRegex(ValueError,"not continuous"):
            eth.validate_sources(feed,TARGET,NOW)

    def test_source_timeframe_disagreement_is_rejected(self):
        feed=raw_feed()
        feed["4hour"][0][-2][5]="401"  # valid OHLC, inconsistent 4H volume
        with self.assertRaisesRegex(ValueError,"divergence"):
            eth.validate_sources(feed,TARGET,NOW)

    def test_stale_source_no_signal(self):
        feed=raw_feed()
        del feed["1hour"][0][-2]  # last CLOSED 1H removed; next is unclosed
        with self.assertRaises(ValueError):
            eth.validate_sources(feed,TARGET,NOW)

    def test_early_timestamp_cannot_claim_verified(self):
        feed=raw_feed()
        with self.assertRaisesRegex(ValueError,"latest closed"):
            eth.validate_sources(feed,TARGET,TARGET+5*60)

    def test_http451_error_makes_explicit_no_signal_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory,"snapshot.json")
            report=Path(directory,"snapshot.md")
            with patch.object(eth,"public_klines",side_effect=RuntimeError("BINANCE_USDM_HTTP_451")):
                obj=eth.run(output,report,TARGET,NOW)
            self.assertEqual(obj["status"],"SOURCE_UNAVAILABLE_NO_SIGNAL")
            self.assertFalse(obj["paperForwardObservation"])
            self.assertFalse(obj["brokerOrders"])
            self.assertNotIn("results",obj)
            self.assertIn("HTTP_451",output.read_text())
            self.assertIn("SİNYAL YOK",report.read_text())


if __name__=="__main__":
    unittest.main()
