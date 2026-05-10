---
name: crucible-aims
description: Refresh the project's .review/aims.md interactively without running a full Crucible review. Use when the project's stated goals have shifted between reviews and you want to update aims before the next /crucible run.
---

# /crucible-aims — Refresh Project Aims

Force the Profiler agent to re-interview the user about project aims and rewrite `.review/aims.md`. Useful when the project's goals have shifted between reviews — for example, after a pivot, a new milestone, or a change in stakeholder priorities.

This skill does NOT run a full review. It only refreshes the aims file. To run a review against the refreshed aims, invoke `/crucible` afterward.

## Steps

1. **Check for existing aims.** Look at `.review/aims.md`.
   - If it exists: read its contents and show them to the user, then ask:
     ```
     Current aims at .review/aims.md:

     <contents>

     Refresh these aims, edit specific sections, or cancel?
     (refresh / edit / cancel)
     ```
     - `refresh` → run the full Profiler interview (step 2 below).
     - `edit` → ask which sections (Goal / Success criteria / Non-goals / Constraints / etc.) to update; only re-interview those, then write back the updated file.
     - `cancel` → exit without changes.
   - If `.review/aims.md` does NOT exist: announce `No aims file found — running first-time interview.` and proceed directly to step 2.

2. **Dispatch the Profiler in interview-only mode** via the Task tool:

   ```
   Task(
     subagent_type="profiler",
     description="Refresh project aims (interview only)",
     prompt="""
You are running as the Profiler agent in INTERVIEW-ONLY mode. Your full system prompt is at agents/profiler.md.

# Working directory
<absolute path of the user's project>

# Mode: interview-only
Do NOT cast a committee. Do NOT output a CastingRoster. Your single job for this invocation:

1. Read the project files briefly to confirm the tech stack (file tree, README, language manifests).
2. Run the aims interview (your standard 3–5 adaptive questions per spec §6.1, plus any clarifications).
3. Write a fresh .review/aims.md from the templates/aims.md.tpl skeleton, populating every {{...}} placeholder.
4. If the project has .git/ but .review/ is not yet ignored, append `.review/` to .gitignore (idempotent).
5. Confirm with the user that the file looks right.

Return: a single line of plaintext describing what was updated. No JSON, no roster.
"""
   )
   ```

3. **Print confirmation.** Once the Profiler returns, print:
   ```
   ✓ Aims refreshed at .review/aims.md
   ```

   If the Profiler reported a partial update or any error, surface it verbatim under a `Profiler note:` heading.

4. **Suggest next step.** Print:
   ```
   Run /crucible to review against the updated aims.
   ```

## Edge cases

- **User cancels during the Profiler interview.** The Profiler may halt mid-interview. Catch the partial response and print: `Aims refresh cancelled. Existing aims at .review/aims.md are unchanged.`
- **Profiler returns malformed output.** This skill expects plaintext, not JSON. If the Profiler returns a JSON object anyway, treat its `casting_reasoning` or any human-readable field as the confirmation message.
- **Non-git projects.** Skip the .gitignore step silently — the Profiler's prompt already handles this.

## Notes

This skill is light. It does not invoke peer/team/leadership personas, does not write a report, and does not consume the budget of a full review. Use it freely whenever the project's goals shift.
