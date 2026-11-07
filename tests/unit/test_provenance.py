import hashlib

import pytest

from voxneuro.provenance import combined_file_sha256


def test_combined_file_sha256_hashes_ordered_contents(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_bytes(b'{"receipt":1}')
    second.write_bytes(b'{"receipt":2}')

    expected = hashlib.sha256(first.read_bytes() + second.read_bytes()).hexdigest()
    assert combined_file_sha256(first, second) == expected
    assert combined_file_sha256(second, first) != expected


def test_combined_file_sha256_requires_files(tmp_path):
    with pytest.raises(ValueError, match="At least one file"):
        combined_file_sha256()
    with pytest.raises(FileNotFoundError):
        combined_file_sha256(tmp_path / "missing.json")


def test_release_provenance_contract_and_determinism():
    from voxneuro.provenance import (
        frontend_code_fingerprint,
        project_code_fingerprint,
        release_provenance,
    )

    prov = release_provenance()
    assert isinstance(prov, dict)
    assert "model_pipeline_fingerprint" in prov
    assert "frontend_fingerprint" in prov
    assert len(prov["model_pipeline_fingerprint"]) == 64
    assert len(prov["frontend_fingerprint"]) == 64
    assert prov["model_pipeline_fingerprint"] == project_code_fingerprint()
    assert prov["frontend_fingerprint"] == frontend_code_fingerprint()
