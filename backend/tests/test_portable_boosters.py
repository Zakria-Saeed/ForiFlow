"""Boosters pickled on another OS must still load for serving.

xgboost 3 serialises the training RNG as the C++ standard library prints it,
and libstdc++ (Linux) and MSVC (Windows) disagree on the format, so the shipped
Linux-trained artefacts raised ``input stream corrupted`` on Windows. A state
this platform cannot read stands in for the foreign one here.
"""

from __future__ import annotations

import numpy as np
import pytest

from services.scoring_service import _portable_xgboost_boosters, _with_native_rng_state

xgb = pytest.importorskip("xgboost")


def _booster_with_unreadable_rng_state() -> tuple[object, dict, object]:
    """Train a small booster and return it with a pickle state it cannot read."""
    rng = np.random.default_rng(0)
    features = rng.random((200, 3))
    labels = (features[:, 0] > 0.5).astype(int)
    matrix = xgb.DMatrix(features, label=labels)
    booster = xgb.train({"max_depth": 3, "seed": 42}, matrix, num_boost_round=10)

    state = booster.__getstate__()
    # Normalising first guarantees the int64 length layout: "S", "L", 8 bytes.
    buffer = _with_native_rng_state(bytes(state["handle"]))
    start = buffer.find(b"rng_stateSL") + len(b"rng_stateSL") + 8
    length = int.from_bytes(buffer[start - 8 : start], "big")
    unreadable = buffer[:start] + b"#" * length + buffer[start + length :]
    return booster, {**state, "handle": bytearray(unreadable)}, matrix


def test_unreadable_rng_state_breaks_a_plain_load() -> None:
    """Guard the premise where it holds: MSVC rejects the state, libstdc++
    leaves the stream in a failed state without raising, so Linux loads it."""
    _, state, _ = _booster_with_unreadable_rng_state()
    try:
        xgb.Booster().__setstate__(dict(state))
    except xgb.core.XGBoostError:
        return
    pytest.skip("this platform's C++ library does not reject an unreadable RNG state")


def test_portable_load_restores_identical_predictions() -> None:
    """With the shim the booster loads and predicts exactly as trained."""
    booster, state, matrix = _booster_with_unreadable_rng_state()
    restored = xgb.Booster()
    with _portable_xgboost_boosters():
        restored.__setstate__(state)
    np.testing.assert_array_equal(restored.predict(matrix), booster.predict(matrix))


def test_shim_is_removed_after_loading() -> None:
    """The patched ``__setstate__`` must not leak past the ``with`` block."""
    original = xgb.core.Booster.__setstate__
    with _portable_xgboost_boosters():
        assert xgb.core.Booster.__setstate__ is not original
    assert xgb.core.Booster.__setstate__ is original
