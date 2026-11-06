import numpy as np
import pytest

from tests.fixtures.synthetic_manifest import binary_groups
from voxneuro.exceptions import DatasetError
from voxneuro.modeling.splits import grouped_splits


def test_grouped_splits_have_no_participant_overlap_and_cover_rows_once():
    _, y, groups = binary_groups(30, 3)
    folds = list(grouped_splits(y, groups, n_splits=5))
    seen = []
    for train, test in folds:
        assert set(groups[train]).isdisjoint(groups[test])
        seen.extend(test.tolist())
    assert sorted(seen) == list(range(len(y)))


def test_grouped_splits_require_ids():
    with pytest.raises(DatasetError):
        list(grouped_splits(np.array([0, 1, 0, 1]), np.array(["a", None, "b", "c"]), 2))


def test_grouped_splits_reject_conflicting_participant_diagnoses():
    y = np.asarray([0, 0, 1, 1, 0, 1])
    groups = np.asarray(["a", "a", "b", "b", "c", "c"])
    with pytest.raises(DatasetError, match="consistent diagnosis"):
        list(grouped_splits(y, groups, n_splits=2))


@pytest.mark.parametrize("invalid", [0.5, np.nan, 2])
def test_grouped_splits_reject_non_binary_labels(invalid):
    y = np.asarray([0, 1, 0, 1, invalid, 1])
    groups = np.asarray(["a", "b", "c", "d", "e", "f"])
    with pytest.raises(DatasetError, match="Labels must"):
        list(grouped_splits(y, groups, n_splits=2))


def test_grouped_splits_require_both_classes_in_each_fold():
    y = np.asarray([0, 0, 0, 0, 1, 1])
    groups = np.asarray(["a", "b", "c", "d", "e", "f"])
    with pytest.raises(DatasetError, match="at least 3 distinct participants"):
        list(grouped_splits(y, groups, n_splits=3))
