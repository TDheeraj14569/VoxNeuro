"""Multi-task HTML and JSON reporting builder for VoxNeuro Milestone 3.

Generates comprehensive, self-contained visual HTML dashboards and structured
export summaries for multi-task speech sessions under schema voxneuro.voice.v4.
"""

from __future__ import annotations

import html
from typing import Any

from voxneuro.features.tasks.pipeline import MultiTaskSessionResult
from voxneuro.reporting.report import DISCLAIMER


def render_multitask_report_html(session_data: MultiTaskSessionResult | dict[str, Any]) -> str:
    """Render a standalone, self-contained HTML audit dashboard for a multi-task session."""
    data = (
        session_data.to_dict() if isinstance(session_data, MultiTaskSessionResult) else session_data
    )

    session_id = html.escape(str(data.get("session_id", "N/A")))
    schema_ver = html.escape(str(data.get("schema_version", "voxneuro.voice.v4")))
    schema_fp = html.escape(str(data.get("schema_fingerprint", "N/A")))
    created_utc = html.escape(str(data.get("created_utc", "N/A")))
    overall_status = str(data.get("overall_processing_status", "unknown")).upper()

    tasks: dict[str, dict[str, Any]] = data.get("tasks", {})

    status_badge_class = {
        "COMPLETE": "badge-success",
        "PARTIAL": "badge-warning",
        "QUALITY_FAILED": "badge-danger",
        "INSUFFICIENT_SIGNAL": "badge-warning",
        "NOT_ESTIMABLE": "badge-neutral",
        "PROCESSING_FAILED": "badge-danger",
    }.get(overall_status, "badge-neutral")

    task_cards_html = []

    for t_id, t_info in sorted(tasks.items()):
        t_type = html.escape(str(t_info.get("task_type", t_id)))
        t_status = str(t_info.get("task_status", "unknown")).upper()
        t_ver = html.escape(str(t_info.get("task_schema_version", "N/A")))
        t_fp = html.escape(str(t_info.get("task_schema_fingerprint", "N/A")))[:16]

        badge_cls = {
            "COMPLETE": "badge-success",
            "QUALITY_FAILED": "badge-danger",
            "INSUFFICIENT_SIGNAL": "badge-warning",
            "NOT_ESTIMABLE": "badge-neutral",
            "PROCESSING_FAILED": "badge-danger",
        }.get(t_status, "badge-neutral")

        feats = t_info.get("features", {})
        feat_rows = []
        for f_name, f_val in sorted(feats.items()):
            esc_name = html.escape(f_name)
            if f_val is None:
                val_display = "<span class='text-muted'>null (not estimable)</span>"
            elif isinstance(f_val, float):
                val_display = f"<strong>{f_val:.4f}</strong>"
            else:
                val_display = f"<strong>{html.escape(str(f_val))}</strong>"
            feat_rows.append(f"<tr><td><code>{esc_name}</code></td><td>{val_display}</td></tr>")

        no_feat = "<tr><td colspan='2' class='text-muted'>No features extracted</td></tr>"
        rows_html = "".join(feat_rows) if feat_rows else no_feat
        card_html = f"""
        <div class="card mb-4">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="mb-0">Task: <code>{html.escape(t_id)}</code> ({t_type})</h5>
            <span class="badge {badge_cls}">{t_status}</span>
          </div>
          <div class="card-body">
            <div class="small text-muted mb-3">
              Schema: <code>{t_ver}</code> &bull; Fingerprint: <code>{t_fp}...</code>
            </div>
            <div class="table-responsive">
              <table class="table table-sm table-striped">
                <thead>
                  <tr><th>Feature Identifier</th><th>Extracted Value</th></tr>
                </thead>
                <tbody>
                  {rows_html}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        """
        task_cards_html.append(card_html)

    # Optional VSA Coordinate Chart Data
    vsa_task = tasks.get("vowel_space_group", {})
    vsa_features = vsa_task.get("features", {})
    vsa_val = vsa_features.get("vowel_space_area_hz2")
    f1_a = vsa_features.get("f1_a_median_hz")
    f2_a = vsa_features.get("f2_a_median_hz")
    f1_i = vsa_features.get("f1_i_median_hz")
    f2_i = vsa_features.get("f2_i_median_hz")
    f1_u = vsa_features.get("f1_u_median_hz")
    f2_u = vsa_features.get("f2_u_median_hz")

    vsa_section_html = ""
    if vsa_val is not None:
        vsa_section_html = f"""
        <div class="card mb-4 border-info">
          <div class="card-header bg-info text-white">
            <h5 class="mb-0">Vowel Space Triangle Summary</h5>
          </div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-6">
                <h6>Calculated Vowel Space Area:</h6>
                <h3 class="text-primary">{vsa_val:.2f} <small class="text-muted">Hz²</small></h3>
                <p class="text-muted small">
                  Calculated using the shoelace triangle area formula over median (F1, F2)
                  coordinates of corner vowels /a/, /i/, and /u/. Descriptive acoustic
                  measure; not a standalone clinical biomarker.
                </p>
              </div>
              <div class="col-md-6">
                <table class="table table-sm">
                  <thead>
                    <tr><th>Vowel</th><th>Median F1 (Hz)</th><th>Median F2 (Hz)</th></tr>
                  </thead>
                  <tbody>
                    <tr><td><strong>/a/</strong> (low back)</td><td>{f1_a}</td><td>{f2_a}</td></tr>
                    <tr><td><strong>/i/</strong> (high front)</td>
                        <td>{f1_i}</td><td>{f2_i}</td></tr>
                    <tr><td><strong>/u/</strong> (high back)</td><td>{f1_u}</td><td>{f2_u}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        """

    esc_disclaimer = html.escape(DISCLAIMER)
    no_tasks_html = '<p class="text-muted">No task evaluations recorded in this session.</p>'
    tasks_body_html = "".join(task_cards_html) if task_cards_html else no_tasks_html

    html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>VoxNeuro Multi-Task Voice Session Report</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      line-height: 1.5;
      color: #212529;
      background-color: #f8f9fa;
      margin: 0;
      padding: 2rem;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
      background: #ffffff;
      padding: 2.5rem;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }}
    h1, h2, h3, h5, h6 {{ color: #1a1a1a; }}
    .badge {{
      display: inline-block;
      padding: 0.35em 0.65em;
      font-size: 0.75em;
      font-weight: 700;
      line-height: 1;
      text-align: center;
      white-space: nowrap;
      vertical-align: baseline;
      border-radius: 0.25rem;
    }}
    .badge-success {{ color: #fff; background-color: #28a745; }}
    .badge-warning {{ color: #212529; background-color: #ffc107; }}
    .badge-danger {{ color: #fff; background-color: #dc3545; }}
    .badge-neutral {{ color: #fff; background-color: #6c757d; }}
    .card {{
      border: 1px solid #e9ecef;
      border-radius: 6px;
      margin-bottom: 1.5rem;
      background: #fff;
    }}
    .card-header {{
      padding: 0.75rem 1.25rem;
      background-color: #f8f9fa;
      border-bottom: 1px solid #e9ecef;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .card-body {{ padding: 1.25rem; }}
    table {{ width: 100%; margin-bottom: 1rem; color: #212529; border-collapse: collapse; }}
    th, td {{
      padding: 0.5rem;
      vertical-align: top;
      border-top: 1px solid #dee2e6;
      text-align: left;
    }}
    thead th {{
      vertical-align: bottom;
      border-bottom: 2px solid #dee2e6;
      font-size: 0.85rem;
      color: #495057;
    }}
    code {{ color: #d63384; font-size: 0.875em; }}
    .text-muted {{ color: #6c757d; }}
    .disclaimer-box {{
      padding: 1rem;
      background-color: #fff3cd;
      border: 1px solid #ffeeba;
      color: #856404;
      border-radius: 4px;
      margin-top: 2rem;
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div style="border-bottom: 2px solid #e9ecef; padding-bottom: 1rem; margin-bottom: 1.5rem;">
      <h2>VoxNeuro Multi-Task Voice Session Report</h2>
      <div style="font-size: 0.9rem; color: #6c757d;">
        Session ID: <code>{session_id}</code> &bull; Schema: <code>{schema_ver}</code>
        &bull; FP: <code>{schema_fp[:16]}...</code> &bull; Created: {created_utc}
      </div>
      <div style="margin-top: 0.5rem;">
        Overall Session Status: <span class="badge {status_badge_class}">{overall_status}</span>
      </div>
    </div>

    {vsa_section_html}

    <h3>Task Evaluations</h3>
    {tasks_body_html}

    <div class="disclaimer-box">
      <strong>RESEARCH PROTOTYPE NOTICE &bull; NOT FOR CLINICAL DIAGNOSIS</strong><br>
      {esc_disclaimer}
    </div>
  </div>
</body>
</html>
"""
    return html_document
