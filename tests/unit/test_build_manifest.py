import pandas as pd
import pytest
from scripts.build_manifest import (
    class_from_audio_path,
    normalize_label,
    validate_duplicate_metadata,
)


@pytest.mark.parametrize(
    ("source", "normalized"),
    [("PwPD", "PD"), ("PD", "PD"), ("HC", "HC"), ("healthy control", "HC")],
)
def test_normalize_label_accepts_only_explicit_known_labels(source, normalized):
    assert normalize_label(source) == normalized


@pytest.mark.parametrize("source", [None, float("nan"), "", "unknown", "unclassified"])
def test_normalize_label_rejects_missing_or_unknown_values(source):
    with pytest.raises(ValueError):
        normalize_label(source)


def test_folder_mapping_requires_an_exact_known_class_folder():
    assert class_from_audio_path(__import__("pathlib").Path("data/PD_AH/sample.wav")) == "PD"
    assert class_from_audio_path(__import__("pathlib").Path("data/HC_AH/sample.wav")) == "HC"
    with pytest.raises(ValueError, match="exactly one"):
        class_from_audio_path(__import__("pathlib").Path("data/other/sample.wav"))


def test_duplicate_normalized_sample_ids_must_have_consistent_metadata():
    consistent = pd.DataFrame(
        {
            "__sample_key": ["sample-a", "sample-a"],
            "Label": ["PwPD", "PD"],
            "Age": [64, 64],
            "Sex": ["F", "F"],
        }
    )
    validate_duplicate_metadata(consistent, "__sample_key", "Label")

    inconsistent = consistent.copy()
    inconsistent.loc[1, "Age"] = 65
    with pytest.raises(ValueError, match="Conflicting workbook rows"):
        validate_duplicate_metadata(inconsistent, "__sample_key", "Label")
