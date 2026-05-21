#!/usr/bin/env python3
"""
render_report.py — deterministic Jinja2 renderer for Crucible final reports.

Reads a final-report.json (and the sibling stage_1/, stage_2/, stage_3/
directories when present) and writes a markdown report by substituting
fields into templates/report.md.tpl.

Replaces the v0.1.0 LLM-driven Handlebars-style substitution that drifted
across runs. The rendered output is byte-stable for a given input JSON.

Usage:
    python3 scripts/render_report.py \\
        --input  .review/runs/<id>/final-report.json \\
        --output .review/reports/<id>.md

The script self-locates the bundled Jinja2 in scripts/_vendor/ so it works
without `pip install` or `uv add` from the user's project directory.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts" / "_vendor"))

from jinja2 import Environment, StrictUndefined  # noqa: E402

DEFAULT_TEMPLATE = PLUGIN_ROOT / "templates" / "report.md.tpl"

VERDICT_LABEL = {
    "approved": "APPROVED",
    "conditional_approval": "CONDITIONAL APPROVAL",
    "blocked": "BLOCKED",
}

EMOJI_BY_PREFIX = [
    ("lead-senior-architect", "🏗️"),
    ("lead-project-manager", "📋"),
    ("team-security", "🛡️"),
    ("team-frontend", "🎨"),
    ("team-backend", "⚙️"),
    ("team-database", "🗄️"),
    ("team-network", "🌐"),
    ("team-devops-infra", "🚀"),
    ("team-performance", "⚡"),
    ("team-accessibility", "♿"),
    ("team-observability", "📊"),
    ("team-privacy-compliance", "🔒"),
    ("team-data-ml", "🤖"),
    ("peer-", "👨‍💻"),
    ("team-", "🏢"),
]

STAGE_HEADINGS = {
    1: "Stage 1 — Peer Code Review",
    2: "Stage 2 — Cross-functional Review",
    3: "Stage 3 — Leadership",
}


def emoji_for(persona: str) -> str:
    for prefix, emoji in EMOJI_BY_PREFIX:
        if persona.startswith(prefix):
            return emoji
    return ""


def title_from(report: dict) -> str:
    """Prefer the review_id slug; fall back to scope description."""
    m = re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}-(.+)$", report["review_id"])
    if m:
        return m.group(1)
    scope = report.get("casting_roster", {}).get("review_scope", {})
    return scope.get("description") or report["review_id"]


def project_label(casting_roster: dict) -> str:
    profile = casting_roster.get("project_profile", {})
    type_ = profile.get("type", "")
    langs = ", ".join(profile.get("languages", []))
    frameworks = ", ".join(profile.get("frameworks", []))
    if langs and frameworks:
        return f"{type_} ({langs} / {frameworks})"
    if langs:
        return f"{type_} ({langs})"
    return type_


def blockquote(text: str) -> str:
    """Prefix every line with '> '; empty lines become '>'."""
    return "\n".join(
        ("> " + raw) if raw.strip() else ">"
        for raw in text.splitlines()
    )


def line_range_for(evidence: dict) -> str:
    line_start = evidence["line_start"]
    line_end = evidence.get("line_end")
    if line_end and line_end != line_start:
        return f"{line_start}-{line_end}"
    return str(line_start)


def load_report(report_path: Path, run_dir: Path | None = None) -> dict:
    """
    Load final-report.json. If sibling stage_<N>/ dirs exist, use them to
    enrich any stage_reports entries that lack 'findings' or 'summary_quote'
    (covers v0.1.0 Aggregator-summary drift).
    """
    with open(report_path) as f:
        report = json.load(f)

    if run_dir is None:
        run_dir = report_path.parent

    for stage_n in (1, 2, 3):
        stage_dir = run_dir / f"stage_{stage_n}"
        if not stage_dir.is_dir():
            continue
        per_stage: dict[str, dict] = {}
        for p in sorted(stage_dir.glob("*.json")):
            with open(p) as f:
                pf = json.load(f)
            per_stage[pf["persona"]] = pf
        enriched_stage = []
        for entry in report["stage_reports"][f"stage_{stage_n}"]:
            persona = entry.get("persona", "")
            if "findings" in entry and "summary_quote" in entry:
                enriched_stage.append(entry)
            elif persona in per_stage:
                enriched_stage.append(per_stage[persona])
            else:
                enriched_stage.append(entry)
        report["stage_reports"][f"stage_{stage_n}"] = enriched_stage

    return report


def build_bullet_block(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"- {x}" for x in items)


def build_key_notes_block(key_quotes: list[dict]) -> str:
    if not key_quotes:
        return ""
    lines = []
    for q in key_quotes:
        emoji = emoji_for(q["persona"])
        prefix = f"{emoji} " if emoji else ""
        lines.append(f"{prefix}**{q['persona']}:** \"{q['quote']}\"")
    return "\n\n".join(lines)


def build_persona_block(persona: dict) -> str:
    parts: list[str] = []
    parts.append(f"**{persona['persona']}** ({persona['score']}/10 · {persona['verdict']})\n\n")
    parts.append(f"> \"{persona['summary_quote']}\"\n")
    findings = persona.get("findings") or []
    if findings:
        parts.append("\n")
        for f in findings:
            evidence = f["evidence"]
            line_range = line_range_for(evidence)
            parts.append(
                f"- **[{f['severity']}]** `{evidence['path']}:{line_range}` — {f['title']}\n"
            )
    parts.append("\n---\n\n")
    return "".join(parts)


def build_stage_block(stage_n: int, personas: list[dict]) -> str:
    parts: list[str] = []
    parts.append(f"### {STAGE_HEADINGS[stage_n]}\n\n")
    parts.append("| Persona | Score | Verdict |\n")
    parts.append("|---|---|---|\n")
    for p in personas:
        parts.append(f"| {p['persona']} | {p['score']}/10 | {p['verdict']} |\n")
    parts.append("\n")
    for p in personas:
        parts.append(build_persona_block(p))
    return "".join(parts)


def build_stage_reports_block(report: dict) -> str:
    return "".join(
        build_stage_block(n, report["stage_reports"][f"stage_{n}"])
        for n in (1, 2, 3)
    )


def build_context(report: dict) -> dict:
    return {
        "title": title_from(report),
        "review_id": report["review_id"],
        "completed_at": report["completed_at"],
        "project_label": project_label(report.get("casting_roster", {})),
        "verdict_label": VERDICT_LABEL[report["final_verdict"]],
        "final_score_label": f"{float(report['final_score']):.1f}",
        "verdict_reasoning": report["verdict_reasoning"],
        "executive_summary": report["executive_summary"],
        "what_is_good_block": build_bullet_block(report["what_is_good"]),
        "what_is_concerning_block": build_bullet_block(report["what_is_concerning"]),
        "key_notes_block": build_key_notes_block(report["key_quotes"]),
        "stage_reports_block": build_stage_reports_block(report),
        "aims_blockquote": blockquote(report["aims_snapshot"]),
        "committee_stage_1": ", ".join(
            p["persona"] for p in report["stage_reports"]["stage_1"]
        ),
        "committee_stage_2": ", ".join(
            p["persona"] for p in report["stage_reports"]["stage_2"]
        ),
        "committee_stage_3": ", ".join(
            p["persona"] for p in report["stage_reports"]["stage_3"]
        ),
        "models_used_label": ", ".join(report["metadata"]["models_used"]),
        "plugin_version": report["metadata"]["plugin_version"],
    }


def render(report: dict, template_path: Path = DEFAULT_TEMPLATE) -> str:
    env = Environment(
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template_src = template_path.read_text()
    template = env.from_string(template_src)
    return template.render(**build_context(report))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--input", required=True, type=Path,
                   help="Path to final-report.json")
    p.add_argument("--output", required=True, type=Path,
                   help="Path to write rendered markdown")
    p.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE,
                   help="Override template path (default: bundled report.md.tpl)")
    p.add_argument("--run-dir", type=Path, default=None,
                   help="Optional run directory for stage_<N>/ enrichment "
                        "(defaults to parent of --input)")
    args = p.parse_args(argv)

    report = load_report(args.input, args.run_dir)
    rendered = render(report, args.template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
