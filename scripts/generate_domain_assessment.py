"""Generate versioned candidate domain assessment dossier (voxneuro.domain_assessment.v1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voxneuro.modeling.domain_assessment import (
    create_pending_framework_assessment_dossier,
)
from voxneuro.modeling.domain_registry import load_domain_registry

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "review_evidence" / "m4_domain_assessment.json",
        help="Target output path for assessment dossier JSON",
    )
    args = parser.parse_args()

    registry = load_domain_registry()
    dossier = create_pending_framework_assessment_dossier(registry=registry)

    # Save to requested output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dossier_json = dossier.to_json(indent=2)
    args.output.write_text(dossier_json + "\n", encoding="utf-8")

    # Also mirror into artifacts/reports/domain_validation/
    artifacts_dir = ROOT / "artifacts" / "reports" / "domain_validation"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "m4_domain_assessment.json").write_text(dossier_json + "\n", encoding="utf-8")

    digest = dossier.fingerprint()
    print("Generated candidate domain assessment dossier:")
    print(f"- Schema Version: {dossier.schema_version}")
    print(f"- Assessment ID: {dossier.assessment_id}")
    print(f"- Status: {dossier.status}")
    print(f"- Fingerprint: {digest}")
    print(f"- Written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
