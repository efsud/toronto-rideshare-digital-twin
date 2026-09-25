from toronto_rideshare.policies.behavior import (
    BehaviorConfig,
    OfferAcceptanceConfig,
    driver_offer_probability,
    effective_demand_multiplier,
    effective_supply_multiplier,
)


def test_offer_acceptance_config_is_public_behavior_api() -> None:
    cfg = OfferAcceptanceConfig(
        intercept=0.0,
        earnings_per_cad=0.0,
        pickup_minutes_penalty=0.0,
    )

    assert driver_offer_probability(10.0, 5.0, config=cfg) == 0.5


def test_rider_elasticity_reduces_demand_on_surcharge() -> None:
    cfg = BehaviorConfig(rider_price_elasticity=-0.3)
    base = effective_demand_multiplier(1.0, 0.0, config=cfg)
    surcharged = effective_demand_multiplier(1.0, 5.0, config=cfg)
    assert surcharged < base


def test_driver_bonus_increases_supply() -> None:
    cfg = BehaviorConfig(driver_bonus_elasticity=0.4)
    base = effective_supply_multiplier(20, 0.0, config=cfg)
    boosted = effective_supply_multiplier(20, 12.0, config=cfg)
    assert boosted >= base
