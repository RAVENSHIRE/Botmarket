"""Computing and scoring factors against a venue's market data.

The domain module does the maths on a list of candles; this one gets the
candles. Splitting it that way keeps every statistic testable on fixed data
while the network-facing half stays thin enough to read in one sitting.
"""

from __future__ import annotations

from collections.abc import Sequence

from botmarket.domain import factors as factor_domain
from botmarket.domain.errors import InvalidAction, NotFound
from botmarket.domain.venue import Candle, Environment
from botmarket.venues import registry

DEFAULT_HORIZON = 6
MAX_CANDLES = 500


def library() -> list[dict]:
    """Describe every registered factor."""
    return [
        {
            "name": factor.name,
            "category": factor.category,
            "description": factor.description,
            "lookback": factor.lookback,
        }
        for factor in sorted(factor_domain.REGISTRY.values(), key=lambda f: f.name)
    ]


def candles_for(
    symbol: str,
    *,
    venue: str = "paper",
    environment: str = "paper",
    interval: str = "1h",
    limit: int = 200,
) -> list[Candle]:
    """Fetch price history for a symbol from a venue.

    Raises:
        InvalidAction: If the venue/environment pairing is not allowed.
    """
    env = registry.parse_environment(environment)
    feed = registry.build_market_data(venue, env)
    return feed.candles(symbol.upper(), interval=interval, limit=min(limit, MAX_CANDLES))


def _score_payload(score: factor_domain.FactorScore) -> dict:
    """Shape a factor score for the API."""
    return {
        "name": score.name,
        "horizon": score.horizon,
        "samples": score.samples,
        "ic": score.ic,
        "rank_ic": score.rank_ic,
        "icir": score.icir,
        "hit_rate": score.hit_rate,
        "significant": score.is_significant,
    }


def evaluate_symbol(
    symbol: str,
    *,
    venue: str = "paper",
    environment: str = "paper",
    interval: str = "1h",
    horizon: int = DEFAULT_HORIZON,
    limit: int = 200,
) -> dict:
    """Score every factor for a symbol and blend the significant ones.

    Returns:
        Current factor values, their effectiveness scores strongest first, and
        the combined signal in ``[-1, 1]``.
    """
    candles = candles_for(
        symbol, venue=venue, environment=environment, interval=interval, limit=limit
    )
    if not candles:
        raise NotFound(f"No price history available for {symbol.upper()}")

    scores = factor_domain.rank_factors(candles, horizon=horizon)
    values = factor_domain.compute_all(candles)

    return {
        "symbol": symbol.upper(),
        "venue": venue,
        "environment": environment,
        "interval": interval,
        "horizon": horizon,
        "candles": len(candles),
        "last_price": float(candles[-1].close),
        "values": {name: value for name, value in sorted(values.items())},
        "scores": [_score_payload(s) for s in scores],
        "signal": round(factor_domain.signal_from_factors(candles, scores), 6),
    }


def evaluate_one(
    name: str,
    symbol: str,
    *,
    venue: str = "paper",
    environment: str = "paper",
    interval: str = "1h",
    horizon: int = DEFAULT_HORIZON,
    limit: int = 200,
) -> dict:
    """Score a single named factor for a symbol.

    Raises:
        NotFound: If the factor is not registered or there is no price history.
    """
    try:
        factor = factor_domain.get(name)
    except KeyError as exc:
        raise NotFound(str(exc)) from exc

    candles = candles_for(
        symbol, venue=venue, environment=environment, interval=interval, limit=limit
    )
    if not candles:
        raise NotFound(f"No price history available for {symbol.upper()}")

    score = factor_domain.evaluate(name, candles, horizon=horizon)
    return {
        "symbol": symbol.upper(),
        "factor": {
            "name": factor.name,
            "category": factor.category,
            "description": factor.description,
            "lookback": factor.lookback,
        },
        "value": factor.compute(candles),
        "score": _score_payload(score),
    }


def signal_for(
    symbol: str,
    *,
    venue: str = "paper",
    environment: str = "paper",
    interval: str = "1h",
    horizon: int = DEFAULT_HORIZON,
) -> float:
    """Return only the blended signal for a symbol.

    This is what a trading agent calls: one number, sign meaning direction, and
    zero meaning "no factor cleared the significance bar, so do not trade".
    """
    candles = candles_for(symbol, venue=venue, environment=environment, interval=interval)
    if not candles:
        return 0.0
    scores = factor_domain.rank_factors(candles, horizon=horizon)
    return round(factor_domain.signal_from_factors(candles, scores), 6)


def market_overview(
    symbols: Sequence[str],
    *,
    venue: str = "paper",
    environment: str = "paper",
    interval: str = "1h",
) -> list[dict]:
    """Return a compact signal row per symbol, for the dashboard.

    A symbol the venue cannot price is reported with its error rather than
    dropped, so a typo in a watchlist is visible instead of silent.
    """
    env = registry.parse_environment(environment)
    feed = registry.build_market_data(venue, env)
    rows: list[dict] = []

    for symbol in symbols:
        try:
            candles = feed.candles(symbol.upper(), interval=interval, limit=200)
            quote = feed.quote(symbol.upper())
        except (InvalidAction, NotFound, KeyError) as exc:
            rows.append({"symbol": symbol.upper(), "error": str(exc)})
            continue

        scores = factor_domain.rank_factors(candles, horizon=DEFAULT_HORIZON)
        best = scores[0] if scores else None
        rows.append(
            {
                "symbol": symbol.upper(),
                "price": float(quote.mid),
                "signal": round(factor_domain.signal_from_factors(candles, scores), 6),
                "best_factor": best.name if best else None,
                "best_ic": best.ic if best else 0.0,
                "significant_factors": sum(1 for s in scores if s.is_significant),
            }
        )

    return rows


def default_environment(venue: str) -> Environment:
    """Return the environment a venue defaults to when none was given."""
    return Environment.PAPER if venue == "paper" else Environment.TESTNET
