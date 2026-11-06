# VoxNeuro user guide

VoxNeuro is a local research tool for technical quality checks, signal plots, and acoustic feature extraction from a sustained vowel. It does not determine whether a person has Parkinson's disease and does not classify new user recordings.

## Start the application

Use CPython 3.12 and the committed lockfile:

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv sync --all-extras --locked
uv run --locked streamlit run app.py --server.address 127.0.0.1
```

The browser opens the Overview page. The sidebar selects Overview, Voice assessment, Signal analysis, Feature analysis, Research model, Reports, or Method & privacy.

## Analyze a recording

1. Open **Voice assessment** and choose **Record with microphone** or **Upload WAV**.
2. If recording, hold `/a/` steadily for roughly 3–5 seconds in a quiet room. Keep the microphone at a steady distance. This is a task instruction, not a health threshold. Browser microphone access is requested only when you activate the recording control; WAV upload is an alternative.
3. VoxNeuro decodes the actual WAV metadata and checks duration, finite values, level, clipping, voiced frames, and stereo phase cancellation. An error message explains why a recording cannot continue.
4. A passing recording is converted according to the configured mono policy, DC corrected, silence trimmed, revalidated, and resampled to 16 kHz. Audio that fails quality checks does not proceed to feature analysis.
5. The feature workflow reports technical measurements and analysis status. A quality pass means only that software accepted the signal for analysis.

## Review results

- **Signal analysis** shows source and processed recording information, playback controls, a movable 0.5-second 3D waveform detail window, a 3D spectrogram, orbit/zoom/reset controls, and 2D plots. The 3D spectrogram uses the configured STFT window/hop and frequency cap; its displayed magnitude is dB re 1.0, not calibrated sound pressure. These views describe the audio signal and do not enter the model pipeline.
- **Feature analysis** groups the 39 versioned measures by pitch, voice stability, MFCC, and spectral summaries. Undefined measurements remain missing. VoxNeuro does not label values normal or abnormal.
- **Reports** makes JSON and CSV outputs available for explicit download. The report preserves the feature-schema version and fingerprints. It avoids filenames, local paths, diagnosis, and disease-risk scores.
- **Research model** displays grouped internal UAMS results from local research artifacts when available. It is not connected to the current recording. Age-only, voice-only, and age-plus-voice logistic comparators use the same participant folds; the combined baseline is exploratory and does not establish an independent voice effect. Group/exclusion counts, fold spread, and lack of external validation are shown.
- **Method & privacy** explains processing, local handling, and what the project has not established.

## State, saving, and clearing

The current recording and results live in the Streamlit process/session to support the workflow. They are not written to a recording folder by default. Download buttons create a file only when you request a download. Use the assessment page's clear-results control to remove current analysis state. Closing the browser/session discards that in-memory state. Research dataset scripts intentionally create local manifests, feature tables, receipts, and models under ignored `data/` and `artifacts/` directories; those are distinct from app recordings and should be handled as sensitive research data.

## Dataset and model commands

See the root README for source download instructions. UAMS and UCI have independent inspection modes. The UAMS workflow requires raw voice data and a demographics workbook; only the three documented clipping exclusions may be accepted with the explicit reviewed-exclusion flag. UCI is a repeated-record feature-table experiment and does not validate the app's raw-audio feature extraction.

## Troubleshooting

- If microphone access is denied, select **Upload WAV** and choose a supported WAV or WAVEX file.
- If upload fails, check that the file is WAV, finite, non-empty, within configured duration, and below the configured 25 MB limit.
- If quality validation fails, read the displayed reason. Do not bypass the check or interpret it medically.
- If research metrics are unavailable, check `docs/testing/VERIFICATION_REPORT.md`. Metrics require local datasets and current, matching evaluation receipts; generated results are not included in the source ZIP.
