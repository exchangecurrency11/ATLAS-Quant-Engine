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


if __name__ == '__main__':
    unittest.main()
