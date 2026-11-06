"""Grouped-fold metric visualization."""

import matplotlib.pyplot as plt
import pandas as pd


def fold_metric_figure(metrics: pd.DataFrame, metric: str = "balanced_accuracy"):
    fig, ax = plt.subplots(figsize=(8, 3.5))
    metrics.boxplot(column=metric, by="model", ax=ax, grid=False)
    ax.set(
        title=f"Participant-wise cross-validation: {metric}",
        xlabel="Research baseline",
        ylabel=metric.replace("_", " "),
    )
    fig.suptitle("")
    fig.tight_layout()
    return fig
