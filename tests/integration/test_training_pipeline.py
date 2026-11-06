import pandas as pd

from tests.fixtures.synthetic_manifest import binary_groups
from voxneuro.modeling.evaluation import evaluate_grouped
from voxneuro.modeling.training import fit_final_research_model


def test_grouped_evaluation_and_fixed_fit_are_usable():
    X, y, groups = binary_groups(30, 1)
    metrics, _ = evaluate_grouped(X, y, groups, n_splits=5)
    assert not metrics.empty
    model = fit_final_research_model(X, y)
    assert len(model.predict(pd.DataFrame(X.iloc[:2]))) == 2
