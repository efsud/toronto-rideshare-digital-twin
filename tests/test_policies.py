from toronto_rideshare.policies import driver_bonus_cad, rider_adjustment_cad


def test_rider_adjustment_sign() -> None:
    assert rider_adjustment_cad(2.0) > 0
    assert rider_adjustment_cad(-2.0) < 0


def test_driver_bonus_nonnegative() -> None:
    assert driver_bonus_cad(-1.0) == 0.0
    assert driver_bonus_cad(2.0) > 0
