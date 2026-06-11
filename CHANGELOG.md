# Changelog

## [0.5.0] - 2026-06-11

- Promoted the coworker-facing semi-beta release to `0.5.0`.
- Changed default artifact layout so each CSV now writes into a dedicated `<csv_stem>_timeline-diagram/` folder.
- Added an `ai-review/` subfolder inside each artifact folder for manual-AI handoff files: the review packet, saved prompt/instructions, and expected AI patch JSON.
- Updated the GUI to describe the artifact-folder behavior, show the AI review folder clearly, and write a reusable `*_timeline_ai_review_prompt.md` file during Prepare.
- Updated CLI prepare output to print the artifact folder and AI review folder, and to write the same saved AI prompt file as the GUI.
- Kept GUI/CLI version display synced from the root `VERSION` file through `timeline_builder.__version__`.
- Changed draw.io rendering z-order so connector wires are written behind date/event cards instead of appearing over card text.
- Added tests for artifact-folder naming, AI review subfolder placement, saved prompt creation, and draw.io connector/card z-order.

## [0.4.7] - 2026-06-11

- Fixed draw.io card stacking so connector wires render behind event/date cards instead of crossing in front of card text.
- Updated `drawio_renderer.py` to collect generated mxGraph cells into z-order buckets before appending them to the XML root.
- Preserved deterministic rendering and existing compact card labels; this is a renderer-only layout change with no timeline/AI patch behavior changes.

## [0.4.6] - 2026-06-11

- Made the GUI a stricter one-button wizard for the normal path: Prepare, Select AI Patch + Check + Render, then Open in draw.io.
- Moved extra helpers such as open packet, copy packet path, open output folder, reviewed JSON, quality report, and SVG preview into the Advanced menu instead of showing them as workflow buttons.
- Centralized GUI version display on `timeline_builder.__version__`, which reads the root `VERSION` file.
- Added a CLI `--version` flag using the same source of truth.
- Improved launcher diagnostics and installer output so stale launcher targets are easier to spot.
- Updated the optional Nautilus action installer to prefer the stable `~/.local/bin/timeline-builder` launcher when available.
- Added tests to prevent GUI version strings from being hard-coded again.

## [0.4.5] - 2026-06-11

- Updated visible event cards to show wrapped title, ticket number, and compact source reference only.
- Removed source date/time from the visible card because the date lane already provides the timeline date.
- Added manual title wrapping before draw.io import so long card titles stay inside the box.
- Added ticket fallback logic for AI-created events, including issue-key lookup from the review packet when the AI patch leaves `issue_key` null.
- Slightly widened/tallened event cards and SVG previews to reduce crowding.
- Updated GUI version label and renderer/apply-patch tests.

## [0.4.4] - 2026-06-10

- Stopped rendering comment/body snippets inside draw.io/SVG event cards.
- Event cards now show only title, ticket, source date/time, and a compact source reference such as `Src: R140 · Comment.2`.
- Preserved full details, source rows, source fields, and source timestamp in draw.io cell metadata and JSON for traceability.
- Slightly widened/tallened cards and added hidden overflow styling to prevent visible spillover.
- Added source timestamp extraction for Python-generated draft events so comment dates/times can show without the full comment text.
- Updated GUI version label and renderer tests.

## [0.4.3] - 2026-06-10

- Clarified that the AI patch is intentionally small because Python already owns the draft timeline.
- Added review-item coverage validation so thin/no-op patches can no longer silently render the untouched Python draft when the review packet contained items.
- Preferred `review_decisions`: one concise decision per review item, while still allowing older rich patch sections to cover review items by source row.
- Updated the manual AI review prompt, README, docs, schema, tests, and GUI version label.

## [0.4.2] - 2026-06-10

- Relaxed the AI patch workflow after real testing showed the one-decision-per-review-item prompt was too conservative.
- Made `review_decisions` optional again; old-style patch JSON from the v0.4.0 prompt is accepted.
- Removed hard title/detail length rejection from patch validation; the renderer now handles card concision by truncating visible text.
- Kept source-row/date guardrails for AI-created events while relaxing brittle source-field matching.
- Made the GUI version/title/status more obvious so stale launchers are easier to spot.

## [0.4.1] - 2026-06-10

- Added `review_decisions` to AI patch JSON so the AI must make exactly one auditable decision for each review packet item.
- Tightened patch validation against source support: AI-created events must use source rows, source fields, and dates present in the draft/review packet.
- Added card-text length checks to reduce overloaded diagram cards.
- Simplified the GUI into tabbed stages with one primary button for prepare and one primary button for patch-check/render.
- Updated draw.io/SVG rendering with colored swimlane backgrounds, softer card styling, shorter visible card content, and source traceability stored as cell metadata.

## [0.4.0] - 2026-06-10

- Refactored the project around a GUI-first Timeline Builder workflow.
- Added the `timeline_builder/` package with shared CSV loading, draft generation, AI patch application, validation, quality gates, deterministic draw.io rendering, SVG preview export, naming, and draw.io Desktop detection.
- Added one user-facing CLI: `scripts/timeline_builder.py`.
- Added `tools/timeline_builder_gui.py` for the full prepare → AI patch → validate → render workflow.
- Changed Nautilus integration to a single optional launcher action: `Timeline: Open in Timeline Builder`.
- Kept the Nautilus Actions Manager generic; it no longer embeds Timeline Builder pipeline controls.
- Added AI patch and review packet schemas.
- Added a stricter manual AI review prompt requiring patch JSON and debug reports.
- Source rows are now handled internally by the CSV loader. The old source-row script remains only as a compatibility/debug helper.

## [0.1.6] - 2026-06-9

* Added `scripts/prepare_timeline_review.py`.

  * Creates a conservative draft timeline JSON from Jira CSV data.
  * Uses an existing `source_row` column when present.
  * Falls back to CSV data row numbers when `source_row` is missing.
  * Can optionally write a numbered CSV with `--write-numbered-csv`.
  * Creates draft incident events from clear `Issue Type = Incident` rows.
  * Extracts only obvious action events from comment text.
  * Sends non-Incident issue types to an AI review packet instead of discarding them.
  * Sends ambiguous comments to the review packet instead of guessing.

* Added `scripts/context_prepare_timeline_review.sh`.

  * Nautilus/right-click wrapper for preparing timeline draft JSON, review packet JSON, and warnings JSON from a selected Jira CSV.

* Added `prompts/review_timeline_packet.md`.

  * Manual AI review prompt for reviewing the generated timeline review packet.

* Added `docs/REVIEW_PACKET_WORKFLOW.md`.

  * Documents the Python draft → AI review packet → reviewed JSON → validation/render workflow.

* Added Nautilus action:

  * `Timeline: Prepare AI review packet`

### Changed

* Updated `tools/nautilus_actions_gui.py` so Timeline actions include the new AI review packet preparation action.
* Changed the intended workflow from “Python tries to fully classify every Jira row” to “Python creates a safe draft and review packet, then AI performs required review.”
* Non-Incident Jira issue types are now preserved for review with source context instead of being reduced to unsupported-type warnings only.
* Ambiguous rows/comments are now passed forward with enough source text for AI/human review.

### Fixed

* Prevented important non-Incident Jira rows from being silently excluded from the timeline process.
* Fixed the earlier workflow gap where warnings listed skipped source rows but did not provide enough source context for AI review to recover or classify them.

### Notes

* This does not remove the existing renderer, validator, or normalizer.
* This adds a safer AI-required review path alongside the existing Python-first tooling.
* The review packet workflow is designed so Python handles mechanical extraction while AI handles judgment-heavy timeline cleanup and classification.

## [0.1.5] - 2026-06-9

### Added

* Added Python-first Jira CSV normalization via `scripts/normalize_jira_csv.py`.
* Added `scripts/context_normalize_jira_csv.sh` for right-click CSV → timeline JSON generation.
* Added `scripts/context_generate_drawio_from_jira_csv.sh` for right-click CSV → timeline JSON → validation → draw.io generation.
* Added Nautilus action: `Timeline: Generate timeline JSON from Jira CSV`.
* Added Nautilus action: `Timeline: Generate draw.io from Jira CSV`.
* Added timestamped `actions.json` backups before GUI save/install/delete operations.

### Changed

* Moved Timeline Builder installer controls out of the selected action’s **Action details** panel and into a separate global Timeline Builder installer section.
* Updated the Timeline action installer to manage the expanded Timeline action set while preserving unrelated Nautilus actions.
* Updated Timeline action installation to replace legacy Timeline action labels plus the new Python-first Timeline action labels.

### Fixed

* Fixed confusing GUI behavior where Timeline Builder controls appeared inside the per-action editor for unrelated actions.

## [0.1.4] - 2026-06-05

### Fixed

- Removed the hardcoded repo path from `tools/nautilus_actions_gui.py`.
- GUI now defaults to the repo it is launched from, so the project can be installed in any user folder.
- Timeline action commands now shell-quote wrapper script paths so repo folders with spaces are safer.
- Replaced the old sanity-check wrapper with the same reliable debug/logging pattern used by the other context-menu wrappers.
- Fixed wrapper behavior so failure logs are printed before the terminal closes.
- Fixed stale draw.io renderer metadata that still referenced `0.1.0`.
- Fixed stale README version text.
- Fixed broken changelog formatting from the previous package.

### Added

- Bundled the Nautilus custom-actions helper under `tools/nautilus-custom-actions/`.
- Added `tools/install_nautilus_custom_actions.sh` to install the bundled Nautilus extension and `nca-settings` command.
- Added an **Install/Update Nautilus Helper** button to the GUI.
- Added fresh-user setup instructions that do not assume a specific username or repo path.

### Changed

- Release ZIP now contains only the current project folder, not old archived copies.
- Removed generated `__pycache__` files from the release package.
- Vendored Nautilus helper now starts with no example right-click actions by default.
- Project version is read from the `VERSION` file when rendering draw.io metadata.

## [0.1.3] - 2026-06-05

### Fixed

- Fixed Nautilus wrapper failures caused by hardcoded versioned repo folder paths.
- Fixed right-click actions after renaming the project folder to an unversioned repo directory.
- Fixed `Timeline: Add source_row to CSV` debug logging on systems without a `~/Desktop` folder.
- Fixed `Timeline: Sanity Check JSON` wrapper path/location issues.
- Fixed `Timeline: Render draw.io` wrapper so it validates before rendering and reports the output path.

### Changed

- Nautilus wrapper scripts detect the repo root from their own location.
- Nautilus wrapper scripts accept the selected file from either `$1` or `$NCA_PATH`.
- Debug logs use XDG-friendly state storage under `~/.local/state/timeline_builder/`.

## [0.1.2] - 2026-06-05

### Added

- Expanded README with first-time setup instructions.
- Added install-anywhere guidance for users with different usernames and folder locations.
- Added command-line workflow documentation.
- Added Nautilus GUI setup workflow.
- Added right-click workflow documentation.

### Changed

- Removed user-specific hardcoded default path from the Nautilus GUI in the intended design.
- GUI should default to the current repo folder when launched from inside the project.

## [0.1.1] - 2026-06-05

### Added

- Added Nautilus right-click wrapper scripts.
- Added standalone GUI editor for Nautilus custom actions.
- Added optional launcher installer.
- GUI loads existing `actions.json` for backwards compatibility.
- GUI can install or update the three timeline actions without deleting unrelated actions.

## [0.1.0] - 2026-06-05

### Added

- Initial GitHub-ready release.
- Added chatbot prompt for Jira CSV to timeline JSON.
- Added JSON schema.
- Added source-row CSV helper.
- Added timeline JSON sanity checker.
- Added draw.io renderer.
- Added sample timeline JSON and sample draw.io output.
- Added smoke test.

