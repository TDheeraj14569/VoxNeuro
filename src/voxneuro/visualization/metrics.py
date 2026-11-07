"""Grouped-fold metric visualization."""

import pandas as pd
from matplotlib.figure import Figure


def fold_metric_figure(metrics: pd.DataFrame, metric: str = "balanced_accuracy"):
    fig = Figure(figsize=(8, 3.5))
    ax = fig.subplots()
    metrics.boxplot(column=metric, by="model", ax=ax, grid=False)
    ax.set(
        title=f"Participant-wise cross-validation: {metric}",
        xlabel="Research baseline",
        ylabel=metric.replace("_", " "),
    )
    fig.suptitle("")
    fig.tight_layout()
    return fig
