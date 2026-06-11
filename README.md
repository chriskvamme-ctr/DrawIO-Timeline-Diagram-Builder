# DrawIO Timeline Diagram Builder

DrawIO Timeline Diagram Builder turns Jira CSV exports into editable **draw.io / diagrams.net** timeline diagrams.

The workflow is intentionally split into a safe Python pass, a manual AI review pass, and deterministic rendering:

```text
Jira CSV → Python draft timeline → AI review patch → reviewed timeline JSON → validation / quality gates → draw.io render
```

Python prepares the draft and enforces validation. The AI reviews a structured packet and returns patch JSON. The renderer only renders validated timeline JSON.

## Requirements

- Python 3.10+
- Tkinter for the GUI (`python3-tk` on Ubuntu/Debian)
- Optional: draw.io Desktop for one-click opening/export workflows
- Optional: Nautilus/GNOME Files custom-actions helper for right-click launching

Ubuntu/Debian basics:

```bash
sudo apt update
sudo apt install python3 python3-tk
```

Optional draw.io Desktop:

```bash
sudo snap install drawio
```

Flatpak alternative:

```bash
flatpak install flathub com.jgraph.drawio.desktop
```

## Quick start: GUI workflow

Run the Timeline Builder GUI:

```bash
python3 tools/timeline_builder_gui.py
```

In the GUI:

1. Select a Jira CSV export.
2. Confirm the parent folder where the wizard should create the per-CSV artifact folder.
3. Click **Prepare AI Packet + Copy Prompt**. This creates `<csv_stem>_timeline-diagram/`, writes the draft/review artifacts, writes an AI prompt file, and copies the AI prompt + file instructions to your clipboard.
4. Send the review packet from the `ai-review/` subfolder to your AI chat and save the response as the expected `*_timeline_ai_patch.json` file in that same subfolder.
> Delete any artifacts copied from the AI timeline patch file for non-.json syntax as these could cause errors. IE "[three backticks]json" at the top of the file, or "[three backticks]" at the bottom of the file. Or typical AI response text such as "Sure, I'll create that AI patch using the files you provided..."
5. Click **Select AI Patch + Check + Render**. If the patch is already at the expected path, the GUI uses it automatically; otherwise it asks you to select it. This validates the patch, applies it, validates the reviewed timeline, runs quality gates, renders `.drawio`, and exports SVG.
6. Click **Open in draw.io** from the final tab.

The GUI is organized into three focused tabs: **Prepare**, **AI Patch**, and **Done**. The normal path has one primary button per stage after file selection. Extra helpers such as opening the packet, copying paths, opening JSON reports, or opening the SVG preview live in the **Advanced** menu instead of cluttering the main workflow. The window title shows the version from the project `VERSION` file so you can tell whether an old launcher is still opening a stale copy. SVG export is generated directly from timeline JSON in Python, so it does not require draw.io Desktop.

## Output files

Artifacts use the original CSV basename with fixed stage suffixes, inside a dedicated per-CSV folder.

For:

```text
digit_142_history.csv
```

The expected folder layout is:

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

The `ai-review/` folder is the manual-AI handoff folder: give the review packet to the AI, use the prompt file if needed, and save the AI response as the expected patch JSON there. A numbered CSV is not required. Source rows are handled internally. A debug/compatibility numbered CSV can be written with the CLI `--write-numbered-csv` option.


## Diagram card display

Rendered event cards are intentionally compact. The visible card text shows only:

```text
Title, wrapped as needed
Ticket: ISSUE-123
Src: R140 · Comment.2
```

Long comments, account IDs, raw details, full source rows, support text, and source timestamps remain in the reviewed JSON and draw.io cell metadata for traceability, but they are not placed inside the visible card body.

## Manual AI review

The AI review step is mandatory in the intended workflow. The AI should receive the draft timeline and review packet, then return **patch JSON only**.

The prompt lives at:

```text
prompts/review_timeline_packet.md
```

The patch JSON includes:

- `summary`
- `debug_report`
- `review_decisions` — review-item audit trail; include one decision per review item when the packet has review items
- `event_edits`
- `new_events`
- `event_removals`
- `warnings_to_keep`
- `human_review_needed`
- `blockers`

Python rejects patches that remove traceability, reference missing event IDs, use unsupported lanes, omit source rows/source fields for new events, use source rows that were not in the draft/review packet, use unsupported event dates when packet date support is available, return a full replacement timeline when a patch was expected, or fail to account for every review item in the review packet. The preferred way to account for review items is `review_decisions`: one concise decision per `review_items[].review_id`. This lets the AI make only one decision for each review item while Python keeps ownership of the full timeline.

## Version and launcher troubleshooting

The source of truth for the app version is the root `VERSION` file. The Python package exposes the same value as `timeline_builder.__version__`, and the GUI title/header and CLI `--version` output use that value.

If the GUI still looks old, reinstall the launcher from the newly extracted project folder:

```bash
tools/install_gui_launcher.sh
```

Then confirm the launcher target:

```bash
cat "$(which timeline-builder)"
timeline-builder  # window title should match VERSION
```

The GUI also logs the project root it is running from on startup.

## Command-line usage

Use the single CLI entrypoint:

```bash
python3 scripts/timeline_builder.py prepare input.csv
python3 scripts/timeline_builder.py apply-review input_timeline-diagram/input_timeline_draft.json input_timeline-diagram/ai-review/input_timeline_ai_patch.json
python3 scripts/timeline_builder.py render input_timeline-diagram/input_timeline_reviewed.json
python3 scripts/timeline_builder.py export-svg input_timeline-diagram/input_timeline_reviewed.json
```

Prepare with an explicit output parent folder. This creates `/tmp/timeline-output/input_timeline-diagram/`:

```bash
python3 scripts/timeline_builder.py prepare input.csv --output-folder /tmp/timeline-output
```

Apply an AI patch and write the default reviewed JSON and quality report:

```bash
python3 scripts/timeline_builder.py apply-review \
  digit_142_history_timeline-diagram/digit_142_history_timeline_draft.json \
  digit_142_history_timeline-diagram/ai-review/digit_142_history_timeline_ai_patch.json
```

Render is blocked if a quality report says the reviewed timeline failed blocker gates. You can override only when you intentionally accept the blockers:

```bash
python3 scripts/timeline_builder.py render digit_142_history_timeline-diagram/digit_142_history_timeline_reviewed.json --force-render
```

## Quality gates

The quality report is written to:

```text
*_timeline_quality_report.json
```

Important blocker:

```text
Blocked: reviewed timeline contains only incident events. This usually means actions/context were not recovered from comments or non-Incident rows. Review packet must be checked before rendering.
```

That blocker applies when the reviewed timeline has at least five events and all events are in the Incident lane.

Other blockers include invalid patch JSON, invalid reviewed JSON, missing source rows, zero renderable events, and incomplete AI review coverage. Patch validation checks that AI-created events use source-supported rows and dates where packet support is available, and rejects thin/no-op patches that do not account for the review packet's review items.

## Nautilus integration

The main product is the Timeline Builder GUI. Nautilus is optional and should only launch the GUI.

Install the helper extension if needed:

```bash
bash tools/install_nautilus_custom_actions.sh
```

Install the single Timeline launcher action:

```bash
python3 tools/install_timeline_builder_action.py
nautilus -q
```

This adds one action:

```text
Timeline: Open in Timeline Builder
```

The generic Nautilus Actions Manager remains available for arbitrary actions:

```bash
python3 tools/nautilus_actions_gui.py
```

It edits only generic action fields such as label, command, selection type, extensions, MIME types, description, enabled, terminal, and include directories.

## Troubleshooting

If the GUI does not open, confirm Tkinter is installed:

```bash
python3 -m tkinter
```

If draw.io does not open from the GUI, install draw.io Desktop or rely on the generated `.drawio` file and open it manually.

If rendering is blocked, open `*_timeline_quality_report.json` and address the listed blockers before rendering.

If the AI returns prose or a full timeline JSON, ask it again using `prompts/review_timeline_packet.md` and save only the patch JSON.
