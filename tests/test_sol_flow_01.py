#!/usr/bin/env python3
"""SOL-FLOW-01 offline integrity tests; synthetic candles, no real PnL claims."""
import copy
import importlib.util
from pathlib import Path
import sys
import types
import unittest

sys.modules['backtest_retest_long_v4'] = types.SimpleNamespace(replay_pair=lambda *a,**kw:None)
sys.modules['signal_quality_v7'] = types.SimpleNamespace(evaluate_bos_quality=lambda *a,**kw:None)
sys.modules['v7_paper_comparison'] = types.SimpleNamespace(read_history=lambda path:{})
spec=importlib.util.spec_from_file_location('sol_flow_01',Path(__file__).resolve().parents[1]/'sol_flow_01.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
START=m.START


def bars(n=40, extra_future=0, last_buy=.65):
    result=[]
    for i in range(n+extra_future):
        price=100+i/100
        v=100.0
        tbv=(last_buy if i==n-1 else .55)*v
        result.append({'t':START+i*3600,'o':price,'h':price+1,'l':price-1,
            'c':price+.2,'v':v,'qv':v*(price+.1),'trades':100,
            'tbv':tbv,'tbq':tbv*(price+.1)})
    return result


class FlowTests(unittest.TestCase):
    def test_no_future_leak_when_appending_future_candles(self):
        base=bars()
        closed=base[-1]['t']+3600
        first=m.FlowIndex(base).at(closed)
        extended=m.FlowIndex(bars(40,extra_future=5))
        self.assertEqual(first, extended.at(closed))
        self.assertEqual(first['last1HBuyShare'],.65)
        self.assertEqual(first['featureLastKnownAt'],closed)

    def test_1h_long_short_symmetric(self):
        f=m.FlowIndex(bars()).at(START+40*3600)
        self.assertTrue(m.decision(f,'bullish',m.ARMS[1])[0])
        self.assertFalse(m.decision(f,'bearish',m.ARMS[1])[0])
        self.assertTrue(m.decision(f,'bullish',m.ARMS[2])[0])
        self.assertTrue(m.decision(f,'bullish',m.ARMS[3])[0])
        self.assertTrue(m.decision(f,'bullish',m.ARMS[4])[0])
        self.assertTrue(m.decision(f,'bearish',m.ARMS[0])[0])

    def test_last_bar_taker_is_not_used_before_close(self):
        ix=m.FlowIndex(bars(40))
        at=START+40*3600
        self.assertNotEqual(ix.at(at)['last1HBuyShare'],ix.at(at-3600)['last1HBuyShare'])
        with self.assertRaisesRegex(ValueError,'STALE_OR_INSUFFICIENT'):
            ix.at(at+3600)

    def test_gap_duplicate_and_bad_data_fails_closed(self):
        raw=bars()
        for name,mutation in {
            'gap':lambda x:x.pop(11),
            'duplicate':lambda x:x[11].__setitem__('t',x[10]['t']),
            'missing':lambda x:x[5].pop('tbv'),
            'impossible':lambda x:x[5].__setitem__('tbv',999),
            'badtrades':lambda x:x[5].__setitem__('trades',1.2),
        }.items():
            with self.subTest(case=name):
                x=copy.deepcopy(raw)
                mutation(x)
                with self.assertRaises(ValueError):
                    m.FlowIndex(x)

    def test_aggregate_mismatch_rejected(self):
        rows=bars(48)
        def agg(rows, count):
            return [{'t':z[0]['t'],'o':z[0]['o'],'h':max(b['h'] for b in z),
                     'l':min(b['l'] for b in z),'c':z[-1]['c'],
                     'v':sum(b['v'] for b in z)}
                    for z in (rows[i:i+count] for i in range(0,len(rows),count))]
        four=agg(rows,4)
        day=agg(rows,24)
        self.assertTrue(m.validate_aggregate(rows,four,4))
        self.assertTrue(m.validate_aggregate(rows,day,24))
        four[1]['c']+=.01
        with self.assertRaisesRegex(ValueError,'AGGREGATE_c'):
            m.validate_aggregate(rows,four,4)

    def test_retest_pair_ohlcv_mismatch_fails_closed(self):
        raw=bars()
        ix=m.FlowIndex(raw)
        cb=copy.deepcopy(raw[-1])
        cb['v']=111
        counter={'eligibleOriginalRetestsAssessed':0,'vetoedRetests':0,'reasonCounts':{}}
        gate=m.gate_factory(ix,m.ARMS[1],counter)
        with self.assertRaisesRegex(ValueError,'MISMATCH'):
            gate([cb],{'side':'bullish'},cb)
        self.assertEqual(counter['eligibleOriginalRetestsAssessed'],0)

    def test_retest_gate_accepts_completed_and_vetoes_opposite(self):
        raw=bars()
        ix=m.FlowIndex(raw)
        counter={'eligibleOriginalRetestsAssessed':0,'vetoedRetests':0,'reasonCounts':{}}
        gate=m.gate_factory(ix,m.ARMS[1],counter)
        self.assertEqual(gate(raw,{'side':'bullish'},raw[-1])['passed'],True)
        self.assertEqual(gate(raw,{'side':'bearish'},raw[-1])['passed'],False)
        self.assertEqual(counter['eligibleOriginalRetestsAssessed'],2)
        self.assertEqual(counter['vetoedRetests'],1)

    def test_cost_stress_and_stop_first_is_in_baseline_engine(self):
        report={'status':'PAPER_BACKTEST_NOT_LIVE', 'trades':[
            {'watchKnownUTC':START, 'retestKnownUTC':START+3600,
             'entryOpenUTC':START+3600, 'exitKnownUTC':START+7200,
             'entry':100, 'risk':1, 'netRIllustrative':.82}],
             'alertsCount':1,'qualityGateRejectedBOS':0,
             'qualityGateRejectedRetest':0,'retestExpiredCount':0,
             'unresolvedPositionExcluded':False,'pendingEntryExcluded':False}
        x=m.score(report)
        self.assertEqual(x['trades'],1)
        self.assertAlmostEqual(x['netR25BpsPerSide'],.5,places=6)
        self.assertGreater(x['netR9BpsPerSide'],x['netR25BpsPerSide'])

    def test_reject_forged_manifest_and_reject_bad_arm(self):
        hist={'1hour':{m.PAIR:bars()},'4hour':{m.PAIR:[]},'daily':{m.PAIR:[]}}
        with self.assertRaisesRegex(ValueError,'MANIFEST'):
            m.run(hist,{'source':'Made up', 'checksumsVerified':100})
        with self.assertRaises(ValueError):
            m.decision({},'bullish','unknown')


if __name__=='__main__':
    unittest.main(verbosity=2)
