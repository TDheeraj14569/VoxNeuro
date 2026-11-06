import shutil
from copy import deepcopy

import pytest
import yaml

from voxneuro import config


def _write_config(tmp_path, monkeypatch, name, values):
    config_dir = tmp_path / "configs"
    shutil.copytree(config.PROJECT_ROOT / "configs", config_dir, dirs_exist_ok=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (config_dir / name).write_text(yaml.safe_dump(values), encoding="utf-8")


@pytest.mark.parametrize(
    "name",
    [
        "application_config.yaml",
        "audio_config.yaml",
        "feature_config.yaml",
        "model_config.yaml",
        "reviewed_exclusions.yaml",
    ],
)
def test_all_checked_in_configurations_pass_typed_validation(name):
    assert config.load_config(name)


@pytest.mark.parametrize(
    ("name", "updates", "message"),
    [
        ("application_config.yaml", {"store_recordings": "false"}, "store_recordings"),
        ("application_config.yaml", {"unexpected": 1}, "unknown keys"),
        ("audio_config.yaml", {"min_rms": True}, "finite number"),
        ("audio_config.yaml", {"min_duration_seconds": 40.0}, "less than"),
        (
            "feature_config.yaml",
            {"pitch_floor_hz": 400, "pitch_ceiling_hz": 300},
            "less than",
        ),
        ("feature_config.yaml", {"hop_samples": 2048}, "cannot exceed"),
        ("model_config.yaml", {"cv_splits": 1}, "cv_splits"),
        ("model_config.yaml", {"inner_cv_splits": 1}, "inner_cv_splits"),
        ("model_config.yaml", {"cv_repeats": 0}, "cv_repeats"),
        ("model_config.yaml", {"bootstrap_iterations": 10}, "bootstrap_iterations"),
        (
            "model_config.yaml",
            {"allow_user_microphone_inference": True},
            "not supported",
        ),
    ],
)
def test_configuration_loader_rejects_invalid_types_ranges_and_unknown_keys(
    tmp_path, monkeypatch, name, updates, message
):
    values = deepcopy(config.load_config(name))
    values.update(updates)
    _write_config(tmp_path, monkeypatch, name, values)

    with pytest.raises(ValueError, match=message):
        config.load_config(name)


@pytest.mark.parametrize("mfcc_count", [12, 14])
def test_feature_configuration_requires_the_schema_mfcc_count(tmp_path, monkeypatch, mfcc_count):
    values = deepcopy(config.load_config("feature_config.yaml"))
    values["mfcc_count"] = mfcc_count
    _write_config(tmp_path, monkeypatch, "feature_config.yaml", values)

    with pytest.raises(ValueError, match="exactly 13 MFCC coefficients"):
        config.load_config("feature_config.yaml")


def test_feature_configuration_rejects_cutoff_at_target_nyquist(tmp_path, monkeypatch):
    values = deepcopy(config.load_config("feature_config.yaml"))
    values["common_max_hz"] = 8000
    _write_config(tmp_path, monkeypatch, "feature_config.yaml", values)

    with pytest.raises(ValueError, match="strictly below the configured target.*Nyquist"):
        config.load_config("feature_config.yaml")


def test_configuration_loader_rejects_missing_keys_and_unknown_config_names(tmp_path, monkeypatch):
    values = deepcopy(config.load_config("application_config.yaml"))
    values.pop("max_upload_mb")
    _write_config(tmp_path, monkeypatch, "application_config.yaml", values)
    with pytest.raises(ValueError, match="missing keys"):
        config.load_config("application_config.yaml")
    with pytest.raises(ValueError, match="Unsupported configuration"):
        config.load_config("arbitrary.yaml")


def test_reviewed_exclusion_config_rejects_unreviewed_entries(tmp_path, monkeypatch):
    values = deepcopy(config.load_config("reviewed_exclusions.yaml"))
    first_sample = next(iter(values["reviewed_exclusions"]))
    values["reviewed_exclusions"][first_sample]["review_status"] = "pending"
    _write_config(tmp_path, monkeypatch, "reviewed_exclusions.yaml", values)

    with pytest.raises(ValueError, match="not an accepted reviewed category"):
        config.load_config("reviewed_exclusions.yaml")
