"""Reproducible M6 dataset readiness, multi-model training, calibration, and registry CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from voxneuro.modeling.dataset_readiness import build_dataset_readiness_report  # noqa: E402
from voxneuro.modeling.m6_experiment import (  # noqa: E402
    generate_m6_model_card,
    render_model_card_html,
    run_m6_comparative_experiments,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run VoxNeuro M6 ML benchmarking & readiness report."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "reports" / "model_evaluation",
        help="Directory for generated M6 evaluation and readiness reports.",
    )
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    readiness = build_dataset_readiness_report()
    experiment = run_m6_comparative_experiments(random_seed=args.seed)
    model_card = generate_m6_model_card(experiment)
    model_card_html = render_model_card_html(model_card)

    (args.output_dir / "m6_dataset_readiness.json").write_text(
        json.dumps(readiness, indent=2), encoding="utf-8"
    )
    (args.output_dir / "m6_experiment_summary.json").write_text(
        json.dumps(experiment, indent=2, default=str), encoding="utf-8"
    )
    (args.output_dir / "m6_model_card.json").write_text(
        json.dumps(model_card, indent=2, default=str), encoding="utf-8"
    )
    (args.output_dir / "m6_model_card.html").write_text(model_card_html, encoding="utf-8")
    print(f"Wrote M6 readiness, experiment, and model card outputs to {args.output_dir}")
    print(f"Cohorts evaluated: {experiment['cohorts_evaluated']}")
    for row in experiment["multi_family_benchmarks"]:
        print(
            f"  {row['cohort']} | {row['model_family']}: "
            f"ROC-AUC={row['roc_auc']} BA={row['balanced_accuracy']} "
            f"Brier={row['brier_score']} ECE={row['ece']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
