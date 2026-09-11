from toronto_rideshare.network.build_network import DEFAULT_HIGHWAY_SPEEDS_KPH


def test_default_speed_table_has_core_road_classes() -> None:
    for highway in ("motorway", "primary", "secondary", "residential"):
        assert highway in DEFAULT_HIGHWAY_SPEEDS_KPH
        assert DEFAULT_HIGHWAY_SPEEDS_KPH[highway] > 0
