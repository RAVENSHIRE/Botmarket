"""Tests for the factor library and its effectiveness scoring."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from botmarket.domain import factors
from botmarket.domain.venue import Candle


def candles(closes: list[float], *, volumes: list[float] | None = None) -> list[Candle]:
    """Build a candle series from closing prices."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol="TEST",
            timestamp=start + timedelta(hours=i),
            open=Decimal(str(closes[max(0, i - 1)])),
            high=Decimal(str(close * 1.01)),
            low=Decimal(str(close * 0.99)),
            close=Decimal(str(close)),
            volume=Decimal(str(volumes[i] if volumes else 1000)),
        )
        for i, close in enumerate(closes)
    ]


def rising(n: int = 120, step: float = 1.0) -> list[Candle]:
    """A cleanly rising series."""
    return candles([100 + i * step for i in range(n)])


# --- Correlation helpers -------------------------------------------------


def test_correlation_of_a_perfect_line_is_one():
    assert factors.correlation([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)


def test_correlation_of_an_inverse_line_is_minus_one():
    assert factors.correlation([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)


def test_constant_series_correlate_to_zero_rather_than_raising():
    """A flat factor over a quiet window is normal input, not an error."""
    assert factors.correlation([1, 1, 1, 1], [1, 2, 3, 4]) == 0.0


def test_rank_correlation_ignores_outlier_magnitude():
    """Spearman sees the ordering, which is why it survives a fat tail."""
    xs = [1, 2, 3, 4, 1000]
    ys = [1, 2, 3, 4, 5]
    assert factors.rank_correlation(xs, ys) == pytest.approx(1.0)
    assert factors.correlation(xs, ys) < 0.9


# --- Individual factors --------------------------------------------------


def test_momentum_is_positive_in_an_uptrend():
    assert factors.momentum(rising(), 12) > 0


def test_momentum_is_negative_in_a_downtrend():
    falling = candles([200 - i for i in range(120)])
    assert factors.momentum(falling, 12) < 0


def test_factors_return_none_without_enough_history():
    short = rising(5)
    for name in factors.REGISTRY:
        assert factors.compute(name, short) is None


def test_volatility_rises_with_choppiness():
    calm = candles([100 + (i % 2) * 0.1 for i in range(60)])
    wild = candles([100 + (i % 2) * 20 for i in range(60)])
    assert factors.volatility(wild, 24) > factors.volatility(calm, 24)


def test_rsi_is_bounded_and_signed():
    assert factors.rsi(rising(), 14) == pytest.approx(1.0)
    falling = candles([200 - i for i in range(120)])
    assert factors.rsi(falling, 14) == pytest.approx(-1.0)


def test_rsi_of_a_flat_market_is_neutral():
    assert factors.rsi(candles([100] * 60), 14) == 0.0


def test_volume_zscore_flags_a_spike():
    volumes = [1000.0 + (i % 5) * 50 for i in range(59)] + [9000.0]
    series = candles([100 + i * 0.1 for i in range(60)], volumes=volumes)
    assert factors.volume_zscore(series, 24) > 3


def test_volume_spike_against_flat_history_saturates():
    """Zero spread is the most extreme case, not the least — it must not read 0."""
    volumes = [1000.0] * 59 + [9000.0]
    series = candles([100 + i * 0.1 for i in range(60)], volumes=volumes)
    assert factors.volume_zscore(series, 24) == factors.Z_CAP

    quiet = candles([100 + i * 0.1 for i in range(60)], volumes=[1000.0] * 60)
    assert factors.volume_zscore(quiet, 24) == 0.0


def test_volume_zscore_is_capped():
    volumes = [1000.0 + (i % 3) for i in range(59)] + [10_000_000.0]
    series = candles([100 + i * 0.1 for i in range(60)], volumes=volumes)
    assert factors.volume_zscore(series, 24) == factors.Z_CAP


def test_range_position_marks_the_extremes():
    """Each synthetic bar carries a 1% wick, so the close sits just inside ±1."""
    assert factors.range_position(rising(), 24) > 0.8
    falling = candles([200 - i for i in range(120)])
    assert factors.range_position(falling, 24) < -0.8


def test_range_position_hits_the_bound_without_wicks():
    """With high == low == close, the newest bar is exactly the range top."""
    flat_wicks = [
        Candle(
            symbol="TEST",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=i),
            open=Decimal(str(100 + i)),
            high=Decimal(str(100 + i)),
            low=Decimal(str(100 + i)),
            close=Decimal(str(100 + i)),
            volume=Decimal(1000),
        )
        for i in range(60)
    ]
    assert factors.range_position(flat_wicks, 24) == pytest.approx(1.0)


def test_trend_strength_is_positive_when_fast_leads_slow():
    assert factors.trend_strength(rising(), 8, 24) > 0


# --- Registry ------------------------------------------------------------


def test_unknown_factor_names_the_alternatives():
    with pytest.raises(KeyError) as caught:
        factors.get("does_not_exist")
    assert "momentum_12" in str(caught.value)


def test_compute_all_covers_the_registry():
    values = factors.compute_all(rising())
    assert set(values) == set(factors.REGISTRY)


# --- Scoring -------------------------------------------------------------


def test_momentum_scores_well_on_a_trending_series():
    """A trend-follower on a pure trend should show a strong positive IC."""
    score = factors.evaluate("momentum_12", rising(200), horizon=6)
    assert score.samples > factors.MIN_SAMPLES
    assert score.ic > 0.5
    assert score.hit_rate > 0.9
    assert score.is_significant


def test_a_factor_with_no_edge_scores_near_zero():
    """Mean-reverting noise gives momentum nothing to predict."""
    series = candles([100 + (5 if i % 2 else -5) for i in range(200)])
    score = factors.evaluate("momentum_12", series, horizon=6)
    assert abs(score.ic) < 0.5


def test_score_is_empty_rather_than_raising_on_short_history():
    score = factors.evaluate("momentum_48", rising(10), horizon=6)
    assert score.samples == 0
    assert score.ic == 0.0
    assert not score.is_significant


def test_scoring_never_uses_future_information():
    """A factor is paired only with the return that came after it.

    Truncating the series must not change the scores computed on the part that
    remains — if it did, later bars were leaking into earlier ones.
    """
    long_series = rising(200)
    early = factors.evaluate("momentum_12", long_series[:120], horizon=6)
    truncated_again = factors.evaluate("momentum_12", long_series[:120], horizon=6)
    assert early == truncated_again
    assert early.samples == len(long_series[:120]) - 13 - 6


def test_rank_factors_orders_by_absolute_ic():
    scores = factors.rank_factors(rising(200), horizon=6)
    magnitudes = [abs(s.ic) for s in scores]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_icir_is_infinite_only_when_every_bucket_agrees_exactly():
    """A perfectly stable non-zero IC has no spread to divide by."""
    score = factors.evaluate("momentum_12", rising(200), horizon=6)
    assert score.icir != 0.0


# --- Blended signal ------------------------------------------------------


def test_signal_is_positive_in_an_uptrend():
    series = rising(200)
    scores = factors.rank_factors(series, horizon=6)
    assert factors.signal_from_factors(series, scores) > 0


def test_signal_is_zero_when_nothing_is_significant():
    """No edge must read as 'do not trade', not as a weak opinion."""
    series = rising(200)
    scores = [
        factors.FactorScore(
            name=name, horizon=6, samples=100, ic=0.0, rank_ic=0.0, icir=0.0, hit_rate=0.5
        )
        for name in factors.REGISTRY
    ]
    assert factors.signal_from_factors(series, scores) == 0.0


def test_a_negative_ic_factor_votes_the_other_way():
    """A factor that reliably predicted falls is useful, inverted."""
    series = rising(200)
    inverted = [
        factors.FactorScore(
            name="momentum_12", horizon=6, samples=100, ic=-0.8,
            rank_ic=-0.8, icir=-1.0, hit_rate=0.2,
        )
    ]
    upright = [
        factors.FactorScore(
            name="momentum_12", horizon=6, samples=100, ic=0.8,
            rank_ic=0.8, icir=1.0, hit_rate=0.8,
        )
    ]
    assert factors.signal_from_factors(series, inverted) < 0
    assert factors.signal_from_factors(series, upright) > 0


def test_signal_stays_within_bounds():
    series = rising(200)
    scores = factors.rank_factors(series, horizon=6)
    signal = factors.signal_from_factors(series, scores)
    assert -1.0 <= signal <= 1.0
    assert not math.isnan(signal)
