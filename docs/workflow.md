# Timeline Builder Workflow

The intended workflow is:

```text
Jira CSV → Python draft timeline → AI review patch → reviewed timeline JSON → validation / quality gates → draw.io render
```

## Artifact layout

Each CSV gets its own artifact folder named:

```text
<csv_stem>_timeline-diagram/
```

Manual-AI handoff files go in the nested folder:

```text
<csv_stem>_timeline-diagram/ai-review/
```

For `digit_142_history.csv`, the layout is:

```text
digit_142_history_timeline-diagram/
  digit_142_history_timeline_draft.json
  digit_142_history_timeline_warnings.json
  digit_142_history_timeline_reviewed.json
  digit_142_history_timeline_quality_report.json
  digit_142_history_timeline_reviewed.drawio
  digit_142_history_timeline_reviewed.svg
  ai-review/
    digit_142_history_timeline_review_packet.json
    digit_142_history_timeline_ai_review_prompt.md
    digit_142_history_timeline_ai_patch.json
```

## 1. Prepare

Python reads the Jira CSV, detects columns case-insensitively, handles `source_row` internally, creates a conservative draft timeline, and writes a review packet.

```bash
python3 scripts/timeline_builder.py prepare input.csv
```

Outputs:

- `<csv_stem>_timeline-diagram/*_timeline_draft.json`
- `<csv_stem>_timeline-diagram/*_timeline_warnings.json`
- `<csv_stem>_timeline-diagram/ai-review/*_timeline_review_packet.json`
- `<csv_stem>_timeline-diagram/ai-review/*_timeline_ai_review_prompt.md`

## 2. Manual AI review

Upload or paste the review packet to an AI chat with the saved prompt file or `prompts/review_timeline_packet.md`.

The AI must return patch JSON only. When the review packet has `review_items`, `review_decisions[]` should include one concise decision per review item. The actual applied changes are still the top-level patch arrays: `event_edits`, `new_events`, `event_removals`, `warnings_to_keep`, `human_review_needed`, and `blockers`. Python rejects thin/no-op patches that do not account for the review items.

Save it as:

- `<csv_stem>_timeline-diagram/ai-review/*_timeline_ai_patch.json`

The GUI **Prepare AI Packet + Copy Prompt** button writes the packet/prompt files and copies the prompt/file instructions automatically.

## 3. Apply review

```bash
python3 scripts/timeline_builder.py apply-review \
  input_timeline-diagram/input_timeline_draft.json \
  input_timeline-diagram/ai-review/input_timeline_ai_patch.json
```

Outputs:

- `<csv_stem>_timeline-diagram/*_timeline_reviewed.json`
- `<csv_stem>_timeline-diagram/*_timeline_quality_report.json`

The GUI **Select AI Patch + Check + Render** button applies the review, validates it, runs quality gates, renders draw.io, and exports SVG in one step.

## 4. Render

```bash
python3 scripts/timeline_builder.py render input_timeline-diagram/input_timeline_reviewed.json
```

Output:

- `<csv_stem>_timeline-diagram/*_timeline_reviewed.drawio`

## 5. Optional SVG preview

```bash
python3 scripts/timeline_builder.py export-svg input_timeline-diagram/input_timeline_reviewed.json
```

Output:

- `<csv_stem>_timeline-diagram/*_timeline_reviewed.svg`

## Card rendering note

Visible draw.io/SVG event cards are deliberately compact: wrapped title, ticket, and compact source reference only. Connector wires are rendered behind date/event cards so they do not cross over visible card text. The renderer keeps full details, source rows, source fields, and source timestamp in the reviewed JSON and draw.io cell metadata instead of crowding the visible card body.
