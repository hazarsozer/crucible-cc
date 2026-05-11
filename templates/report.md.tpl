# Crucible Review — {{review_scope_description}}

_Review ID: {{review_id}} · Generated: {{completed_at}} · Project: {{project_type}}_

## Final Verdict

**Score:** {{final_score}}/10
**Verdict:** {{final_verdict}}

{{verdict_reasoning}}

## Executive Summary

{{executive_summary}}

## What's Good

{{#each what_is_good}}
- {{this}}
{{/each}}

## What's Concerning

{{#each what_is_concerning}}
- {{this}}
{{/each}}

## Key Notes from the Committee

{{#each key_quotes}}
### {{persona}}
> {{quote}}

{{/each}}

## Stage 0 — Profiler

### Project profile
- **Type:** {{casting_roster.project_profile.type}}
- **Languages:** {{casting_roster.project_profile.languages}}
- **Frameworks:** {{casting_roster.project_profile.frameworks}}
- **Datastores:** {{casting_roster.project_profile.datastores}}

### Review scope
- **Kind:** {{casting_roster.review_scope.kind}}
- **Description:** {{casting_roster.review_scope.description}}
- **Files:** {{casting_roster.review_scope.files}}

### Casting reasoning
{{casting_roster.casting_reasoning}}

## Stage 1 — Peer Review

{{#each stage_reports.stage_1}}
### {{persona}} ({{model_used}})

**Verdict:** {{verdict}} · **Score:** {{score}}/10

> {{summary_quote}}

#### Findings

{{#each findings}}
- **[{{severity}}]** {{title}} — `{{location}}`
  - {{explanation}}
  - **Suggestion:** {{suggestion}}

{{/each}}

#### Stage handoff notes
{{stage_handoff_notes}}

{{/each}}

## Stage 2 — Cross-functional

{{#each stage_reports.stage_2}}
### {{persona}} ({{model_used}})

**Verdict:** {{verdict}} · **Score:** {{score}}/10

> {{summary_quote}}

#### Findings

{{#each findings}}
- **[{{severity}}]** {{title}} — `{{location}}`
  - {{explanation}}
  - **Suggestion:** {{suggestion}}

{{/each}}

#### Stage handoff notes
{{stage_handoff_notes}}

{{/each}}

## Stage 3 — Leadership

{{#each stage_reports.stage_3}}
### {{persona}} ({{model_used}})

**Verdict:** {{verdict}} · **Score:** {{score}}/10

> {{summary_quote}}

#### Findings

{{#each findings}}
- **[{{severity}}]** {{title}} — `{{location}}`
  - {{explanation}}
  - **Suggestion:** {{suggestion}}

{{/each}}

#### Stage handoff notes
{{stage_handoff_notes}}

{{/each}}

## Aims Snapshot

{{aims_snapshot}}

## Run Metadata

- **Plugin version:** {{metadata.plugin_version}}
- **Wall-clock:** {{metadata.wall_clock_seconds}}s
- **Models used:** {{metadata.models_used}}

_API cost is not displayed here. Claude Code does not expose token-level pricing to plugin skill scripts, so any number Crucible printed would be a guess. Run `/status` in your Claude Code session to see real API cost for this run._
