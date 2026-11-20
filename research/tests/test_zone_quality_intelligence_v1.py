import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zone_quality_intelligence_v1 import assess, _group

BASE = dict(symbol='BTCUSDT_PERP.A', side='SHORT', signal_at='2026-11-15T15:05:00Z',
            signal_price=100, signal_candle_low=99, signal_candle_high=102,
            pinned_commit='a'*40, commit_published_at='2026-11-15T15:04:30Z', atr=2)


def fixture(ob=True, fvg=True, liq=True):
    return {'results': [{
        'symbol': 'BTCUSDT_PERP.A', 'interval': '1hour', 'status': 'READY',
        'lastCloseTimeUTC': '2026-11-15T15:00:00Z',
        'candidateOrderBlocks': ([{'side': 'bullish', 'state': 'fresh',
                 'confirmedAt': 1794668400, 'body': {'low': 95, 'high': 96},
                 'volumeRatio': 2.5, 'event': 'BOS', 'fvgConfluence': True}] if ob else []),
        'openFVG': ([{'side': 'bullish', 'state': 'open', 'formedAt': 1794664800,
                      'low': 95.5, 'high': 96.5}] if fvg else []),
        'liquidity': ([{'kind': 'equal_lows', 'secondPivotAt': 1794585600,
                       'level': 95.4}] if liq else []),
    }]}


class QualityTests(unittest.TestCase):
    def test_cluster_and_breakdown(self):
        z = assess(fixture(), **BASE)
        self.assertEqual(z['status'], 'CANDIDATES_UNVALIDATED')
        self.assertEqual(z['rawFeatureCount'], 3)
        self.assertEqual(z['mergedZoneCount'], 1)
        self.assertEqual(z['zones'][0]['typeCount'], 3)
        self.assertEqual(z['zones'][0]['evidenceIndex'], 79)
        self.assertIn('Uncalibrated', z['scoreMeaning'])
        self.assertFalse(z['atrSourceIndependentlyVerified'])

    def test_no_zone_is_explicit(self):
        z = assess(fixture(False, False, False), **BASE)
        self.assertEqual(z['status'], 'NO_ZONE')
        self.assertEqual(z['zones'], [])

    def test_wick_visited_zone_excluded(self):
        z = assess(fixture(), **dict(BASE, signal_candle_low=95.3))
        self.assertEqual(z['rawFeatureCount'], 0)
        self.assertEqual(len(z['excludedWickTouches']), 3)

    def test_unverified_source_after_signal_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'LOOKAHEAD'):
            assess(fixture(), **dict(BASE, commit_published_at='2026-11-15T15:06:00Z'))

    def test_missing_wick_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'required'):
            assess(fixture(), **dict(BASE, signal_candle_low=None))

    def test_invalid_atr_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'atr'):
            assess(fixture(), **dict(BASE, atr=float('nan')))

    def test_source_metadata_only_from_eligible_ob(self):
        f = fixture()
        f['results'][0]['candidateOrderBlocks'][0]['confirmedAt'] = 1794758400
        z = assess(f, **BASE)
        self.assertEqual(z['rawFeatureCount'], 2)
        self.assertNotIn('bos_backed_ob', z['zones'][0]['scoreComponents'])
        self.assertNotIn('ob_volume_ratio_at_least_2', z['zones'][0]['scoreComponents'])

    def test_long_symmetry(self):
        f = fixture()
        o = f['results'][0]
        o['candidateOrderBlocks'][0]['side'] = 'bearish'
        o['candidateOrderBlocks'][0]['body'] = {'low': 104, 'high': 105}
        o['openFVG'][0].update(side='bearish', low=103.5, high=104.5)
        o['liquidity'][0].update(kind='equal_highs', level=104.2)
        z = assess(f, **dict(BASE, side='LONG'))
        self.assertEqual(z['rawFeatureCount'], 3)
        self.assertEqual(z['mergedZoneCount'], 1)
        self.assertGreater(z['zones'][0]['distanceATR'], 0)

    def test_no_transitive_bridge(self):
        def item(a, b):
            return dict(low=a, high=b, interval='1hour', kind='open_FVG',
                        knownAtUTC='2026-11-14T00:00:00Z')
        groups = _group([item(1, 2), item(1.9, 3), item(2.9, 4)], tolerance=0)
        self.assertEqual(sorted(map(len, groups)), [1, 2])

    def test_distance_not_falsely_quality(self):
        f = fixture(ob=False, liq=False)
        f['results'][0]['openFVG'].append({'side':'bullish', 'state':'open',
                 'formedAt':1794664800, 'low':70, 'high':71})
        z = assess(f, **BASE)
        self.assertEqual(z['mergedZoneCount'], 2)
        self.assertEqual(z['zones'][0]['evidenceIndex'], z['zones'][1]['evidenceIndex'])
        self.assertLess(z['zones'][0]['distanceATR'], z['zones'][1]['distanceATR'])

    def test_large_range_penalty(self):
        f = fixture(fvg=False, liq=False)
        ob = f['results'][0]['candidateOrderBlocks'][0]
        ob['body'] = {'low': 85, 'high': 96}
        z = assess(f, **BASE)
        self.assertIn('very_wide_envelope_gt_4_atr', z['zones'][0]['scoreComponents'])


if __name__ == '__main__':
    unittest.main()
