"""Trip-level pricing and competing-request choice for the daily marketplace.

Coefficients are tunable assumptions, not estimated Toronto elasticities.
"""

import math
from dataclasses import dataclass

from toronto_rideshare.marketplace.fares import FareBreakdown, compute_fare


@dataclass(frozen=True)
class TripQuote:
    request_id: str
    offered_at_min: float
    origin_shortage: float
    destination_shortage: float
    transfer_value: float
    fare: FareBreakdown

    @property
    def subsidy_cad(self):
        return max(0.0, -self.fare.rider_adjustment_cad) + self.fare.driver_bonus_cad


def quote_trip(
    request_id,
    now,
    distance_km,
    duration_min,
    origin_shortage,
    destination_shortage,
    *,
    adaptive=False,
    rider_cap=5.0,
    bonus_cap=12.0,
    origin_gain=0.5,
    transfer_gain=1.0,
    discount_gain=0.5,
    available_budget=math.inf,
):
    """Reward movement toward relative shortage; reserve a firm quote before acceptance.

    A trip from surplus to shortage has positive transfer value; reversing its
    direction reverses that value. Subsidies are capped before the rider sees the
    quote, so budget pressure cannot later change an accepted rider price.
    """
    transfer = destination_shortage - origin_shortage
    adjustment = bonus = 0.0
    if adaptive:
        useful_transfer = max(0.0, transfer)
        adjustment = max(
            -rider_cap,
            min(rider_cap, origin_gain * origin_shortage - discount_gain * useful_transfer),
        )
        bonus = min(bonus_cap, transfer_gain * useful_transfer)
    fare = compute_fare(
        distance_km, duration_min, rider_adjustment_cad=adjustment, driver_bonus_cad=bonus
    )
    subsidy = max(0.0, -fare.rider_adjustment_cad) + fare.driver_bonus_cad
    if subsidy > available_budget:
        scale = max(0.0, available_budget) / subsidy
        adjustment = fare.rider_adjustment_cad
        if adjustment < 0:
            adjustment *= scale
        fare = compute_fare(
            distance_km,
            duration_min,
            rider_adjustment_cad=adjustment,
            driver_bonus_cad=bonus * scale,
        )
    return TripQuote(request_id, now, origin_shortage, destination_shortage, transfer, fare)


def rider_quote_probability(quote, *, intercept=2.0, price_per_cad=0.08):
    """Acceptance responds to the actual total quote, including the baseline fare."""
    score = intercept - price_per_cad * quote.fare.rider_payment_cad
    return 1 / (1 + math.exp(-max(-40.0, min(40.0, score))))


def driver_choice_probabilities(
    offers, *, intercept=0.5, earnings_per_cad=0.10, pickup_penalty=0.18, occupied_penalty=0.02
):
    """Multinomial logit over (id, earnings, pickup, occupied) plus staying idle.

    Keys are request IDs; None is the outside option. Canonical ID sorting makes
    probabilities independent of input ordering. Higher pay increases choice
    probability, holding route burdens and the competing menu fixed.
    """
    scores = {None: 0.0}
    for ident, earnings, pickup, occupied in sorted(offers):
        if ident in scores:
            raise ValueError("Each driver menu must contain unique request IDs")
        score = intercept + earnings_per_cad * earnings - pickup_penalty * pickup
        scores[ident] = max(-700.0, min(700.0, score - occupied_penalty * occupied))
    maximum = max(scores.values())
    weights = {ident: math.exp(score - maximum) for ident, score in scores.items()}
    total = sum(weights.values())
    return {ident: value / total for ident, value in weights.items()}


def choose_request(probabilities, draw):
    if not 0 <= draw < 1:
        raise ValueError("Choice draw must be in [0,1)")
    cumulative = 0.0
    for request_id, probability in probabilities.items():
        cumulative += probability
        if draw < cumulative:
            return request_id
    return next(reversed(probabilities))  # floating-point tail only
