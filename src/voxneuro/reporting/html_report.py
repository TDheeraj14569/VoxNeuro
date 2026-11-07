"""Self-contained HTML report for one analysed voice recording."""

from __future__ import annotations

import html
import math
from string import Template

import numpy as np
from scipy.signal import stft

from voxneuro.features.schema import FEATURE_DEFINITIONS, FEATURE_NAMES


def _display_value(value: object) -> tuple[str, str]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            return f"{float(value):.6g}", "Measured"
    return "Unavailable", "Not extracted"


def _waveform_svg(samples: np.ndarray, sample_rate: int) -> str:
    data = np.asarray(samples, dtype=np.float64)
    if data.ndim != 1 or len(data) < 2 or sample_rate <= 0 or not np.isfinite(data).all():
        return "<p class='empty'>A valid processed mono waveform was not supplied.</p>"
    width, height, left, top = 960.0, 240.0, 52.0, 16.0
    plot_width, plot_height = width - left - 18.0, height - 58.0
    blocks = min(900, len(data))
    edges = np.linspace(0, len(data), blocks + 1, dtype=int)
    points = []
    for index in range(blocks):
        chunk = data[edges[index] : max(edges[index] + 1, edges[index + 1])]
        minimum = float(chunk.min())
        maximum = float(chunk.max())
        x = left + (index / max(1, blocks - 1)) * plot_width
        y_top = top + (1.0 - maximum) * plot_height / 2
        y_bottom = top + (1.0 - minimum) * plot_height / 2
        points.append(f"{x:.1f},{y_top:.1f} {x:.1f},{y_bottom:.1f}")
    duration = len(data) / sample_rate
    return (
        f"<svg viewBox='0 0 {width:g} {height:g}' role='img' "
        "aria-label='Waveform of the analysed processed audio' "
        "xmlns='http://www.w3.org/2000/svg'>"
        "<title>Processed voice waveform</title>"
        f"<line x1='{left:g}' y1='{top + plot_height / 2:g}' "
        f"x2='{left + plot_width:g}' y2='{top + plot_height / 2:g}' stroke='#d3e0e2'/>"
        f"<g stroke='#087f83' stroke-width='1.1'>"
        f"{''.join(f'<polyline points="{p}" fill="none"/>' for p in points)}</g>"
        f"<text x='{left:g}' y='{height - 12:g}' font-size='12'>0 s</text>"
        f"<text x='{left + plot_width:g}' y='{height - 12:g}' text-anchor='end' "
        f"font-size='12'>{duration:.2f} s</text>"
        "<text x='12' y='25' font-size='12'>Amplitude</text></svg>"
    )


def _spectrogram_svg(samples: np.ndarray, sample_rate: int) -> str:
    data = np.asarray(samples, dtype=np.float64)
    if data.ndim != 1 or len(data) < 16 or sample_rate <= 0 or not np.isfinite(data).all():
        return "<p class='empty'>A spectrogram could not be generated from this signal.</p>"
    nperseg = min(1024, max(16, 2 ** int(math.floor(math.log2(len(data))))))
    if nperseg < 16:
        return "<p class='empty'>The processed recording is too short for this view.</p>"
    frequencies, times, spectrum = stft(
        data,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=nperseg // 2,
        boundary=None,
    )
    magnitude_db = 20 * np.log10(np.maximum(np.abs(spectrum), 1e-10))
    frequency_limit = min(4000.0, sample_rate / 2)
    rows = np.flatnonzero(frequencies <= frequency_limit)
    if not len(rows) or not len(times):
        return "<p class='empty'>A spectrogram could not be generated from this signal.</p>"
    frequency_indices = np.unique(np.linspace(0, len(rows) - 1, min(54, len(rows))).astype(int))
    time_indices = np.unique(np.linspace(0, len(times) - 1, min(100, len(times))).astype(int))
    selected = magnitude_db[rows[frequency_indices]][:, time_indices]
    high = float(np.max(selected))
    level = np.clip((selected - (high - 60.0)) / 60.0, 0.0, 1.0)
    palette = [(8, 35, 57), (10, 106, 126), (38, 175, 151), (224, 206, 114)]
    width, height, left, top = 960.0, 300.0, 68.0, 18.0
    plot_width, plot_height = width - left - 18.0, height - 72.0
    cell_width = plot_width / max(1, len(time_indices))
    cell_height = plot_height / max(1, len(frequency_indices))
    cells = []
    for row in range(len(frequency_indices)):
        for column in range(len(time_indices)):
            value = float(level[row, column])
            segment = min(2, int(value * 3))
            fraction = value * 3 - segment
            color_a, color_b = palette[segment], palette[segment + 1]
            color = tuple(
                round(a + (b - a) * fraction) for a, b in zip(color_a, color_b, strict=True)
            )
            x = left + column * cell_width
            y = top + plot_height - (row + 1) * cell_height
            cells.append(
                f"<rect x='{x:.2f}' y='{y:.2f}' width='{cell_width + 0.2:.2f}' "
                f"height='{cell_height + 0.2:.2f}' fill='rgb{color}'/>"
            )
    duration = len(data) / sample_rate
    return (
        f"<svg viewBox='0 0 {width:g} {height:g}' role='img' "
        "aria-label='Short-time Fourier transform spectrogram of the analysed audio' "
        "xmlns='http://www.w3.org/2000/svg'>"
        "<title>Processed audio spectrogram, magnitude relative to full scale</title>"
        f"<g shape-rendering='crispEdges'>{''.join(cells)}</g>"
        f"<text x='{left:g}' y='{height - 12:g}' font-size='12'>0 s</text>"
        f"<text x='{left + plot_width:g}' y='{height - 12:g}' text-anchor='end' "
        f"font-size='12'>{duration:.2f} s</text>"
        f"<text x='10' y='25' font-size='12'>Frequency (Hz)</text>"
        f"<text x='{left - 8:g}' y='{top + plot_height:g}' "
        "text-anchor='end' font-size='11'>0</text>"
        f"<text x='{left - 8:g}' y='{top + 9:g}' text-anchor='end' font-size='11'>"
        f"{frequency_limit:g}</text></svg>"
    )


def render_voice_report_html(
    report: dict,
    *,
    processed_samples: np.ndarray | None = None,
    sample_rate: int | None = None,
) -> str:
    """Render actual session values and charts as a local, dependency-free HTML file."""
    quality = report.get("audio_quality", {})
    preprocessing = report.get("preprocessing", {})
    features = report.get("features", {})
    provenance = report.get("feature_provenance", {})
    model = report.get("model_assessment", {})
    rows = []
    for definition in FEATURE_DEFINITIONS:
        value, status = _display_value(features.get(definition.name))
        rows.append(
            "<tr>"
            f"<th scope='row'><code>{html.escape(definition.name)}</code></th>"
            f"<td>{html.escape(value)}</td>"
            f"<td>{html.escape(definition.units)}</td>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{html.escape(definition.method)}. Validity: "
            f"{html.escape(definition.validity)}.</td></tr>"
        )
    warnings = quality.get("warnings") or []
    errors = quality.get("errors") or []
    notices = "".join(f"<li>{html.escape(str(item))}</li>" for item in [*errors, *warnings])
    if not notices:
        notices = "<li>No quality warnings were recorded.</li>"
    sample_rate = int(sample_rate or preprocessing.get("target_sample_rate_hz") or 0)
    waveform = (
        _waveform_svg(processed_samples, sample_rate)
        if processed_samples is not None and sample_rate > 0
        else "<p class='empty'>Waveform is not available in this report.</p>"
    )
    spectrogram = (
        _spectrogram_svg(processed_samples, sample_rate)
        if processed_samples is not None and sample_rate > 0
        else "<p class='empty'>Spectrogram is not available in this report.</p>"
    )
    quality_rows = []
    for label, key, unit in (
        ("Recording duration", "duration_seconds", "s"),
        ("Original sample rate", "sample_rate_hz", "Hz"),
        ("Channels", "channels", ""),
        ("Peak amplitude", "peak_amplitude_fs", "full scale"),
        ("RMS amplitude", "rms_amplitude_fs", "full scale"),
        ("Clipping fraction", "clipping_fraction", "fraction"),
        ("Voiced fraction", "voiced_fraction", "fraction"),
        ("Active fraction", "active_fraction", "fraction"),
    ):
        value, _ = _display_value(quality.get(key))
        quality_rows.append(
            f"<tr><th scope='row'>{html.escape(label)}</th>"
            f"<td>{html.escape(value)} {html.escape(unit)}</td></tr>"
        )
    audio_sha256 = quality.get("audio_sha256")
    if audio_sha256 and isinstance(audio_sha256, str):
        escaped_hash = html.escape(audio_sha256)
        quality_rows.append(
            "<tr><th scope='row'>Recorded audio SHA-256</th>"
            f"<td><code>{escaped_hash}</code> (recorded digest for provenance)</td></tr>"
        )
    preprocessing_rows = []
    for key, value in preprocessing.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            shown, _ = _display_value(value)
            if isinstance(value, str):
                shown = value
            elif isinstance(value, bool):
                shown = str(value)
            preprocessing_rows.append(
                f"<tr><th scope='row'>{html.escape(str(key).replace('_', ' '))}</th>"
                f"<td>{html.escape(shown)}</td></tr>"
            )
    report_id = html.escape(str(report.get("generated_utc", "session")))
    status = html.escape(str(model.get("status", "No model assessment available.")))
    disclaimer = html.escape(str(report.get("clinical_disclaimer", "Research use only.")))
    feature_version = html.escape(str(provenance.get("schema_version", "unknown")))
    schema_fingerprint = html.escape(str(provenance.get("schema_fingerprint", "unknown")))
    tmpl = Template(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VoxNeuro acoustic analysis report</title>
<style>
:root{color-scheme:light;--ink:#132b35;--muted:#526a73;--line:#d7e1e5;--accent:#087f83}
*{box-sizing:border-box}
body{margin:0;background:#edf3f4;color:var(--ink);
font:15px/1.6 Segoe UI,Arial,sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 18px 50px}
header{background:#102a36;color:white;border-radius:14px;padding:24px}
h1{margin:0;font-size:28px}
header p{margin:6px 0;color:#d4e5e8}
section{background:white;margin-top:18px;padding:20px;border:1px solid var(--line);
border-radius:12px}
h2{margin:0 0 12px;font-size:20px}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid var(--line)}
th{font-weight:650}
code{overflow-wrap:anywhere}
.scroll{overflow-x:auto}
.charts svg{width:100%;height:auto}
.notice{padding:12px 15px;border-left:4px solid #b56d14;background:#fff8eb}
.muted,.empty,footer{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
@media(max-width:600px){main{padding:12px 8px 30px}section{padding:14px}h1{font-size:23px}}
</style></head><body><main>
<header><h1>VoxNeuro · Voice acoustic analysis</h1>
<p>Report generated: ${REPORT_ID} · Feature schema: ${SCHEMA_VERSION}</p>
<p>Research prototype; no diagnosis is produced.</p></header>
<section><h2>Recording quality</h2>
<div class="scroll"><table><tbody>${QUALITY_ROWS}</tbody></table></div>
<p><b>Quality outcome:</b> ${QUALITY_STATUS}</p><ul>${WARNINGS}</ul></section>
<section><h2>Preprocessing</h2>
<div class="scroll"><table><tbody>${PREPROCESSING_ROWS}</tbody></table></div>
</section>
<section><h2>Waveform and spectrogram</h2>
<div class="grid charts">${WAVEFORM} ${SPECTROGRAM}</div>
<p class="muted">The spectrogram shows short-time magnitude relative to digital full scale;
it is not calibrated sound-pressure level.</p></section>
<section><h2>Acoustic feature measurements</h2>
<p>All ${FEATURE_COUNT} measurements in schema ${SCHEMA_VERSION} are listed.
Undefined values remain unavailable; no clinical normal range is applied.</p>
<div class="scroll"><table><caption>Measured features and extraction definitions</caption>
<thead><tr><th scope="col">Feature</th><th scope="col">Value</th>
<th scope="col">Unit</th><th scope="col">Status</th>
<th scope="col">Method and validity</th></tr></thead>
<tbody>${FEATURE_ROWS}</tbody></table></div>
<p class="muted">Schema fingerprint: <code>${SCHEMA_FINGERPRINT}</code></p></section>
<section><h2>Model assessment</h2><p>${MODEL_STATUS}</p>
<p class="notice">${DISCLAIMER}</p>
<p>No calibrated disease probability, clinical threshold, diagnosis, or rule-out
result is provided.</p></section>
<footer>Report contents are generated from this session's measured audio and feature values.
The application does not store recordings or reports by default.</footer>
</main></body></html>"""
    )
    return tmpl.substitute(
        REPORT_ID=report_id,
        SCHEMA_VERSION=feature_version,
        SCHEMA_FINGERPRINT=schema_fingerprint,
        QUALITY_ROWS="".join(quality_rows),
        QUALITY_STATUS=(
            "Passed technical audio checks." if quality.get("valid") else "Not passed."
        ),
        WARNINGS=notices,
        PREPROCESSING_ROWS="".join(preprocessing_rows),
        WAVEFORM=f"<figure><figcaption>Processed waveform</figcaption>{waveform}</figure>",
        SPECTROGRAM=(
            f"<figure><figcaption>Short-time Fourier spectrogram</figcaption>{spectrogram}</figure>"
        ),
        FEATURE_COUNT=str(len(FEATURE_NAMES)),
        FEATURE_ROWS="".join(rows),
        MODEL_STATUS=status,
        DISCLAIMER=disclaimer,
    )
