from __future__ import annotations

import numpy as np
import pytest

from sys_foot_quant.calibration_engine.isotonic_calibration import (
    fit_isotonic_calibration,
)


def test_fitted_curve_is_monotone_non_decreasing() -> None:
    rng = np.random.default_rng(0)
    p_calib = rng.uniform(0, 1, size=500)
    y_calib = (rng.uniform(0, 1, size=500) < p_calib).astype(float)
    curve = fit_isotonic_calibration(p_calib, y_calib)

    grid = np.linspace(0.0, 1.0, 200)
    predicted = curve.predict(grid)
    assert np.all(np.diff(predicted) >= -1e-12)


def test_well_calibrated_input_stays_close_to_identity_on_average() -> None:
    rng = np.random.default_rng(1)
    n = 5000
    p_calib = rng.uniform(0.05, 0.95, size=n)
    y_calib = (rng.uniform(0, 1, size=n) < p_calib).astype(float)
    curve = fit_isotonic_calibration(p_calib, y_calib)

    grid = np.linspace(0.1, 0.9, 50)
    predicted = curve.predict(grid)
    assert np.mean(np.abs(predicted - grid)) < 0.05


def test_systematically_overconfident_input_is_corrected_downward() -> None:
    # p_calib toujours 0.3 au-dessus de la vraie probabilite -> la courbe
    # ajustee doit ramener les predictions vers le bas, en calibration.
    rng = np.random.default_rng(2)
    n = 4000
    true_p = rng.uniform(0.1, 0.6, size=n)
    p_calib = np.clip(true_p + 0.3, 0.0, 1.0)
    y_calib = (rng.uniform(0, 1, size=n) < true_p).astype(float)
    curve = fit_isotonic_calibration(p_calib, y_calib)

    predicted = curve.predict(p_calib)
    assert predicted.mean() < p_calib.mean()
    assert predicted.mean() == pytest.approx(true_p.mean(), abs=0.05)


def test_predict_clips_outside_calibration_range() -> None:
    p_calib = np.array([0.3, 0.4, 0.5, 0.6, 0.7])
    y_calib = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    curve = fit_isotonic_calibration(p_calib, y_calib)

    below = curve.predict(np.array([0.0, 0.1]))
    above = curve.predict(np.array([0.9, 1.0]))
    assert np.all(below == below[0])  # clippe a la valeur du point le plus bas
    assert np.all(above == above[0])  # clippe a la valeur du point le plus haut


def test_predict_on_exact_calibration_points_matches_fitted_values() -> None:
    p_calib = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    y_calib = np.array([0.0, 1.0, 0.0, 1.0, 1.0])
    curve = fit_isotonic_calibration(p_calib, y_calib)
    predicted = curve.predict(curve.x_calibration)
    assert np.allclose(predicted, curve.fitted_values)


def test_constant_calibration_input_returns_constant_prediction() -> None:
    p_calib = np.full(20, 0.5)
    y_calib = np.array([1.0, 0.0] * 10)
    curve = fit_isotonic_calibration(p_calib, y_calib)
    predicted = curve.predict(np.array([0.0, 0.5, 1.0]))
    assert np.allclose(predicted, 0.5, atol=1e-9)


def test_mismatched_shapes_raise() -> None:
    with pytest.raises(ValueError):
        fit_isotonic_calibration(np.array([0.1, 0.2]), np.array([1.0]))


def test_empty_calibration_set_raises() -> None:
    with pytest.raises(ValueError):
        fit_isotonic_calibration(np.array([]), np.array([]))


def test_unsorted_input_is_handled_correctly() -> None:
    # L'ordre d'entree ne doit pas affecter le resultat - le tri interne
    # doit rendre le resultat independant de l'ordre de presentation.
    p_a = np.array([0.5, 0.1, 0.9, 0.3, 0.7])
    y_a = np.array([1.0, 0.0, 1.0, 0.0, 1.0])
    curve_a = fit_isotonic_calibration(p_a, y_a)

    perm = [2, 0, 4, 1, 3]
    p_b = p_a[perm]
    y_b = y_a[perm]
    curve_b = fit_isotonic_calibration(p_b, y_b)

    grid = np.linspace(0.0, 1.0, 20)
    assert np.allclose(curve_a.predict(grid), curve_b.predict(grid))
