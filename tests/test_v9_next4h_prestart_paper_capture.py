"""V9 before-start paper forecast: no future data, never live order."""
from datetime import datetime, timezone
import copy
import json
import math
import unittest
from v9_next4h_prestart_paper_capture import (
   next_boundary,check_clock,get_group,aggregate_closed_four,snapshot,
   PAPER_STATUS,HOUR,FOUR,DAY,EXCHANGE_SYMBOLS)
from v9_next_4h_color_research import features_at,prepare


TARGET=int(datetime(2026,11,11,tzinfo=timezone.utc).timestamp())
NOW=TARGET-600
SYMS=("BTCUSDT","ETHUSDT","SOLUSDT")


def synthetic_sources():
    low=TARGET-1000*HOUR
    daybase=(TARGET//DAY-330)*DAY
    records={"1hour":{},"daily":{}}
    for symbol,multi in (("BTCUSDT",700.),("ETHUSDT",20.),("SOLUSDT",1.)):
        hours=[]
        for j in range(1000):
            t=low+j*HOUR
            p=100.0+j*.015+math.sin(j/6)*.2
            o=p*multi
            c=(p+math.cos(j/4)*.015)*multi
            v=100+j%7
            h=max(o,c)+.3*multi
            l=min(o,c)-.3*multi
            hours.append({"t":t,"o":o,"h":h,"l":l,"c":c,"v":v,
                          "bv":v*(.5+.08*math.sin(j/15)),
                          "tx":100+j%13,"btx":45+j%6})
        days=[]
        for j in range(330):
            t=daybase+j*DAY
            p=(110+j*.03)*multi
            days.append({"t":t,"o":p,"h":p+2*multi,
                         "l":p-2*multi,"c":p+math.sin(j/7)*multi,
                         "v":2400.})
        last_complete=days[-2]
        hrs=[h for h in hours if last_complete["t"]<=h["t"]<last_complete["t"]+DAY]
        assert len(hrs)==24
        last_complete["c"]=hrs[-1]["c"]
        last_complete["v"]=sum(h["v"] for h in hrs)
        last_complete["h"]=max(last_complete["o"],last_complete["c"],
                               max(h["h"] for h in hrs))+multi
        last_complete["l"]=min(last_complete["o"],last_complete["c"],
                               min(h["l"] for h in hrs))-multi
        records["1hour"][symbol]=hours
        records["daily"][symbol]=days
    return records


def fake_fetch(records):
    def fetch(tf,params):
        return json.dumps([
           {"symbol":EXCHANGE_SYMBOLS[s],"history":records[tf][s]}
           for s in SYMS]).encode()
    return fetch


def fake_models():
    # Feature vector 30 per asset + 4 deterministic clock features
    n=94
    return {"status":"FROZEN_SHADOW_PAPER_MODELS_NOT_PRODUCTION",
            "noProspectiveTrackRecordYet":True,
            "symbols":{s:{"featureCount":n,
                          "logisticIntercept":0.15 if s=="SOLUSDT" else -.15,
                          "logisticCoefficients":[0.0]*n,
                          "scalerMean":[0.0]*n,
                          "scalerScale":[1.0]*n,
                          "trainingLabelsSHA256":"f"*64}
                       for s in SYMS}}


class ProspectiveV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=synthetic_sources()
        cls.models=fake_models()

    def test_clock_strictly_before_future_open(self):
        self.assertEqual(next_boundary(NOW),TARGET)
        self.assertEqual(check_clock(NOW),TARGET)
        for bad in (TARGET-1600,TARGET-60,TARGET+60):
            with self.assertRaisesRegex(ValueError,"NOT_WITHIN_PRE_START"):
                check_clock(bad)

    def test_api_discards_partial_final_hour(self):
        result,_=get_group("1hour",TARGET-1000*HOUR,NOW,"mock",
                           fetch=fake_fetch(self.source))
        for s in SYMS:
            self.assertEqual(len(result[s]),999)
            self.assertEqual(result[s][-1]["t"]+HOUR,TARGET-HOUR)
            self.assertEqual(result[s][-1]["trades"],self.source["1hour"][s][-2]["tx"])

    def test_prospective_complete_snapshot_and_no_next_open(self):
        out=snapshot(NOW,self.models,"mock",fetch=fake_fetch(self.source))
        self.assertEqual(out["status"],PAPER_STATUS)
        self.assertEqual(out["minutesBeforeStart"],10)
        self.assertTrue(out["noTargetOpenKnown"])
        self.assertFalse(out["brokerOrders"])
        self.assertFalse(out["productionModified"])
        self.assertFalse(out["liveTradeOrAlertsActivated"])
        self.assertEqual(set(out["assetForecasts"]),set(SYMS))
        for s,x in out["assetForecasts"].items():
            self.assertTrue(x["predictionOnlyNotAnOrder"])
            self.assertEqual(x["featuresReplayed"],94)
            self.assertLess(x["lastFullyClosed1HEndUTC"],out["target4HStartUTC"])

    def test_unknown_target_and_unclosed_final_hour_do_not_repaint(self):
        a=snapshot(NOW,self.models,"mock",fetch=fake_fetch(self.source))
        future=copy.deepcopy(self.source)
        for sym in SYMS:
            bar=future["1hour"][sym][-1]
            bar["c"]=bar["o"]*1.1
            bar["h"]=max(bar["h"],bar["c"])
            bar["v"]*=10
            bar["bv"]*=10
            bar["tx"]*=10
        b=snapshot(NOW,self.models,"mock",fetch=fake_fetch(future))
        for sym in SYMS:
            self.assertEqual(a["assetForecasts"][sym]["direction"],
                             b["assetForecasts"][sym]["direction"])
            self.assertEqual(a["assetForecasts"][sym]["pGreenUNCALIBRATED"],
                             b["assetForecasts"][sym]["pGreenUNCALIBRATED"])

    def test_missing_1h_cannot_be_filled_or_ignored(self):
        bad=copy.deepcopy(self.source)
        del bad["1hour"]["SOLUSDT"][-20]
        with self.assertRaisesRegex(ValueError,"1H_INCOMPLETE_STALE_OR_MISSING"):
            snapshot(NOW,self.models,"mock",fetch=fake_fetch(bad))

    def test_wrong_frozen_features_cannot_generate_forecast(self):
        bad=copy.deepcopy(self.models)
        bad["symbols"]["SOLUSDT"]["featureCount"]=90
        with self.assertRaisesRegex(ValueError,"MODEL_SCHEMA_MISMATCH"):
            snapshot(NOW,bad,"mock",fetch=fake_fetch(self.source))

    def test_no_prospective_model_can_use_unknown_target_candle(self):
        from v9_next_4h_color_research import prepare,features_at
        hour,_=get_group("1hour",TARGET-1000*HOUR,NOW,"mock",
                          fetch=fake_fetch(self.source))
        days,_=get_group("daily",(TARGET//DAY-330)*DAY,NOW,"mock",
                          fetch=fake_fetch(self.source))
        raw={s:{"one":hour[s],
                "four":aggregate_closed_four(hour[s][:-3]),
                "daily":days[s]} for s in SYMS}
        data=prepare(raw)
        x=features_at("BTCUSDT",data,len(data["BTCUSDT"]["four"])+1,
                      target_start_t=TARGET)
        self.assertEqual(len(x),30)
        with self.assertRaisesRegex(ValueError,"PROSPECTIVE_LAST_COMPLETE"):
            features_at("BTCUSDT",data,len(data["BTCUSDT"]["four"]),
                        target_start_t=TARGET)


if __name__=="__main__":
    unittest.main()
