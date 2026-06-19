"""Unit tests for the Cradlewise infant-cry detection DSP.

Exercises the pure signal-processing module
``config/custom_components/cradlewise/cry_dsp.py`` with synthetic audio:

  * analyse_cry_window — single-window classification across signal types
  * CryDetector        — buffering, windowing, decimation, and majority-vote
                         debounce that drives the binary_sensor state

Requires only numpy (no Home Assistant / aiortc), so it runs in CI without the
full integration stack.

Running:
  source venv/bin/activate && pytest tests/test_cry_detection.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# The integration package lives outside the import path; add it directly.
_CRADLEWISE_DIR = (
    Path(__file__).parent.parent / "config" / "custom_components" / "cradlewise"
)
sys.path.insert(0, str(_CRADLEWISE_DIR))

import cry_dsp  # noqa: E402  (path injected above)

RATE = cry_dsp.CRY_WINDOW_SAMPLES  # 48000 — one analysis window == 1 second


# ── Synthetic signal generators ─────────────────────────────────────────────────


def _t(n: int, rate: int = RATE) -> np.ndarray:
    return np.linspace(0, n / rate, n, endpoint=False, dtype=np.float32)


def tone(freq: float, amp: float = 0.5, n: int = RATE, rate: int = RATE) -> np.ndarray:
    return (amp * np.sin(2 * np.pi * freq * _t(n, rate))).astype(np.float32)


def cry_like(n: int = RATE, rate: int = RATE, fundamental: float = 500.0) -> np.ndarray:
    """Harmonic stack in the cry band: a tonal, structured spectrum at 400–1600 Hz."""
    t = _t(n, rate)
    sig = (
        0.5 * np.sin(2 * np.pi * fundamental * t)
        + 0.3 * np.sin(2 * np.pi * 2 * fundamental * t)
        + 0.2 * np.sin(2 * np.pi * 3 * fundamental * t)
    )
    return sig.astype(np.float32)


def white_noise(n: int = RATE, amp: float = 0.3, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) * amp).astype(np.float32)


def silence(n: int = RATE) -> np.ndarray:
    return np.zeros(n, dtype=np.float32)


# ── analyse_cry_window: positive cases ──────────────────────────────────────────


def test_synthetic_cry_is_detected():
    assert cry_dsp.analyse_cry_window(cry_like()) is True


@pytest.mark.parametrize("fundamental", [400, 500, 650, 800])
def test_cry_detected_across_fundamentals(fundamental):
    assert cry_dsp.analyse_cry_window(cry_like(fundamental=fundamental)) is True


def test_single_tone_in_cry_band_is_detected():
    # A clean 600 Hz tone is tonal (low SFM), centroid in range, energy in band.
    assert cry_dsp.analyse_cry_window(tone(600)) is True


# ── analyse_cry_window: negative cases (false-positive rejection) ───────────────


def test_silence_is_rejected():
    assert cry_dsp.analyse_cry_window(silence()) is False


def test_sub_threshold_amplitude_is_rejected():
    # Cry-shaped spectrum but far below the RMS gate → treated as silence.
    quiet = cry_like() * 0.01
    assert cry_dsp.analyse_cry_window(quiet) is False


def test_white_noise_is_rejected():
    # Broadband noise (white-noise machine / fan) → high spectral flatness.
    assert cry_dsp.analyse_cry_window(white_noise()) is False


def test_low_frequency_hum_is_rejected():
    # 120 Hz HVAC / mains hum → centroid below the cry range.
    assert cry_dsp.analyse_cry_window(tone(120)) is False


def test_high_frequency_hiss_is_rejected():
    # 9 kHz tone → centroid above the cry range / energy outside cry band.
    assert cry_dsp.analyse_cry_window(tone(9000)) is False


def test_empty_array_is_rejected():
    assert cry_dsp.analyse_cry_window(np.array([], dtype=np.float32)) is False


def test_accepts_python_list_input():
    # Caller may pass a list; np.asarray coercion must not raise.
    assert cry_dsp.analyse_cry_window(list(cry_like())) is True


# ── analyse_cry_window: sample-rate independence ─────────────────────────────────


def test_cry_detected_at_16khz():
    # rfftfreq must use the supplied rate, not a hardcoded 48 kHz.
    n = 16000
    assert cry_dsp.analyse_cry_window(cry_like(n=n, rate=16000), sample_rate=16000) is True


def test_hum_rejected_at_16khz():
    assert cry_dsp.analyse_cry_window(tone(120, n=16000, rate=16000), sample_rate=16000) is False


# ── CryDetector: buffering & windowing ──────────────────────────────────────────


def test_detector_returns_none_before_first_full_window():
    det = cry_dsp.CryDetector()
    # Half a window of cry audio — not enough to analyse yet.
    assert det.feed(cry_like(n=RATE // 2)) is None
    assert det.is_crying is False


def test_detector_accumulates_across_partial_feeds():
    det = cry_dsp.CryDetector()
    cry = cry_like()
    # Feed the same 1-second cry in 4 quarter-chunks, three separate seconds.
    flips = []
    for _ in range(3):  # three full windows → crosses the 3-vote threshold
        for chunk in np.array_split(cry, 4):
            res = det.feed(chunk)
            if res is not None:
                flips.append(res)
    assert flips == [True]
    assert det.is_crying is True


# ── CryDetector: majority-vote debounce ─────────────────────────────────────────


def test_three_cry_windows_flip_state_on():
    det = cry_dsp.CryDetector()
    results = [det.feed(cry_like()) for _ in range(3)]
    # First two windows accumulate votes (None); third reaches threshold → True.
    assert results == [None, None, True]
    assert det.is_crying is True


def test_two_cry_windows_do_not_flip():
    det = cry_dsp.CryDetector()
    results = [det.feed(cry_like()) for _ in range(2)]
    assert results == [None, None]
    assert det.is_crying is False


def test_single_noisy_window_does_not_flip():
    """One stray cry window amid silence must not trip the sensor."""
    det = cry_dsp.CryDetector()
    assert det.feed(silence()) is None
    assert det.feed(cry_like()) is None       # 1 vote
    assert det.feed(silence()) is None
    assert det.feed(silence()) is None
    assert det.is_crying is False


def test_state_clears_after_baby_settles():
    det = cry_dsp.CryDetector()
    # Drive it crying with three cry windows.
    for _ in range(3):
        det.feed(cry_like())
    assert det.is_crying is True
    # Now feed silence; once cry votes age out of the 5-window deque, it clears.
    cleared = None
    for _ in range(5):
        res = det.feed(silence())
        if res is not None:
            cleared = res
            break
    assert cleared is False
    assert det.is_crying is False


def test_feed_returns_none_when_state_unchanged():
    det = cry_dsp.CryDetector()
    # Already-off detector fed silence → no transition.
    for _ in range(4):
        assert det.feed(silence()) is None
    assert det.is_crying is False


# ── CryDetector: decimation of non-48 kHz audio ─────────────────────────────────


def test_detector_decimates_96khz_audio():
    det = cry_dsp.CryDetector()
    # 96 kHz cry: 2× samples per window; decimated by 2 → one 48 kHz window each.
    flips = []
    for _ in range(3):
        res = det.feed(cry_like(n=RATE * 2, rate=RATE * 2), sample_rate=RATE * 2)
        if res is not None:
            flips.append(res)
    assert flips == [True]
    assert det.is_crying is True


# ── Constants sanity ────────────────────────────────────────────────────────────


def test_vote_threshold_is_majority_of_window():
    assert cry_dsp.CRY_VOTE_THRESHOLD <= cry_dsp.CRY_VOTE_LEN
    assert cry_dsp.CRY_VOTE_THRESHOLD > cry_dsp.CRY_VOTE_LEN // 2


def test_centroid_band_brackets_cry_range():
    assert cry_dsp.CENTROID_LO < cry_dsp.CENTROID_HI
    assert 0.0 < cry_dsp.SFM_MAX < 1.0
    assert 0.0 < cry_dsp.CRY_BAND_RATIO_MIN < 1.0
