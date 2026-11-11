#!/usr/bin/env python3
"""Generate the official VoxNeuro 9-page Biodesign Need Statement presentation PDF.

Usage:
    uv run --with reportlab python docs/biodesign/generate_need_statement_pdf.py [output_path]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

PAGE_WIDTH = 720.0
PAGE_HEIGHT = 540.0

COLOR_TEXT = HexColor("#000000")
COLOR_MUTED = HexColor("#444444")
COLOR_ACCENT = HexColor("#B95E46")


class SlideBuilder:
    def __init__(self, c: canvas.Canvas):
        self.c = c

    def draw_page_header(self, title: str):
        self.c.setFont("Helvetica-Bold", 26)
        self.c.setFillColor(COLOR_TEXT)
        self.c.drawString(24, 496, title)

    def draw_subheading(
        self, text: str, y: float, size: float = 21.0, max_width: float = 672.0
    ) -> float:
        """Draw subheading with automatic wrapping if width exceeds max_width."""
        self.c.setFont("Helvetica-Bold", size)
        self.c.setFillColor(COLOR_TEXT)
        leading = size * 1.25

        words = text.split()
        lines = []
        curr = []
        for w in words:
            test_line = " ".join(curr + [w])
            if self.c.stringWidth(test_line, "Helvetica-Bold", size) > max_width and curr:
                lines.append(" ".join(curr))
                curr = [w]
            else:
                curr.append(w)
        if curr:
            lines.append(" ".join(curr))

        cursor_y = y
        for idx, line in enumerate(lines):
            line_y = cursor_y - (idx * leading)
            self.c.drawString(24, line_y, line)

        return cursor_y - (len(lines) * leading)

    def draw_bullet(
        self,
        label: str,
        body: str,
        y: float,
        font_size: float = 16.5,
        leading: float = 21.0,
        available_width: float = 645.0,
    ) -> float:
        """Draw a bullet point with an optional bold label and wrapping body text.

        Returns the y coordinate after drawing all lines.
        """
        bullet_char = "\u2022"
        bullet_indent = 24.0
        text_indent = 42.0

        # Draw bullet
        self.c.setFont("Helvetica", font_size)
        self.c.setFillColor(COLOR_TEXT)
        self.c.drawString(bullet_indent, y, bullet_char)

        # Full prefix if label
        full_prefix = f"{label} " if label else ""
        label_width = self.c.stringWidth(full_prefix, "Helvetica-Bold", font_size) if label else 0.0

        # Wrap text into lines
        words = body.split()
        lines: list[tuple[bool, str]] = []
        current_line = []
        current_w = label_width

        for word in words:
            word_w = self.c.stringWidth(word + " ", "Helvetica", font_size)
            if current_w + word_w > available_width and current_line:
                lines.append((len(lines) == 0, " ".join(current_line)))
                current_line = [word]
                current_w = word_w
            else:
                current_line.append(word)
                current_w += word_w
        if current_line:
            lines.append((len(lines) == 0, " ".join(current_line)))

        # Render lines
        cursor_y = y
        for idx, (is_first, line_text) in enumerate(lines):
            line_y = cursor_y - (idx * leading)
            if is_first and label:
                self.c.setFont("Helvetica-Bold", font_size)
                self.c.drawString(text_indent, line_y, full_prefix)
                self.c.setFont("Helvetica", font_size)
                self.c.drawString(text_indent + label_width, line_y, line_text)
            else:
                self.c.setFont("Helvetica", font_size)
                self.c.drawString(text_indent, line_y, line_text)

        return cursor_y - (len(lines) * leading)

    def draw_quote_box(
        self,
        quote_text: str,
        y: float,
        font_size: float = 19.0,
        leading: float = 24.5,
        available_width: float = 660.0,
    ) -> float:
        """Draw an emphasized need statement quote box."""
        words = quote_text.split()
        lines = []
        curr = []
        self.c.setFont("Helvetica-Bold", font_size)
        for w in words:
            test_line = " ".join(curr + [w])
            if (
                self.c.stringWidth(test_line, "Helvetica-Bold", font_size) > available_width
                and curr
            ):
                lines.append(" ".join(curr))
                curr = [w]
            else:
                curr.append(w)
        if curr:
            lines.append(" ".join(curr))

        self.c.setFillColor(COLOR_TEXT)
        cursor_y = y
        for idx, line in enumerate(lines):
            line_y = cursor_y - (idx * leading)
            prefix = "\u201c" if idx == 0 else " "
            suffix = "\u201d" if idx == len(lines) - 1 else ""
            self.c.drawString(24, line_y, f"{prefix}{line}{suffix}")

        return cursor_y - (len(lines) * leading)


def build_pdf(output_path: Path) -> Path:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    c.setTitle("VoxNeuro: Need Statement Development in Biodesign")
    c.setAuthor("VoxNeuro Academic Project Team")
    c.setSubject("Biodesign Concept & Practice - Early Neurological Screening")

    b = SlideBuilder(c)

    # =========================================================================
    # PAGE 1: TITLE SLIDE
    # =========================================================================
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(COLOR_TEXT)
    c.drawCentredString(PAGE_WIDTH / 2.0, 340, "Need Statement Development")
    c.drawCentredString(PAGE_WIDTH / 2.0, 290, "in Biodesign")

    c.setFont("Helvetica-Bold", 25)
    c.drawCentredString(PAGE_WIDTH / 2.0, 205, "Voice-Based Neurology Disease Detection")

    c.setFont("Helvetica", 17)
    c.drawCentredString(PAGE_WIDTH / 2.0, 150, "Group Project: Early Neurological Screening")

    c.setFont("Helvetica-Oblique", 12)
    c.setFillColor(COLOR_MUTED)
    c.drawCentredString(
        PAGE_WIDTH / 2.0, 95, "Academic Baseline & Integrity Specification \u2014 Milestone 0"
    )
    c.showPage()

    # =========================================================================
    # PAGE 2: STRATEGIC FOCUS AREA
    # =========================================================================
    b.draw_page_header("Strategic Focus Area")

    sub_y = b.draw_subheading("Identify", 455, size=21.0)
    y = b.draw_bullet(
        "Passion:",
        "our own interest in speech signal processing and machine learning applied to health.",
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Primary research status:",
        (
            "prospective clinician, health worker and patient interviews "
            "pending IEC/IRB ethical clearance; preliminary exploration "
            "derived from academic design models."
        ),
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Secondary research:",
        (
            "peer-reviewed journals, WHO and ICMR epidemiological "
            "reports, conferences, and existing speech-biomarker "
            "literature."
        ),
        y - 3,
        font_size=15.5,
        leading=20.0,
    )

    sub_y = b.draw_subheading("Selection", y - 10, size=21.0)
    y = b.draw_bullet(
        "Interest:",
        "speech analysis and machine learning, with strong team motivation.",
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Funding:",
        "low cost, because a software-only app needs no custom hardware to manufacture.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Technology:",
        "smartphone microphones and machine learning are mature enough to build on.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Competition:",
        "few voice tools exist, with clear gaps in low-resource settings.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    b.draw_bullet(
        "Government / national program:",
        "ICMR priorities include stroke, epilepsy, dementia and conditions associated with ageing.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    c.showPage()

    # =========================================================================
    # PAGE 3: UNMET NEED IDENTIFICATION
    # =========================================================================
    b.draw_page_header("Unmet Need Identification")

    sub_y = b.draw_subheading(
        "Gaps Identified via Literature & Simulated Clinical Scenarios", 455, size=20.0
    )
    y = b.draw_bullet(
        "Simulated observation:",
        (
            "in primary care clinics and rural health camps, adults with "
            "early memory, movement or speech changes are rarely assessed "
            "objectively; signs are noted by ear and family description, "
            "and referral to a neurologist is late or missed."
        ),
        sub_y - 8,
        font_size=15.0,
        leading=19.5,
    )
    y = b.draw_bullet(
        "Count of problems:",
        (
            "three recurring gaps: no objective screening tool, scarce "
            "specialists and equipment, and no structured follow-up of "
            "early signs."
        ),
        y - 2,
        font_size=15.0,
        leading=19.5,
    )
    y = b.draw_bullet(
        "Outcome affected:",
        "delay in diagnosis and timely referral.",
        y - 2,
        font_size=15.0,
        leading=19.5,
    )
    y = b.draw_bullet(
        "Volume and frequency:",
        (
            "preliminary design assumption; to be confirmed through "
            "primary research with formal clinic counts."
        ),
        y - 2,
        font_size=15.0,
        leading=19.5,
    )

    sub_y = b.draw_subheading("Hypothesized & Simulated Care Contexts", y - 10, size=20.0)
    y = b.draw_bullet(
        "Primary care clinic (Simulated):",
        (
            "older adults report memory or speech changes, but there is "
            "no structured screening because of time and training limits."
        ),
        sub_y - 8,
        font_size=15.0,
        leading=19.5,
    )
    y = b.draw_bullet(
        "Rural health camp (Simulated):",
        (
            "patients report tremor, slurred speech or seizures, but "
            "there is no neurologist or equipment and only family "
            "descriptions to go on."
        ),
        y - 2,
        font_size=15.0,
        leading=19.5,
    )
    b.draw_bullet(
        "Tertiary neurology clinic (Simulated):",
        (
            "specialist assessment involves long waits, costly tests and "
            "long travel, because capacity is concentrated in cities."
        ),
        y - 2,
        font_size=15.0,
        leading=19.5,
    )
    c.showPage()

    # =========================================================================
    # PAGE 4: NEED STATEMENT CREATION
    # =========================================================================
    b.draw_page_header("Need Statement Creation")

    sub_y = b.draw_subheading("Who, Where, Why", 455, size=21.0)
    y = b.draw_bullet(
        "WHO:",
        "adults with subtle early neurological symptoms.",
        sub_y - 8,
        font_size=16.5,
        leading=21.0,
    )
    y = b.draw_bullet(
        "WHERE:",
        "primary care and community settings with limited specialist access.",
        y - 3,
        font_size=16.5,
        leading=21.0,
    )
    y = b.draw_bullet(
        "WHY:",
        "to reduce diagnostic delay and enable timely referral.",
        y - 3,
        font_size=16.5,
        leading=21.0,
    )

    sub_y = b.draw_subheading("Need Statement", y - 8, size=21.0)
    y = b.draw_quote_box(
        (
            "A way to detect early neurological disease in adults with subtle "
            "symptoms in primary care and community settings with limited specialist "
            "access, to reduce diagnostic delay and enable timely referral."
        ),
        sub_y - 8,
        font_size=18.5,
        leading=24.0,
    )

    sub_y = b.draw_subheading("Problem, Population, Outcome", y - 10, size=21.0)
    y = b.draw_bullet(
        "Problem:",
        "early neurological disease is detected late and subjectively.",
        sub_y - 8,
        font_size=16.0,
        leading=21.0,
    )
    y = b.draw_bullet(
        "Population:",
        "adults with early symptoms outside specialist centres.",
        y - 3,
        font_size=16.0,
        leading=21.0,
    )
    y = b.draw_bullet(
        "Outcome:", "shorter time to diagnosis and referral.", y - 3, font_size=16.0, leading=21.0
    )
    b.draw_bullet(
        "Boundary:",
        (
            "The statement is solution-independent: it names no "
            "technology, so voice analysis, questionnaires and sensors "
            "all remain possible."
        ),
        y - 3,
        font_size=16.0,
        leading=21.0,
    )
    c.showPage()

    # =========================================================================
    # PAGE 5: NEED STATEMENT CHECK
    # =========================================================================
    b.draw_page_header("Need Statement Check")
    sub_y = b.draw_subheading("Testing Our Statement Against Common Pitfalls", 455, size=22.5)

    y = b.draw_bullet(
        "Too general:",
        (
            "avoided. It names a defined group and clinical context, "
            "adults with subtle early symptoms in primary care."
        ),
        sub_y - 12,
        font_size=18.0,
        leading=23.5,
    )
    y = b.draw_bullet(
        "Too specific:",
        "avoided. It covers early neurological disease, not only Parkinson's or one tool.",
        y - 10,
        font_size=18.0,
        leading=23.5,
    )
    y = b.draw_bullet(
        "Stuck in current practice:",
        "avoided. It focuses on the desired outcome, not on how detection is done today.",
        y - 10,
        font_size=18.0,
        leading=23.5,
    )
    y = b.draw_bullet(
        "Embedded solution:",
        "avoided. No technology is named; the voice app is a later design choice.",
        y - 10,
        font_size=18.0,
        leading=23.5,
    )
    b.draw_bullet(
        "Built on a negative:",
        "avoided. It is framed positively: detect early and enable timely referral.",
        y - 10,
        font_size=18.0,
        leading=23.5,
    )
    c.showPage()

    # =========================================================================
    # PAGE 6: NEED SCOPING (PART 1)
    # =========================================================================
    b.draw_page_header("Need Scoping (Asking the Right Questions)")

    sub_y = b.draw_subheading(
        "a. Clinical Relevance (Published Literature Evidence)", 455, size=20.0
    )
    y = b.draw_bullet(
        "",
        (
            "Neurological disorders are a leading cause of disability "
            "worldwide, and the burden rises with ageing populations (GBD "
            "2021)."
        ),
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "",
        (
            "Earlier detection enables earlier treatment; the target "
            "outcome (time to referral, cases flagged early) is "
            "measurable."
        ),
        y - 2,
        font_size=15.5,
        leading=20.0,
    )

    sub_y = b.draw_subheading(
        "b. Stakeholder Perspective (Design Assumptions \u2014 Primary Research Pending)",
        y - 8,
        size=18.5,
    )
    y = b.draw_bullet(
        "Patients and families:",
        "earlier answers with less travel, cost and waiting.",
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Primary care doctors and health workers:",
        "a quick, simple, objective screening aid.",
        y - 2,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Neurologists:",
        "better-triaged referrals and objective longitudinal trend data.",
        y - 2,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Health systems and payers:",
        "scalable, low-cost screening.",
        y - 2,
        font_size=15.5,
        leading=20.0,
    )

    sub_y = b.draw_subheading("c. Market Potential", y - 8, size=20.0)
    y = b.draw_bullet(
        "Adjacent:",
        "digital health, tele-neurology and remote patient monitoring.",
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    b.draw_bullet(
        "Focused:",
        "speech and voice biomarker tools, an emerging segment; market size to be validated.",
        y - 2,
        font_size=15.5,
        leading=20.0,
    )
    c.showPage()

    # =========================================================================
    # PAGE 7: NEED SCOPING (PART 2)
    # =========================================================================
    b.draw_page_header("Need Scoping (Asking the Right Questions)")

    sub_y = b.draw_subheading(
        "d. Technical Feasibility (Literature & Engineering Scope)", 455, size=20.0
    )
    y = b.draw_bullet(
        "Approaches:",
        (
            "short speech tasks, acoustic features (pitch, jitter, "
            "shimmer, MFCCs) and machine learning on a smartphone."
        ),
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Challenges:",
        (
            "background noise, microphone variability, accents and "
            "languages, small datasets and explainability."
        ),
        y - 3,
        font_size=15.5,
        leading=20.0,
    )

    sub_y = b.draw_subheading("e. Regulatory & Reimbursement", y - 8, size=20.0)
    y = b.draw_bullet(
        "",
        (
            "May be regulated as software as a medical device (FDA SaMD; "
            "India's Medical Device Rules 2017 / CDSCO)."
        ),
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "",
        "Adoption depends on clinical validation and workflow value such as earlier referral.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )

    sub_y = b.draw_subheading("f. Competitive Landscape", y - 8, size=20.0)
    y = b.draw_bullet(
        "Current options:",
        (
            "bedside exam, specialist assessment, neuroimaging and a few "
            "voice-analytics companies (Sonde Health, Canary Speech, "
            "Aural Analytics)."
        ),
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    b.draw_bullet(
        "Gaps:",
        (
            "exams are costly and centralised; voice tools are "
            "English-centric, limited in validation and not built for "
            "low-resource or multilingual settings."
        ),
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    c.showPage()

    # =========================================================================
    # PAGE 8: CATEGORIZING NEEDS
    # =========================================================================
    b.draw_page_header("Categorizing Needs")

    sub_y = b.draw_subheading("Where Our Need Sits", 455, size=21.0)
    y = b.draw_bullet(
        "Incremental:",
        "met by improving current solutions; lower risk and shorter time to market.",
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Mixed (our need):",
        (
            "some elements use existing speech analysis and machine "
            "learning, but major gaps remain in validation, multilingual "
            "use and low-resource settings."
        ),
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Blue sky:",
        "needs breakthroughs or new paradigms; high risk and long development.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )

    sub_y = b.draw_subheading(
        "Superseding Needs: Treating Symptoms vs. Underlying Problem", y - 10, size=18.5
    )
    y = b.draw_bullet(
        "Downstream (leaves):",
        "treat disability after late diagnosis. Works, but treats the symptom.",
        sub_y - 8,
        font_size=15.5,
        leading=20.0,
    )
    y = b.draw_bullet(
        "Intermediate (branch):",
        (
            "detect early disease and refer promptly. This is our need; "
            "it shortens delay and improves treatment timing."
        ),
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    b.draw_bullet(
        "Upstream (trunk):",
        "prevent the neurological disease. It would supersede detection but is far harder.",
        y - 3,
        font_size=15.5,
        leading=20.0,
    )
    c.showPage()

    # =========================================================================
    # PAGE 9: REFINED NEED AND DESIGN EXPLORATION
    # =========================================================================
    b.draw_page_header("Refined Need and Design Exploration")

    sub_y = b.draw_subheading("Refined Need Statement", 455, size=21.0)
    y = b.draw_quote_box(
        (
            "A low-cost, accessible way to detect early neurological disease in adults with subtle "
            "symptoms in primary care and community settings, giving an "
            "objective result and referral guidance without specialist "
            "equipment."
        ),
        sub_y - 8,
        font_size=17.5,
        leading=23.0,
    )

    sub_y = b.draw_subheading("Possible Solution Pathways", y - 8, size=20.0)
    y = b.draw_bullet(
        "Speech and voice analysis app:",
        "short guided recordings on a smartphone, machine learning analysis and an instant report.",
        sub_y - 8,
        font_size=14.5,
        leading=18.5,
    )
    y = b.draw_bullet(
        "Digital cognitive screening app:",
        "phone or tablet tests of memory, attention and executive processing.",
        y - 2,
        font_size=14.5,
        leading=18.5,
    )
    y = b.draw_bullet(
        "Movement analysis app:",
        "camera-based computer vision for gait, tremor and postural assessment.",
        y - 2,
        font_size=14.5,
        leading=18.5,
    )

    sub_y = b.draw_subheading("Selected Pathway & Prototype Boundary", y - 8, size=20.0)
    y = b.draw_bullet(
        "Voice-Based Detection App:",
        (
            "software-only, non-invasive, low-cost and quick; evaluated "
            "on accuracy, user experience, integration and regulatory "
            "fit."
        ),
        sub_y - 8,
        font_size=14.5,
        leading=18.5,
    )
    b.draw_bullet(
        "Prototype Boundary Notice:",
        (
            "VoxNeuro is an academic prototype evaluating sustained-vowel "
            "(/a/) acoustic stability. It does not perform comprehensive "
            "speech/language assessment, does not diagnose disease, and "
            "live microphone inference is disabled pending multi-device "
            "clinical validation."
        ),
        y - 2,
        font_size=14.5,
        leading=18.5,
    )
    c.showPage()

    c.save()
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the official 9-page VoxNeuro Biodesign Need Statement PDF."
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(Path(__file__).resolve().parent / "Voice_Neuro_Detection_Need_Statement.pdf"),
        help="Target output path for the generated PDF",
    )
    args = parser.parse_args()

    out_file = Path(args.output)
    result = build_pdf(out_file)
    print(f"PASS generated 9-page need-statement PDF: {result} ({result.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
