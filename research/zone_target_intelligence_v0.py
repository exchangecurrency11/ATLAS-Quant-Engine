#!/usr/bin/env python3
"""Research-only, as-of audit of BTC/SOL price reaction candidates.

Reads a historical, commit-pinned market_structure_data.json from ATLAS.
Does not retrieve data, predict trades, or modify trading/notification systems.
"""
import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

INTERVAL_SECONDS = {'1hour': 3600, '4hour': 14400, 'daily': 86400}
SYMBOLS = {'BTCUSDT_PERP.A', 'SOLUSDT_PERP.A'}
SHA_RE = re.compile(r'^[a-fA-F0-9]{40}$')


def utc_seconds(value):
    """Accept only explicit UTC ISO timestamps (not local or floating time)."""
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('Timestamp must be UTC ISO-8601 ending in Z')
    try:
        parsed = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError as exc:
        raise ValueError('Invalid UTC timestamp') from exc
    return parsed.timestamp()


def _valid_range(low, high):
    return (all(isinstance(x, (int, float)) and not isinstance(x, bool)
                and math.isfinite(x) for x in (low, high))
            and 0 < low <= high)


def evaluate(structure, *, symbol, side, signal_at, signal_price,
             pinned_commit, commit_published_at, pivot_span=3,
             signal_candle_low=None, signal_candle_high=None):
    """Return candidate levels knowable by signal_at, without future candles.

    Time guard is two-fold: the immutable GitHub commit must have existed before
    the signal, and each underlying zone/pivot must have been confirmed before it.
    The SHA/publication time are caller-supplied provenance; verify them on GitHub.
    """
    if symbol not in SYMBOLS or side not in ('SHORT', 'LONG'):
        raise ValueError('Unsupported symbol or side')
    if not _valid_range(signal_price, signal_price):
        raise ValueError('signal_price must be positive and finite')
    if not isinstance(pinned_commit, str) or not SHA_RE.fullmatch(pinned_commit):
        raise ValueError('A full 40-character pinned commit SHA is required')
    if not isinstance(pivot_span, int) or not 2 <= pivot_span <= 10:
        raise ValueError('pivot_span must be between 2 and 10')
    if (signal_candle_low is None) != (signal_candle_high is None):
        raise ValueError('Provide both signal candle low and high, or neither')
    signal_bar_checked = signal_candle_low is not None
    if signal_bar_checked and (not _valid_range(signal_candle_low, signal_candle_high)
                               or not signal_candle_low <= signal_price <= signal_candle_high):
        raise ValueError('Invalid signal candle OHLC range for closing price')
    cutoff = utc_seconds(signal_at)
    published = utc_seconds(commit_published_at)
    if published > cutoff:
        raise ValueError('LOOKAHEAD: source commit was published after the proposed signal time')
    if not isinstance(structure, dict) or not isinstance(structure.get('results'), list):
        raise ValueError('Expected market_structure_data.json results list')
    wanted = 'bullish' if side == 'SHORT' else 'bearish'
    liquidity_kind = 'equal_lows' if side == 'SHORT' else 'equal_highs'
    candidates = []
    already_touched = []
    inspected = []
    unique_intervals = set()
    for item in structure['results']:
        if item.get('symbol') != symbol:
            continue
        interval = item.get('interval')
        if interval not in INTERVAL_SECONDS:
            continue
        if interval in unique_intervals:
            raise ValueError('Duplicate symbol/timeframe in source')
        unique_intervals.add(interval)
        bar_sec = INTERVAL_SECONDS[interval]
        last_close = item.get('lastCloseTimeUTC')
        if last_close is None or utc_seconds(last_close) > cutoff:
            raise ValueError('LOOKAHEAD: source contains candle closed after the signal')
        source_last_close = utc_seconds(last_close)
        if item.get('status') != 'READY':
            inspected.append({'interval': interval, 'status': 'NOT_READY'})
            continue
        inspected.append({'interval': interval, 'lastCloseTimeUTC': last_close,
                          'status': 'READY'})

        def add_candidate(kind, low, high, known_at, source, state):
            if not _valid_range(low, high) or known_at > min(cutoff, source_last_close):
                return
            # Ahead-of-price zones only; no retroactive targets already touched.
            if side == 'SHORT' and high >= signal_price:
                return
            if side == 'LONG' and low <= signal_price:
                return
            if signal_bar_checked and ((side == 'SHORT' and signal_candle_low <= high)
                                       or (side == 'LONG' and signal_candle_high >= low)):
                already_touched.append({'interval': interval, 'kind': kind,
                                        'low': low, 'high': high,
                                        'reason': 'TOUCHED_DURING_SIGNAL_CANDLE'})
                return
            distance = ((signal_price - high) if side == 'SHORT'
                        else (low - signal_price)) / signal_price * 100
            candidates.append({'interval': interval, 'kind': kind,
                               'low': low, 'high': high,
                               'distancePct': round(distance, 4),
                               'knownAtUTC': datetime.fromtimestamp(
                                   known_at, timezone.utc).isoformat().replace('+00:00', 'Z'),
                               'source': source, 'stateAtCutoff': state})

        for ob in item.get('candidateOrderBlocks', []):
            if ob.get('side') != wanted or ob.get('state') not in ('fresh', 'retested'):
                continue
            body = ob.get('body', {})
            known = ob.get('confirmedAt')
            if not isinstance(known, (int, float)) or not math.isfinite(known):
                continue
            add_candidate('candidate_OB', body.get('low'), body.get('high'),
                          known, 'OHLCV heuristic; no confirmed institutional order',
                          ob['state'])

        for gap in item.get('openFVG', []):
            if gap.get('side') != wanted or gap.get('state') != 'open':
                continue
            formed_at = gap.get('formedAt')
            if not isinstance(formed_at, (int, float)) or not math.isfinite(formed_at):
                continue
            add_candidate('open_FVG', gap.get('low'), gap.get('high'),
                          formed_at + bar_sec, 'three-candle OHLCV gap', 'open')

        for liq in item.get('liquidity', []):
            if liq.get('kind') != liquidity_kind:
                continue
            pivot_at = liq.get('secondPivotAt')
            level = liq.get('level')
            if not isinstance(pivot_at, (int, float)) or not math.isfinite(pivot_at):
                continue
            # market_structure.py confirms a center pivot only after its
            # pivot_span following candles close: t + (pivot_span+1)*bar_sec.
            known = pivot_at + (pivot_span + 1) * bar_sec
            add_candidate('equal_low_liquidity' if side == 'SHORT'
                          else 'equal_high_liquidity', level, level,
                          known, 'chart pivot heuristic; NOT observed resting orders',
                          'unverified_liquidity')

    if not inspected:
        raise ValueError('No matching symbol/timeframe found')
    candidates.sort(key=lambda x: (x['distancePct'], x['interval'], x['kind']))
    return {'mode': 'RESEARCH_ONLY_NO_ORDERS_NO_ALERTS',
            'provenance': {'structureCommit': pinned_commit,
                           'commitPublishedAtUTC': commit_published_at,
                           'provenanceNeedsIndependentGitHubVerification': True},
            'signal': {'symbol': symbol, 'side': side,
                       'signalAtUTC': signal_at, 'signalPrice': signal_price,
                       'signalTimestampExternallyVerified': False},
            'inspected': inspected, 'candidates': candidates,
            'alreadyTouchedDuringSignalCandle': already_touched,
            'signalCandleEligibility': ('GATED_USING_CLOSED_CANDLE_HIGH_LOW'
                                        if signal_bar_checked else 'NOT_CHECKED'),
            'notEvidenceOf': ['future performance', 'institutional orders',
                              'trade entry', 'profit-taking superiority'],
            'warning': 'Candidates are retrospective as-of features, NOT validated forecasts.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--structure', required=True, type=Path)
    p.add_argument('--symbol', default='BTCUSDT_PERP.A', choices=sorted(SYMBOLS))
    p.add_argument('--side', required=True, choices=['SHORT', 'LONG'])
    p.add_argument('--signal-at', required=True)
    p.add_argument('--signal-price', required=True, type=float)
    p.add_argument('--signal-candle-low', type=float)
    p.add_argument('--signal-candle-high', type=float)
    p.add_argument('--pinned-commit', required=True)
    p.add_argument('--commit-published-at', required=True)
    p.add_argument('--pivot-span', type=int, default=3)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    with args.structure.open(encoding='utf-8') as f:
        structure = json.load(f)
    report = evaluate(structure, symbol=args.symbol, side=args.side,
                      signal_at=args.signal_at, signal_price=args.signal_price,
                      pinned_commit=args.pinned_commit,
                      commit_published_at=args.commit_published_at,
                      pivot_span=args.pivot_span,
                      signal_candle_low=args.signal_candle_low,
                      signal_candle_high=args.signal_candle_high)
    result = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result, end='')


if __name__ == '__main__':
    main()
