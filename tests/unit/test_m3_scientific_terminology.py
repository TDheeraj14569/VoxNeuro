"""Unit tests for M3 Scientific Terminology, Protocol and Construct Verification.

Verifies that M3 documentation across `docs/` adheres to scientific rigor:
1. Prohibits unsupported reference ranges for Vowel Space Area (VSA).
2. Prevents deterministic Parkinson's diagnostic claims based on VSA.
3. Verifies DDK is described as acoustic event timing rather than motor planning.
4. Verifies connected speech is described as acoustic VAD proxies rather than respiration.
5. Verifies audio formants are not claimed to directly measure physical articulatory movement.
6. Verifies sustained vowels are not claimed to directly measure mucosal wave symmetry.
7. Confirms synthetic audio fixtures are strictly characterized as software tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DOCS_DIR = Path("docs")
M3_DOCS = [
    DOCS_DIR / "M3_FEATURE_SCHEMA.md",
    DOCS_DIR / "M3_TASK_PROTOCOL.md",
    DOCS_DIR / "M3_ALGORITHM_LIMITATIONS.md",
    DOCS_DIR / "audit" / "M3_COMPLETION_REPORT.md",
]


def test_m3_docs_exist() -> None:
    """Ensure all required M3 documentation files exist."""
    for doc in M3_DOCS:
        assert doc.exists(), f"Required M3 documentation missing: {doc}"


def test_no_unsupported_healthy_vsa_ranges() -> None:
    """Ensure no docs state unsupported typical healthy ranges for VSA."""
    forbidden_vsa_patterns = [
        r"(?i)typical healthy range[:\s]*250,?000",
        r"(?i)healthy range[:\s]*250,?000",
        r"250,?000\s*[\u2013\-]\s*450,?000\s*(?:\\text\{Hz\}|Hz)\^?2",
    ]

    all_md = list(DOCS_DIR.rglob("*.md"))
    violations: list[str] = []
    for md_file in all_md:
        content = md_file.read_text(encoding="utf-8")
        for pat in forbidden_vsa_patterns:
            if re.search(pat, content):
                violations.append(f"{md_file}: matches unsupported VSA range pattern '{pat}'")

    assert not violations, "Found unsupported healthy VSA ranges:\n" + "\n".join(violations)


def test_no_deterministic_parkinsons_claims_from_vsa() -> None:
    """Ensure VSA is not deterministically linked to PD diagnosis or centralization."""
    all_md = list(DOCS_DIR.rglob("*.md"))
    violations: list[str] = []
    for md_file in all_md:
        content = md_file.read_text(encoding="utf-8").lower()
        if "causes articulatory centralization, reducing vsa" in content:
            violations.append(
                f"{md_file}: deterministic claim 'causes articulatory centralization, reducing VSA'"
            )
        if "lower vsa proves" in content:
            violations.append(f"{md_file}: contains unscientific claim 'lower VSA proves'")

    assert not violations, "Found deterministic VSA claims:\n" + "\n".join(violations)

    # Check that M3_FEATURE_SCHEMA.md contains the approved cautious interpretation
    schema_doc = DOCS_DIR / "M3_FEATURE_SCHEMA.md"
    schema_txt = schema_doc.read_text(encoding="utf-8")
    assert (
        "Vowel Space Area is a descriptive acoustic measure derived from estimated F1/F2 locations"
        in schema_txt
    ), "M3_FEATURE_SCHEMA.md missing required descriptive VSA construct definition"
    assert (
        "Reduced vowel-space measures have been reported in some speech research" in schema_txt
    ), "M3_FEATURE_SCHEMA.md missing cautious literature-attributed VSA statement"


def test_ddk_does_not_claim_direct_motor_planning() -> None:
    """Ensure DDK task does not claim direct measurement of motor planning or physical velocity."""
    protocol_doc = DOCS_DIR / "M3_TASK_PROTOCOL.md"
    txt = protocol_doc.read_text(encoding="utf-8")

    # Paradigm 2 must not have Clinical Target claiming motor planning
    m = re.search(r"### Paradigm 2:[^\n]*\n.*?- \*\*Clinical Target:\*\*", txt, re.DOTALL)
    assert m is None, "Paradigm 2 still uses heading 'Clinical Target'"

    assert "does not directly measure motor planning, physical articulatory velocity" in txt, (
        "M3_TASK_PROTOCOL.md must explicitly clarify DDK does not directly measure motor planning"
    )


def test_connected_speech_does_not_claim_direct_breathing_measurement() -> None:
    """Ensure connected speech task does not claim direct measurement of respiratory physiology."""
    protocol_doc = DOCS_DIR / "M3_TASK_PROTOCOL.md"
    txt = protocol_doc.read_text(encoding="utf-8")

    m = re.search(r"### Paradigm 3:[^\n]*\n.*?- \*\*Clinical Target:\*\*", txt, re.DOTALL)
    assert m is None, "Paradigm 3 still uses heading 'Clinical Target'"

    assert (
        "does not directly measure respiratory coordination, lung capacity, breath-group physiology"
        in txt
    ), "M3_TASK_PROTOCOL.md must clarify connected speech does not measure respiratory physiology"


def test_vowel_space_does_not_claim_physical_articulatory_movement() -> None:
    """Ensure VSA task does not claim direct measurement of physical articulatory movement."""
    protocol_doc = DOCS_DIR / "M3_TASK_PROTOCOL.md"
    txt = protocol_doc.read_text(encoding="utf-8")

    m = re.search(r"### Paradigm 4:[^\n]*\n.*?- \*\*Clinical Target:\*\*", txt, re.DOTALL)
    assert m is None, "Paradigm 4 still uses heading 'Clinical Target'"

    assert (
        "does not directly measure physical articulatory movement or oral cavity range of motion"
        in txt
    ), "M3_TASK_PROTOCOL.md must clarify VSA does not directly measure articulatory movement"


def test_sustained_vowel_does_not_claim_mucosal_wave_measurement() -> None:
    """Ensure sustained vowel task does not claim direct mucosal wave measurement."""
    protocol_doc = DOCS_DIR / "M3_TASK_PROTOCOL.md"
    txt = protocol_doc.read_text(encoding="utf-8")

    m = re.search(r"### Paradigm 1:[^\n]*\n.*?- \*\*Clinical Target:\*\*", txt, re.DOTALL)
    assert m is None, "Paradigm 1 still uses heading 'Clinical Target'"

    assert (
        "does not directly measure laryngeal mucosal wave motion or vocal fold micro-tremor" in txt
    ), "M3_TASK_PROTOCOL.md must clarify vowel task does not directly measure mucosal wave motion"


def test_synthetic_fixtures_strictly_software_verification() -> None:
    """Ensure synthetic fixture evidence explicitly disclaims clinical validation."""
    evidence_file = Path("review_evidence/m3_synthetic_fixture_verification.json")
    if evidence_file.exists():
        data = json.loads(evidence_file.read_text(encoding="utf-8"))
        disclaimer = data.get("disclaimer", "")
        assert (
            "software implementation correctness" in disclaimer
            or "algorithmic correctness" in disclaimer
        ), "Synthetic fixture disclaimer missing software verification clarification"
        assert (
            "does not establish a healthy reference range" in disclaimer
            or "not constitute clinical validation" in disclaimer
        ), (
            "Synthetic fixture disclaimer must disclaim "
            "healthy reference range / clinical validation"
        )

    report = DOCS_DIR / "audit" / "M3_COMPLETION_REPORT.md"
    report_txt = report.read_text(encoding="utf-8")
    assert (
        "A synthetic VSA passing a fixture bound does not establish a healthy reference range"
        in report_txt
    ), "M3_COMPLETION_REPORT.md missing explicit synthetic fixture limitations"
