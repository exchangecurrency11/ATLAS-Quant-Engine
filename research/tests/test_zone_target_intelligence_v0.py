import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zone_target_intelligence_v0 import evaluate

SHA = 'a' * 40
BASE = {
    'symbol': 'BTCUSDT_PERP.A', 'side': 'SHORT',
    'signal_at': '2026-11-15T15:05:00Z', 'signal_price': 64740.6,
    'pinned_commit': SHA,
    'commit_published_at': '2026-11-15T15:04:38Z',
}


def fixture():
    return {'results': [{
        'symbol': 'BTCUSDT_PERP.A', 'interval': '1hour', 'status': 'READY',
        'lastCloseTimeUTC': '2026-11-15T15:00:00Z',
        'candidateOrderBlocks': [
            {'side': 'bullish', 'state': 'fresh', 'confirmedAt': 1794668400,
             'body': {'low': 62000, 'high': 62500}},
            {'side': 'bullish', 'state': 'fresh', 'confirmedAt': 1794758400,
             'body': {'low': 58000, 'high': 59000}},
            {'side': 'bearish', 'state': 'fresh', 'confirmedAt': 1794668400,
             'body': {'low': 60000, 'high': 60200}},
        ],
        'openFVG': [
            {'side': 'bullish', 'state': 'open', 'formedAt': 1794664800,
             'low': 61200, 'high': 61400},
            {'side': 'bullish', 'state': 'filled', 'formedAt': 1794664800,
             'low': 60300, 'high': 61000}
        ],
        'liquidity': [
            {'kind': 'equal_lows', 'level': 57894.3, 'secondPivotAt': 1794585600},
        ]
    }]}


class ZoneTests(unittest.TestCase):
    def test_known_before_cutoff_only(self):
        report = evaluate(fixture(), **BASE)
        kinds = [z['kind'] for z in report['candidates']]
        self.assertIn('candidate_OB', kinds)
        self.assertIn('open_FVG', kinds)
        self.assertIn('equal_low_liquidity', kinds)
        self.assertFalse(any(z['low'] == 58000 for z in report['candidates']))
        self.assertFalse(any(z['low'] == 60300 for z in report['candidates']))

    def test_commit_after_signal_is_rejected(self):
        args = dict(BASE, commit_published_at='2026-11-15T16:00:00Z')
        with self.assertRaisesRegex(ValueError, 'LOOKAHEAD'):
            evaluate(fixture(), **args)

    def test_future_closed_candle_is_rejected(self):
        f = fixture()
        f['results'][0]['lastCloseTimeUTC'] = '2026-11-15T16:00:00Z'
        with self.assertRaisesRegex(ValueError, 'LOOKAHEAD'):
            evaluate(f, **BASE)

    def test_unconfirmed_pivot_is_excluded(self):
        f = fixture()
        f['results'][0]['liquidity'].append(
            {'kind': 'equal_lows', 'level': 59001,
             'secondPivotAt': 1794751200})
        report = evaluate(f, **BASE)
        self.assertFalse(any(z['low'] == 59001 for z in report['candidates']))

    def test_straddling_zone_is_not_forward_target(self):
        f = fixture()
        f['results'][0]['candidateOrderBlocks'].append(
            {'side': 'bullish', 'state': 'fresh', 'confirmedAt': 1794668400,
             'body': {'low': 64000, 'high': 65000}})
        report = evaluate(f, **BASE)
        self.assertFalse(any(z['low'] == 64000 for z in report['candidates']))

    def test_missing_symbol_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No matching'):
            evaluate({'results': []}, **BASE)

    def test_invalid_price_rejected(self):
        with self.assertRaisesRegex(ValueError, 'positive'):
            evaluate(fixture(), **dict(BASE, signal_price=float('nan')))



def long_fixture(symbol='BTCUSDT_PERP.A'):
    """Synthetic resistance/supply structure known before the signal cutoff."""
    return {'results': [{
        'symbol': symbol, 'interval': '1hour', 'status': 'READY',
        'lastCloseTimeUTC': '2026-11-15T15:00:00Z',
        'candidateOrderBlocks': [
            {'side': 'bearish', 'state': 'fresh', 'confirmedAt': 1794668400,
             'body': {'low': 66000, 'high': 66500}},
            {'side': 'bearish', 'state': 'retested', 'confirmedAt': 1794668400,
             'body': {'low': 68000, 'high': 68100}},
            {'side': 'bearish', 'state': 'invalidated', 'confirmedAt': 1794668400,
             'body': {'low': 70000, 'high': 71000}},
            {'side': 'bearish', 'state': 'fresh', 'confirmedAt': 1794758400,
             'body': {'low': 72000, 'high': 72500}},
            {'side': 'bullish', 'state': 'fresh', 'confirmedAt': 1794668400,
             'body': {'low': 73000, 'high': 73500}},
            {'side': 'bearish', 'state': 'fresh', 'confirmedAt': 1794668400,
             'body': {'low': 64000, 'high': 65000}},
        ],
        'openFVG': [
            {'side': 'bearish', 'state': 'open', 'formedAt': 1794664800,
             'low': 66600, 'high': 66900},
            {'side': 'bearish', 'state': 'filled', 'formedAt': 1794664800,
             'low': 67500, 'high': 67700},
            {'side': 'bullish', 'state': 'open', 'formedAt': 1794664800,
             'low': 75000, 'high': 75500},
            {'side': 'bearish', 'state': 'open', 'formedAt': 1794754800,
             'low': 76000, 'high': 76300},
        ],
        'liquidity': [
            {'kind': 'equal_highs', 'level': 69000,
             'secondPivotAt': 1794585600},
            {'kind': 'equal_highs', 'level': 74000,
             'secondPivotAt': 1794751200},
            {'kind': 'equal_lows', 'level': 69500,
             'secondPivotAt': 1794585600},
        ],
    }]}


class LongZoneTests(unittest.TestCase):
    def setUp(self):
        self.args = dict(BASE, side='LONG')

    def test_long_produces_only_future_resistance_targets(self):
        report = evaluate(long_fixture(), **self.args)
        self.assertEqual(
            [(z['kind'], z['low']) for z in report['candidates']],
            [('candidate_OB', 66000), ('open_FVG', 66600),
             ('candidate_OB', 68000), ('equal_high_liquidity', 69000)])
        self.assertTrue(all(z['low'] > self.args['signal_price']
                            for z in report['candidates']))
        self.assertEqual([z['distancePct'] for z in report['candidates']],
                         sorted(z['distancePct'] for z in report['candidates']))

    def test_long_ignores_wrong_direction_invalidated_and_filled(self):
        levels = [z['low'] for z in evaluate(long_fixture(), **self.args)['candidates']]
        for forbidden in (64000, 70000, 73000, 67500, 75000):
            self.assertNotIn(forbidden, levels)

    def test_long_excludes_future_ob_fvg_and_unconfirmed_pivot(self):
        levels = [z['low'] for z in evaluate(long_fixture(), **self.args)['candidates']]
        self.assertNotIn(72000, levels)
        self.assertNotIn(76000, levels)
        self.assertNotIn(74000, levels)

    def test_long_rejects_source_commit_after_signal(self):
        late = dict(self.args, commit_published_at='2026-11-15T15:06:00Z')
        with self.assertRaisesRegex(ValueError, 'LOOKAHEAD'):
            evaluate(long_fixture(), **late)

    def test_long_rejects_future_candle(self):
        f = long_fixture()
        f['results'][0]['lastCloseTimeUTC'] = '2026-11-15T16:00:00Z'
        with self.assertRaisesRegex(ValueError, 'LOOKAHEAD'):
            evaluate(f, **self.args)

    def test_sol_long_supported(self):
        a = dict(self.args, symbol='SOLUSDT_PERP.A')
        result = evaluate(long_fixture('SOLUSDT_PERP.A'), **a)
        self.assertEqual(result['signal']['symbol'], 'SOLUSDT_PERP.A')
        self.assertEqual(result['signal']['side'], 'LONG')
        self.assertEqual(len(result['candidates']), 4)

    def test_long_rejects_overlapping_zone_as_forward_target(self):
        levels = [z['low'] for z in evaluate(long_fixture(), **self.args)['candidates']]
        self.assertNotIn(64000, levels)

if __name__ == '__main__':
    unittest.main()
