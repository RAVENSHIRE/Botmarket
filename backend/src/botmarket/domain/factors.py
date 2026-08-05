"""Quantitative factors and their effectiveness scoring.

A *factor* turns a window of price history into one number that is supposed to
say something about what happens next. On its own that is just an indicator;
what makes it a factor is that its predictive power is measured rather than
assumed.

Every factor here is a pure function over :class:`~botmarket.domain.venue.Candle`
bars, registered in :data:`REGISTRY` under a name. Adding one is a function plus
a registry entry — nothing else in the system needs to know.

Scoring uses the standard quant vocabulary:

* **IC** (information coefficient) — Pearson correlation between the factor's
  value at each bar and the return over the following ``horizon`` bars. It
  answers "when this factor was high, did price rise?"
* **Rank IC** — the same thing on ranks (Spearman). It is the more honest of the
  two for factors with fat tails, because one outlier cannot manufacture a
  correlation.
* **ICIR** — mean IC divided by its standard deviation across sub-samples. A
  factor with a small but *stable* edge beats one with a large erratic edge, and
  ICIR is what tells them apart.
* **Hit rate** — how often the factor's sign matched the forward return's sign.

An IC near zero means the factor knows nothing. Negative IC is not useless — it
is a signal to trade the other way — which is why the sign is preserved
everywhere rather than reported as a magnitude.

This is the seam the rest of the factor library grows into: the registry, the
scoring, and the shape of a factor are all here, so adding the next fifty is
additive.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from botmarket.domain.venue import Candle

#: Minimum bars before a score means anything. Below this the correlation is
#: dominated by noise and reporting it would be misleading.
MIN_SAMPLES = 20

#: Ceiling on any z-score-style factor. Keeps a degenerate window from emitting
#: an unbounded value that would swamp every other factor in a blend.
Z_CAP = 10.0


@dataclass(frozen=True)
class Factor:
    """A named, scored signal over price history.

    Attributes:
        name: Registry key, e.g. ``momentum_12``.
        category: Grouping for display — momentum, volatility, volume, trend.
        description: What the number means, in one line.
        lookback: Bars required before the factor produces a value.
        compute: The pure function itself.
    """

    name: str
    category: str
    description: str
    lookback: int
    compute: Callable[[Sequence[Candle]], float | None]


@dataclass(frozen=True)
class FactorScore:
    """How well a factor predicted forward returns over a sample.

    Attributes:
        samples: Number of (factor, forward return) pairs scored.
        ic: Pearson correlation with the forward return.
        rank_ic: Spearman correlation with the forward return.
        icir: Mean IC over sub-samples divided by its standard deviation.
        hit_rate: Fraction of bars where the signs agreed.
    """

    name: str
    horizon: int
    samples: int
    ic: float
    rank_ic: float
    icir: float
    hit_rate: float

    @property
    def is_significant(self) -> bool:
        """Whether the sample is large enough and the edge stable enough to act on.

        The thresholds are the conventional rules of thumb, not a proof: |IC|
        above 0.03 is a real if modest edge, and |ICIR| above 0.3 says it
        persisted rather than arriving in one lucky stretch.
        """
        return self.samples >= MIN_SAMPLES and abs(self.ic) >= 0.03 and abs(self.icir) >= 0.3


# --- Helpers -------------------------------------------------------------


def _closes(candles: Sequence[Candle]) -> list[float]:
    """Return closing prices as floats.

    Factor maths is statistical rather than monetary, so ``float`` is the right
    type here — unlike balances and order sizes, which stay ``Decimal``.
    """
    return [float(c.close) for c in candles]


def _returns(values: Sequence[float]) -> list[float]:
    """Return simple period-over-period returns."""
    return [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] != 0
    ]


def _mean(values: Sequence[float]) -> float:
    """Return the arithmetic mean, or ``0.0`` for an empty sequence."""
    return sum(values) / len(values) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    """Return the population standard deviation."""
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def _ranks(values: Sequence[float]) -> list[float]:
    """Return average ranks, so ties do not bias the rank correlation."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Return the Pearson correlation of two equal-length series.

    Returns ``0.0`` when either series is constant — an undefined correlation
    reported as "no relationship" rather than raising, because a flat factor
    over a quiet window is normal input, not an error.
    """
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return cov / (dx * dy)


def rank_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Return the Spearman correlation of two equal-length series."""
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    return correlation(_ranks(xs), _ranks(ys))


# --- The factors ---------------------------------------------------------


def momentum(candles: Sequence[Candle], window: int = 12) -> float | None:
    """Return the simple return over the last ``window`` bars."""
    closes = _closes(candles)
    if len(closes) <= window or closes[-window - 1] == 0:
        return None
    return (closes[-1] - closes[-window - 1]) / closes[-window - 1]


def volatility(candles: Sequence[Candle], window: int = 24) -> float | None:
    """Return the standard deviation of returns over ``window`` bars."""
    closes = _closes(candles)
    if len(closes) <= window:
        return None
    return _stdev(_returns(closes[-window - 1 :]))


def rsi(candles: Sequence[Candle], window: int = 14) -> float | None:
    """Return the Relative Strength Index, scaled to ``[-1, 1]``.

    The conventional 0–100 scale is re-centred so that zero means neutral,
    which keeps the sign meaningful for correlation against returns — the whole
    library reads the same way as a result.
    """
    closes = _closes(candles)
    if len(closes) <= window:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - window, len(closes))]
    gains = _mean([max(c, 0.0) for c in changes])
    losses = _mean([abs(min(c, 0.0)) for c in changes])
    if gains + losses == 0:
        return 0.0
    # (gains - losses) / (gains + losses) is algebraically the standard RSI
    # mapped from [0, 100] onto [-1, 1].
    return (gains - losses) / (gains + losses)


def volume_zscore(candles: Sequence[Candle], window: int = 24) -> float | None:
    """Return how unusual the latest bar's volume is, in standard deviations.

    A perfectly flat history has zero spread, which would divide by zero. That
    case is not "nothing unusual" — a departure from a constant is the *most*
    extreme reading possible — so it saturates at :data:`Z_CAP` with the sign of
    the move, and only a bar that matches the constant reads as zero.

    The result is capped either way: an unbounded z-score would otherwise
    dominate any blend it takes part in.
    """
    if len(candles) <= window:
        return None
    volumes = [float(c.volume) for c in candles[-window - 1 :]]
    history, latest = volumes[:-1], volumes[-1]
    average = _mean(history)
    spread = _stdev(history)

    if spread == 0:
        if latest == average:
            return 0.0
        return math.copysign(Z_CAP, latest - average)

    return max(-Z_CAP, min(Z_CAP, (latest - average) / spread))


def trend_strength(candles: Sequence[Candle], fast: int = 8, slow: int = 24) -> float | None:
    """Return the gap between a fast and slow moving average, as a fraction."""
    closes = _closes(candles)
    if len(closes) < slow:
        return None
    fast_ma = _mean(closes[-fast:])
    slow_ma = _mean(closes[-slow:])
    if slow_ma == 0:
        return None
    return (fast_ma - slow_ma) / slow_ma


def range_position(candles: Sequence[Candle], window: int = 24) -> float | None:
    """Return where the close sits in its recent range, scaled to ``[-1, 1]``.

    ``+1`` is the top of the window's range, ``-1`` the bottom.
    """
    if len(candles) < window:
        return None
    recent = candles[-window:]
    high = max(float(c.high) for c in recent)
    low = min(float(c.low) for c in recent)
    if high == low:
        return 0.0
    return 2 * (float(recent[-1].close) - low) / (high - low) - 1


REGISTRY: dict[str, Factor] = {
    factor.name: factor
    for factor in (
        Factor(
            name="momentum_12",
            category="momentum",
            description="Return over the last 12 bars; positive means recent strength.",
            lookback=13,
            compute=lambda c: momentum(c, 12),
        ),
        Factor(
            name="momentum_48",
            category="momentum",
            description="Return over the last 48 bars; the slower cousin of momentum_12.",
            lookback=49,
            compute=lambda c: momentum(c, 48),
        ),
        Factor(
            name="volatility_24",
            category="volatility",
            description="Standard deviation of returns over 24 bars.",
            lookback=25,
            compute=lambda c: volatility(c, 24),
        ),
        Factor(
            name="rsi_14",
            category="momentum",
            description="RSI over 14 bars, re-centred so 0 is neutral.",
            lookback=15,
            compute=lambda c: rsi(c, 14),
        ),
        Factor(
            name="volume_z_24",
            category="volume",
            description="How unusual the latest volume is, in standard deviations.",
            lookback=25,
            compute=lambda c: volume_zscore(c, 24),
        ),
        Factor(
            name="trend_8_24",
            category="trend",
            description="Fast/slow moving-average gap; positive means an uptrend.",
            lookback=24,
            compute=lambda c: trend_strength(c, 8, 24),
        ),
        Factor(
            name="range_position_24",
            category="trend",
            description="Where the close sits in its 24-bar range, from -1 to +1.",
            lookback=24,
            compute=lambda c: range_position(c, 24),
        ),
    )
}


def get(name: str) -> Factor:
    """Return the factor registered as ``name``.

    Raises:
        KeyError: If no such factor is registered.
    """
    try:
        return REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown factor '{name}'. Available: {', '.join(sorted(REGISTRY))}"
        ) from exc


def compute(name: str, candles: Sequence[Candle]) -> float | None:
    """Return the current value of ``name`` over ``candles``."""
    return get(name).compute(candles)


def compute_all(candles: Sequence[Candle]) -> dict[str, float | None]:
    """Return every registered factor's current value."""
    return {name: factor.compute(candles) for name, factor in REGISTRY.items()}


def _paired_samples(
    factor: Factor, candles: Sequence[Candle], horizon: int
) -> tuple[list[float], list[float]]:
    """Return aligned (factor value, forward return) pairs.

    The factor at bar ``i`` is paired with the return from ``i`` to
    ``i + horizon``, so nothing is scored against information it could not have
    had at the time.
    """
    values: list[float] = []
    forwards: list[float] = []

    for i in range(factor.lookback, len(candles) - horizon):
        value = factor.compute(candles[: i + 1])
        if value is None:
            continue
        now = float(candles[i].close)
        later = float(candles[i + horizon].close)
        if now == 0:
            continue
        values.append(value)
        forwards.append((later - now) / now)

    return values, forwards


def _icir(values: Sequence[float], forwards: Sequence[float], buckets: int = 4) -> float:
    """Return the IC information ratio across ``buckets`` sub-samples.

    Splitting the sample and looking at the spread of ICs is what separates a
    persistent edge from one good stretch.
    """
    size = len(values) // buckets
    if size < 2:
        return 0.0
    ics = [
        correlation(values[i * size : (i + 1) * size], forwards[i * size : (i + 1) * size])
        for i in range(buckets)
    ]
    spread = _stdev(ics)
    if spread == 0:
        # Identical ICs across every bucket: perfectly stable by construction.
        return 0.0 if _mean(ics) == 0 else math.copysign(float("inf"), _mean(ics))
    return _mean(ics) / spread


def evaluate(name: str, candles: Sequence[Candle], *, horizon: int = 6) -> FactorScore:
    """Score how well ``name`` predicted returns ``horizon`` bars ahead.

    Args:
        name: A registered factor name.
        candles: Price history, oldest first.
        horizon: How many bars ahead the forward return looks.

    Returns:
        A :class:`FactorScore`. With too little history every statistic is zero
        and ``samples`` says why, rather than raising — a short window is a
        normal state for a newly tracked symbol.
    """
    factor = get(name)
    values, forwards = _paired_samples(factor, candles, horizon)

    if len(values) < 2:
        return FactorScore(
            name=name, horizon=horizon, samples=len(values), ic=0.0, rank_ic=0.0,
            icir=0.0, hit_rate=0.0,
        )

    agreements = sum(1 for v, f in zip(values, forwards, strict=True) if v * f > 0)
    return FactorScore(
        name=name,
        horizon=horizon,
        samples=len(values),
        ic=round(correlation(values, forwards), 6),
        rank_ic=round(rank_correlation(values, forwards), 6),
        icir=round(_icir(values, forwards), 6),
        hit_rate=round(agreements / len(values), 6),
    )


def rank_factors(candles: Sequence[Candle], *, horizon: int = 6) -> list[FactorScore]:
    """Score every registered factor, strongest absolute IC first."""
    scores = [evaluate(name, candles, horizon=horizon) for name in REGISTRY]
    scores.sort(key=lambda s: abs(s.ic), reverse=True)
    return scores


def signal_from_factors(
    candles: Sequence[Candle], scores: Sequence[FactorScore]
) -> float:
    """Blend significant factors into one signal in roughly ``[-1, 1]``.

    Each factor votes in the direction its own IC earned: a factor that reliably
    predicted *falling* prices contributes its negative sign rather than being
    discarded. Votes are weighted by |IC|, and factors that failed
    :attr:`FactorScore.is_significant` do not vote at all.

    Returns:
        ``0.0`` when nothing is significant — the honest answer for "no edge",
        and the value a caller should treat as "do not trade".
    """
    numerator = 0.0
    weight_total = 0.0

    for score in scores:
        if not score.is_significant:
            continue
        value = compute(score.name, candles)
        if value is None:
            continue
        weight = abs(score.ic)
        numerator += math.copysign(1.0, score.ic) * max(-1.0, min(1.0, value)) * weight
        weight_total += weight

    if weight_total == 0:
        return 0.0
    return max(-1.0, min(1.0, numerator / weight_total))
