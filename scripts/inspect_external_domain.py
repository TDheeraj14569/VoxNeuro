"""Inspect candidate external recording-domain audio and acquisition metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from voxneuro.modeling.domain_registry import load_domain_registry

ROOT = Path(__file__).resolve().parents[1]


def inspect_domain(domain_id: str, audio_dir: Path | None = None) -> dict:
    registry = load_domain_registry()
    if not registry.is_registered(domain_id):
        print(f"Error: Domain {domain_id!r} is not registered in recording_domain_registry.yaml")
        return {"status": "UNREGISTERED_DOMAIN", "domain_id": domain_id}

    entry = registry.get_domain(domain_id)
    meta = entry.metadata

    summary = {
        "domain_id": entry.domain_id,
        "domain_name": entry.domain_name,
        "domain_category": entry.domain_category,
        "candidate_compatibility_status": entry.candidate_compatibility_status,
        "inference_eligible": entry.inference_eligible,
        "acquisition_metadata": meta.to_dict(),
        "audio_files_found": 0,
        "audio_directory": str(audio_dir) if audio_dir else None,
        "inspection_status": "NO_AUDIO_DIRECTORY_SPECIFIED",
    }

    if audio_dir is not None:
        if not audio_dir.exists():
            summary["inspection_status"] = "AUDIO_DIRECTORY_NOT_FOUND"
        else:
            wav_files = list(audio_dir.rglob("*.wav"))
            summary["audio_files_found"] = len(wav_files)
            summary["inspection_status"] = (
                "AUDIO_FILES_LOCATED" if wav_files else "NO_WAV_FILES_FOUND"
            )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="neurovoz_studio", help="Canonical domain ID")
    parser.add_argument("--audio-dir", type=Path, default=None, help="Path to raw audio directory")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args()

    result = inspect_domain(args.domain, args.audio_dir)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"=== Domain Inspection: {result['domain_id']} ===")
        print(f"Name: {result['domain_name']}")
        print(f"Category: {result['domain_category']}")
        print(f"Compatibility Status: {result['candidate_compatibility_status']}")
        print(f"Inference Eligible: {result['inference_eligible']}")
        print(f"Inspection Status: {result['inspection_status']}")
        print(f"Audio Files Count: {result['audio_files_found']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
