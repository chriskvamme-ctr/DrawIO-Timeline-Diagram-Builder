#!/usr/bin/env python3
"""GUI-first Timeline Builder workflow."""
from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timeline_builder import __version__
from timeline_builder.ai_patch import apply_patch, load_json
from timeline_builder.drawio_desktop import open_path, status_text
from timeline_builder.drawio_renderer import render, render_svg
from timeline_builder.draft_builder import prepare
from timeline_builder.naming import csv_artifact_paths
from timeline_builder.quality_gates import load_optional_review_packet, run_quality_gates, write_quality_report
from timeline_builder.review_packet import copy_prompt_text
from timeline_builder.validation import validate_patch, validate_timeline

APP_TITLE = f"Timeline Builder v{__version__} — Wizard"


class TimelineBuilderGui(tk.Tk):
    """Small wizard that keeps normal workflow to one primary button per stage."""

    def __init__(self, preloaded_csv: Path | None = None) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1080x760")
        self.minsize(900, 660)

        self.csv_var = tk.StringVar(value=str(preloaded_csv) if preloaded_csv else "")
        initial_output = str(preloaded_csv.parent) if preloaded_csv else ""
        self.output_dir_var = tk.StringVar(value=initial_output)
        self.patch_var = tk.StringVar(value="")
        self.drawio_status_var = tk.StringVar(value=status_text())
        self.stage_var = tk.StringVar(value="Step 1: select a CSV, then press Prepare AI Packet.")
        self.paths = csv_artifact_paths(preloaded_csv) if preloaded_csv else None

        self._build_ui()
        self.log(f"Running Timeline Builder {__version__} from: {ROOT}")
        if preloaded_csv:
            self._update_paths_from_input(reset_patch=True)
            self.log(f"Preloaded CSV: {preloaded_csv}")
        self._refresh_stage_text()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._build_menu()
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Header.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Stage.TLabel", font=("TkDefaultFont", 11))
        style.configure("Primary.TButton", padding=(14, 8))
        style.configure("Section.TLabelframe.Label", font=("TkDefaultFont", 11, "bold"))

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=APP_TITLE, style="Header.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.drawio_status_var).pack(side="right")

        ttk.Label(root, textvariable=self.stage_var, style="Stage.TLabel").pack(fill="x", pady=(0, 10))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="x", pady=(0, 8))

        self.prepare_tab = ttk.Frame(self.notebook, padding=12)
        self.ai_tab = ttk.Frame(self.notebook, padding=12)
        self.output_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.prepare_tab, text="1 Prepare")
        self.notebook.add(self.ai_tab, text="2 AI Patch")
        self.notebook.add(self.output_tab, text="3 Done")

        self._build_prepare_tab(self.prepare_tab)
        self._build_ai_tab(self.ai_tab)
        self._build_output_tab(self.output_tab)
        self._build_log_section(root)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        advanced = tk.Menu(menu, tearoff=False)
        advanced.add_command(label="Copy AI prompt again", command=self.copy_prompt)
        advanced.add_command(label="Copy review packet path", command=self.copy_packet_path)
        advanced.add_command(label="Open review packet", command=lambda: self.open_file("review_packet"))
        advanced.add_command(label="Open AI prompt file", command=lambda: self.open_file("ai_prompt"))
        advanced.add_command(label="Open output folder", command=self.open_output_folder)
        advanced.add_separator()
        advanced.add_command(label="Open reviewed JSON", command=lambda: self.open_file("reviewed"))
        advanced.add_command(label="Open quality report", command=lambda: self.open_file("quality_report"))
        advanced.add_command(label="Open SVG preview", command=lambda: self.open_file("svg"))
        advanced.add_separator()
        advanced.add_command(label="Copy launcher diagnostics", command=self.copy_diagnostics)
        menu.add_cascade(label="Advanced", menu=advanced)
        self.config(menu=menu)

    def _build_prepare_tab(self, parent: tk.Widget) -> None:
        intro = (
            "Load a Jira CSV and choose where to create the artifact folder. The wizard creates a "
            "<csv name>_timeline-diagram folder, puts the AI handoff files in an ai-review subfolder, "
            "then copies the prompt and file instructions to your clipboard."
        )
        ttk.Label(parent, text=intro, wraplength=930, justify="left").pack(fill="x", pady=(0, 12))

        form = ttk.Frame(parent)
        form.pack(fill="x")
        ttk.Label(form, text="Jira CSV").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.csv_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(form, text="Select CSV", command=self.select_csv).grid(row=0, column=2)
        ttk.Label(form, text="Save under folder").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(form, textvariable=self.output_dir_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(form, text="Choose Folder", command=self.select_output_folder).grid(row=1, column=2, pady=(8, 0))
        form.columnconfigure(1, weight=1)

        self.prepare_paths_label = ttk.Label(parent, text="", wraplength=930, justify="left")
        self.prepare_paths_label.pack(fill="x", pady=(12, 0))

        action_row = ttk.Frame(parent)
        action_row.pack(fill="x", pady=(18, 0))
        ttk.Button(
            action_row,
            text="Prepare AI Packet + Copy Prompt",
            style="Primary.TButton",
            command=self.prepare_for_ai,
        ).pack(side="left")

    def _build_ai_tab(self, parent: tk.Widget) -> None:
        text = (
            "Paste the copied instructions into your AI chat, attach or paste the review packet, and save the returned "
            "JSON patch. Then use the single button below. It will select or auto-detect the patch, validate it, apply it, "
            "run quality gates, render draw.io, and export SVG."
        )
        ttk.Label(parent, text=text, wraplength=930, justify="left").pack(fill="x")

        self.ai_paths_label = ttk.Label(parent, text="", wraplength=930, justify="left")
        self.ai_paths_label.pack(fill="x", pady=(12, 0))

        action_row = ttk.Frame(parent)
        action_row.pack(fill="x", pady=(18, 0))
        ttk.Button(
            action_row,
            text="Select AI Patch + Check + Render",
            style="Primary.TButton",
            command=self.select_patch_and_render,
        ).pack(side="left")

    def _build_output_tab(self, parent: tk.Widget) -> None:
        ttk.Label(
            parent,
            text="The reviewed timeline has been validated and rendered. Open the editable draw.io file from here.",
            wraplength=930,
            justify="left",
        ).pack(fill="x")
        self.output_paths_label = ttk.Label(parent, text="", wraplength=930, justify="left")
        self.output_paths_label.pack(fill="x", pady=(12, 0))

        action_row = ttk.Frame(parent)
        action_row.pack(fill="x", pady=(18, 0))
        ttk.Button(action_row, text="Open in draw.io", style="Primary.TButton", command=lambda: self.open_file("drawio")).pack(side="left")

    def _build_log_section(self, parent: tk.Widget) -> None:
        frame = ttk.LabelFrame(parent, text="Status log", style="Section.TLabelframe", padding=8)
        frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        self.log_text = tk.Text(frame, height=15, wrap="word", yscrollcommand=scrollbar.set)
        self.log_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

    # ------------------------------------------------------------------
    # Path and state helpers
    # ------------------------------------------------------------------
    def select_csv(self) -> None:
        path = filedialog.askopenfilename(title="Select Jira CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*")])
        if not path:
            return
        self.csv_var.set(path)
        if not self.output_dir_var.get():
            self.output_dir_var.set(str(Path(path).parent))
        self._update_paths_from_input(reset_patch=True)
        self._refresh_stage_text()
        self.log(f"Selected CSV: {path}")

    def select_output_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder", initialdir=self.output_dir_var.get() or str(Path.home()))
        if folder:
            self.output_dir_var.set(folder)
            self._update_paths_from_input(reset_patch=True)
            self._refresh_stage_text()
            self.log(f"Output folder: {folder}")

    def _update_paths_from_input(self, *, reset_patch: bool = False) -> None:
        csv_text = self.csv_var.get().strip()
        if not csv_text:
            self.paths = None
            return
        output = Path(self.output_dir_var.get()).expanduser() if self.output_dir_var.get().strip() else None
        self.paths = csv_artifact_paths(Path(csv_text).expanduser(), output)
        if reset_patch or not self.patch_var.get().strip():
            self.patch_var.set(str(self.paths.ai_patch))

    def _refresh_stage_text(self) -> None:
        self._update_paths_from_input()
        if not self.paths:
            self.stage_var.set("Step 1: select a CSV, then press Prepare AI Packet.")
            self._refresh_path_labels()
            return
        if self.paths.drawio.exists():
            self.stage_var.set("Step 3: rendered draw.io is ready.")
            self.notebook.select(self.output_tab)
        elif self.paths.review_packet.exists():
            self.stage_var.set("Step 2: send the packet to AI, save the patch JSON, then press Select AI Patch + Check + Render.")
        else:
            self.stage_var.set("Step 1: press Prepare AI Packet + Copy Prompt.")
        self._refresh_path_labels()

    def _refresh_path_labels(self) -> None:
        if not self.paths:
            prepare_text = "No CSV selected yet."
            ai_text = "Prepare the AI packet first."
            output_text = "No output has been rendered yet."
        else:
            prepare_text = (
                f"Artifact folder: {self.paths.artifact_folder}\n"
                f"Draft: {self.paths.draft}\n"
                f"AI review folder: {self.paths.ai_review_folder}\n"
                f"Review packet: {self.paths.review_packet}\n"
                f"AI prompt file: {self.paths.ai_prompt}\n"
                f"Expected AI patch: {self.paths.ai_patch}"
            )
            ai_text = (
                f"AI review folder: {self.paths.ai_review_folder}\n"
                f"Review packet to give AI: {self.paths.review_packet}\n"
                f"Prompt file, if needed: {self.paths.ai_prompt}\n"
                f"Save AI patch here: {self.paths.ai_patch}"
            )
            output_text = (
                f"Artifact folder: {self.paths.artifact_folder}\n"
                f"draw.io: {self.paths.drawio}\n"
                f"SVG preview: {self.paths.svg}\n"
                f"Quality report: {self.paths.quality_report}"
            )
        self.prepare_paths_label.config(text=prepare_text)
        self.ai_paths_label.config(text=ai_text)
        self.output_paths_label.config(text=output_text)

    def _require_paths(self) -> bool:
        self._update_paths_from_input()
        if not self.paths:
            messagebox.showerror("Missing input", "Select a Jira CSV first.")
            return False
        return True

    def log(self, message: str) -> None:
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.update_idletasks()

    # ------------------------------------------------------------------
    # Primary workflow buttons
    # ------------------------------------------------------------------
    def prepare_for_ai(self) -> None:
        if not self._require_paths():
            return
        try:
            self._prepare_review_files()
            self.copy_prompt(show_message=False)
            self.notebook.select(self.ai_tab)
            self._refresh_stage_text()
            self.log("Copied AI prompt + packet instructions to clipboard.")
            self.log("Next: send the review packet to AI, save the returned JSON patch, then press the AI Patch button.")
            messagebox.showinfo(
                "AI packet ready",
                "Draft, review packet, warnings, and AI prompt file are ready.\n\nThe AI prompt + file instructions were copied to your clipboard.",
            )
        except Exception as exc:
            self.log(f"ERROR preparing AI review: {exc}")
            messagebox.showerror("Prepare failed", str(exc))

    def select_patch_and_render(self) -> None:
        if not self._require_paths():
            return
        try:
            patch_path = self._resolve_patch_path()
            if not patch_path:
                return
            self.patch_var.set(str(patch_path))
            self._check_patch_and_render(patch_path)
        except Exception as exc:
            self.log(f"ERROR checking/rendering: {exc}")
            messagebox.showerror("Check + render failed", str(exc))

    # ------------------------------------------------------------------
    # Workflow internals
    # ------------------------------------------------------------------
    def _prepare_review_files(self) -> None:
        if not self._require_paths():
            return
        csv_path = Path(self.csv_var.get()).expanduser()
        draft, packet, warnings = prepare(csv_path, draft_timeline_file=self.paths.draft.name)
        self._write_json(self.paths.draft, draft)
        self._write_json(self.paths.review_packet, packet)
        self._write_json(self.paths.warnings, warnings)
        self.paths.ai_prompt.parent.mkdir(parents=True, exist_ok=True)
        self.paths.ai_prompt.write_text(
            copy_prompt_text(draft_path=self.paths.draft, packet_path=self.paths.review_packet, patch_path=self.paths.ai_patch),
            encoding="utf-8",
        )
        self.log(f"Artifact folder: {self.paths.artifact_folder}")
        self.log(f"AI review folder: {self.paths.ai_review_folder}")
        self.log(f"Wrote draft: {self.paths.draft}")
        self.log(f"Wrote review packet: {self.paths.review_packet}")
        self.log(f"Wrote AI prompt file: {self.paths.ai_prompt}")
        self.log(f"Wrote warnings: {self.paths.warnings}")
        self.log(f"Review items in packet: {len(packet.get('review_items', []))}")

    def _resolve_patch_path(self) -> Path | None:
        expected = self.paths.ai_patch if self.paths else None
        current = Path(self.patch_var.get()).expanduser() if self.patch_var.get().strip() else expected
        if current and current.exists():
            self.log(f"Using AI patch: {current}")
            return current
        initial = str(expected.parent) if expected else str(Path.home())
        path = filedialog.askopenfilename(
            title="Select AI patch JSON",
            initialdir=initial,
            initialfile=expected.name if expected else "",
            filetypes=[("JSON files", "*.json"), ("All files", "*")],
        )
        if not path:
            self.log("AI patch selection cancelled.")
            return None
        return Path(path).expanduser()

    def _check_patch_and_render(self, patch_path: Path) -> None:
        if not self.paths:
            raise ValueError("Select a Jira CSV first.")
        if not patch_path.exists():
            raise FileNotFoundError(f"Patch JSON does not exist yet: {patch_path}")
        if not self.paths.draft.exists():
            raise FileNotFoundError(f"Draft JSON does not exist yet: {self.paths.draft}")

        draft = load_json(self.paths.draft)
        patch = load_json(patch_path)
        review_packet = load_optional_review_packet(self.paths.review_packet)

        errors = validate_patch(patch, draft, review_packet=review_packet)
        if errors:
            report = {"status": "blocked", "blockers": ["AI patch invalid"], "validation_errors": errors}
            write_quality_report(report, self.paths.quality_report)
            raise ValueError("AI patch is invalid:\n" + "\n".join(f"- {error}" for error in errors))
        self.log("AI patch passed validation.")

        reviewed = apply_patch(draft, patch, review_packet=review_packet)
        self._write_json(self.paths.reviewed, reviewed)
        timeline_errors = validate_timeline(reviewed)
        if timeline_errors:
            raise ValueError("Reviewed timeline is invalid:\n" + "\n".join(f"- {error}" for error in timeline_errors))
        self.log(f"Wrote reviewed JSON: {self.paths.reviewed}")

        report = run_quality_gates(reviewed, review_packet=review_packet)
        write_quality_report(report, self.paths.quality_report)
        self.log(f"Wrote quality report: {self.paths.quality_report}")
        self.log(f"Quality status: {report['status']}")
        for blocker in report.get("blockers", []):
            self.log(f"BLOCKER: {blocker}")
        if report.get("status") == "blocked":
            blockers = "\n".join(str(x) for x in report.get("blockers", []))
            raise ValueError("Render blocked by quality gates:\n" + blockers)

        render(self.paths.reviewed, self.paths.drawio)
        self.log(f"Wrote draw.io: {self.paths.drawio}")
        render_svg(self.paths.reviewed, self.paths.svg)
        self.log(f"Wrote SVG preview: {self.paths.svg}")

        self.notebook.select(self.output_tab)
        self._refresh_stage_text()
        self.open_file("drawio", show_missing_error=False)
        messagebox.showinfo("Render complete", "The draw.io file is ready. The Output tab has the final open button.")

    # ------------------------------------------------------------------
    # Advanced/menu helpers
    # ------------------------------------------------------------------
    def copy_prompt(self, *, show_message: bool = True) -> None:
        if not self._require_paths():
            return
        text = copy_prompt_text(draft_path=self.paths.draft, packet_path=self.paths.review_packet, patch_path=self.paths.ai_patch)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("Copied AI review prompt and file instructions to clipboard.")
        if show_message:
            messagebox.showinfo("Copied", "AI review prompt + file instructions copied to clipboard.")

    def copy_packet_path(self) -> None:
        if not self._require_paths():
            return
        self.clipboard_clear()
        self.clipboard_append(str(self.paths.review_packet))
        self.log("Copied review packet path to clipboard.")

    def copy_diagnostics(self) -> None:
        diagnostics = f"Timeline Builder {__version__}\nProject root: {ROOT}\nPython: {sys.executable}\nLauncher target should be: {ROOT / 'tools' / 'timeline_builder_gui.py'}\n"
        self.clipboard_clear()
        self.clipboard_append(diagnostics)
        self.log("Copied launcher diagnostics to clipboard.")
        messagebox.showinfo("Diagnostics copied", diagnostics)

    # Compatibility/granular methods kept for scripts/tests/debugging, but not shown as normal buttons.
    def prepare_review(self) -> None:
        self._prepare_review_files()

    def select_patch(self) -> None:
        if not self._require_paths():
            return
        path = self._resolve_patch_path()
        if path:
            self.patch_var.set(str(path))
            self.log(f"Selected AI patch: {path}")

    def check_patch_and_render(self) -> None:
        if not self._require_paths():
            return
        patch_path = Path(self.patch_var.get()).expanduser()
        self._check_patch_and_render(patch_path)

    def apply_ai_patch(self) -> None:
        self.check_patch_and_render()

    def validate_reviewed(self) -> None:
        if not self._require_paths():
            return
        try:
            data = load_json(self.paths.reviewed)
            errors = validate_timeline(data)
            if errors:
                self.log("Reviewed JSON is invalid:")
                for error in errors:
                    self.log(f"- {error}")
                messagebox.showerror("Invalid reviewed JSON", "\n".join(errors))
            else:
                self.log("Reviewed JSON is valid.")
        except Exception as exc:
            self.log(f"ERROR validating reviewed JSON: {exc}")
            messagebox.showerror("Validation failed", str(exc))

    def run_quality(self) -> None:
        if not self._require_paths():
            return
        try:
            reviewed = load_json(self.paths.reviewed)
            report = run_quality_gates(reviewed, review_packet=load_optional_review_packet(self.paths.review_packet))
            write_quality_report(report, self.paths.quality_report)
            self.log(f"Wrote quality report: {self.paths.quality_report}")
            self.log(f"Quality status: {report['status']}")
            for blocker in report.get("blockers", []):
                self.log(f"BLOCKER: {blocker}")
        except Exception as exc:
            self.log(f"ERROR running quality gates: {exc}")
            messagebox.showerror("Quality gates failed", str(exc))

    def render_drawio(self) -> None:
        if not self._require_paths():
            return
        try:
            render(self.paths.reviewed, self.paths.drawio)
            self.log(f"Wrote draw.io: {self.paths.drawio}")
        except Exception as exc:
            self.log(f"ERROR rendering draw.io: {exc}")
            messagebox.showerror("Render failed", str(exc))

    def export_svg(self) -> None:
        if not self._require_paths():
            return
        try:
            render_svg(self.paths.reviewed, self.paths.svg)
            self.log(f"Wrote SVG preview: {self.paths.svg}")
        except Exception as exc:
            self.log(f"ERROR exporting SVG: {exc}")
            messagebox.showerror("SVG export failed", str(exc))

    def open_output_folder(self) -> None:
        if not self._require_paths():
            return
        self._open_path(self.paths.artifact_folder)

    def open_file(self, kind: str, *, show_missing_error: bool = True) -> None:
        if not self._require_paths():
            return
        path = getattr(self.paths, kind)
        if not path.exists():
            if show_missing_error:
                messagebox.showerror("Missing file", f"File does not exist yet:\n\n{path}")
            return
        if kind == "drawio":
            proc = open_path(path)
            if proc:
                self.log(f"Opened draw.io: {path}")
                return
        self._open_path(path)

    def _open_path(self, path: Path) -> None:
        try:
            subprocess.Popen(["xdg-open", str(path)])
            self.log(f"Opened: {path}")
        except Exception as exc:
            self.log(f"ERROR opening {path}: {exc}")
            messagebox.showerror("Open failed", str(exc))

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    preloaded = Path(argv[0]).expanduser() if argv else None
    app = TimelineBuilderGui(preloaded)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
