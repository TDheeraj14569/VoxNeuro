"""Unit tests for domain shift analysis, standardized mean difference, and FDR corrections."""

import json

import numpy as np
import pandas as pd
import pytest
from scripts.generate_m4_review_evidence import generate_domain_shift_evidence

from voxneuro.features.schema import FEATURE_NAMES
from voxneuro.modeling.domain_shift import (
    benjamini_hochberg_fdr,
    compare_acquisition_metadata,
    compute_feature_shift,
    compute_standardized_mean_difference,
    summarize_domain_shift,
)


def test_compare_acquisition_metadata():
    ref = {
        "device_category": "telephone",
        "microphone_type": "carbon_mouthpiece",
        "original_sample_rate": 16000,
        "recording_environment": "telephone_network",
        "audio_codec": "pcm_s16le",
    }
    cand = {
        "device_category": "studio_microphone",
        "microphone_type": "electret_condenser",
        "original_sample_rate": 44100,
        "recording_environment": "sound_treated_booth",
        "audio_codec": "pcm_s16le",
    }
    diffs = compare_acquisition_metadata(ref, cand)
    assert len(diffs) == 4
    assert any("Device category mismatch" in d for d in diffs)
    assert any("44100 Hz" in d for d in diffs)


def test_standardized_mean_difference_calculation():
    # Identical vectors -> SMD = 0
    v1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert compute_standardized_mean_difference(v1, v1) == 0.0

    # Offset vectors
    v2 = v1 + 2.0
    smd = compute_standardized_mean_difference(v1, v2)
    assert smd > 0.0
    assert abs(smd - (2.0 / np.std(v1, ddof=1))) < 1e-5


def test_benjamini_hochberg_fdr_monotonicity():
    p_vals = [0.01, 0.04, 0.03, 0.20, 0.80]
    q_vals = benjamini_hochberg_fdr(p_vals)
    assert len(q_vals) == len(p_vals)
    assert all(0.0 <= q <= 1.0 for q in q_vals)
    # Check that rank ordering is consistent
    assert q_vals[0] <= q_vals[2] <= q_vals[1]


def test_feature_shift_and_summary_generation():
    np.random.seed(2026)
    feat_names = ["f0_mean_hz", "jitter_local", "shimmer_local"]
    ref_df = pd.DataFrame(np.random.normal(100, 10, (40, 3)), columns=feat_names)
    # Shift f0_mean_hz substantially, leave shimmer identical
    cand_df = pd.DataFrame(
        {
            "f0_mean_hz": np.random.normal(150, 10, 40),
            "jitter_local": np.random.normal(105, 10, 40),
            "shimmer_local": np.random.normal(100, 10, 40),
        }
    )

    shift_df = compute_feature_shift(ref_df, cand_df, feature_names=feat_names)
    assert len(shift_df) == 3
    assert "p_value_fdr" in shift_df.columns
    assert "p_value_bonferroni" in shift_df.columns

    # f0_mean_hz should be highly significant
    f0_row = shift_df.loc[shift_df["feature"] == "f0_mean_hz"].iloc[0]
    assert bool(f0_row["shift_significant_fdr"]) is True
    assert f0_row["abs_smd"] > 2.0

    summary = summarize_domain_shift(shift_df, ["Acoustic difference"])
    assert summary.n_features_evaluated == 3
    assert summary.n_features_significant_shift_fdr >= 1
    assert summary.max_absolute_smd is not None


def test_compute_feature_shift_rejects_identical_self_comparison():
    """Identical datasets must NEVER be labelled as an independent external comparison."""
    df = pd.DataFrame({"f0_mean_hz": [120.0, 130.0], "jitter_local": [0.01, 0.02]})
    with pytest.raises(ValueError, match="Reference and candidate feature tables are identical"):
        compute_feature_shift(df, df)


def test_generate_domain_shift_evidence_pending_when_no_external_data(tmp_path):
    """When no external features exist, generator must write pending JSON and empty CSV."""
    csv_p, json_p = generate_domain_shift_evidence(tmp_path)
    assert csv_p.is_file()
    assert json_p.is_file()

    # CSV has headers only (zero data rows)
    csv_df = pd.read_csv(csv_p)
    assert len(csv_df) == 0
    assert "feature" in csv_df.columns
    assert "smd_cohen_d" in csv_df.columns

    # JSON has explicit pending status
    data = json.loads(json_p.read_text(encoding="utf-8"))
    assert data["status"] == "DOMAIN_VALIDATION_PENDING"
    assert data["comparison_performed"] is False
    assert data["features_evaluated"] == 0
    assert data["domain_shift_metrics"] is None
    assert "No eligible independent" in data["reason"]


def test_generate_domain_shift_evidence_with_external_data(tmp_path):
    """When genuine external data is provided, generator must compute actual comparison metrics."""
    ref_csv = tmp_path / "ref_features.csv"
    cand_csv = tmp_path / "cand_features.csv"
    rng = np.random.default_rng(2026)
    ref_data = {fn: rng.normal(100.0, 10.0, 30) for fn in FEATURE_NAMES}
    ref_data["participant_id"] = [f"REF_{i:03d}" for i in range(30)]
    pd.DataFrame(ref_data).to_csv(ref_csv, index=False)

    data = {fn: rng.normal(50.0, 5.0, 30) for fn in FEATURE_NAMES}
    data["participant_id"] = [f"EXT_{i:03d}" for i in range(30)]
    pd.DataFrame(data).to_csv(cand_csv, index=False)

    csv_p, json_p = generate_domain_shift_evidence(
        tmp_path,
        candidate_features_path=cand_csv,
        candidate_domain_id="neurovoz_studio",
        reference_features_path=ref_csv,
    )
    assert csv_p.is_file()
    assert json_p.is_file()

    csv_df = pd.read_csv(csv_p)
    assert len(csv_df) == len(FEATURE_NAMES)
    assert (csv_df["evaluation_status"] == "EVALUATED").all()

    data = json.loads(json_p.read_text(encoding="utf-8"))
    assert data["status"] == "DOMAIN_SHIFT_EVALUATED"
    assert data["comparison_performed"] is True
    assert data["candidate_domain"] == "neurovoz_studio"
    assert len(data["reference_dataset_checksum"]) == 64
    assert len(data["candidate_dataset_checksum"]) == 64
    assert data["features_evaluated"] == len(FEATURE_NAMES)
    assert data["domain_shift_metrics"]["features_significant_fdr"] >= 0
