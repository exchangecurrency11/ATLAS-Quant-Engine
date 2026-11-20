#!/usr/bin/env python3
"""Research-only, non-calibrated zone evidence scoring for ATLAS.

Consumes a *time-pinned* market_structure_data.json plus a fully specified
signal candle. No external I/O, trading, GitHub writes, or live alerts.

Scoring is an explicitly frozen heuristic research INDEX, not a probability
of reversal, profit estimate or validated predictive ranking.
"""
import argparse
import json
import math
from pathlib import Path

from zone_target_intelligence_v0 import evaluate, utc_seconds

SCORE_VERSION = 'ZQI-V1-PRECALIBRATION-20261120'
INTERVAL_PRIORITY = {'1hour': 0, '4hour': 1, 'daily': 2}


def _finite_positive(x):
    return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def _near(a, b):
    return math.isclose(a, b, abs_tol=1e-6, rel_tol=1e-10)


def _ob_details(structure, item, symbol, side):
    """Enrich ONLY an already eligible v0 candidate, never reselect a raw OB."""
    if item['kind'] != 'candidate_OB':
        return {}
    wanted = 'bullish' if side == 'SHORT' else 'bearish'
    t = utc_seconds(item['knownAtUTC'])
    for result in structure['results']:
        if result.get('symbol') != symbol or result.get('interval') != item['interval']:
            continue
        for ob in result.get('candidateOrderBlocks', []):
            body = ob.get('body', {})
            if (ob.get('side') == wanted and ob.get('state') == item['stateAtCutoff']
                and _finite_positive(ob.get('confirmedAt')) and _near(ob['confirmedAt'], t)
                and _finite_positive(body.get('low')) and _finite_positive(body.get('high'))
                and _near(body['low'], item['low']) and _near(body['high'], item['high'])):
                volume = ob.get('volumeRatio')
                return {'obEvent': ob.get('event') if ob.get('event') in ('BOS', 'CHoCH') else None,
                        'obVolumeRatio': round(float(volume), 4) if _finite_positive(volume) else None,
                        'obFVGConfluence': ob.get('fvgConfluence') is True}
    return {'obMetadataUnavailable': True}


def _close(a, b, tolerance):
    """Pairwise gap <= tolerance: avoid transitive chaining through a wide zone."""
    return max(a['low'] - b['high'], b['low'] - a['high'], 0) <= tolerance + 1e-9


def _group(items, tolerance):
    # Deterministic order independent of source list order.
    ordered = sorted(items, key=lambda x: (x['low'], x['high'],
                                           INTERVAL_PRIORITY[x['interval']], x['kind'],
                                           x['knownAtUTC']))
    groups = []
    for candidate in ordered:
        # Merge only when the incoming feature is close to EVERY member.
        eligible = [g for g in groups if all(_close(candidate, x, tolerance) for x in g)]
        if eligible:
            # Prefer the smallest geometric envelope if multiple groups qualify.
            eligible.sort(key=lambda g: (max(x['high'] for x in g) - min(x['low'] for x in g),
                                         min(x['low'] for x in g)))
            eligible[0].append(candidate)
        else:
            groups.append([candidate])
    return groups


def _score(group, atr):
    kinds = {x['kind'] for x in group}
    frames = {x['interval'] for x in group}
    obs = [x for x in group if x['kind'] == 'candidate_OB']
    details = [x.get('obDetails', {}) for x in obs]
    ratios = [x['obVolumeRatio'] for x in details if x.get('obVolumeRatio') is not None]
    width = (max(x['high'] for x in group) - min(x['low'] for x in group)) / atr
    points = {'as_of_eligible': 35}
    if len(kinds) >= 2:
        points['feature_type_diversity'] = 12
    if len(kinds) == 3:
        points['three_feature_types'] = 6
    if len(frames) >= 2:
        points['multiple_timeframes'] = 12
    if len(frames) == 3:
        points['three_timeframes'] = 6
    if ratios:
        peak = max(ratios)
        if peak >= 2.0:
            points['ob_volume_ratio_at_least_2'] = 10
        elif peak >= 1.3:
            points['ob_volume_ratio_at_least_1_3'] = 5
    if any(x['stateAtCutoff'] == 'fresh' for x in obs):
        points['fresh_ob'] = 6
    elif obs and all(x['stateAtCutoff'] == 'retested' for x in obs):
        points['retested_ob_only'] = -5
    if any(d.get('obEvent') == 'BOS' for d in details):
        points['bos_backed_ob'] = 5
    if any(d.get('obFVGConfluence') is True for d in details):
        points['ob_recorded_fvg_confluence'] = 5
    if width > 2:
        points['wide_envelope_gt_2_atr'] = -12
    if width > 4:
        points['very_wide_envelope_gt_4_atr'] = -12
    return max(0, min(100, sum(points.values()))), points, round(width, 4)


def assess(structure, *, symbol, side, signal_at, signal_price,
           pinned_commit, commit_published_at, atr,
           signal_candle_low, signal_candle_high, pivot_span=3):
    """Rank eligible structural zones by uncalibrated evidence, not distance.

    A numeric ATR is mandatory ONLY to set geometry tolerance/width. This
    function does not validate the ATR's own candle provenance: the calling
    forensic pipeline must independently pin its earlier market-data source.
    """
    if not _finite_positive(atr):
        raise ValueError('atr must be a positive finite number')
    if signal_candle_low is None or signal_candle_high is None:
        raise ValueError('Fully observed signal candle high and low are required')
    base = evaluate(structure, symbol=symbol, side=side, signal_at=signal_at,
                    signal_price=signal_price, pinned_commit=pinned_commit,
                    commit_published_at=commit_published_at, pivot_span=pivot_span,
                    signal_candle_low=signal_candle_low,
                    signal_candle_high=signal_candle_high)
    if base['signalCandleEligibility'] != 'GATED_USING_CLOSED_CANDLE_HIGH_LOW':
        raise ValueError('Wick eligibility was not checked')

    raw = []
    for x in base['candidates']:
        y = dict(x)
        y['obDetails'] = _ob_details(structure, y, symbol, side)
        raw.append(y)
    clusters = _group(raw, tolerance=0.10 * atr)
    scored = []
    for group in clusters:
        points, components, width_atr = _score(group, atr)
        lo, hi = min(x['low'] for x in group), max(x['high'] for x in group)
        entry_edge = hi if side == 'SHORT' else lo
        distance_atr = (signal_price - entry_edge) / atr if side == 'SHORT' else (entry_edge - signal_price) / atr
        scored.append({'range': [lo, hi], 'typeCount': len({x['kind'] for x in group}),
                       'timeframes': sorted({x['interval'] for x in group},
                                            key=lambda k: INTERVAL_PRIORITY[k]),
                       'types': sorted({x['kind'] for x in group}),
                       'evidenceIndex': points, 'scoreComponents': components,
                       'envelopeWidthATR': width_atr,
                       'distanceATR': round(distance_atr, 4),
                       'sourceFeatureCount': len(group),
                       'sourceFeatures': group})
    scored.sort(key=lambda x: (-x['evidenceIndex'], x['distanceATR'], x['range'][0]))
    for i, zone in enumerate(scored, 1):
        zone['researchZoneId'] = f'Z{i:03d}'

    return {'mode': 'RESEARCH_ONLY_NO_ORDERS_NO_ALERTS', 'scoreVersion': SCORE_VERSION,
            'status': 'NO_ZONE' if not scored else 'CANDIDATES_UNVALIDATED',
            'signal': base['signal'], 'provenance': base['provenance'],
            'atrAssumed': atr,
            'atrSourceIndependentlyVerified': False,
            'rawFeatureCount': len(raw), 'mergedZoneCount': len(scored),
            'excludedWickTouches': base['alreadyTouchedDuringSignalCandle'],
            'zones': scored,
            'scoreMeaning': 'Uncalibrated structural-evidence points; NOT probability, reversal expectation, or financial return.',
            'missingEvidence': ['OB source volume and FVG overlap are heuristic',
                                'ATR market-data as-of proof remains external',
                                'no out-of-sample validation',
                                'no exchange order-book or fill verification']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--structure', required=True, type=Path)
    p.add_argument('--symbol', required=True)
    p.add_argument('--side', required=True, choices=('LONG', 'SHORT'))
    p.add_argument('--signal-at', required=True)
    p.add_argument('--signal-price', required=True, type=float)
    p.add_argument('--signal-candle-low', required=True, type=float)
    p.add_argument('--signal-candle-high', required=True, type=float)
    p.add_argument('--pinned-commit', required=True)
    p.add_argument('--commit-published-at', required=True)
    p.add_argument('--atr', required=True, type=float)
    p.add_argument('--pivot-span', type=int, default=3)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    data = json.loads(a.structure.read_text(encoding='utf-8'))
    result = assess(data, symbol=a.symbol, side=a.side, signal_at=a.signal_at,
                    signal_price=a.signal_price, pinned_commit=a.pinned_commit,
                    commit_published_at=a.commit_published_at, atr=a.atr,
                    signal_candle_low=a.signal_candle_low,
                    signal_candle_high=a.signal_candle_high,
                    pivot_span=a.pivot_span)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if a.output:
        a.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
