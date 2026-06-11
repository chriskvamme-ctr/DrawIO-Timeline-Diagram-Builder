"""Predictable artifact naming helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ARTIFACT_FOLDER_SUFFIX = "_timeline-diagram"
AI_REVIEW_FOLDER_NAME = "ai-review"


@dataclass(frozen=True)
class TimelinePaths:
    base: Path
    draft: Path
    review_packet: Path
    warnings: Path
    ai_patch: Path
    ai_prompt: Path
    reviewed: Path
    quality_report: Path
    drawio: Path
    svg: Path
    numbered_csv: Path

    @property
    def artifact_folder(self) -> Path:
        """Folder that contains the normal timeline artifacts for one CSV."""
        return self.base.parent

    @property
    def ai_review_folder(self) -> Path:
        """Folder that contains the manual-AI review handoff files."""
        return self.review_packet.parent


def artifact_folder_for_csv(input_csv: Path, output_folder: Path | None = None) -> Path:
    """Return the per-CSV artifact folder.

    If output_folder is already the expected ``<csv_stem>_timeline-diagram``
    folder, use it directly. Otherwise create/use that child folder under the
    selected output parent.
    """
    input_csv = Path(input_csv)
    parent = Path(output_folder) if output_folder else input_csv.parent
    folder_name = f"{input_csv.stem}{ARTIFACT_FOLDER_SUFFIX}"
    if parent.name == folder_name:
        return parent
    return parent / folder_name


def csv_artifact_paths(input_csv: Path, output_folder: Path | None = None) -> TimelinePaths:
    """Return the fixed-stage artifact paths for a Jira CSV input."""
    input_csv = Path(input_csv)
    folder = artifact_folder_for_csv(input_csv, output_folder)
    base = folder / input_csv.stem
    return paths_from_base(base)


def paths_from_base(base: Path) -> TimelinePaths:
    base = Path(base)
    ai_folder = base.parent / AI_REVIEW_FOLDER_NAME
    return TimelinePaths(
        base=base,
        draft=base.with_name(base.name + "_timeline_draft.json"),
        review_packet=ai_folder / (base.name + "_timeline_review_packet.json"),
        warnings=base.with_name(base.name + "_timeline_warnings.json"),
        ai_patch=ai_folder / (base.name + "_timeline_ai_patch.json"),
        ai_prompt=ai_folder / (base.name + "_timeline_ai_review_prompt.md"),
        reviewed=base.with_name(base.name + "_timeline_reviewed.json"),
        quality_report=base.with_name(base.name + "_timeline_quality_report.json"),
        drawio=base.with_name(base.name + "_timeline_reviewed.drawio"),
        svg=base.with_name(base.name + "_timeline_reviewed.svg"),
        numbered_csv=base.with_name(base.name + "_numbered.csv"),
    )


def base_from_draft_path(draft_json: Path) -> Path:
    path = Path(draft_json)
    suffix = "_timeline_draft"
    stem = path.stem
    if stem.endswith(suffix):
        return path.with_name(stem[: -len(suffix)])
    return path.with_suffix("")


def base_from_reviewed_path(reviewed_json: Path) -> Path:
    path = Path(reviewed_json)
    suffix = "_timeline_reviewed"
    stem = path.stem
    if stem.endswith(suffix):
        return path.with_name(stem[: -len(suffix)])
    return path.with_suffix("")


def default_drawio_path(reviewed_json: Path) -> Path:
    return paths_from_base(base_from_reviewed_path(reviewed_json)).drawio


def default_svg_path(reviewed_json: Path) -> Path:
    return paths_from_base(base_from_reviewed_path(reviewed_json)).svg
