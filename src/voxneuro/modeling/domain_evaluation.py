"""Frozen reference-model external evaluation and participant-level bootstrap."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)

from voxneuro.config import load_config
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling.domain_assessment import (
    MetricSummary,
    QualityAttritionSummary,
)
from voxneuro.modeling.model_bundle import load_bundle
from voxneuro.modeling.trust_registry import (
    AuthorizationTrustRegistry,
    AuthorizationTrustRootError,
    SignedAuthorizationRegistry,
    authorize_reviewer_from_registry,
    authorize_source_from_registry,
    verify_signed_authorization_registry,
)
from voxneuro.provenance import project_code_fingerprint

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "models" / "uams_logistic_research.joblib"
FROZEN_REFERENCE_MODEL_SHA256 = "eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333"


def _get_valid_reference_hashes(bundle_path: Path) -> set[str]:
    """Return acceptable hashes: authoritative frozen constant and/or local sidecar."""
    valid = {FROZEN_REFERENCE_MODEL_SHA256}
    sidecar = bundle_path.parent / f"{bundle_path.name}.sha256"
    if sidecar.is_file():
        valid.add(sidecar.read_text(encoding="ascii").strip())
    return valid


def verify_frozen_model_identity(path: Path | None = None) -> dict[str, Any]:
    """Verify frozen reference model binary identity against authoritative checksum."""
    bundle_path = path or DEFAULT_MODEL_PATH
    if not bundle_path.is_file():
        return {
            "verified": False,
            "status": "MODEL_ARTIFACT_NOT_VERIFIED",
            "reason": f"Frozen reference model file not found: {bundle_path}",
            "actual_sha256": None,
            "expected_sha256": FROZEN_REFERENCE_MODEL_SHA256,
        }
    actual_hash = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    valid_hashes = _get_valid_reference_hashes(bundle_path)
    if actual_hash not in valid_hashes:
        return {
            "verified": False,
            "status": "MODEL_ARTIFACT_NOT_VERIFIED",
            "reason": (
                f"Frozen reference model checksum mismatch: "
                f"{actual_hash} != {FROZEN_REFERENCE_MODEL_SHA256}"
            ),
            "actual_sha256": actual_hash,
            "expected_sha256": FROZEN_REFERENCE_MODEL_SHA256,
        }
    return {
        "verified": True,
        "status": "MODEL_ARTIFACT_VERIFIED",
        "reason": "Frozen reference model artifact SHA-256 matches authoritative receipt.",
        "actual_sha256": actual_hash,
        "expected_sha256": actual_hash,
    }


def load_frozen_reference_model(path: Path | None = None) -> dict[str, Any]:
    """Load and cryptographically verify the frozen reference research model bundle."""
    bundle_path = path or DEFAULT_MODEL_PATH
    if not bundle_path.is_file():
        raise FileNotFoundError(
            f"Frozen reference model not found (MODEL_ARTIFACT_NOT_VERIFIED): {bundle_path}"
        )

    actual_hash = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    valid_hashes = _get_valid_reference_hashes(bundle_path)
    if path is None and actual_hash not in valid_hashes:
        raise ValueError(
            f"Frozen reference model checksum mismatch (MODEL_ARTIFACT_NOT_VERIFIED): "
            f"{actual_hash} != {FROZEN_REFERENCE_MODEL_SHA256}"
        )

    bundle = load_bundle(bundle_path)

    # Validate essential safety and schema metadata
    if bundle.get("feature_schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Frozen model feature schema version mismatch: "
            f"{bundle.get('feature_schema_version')} != {SCHEMA_VERSION}"
        )

    if bundle.get("feature_schema_fingerprint") != schema_fingerprint():
        raise ValueError("Frozen model feature schema fingerprint does not match canonical Core39.")

    feat_cfg = bundle.get("feature_config")
    if not isinstance(feat_cfg, dict) or bundle.get(
        "feature_config_fingerprint"
    ) != feature_config_fingerprint(feat_cfg):
        raise ValueError("Frozen model feature configuration fingerprint is inconsistent.")

    prep_cfg = bundle.get("preprocessing_config")
    if not isinstance(prep_cfg, dict) or bundle.get(
        "preprocessing_config_fingerprint"
    ) != configuration_fingerprint(prep_cfg):
        raise ValueError("Frozen model preprocessing configuration fingerprint is inconsistent.")

    if bundle.get("allow_user_microphone_inference") is not False:
        raise ValueError("Frozen model must enforce allow_user_microphone_inference: false.")

    return bundle


def _compute_metrics_from_arrays(
    y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None = None
) -> dict[str, float]:
    """Compute standard classification metrics for binary 0/1 vectors."""
    bacc = float(balanced_accuracy_score(y_true, y_pred))
    sens = float(recall_score(y_true, y_pred, zero_division=0))
    # Specificity = recall of negative class
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    mcc = float(matthews_corrcoef(y_true, y_pred))

    roc_auc = float("nan")
    ap = float("nan")
    if y_score is not None and len(np.unique(y_true)) > 1:
        try:
            roc_auc = float(roc_auc_score(y_true, y_score))
            ap = float(average_precision_score(y_true, y_score))
        except Exception:
            pass

    return {
        "balanced_accuracy": bacc,
        "sensitivity": sens,
        "specificity": spec,
        "precision": prec,
        "f1": f1,
        "roc_auc": roc_auc,
        "average_precision": ap,
        "mcc": mcc,
    }


def evaluate_frozen_model_on_cohort(
    bundle: dict[str, Any],
    features_df: pd.DataFrame,
    participant_col: str = "participant_id",
    target_col: str = "diagnostic_group",
    random_seed: int = 2026,
    n_bootstrap: int = 1000,
    min_subgroup_n: int = 10,
) -> dict[str, MetricSummary]:
    """Evaluate frozen model with participant-level aggregation and bootstrap uncertainty."""
    if features_df.empty:
        raise ValueError("Features DataFrame cannot be empty for cohort evaluation.")

    required_cols = {participant_col, target_col} | set(FEATURE_NAMES)
    missing = required_cols - set(features_df.columns)
    if missing:
        raise ValueError(f"Cohort evaluation DataFrame missing columns: {sorted(missing)}")

    # Aggregate to participant-level (averaging numeric features per participant)
    grouped = features_df.groupby([participant_col, target_col])[FEATURE_NAMES].mean().reset_index()

    participants = grouped[participant_col].values
    y_raw = grouped[target_col].values

    # Map labels to 0 (HC) and 1 (PD)
    y_true = np.array(
        [1 if str(v).lower() in {"pd", "1", "parkinson", "parkinsons"} else 0 for v in y_raw]
    )

    n_total = len(participants)
    n_pd = int(np.sum(y_true == 1))
    n_hc = int(np.sum(y_true == 0))

    # Safety: check sample size
    is_small_sample = (n_total < 20) or (n_pd < min_subgroup_n) or (n_hc < min_subgroup_n)

    X = grouped[FEATURE_NAMES]
    model = bundle["model"]
    y_pred = model.predict(X)

    y_score = None
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X)
            if proba.shape[1] > 1:
                y_score = proba[:, 1]
            else:
                y_score = proba[:, 0]
        except Exception:
            y_score = None
    elif hasattr(model, "decision_function"):
        try:
            y_score = model.decision_function(X)
        except Exception:
            y_score = None

    point_metrics = _compute_metrics_from_arrays(y_true, y_pred, y_score)

    if is_small_sample:
        # Small sample flag: confidence intervals are unreliable
        return {
            k: MetricSummary(
                point_estimate=v if np.isfinite(v) else None,
                ci_lower=None,
                ci_upper=None,
                status="UNRELIABLE_SMALL_SAMPLE",
            )
            for k, v in point_metrics.items()
        }

    # Stratified participant-level bootstrap
    rng = np.random.default_rng(random_seed)
    pd_indices = np.where(y_true == 1)[0]
    hc_indices = np.where(y_true == 0)[0]

    boot_results: dict[str, list[float]] = {k: [] for k in point_metrics}

    for _ in range(n_bootstrap):
        sample_pd = rng.choice(pd_indices, size=len(pd_indices), replace=True)
        sample_hc = rng.choice(hc_indices, size=len(hc_indices), replace=True)
        sample_idx = np.concatenate([sample_pd, sample_hc])

        y_boot_true = y_true[sample_idx]
        y_boot_pred = y_pred[sample_idx]
        y_boot_score = y_score[sample_idx] if y_score is not None else None

        iter_metrics = _compute_metrics_from_arrays(y_boot_true, y_boot_pred, y_boot_score)
        for k, v in iter_metrics.items():
            if np.isfinite(v):
                boot_results[k].append(v)

    summaries: dict[str, MetricSummary] = {}
    for k, pt in point_metrics.items():
        vals = boot_results[k]
        if len(vals) >= 100:
            ci_l = float(np.percentile(vals, 2.5))
            ci_u = float(np.percentile(vals, 97.5))
            summaries[k] = MetricSummary(
                point_estimate=pt if np.isfinite(pt) else None,
                ci_lower=ci_l,
                ci_upper=ci_u,
                status="ESTIMATED",
            )
        else:
            summaries[k] = MetricSummary(
                point_estimate=pt if np.isfinite(pt) else None,
                ci_lower=None,
                ci_upper=None,
                status="NOT_ESTIMABLE",
            )

    return summaries


def build_quality_attrition_summary(
    total_enrolled: int,
    recordings_attempted: int,
    passed_count: int,
    reasons: dict[str, int] | None = None,
    failures_by_group: dict[str, int] | None = None,
) -> QualityAttritionSummary:
    """Construct an auditable QualityAttritionSummary instance."""
    failed_count = recordings_attempted - passed_count
    rate = float(failed_count / recordings_attempted) if recordings_attempted > 0 else 0.0

    return QualityAttritionSummary(
        total_enrolled=total_enrolled,
        recordings_attempted=recordings_attempted,
        recordings_passed_quality=passed_count,
        attrition_rate=rate,
        reasons=dict(reasons or {}),
        failures_by_group=dict(failures_by_group or {}),
    )


@dataclass(frozen=True)
class IndependenceAttestation:
    """Cryptographic attestation of participant cohort independence bound to trust registry."""

    attestation_id: str
    reference_dataset_id: str
    reference_dataset_version: str
    reference_participant_count: int
    reference_roster_source: str
    reference_roster_sha256: str
    reference_authorization_ref: str
    candidate_dataset_id: str
    candidate_dataset_version: str
    candidate_participant_count: int
    candidate_roster_source: str
    candidate_roster_sha256: str
    candidate_authorization_ref: str
    identity_basis_type: str
    overlap_status: str
    overlapping_participants_count: int
    duplicate_reference_count: int
    duplicate_candidate_count: int
    roster_fingerprint: str
    reviewer_identity: str
    key_id: str
    timestamp_utc: str
    reviewer_role: str = ""
    registry_id: str = ""
    registry_version: str = ""
    registry_fingerprint: str = ""
    reference_source_expiry_utc: str = ""
    candidate_source_expiry_utc: str = ""
    normalization_protocol: str = "casefold_strip_prefix_v1"
    authentication_method: str = "HMAC-SHA256"
    attestation_hmac: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_hmac(self, key: bytes | str) -> str:
        key_bytes = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        d = asdict(self)
        d["attestation_hmac"] = ""
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hmac.new(key_bytes, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _is_valid_sha256_hex(value: Any) -> bool:
    s = str(value or "")
    return len(s) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in s)


def _load_source_roster(roster_path: Path | str) -> tuple[str, list[str]]:
    """Read raw source roster file bytes, compute SHA-256, and extract participant IDs."""
    path = Path(roster_path)
    if not path.is_file():
        raise FileNotFoundError(f"INDEPENDENCE_NOT_VERIFIED: Source roster file not found: {path}")
    raw_bytes = path.read_bytes()
    file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    text = raw_bytes.decode("utf-8")

    ids: list[str]
    suffix = path.suffix.lower()
    if suffix == ".json":
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            raw_list = parsed.get("participant_ids") or parsed.get("participants") or []
        elif isinstance(parsed, list):
            raw_list = parsed
        else:
            raise ValueError(f"Unsupported JSON roster structure in {path}")
        ids = [str(item).strip() for item in raw_list if str(item).strip()]
    else:
        non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if suffix == ".csv" or (
            non_empty_lines
            and "participant_id" in [c.strip() for c in non_empty_lines[0].split(",")]
        ):
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames or "participant_id" not in reader.fieldnames:
                raise ValueError(f"CSV roster file {path} missing 'participant_id' column.")
            ids = [
                str(row["participant_id"]).strip()
                for row in reader
                if str(row.get("participant_id", "")).strip()
            ]
        else:
            if non_empty_lines and non_empty_lines[0].casefold() == "participant_id":
                non_empty_lines = non_empty_lines[1:]
            ids = non_empty_lines

    if not ids:
        raise ValueError(f"INDEPENDENCE_NOT_VERIFIED: Roster file {path} has no participant IDs.")
    return file_sha256, ids


def normalize_participant_id(raw_id: Any) -> str:
    """Normalize participant identifier for safe cross-cohort comparison."""
    s = str(raw_id).strip().casefold()
    s = re.sub(r"^(?:participant|part|sub|pt|p)[_\-\s]*", "", s)
    return s


def verify_participant_independence(
    reference_participants: list[str] | set[str],
    candidate_participants: list[str] | set[str],
    key: str | bytes | None = None,
    key_id: str = "voxneuro-key-v1",
    identity_basis_type: str = "authorized_crosswalk",
) -> dict[str, Any]:
    """Verify participant independence using privacy-preserving HMAC-SHA256 comparison."""
    active_key = key or os.environ.get("VOXNEURO_HMAC_KEY")
    if not active_key:
        return {
            "overlap_status": "INDEPENDENCE_NOT_VERIFIED",
            "is_disjoint": False,
            "overlapping_participants_count": None,
            "duplicate_reference_count": 0,
            "duplicate_candidate_count": 0,
            "key_id": key_id,
            "reason": (
                "External HMAC key material unavailable; participant independence cannot "
                "be established without a key managed outside the repository."
            ),
        }

    ref_list = [normalize_participant_id(p) for p in reference_participants if str(p).strip()]
    cand_list = [normalize_participant_id(p) for p in candidate_participants if str(p).strip()]

    ref_dups = len(ref_list) - len(set(ref_list))
    cand_dups = len(cand_list) - len(set(cand_list))

    if not ref_list or not cand_list:
        return {
            "overlap_status": "INDEPENDENCE_NOT_VERIFIED",
            "is_disjoint": False,
            "overlapping_participants_count": None,
            "duplicate_reference_count": ref_dups,
            "duplicate_candidate_count": cand_dups,
            "key_id": key_id,
            "reason": "Reference or candidate participant list is empty or invalid.",
        }

    # Requirement B4: A valid common identity basis or authorized crosswalk must exist.
    # Disparate pseudonyms without a crosswalk cannot establish independence.
    if identity_basis_type not in {"authorized_crosswalk", "common_identity_basis"}:
        return {
            "overlap_status": "INDEPENDENCE_NOT_VERIFIED",
            "is_disjoint": False,
            "overlapping_participants_count": None,
            "duplicate_reference_count": ref_dups,
            "duplicate_candidate_count": cand_dups,
            "key_id": key_id,
            "reason": (
                f"No common identity basis exists between cohorts "
                f"(identity_basis_type: {identity_basis_type!r}); independently assigned "
                "pseudonyms cannot establish non-overlap. Status: INDEPENDENCE_NOT_VERIFIED."
            ),
        }

    key_bytes = active_key.encode("utf-8") if isinstance(active_key, str) else bytes(active_key)

    def _hash_id(norm_id: str) -> str:
        return hmac.new(key_bytes, norm_id.encode("utf-8"), hashlib.sha256).hexdigest()

    ref_hashes = {_hash_id(p) for p in ref_list}
    cand_hashes = {_hash_id(p) for p in cand_list}

    intersection = ref_hashes & cand_hashes
    if intersection:
        return {
            "overlap_status": "OVERLAP_DETECTED",
            "is_disjoint": False,
            "overlapping_participants_count": len(intersection),
            "duplicate_reference_count": ref_dups,
            "duplicate_candidate_count": cand_dups,
            "key_id": key_id,
            "reason": f"Detected {len(intersection)} overlapping participant(s) between cohorts.",
        }

    if ref_dups > 0 or cand_dups > 0:
        return {
            "overlap_status": "DUPLICATES_DETECTED",
            "is_disjoint": True,
            "overlapping_participants_count": 0,
            "duplicate_reference_count": ref_dups,
            "duplicate_candidate_count": cand_dups,
            "key_id": key_id,
            "reason": (
                f"Detected duplicate participant identifiers (ref: {ref_dups}, cand: {cand_dups})."
            ),
        }

    return {
        "overlap_status": "VERIFIED_DISJOINT",
        "is_disjoint": True,
        "overlapping_participants_count": 0,
        "duplicate_reference_count": 0,
        "duplicate_candidate_count": 0,
        "key_id": key_id,
        "reason": (
            "No overlapping participants detected between cohorts under authorized identity basis."
        ),
    }


def create_participant_independence_attestation(
    reference_dataset_id: str,
    reference_dataset_version: str,
    candidate_dataset_id: str,
    candidate_dataset_version: str,
    *,
    signed_registry: SignedAuthorizationRegistry | dict[str, Any] | None = None,
    reference_roster_path: Path | str | None = None,
    candidate_roster_path: Path | str | None = None,
    reference_roster_source: str = "",
    reference_authorization_ref: str = "",
    candidate_roster_source: str = "",
    candidate_authorization_ref: str = "",
    identity_basis_type: str = "",
    reviewer_identity: str = "",
    requested_task: str = "sustained_vowel",
    requested_operation: str = "frozen_model_evaluation",
    reference_roster_sha256: str = "",
    candidate_roster_sha256: str = "",
    reference_participants: list[str] | set[str] | None = None,
    candidate_participants: list[str] | set[str] | None = None,
    normalization_protocol: str = "casefold_strip_prefix_v1",
    key: bytes | str | None = None,
    key_id: str = "voxneuro-key-v1",
) -> IndependenceAttestation:
    """Construct an HMAC attestation bound to an Ed25519-signed trust registry and rosters."""
    ok_reg, reg_msg, verified_reg = verify_signed_authorization_registry(signed_registry)
    if not ok_reg or verified_reg is None:
        raise AuthorizationTrustRootError(reg_msg)

    active_key = key or os.environ.get("VOXNEURO_HMAC_KEY")

    if reference_roster_path is None or candidate_roster_path is None:
        raise ValueError(
            "INDEPENDENCE_NOT_VERIFIED: reference_roster_path and candidate_roster_path "
            "are required to bind attestation to actual source rosters."
        )
    if (
        not str(reference_roster_source or "").strip()
        or not str(candidate_roster_source or "").strip()
    ):
        raise ValueError(
            "INDEPENDENCE_NOT_VERIFIED: explicit reference_roster_source and "
            "candidate_roster_source are required."
        )
    if (
        not str(reference_authorization_ref or "").strip()
        or not str(candidate_authorization_ref or "").strip()
    ):
        raise ValueError(
            "INDEPENDENCE_NOT_VERIFIED: explicit reference_authorization_ref and "
            "candidate_authorization_ref are required."
        )
    if not str(identity_basis_type or "").strip():
        raise ValueError("INDEPENDENCE_NOT_VERIFIED: explicit identity_basis_type is required.")
    if not str(reviewer_identity or "").strip():
        raise ValueError("INDEPENDENCE_NOT_VERIFIED: explicit reviewer_identity is required.")

    ok_rev, rev_msg, rev_rec = authorize_reviewer_from_registry(
        verified_reg,
        reviewer_identity,
        requested_task=requested_task,
        requested_operation=requested_operation,
    )
    if not ok_rev or rev_rec is None:
        raise PermissionError(rev_msg)

    actual_ref_sha, ref_raw_ids = _load_source_roster(reference_roster_path)
    actual_cand_sha, cand_raw_ids = _load_source_roster(candidate_roster_path)

    if reference_roster_sha256 and reference_roster_sha256 != actual_ref_sha:
        raise ValueError(
            "INDEPENDENCE_NOT_VERIFIED: supplied reference_roster_sha256 does not match "
            "actual source roster file bytes."
        )
    if candidate_roster_sha256 and candidate_roster_sha256 != actual_cand_sha:
        raise ValueError(
            "INDEPENDENCE_NOT_VERIFIED: supplied candidate_roster_sha256 does not match "
            "actual source roster file bytes."
        )

    ok_ref_src, msg_ref_src, ref_src_rec = authorize_source_from_registry(
        verified_reg,
        role="reference",
        dataset_id=reference_dataset_id,
        dataset_version=reference_dataset_version,
        source_id=reference_roster_source,
        authorization_ref=reference_authorization_ref,
        actual_artifact_sha256=actual_ref_sha,
        requested_task=requested_task,
        requested_operation=requested_operation,
    )
    if not ok_ref_src or ref_src_rec is None:
        raise PermissionError(msg_ref_src)

    ok_cand_src, msg_cand_src, cand_src_rec = authorize_source_from_registry(
        verified_reg,
        role="candidate",
        dataset_id=candidate_dataset_id,
        dataset_version=candidate_dataset_version,
        source_id=candidate_roster_source,
        authorization_ref=candidate_authorization_ref,
        actual_artifact_sha256=actual_cand_sha,
        requested_task=requested_task,
        requested_operation=requested_operation,
    )
    if not ok_cand_src or cand_src_rec is None:
        raise PermissionError(msg_cand_src)

    if reference_participants is not None:
        supplied_ref = sorted(
            normalize_participant_id(p) for p in reference_participants if str(p).strip()
        )
        loaded_ref = sorted(normalize_participant_id(p) for p in ref_raw_ids if str(p).strip())
        if supplied_ref != loaded_ref:
            raise ValueError(
                "INDEPENDENCE_NOT_VERIFIED: reference_participants argument disagrees with "
                "reference_roster_path contents."
            )
    if candidate_participants is not None:
        supplied_cand = sorted(
            normalize_participant_id(p) for p in candidate_participants if str(p).strip()
        )
        loaded_cand = sorted(normalize_participant_id(p) for p in cand_raw_ids if str(p).strip())
        if supplied_cand != loaded_cand:
            raise ValueError(
                "INDEPENDENCE_NOT_VERIFIED: candidate_participants argument disagrees with "
                "candidate_roster_path contents."
            )

    ref_list = [normalize_participant_id(p) for p in ref_raw_ids if str(p).strip()]
    cand_list = [normalize_participant_id(p) for p in cand_raw_ids if str(p).strip()]

    fp_payload = {
        "ref_dataset": f"{reference_dataset_id}:{reference_dataset_version}",
        "cand_dataset": f"{candidate_dataset_id}:{candidate_dataset_version}",
        "ref_roster_sha256": actual_ref_sha,
        "cand_roster_sha256": actual_cand_sha,
        "ref_count": len(ref_list),
        "cand_count": len(cand_list),
        "identity_basis_type": identity_basis_type,
        "normalization_protocol": normalization_protocol,
        "registry_id": verified_reg.registry_id,
        "registry_version": verified_reg.registry_version,
        "registry_fingerprint": verified_reg.registry_fingerprint,
        "reviewer_role": rev_rec.role,
    }
    roster_fp = hashlib.sha256(
        json.dumps(fp_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    ind_res = verify_participant_independence(
        ref_raw_ids,
        cand_raw_ids,
        key=active_key,
        key_id=key_id,
        identity_basis_type=identity_basis_type,
    )
    ts = datetime.now(UTC).isoformat()
    raw_sig_base = f"{reference_dataset_id}:{candidate_dataset_id}:{ts}:{roster_fp}"
    att_id = f"att-{hashlib.sha256(raw_sig_base.encode()).hexdigest()[:16]}"

    att = IndependenceAttestation(
        attestation_id=att_id,
        reference_dataset_id=reference_dataset_id,
        reference_dataset_version=reference_dataset_version,
        reference_participant_count=len(ref_list),
        reference_roster_source=reference_roster_source,
        reference_roster_sha256=actual_ref_sha,
        reference_authorization_ref=reference_authorization_ref,
        candidate_dataset_id=candidate_dataset_id,
        candidate_dataset_version=candidate_dataset_version,
        candidate_participant_count=len(cand_list),
        candidate_roster_source=candidate_roster_source,
        candidate_roster_sha256=actual_cand_sha,
        candidate_authorization_ref=candidate_authorization_ref,
        normalization_protocol=normalization_protocol,
        duplicate_reference_count=ind_res.get("duplicate_reference_count", 0),
        duplicate_candidate_count=ind_res.get("duplicate_candidate_count", 0),
        overlap_status=ind_res["overlap_status"],
        overlapping_participants_count=ind_res.get("overlapping_participants_count") or 0,
        identity_basis_type=identity_basis_type,
        roster_fingerprint=roster_fp,
        reviewer_identity=reviewer_identity,
        reviewer_role=rev_rec.role,
        registry_id=verified_reg.registry_id,
        registry_version=verified_reg.registry_version,
        registry_fingerprint=verified_reg.registry_fingerprint,
        reference_source_expiry_utc=ref_src_rec.expiry_utc,
        candidate_source_expiry_utc=cand_src_rec.expiry_utc,
        key_id=key_id,
        timestamp_utc=ts,
        authentication_method="HMAC-SHA256",
    )
    if active_key and ind_res["overlap_status"] == "VERIFIED_DISJOINT":
        sig = att.compute_hmac(active_key)
        return IndependenceAttestation(**{**att.to_dict(), "attestation_hmac": sig})
    return att


def verify_participant_independence_attestation(
    attestation: IndependenceAttestation | dict[str, Any],
    expected_reference: tuple[str, str] | None = None,
    expected_candidate: tuple[str, str] | None = None,
    expected_reference_dataset: tuple[str, str] | None = None,
    expected_candidate_dataset: tuple[str, str] | None = None,
    key: bytes | str | None = None,
    expected_key_id: str = "voxneuro-key-v1",
    *,
    signed_registry: SignedAuthorizationRegistry | dict[str, Any] | None = None,
    reference_roster_path: Path | str | None = None,
    candidate_roster_path: Path | str | None = None,
    expected_reviewer_id: str | None = None,
    requested_task: str = "sustained_vowel",
    requested_operation: str = "frozen_model_evaluation",
) -> tuple[bool, str]:
    """Verify trust-root signature, source & reviewer authorization, HMAC, and live rosters."""
    ok_reg, reg_msg, verified_reg = verify_signed_authorization_registry(signed_registry)
    if not ok_reg or verified_reg is None:
        return False, reg_msg

    active_key = key or os.environ.get("VOXNEURO_HMAC_KEY")
    if not active_key:
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: External HMAC key unavailable for attestation.",
        )

    exp_ref = expected_reference or expected_reference_dataset
    exp_cand = expected_candidate or expected_candidate_dataset
    if exp_ref is None or exp_cand is None:
        raise ValueError("Must specify expected reference and candidate dataset identifiers.")

    att_dict = (
        attestation.to_dict()
        if isinstance(attestation, IndependenceAttestation)
        else dict(attestation)
    )
    declared_hmac = att_dict.get("attestation_hmac", "")
    if not declared_hmac:
        return False, "Attestation HMAC signature is missing (INDEPENDENCE_NOT_VERIFIED)."

    att_key_id = att_dict.get("key_id", "")
    if att_key_id != expected_key_id:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: Attestation key_id mismatch: "
            f"expected {expected_key_id!r}, got {att_key_id!r}",
        )

    if att_dict.get("authentication_method") != "HMAC-SHA256":
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: authentication_method must be 'HMAC-SHA256', "
            f"got {att_dict.get('authentication_method')!r}",
        )

    if att_dict.get("normalization_protocol") != "casefold_strip_prefix_v1":
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: unsupported normalization_protocol "
            f"{att_dict.get('normalization_protocol')!r}.",
        )

    basis = att_dict.get("identity_basis_type")
    if basis not in {"authorized_crosswalk", "common_identity_basis"}:
        return (
            False,
            f"Independence attestation rejected: identity_basis_type is {basis!r} "
            "(must be 'authorized_crosswalk' or 'common_identity_basis'). "
            "Status: INDEPENDENCE_NOT_VERIFIED.",
        )

    try:
        att_obj = IndependenceAttestation(**att_dict)
    except TypeError as exc:
        return False, f"INDEPENDENCE_NOT_VERIFIED: malformed attestation schema ({exc})."

    computed_hmac = att_obj.compute_hmac(active_key)
    if not hmac.compare_digest(declared_hmac, computed_hmac):
        return False, "INDEPENDENCE_NOT_VERIFIED: Attestation HMAC signature mismatch."

    if (
        att_dict.get("registry_id") != verified_reg.registry_id
        or att_dict.get("registry_version") != verified_reg.registry_version
        or att_dict.get("registry_fingerprint") != verified_reg.registry_fingerprint
    ):
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: attestation registry binding mismatches signed trust root.",
        )

    actual_ref = (
        att_dict.get("reference_dataset_id"),
        att_dict.get("reference_dataset_version"),
    )
    if actual_ref != exp_ref:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: Reference dataset mismatch: "
            f"expected {exp_ref}, got {actual_ref}",
        )

    actual_cand = (
        att_dict.get("candidate_dataset_id"),
        att_dict.get("candidate_dataset_version"),
    )
    if actual_cand != exp_cand:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: Candidate dataset mismatch: "
            f"expected {exp_cand}, got {actual_cand}",
        )

    reviewer_id = str(att_dict.get("reviewer_identity") or "").strip()
    if expected_reviewer_id is not None and reviewer_id != str(expected_reviewer_id).strip():
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer_identity {reviewer_id!r} mismatches "
            f"requested reviewer {expected_reviewer_id!r}.",
        )
    ok_rev, rev_msg, rev_rec = authorize_reviewer_from_registry(
        verified_reg,
        reviewer_id,
        requested_task=requested_task,
        requested_operation=requested_operation,
    )
    if not ok_rev or rev_rec is None:
        return False, rev_msg
    if att_dict.get("reviewer_role") != rev_rec.role:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer_role {att_dict.get('reviewer_role')!r} "
            f"mismatches registry role {rev_rec.role!r}.",
        )

    if att_dict.get("overlap_status") != "VERIFIED_DISJOINT":
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: Cohort overlap status is "
            f"{att_dict.get('overlap_status')!r} (must be 'VERIFIED_DISJOINT').",
        )

    if att_dict.get("overlapping_participants_count", 0) > 0:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: Overlapping participants detected: "
            f"{att_dict.get('overlapping_participants_count')}.",
        )

    if (
        att_dict.get("duplicate_candidate_count", 0) > 0
        or att_dict.get("duplicate_reference_count", 0) > 0
    ):
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: Duplicate participant identifiers present in cohort.",
        )

    ref_roster_sha = att_dict.get("reference_roster_sha256", "")
    cand_roster_sha = att_dict.get("candidate_roster_sha256", "")
    if not _is_valid_sha256_hex(ref_roster_sha) or not _is_valid_sha256_hex(cand_roster_sha):
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: Attestation missing valid 64-character roster SHA-256.",
        )

    if reference_roster_path is None or candidate_roster_path is None:
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: source reference_roster_path and "
            "candidate_roster_path are required to verify roster hashes.",
        )
    try:
        actual_ref_sha, ref_raw_ids = _load_source_roster(reference_roster_path)
        actual_cand_sha, cand_raw_ids = _load_source_roster(candidate_roster_path)
    except Exception as exc:
        return False, f"INDEPENDENCE_NOT_VERIFIED: failed loading source roster ({exc})."

    if actual_ref_sha != ref_roster_sha:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reference roster file SHA-256 mismatch: "
            f"{actual_ref_sha} != {ref_roster_sha}",
        )
    if actual_cand_sha != cand_roster_sha:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: candidate roster file SHA-256 mismatch: "
            f"{actual_cand_sha} != {cand_roster_sha}",
        )

    ok_ref_src, msg_ref_src, ref_src_rec = authorize_source_from_registry(
        verified_reg,
        role="reference",
        dataset_id=actual_ref[0] or "",
        dataset_version=actual_ref[1] or "",
        source_id=att_dict.get("reference_roster_source", ""),
        authorization_ref=att_dict.get("reference_authorization_ref", ""),
        actual_artifact_sha256=actual_ref_sha,
        requested_task=requested_task,
        requested_operation=requested_operation,
    )
    if not ok_ref_src or ref_src_rec is None:
        return False, msg_ref_src
    if att_dict.get("reference_source_expiry_utc") != ref_src_rec.expiry_utc:
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: reference_source_expiry_utc disagrees with trust registry.",
        )

    ok_cand_src, msg_cand_src, cand_src_rec = authorize_source_from_registry(
        verified_reg,
        role="candidate",
        dataset_id=actual_cand[0] or "",
        dataset_version=actual_cand[1] or "",
        source_id=att_dict.get("candidate_roster_source", ""),
        authorization_ref=att_dict.get("candidate_authorization_ref", ""),
        actual_artifact_sha256=actual_cand_sha,
        requested_task=requested_task,
        requested_operation=requested_operation,
    )
    if not ok_cand_src or cand_src_rec is None:
        return False, msg_cand_src
    if att_dict.get("candidate_source_expiry_utc") != cand_src_rec.expiry_utc:
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: candidate_source_expiry_utc disagrees with trust registry.",
        )

    ref_norm = [normalize_participant_id(p) for p in ref_raw_ids if str(p).strip()]
    cand_norm = [normalize_participant_id(p) for p in cand_raw_ids if str(p).strip()]
    if len(ref_norm) != att_dict.get("reference_participant_count"):
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reference roster count mismatch: "
            f"{len(ref_norm)} != {att_dict.get('reference_participant_count')}",
        )
    if len(cand_norm) != att_dict.get("candidate_participant_count"):
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: candidate roster count mismatch: "
            f"{len(cand_norm)} != {att_dict.get('candidate_participant_count')}",
        )

    live_ind = verify_participant_independence(
        ref_raw_ids,
        cand_raw_ids,
        key=active_key,
        key_id=att_key_id,
        identity_basis_type=basis,
    )
    if live_ind.get("overlap_status") != "VERIFIED_DISJOINT":
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: recomputed cohort independence check failed "
            f"({live_ind.get('overlap_status')}: {live_ind.get('reason')}).",
        )

    expected_fp_payload = {
        "ref_dataset": f"{actual_ref[0]}:{actual_ref[1]}",
        "cand_dataset": f"{actual_cand[0]}:{actual_cand[1]}",
        "ref_roster_sha256": actual_ref_sha,
        "cand_roster_sha256": actual_cand_sha,
        "ref_count": len(ref_norm),
        "cand_count": len(cand_norm),
        "identity_basis_type": basis,
        "normalization_protocol": att_dict.get("normalization_protocol"),
        "registry_id": verified_reg.registry_id,
        "registry_version": verified_reg.registry_version,
        "registry_fingerprint": verified_reg.registry_fingerprint,
        "reviewer_role": rev_rec.role,
    }
    expected_fp = hashlib.sha256(
        json.dumps(expected_fp_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if att_dict.get("roster_fingerprint") != expected_fp:
        return (
            False,
            "INDEPENDENCE_NOT_VERIFIED: recomputed roster_fingerprint mismatch with rosters.",
        )

    return True, "Participant independence attestation verified against signed trust registry."


@dataclass(frozen=True)
class EvaluationProvenanceReceipt:
    """Cryptographic provenance receipt required for external cohort evaluation."""

    candidate_domain_id: str
    dataset_id: str
    dataset_version: str
    dataset_source: str
    authorization_status: str
    task_identifier: str
    feature_schema_version: str
    feature_schema_fingerprint: str
    feature_config_fingerprint: str
    preprocessing_config_fingerprint: str
    code_fingerprint: str
    reference_feature_table_sha256: str
    candidate_feature_table_sha256: str
    num_recordings: int
    num_unique_participants: int
    diagnostic_label_provenance: str
    participant_overlap_status: str
    duplicate_participant_count: int
    duplicate_recording_count: int
    feature_validation_status: str
    quality_exclusion_count: int
    evaluation_protocol_id: str
    timestamp_utc: str
    key_id: str = "voxneuro-key-v1"
    receipt_sha256: str = ""
    receipt_hmac: str = ""
    dua_expiration_date: str | None = None
    dua_document_fingerprint: str = ""
    permitted_operations: list[str] = field(default_factory=lambda: ["frozen_model_evaluation"])
    frozen_model_sha256: str = FROZEN_REFERENCE_MODEL_SHA256
    independence_attestation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_sha256(self) -> str:
        d = asdict(self)
        d["receipt_sha256"] = ""
        d["receipt_hmac"] = ""
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def compute_hmac(self, key: bytes | str) -> str:
        key_bytes = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        d = asdict(self)
        d["receipt_sha256"] = ""
        d["receipt_hmac"] = ""
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hmac.new(key_bytes, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_authoritative_dataset_access(
    rec_dict: dict[str, Any],
    domain_entry: Any,
    study_conn: sqlite3.Connection | None,
    *,
    dataset_access_record: Any | None = None,
    verified_registry: AuthorizationTrustRegistry | None = None,
    dua_document_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Validate dataset DUA/authorization strictly from DB, DUA artifact, and signed registry."""
    from voxneuro.study.consent import get_dataset_access
    from voxneuro.study.schema import DatasetAccessRecord

    rec_ds_id = rec_dict.get("dataset_id", "")
    rec_ds_ver = rec_dict.get("dataset_version", "")

    if study_conn is None:
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative study database connection "
            "is required; caller-supplied DatasetAccessRecord cannot bypass authority lookup.",
        )

    try:
        db_rec = get_dataset_access(study_conn, rec_ds_id, dataset_version=rec_ds_ver)
    except KeyError:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: dataset {rec_ds_id!r} version "
            f"{rec_ds_ver!r} has no registered authorization record in study database.",
        )
    except sqlite3.Error as exc:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative database query failed ({exc}).",
        )

    if dataset_access_record is not None:
        try:
            passed_rec = (
                dataset_access_record
                if isinstance(dataset_access_record, DatasetAccessRecord)
                else DatasetAccessRecord(**dataset_access_record)
            )
        except Exception as exc:
            return (
                False,
                f"DATASET_AUTHORIZATION_NOT_VERIFIED: malformed DatasetAccessRecord ({exc}).",
            )
        if passed_rec != db_rec:
            return (
                False,
                "DATASET_AUTHORIZATION_NOT_VERIFIED: supplied DatasetAccessRecord "
                "does not match authoritative database record.",
            )

    auth_rec = db_rec
    if auth_rec.dataset_id != rec_ds_id or auth_rec.dataset_version != rec_ds_ver:
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative dataset_id/version mismatch.",
        )
    owner = str(auth_rec.dataset_owner or "").strip()
    if not owner or owner.casefold() in {"unknown", "pending", "none", "tbd"}:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: invalid dataset_owner {owner!r}.",
        )
    if auth_rec.access_approval_state != "APPROVED":
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative access_approval_state is "
            f"{auth_rec.access_approval_state!r} (not authorized).",
        )
    if auth_rec.dua_state not in {"ACTIVE", "NOT_REQUIRED"}:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative dua_state is "
            f"{auth_rec.dua_state!r} (not authorized).",
        )

    today_iso = datetime.now(UTC).date().isoformat()
    if not auth_rec.expiration_date:
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative DUA expiration_date is required.",
        )
    if str(auth_rec.expiration_date)[:10] < today_iso:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative DUA expired on "
            f"{auth_rec.expiration_date}.",
        )
    rec_exp = rec_dict.get("dua_expiration_date")
    if rec_exp and str(rec_exp)[:10] < today_iso:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: receipt DUA expired on {rec_exp}.",
        )
    if (
        auth_rec.expiration_date
        and rec_exp
        and str(auth_rec.expiration_date)[:10] != str(rec_exp)[:10]
    ):
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: DUA expiration_date mismatch between "
            "receipt and authoritative record.",
        )

    task_id = rec_dict.get("task_identifier", "")
    if (
        task_id not in auth_rec.permitted_tasks
        or domain_entry.metadata.task_type not in auth_rec.permitted_tasks
    ):
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: task {task_id!r} not in authoritative "
            f"permitted_tasks {auth_rec.permitted_tasks}.",
        )

    auth_ops = set(auth_rec.permitted_data_processing_operations or [])
    if not auth_ops.intersection({"frozen_model_evaluation", "external_validation"}):
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative record does not permit "
            "frozen_model_evaluation or external_validation.",
        )
    rec_ops = set(rec_dict.get("permitted_operations") or [])
    if not rec_ops or not rec_ops.issubset(auth_ops):
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: receipt permitted_operations "
            f"{sorted(rec_ops)} exceed authoritative {sorted(auth_ops)}.",
        )

    if not str(auth_rec.storage_restrictions or "").strip():
        return False, "DATASET_AUTHORIZATION_NOT_VERIFIED: storage_restrictions missing."
    if not str(auth_rec.publication_restrictions or "").strip():
        return False, "DATASET_AUTHORIZATION_NOT_VERIFIED: publication_restrictions missing."

    src_doc = str(auth_rec.source_documentation or "").strip()
    if not src_doc or src_doc in {"DUA_PENDING_REVIEW", "UNKNOWN", "NONE", "PENDING"}:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: invalid source_documentation {src_doc!r}.",
        )

    if not str(rec_dict.get("dataset_source") or "").strip():
        return False, "DATASET_AUTHORIZATION_NOT_VERIFIED: receipt dataset_source missing."

    auth_fp = str(auth_rec.dua_document_fingerprint or "").strip()
    rec_fp = str(rec_dict.get("dua_document_fingerprint") or "").strip()
    if not _is_valid_sha256_hex(auth_fp) or not _is_valid_sha256_hex(rec_fp) or auth_fp != rec_fp:
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: dua_document_fingerprint missing or mismatched.",
        )

    if auth_rec.dua_verification_status != "DOCUMENT_AUTHENTICATED":
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative DUA record "
            f"dua_verification_status is {auth_rec.dua_verification_status!r} "
            "(must be 'DOCUMENT_AUTHENTICATED').",
        )

    if dua_document_path is None:
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: actual DUA document artifact is required "
            "to verify checksum; a SHA-256 string alone is insufficient.",
        )
    dua_path_obj = Path(dua_document_path)
    if not dua_path_obj.is_file():
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: DUA document artifact not found: {dua_path_obj}.",
        )
    actual_dua_sha = hashlib.sha256(dua_path_obj.read_bytes()).hexdigest()
    if actual_dua_sha.casefold() != auth_fp.casefold():
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: DUA document artifact SHA-256 mismatches "
            f"authoritative database fingerprint ({actual_dua_sha} != {auth_fp}).",
        )

    if verified_registry is None:
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: signed M4 trust registry is required to "
            "cross-bind database DUA record.",
        )

    if not str(auth_rec.source_id or "").strip():
        return False, "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative source_id is missing."

    cand_sources = [
        s
        for s in verified_registry.authorized_sources
        if s.role == "candidate"
        and s.dataset_id == rec_ds_id
        and s.dataset_version == rec_ds_ver
        and s.source_id == auth_rec.source_id
    ]
    if not cand_sources:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: candidate source {auth_rec.source_id!r} for "
            f"dataset {rec_ds_id!r} ({rec_ds_ver!r}) not registered in signed M4 trust registry.",
        )
    if len(cand_sources) > 1:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: ambiguous candidate source entries for "
            f"{auth_rec.source_id!r} in signed M4 trust registry.",
        )

    cand_src = cand_sources[0]

    # 12-point exact cross-binding between SQLite DUA record and Ed25519-signed source record
    if cand_src.authorization_state not in {"APPROVED", "ACTIVE"}:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: signed source authorization_state is "
            f"{cand_src.authorization_state!r} (not authorized).",
        )
    if not str(auth_rec.authorization_ref or "").strip() or (
        auth_rec.authorization_ref != cand_src.authorization_ref
    ):
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: authorization_ref mismatch between DB "
            f"({auth_rec.authorization_ref!r}) and signed registry "
            f"({cand_src.authorization_ref!r}).",
        )
    if not str(auth_rec.issuing_authority or "").strip() or (
        auth_rec.issuing_authority != cand_src.issuing_authority
        or auth_rec.issuing_authority != verified_registry.issuing_authority
    ):
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: issuing_authority mismatch between DB "
            f"({auth_rec.issuing_authority!r}) and signed registry "
            f"({cand_src.issuing_authority!r}).",
        )
    if (
        auth_rec.authorization_registry_id != verified_registry.registry_id
        or auth_rec.authorization_registry_version != verified_registry.registry_version
        or auth_rec.authorization_registry_version != cand_src.registry_version
    ):
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: authorization registry ID/version mismatch "
            "between DB record and signed M4 trust registry.",
        )
    if task_id not in cand_src.permitted_tasks or not set(auth_rec.permitted_tasks).issubset(
        set(cand_src.permitted_tasks)
    ):
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: DB permitted_tasks {auth_rec.permitted_tasks} "
            f"exceed or mismatch signed registry {list(cand_src.permitted_tasks)}.",
        )
    if not rec_ops.issubset(set(cand_src.permitted_operations)) or not auth_ops.issubset(
        set(cand_src.permitted_operations)
    ):
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: DB permitted operations {sorted(auth_ops)} "
            f"exceed or mismatch signed registry {list(cand_src.permitted_operations)}.",
        )

    cand_src_exp_date = str(cand_src.expiry_utc or "")[:10]
    if not cand_src_exp_date or cand_src_exp_date < today_iso:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: signed source authorization expired on "
            f"{cand_src.expiry_utc!r}.",
        )
    if str(auth_rec.expiration_date)[:10] != cand_src_exp_date:
        return (
            False,
            f"DATASET_AUTHORIZATION_NOT_VERIFIED: DB expiration_date "
            f"{auth_rec.expiration_date!r} does not match signed source expiry_utc "
            f"{cand_src.expiry_utc!r}.",
        )

    if (
        not _is_valid_sha256_hex(cand_src.dua_document_fingerprint)
        or cand_src.dua_document_fingerprint.casefold() != auth_fp.casefold()
        or cand_src.dua_document_fingerprint.casefold() != actual_dua_sha.casefold()
    ):
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: DUA document fingerprint is not bound to "
            "the signed authority source record.",
        )
    if (
        not str(auth_rec.dua_source_artifact_reference or "").strip()
        or auth_rec.dua_source_artifact_reference != cand_src.retrieval_reference
    ):
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: DUA source artifact reference mismatch "
            f"({auth_rec.dua_source_artifact_reference!r} != {cand_src.retrieval_reference!r}).",
        )
    if not _is_valid_sha256_hex(cand_src.artifact_sha256):
        return (
            False,
            "DATASET_AUTHORIZATION_NOT_VERIFIED: signed source missing valid artifact_sha256.",
        )

    att_data = rec_dict.get("independence_attestation")
    if isinstance(att_data, dict):
        if att_data.get("candidate_roster_source") != auth_rec.source_id:
            return (
                False,
                "DATASET_AUTHORIZATION_NOT_VERIFIED: DB source_id does not match attestation "
                "candidate_roster_source.",
            )
        if att_data.get("candidate_authorization_ref") != auth_rec.authorization_ref:
            return (
                False,
                "DATASET_AUTHORIZATION_NOT_VERIFIED: DB authorization_ref does not match "
                "attestation candidate_authorization_ref.",
            )

    return True, "Authoritative dataset access verified."


def verify_evaluation_provenance_receipt(
    receipt: EvaluationProvenanceReceipt | dict[str, Any],
    candidate_csv_path: Path,
    reference_csv_path: Path | None = None,
    registry: Any | None = None,
    key: bytes | str | None = None,
    *,
    signed_registry: SignedAuthorizationRegistry | dict[str, Any] | None = None,
    expected_reviewer_id: str | None = None,
    reference_roster_path: Path | None = None,
    candidate_roster_path: Path | None = None,
    study_conn: sqlite3.Connection | None = None,
    dataset_access_record: Any | None = None,
    dua_document_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Verify that an external evaluation provenance receipt satisfies all fail-closed criteria."""
    ok_trust, trust_msg, verified_trust_reg = verify_signed_authorization_registry(signed_registry)
    if not ok_trust or verified_trust_reg is None:
        return False, trust_msg

    active_key = key or os.environ.get("VOXNEURO_HMAC_KEY")

    if isinstance(receipt, dict):
        rec_dict = dict(receipt)
        receipt_obj = EvaluationProvenanceReceipt(**rec_dict)
    else:
        receipt_obj = receipt
        rec_dict = receipt.to_dict()

    # B5.1 Key Identity validation
    rec_key_id = rec_dict.get("key_id", "")
    if rec_key_id not in {"voxneuro-key-v1"}:
        return False, f"Receipt rejected: key_id {rec_key_id!r} is unknown, retired, or invalid."

    declared_hmac = rec_dict.get("receipt_hmac", "")
    declared_sha = rec_dict.get("receipt_sha256", "")

    # Requirement 2.6: Authenticate receipt with HMAC
    if not declared_hmac:
        return False, "Receipt rejected: unauthenticated receipt missing receipt_hmac signature."

    if not active_key:
        return False, "Receipt rejected: external HMAC key material unavailable for verification."

    computed_hmac = receipt_obj.compute_hmac(active_key)
    if not hmac.compare_digest(declared_hmac, computed_hmac):
        return False, "Receipt HMAC authentication failed: signature mismatch."

    # Also verify integrity checksum if supplied
    if declared_sha:
        computed_sha = receipt_obj.compute_sha256()
        if declared_sha != computed_sha:
            return False, f"Receipt checksum mismatch: {declared_sha} != {computed_sha}"

    domain_id = rec_dict.get("candidate_domain_id", "")
    from voxneuro.modeling.domain_registry import load_domain_registry

    reg = registry or load_domain_registry()
    if not reg.is_candidate(domain_id):
        return False, f"Candidate domain {domain_id!r} is not registered as a candidate domain."

    domain_entry = reg.get_domain(domain_id)
    if not domain_entry.research_evaluation_eligible:
        return False, f"Domain {domain_id!r} is marked research_evaluation_eligible: false."

    # B5.2 Dataset Authorization validation against registry
    rec_ds_id = rec_dict.get("dataset_id", "")
    rec_ds_ver = rec_dict.get("dataset_version", "")
    if rec_ds_id != domain_entry.metadata.dataset_id:
        return (
            False,
            f"Dataset ID mismatch in receipt: {rec_ds_id!r} != "
            f"{domain_entry.metadata.dataset_id!r}",
        )
    if rec_ds_ver != domain_entry.metadata.dataset_version:
        return (
            False,
            f"Dataset version mismatch in receipt: {rec_ds_ver!r} != "
            f"{domain_entry.metadata.dataset_version!r}",
        )

    auth_status = str(rec_dict.get("authorization_status", "")).upper()
    if auth_status not in {"AUTHORIZED_DUA", "AUTHORIZED_OPEN_DATA", "AUTHORIZED"}:
        return False, f"Dataset authorization status {auth_status!r} is not authorized."

    # Check DUA expiration date if specified
    exp_date = rec_dict.get("dua_expiration_date")
    if exp_date:
        today_iso = datetime.now(UTC).date().isoformat()
        if str(exp_date)[:10] < today_iso:
            return False, f"Dataset DUA expired on {exp_date}."

    # Check permitted operations
    permitted_ops = rec_dict.get("permitted_operations") or []
    if not any(op in permitted_ops for op in ["frozen_model_evaluation", "external_validation"]):
        return (
            False,
            f"Operation 'frozen_model_evaluation' not permitted by receipt: {permitted_ops}",
        )

    # Check task compatibility
    task_id = rec_dict.get("task_identifier", "")
    if task_id != domain_entry.metadata.task_type:
        return (
            False,
            f"Task {task_id!r} does not match registered task {domain_entry.metadata.task_type!r}.",
        )

    ok_auth, auth_msg = _verify_authoritative_dataset_access(
        rec_dict,
        domain_entry,
        study_conn=study_conn,
        dataset_access_record=dataset_access_record,
        verified_registry=verified_trust_reg,
        dua_document_path=dua_document_path,
    )
    if not ok_auth:
        return False, auth_msg

    # B5.3 Required Fingerprints (recompute and compare, cannot be skipped)
    rec_schema_ver = rec_dict.get("feature_schema_version")
    if rec_schema_ver != SCHEMA_VERSION:
        return (
            False,
            f"Schema version mismatch: {rec_schema_ver} != {SCHEMA_VERSION}",
        )
    if rec_dict.get("feature_schema_fingerprint") != schema_fingerprint():
        return False, "Feature schema fingerprint does not match canonical Core39."

    exp_feat_fp = feature_config_fingerprint(load_config("feature_config.yaml"))
    rec_feat_fp = rec_dict.get("feature_config_fingerprint", "")
    if not rec_feat_fp or rec_feat_fp != exp_feat_fp:
        return False, f"Feature configuration fingerprint mismatch: {rec_feat_fp} != {exp_feat_fp}"

    exp_prep_fp = configuration_fingerprint(load_config("audio_config.yaml"))
    rec_prep_fp = rec_dict.get("preprocessing_config_fingerprint", "")
    if not rec_prep_fp or rec_prep_fp != exp_prep_fp:
        return (
            False,
            f"Preprocessing configuration fingerprint mismatch: {rec_prep_fp} != {exp_prep_fp}",
        )

    exp_code_fp = project_code_fingerprint()
    rec_code_fp = rec_dict.get("code_fingerprint", "")
    if not rec_code_fp or rec_code_fp != exp_code_fp:
        return False, f"Project code fingerprint mismatch: {rec_code_fp} != {exp_code_fp}"

    # B5.4 Model Integrity: exact frozen reference model SHA-256
    rec_model_sha = rec_dict.get("frozen_model_sha256", "")
    if not rec_model_sha or rec_model_sha != FROZEN_REFERENCE_MODEL_SHA256:
        return (
            False,
            f"Frozen model SHA-256 mismatch in receipt: {rec_model_sha!r} != "
            f"{FROZEN_REFERENCE_MODEL_SHA256!r}",
        )

    # Evaluation Protocol ID check
    rec_proto_id = rec_dict.get("evaluation_protocol_id", "")
    if rec_proto_id != "VOXNEURO-M4-EXT-VAL-2026-V1":
        return (
            False,
            f"Evaluation protocol ID mismatch: {rec_proto_id!r} != 'VOXNEURO-M4-EXT-VAL-2026-V1'",
        )

    # B5.5 Feature-table content & validation
    if not candidate_csv_path.is_file():
        return False, f"Candidate features file not found: {candidate_csv_path}"
    actual_cand_sha = hashlib.sha256(candidate_csv_path.read_bytes()).hexdigest()
    if actual_cand_sha != rec_dict.get("candidate_feature_table_sha256"):
        return (
            False,
            f"Candidate feature table SHA-256 mismatch: "
            f"{actual_cand_sha} != {rec_dict.get('candidate_feature_table_sha256')}",
        )

    if reference_csv_path is None or not reference_csv_path.is_file():
        return (
            False,
            "Reference feature table file is required and must exist for receipt verification.",
        )

    actual_ref_sha = hashlib.sha256(reference_csv_path.read_bytes()).hexdigest()
    if actual_ref_sha != rec_dict.get("reference_feature_table_sha256"):
        return (
            False,
            f"Reference feature table SHA-256 mismatch: "
            f"{actual_ref_sha} != {rec_dict.get('reference_feature_table_sha256')}",
        )

    # Inspect candidate CSV content and validate schema
    try:
        cand_df = pd.read_csv(candidate_csv_path)
    except Exception as exc:
        return False, f"Failed to parse candidate feature table CSV: {exc}"

    if cand_df.empty:
        return False, "Candidate feature table is empty."

    for col in ("participant_id", "diagnostic_group"):
        if col not in cand_df.columns:
            return False, f"Candidate feature table missing required column: {col!r}"

    missing_features = set(FEATURE_NAMES) - set(cand_df.columns)
    if missing_features:
        return (
            False,
            f"Candidate feature table missing Core39 feature columns: {sorted(missing_features)}",
        )

    # Check that all feature columns are numeric and finite
    for feat in FEATURE_NAMES:
        if not pd.api.types.is_numeric_dtype(cand_df[feat]):
            return False, f"Feature column {feat!r} is not numeric in candidate feature table."
        if cand_df[feat].isna().any() or np.isinf(cand_df[feat]).any():
            return (
                False,
                f"Feature column {feat!r} contains NaN or infinite values in candidate table.",
            )

    # Validate row and participant counts against receipt
    expected_recs = rec_dict.get("num_recordings")
    if len(cand_df) != expected_recs:
        return (
            False,
            f"Candidate recording count mismatch: {len(cand_df)} != {expected_recs}",
        )
    unique_parts = cand_df["participant_id"].nunique()
    expected_parts = rec_dict.get("num_unique_participants")
    if unique_parts != expected_parts:
        return (
            False,
            f"Candidate unique participant count mismatch: {unique_parts} != {expected_parts}",
        )

    # Validate diagnostic label provenance
    diag_prov = rec_dict.get("diagnostic_label_provenance", "")
    if diag_prov not in {
        "clinical_neurologist",
        "expert_consensus",
        "panel_adjudication",
        "board_certified_neurologist",
    }:
        return (
            False,
            f"Diagnostic label provenance {diag_prov!r} is unverified or invalid.",
        )

    # Check duplicates and quality
    if rec_dict.get("duplicate_participant_count", 0) > 0:
        return (
            False,
            f"Duplicate participants detected: {rec_dict.get('duplicate_participant_count')}.",
        )
    if rec_dict.get("duplicate_recording_count", 0) > 0:
        return False, f"Duplicate recordings detected: {rec_dict.get('duplicate_recording_count')}."
    if rec_dict.get("feature_validation_status") != "PASSED":
        return False, f"Feature validation status is {rec_dict.get('feature_validation_status')!r}."

    # Requirement 2.5: Authenticated participant independence attestation
    att_data = rec_dict.get("independence_attestation")
    if not att_data:
        return (
            False,
            "Receipt rejected: participant independence attestation missing "
            "(INDEPENDENCE_NOT_VERIFIED).",
        )

    is_att_valid, att_msg = verify_participant_independence_attestation(
        att_data,
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=(
            domain_entry.metadata.dataset_id,
            domain_entry.metadata.dataset_version,
        ),
        key=active_key,
        signed_registry=signed_registry,
        reference_roster_path=reference_roster_path,
        candidate_roster_path=candidate_roster_path,
        expected_reviewer_id=expected_reviewer_id,
        requested_task=task_id,
        requested_operation="frozen_model_evaluation",
    )
    if not is_att_valid:
        return False, f"Participant independence attestation rejected: {att_msg}"

    return True, "Receipt verified successfully."


def evaluate_external_domain_with_provenance(
    receipt: EvaluationProvenanceReceipt | dict[str, Any],
    candidate_features_path: Path,
    reference_features_path: Path,
    bundle_path: Path | None = None,
    registry: Any | None = None,
    key: bytes | str | None = None,
    *,
    signed_registry: SignedAuthorizationRegistry | dict[str, Any] | None = None,
    expected_reviewer_id: str | None = None,
    reference_roster_path: Path | None = None,
    candidate_roster_path: Path | None = None,
    study_conn: sqlite3.Connection | None = None,
    dataset_access_record: Any | None = None,
    dua_document_path: Path | str | None = None,
) -> dict[str, Any]:
    """Execute external domain evaluation under strict fail-closed provenance gating."""
    is_valid, reason = verify_evaluation_provenance_receipt(
        receipt,
        candidate_csv_path=candidate_features_path,
        reference_csv_path=reference_features_path,
        registry=registry,
        key=key,
        signed_registry=signed_registry,
        expected_reviewer_id=expected_reviewer_id,
        reference_roster_path=reference_roster_path,
        candidate_roster_path=candidate_roster_path,
        study_conn=study_conn,
        dataset_access_record=dataset_access_record,
        dua_document_path=dua_document_path,
    )
    if not is_valid:
        raise PermissionError(f"External evaluation rejected: {reason}")

    target_bundle = bundle_path or DEFAULT_MODEL_PATH
    if not target_bundle.is_file():
        raise FileNotFoundError(
            f"MODEL_ARTIFACT_NOT_VERIFIED: Frozen model binary missing at {target_bundle}."
        )
    if bundle_path is None:
        identity = verify_frozen_model_identity(target_bundle)
        if not identity.get("verified"):
            raise ValueError(f"{identity.get('status')}: {identity.get('reason')}")

    bundle = load_frozen_reference_model(bundle_path)
    features_df = pd.read_csv(candidate_features_path)
    metrics = evaluate_frozen_model_on_cohort(bundle, features_df)
    return {
        "status": "CANDIDATE_DOMAIN_EVALUATED_PENDING_REVIEW",
        "receipt_sha256": (
            receipt.receipt_sha256
            if isinstance(receipt, EvaluationProvenanceReceipt)
            else receipt.get("receipt_sha256")
        ),
        "receipt_hmac": (
            receipt.receipt_hmac
            if isinstance(receipt, EvaluationProvenanceReceipt)
            else receipt.get("receipt_hmac")
        ),
        "performance_metrics": {k: v.to_dict() for k, v in metrics.items()},
        "inference_eligible": False,
    }
