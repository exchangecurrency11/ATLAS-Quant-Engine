"""Official Binance USD-M public read-only 1H candles: avoid partial/late data."""
import unittest,json
from urllib.parse import parse_qs,urlparse
from v9_official_binance_live_rest_probe import official_hours,run,HOUR
CLOSE=1760000000//HOUR*HOUR


def mock(url):
    params=parse_qs(urlparse(url).query)
    n=int(params["limit"][0])
    result=[]
    for i in range(n):
        start=CLOSE-(n-i)*HOUR
        result.append([start*1000,"100","105","99","101","1000",
                       (start+HOUR)*1000-1,"100000","850","500","50000","0"])
    return result


class OfficialLiveSourceTests(unittest.TestCase):
    def test_three_assets_obtain_causal_source(self):
        r=run(CLOSE,fetch=mock)
        self.assertTrue(r["allThreeOfficialRESTSourceAvailable"])
        self.assertFalse(r["orders"])
        self.assertFalse(r["alertsEnabled"])
        self.assertEqual(len(r["assets"]),3)
        for x in r["assets"].values():
            self.assertEqual(x["bars"],8)
            self.assertEqual(x["sumTradeCountLast8H"],6800)

    def test_future_or_wrong_hour_fails_closed(self):
        def bad(url):
            records=mock(url)
            records[-1][0]+=HOUR*1000
            return records
        with self.assertRaisesRegex(ValueError,"INCONSISTENT"):
            official_hours("BTCUSDT",CLOSE,fetch=bad)

    def test_source_unavailable_is_not_fake_equivalence(self):
        def bad(_):
            raise OSError("restricted")
        r=run(CLOSE,fetch=bad)
        self.assertFalse(r["allThreeOfficialRESTSourceAvailable"])
        self.assertTrue(r["sourceUnavailableDoesNotAuthorizeUnverifiedTX"])
        for x in r["assets"].values():
            self.assertEqual(
              x["status"],"OFFICIAL_BINANCE_REST_UNAVAILABLE_DO_NOT_REPLACE_TRADE_COUNT")

    def test_incomplete_response_fails_closed(self):
        def bad(url):return mock(url)[:-1]
        with self.assertRaisesRegex(ValueError,"MISSING_OR_INCOMPLETE"):
            official_hours("SOLUSDT",CLOSE,fetch=bad)


if __name__=="__main__":
    unittest.main()
