# WAV analysis guide

## Streamlit application

Start the local application:

    uv sync --all-extras --locked
    uv run streamlit run app.py --server.address 127.0.0.1

Open the local address printed by Streamlit. Select Voice assessment, record a sustained /a/ or upload a WAV, and choose Analyze this recording. The app validates the file, shows signal quality, waveform and spectrogram, extracts the Core39 measurements, and offers a self-contained HTML report.

## Command-line acoustic analysis

Run:

    uv run python scripts/analyze_voice.py --audio path/to/recording.wav --report artifacts/reports/individual/analysis.html

The command validates a WAV, extracts the current acoustic measurements, and writes a local HTML report. It does not issue a PD/HC classification.

## Why a disease result is withheld

The available raw-audio development cohort was telephone-collected. Compatibility with laptop, smartphone, browser microphone, language, room, and other acquisition conditions has not been established. The internal grouped model results also show that age alone outperforms voice-only models in this small cohort. Therefore, showing an experimental class for an arbitrary uploaded or microphone recording would overstate what the evidence supports.

The report's model assessment should say that classification is unavailable when domain compatibility is not established. This is an intentional safety state, not a failed feature extraction. Acoustic values describe signal properties and do not diagnose or rule out Parkinson's disease.

## Report and data handling

HTML reports are local artifacts. Audio is processed in the app process and is not saved by default. Do not share an individual recording or report unless you have authority to do so. The source-review ZIP excludes participant recordings, model binaries, and generated experiment outputs.
