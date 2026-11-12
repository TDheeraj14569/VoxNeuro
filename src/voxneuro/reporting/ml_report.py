"""Self-contained HTML summaries for nested research-model evaluations."""

from __future__ import annotations

import html
import math
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve

METRICS = (
    ("accuracy", "Accuracy"),
    ("precision", "Precision"),
    ("sensitivity", "Sensitivity / recall"),
    ("specificity", "Specificity"),
    ("balanced_accuracy", "Balanced accuracy"),
    ("f1", "F1 score"),
    ("roc_auc", "ROC-AUC"),
    ("pr_auc", "Trapezoidal PR-AUC"),
    ("average_precision", "Average precision"),
    ("mcc", "Matthews correlation coefficient"),
    ("brier_score", "Brier score"),
)

MODEL_LABELS = {
    "dummy": "Prior dummy baseline",
    "logistic_l2": "Logistic regression (L2)",
    "logistic_elastic_net": "Logistic regression (elastic net)",
    "linear_svm": "Linear support-vector machine",
    "rbf_svm": "RBF support-vector machine",
    "random_forest": "Random forest",
    "extra_trees": "Extra Trees",
    "hist_gradient_boosting": "Histogram gradient boosting",
    "age_only_logistic": "Age-only logistic comparator",
    "age_plus_voice_logistic": "Age + voice logistic comparator",
    "majority_classifier": "Majority class baseline",
    "voice_only_svm": "Voice-only linear SVM",
    "voice_only_logistic": "Voice-only logistic regression (L2)",
    "sex_only_logistic": "Sex-only logistic comparator",
    "age_plus_sex_logistic": "Age + sex logistic comparator",
    "age_plus_sex_plus_voice_logistic": "Age + sex + voice logistic comparator",
    "matched_voice_svm": "Matched cohort voice SVM (NOT ESTIMABLE)",
}


def summarize_nested_metrics(metrics: pd.DataFrame, primary_seed: int) -> pd.DataFrame:
    """Summarize repeat-to-repeat performance and attach primary-repeat CIs."""
    if metrics.empty:
        raise ValueError("Nested evaluation metrics are empty.")
    metric_names = [name for name, _ in METRICS if name in metrics]
    rows = []
    for model, subset in metrics.groupby("model", sort=False):
        primary = subset.loc[subset["repeat_seed"].eq(primary_seed)]
        if len(primary) != 1:
            raise ValueError(f"Expected exactly one primary-seed result for {model}.")
        row = {
            "model": model,
            "model_label": MODEL_LABELS.get(model, model),
            "n_participants": int(subset["n_participants"].min()),
            "score_kind": str(subset["score_kind"].iloc[0]),
            "primary_seed": int(primary_seed),
        }
        for metric in metric_names:
            values = pd.to_numeric(subset[metric], errors="coerce").dropna()
            row[f"{metric}_mean"] = float(values.mean()) if not values.empty else math.nan
            row[f"{metric}_repeat_sd"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
            for bound in ("ci_low", "ci_high"):
                column = f"{metric}_{bound}"
                row[f"{metric}_{bound}"] = (
                    float(primary.iloc[0][column]) if column in primary else math.nan
                )
        for count_name in ("tn", "fp", "fn", "tp"):
            row[count_name] = int(primary.iloc[0][count_name])
        for outer_metric in (
            "outer_fold_roc_auc_mean",
            "outer_fold_roc_auc_sd",
            "outer_fold_ap_mean",
            "outer_fold_ap_sd",
        ):
            if outer_metric in subset.columns:
                vals = pd.to_numeric(subset[outer_metric], errors="coerce").dropna()
                row[outer_metric] = float(vals.mean()) if not vals.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _format_value(value: object, digits: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not available"
    return f"{number:.{digits}f}" if math.isfinite(number) else "Not available"


def _comparison_table(summary: pd.DataFrame) -> str:
    active_metrics = [
        (metric, label) for metric, label in METRICS if f"{metric}_mean" in summary.columns
    ]
    headers = ["Candidate"] + [label for _, label in active_metrics] + ["TN / FP / FN / TP"]
    output = ["<table><caption>Participant-level out-of-fold results</caption><thead><tr>"]
    output.extend(f"<th scope='col'>{html.escape(value)}</th>" for value in headers)
    output.append("</tr></thead><tbody>")
    for _, row in summary.iterrows():
        output.append(f"<tr><th scope='row'>{html.escape(str(row['model_label']))}</th>")
        for metric, _ in active_metrics:
            mean_key = f"{metric}_mean"
            sd_key = f"{metric}_repeat_sd"
            ci_low_key = f"{metric}_ci_low"
            ci_high_key = f"{metric}_ci_high"
            mean = _format_value(row[mean_key])
            sd = _format_value(row[sd_key])
            low = _format_value(row[ci_low_key])
            high = _format_value(row[ci_high_key])
            output.append(
                "<td>"
                f"{mean} <span class='muted'>± {sd} repeat SD</span>"
                f"<br><span class='interval'>Primary-seed participant bootstrap: "
                f"{low}–{high}</span></td>"
            )
        confusion = " / ".join(str(int(row[key])) for key in ("tn", "fp", "fn", "tp"))
        output.append(f"<td>{html.escape(confusion)}</td>")
        output.append("</tr>")
    output.append("</tbody></table>")
    return "".join(output)


def _curve_svg(predictions: pd.DataFrame, primary_seed: int, curve: str) -> str:
    """Build an accessible, self-contained SVG from primary-seed participant OOF scores."""
    selected = predictions.loc[predictions["repeat_seed"].eq(primary_seed)]
    colors = [
        "#087f83",
        "#b56d14",
        "#6654a3",
        "#bd4f67",
        "#3174a1",
        "#598142",
        "#35464f",
        "#9a6b45",
        "#c24f4f",
        "#4a6b82",
    ]
    x0, y0, width, height = 66.0, 24.0, 500.0, 220.0
    paths = []
    legends = []
    for index, (model, subset) in enumerate(selected.groupby("model", sort=False)):
        truth = subset["y_true"].to_numpy(dtype=int)
        score = subset["score"].to_numpy(dtype=float)
        if len(np.unique(truth)) != 2 or not np.isfinite(score).all():
            continue
        if curve == "roc":
            x_values, y_values, _ = roc_curve(truth, score)
        else:
            y_values, x_values, _ = precision_recall_curve(truth, score)
        points = [
            f"{x0 + float(x) * width:.1f},{y0 + (1.0 - float(y)) * height:.1f}"
            for x, y in zip(x_values, y_values, strict=True)
        ]
        color = colors[index % len(colors)]
        label = html.escape(MODEL_LABELS.get(str(model), str(model)))
        paths.append(
            f"<polyline fill='none' stroke='{color}' stroke-width='2.4' "
            f"points='{' '.join(points)}'/>"
        )
        legend_y = 296 + (index // 3) * 20
        legend_x = 70 + (index % 3) * 180
        legends.append(
            f"<line x1='{legend_x}' y1='{legend_y}' x2='{legend_x + 20}' "
            f"y2='{legend_y}' stroke='{color}' stroke-width='3'/>"
            f"<text x='{legend_x + 26}' y='{legend_y + 4}' font-size='11'>{label}</text>"
        )
    title = "ROC curves" if curve == "roc" else "Precision–recall curves"
    x_label = "False-positive rate" if curve == "roc" else "Recall"
    y_label = "True-positive rate" if curve == "roc" else "Precision"
    baseline = (
        f"<line x1='{x0}' y1='{y0 + height}' x2='{x0 + width}' y2='{y0}' "
        "stroke='#97aab0' stroke-dasharray='5 5'/>"
        if curve == "roc"
        else ""
    )
    ticks = (
        "<text x='66' y='256' text-anchor='middle' font-size='10' fill='#526a73'>0.0</text>"
        "<text x='316' y='256' text-anchor='middle' font-size='10' fill='#526a73'>0.5</text>"
        "<text x='566' y='256' text-anchor='middle' font-size='10' fill='#526a73'>1.0</text>"
        "<text x='58' y='247' text-anchor='end' font-size='10' fill='#526a73'>0.0</text>"
        "<text x='58' y='137' text-anchor='end' font-size='10' fill='#526a73'>0.5</text>"
        "<text x='58' y='28' text-anchor='end' font-size='10' fill='#526a73'>1.0</text>"
    )
    return (
        f"<svg viewBox='0 0 620 380' role='img' aria-label='{title} for primary seed "
        f"{primary_seed}' xmlns='http://www.w3.org/2000/svg'>"
        f"<title>{title} from outer-fold participant-level scores</title>"
        "<rect x='0' y='0' width='620' height='380' rx='10' fill='#fff'/>"
        f"<line x1='{x0}' y1='{y0 + height}' x2='{x0 + width}' "
        f"y2='{y0 + height}' stroke='#526a73'/>"
        f"<line x1='{x0}' y1='{y0}' x2='{x0}' y2='{y0 + height}' stroke='#526a73'/>"
        f"{ticks}"
        f"{baseline}{''.join(paths)}"
        f"<text x='316' y='272' text-anchor='middle' font-size='12'>{x_label}</text>"
        f"<text x='17' y='135' text-anchor='middle' font-size='12' "
        f"transform='rotate(-90 17 135)'>{y_label}</text>"
        f"{''.join(legends)}</svg>"
    )


def render_nested_evaluation_html(
    *,
    dataset_name: str,
    source_description: str,
    participant_count: int,
    pd_participants: int,
    hc_participants: int,
    recording_count: int,
    feature_description: str,
    outer_splits: int,
    inner_splits: int,
    repeat_seeds: tuple[int, ...],
    summary: pd.DataFrame,
    predictions: pd.DataFrame,
    primary_seed: int,
    fold_metrics: pd.DataFrame,
    tuning_results: pd.DataFrame,
    limitations: tuple[str, ...],
) -> str:
    """Render an offline HTML report with accessible tables and no remote assets."""
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    escaped_dataset = html.escape(dataset_name)
    escaped_source = html.escape(source_description)
    escaped_features = html.escape(feature_description)
    caveats = "".join(f"<li>{html.escape(item)}</li>" for item in limitations)
    seeds_text = ", ".join(str(seed) for seed in repeat_seeds)
    tuning_rows = []
    columns = ["model", "repeat_seed", "outer_fold", "selected_parameters"]
    for _, row in tuning_results[columns].iterrows():
        tuning_rows.append(
            "<tr>"
            f"<td>{html.escape(MODEL_LABELS.get(str(row['model']), str(row['model'])))}</td>"
            f"<td>{int(row['repeat_seed'])}</td>"
            f"<td>{int(row['outer_fold'])}</td>"
            f"<td><code>{html.escape(str(row['selected_parameters']))}</code></td>"
            "</tr>"
        )
    agg_kwargs = {
        "ba_mean": ("balanced_accuracy", "mean"),
        "ba_std": ("balanced_accuracy", "std"),
    }
    if "roc_auc" in fold_metrics.columns:
        agg_kwargs["auc_mean"] = ("roc_auc", "mean")
        agg_kwargs["auc_std"] = ("roc_auc", "std")
    if "average_precision" in fold_metrics.columns:
        agg_kwargs["ap_mean"] = ("average_precision", "mean")
        agg_kwargs["ap_std"] = ("average_precision", "std")
    fold_summary = fold_metrics.groupby("model", as_index=False).agg(**agg_kwargs)
    fold_ba_note = ", ".join(
        f"{MODEL_LABELS.get(str(row['model']), str(row['model']))}: "
        f"{float(row['ba_mean']):.3f} ± {float(row['ba_std']):.3f}"
        for _, row in fold_summary.iterrows()
    )
    fold_auc_note = (
        ", ".join(
            f"{MODEL_LABELS.get(str(row['model']), str(row['model']))}: "
            f"{float(row['auc_mean']):.3f} ± {float(row['auc_std']):.3f}"
            for _, row in fold_summary.iterrows()
            if not math.isnan(float(row["auc_mean"]))
        )
        if "auc_mean" in fold_summary.columns
        else ""
    )
    fold_ap_note = (
        ", ".join(
            f"{MODEL_LABELS.get(str(row['model']), str(row['model']))}: "
            f"{float(row['ap_mean']):.3f} ± {float(row['ap_std']):.3f}"
            for _, row in fold_summary.iterrows()
            if not math.isnan(float(row["ap_mean"]))
        )
        if "ap_mean" in fold_summary.columns
        else ""
    )
    roc_svg = _curve_svg(predictions, primary_seed, "roc")
    pr_svg = _curve_svg(predictions, primary_seed, "pr")
    html_parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>VoxNeuro — {escaped_dataset} nested model evaluation</title>",
        "<style>",
        ":root { color-scheme: light; --ink:#132b35; --muted:#526a73;",
        "--line:#d7e1e5; --accent:#087f83; --paper:#fff; --wash:#eef5f5; }",
        "* { box-sizing:border-box; }",
        "body { margin:0; background:#edf3f4; color:var(--ink);",
        "font:15px/1.6 Segoe UI,Arial,sans-serif; }",
        "main { max-width:1240px; margin:0 auto; padding:32px 22px 60px; }",
        "header { background:#102a36; color:white; border-radius:16px; padding:30px 34px; }",
        "h1 { margin:0 0 6px; font-size:30px; }",
        "header p { margin:4px 0; color:#d4e5e8; }",
        "section { margin-top:22px; background:var(--paper); border:1px solid var(--line);",
        "border-radius:14px; padding:22px 24px; box-shadow:0 4px 16px #18363d0b; }",
        "h2 { font-size:20px; margin:0 0 12px; }",
        ".charts { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); "
        "gap:14px; }",
        "figure { margin:0; } figure svg { display:block; width:100%; height:auto; }",
        ".facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); "
        "gap:10px; }",
        ".fact { background:var(--wash); padding:12px 14px; border-radius:9px; }",
        ".fact strong { display:block; font-size:20px; color:var(--accent); }",
        ".muted { display:block; color:var(--muted); font-size:12px; white-space:nowrap; }",
        ".interval { font-size:12px; color:var(--muted); }",
        ".scroll { overflow-x:auto; }",
        "table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }",
        "caption { text-align:left; font-weight:700; padding:0 0 10px; }",
        "th,td { border-bottom:1px solid var(--line); padding:10px 9px;",
        "text-align:left; vertical-align:top; }",
        "thead th { background:#f2f7f8; position:sticky; top:0; font-size:13px; }",
        "tbody th { min-width:185px; } td { min-width:150px; }",
        "code { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; }",
        ".note { border-left:4px solid #b56d14; background:#fff8eb; padding:12px 15px; }",
        "li { margin:.35em 0; }",
        "footer { margin-top:20px; color:var(--muted); font-size:13px; }",
        "@media(max-width:650px) { main { padding:14px 10px 36px; }",
        "header,section { padding:18px; } h1 { font-size:24px; } }",
        "</style>",
        "</head>",
        "<body><main>",
        "<header><h1>VoxNeuro · ML evaluation</h1>",
        f"<p>{escaped_dataset} · participant-level nested cross-validation</p>",
        f"<p>Generated {generated} · Research evaluation, not a diagnostic performance claim</p>",
        "</header>",
        "<section><h2>Study snapshot</h2><div class='facts'>",
        f"<div class='fact'><strong>{participant_count}</strong>participants</div>",
        f"<div class='fact'><strong>{pd_participants}</strong>PD group</div>",
        f"<div class='fact'><strong>{hc_participants}</strong>healthy-control group</div>",
        f"<div class='fact'><strong>{recording_count}</strong>recordings / rows</div>",
        (
            f"<div class='fact'><strong>{outer_splits} × {inner_splits}</strong>"
            "outer × inner folds</div>"
        ),
        f"<div class='fact'><strong>{len(repeat_seeds)}</strong>repeated seeds</div>",
        "</div>",
        f"<p><b>Source:</b> {escaped_source}</p>",
        f"<p><b>Predictors:</b> {escaped_features}</p>",
        f"<p><b>Seeds:</b> {html.escape(seeds_text)}.</p></section>",
        "<section><h2>Model comparison</h2>",
        (
            "<p>Each candidate's hyperparameters were tuned using only participant-grouped inner "
            "folds from each outer training partition. Predictions come from participants held "
            "out by the corresponding outer fold. Results show repeated-CV means and seed "
            "variability, plus a primary-seed participant bootstrap interval. The interval is "
            "conditional on the fitted CV models, not external-validation uncertainty.</p>"
        ),
        f"<div class='scroll'>{_comparison_table(summary)}</div></section>",
        "<section><h2>Primary-seed ranking curves</h2>",
        (
            "<p>Curves use participant-level outer-fold scores from the primary repeat. "
            "They show ranking behavior, not calibrated probabilities or external performance.</p>"
        ),
        "<div class='charts'>",
        f"<figure><figcaption>ROC curve · seed {primary_seed}</figcaption>{roc_svg}</figure>",
        (
            f"<figure><figcaption>Precision–recall curve · seed {primary_seed}</figcaption>"
            f"{pr_svg}</figure>"
        ),
        "</div></section>",
        "<section><h2>Model selection and score handling</h2>",
        (
            "<p>Candidate families are compared descriptively; this report does not declare a "
            "winning clinical model or tune a clinical threshold. The bundled logistic model "
            "remains an interpretable research reference. SVM decision scores are ranking scores, "
            "not probabilities. Values from <code>predict_proba</code> are uncalibrated model "
            "outputs. Brier score is descriptive and does not establish calibration. The default "
            "estimator decision rule is used; no threshold was optimized on held-out "
            "participants.</p>"
        ),
        f"<p>Outer-fold balanced accuracy: {html.escape(fold_ba_note)}.</p>",
        *(
            [
                f"<p>Outer-fold ROC-AUC (fold-averaged across outer folds, distinct from pooled "
                f"OOF): {html.escape(fold_auc_note)}.</p>"
            ]
            if fold_auc_note
            else []
        ),
        *(
            [
                f"<p>Outer-fold Average Precision (fold-averaged across outer folds, distinct from "
                f"pooled OOF): {html.escape(fold_ap_note)}.</p>"
            ]
            if fold_ap_note
            else []
        ),
        (
            "<p>Cross-validation partitions are grouped strictly by participant. "
            "In multi-recording cohorts, repeated samples are aggregated to the participant "
            "level before scoring. Imputation, scaling, fitting and hyperparameter selection "
            "occur strictly inside training folds.</p></section>"
        ),
        "<section><h2>Inner-fold selections</h2>",
        (
            "<p>Configurations were selected by inner-fold balanced accuracy and evaluated on "
            "the corresponding untouched outer fold.</p>"
        ),
        "<div class='scroll'><table><caption>Selected settings by outer fold</caption>",
        "<thead><tr><th>Candidate</th><th>Seed</th><th>Outer fold</th>",
        "<th>Selected parameters</th></tr></thead>",
        f"<tbody>{''.join(tuning_rows)}</tbody></table></div></section>",
        "<section><h2>Interpretation limits</h2>",
        (
            "<div class='note'><b>Do not use these results to diagnose or rule out Parkinson's "
            "disease.</b> These are internal retrospective cohort estimates.</div>"
        ),
        f"<ul>{caveats}</ul></section>",
        (
            "<footer>VoxNeuro is a research software prototype. Voice measurements are not "
            "specific to Parkinson's disease. This report has no remote scripts or "
            "resources.</footer>"
        ),
        "</main></body></html>",
    ]
    return "\n".join(html_parts)
