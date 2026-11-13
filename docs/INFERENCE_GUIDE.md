# Individual recording analysis and model-result states

## Run the local app

```powershell
uv sync --all-extras --locked
uv run streamlit run app.py --server.address 127.0.0.1
```

In the app, open **Voice assessment**, record a sustained `/a/` or upload a WAV, declare the recording device category, and select **Analyze this recording**. Capture origin (file upload or live browser microphone) and acquisition device are separate fields. An upload may have come from any device; upload type does not establish the recording domain. The selected device category is a user statement, not hardware verification or evidence of compatibility.

The app validates the source audio, preprocesses it, extracts the versioned Core39 features, and creates a report. The blue **Audio quality checks passed** state means only that the signal passed configured technical checks for measurement. It is not a health assessment and does not mean that the person is healthy or has Parkinson's disease. If the source is known, UAMS cohort recordings use **Telephone / PSTN**; a WAV upload by itself does not establish that source.

## Three result states

1. **Approved prediction:** unavailable in this release. No domain has an approved validation report in the trusted allowlist, and `allow_user_microphone_inference` remains false. The user-facing exploratory path does not change this gate.
2. **Exploratory candidate:** can appear only when the local, internally generated research model and all current provenance/evaluation receipts are present and verified; quality, task, schema, feature completeness, acquisition-context, and training-only out-of-distribution checks pass; and a device category is explicitly supplied. The UI calls the output an **EXPLORATORY — NOT DOMAIN VALIDATED** candidate, reports its raw uncalibrated model score and fixed decision threshold (never a probability), and shows evaluation metrics and OOD findings. It is not a diagnostic or screening result and must not influence care.
3. **Abstention:** appears when the candidate cannot be safely computed. The interface gives the specific failure reason (for example, missing model/evidence, unknown device category, invalid quality, incompatible task/schema, or severe out-of-distribution input). Audio quality and acoustic feature results remain available when those analyses succeeded.

The checked-in source release intentionally excludes participant recordings, model binaries, and generated evaluation receipts. Therefore a clean extraction normally has no individual model candidate to show until the researcher downloads the data under its license and completes the documented audit → extraction → fixed evaluation → nested evaluation → training → model verification sequence. See the [README](../README.md) and [reproducibility guide](REPRODUCIBILITY.md). Do not substitute a synthetic model or a stale receipt.

When a local upload is byte-for-byte identical to a WAV in the model-development dataset manifest, the app withholds an individual score with `KNOWN_TRAINING_RECORDING`. The full-refit model has seen that recording, so its individual score would be in-sample and misleading, even if the dataset's reference label is PD. Use participant-grouped out-of-fold evaluation to assess known cohort files; it holds each evaluated participant out of that fold's training data. The reference label and a model prediction are separate facts.

## Research-model evidence

The current local UAMS experiment uses participant-grouped nested cross-validation. Its age-only comparator exceeds the voice-only logistic reference, and the cohort is small, retrospective, telephone-collected, and affected by three PD-only clipping exclusions. The L2 logistic reference misses some PD-labeled participants in held-out folds; the app must not be forced to show PD for every PD-labeled recording. These facts are shown alongside internal metrics. Internal cross-validation does not demonstrate independent, prospective, population-specific, device, or clinical performance. The generated model is research-only, refit on the development cohort, and is not validated for individual disease assessment.

The UCI #470 experiment is a separate pre-extracted-feature benchmark. It is not raw WAV validation and does not establish microphone compatibility.

## Reports and data handling

The HTML/JSON reports retain audio-quality findings, feature schema/provenance, and the model outcome state. When inference abstains, successful acoustic measurements are still reportable. Reports do not convert acoustic measurements into a diagnosis. Audio is processed in the local app process and is not saved by default; downloaded reports are saved only when the user chooses to download them. A voice can itself be identifying.
