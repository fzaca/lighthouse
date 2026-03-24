"""Tests for the geospatial utility helpers."""

from __future__ import annotations

import math

import pytest

from pharox.utils.geo import EARTH_RADIUS_KM, haversine_distance_km


def test_same_point_distance_is_zero() -> None:
    """Distance from a point to itself must be 0."""
    assert haversine_distance_km(48.8566, 2.3522, 48.8566, 2.3522) == pytest.approx(
        0.0, abs=1e-9
    )


def test_paris_to_london_distance() -> None:
    """Paris → London is roughly 340 km."""
    dist = haversine_distance_km(48.8566, 2.3522, 51.5074, -0.1278)
    assert 330 < dist < 350


def test_new_york_to_los_angeles() -> None:
    """New York → Los Angeles is roughly 3940 km."""
    dist = haversine_distance_km(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3900 < dist < 4000


def test_antipodal_points_approach_half_circumference() -> None:
    """Points on opposite sides of the Earth should be close to π × R km."""
    dist = haversine_distance_km(0.0, 0.0, 0.0, 180.0)
    assert dist == pytest.approx(math.pi * EARTH_RADIUS_KM, rel=1e-6)


def test_symmetry() -> None:
    """haversine_distance_km(a, b) == haversine_distance_km(b, a)."""
    d1 = haversine_distance_km(48.8566, 2.3522, 51.5074, -0.1278)
    d2 = haversine_distance_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert d1 == pytest.approx(d2)


def test_earth_radius_constant() -> None:
    """EARTH_RADIUS_KM should equal the standard value of 6371.0 km."""
    assert EARTH_RADIUS_KM == 6371.0
