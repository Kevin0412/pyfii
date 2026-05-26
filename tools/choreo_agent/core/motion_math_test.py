#!/usr/bin/env python3
"""Motion math regression tests."""
from motion_math import (
    accel_for_feel,
    flight_time_ms,
    motion_budget,
    speed_for_interval,
)


def test_triangle_speed_curve():
    assert flight_time_ms(25, 100, 100) == 1000


def test_trapezoid_speed_curve():
    assert flight_time_ms(200, 100, 100) == 3000


def test_accel_override_is_independent():
    budget = motion_budget(200, 2.8, accel_cm_s2=150)
    assert budget.accel_cm_s2 == 150
    assert budget.accel_cm_s2 != budget.speed_cm_s * 2


def test_speed_for_interval_uses_feel_default():
    soft_speed = speed_for_interval(220, 2.4, feel="soft")
    crisp_speed = speed_for_interval(220, 2.4, feel="crisp")
    assert soft_speed >= crisp_speed
    assert accel_for_feel(120, "soft") < accel_for_feel(120, "crisp")


if __name__ == "__main__":
    test_triangle_speed_curve()
    test_trapezoid_speed_curve()
    test_accel_override_is_independent()
    test_speed_for_interval_uses_feel_default()
    print("OK")
