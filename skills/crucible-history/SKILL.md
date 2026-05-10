---
name: crucible-history
description: List past Crucible reviews stored in .review/reports/ and optionally show the full markdown of one. Use to see how the project's review verdicts have evolved over time.
---

# /crucible-history — Review History

List past Crucible reviews and offer to show one in full. Reviews are stored at `.review/reports/<review_id>.md` in the project root.

## Steps

1. **List reports.** Find every file under `.review/reports/` matching the pattern `*.md`. If none exist, print:
   ```
   No past reviews found. Run /crucible to create one.
   ```
   and exit.

2. **Parse metadata from each report.** For each file, extract:
   - `review_id` — from the filename (strip `.md`).
   - `final_score` — from the line beginning with `**Score:**` (or fall back to `Score:` if formatting differs).
   - `final_verdict` — from the line beginning with `**Verdict:**`.
   - `scope_description` — from the H1 line `# Crucible Review — <description>`.
   - `completed_at` — from the metadata line `_Review ID: ... · Generated: <timestamp>_`.

   If parsing fails on any field, fall back to `?` for that field.

3. **Sort reports** newest-first by `completed_at` if available, else by filename (which encodes the timestamp prefix).

4. **Print a table.** Use fixed-width columns. Truncate long descriptions to 40 chars with `…`.
   ```
   #   Review ID                          Score  Verdict                Scope
   ─────────────────────────────────────────────────────────────────────────────────
   1   2026-05-10-1430-auth-refactor      7.1    conditional_approval   auth module rewrite
   2   2026-05-09-1620-api-rewrite        8.4    approved               /api/v2 endpoints
   ...
   ```

5. **Prompt for selection.**
   ```
   Show full report for which # (or `n` to exit)?
   ```
   - If the user enters a number that maps to a row, print the full contents of that report file.
   - If the user enters `n`, `no`, `exit`, `quit`, or empty, exit silently.
   - If the input is invalid, print `Not a valid selection.` and exit.

6. **For partial reports.** Files matching `*-PARTIAL.md` (incomplete runs) appear in the listing with a `⚠️` prefix in the `Verdict` column to make it clear they don't represent a complete pipeline run.

## Edge cases

- **No `.review/` directory.** Treat as `no past reviews`.
- **A report file exists but has no parseable metadata.** Show it with `?` placeholders. Don't crash.
- **Many reports (≥ 50).** Limit the table to the most recent 25 entries. Print a footer: `... and <N> older reviews. Browse .review/reports/ directly to see all.`
- **The user pipes input or runs in a non-interactive shell.** If stdin is not a TTY, skip the selection prompt and only print the table.

## Notes

This skill is read-only. It does not modify any files, does not invoke any subagents, and does not consume model budget. It's purely a navigator over the user's review history.
