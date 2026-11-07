"""Local 3D waveform and spectrogram data preparation for the Streamlit UI."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import stft

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VISUALIZER_BUNDLE = (
    PROJECT_ROOT / "frontend" / "acoustic-visualizer" / "dist" / "visualizer.bundle.js"
)
MAX_WAVEFORM_POINTS = 1200
MAX_SPECTROGRAM_TIME_BINS = 128
MAX_SPECTROGRAM_FREQUENCY_BINS = 64


def _mono_finite(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("3D signal visualization requires mono 1D audio.")
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("3D signal visualization requires finite, non-empty audio.")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)):
        raise ValueError("3D signal visualization requires an integer sample rate.")
    if sample_rate <= 0:
        raise ValueError("3D signal visualization requires a positive sample rate.")
    return values


def waveform_payload(samples: np.ndarray, sample_rate: int) -> dict[str, Any]:
    """Return at most 1,200 time/amplitude points, preserving local extrema."""
    values = _mono_finite(samples, sample_rate)
    if values.size <= MAX_WAVEFORM_POINTS:
        indices = np.arange(values.size, dtype=np.int64)
    else:
        bins = (MAX_WAVEFORM_POINTS - 2) // 2
        edges = np.linspace(0, values.size, bins + 1, dtype=np.int64)
        extrema: list[int] = []
        for start, stop in zip(edges[:-1], edges[1:], strict=True):
            if stop <= start:
                continue
            segment = values[start:stop]
            minimum = int(start + np.argmin(segment))
            maximum = int(start + np.argmax(segment))
            extrema.extend(sorted((minimum, maximum)))
        indices = np.unique(np.asarray([0, *extrema, values.size - 1], dtype=np.int64))
    points = [[round(int(index) / int(sample_rate), 6), float(values[index])] for index in indices]
    return {
        "mode": "waveform",
        "sample_rate_hz": int(sample_rate),
        "duration_seconds": values.size / int(sample_rate),
        "points": points,
    }


def spectrogram_payload(
    samples: np.ndarray,
    sample_rate: int,
    *,
    maximum_frequency_hz: float = 3800.0,
    window_samples: int = 512,
    hop_samples: int = 128,
) -> dict[str, Any]:
    """Return a bounded STFT grid as dB relative to unit amplitude (20 log10 magnitude)."""
    values = _mono_finite(samples, sample_rate)
    if (
        isinstance(window_samples, bool)
        or not isinstance(window_samples, (int, np.integer))
        or int(window_samples) < 64
    ):
        raise ValueError("STFT window size must be an integer of at least 64 samples.")
    if (
        isinstance(hop_samples, bool)
        or not isinstance(hop_samples, (int, np.integer))
        or not 1 <= int(hop_samples) <= int(window_samples)
    ):
        raise ValueError("STFT hop size must be an integer between 1 and the window size.")
    if (
        isinstance(maximum_frequency_hz, bool)
        or not isinstance(maximum_frequency_hz, (int, float, np.floating, np.integer))
        or not np.isfinite(float(maximum_frequency_hz))
        or float(maximum_frequency_hz) <= 0
    ):
        raise ValueError("Maximum spectrogram frequency must be a finite positive value.")
    if float(maximum_frequency_hz) >= sample_rate / 2:
        raise ValueError("Maximum spectrogram frequency must be below the sample-rate Nyquist.")

    nperseg = min(window_samples, values.size)
    effective_hop = min(hop_samples, nperseg)
    noverlap = nperseg - effective_hop
    frequencies, times, spectrum = stft(
        values,
        fs=int(sample_rate),
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=False,
    )
    frequency_indices = np.flatnonzero(frequencies <= maximum_frequency_hz)
    if frequency_indices.size < 2 or times.size < 2:
        raise ValueError("Audio is too short for a stable 3D spectrogram.")
    frequency_indices = frequency_indices[
        np.linspace(
            0,
            frequency_indices.size - 1,
            min(frequency_indices.size, MAX_SPECTROGRAM_FREQUENCY_BINS),
            dtype=np.int64,
        )
    ]
    time_indices = np.linspace(
        0,
        times.size - 1,
        min(times.size, MAX_SPECTROGRAM_TIME_BINS),
        dtype=np.int64,
    )
    magnitudes = np.abs(spectrum[np.ix_(frequency_indices, time_indices)])
    magnitude_db = 20.0 * np.log10(np.maximum(magnitudes, 1e-9))
    if not np.isfinite(magnitude_db).all():
        raise ValueError("STFT produced non-finite spectrogram values.")
    return {
        "mode": "spectrogram",
        "sample_rate_hz": int(sample_rate),
        "time_scale": "seconds",
        "frequency_scale": "Hz",
        "magnitude_scale": "20 log10(|STFT| / 1.0), dB re 1.0",
        "display_db_min": -90.0,
        "display_db_max": 0.0,
        "times": [float(value) for value in times[time_indices]],
        "frequencies_hz": [float(value) for value in frequencies[frequency_indices]],
        "magnitude_db": magnitude_db.tolist(),
    }


def decorative_hero_payload() -> dict[str, str]:
    """Identify the home-page signal ribbon as decorative rather than measured data."""
    return {"mode": "hero"}


@lru_cache(maxsize=1)
def _visualizer_bundle() -> str:
    try:
        return VISUALIZER_BUNDLE.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(
            "The local 3D visualization bundle is missing. Run npm ci and npm run build "
            "in frontend/acoustic-visualizer."
        ) from exc


def viewer_html(data: dict[str, Any]) -> str:
    """Create an isolated, self-contained iframe using only the checked-in JS bundle."""
    serialized = json.dumps(data, allow_nan=False, separators=(",", ":"))
    if len(serialized) > 256_000:
        raise ValueError("3D visualization data exceeded the 256 KB component limit.")
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    bundle = _visualizer_bundle()
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0; width: 100%; height: 100%; background: #0a1922; color: #e7f2ef;
  font: 12px 'Segoe UI', sans-serif; overflow: hidden;
}}
#viewer {{
  height: 100%; min-height: 240px; position: relative; border: 1px solid #21414a;
  border-radius: 12px; overflow: hidden; background: #0a1922;
}}
canvas {{ display: block; width: 100%; height: 100%; }}
.toolbar {{ position: absolute; z-index: 2; top: 10px; right: 12px; display: flex; gap: 8px; }}
.toolbar[hidden] {{ display: none; }}
button {{
  background: #122733; color: #d8eeea; border: 1px solid #31515a; border-radius: 6px;
  padding: 6px 9px; font: inherit; cursor: pointer;
}}
button:hover {{ border-color: #55d9c1; }}
button:focus-visible {{ outline: 2px solid #70b9e8; outline-offset: 2px; }}
.note, .axes {{
  position: absolute; left: 12px; z-index: 2; max-width: 75%;
  background: #0a1922cc; padding: 5px 8px; border-radius: 4px;
}}
.note {{ bottom: 10px; color: #a7b8b5; }}
.axes {{ top: 11px; color: #b9f0df; }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
</style></head><body>
<div id="viewer" role="group" aria-label="Interactive three-dimensional acoustic visualization">
<canvas role="img"
        aria-label="Three-dimensional acoustic scene. Drag to orbit and scroll to zoom."></canvas>
<div class="toolbar">
  <button type="button" data-reset-view aria-label="Reset 3D camera view">Reset view</button>
</div>
<div class="axes" data-axis-labels></div>
<div class="note" id="voxneuro-fallback-note">Loading local visualization…</div>
</div>
<script>window.VOXNEURO_DATA={serialized};</script><script>{bundle}</script>
<script>window.__voxneuroDispose=VoxNeuro3D.mount(document.getElementById('viewer'),window.VOXNEURO_DATA);</script>
</body></html>"""


def render_acoustic_view(data: dict[str, Any], *, height: int = 420) -> None:
    """Render a local WebGL view; keep the caller's 2D plotting path as fallback."""
    import streamlit as st

    if type(height) is not int or not 240 <= height <= 900:
        raise ValueError("Visualization height must be an integer between 240 and 900 pixels.")
    st.iframe(
        viewer_html(data),
        height=height,
        alt="Interactive local 3D waveform or spectrogram view",
    )
