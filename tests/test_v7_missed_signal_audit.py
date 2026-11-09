"""Deterministic, offline rejected BOS counterfactual tests."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v7_missed_signal_audit import (
    evaluate_counterfactual, load_frozen_candidates, evaluate, fmt_report)

T0=int(datetime(2026,11,9,0,tzinfo=timezone.utc).timestamp())
H=3600


def bars(n=85):
    output=[]
    for i in range(n):
        output.append({"t":T0+(i-40)*H, "o":99.0,"h":99.3,"l":98.5,
                       "c":99.0,"v":200.0})
    b=output[40]
    b.update(o=100.0,h=101.0,l=98.5,c=99.1)
    output[41].update(o=99.2,h=99.5,l=98.8,c=98.9)
    output[42].update(o=98.8,h=99.0,l=90.0,c=91.0)
    return output


def candidate(accepted=False):
    return {
        "bosCloseEpoch":T0+H,
        "side":"bearish",
        "brokenLevel":99.5,
        "frozenBosCandle":{"open":100.0,"high":101.0,"low":98.5,"close":99.1},
        "acceptedByV7":accepted,
    }


class V7MissedSignalTests(unittest.TestCase):
    def test_positive_counterfactual_requires_retest_and_closed_bar(self):
        got=evaluate_counterfactual(candidate(),bars())
        self.assertEqual(got["status"],"CLOSED_COUNTERFACTUAL_PAPER")
        self.assertGreater(got["assumedNetR"],0)
        self.assertEqual(got["retestClosedUTC"],
                         datetime.fromtimestamp(T0+2*H,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertEqual(got["entryOpenUTC"],
                         datetime.fromtimestamp(T0+2*H,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertTrue(got["notExecuted"])

    def test_rejected_setup_with_stopped_trade_is_avoided_loss(self):
        data=bars()
        data[42]["h"]=103.0
        outcome=evaluate_counterfactual(candidate(),data)
        self.assertEqual(outcome["status"],"CLOSED_COUNTERFACTUAL_PAPER")
        self.assertLess(outcome["assumedNetR"],0)
        self.assertIn("STOP",outcome["exitReason"])

    def test_no_wick_touch_never_called_missed_winner(self):
        data=bars()
        for i in range(41,len(data)):
            data[i].update(o=98.0,h=98.9,l=85.0,c=87.0)
        outcome=evaluate_counterfactual(candidate(),data)
        self.assertEqual(outcome["status"],"EXPIRED_WITHOUT_V4_RETEST")
        self.assertNotIn("assumedNetR",outcome)

    def test_no_future_closed_entry_cannot_be_scored(self):
        outcome=evaluate_counterfactual(candidate(),bars()[:42])
        self.assertEqual(outcome["status"],"AWAITING_CLOSED_ENTRY_BAR")
        self.assertNotIn("assumedNetR",outcome)

    def test_history_price_revision_fails_closed(self):
        data=bars()
        data[40]["c"]=101.0
        self.assertEqual(evaluate_counterfactual(candidate(),data)["status"],
                         "SOURCE_MISMATCH")

    def test_frozen_gate_measured_at_original_close(self):
        data=bars()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            snaps=root/"snapshots"
            snaps.mkdir()
            b=data[40]
            event_time=b["t"]+H
            event={
                "event":"BOS","direction":"bearish","at":b["t"],
                "confirmedAt":event_time,"brokenLevel":99.5,
            }
            time=datetime.fromtimestamp(event_time,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            snap={
                "status":"VERIFIED_PAPER_OBSERVATION",
                "targetClosed1HUTC":time,
                "observedAtUTC":time,"marketDataCheckedAtUTC":time,
                "marketContext":{
                    "BTCUSDT_PERP.A":{
                        "timeframes":{
                            "1hour":{"candle":{"open":b["o"],"high":b["h"],
                                              "low":b["l"],"close":b["c"]}}
                        },
                        "newStructureEventsAtClose":[event],
                        "bosQualityBreakdown":[{
                            "direction":"bearish","level":99.5,
                            "higherTFalignedWithBOS":False,
                            "momentumAlignedWithBOS":True,
                            "previousHourVolumeIncrease20Pct":True,
                            "gate":{"passed":True,"reasons":[],"features":{
                                "breakATR":0.3,"relativeVolume20":1.9,
                                "ema20ExtensionATR":1.2}},
                        }]
                    },
                    "SOLUSDT_PERP.A":{
                        "timeframes":{"1hour":{"candle":{"open":1,"high":1,"low":1,"close":1}}},
                        "newStructureEventsAtClose":[],
                        "bosQualityBreakdown":[],
                    }
                },
                "results":{
                    "BTCUSDT_PERP.A":{
                        "V4_baseline":{"newWatchAtThisClose":[]},
                        "V7_signal_filter":{"newWatchAtThisClose":[]},
                    },
                    "SOLUSDT_PERP.A":{
                        "V4_baseline":{"newWatchAtThisClose":[]},
                        "V7_signal_filter":{"newWatchAtThisClose":[]},
                    }
                },
            }
            (snaps/"one.json").write_text(json.dumps(snap),encoding="utf-8")
            items,n,issues=load_frozen_candidates(snaps)
            self.assertEqual(n,1)
            self.assertEqual(len(items),1)
            self.assertEqual(issues,{})
            self.assertEqual(items[0]["rejectionFactors"],["4H_DAILY_ALIGNMENT_VETO"])
            source=root/"history.json"
            source.write_text(json.dumps([
                {"symbol":"BTCUSDT_PERP.A","history":data},
                {"symbol":"SOLUSDT_PERP.A","history":data},
            ]),encoding="utf-8")
            result=evaluate(snaps,source,as_of=data[-1]["t"]+H)
            self.assertEqual(result["summary"]["forwardObservedBOS"],1)
            self.assertEqual(result["summary"]["v7RejectedBOS"],1)
            self.assertEqual(result["summary"]["potentiallyMissedPositivePaper"],1)
            self.assertEqual(result["summary"]["avoidedNegativeOrFlatPaper"],0)
            self.assertIn("4H_DAILY_ALIGNMENT_VETO",fmt_report(result))


if __name__=="__main__":
    unittest.main()
