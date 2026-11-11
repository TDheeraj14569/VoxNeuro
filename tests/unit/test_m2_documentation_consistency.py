"""Unit tests for M2 Scientific Documentation Consistency and Integrity.

Verifies that project documentation across `docs/` adheres to scientific rigor:
1. Prohibits unsupported overstatements regarding incremental voice contributions.
2. Ensures primary-seed paired Delta Balanced Accuracy metrics match the authoritative M2 report.
3. Confirms 95% bootstrap confidence intervals are accurately documented.
4. Ensures McNemar's test is correctly qualified as supplementary rather than a primary
   test of BA difference.
5. Verifies explicit acknowledgement of scientific uncertainty regarding voice contribution.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS_DIR = Path("docs")

FORBIDDEN_PHRASES = [
    "zero incremental diagnostic power",
    "zero incremental predictive value",
    "zero incremental predictive accuracy",
    "zero incremental diagnostic accuracy",
    "voice adds zero diagnostic accuracy",
    "voice adds zero predictive accuracy",
    "definitively no voice",
    "conclusively useless",
    "zero diagnostic accuracy",
    "zero predictive value",
]

CORE_DOCS = [
    DOCS_DIR / "reports" / "M2_BIAS_AUDIT_REPORT.md",
    DOCS_DIR / "dataset" / "UAMS_DATASET_REPORT.md",
    DOCS_DIR / "limitations" / "RISK_ASSESSMENT.md",
    DOCS_DIR / "testing" / "VERIFICATION_REPORT.md",
    DOCS_DIR / "REPRODUCIBILITY.md",
    DOCS_DIR / "KNOWN_LIMITATIONS.md",
    DOCS_DIR / "reports" / "MODEL_CARD.md",
]


def test_core_docs_exist() -> None:
    """Ensure all core documentation targets exist."""
    for doc in CORE_DOCS:
        assert doc.exists(), f"Required documentation file missing: {doc}"


def test_no_forbidden_overstatements_in_docs() -> None:
    """Ensure no docs contain unscientific claims asserting absolute zero voice contribution."""
    all_md_files = list(DOCS_DIR.rglob("*.md"))
    assert len(all_md_files) > 0, "No markdown files found in docs/"

    violations: list[str] = []
    for md_file in all_md_files:
        content = md_file.read_text(encoding="utf-8")
        content_lower = content.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in content_lower:
                # Find line numbers for reporting
                for i, line in enumerate(content.splitlines(), 1):
                    if phrase in line.lower():
                        violations.append(f"{md_file}:{i}: '{phrase}' in '{line.strip()}'")

    assert not violations, "Found forbidden overstatement phrases in documentation:\n" + "\n".join(
        violations
    )


def test_primary_paired_delta_ba_values() -> None:
    """Verify primary-seed paired Delta Balanced Accuracy values match M2 authoritative results.

    Authoritative values from M2_BIAS_AUDIT_REPORT.md:
      Age + Voice vs Age Only: Delta BA = -0.0758
      Age + Sex + Voice vs Age + Sex: Delta BA = -0.0745
    """
    authoritative_report = DOCS_DIR / "reports" / "M2_BIAS_AUDIT_REPORT.md"
    auth_text = authoritative_report.read_text(encoding="utf-8")

    assert "-0.0758" in auth_text, "Authoritative report missing Age+Voice Delta BA -0.0758"
    assert "-0.0745" in auth_text, "Authoritative report missing Age+Sex+Voice Delta BA -0.0745"

    reports_checking_both = [
        DOCS_DIR / "REPRODUCIBILITY.md",
        DOCS_DIR / "testing" / "VERIFICATION_REPORT.md",
        DOCS_DIR / "KNOWN_LIMITATIONS.md",
        DOCS_DIR / "reports" / "MODEL_CARD.md",
    ]

    for doc in reports_checking_both:
        text = doc.read_text(encoding="utf-8")
        assert "-0.0758" in text, f"{doc} missing primary-seed Age+Voice Delta BA (-0.0758)"
        assert "-0.0745" in text, f"{doc} missing primary-seed Age+Sex+Voice Delta BA (-0.0745)"


def test_primary_paired_confidence_intervals() -> None:
    """Verify 95% bootstrap confidence intervals match M2 authoritative results.

    Authoritative CIs:
      Age + Voice vs Age: [-0.1842, +0.0284]
      Age + Sex + Voice vs Age + Sex: [-0.1843, +0.0310]
    """
    reports = [
        DOCS_DIR / "reports" / "M2_BIAS_AUDIT_REPORT.md",
        DOCS_DIR / "REPRODUCIBILITY.md",
        DOCS_DIR / "testing" / "VERIFICATION_REPORT.md",
        DOCS_DIR / "KNOWN_LIMITATIONS.md",
        DOCS_DIR / "reports" / "MODEL_CARD.md",
    ]

    for doc in reports:
        text = doc.read_text(encoding="utf-8")
        assert "-0.1842" in text and ("+0.0284" in text or "0.0284" in text), (
            f"{doc} missing 95% CI [-0.1842, +0.0284]"
        )
        assert "-0.1843" in text and ("+0.0310" in text or "0.0310" in text), (
            f"{doc} missing 95% CI [-0.1843, +0.0310]"
        )


def test_mcnemar_qualified_as_supplementary() -> None:
    """Verify McNemar test is explicitly designated as supplementary in key reports."""
    key_reports = [
        DOCS_DIR / "reports" / "M2_BIAS_AUDIT_REPORT.md",
        DOCS_DIR / "REPRODUCIBILITY.md",
        DOCS_DIR / "testing" / "VERIFICATION_REPORT.md",
    ]

    for doc in key_reports:
        text = doc.read_text(encoding="utf-8")
        if "0.2632" in text:
            # McNemar p-value is mentioned; ensure 'supplementary' or 'Supplementary' appears nearby
            m = re.search(
                r"(?i)supplementary[^\n.]*mcnemar|mcnemar[^\n.]*supplementary",
                text,
            )
            assert m is not None, (
                f"{doc} mentions McNemar p-value without supplementary qualification"
            )


def test_scientific_uncertainty_acknowledged() -> None:
    """Verify that documentation acknowledges uncertainty regarding incremental contribution."""
    for doc in CORE_DOCS:
        text = doc.read_text(encoding="utf-8").lower()
        has_uncertainty = any(
            phrase in text
            for phrase in [
                "true incremental contribution remains uncertain",
                "remains uncertain",
                "uncertainty",
                "confidence intervals include zero and positive effects",
                "confidence intervals include both zero and positive",
            ]
        )
        assert has_uncertainty, (
            f"{doc} does not acknowledge scientific uncertainty regarding voice contribution"
        )
