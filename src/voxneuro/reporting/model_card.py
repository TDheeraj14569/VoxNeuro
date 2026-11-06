"""Static model card template populated from measured artifacts."""


def model_card_template() -> str:
    return """# VoxNeuro experimental model card

**Status:** Research-only; not a medical device and not clinically validated.

## Intended use

Experimental comparison of acoustic features in the documented research dataset. No individual
diagnosis, treatment, or clinical referral decision.

## Data and evaluation

See `docs/dataset/UAMS_DATASET_REPORT.md`, `docs/testing/VERIFICATION_REPORT.md`, and the
generated evaluation tables for provenance and actual measured results. Dataset samples are
participant-grouped; there is no claim of external validation.

## Limitations

Small cohort, possible demographic confounding, telephone-domain recordings, no independent
external site, no demonstrated compatibility with ordinary laptop or smartphone recordings, and
no clinical calibration.

## Risk controls

The application does not expose model predictions for new microphone input. Missing or poor-quality
signals fail closed. Voice audio may be identifying; files are not retained by default.
"""
