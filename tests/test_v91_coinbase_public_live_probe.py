import unittest
import datetime as dt
from urllib.parse import urlparse

from research.v91_coinbase_public_live_probe import (
    run_probe, inspect_spot_candles, inspect_spot_ticker, inspect_intx_quote
)

H=3600
close=dt.datetime(2026,11,11,17,tzinfo=dt.timezone.utc).timestamp()
now=close+900
def fake(url):
    q=urlparse(url)
    if q.hostname == "api.exchange.coinbase.com":
        if q.path.endswith("/ticker"):
            return {"status":"JSON_RECEIVED","_payload":{
                "price":"101.25","time":"2026-11-11T17:14:59Z",
                "volume":"100"}}
        if q.path.endswith("/candles"):
            return {"status":"JSON_RECEIVED","_payload":[
                [int(close-H),96,106,100,101,80],
                [int(close-2*H),91,103,99,100,75],
            ]}
    if q.hostname == "api.international.coinbase.com" and q.path.endswith("/quote"):
        return {"status":"JSON_RECEIVED","_payload":{"bid":"100","ask":"102"}}
    raise AssertionError(url)

class Tests(unittest.TestCase):
    def test_valid_spot_and_perp_independent_venues(self):
        results=run_probe(now,fake)
        self.assertTrue(results["allThreeSpotFreshAndClosed"])
        self.assertTrue(results["allThreePerpPublicQuotesReachable"])
        self.assertFalse(results["binancePerpParityProven"])
        self.assertFalse(results["orders"])
        self.assertFalse(results["alerts"])
        self.assertEqual(set(results["assets"].keys()),{"BTC","ETH","SOL"})
        for asset in ("BTC","ETH","SOL"):
            r=results["assets"][asset]
            self.assertEqual(r["coinbaseSpotTicker"]["status"],"FRESH_COINBASE_SPOT_TICKER")
            self.assertEqual(r["coinbaseSpotClosed1H"]["status"],"VALID_COINBASE_SPOT_CLOSED_1H")
            self.assertEqual(r["coinbaseSpotClosed1H"]["candle"]["openTimeUTC"],"2026-11-11T16:00:00Z")
            self.assertEqual(r["coinbaseIntxPerpQuote"]["status"],
                             "INTX_PUBLIC_PERP_QUOTE_ENDPOINT_REACHABLE_UNVERIFIED")
    def test_403_fails_closed(self):
        result=run_probe(now, lambda url:{"status":"HTTP_UNAVAILABLE","httpCode":403})
        self.assertFalse(result["allThreeSpotFreshAndClosed"])
        self.assertFalse(result["allThreePerpPublicQuotesReachable"])
    def test_stale_ticker_fails_closed(self):
        ticker=inspect_spot_ticker({"status":"JSON_RECEIVED","_payload":{
            "price":"99","time":"2026-11-11T16:00:00Z"}},now)
        self.assertEqual(ticker["status"],"TICKER_INVALID_OR_STALE")
    def test_malformed_candle_does_not_count_as_closed(self):
        self.assertEqual(inspect_spot_candles({"status":"JSON_RECEIVED","_payload":[
            [int(close),95,106,100,101,80]]},int(close))["status"],
            "LAST_CLOSED_1H_MISSING_OR_DUPLICATE")
    def test_intx_reachability_not_fresh_quote_parity(self):
        q=inspect_intx_quote({"status":"JSON_RECEIVED","_payload":{"bid":"1"}})
        self.assertEqual(q["status"],"INTX_PUBLIC_PERP_QUOTE_ENDPOINT_REACHABLE_UNVERIFIED")
if __name__=="__main__":
    unittest.main()
