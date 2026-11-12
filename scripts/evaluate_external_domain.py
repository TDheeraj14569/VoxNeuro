"""Evaluate candidate external recording domain against the frozen reference model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from voxneuro.modeling.domain_evaluation import (
    evaluate_frozen_model_on_cohort,
    load_frozen_reference_model,
    verify_evaluation_provenance_receipt,
    verify_frozen_model_identity,
)
from voxneuro.modeling.domain_registry import load_domain_registry
from voxneuro.modeling.domain_shift import (
    compare_acquisition_metadata,
    compute_feature_shift,
    summarize_domain_shift,
)
from voxneuro.modeling.trust_registry import (
    AuthorizationTrustRootError,
    load_and_verify_authorization_registry,
)
from voxneuro.study.database import get_connection

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="neurovoz_studio", help="Candidate domain identifier")
    parser.add_argument(
        "--features-path", type=Path, default=None, help="Path to extracted features CSV"
    )
    parser.add_argument(
        "--receipt-path", type=Path, default=None, help="Path to validated provenance receipt JSON"
    )
    parser.add_argument(
        "--study-db",
        type=Path,
        default=None,
        help="Path to SQLite study governance database containing authoritative dataset_access",
    )
    parser.add_argument(
        "--reference-roster-path",
        type=Path,
        default=None,
        help="Path to reference dataset participant roster file",
    )
    parser.add_argument(
        "--candidate-roster-path",
        type=Path,
        default=None,
        help="Path to candidate dataset participant roster file",
    )
    parser.add_argument(
        "--authorization-registry",
        type=Path,
        default=None,
        help="Path to Ed25519-signed M4 authorization trust registry JSON",
    )
    parser.add_argument(
        "--authorization-registry-signature",
        type=Path,
        default=None,
        help="Path to detached Ed25519 signature file for the authorization registry",
    )
    parser.add_argument(
        "--reviewer-id",
        default="",
        help="Claimed reviewer identifier (validated strictly against the signed trust registry)",
    )
    parser.add_argument(
        "--dua-document",
        type=Path,
        default=None,
        help="Path to the authenticated DUA document artifact whose SHA-256 binds DB and registry",
    )
    parser.add_argument(
        "--authorized-reviewers",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--authorized-sources-json",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--out-dir", type=Path, default=ROOT / "artifacts" / "reports" / "domain_validation"
    )
    parser.add_argument("--json", action="store_true", help="Print summary as JSON")
    args = parser.parse_args()

    # Reject deprecated unsigned caller-supplied authorization arguments under all modes
    if args.authorized_reviewers is not None or args.authorized_sources_json is not None:
        print(
            "Error: AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: insecure unsigned flags "
            "--authorized-reviewers and --authorized-sources-json are disabled. "
            "Supply --authorization-registry, --authorization-registry-signature, "
            "and --reviewer-id."
        )
        return 1

    registry = load_domain_registry()
    if not registry.is_registered(args.domain):
        print(f"Error: Unknown domain {args.domain!r}")
        return 1

    entry = registry.get_domain(args.domain)
    ref_entry = registry.get_domain("uams_telephone")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    acq_diffs = compare_acquisition_metadata(ref_entry.metadata.to_dict(), entry.metadata.to_dict())
    model_identity = verify_frozen_model_identity()

    if args.features_path is None or not args.features_path.is_file():
        trust_status = "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"
        if (
            args.authorization_registry is not None
            and args.authorization_registry_signature is not None
        ):
            try:
                load_and_verify_authorization_registry(
                    args.authorization_registry, args.authorization_registry_signature
                )
                trust_status = "AUTHORIZATION_TRUST_ROOT_VERIFIED"
            except AuthorizationTrustRootError:
                trust_status = "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"

        summary = {
            "domain_id": entry.domain_id,
            "status": "FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING",
            "model_artifact_status": model_identity["status"],
            "authorization_trust_root_status": trust_status,
            "decision_rationale": (
                f"Candidate domain {entry.domain_id!r} evaluation framework verified. "
                "Independent raw audio or extracted features are not present in "
                "the local workspace. "
                "Validation is pending signed trust-registry authorization and an executed DUA."
            ),
            "acquisition_differences": acq_diffs,
            "inference_eligible": False,
        }
        report_file = args.out_dir / f"{entry.domain_id}_evaluation_status.json"
        report_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"=== Domain Evaluation Status: {entry.domain_id} ===")
            print(f"Status: {summary['status']}")
            print(f"Model Status: {summary['model_artifact_status']}")
            print(f"Trust Root Status: {summary['authorization_trust_root_status']}")
            print(f"Rationale: {summary['decision_rationale']}")
            print(f"Report written to: {report_file}")
        return 0

    if not model_identity.get("verified"):
        print(f"Error: {model_identity['status']}: {model_identity['reason']}")
        return 1

    # Step 1: Verify the signed M4 authorization trust registry before inspecting anything else
    if (
        args.authorization_registry is None
        or not args.authorization_registry.is_file()
        or args.authorization_registry_signature is None
        or not args.authorization_registry_signature.is_file()
    ):
        print(
            "Error: AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: signed authorization registry "
            "(--authorization-registry) and signature (--authorization-registry-signature) "
            "are required."
        )
        return 1

    try:
        verified_trust_reg, signed_env = load_and_verify_authorization_registry(
            args.authorization_registry,
            args.authorization_registry_signature,
        )
    except AuthorizationTrustRootError as exc:
        print(f"Error: {exc}")
        return 1

    if not str(args.reviewer_id or "").strip():
        print(
            "Error: --reviewer-id is required for attestation validation. "
            "Status: INDEPENDENCE_NOT_VERIFIED"
        )
        return 1

    if args.receipt_path is None or not args.receipt_path.is_file():
        print(
            "Error: Provenance receipt is required for external feature evaluation "
            "(--receipt-path). Status: INDEPENDENCE_NOT_VERIFIED"
        )
        return 1

    if args.study_db is None or not args.study_db.is_file():
        print(
            "Error: Authoritative study governance database (--study-db) is required. "
            "Status: DATASET_AUTHORIZATION_NOT_VERIFIED"
        )
        return 1

    if (
        args.reference_roster_path is None
        or not args.reference_roster_path.is_file()
        or args.candidate_roster_path is None
        or not args.candidate_roster_path.is_file()
    ):
        print(
            "Error: Source participant roster paths (--reference-roster-path and "
            "--candidate-roster-path) are required. Status: INDEPENDENCE_NOT_VERIFIED"
        )
        return 1

    if args.dua_document is None or not args.dua_document.is_file():
        print(
            "Error: Authenticated DUA document artifact (--dua-document) is required. "
            "Status: DATASET_AUTHORIZATION_NOT_VERIFIED"
        )
        return 1

    try:
        receipt_data = json.loads(args.receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error reading provenance receipt JSON: {exc}")
        return 1

    uams_path = ROOT / "data" / "processed" / "voice_features.csv"
    conn = get_connection(args.study_db)
    try:
        is_valid, reason = verify_evaluation_provenance_receipt(
            receipt_data,
            candidate_csv_path=args.features_path,
            reference_csv_path=uams_path if uams_path.is_file() else None,
            registry=registry,
            signed_registry=signed_env,
            expected_reviewer_id=args.reviewer_id,
            reference_roster_path=args.reference_roster_path,
            candidate_roster_path=args.candidate_roster_path,
            study_conn=conn,
            dua_document_path=args.dua_document,
        )
    finally:
        conn.close()
    if not is_valid:
        print(f"Error: Provenance receipt verification failed: {reason}")
        return 1

    bundle = load_frozen_reference_model()
    features_df = pd.read_csv(args.features_path)
    metrics = evaluate_frozen_model_on_cohort(bundle, features_df)

    shift_summary = None
    if uams_path.is_file():
        uams_df = pd.read_csv(uams_path)
        shift_df = compute_feature_shift(uams_df, features_df)
        shift_csv = args.out_dir / f"{entry.domain_id}_feature_shift.csv"
        shift_df.to_csv(shift_csv, index=False)
        shift_summary = summarize_domain_shift(shift_df, acq_diffs).to_dict()

    eval_summary = {
        "domain_id": entry.domain_id,
        "status": "CANDIDATE_DOMAIN_EVALUATED_PENDING_REVIEW",
        "authorization_registry_id": verified_trust_reg.registry_id,
        "authorization_registry_version": verified_trust_reg.registry_version,
        "authorization_registry_fingerprint": verified_trust_reg.registry_fingerprint,
        "verified_reviewer_id": args.reviewer_id,
        "performance_metrics": {k: v.to_dict() for k, v in metrics.items()},
        "domain_shift_summary": shift_summary,
        "inference_eligible": False,
    }
    report_file = args.out_dir / f"{entry.domain_id}_evaluation_results.json"
    report_file.write_text(json.dumps(eval_summary, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(eval_summary, indent=2))
    else:
        print(f"=== Domain Evaluation Completed: {entry.domain_id} ===")
        print(f"Status: {eval_summary['status']}")
        for k, v in metrics.items():
            print(f"- {k}: {v.point_estimate} (status: {v.status})")
        print(f"Report written to: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
