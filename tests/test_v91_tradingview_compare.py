"""TradingView V9.1 research intake schema, timestamps and fail-closed parity."""
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from v91_tradingview_compare import (
    validate_alert,compare_snapshot,run,summarize,VERSION,HOUR_MS)


END=int(datetime(2026,11,11,16,0,tzinfo=timezone.utc).timestamp())
ENDMS=END*1000
V7CANDLE={"open":100.,"high":101.,"low":99.,"close":100.2}


def valid_tv():
    return {"schema":VERSION,"source":"TradingViewPineV6",
        "exchange":"BINANCE","ticker":"SOLUSDT.P","timeframe":"60",
        "barOpenMs":ENDMS-HOUR_MS,"barCloseMs":ENDMS,
        **V7CANDLE,"volume":100.0,"atr14":1.5,"rsi14":53.0,
        "macdHistogram":0.4,"ema20":100.,"ema50":99.,
        "ema200":95.,"bullBOS":False,"bearBOS":False,
        "chochBull":False,"chochBear":False,
        "sweepHigh":False,"sweepLow":True,
        "fvgBull":True,"fvgBear":False,
        "confirmedSwingHigh":101.3,
        "confirmedSwingLow":98.2,
        "brokenLevel":None,"pivotRightBars":3,
        "confirmed":True,"researchOnly":True,"noTradeAction":True}


def valid_v7():
    return {"status":"VERIFIED_PAPER_OBSERVATION",
        "brokerOrders":False,"observedAtUTC":"2026-11-11T16:19:00Z",
        "targetClosed1HUTC":"2026-11-11T16:00:00Z",
        "inputSHA256":{"1hour":"somesource"},
        "marketContext":{"SOLUSDT_PERP.A":{
            "checkedClosed1HUTC":"2026-11-11T16:00:00Z",
            "timeframes":{"1hour":{"candle":deepcopy(V7CANDLE)}},
            "newStructureEventsAtClose":[],
        }},
        "results":{"SOLUSDT_PERP.A":{"V7_signal_filter":{
            "newWatchAtThisClose":[]}}}
    }


class V91TradingViewTests(unittest.TestCase):
    def test_valid_separate_futures_closed_1h(self):
        self.assertEqual(validate_alert(valid_tv())["ticker"],"SOLUSDT.P")
        r=compare_snapshot(valid_tv(),valid_v7())
        self.assertTrue(r["priceParityWithin1bpEachOHLC"])
        self.assertTrue(r["tvVsV7RawBOSDirectionAgreementAtExactClose"])
        self.assertFalse(r["tvFromActualLiveAlertProven"])
        self.assertFalse(r["automaticLiveEntryFilteringAllowed"])
        self.assertTrue(r["noBrokerOrders"])

    def test_wrong_spot_exchange_and_other_contract_refused(self):
        for name,value in [("exchange","BYBIT"),("ticker","SOLUSDT"),
                           ("ticker","ETHUSDT.P"),("timeframe","240"),
                           ("confirmed",False),("noTradeAction",False)]:
            with self.subTest(name=name,value=value):
                x=valid_tv();x[name]=value
                with self.assertRaises(ValueError):
                    validate_alert(x)

    def test_future_unclosed_or_wrong_ms_bar_refused(self):
        for name,value in [("barCloseMs",ENDMS-5*60*1000),
                           ("barCloseMs",ENDMS+HOUR_MS),
                           ("barOpenMs",ENDMS),
                           ("barOpenMs",ENDMS-HOUR_MS+2000)]:
            with self.subTest(name=name):
                x=valid_tv();x[name]=value
                with self.assertRaisesRegex(ValueError,"COMPLETE_UTC_HOUR"):
                    validate_alert(x)

    def test_invalid_flags_and_choch_refused(self):
        x=valid_tv();x["bullBOS"]="true"
        with self.assertRaisesRegex(ValueError,"NOT_BOOLEAN"):
            validate_alert(x)
        x=valid_tv();x["chochBull"]=True
        with self.assertRaisesRegex(ValueError,"CHOCH_WITHOUT"):
            validate_alert(x)
        x=valid_tv();x["bullBOS"]=True;x["bearBOS"]=True
        with self.assertRaisesRegex(ValueError,"DOUBLE_BOS"):
            validate_alert(x)

    def test_no_future_or_other_hour_v7_join(self):
        x=valid_v7();x["targetClosed1HUTC"]="2026-11-11T17:00:00Z"
        with self.assertRaisesRegex(ValueError,"DIFFERENT_CLOSED_1H"):
            compare_snapshot(valid_tv(),x)
        x=valid_v7();x["observedAtUTC"]="2026-11-11T18:15:00Z"
        with self.assertRaisesRegex(ValueError,"NOT_CAPTURED_IN_HOUR"):
            compare_snapshot(valid_tv(),x)

    def test_untrusted_payload_does_not_turn_into_signal(self):
        x=valid_tv();x["bullBOS"]=True;x["brokenLevel"]=100.1
        v=valid_v7()
        r=compare_snapshot(x,v)
        self.assertFalse(r["tvVsV7RawBOSDirectionAgreementAtExactClose"])
        self.assertEqual(r["v7NewQualifyingBOSWatches"],0)
        self.assertFalse(r["automaticLiveEntryFilteringAllowed"])
        self.assertFalse(r["outcomeOrWinningProbabilityInferred"])

    def test_different_providers_price_1bp_limit(self):
        x=valid_tv();x["close"]=100.3
        # V7 recorded close 100.2; deviation ~10bp
        r=compare_snapshot(x,valid_v7())
        self.assertFalse(r["priceParityWithin1bpEachOHLC"])
        self.assertFalse(r["tvVsV7RawBOSDirectionAgreementAtExactClose"])

    def test_no_duplicate_symbol_hour(self):
        x=compare_snapshot(valid_tv(),valid_v7())
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            summarize([x,x])

    def test_historical_manual_alert_not_falsely_prospective(self):
        with tempfile.TemporaryDirectory() as d:
            v7dir=Path(d)
            filename=v7dir/"2026-11-11T16-00Z.json"
            filename.write_text(json.dumps(valid_v7()))
            report=run(valid_tv(),str(v7dir))
            self.assertEqual(report["count"],1)
            self.assertEqual(report["OHLCParityPass"],1)
            self.assertTrue(report["noConfirmedTradingViewWebhookConnection"])
            self.assertTrue(report["retrospectiveUserProvidedAlertsNotProspective"])
            self.assertTrue(report["promotionBlocked"])

    def test_refuse_missing_original_snapshot_no_invented_event(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"NO_BACKFILL"):
                run(valid_tv(),d)


if __name__=="__main__":
    unittest.main()
