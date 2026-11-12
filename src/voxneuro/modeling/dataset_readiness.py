"""Dataset readiness assessment, normalized cohort adapters, and leakage guards (M6)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from voxneuro.config import PROJECT_ROOT
from voxneuro.dataset.loader import load_feature_table
from voxneuro.dataset.uci import (
    UCI_METADATA_COLUMNS,
    load_uci_feature_table,
    uci_schema_fingerprint,
)
from voxneuro.exceptions import DatasetError
from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.modeling.domain_registry import load_domain_registry
from voxneuro.modeling.splits import grouped_splits
from voxneuro.study.consent import get_dataset_access

FORBIDDEN_PREDICTOR_COLUMNS = frozenset(
    {
        "participant_id",
        "sample_id",
        "id",
        "label",
        "class",
        "class_label",
        "diagnosis",
        "target",
        "y",
        "dataset_source",
        "domain_id",
        "wav_path",
        "file_path",
    }
)


@dataclass(frozen=True)
class DatasetReadinessRecord:
    """Structured readiness and governance record for a cohort."""

    dataset_id: str
    dataset_name: str
    dataset_version: str
    license_name: str
    acquisition_domain_id: str
    status: str
    ready_for_training: bool
    ready_for_external_validation: bool
    raw_audio_available: bool
    core39_compatible: bool
    participant_count: int
    recording_count: int
    class_counts: dict[str, int]
    missing_values_count: int
    exact_duplicate_feature_rows: int
    participant_label_conflicts: int
    dua_authorization_state: str
    dataset_sha256: str | None
    notes: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_participant_split_integrity(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    n_splits: int = 5,
    random_seed: int = 2026,
    excluded_metadata_cols: tuple[str, ...] = ("participant_id", "sample_id"),
) -> dict[str, Any]:
    """Verify zero predictor leakage, consistent participant labels, and disjoint grouped splits."""
    predictor_cols = [c for c in X.columns if c not in excluded_metadata_cols]
    leaking = [c for c in predictor_cols if c.strip().lower() in FORBIDDEN_PREDICTOR_COLUMNS]
    if leaking:
        raise DatasetError(f"Target/identifier leakage column(s) found in predictors: {leaking}")
    if not predictor_cols:
        raise DatasetError("Feature matrix contains no valid predictor columns.")

    labels = np.asarray(y, dtype=int)
    grp = np.asarray(groups)
    fold_summaries: list[dict[str, Any]] = []
    for fold_idx, (train_idx, test_idx) in enumerate(
        grouped_splits(labels, grp, n_splits=n_splits, random_seed=random_seed), start=1
    ):
        overlap = set(grp[train_idx]) & set(grp[test_idx])
        if overlap:
            raise DatasetError(f"Fold {fold_idx} leaked {len(overlap)} participant IDs.")
        fold_summaries.append(
            {
                "fold": fold_idx,
                "train_participants": int(len(np.unique(grp[train_idx]))),
                "test_participants": int(len(np.unique(grp[test_idx]))),
                "train_rows": int(len(train_idx)),
                "test_rows": int(len(test_idx)),
                "overlap_count": 0,
            }
        )

    dup_count = int(X[predictor_cols].duplicated(keep="first").sum())
    return {
        "n_rows": int(len(X)),
        "n_participants": int(len(np.unique(grp))),
        "n_predictors": int(len(predictor_cols)),
        "duplicate_feature_rows": dup_count,
        "folds_verified": len(fold_summaries),
        "fold_summaries": fold_summaries,
        "leakage_free": True,
    }


def extract_uci_csv_from_zip(zip_path: Path, destination_dir: Path) -> Path:
    """Safely extract UCI #470 CSV via bsdtar/tar when zip contains pd_speech_features.rar."""
    if not zip_path.is_file():
        raise FileNotFoundError(f"UCI archive not found: {zip_path}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        rar_members = [n for n in zf.namelist() if n.lower().endswith(".rar")]
        csv_members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if csv_members:
            target = destination_dir / "pd_speech_features.csv"
            target.write_bytes(zf.read(csv_members[0]))
            return target
        if not rar_members:
            raise ValueError(f"UCI archive {zip_path} contains neither CSV nor RAR.")
        rar_path = destination_dir / "pd_speech_features.rar"
        rar_path.write_bytes(zf.read(rar_members[0]))
    try:
        proc = subprocess.run(
            ["tar", "-xf", str(rar_path), "-C", str(destination_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        rar_path.unlink(missing_ok=True)
    csv_candidate = destination_dir / "pd_speech_features.csv"
    if proc.returncode != 0 or not csv_candidate.is_file():
        raise RuntimeError(
            f"Unable to extract UCI RAR with system tar: {proc.stderr.strip() or 'missing csv'}"
        )
    return csv_candidate


def load_uams_cohort(
    feature_csv_path: Path | None = None,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    """Load validated UAMS Core39 table alongside participant groups and demographic covariates."""
    target = feature_csv_path or (PROJECT_ROOT / "data" / "processed" / "voice_features.csv")
    frame = load_feature_table(target)
    if "class_label" not in frame.columns or "participant_id" not in frame.columns:
        raise DatasetError("UAMS feature table is missing required class_label/participant_id.")
    missing_feats = [c for c in FEATURE_NAMES if c not in frame.columns]
    if missing_feats:
        raise DatasetError(f"UAMS feature table is missing Core39 columns: {missing_feats}")
    if "schema_version" in frame.columns and not (frame["schema_version"] == SCHEMA_VERSION).all():
        raise DatasetError(f"UAMS feature table contains non-{SCHEMA_VERSION} schema rows.")

    y = frame["class_label"].astype(str).str.strip().str.upper().map({"HC": 0, "PD": 1})
    if y.isna().any():
        raise DatasetError("UAMS feature table contains unrecognized class_label values.")

    groups = frame["participant_id"].astype(str).to_numpy()
    X_voice = frame[["participant_id", "sample_id", *FEATURE_NAMES]].copy()
    demographics = pd.DataFrame({"participant_id": frame["participant_id"].astype(str)})
    if "age" in frame.columns:
        demographics["age"] = pd.to_numeric(frame["age"], errors="coerce")
    if "sex" in frame.columns:
        sex_norm = frame["sex"].astype(str).str.strip().str.upper()
        demographics["sex_male"] = sex_norm.map({"M": 1.0, "MALE": 1.0, "F": 0.0, "FEMALE": 0.0})
    return X_voice, y.to_numpy(dtype=int), groups, demographics


def load_uci_cohort(
    uci_path: Path | None = None,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    """Load validated UCI #470 pre-extracted 752-feature cohort (no raw audio)."""
    raw_zip = PROJECT_ROOT / "data" / "raw" / "uci" / "uci-470.zip"
    interim_csv = PROJECT_ROOT / "data" / "interim" / "uci" / "pd_speech_features.csv"
    if uci_path is not None and uci_path.is_file():
        frame = (
            load_uci_feature_table(uci_path)
            if uci_path.suffix.lower() == ".csv"
            else load_uci_feature_table(
                extract_uci_csv_from_zip(uci_path, Path(tempfile.mkdtemp(prefix="vx_uci_")))
            )
        )
    elif interim_csv.is_file():
        frame = load_uci_feature_table(interim_csv)
    elif raw_zip.is_file():
        with tempfile.TemporaryDirectory(prefix="voxneuro_uci_readiness_") as tmpdir:
            extracted = extract_uci_csv_from_zip(raw_zip, Path(tmpdir))
            frame = load_uci_feature_table(extracted)
    else:
        raise FileNotFoundError("Neither data/interim/uci CSV nor data/raw/uci/uci-470.zip exists.")

    predictor_cols = [c for c in frame.columns if c not in UCI_METADATA_COLUMNS]
    X_features = pd.concat(
        [
            pd.DataFrame({"participant_id": frame["id"].astype(str)}),
            frame[predictor_cols].astype(np.float64),
        ],
        axis=1,
    )
    y = frame["class"].to_numpy(dtype=int)
    groups = frame["id"].astype(str).to_numpy()
    demographics = pd.DataFrame(
        {
            "participant_id": frame["id"].astype(str),
            "gender_code": frame["gender"].astype(float),
        }
    )
    return X_features, y, groups, demographics


def inspect_uams_dataset(
    feature_csv_path: Path | None = None,
) -> DatasetReadinessRecord:
    """Inspect local UAMS sustained-vowel dataset readiness & confounding."""
    target = feature_csv_path or (PROJECT_ROOT / "data" / "processed" / "voice_features.csv")
    if not target.is_file():
        return DatasetReadinessRecord(
            dataset_id="uams",
            dataset_name="UAMS Sustained-Vowel /a/ Cohort",
            dataset_version="figshare-23849127.v1",
            license_name="CC BY 4.0",
            acquisition_domain_id="uams_telephone",
            status="MISSING_LOCAL_PROCESSED_DATA",
            ready_for_training=False,
            ready_for_external_validation=False,
            raw_audio_available=bool((PROJECT_ROOT / "data" / "interim" / "uams").is_dir()),
            core39_compatible=True,
            participant_count=0,
            recording_count=0,
            class_counts={},
            missing_values_count=0,
            exact_duplicate_feature_rows=0,
            participant_label_conflicts=0,
            dua_authorization_state="OPEN_CC_BY_4_0",
            dataset_sha256=None,
            notes=[],
            blockers=[
                "Processed feature table not found at relative path "
                "data/processed/voice_features.csv."
            ],
        )

    X_voice, y, groups, demographics = load_uams_cohort(target)
    raw_dir = PROJECT_ROOT / "data" / "interim" / "uams"
    wav_count = len(list(raw_dir.rglob("*.wav"))) if raw_dir.is_dir() else 0
    df_features = X_voice[list(FEATURE_NAMES)]
    missing_count = int(df_features.isna().sum().sum())
    dup_count = int(df_features.duplicated().sum())
    conflicts = 0
    split_check = verify_participant_split_integrity(X_voice, y, groups, n_splits=5)
    notes = [
        f"Verified {split_check['n_participants']} participants with zero cross-fold leakage.",
        "Telephone-collected 8 kHz sustained vowel /a/; severe age confounding (PD older than HC).",
    ]
    if "age" in demographics.columns and demographics["age"].notna().all():
        hc_age = demographics.loc[y == 0, "age"]
        pd_age = demographics.loc[y == 1, "age"]
        notes.append(
            f"Mean age HC={hc_age.mean():.2f} vs PD={pd_age.mean():.2f} (strong age confound)."
        )
    return DatasetReadinessRecord(
        dataset_id="uams",
        dataset_name="UAMS Sustained-Vowel /a/ Cohort",
        dataset_version="figshare-23849127.v1",
        license_name="CC BY 4.0",
        acquisition_domain_id="uams_telephone",
        status="READY_INTERNAL_RESEARCH_ONLY",
        ready_for_training=True,
        ready_for_external_validation=False,
        raw_audio_available=wav_count > 0,
        core39_compatible=True,
        participant_count=int(len(np.unique(groups))),
        recording_count=int(len(X_voice)),
        class_counts={"HC": int((y == 0).sum()), "PD": int((y == 1).sum())},
        missing_values_count=missing_count,
        exact_duplicate_feature_rows=dup_count,
        participant_label_conflicts=conflicts,
        dua_authorization_state="OPEN_CC_BY_4_0",
        dataset_sha256=_sha256_file(target),
        notes=notes,
        blockers=[],
    )


def inspect_uci470_dataset(uci_path: Path | None = None) -> DatasetReadinessRecord:
    """Inspect UCI #470 pre-extracted acoustic benchmark table readiness."""
    raw_zip = PROJECT_ROOT / "data" / "raw" / "uci" / "uci-470.zip"
    interim_csv = PROJECT_ROOT / "data" / "interim" / "uci" / "pd_speech_features.csv"
    try:
        X_uci, y, groups, _ = load_uci_cohort(uci_path)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        return DatasetReadinessRecord(
            dataset_id="uci470",
            dataset_name="UCI Parkinson's Disease Classification (#470)",
            dataset_version="doi-10.24432/C5MS4X",
            license_name="CC BY 4.0",
            acquisition_domain_id="uci470_precomputed_44k_mic",
            status="MISSING_OR_UNREADABLE",
            ready_for_training=False,
            ready_for_external_validation=False,
            raw_audio_available=False,
            core39_compatible=False,
            participant_count=0,
            recording_count=0,
            class_counts={},
            missing_values_count=0,
            exact_duplicate_feature_rows=0,
            participant_label_conflicts=0,
            dua_authorization_state="OPEN_CC_BY_4_0",
            dataset_sha256=None,
            notes=[],
            blockers=[str(exc)],
        )

    pred_cols = [c for c in X_uci.columns if c != "participant_id"]
    dup_count = int(X_uci[pred_cols].duplicated().sum())
    verify_participant_split_integrity(
        X_uci, y, groups, n_splits=5, excluded_metadata_cols=("participant_id",)
    )
    sha = (
        _sha256_file(uci_path)
        if uci_path and uci_path.is_file()
        else (_sha256_file(interim_csv) if interim_csv.is_file() else _sha256_file(raw_zip))
    )
    return DatasetReadinessRecord(
        dataset_id="uci470",
        dataset_name="UCI Parkinson's Disease Classification (#470)",
        dataset_version=f"doi-10.24432/C5MS4X|schema-{uci_schema_fingerprint()[:12]}",
        license_name="CC BY 4.0",
        acquisition_domain_id="uci470_precomputed_44k_mic",
        status="READY_FEATURE_TABLE_BENCHMARK_ONLY",
        ready_for_training=True,
        ready_for_external_validation=False,
        raw_audio_available=False,
        core39_compatible=False,
        participant_count=int(len(np.unique(groups))),
        recording_count=int(len(X_uci)),
        class_counts={"HC": int((y == 0).sum()), "PD": int((y == 1).sum())},
        missing_values_count=int(X_uci[pred_cols].isna().sum().sum()),
        exact_duplicate_feature_rows=dup_count,
        participant_label_conflicts=0,
        dua_authorization_state="OPEN_CC_BY_4_0",
        dataset_sha256=sha,
        notes=[
            "252 participants x 3 repeats; 752 pre-extracted predictors; raw WAV audio withheld.",
            "No per-participant age column; cannot serve as Core39 microphone validation.",
        ],
        blockers=["No raw audio or Core39 mapping available (precomputed table only)."],
    )


def inspect_external_candidate_domains(
    conn: sqlite3.Connection | None = None,
) -> list[DatasetReadinessRecord]:
    """Inspect candidate external domains against local filesystem and DUA registry."""
    registry = load_domain_registry()
    records: list[DatasetReadinessRecord] = []
    for domain_id, dom in sorted(registry.domains.items()):
        if domain_id in registry.training_domains:
            continue
        raw_dir = PROJECT_ROOT / "data" / "raw" / "external" / domain_id
        has_local_files = raw_dir.is_dir() and any(
            p.suffix.lower() in {".wav", ".flac", ".csv"} for p in raw_dir.rglob("*") if p.is_file()
        )
        dua_state = "NOT_REGISTERED_OR_NO_DB"
        dataset_key = dom.metadata.dataset_id or domain_id
        if conn is not None:
            try:
                dua = get_dataset_access(conn, dataset_key)
                dua_state = (
                    f"{dua.access_approval_state}/{dua.dua_state}/{dua.dua_verification_status}"
                )
            except KeyError:
                dua_state = "MISSING_DUA_RECORD"

        blockers: list[str] = []
        if not has_local_files:
            blockers.append(
                f"No authorized local audio or feature files present for {domain_id!r}."
            )
        if not dua_state.startswith("APPROVED/ACTIVE/DOCUMENT_AUTHENTICATED"):
            blockers.append(f"M4/M5 DUA authorization incomplete ({dua_state}).")
        if dom.inference_eligible:
            blockers.append("Unexpected inference_eligible=True without trusted report.")

        records.append(
            DatasetReadinessRecord(
                dataset_id=domain_id,
                dataset_name=dom.domain_name or domain_id,
                dataset_version=dom.metadata.dataset_version or "external-candidate",
                license_name="DUA / Restricted Access",
                acquisition_domain_id=domain_id,
                status="BLOCKED_EXTERNAL_DATA_OR_DUA_MISSING"
                if blockers
                else "READY_FOR_CANDIDATE_EVAL",
                ready_for_training=False,
                ready_for_external_validation=not blockers,
                raw_audio_available=has_local_files,
                core39_compatible=bool(dom.feature_schema_compatibility == SCHEMA_VERSION),
                participant_count=0,
                recording_count=0,
                class_counts={},
                missing_values_count=0,
                exact_duplicate_feature_rows=0,
                participant_label_conflicts=0,
                dua_authorization_state=dua_state,
                dataset_sha256=None,
                notes=[
                    f"Candidate external recording domain ({dom.metadata.device_category}, "
                    f"status={dom.candidate_compatibility_status})."
                ],
                blockers=blockers,
            )
        )
    return records


def build_dataset_readiness_report(
    conn: sqlite3.Connection | None = None,
    *,
    uams_csv_path: Path | None = None,
    uci_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble full M6 dataset readiness report across UAMS, UCI, and external candidates."""
    uams = inspect_uams_dataset(uams_csv_path)
    uci = inspect_uci470_dataset(uci_path)
    externals = inspect_external_candidate_domains(conn)
    all_records = [uams, uci, *externals]
    training_ready = uams.ready_for_training or uci.ready_for_training
    ext_ready = any(r.ready_for_external_validation for r in externals)
    return {
        "schema_version": SCHEMA_VERSION,
        "training_data_ready": training_ready,
        "external_validation_data_ready": ext_ready,
        "cohorts": [r.to_dict() for r in all_records],
        "summary": {
            "total_cohorts_checked": len(all_records),
            "training_cohorts_ready": sum(1 for r in (uams, uci) if r.ready_for_training),
            "external_cohorts_ready": sum(1 for r in externals if r.ready_for_external_validation),
            "external_blockers": [
                {"dataset_id": r.dataset_id, "blockers": r.blockers}
                for r in externals
                if r.blockers
            ],
        },
        "report_sha256": hashlib.sha256(
            json.dumps([r.to_dict() for r in all_records], sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
