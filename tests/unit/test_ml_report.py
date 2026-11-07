import pandas as pd

from voxneuro.reporting.ml_report import render_nested_evaluation_html, summarize_nested_metrics


def test_nested_summary_and_standalone_html_report_escape_user_text():
    metrics = pd.DataFrame(
        [
            {
                "model": "logistic_l2",
                "repeat_seed": 7,
                "n_participants": 20,
                "score_kind": "uncalibrated_probability",
                "accuracy": 0.7,
                "balanced_accuracy": 0.7,
                "precision": 0.75,
                "sensitivity": 0.6,
                "specificity": 0.8,
                "f1": 0.67,
                "roc_auc": 0.8,
                "pr_auc": 0.77,
                "average_precision": 0.78,
                "brier_score": 0.2,
                "mcc": 0.4,
                "tn": 8,
                "fp": 2,
                "fn": 4,
                "tp": 6,
                "balanced_accuracy_ci_low": 0.5,
                "balanced_accuracy_ci_high": 0.9,
            },
            {
                "model": "logistic_l2",
                "repeat_seed": 8,
                "n_participants": 20,
                "score_kind": "uncalibrated_probability",
                "accuracy": 0.75,
                "balanced_accuracy": 0.75,
                "precision": 0.8,
                "sensitivity": 0.7,
                "specificity": 0.8,
                "f1": 0.75,
                "roc_auc": 0.82,
                "pr_auc": 0.79,
                "average_precision": 0.8,
                "brier_score": 0.19,
                "mcc": 0.5,
                "tn": 8,
                "fp": 2,
                "fn": 3,
                "tp": 7,
            },
        ]
    )
    summary = summarize_nested_metrics(metrics, primary_seed=7)
    assert summary.loc[0, "balanced_accuracy_mean"] == 0.725
    assert summary.loc[0, "balanced_accuracy_ci_low"] == 0.5

    report = render_nested_evaluation_html(
        dataset_name="Test <dataset>",
        source_description="Local source",
        participant_count=20,
        pd_participants=10,
        hc_participants=10,
        recording_count=20,
        feature_description="Core39",
        outer_splits=5,
        inner_splits=3,
        repeat_seeds=(7, 8),
        summary=summary,
        predictions=pd.DataFrame(
            {
                "model": ["logistic_l2", "logistic_l2"],
                "repeat_seed": [7, 7],
                "y_true": [0, 1],
                "score": [0.2, 0.8],
            }
        ),
        primary_seed=7,
        fold_metrics=pd.DataFrame({"model": ["logistic_l2"], "balanced_accuracy": [0.7]}),
        tuning_results=pd.DataFrame(
            {
                "model": ["logistic_l2"],
                "repeat_seed": [7],
                "outer_fold": [1],
                "selected_parameters": ['{"classifier__C": 1.0}'],
            }
        ),
        limitations=("Research only",),
    )
    assert "Test &lt;dataset&gt;" in report
    assert "participant-level nested cross-validation" in report
    assert "ROC curves from outer-fold participant-level scores" in report
    assert "no remote scripts" in report
    assert "https://" not in report


def test_nested_report_displays_outer_fold_metrics():
    metrics = pd.DataFrame(
        [
            {
                "model": "logistic_l2",
                "repeat_seed": 2026,
                "n_participants": 20,
                "score_kind": "uncalibrated_probability",
                "accuracy": 0.72,
                "balanced_accuracy": 0.72,
                "precision": 0.75,
                "sensitivity": 0.70,
                "specificity": 0.75,
                "f1": 0.72,
                "roc_auc": 0.80,
                "pr_auc": 0.78,
                "average_precision": 0.78,
                "brier_score": 0.20,
                "mcc": 0.45,
                "tn": 8,
                "fp": 2,
                "fn": 3,
                "tp": 7,
                "balanced_accuracy_ci_low": 0.6,
                "balanced_accuracy_ci_high": 0.85,
            }
        ]
    )
    summary = summarize_nested_metrics(metrics, primary_seed=2026)
    fold_metrics = pd.DataFrame(
        {
            "model": ["logistic_l2", "logistic_l2"],
            "balanced_accuracy": [0.70, 0.74],
            "roc_auc": [0.78, 0.82],
            "average_precision": [0.75, 0.81],
        }
    )
    report = render_nested_evaluation_html(
        dataset_name="UAMS",
        source_description="Telephone UAMS cohort",
        participant_count=78,
        pd_participants=37,
        hc_participants=41,
        recording_count=78,
        feature_description="Core39",
        outer_splits=5,
        inner_splits=3,
        repeat_seeds=(2026,),
        summary=summary,
        predictions=pd.DataFrame(
            {
                "model": ["logistic_l2", "logistic_l2"],
                "repeat_seed": [2026, 2026],
                "y_true": [0, 1],
                "score": [0.2, 0.8],
            }
        ),
        primary_seed=2026,
        fold_metrics=fold_metrics,
        tuning_results=pd.DataFrame(
            {
                "model": ["logistic_l2"],
                "repeat_seed": [2026],
                "outer_fold": [1],
                "selected_parameters": ['{"classifier__C": 1.0}'],
            }
        ),
        limitations=("Research limitation",),
    )
    assert "Outer-fold ROC-AUC" in report
    assert "Outer-fold Average Precision" in report
    assert "Logistic regression (L2): 0.800" in report
    assert "Logistic regression (L2): 0.780" in report
