#!/usr/bin/env python3
"""Generic Nautilus custom-actions editor.

This utility intentionally manages only generic Nautilus action fields. Timeline
Builder workflow controls live in tools/timeline_builder_gui.py.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nautilus-custom-actions"
CONFIG_PATH = APP_DIR / "actions.json"

DEFAULT_ACTION: dict[str, Any] = {
    "enabled": True,
    "label": "New Action",
    "command": "xdg-open {path}",
    "selection": "single",
    "extensions": [],
    "mime_types": [],
    "description": "",
    "terminal": False,
    "include_dirs": False,
}

HELP = {
    "label": "Text shown in the Nautilus right-click menu.",
    "command": "Command Nautilus runs. Use placeholders like {path}, {paths}, {dir}, or {raw_path}. Do not wrap {path} in quotes; the extension shell-quotes it.",
    "selection": "When the action appears: single file, multiple files, or any selection.",
    "extensions": "Comma-separated file extensions, such as .csv or .json. Leave blank to allow all extensions.",
    "mime_types": "Comma-separated MIME filters, such as text/csv or application/json. Leave blank unless extension filtering is not enough.",
    "description": "Short tooltip/description.",
    "terminal": "Run in a terminal window so output/errors are visible.",
    "include_dirs": "Show the action for folders as well as files.",
}


def ensure_config() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config({"actions": []}, make_backup=False)


def load_config() -> dict[str, Any]:
    ensure_config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"actions": []}
    if not isinstance(data, dict):
        return {"actions": []}
    if not isinstance(data.get("actions"), list):
        data["actions"] = []
    return data


def backup_config() -> Path | None:
    if not CONFIG_PATH.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CONFIG_PATH.with_name(f"actions.json.bak.{timestamp}")
    backup.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def save_config(data: dict[str, Any], *, make_backup: bool = True) -> Path | None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    backup = backup_config() if make_backup else None
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CONFIG_PATH)
    return backup


def csv_to_list(text: str, *, extensions: bool = False) -> list[str]:
    result: list[str] = []
    for raw in text.split(","):
        item = raw.strip()
        if not item:
            continue
        if extensions and not item.startswith(".") and not item.startswith("*"):
            item = "." + item
        result.append(item)
    return result


def list_to_csv(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return ", ".join(str(item) for item in value)


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.tip:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{self.widget.winfo_rootx() + 18}+{self.widget.winfo_rooty() + 24}")
        label = tk.Label(self.tip, text=self.text, justify="left", bg="#111827", fg="white", padx=8, pady=6, wraplength=360)
        label.pack()

    def hide(self, _event=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


class NautilusActionsGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nautilus Actions Manager")
        self.geometry("1040x700")
        self.minsize(880, 620)
        self.config_data: dict[str, Any] = {"actions": []}
        self.current_index: int | None = None

        self.enabled_var = tk.BooleanVar(value=True)
        self.label_var = tk.StringVar()
        self.command_var = tk.StringVar()
        self.selection_var = tk.StringVar(value="single")
        self.extensions_var = tk.StringVar()
        self.mime_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self.terminal_var = tk.BooleanVar(value=False)
        self.include_dirs_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready.")

        self._style()
        self._build_ui()
        self.reload_config()

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Header.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Field.TLabel", font=("TkDefaultFont", 10, "bold"))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Nautilus Actions Manager", style="Header.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status_var).pack(side="right")
        ttk.Label(root, text=f"Editing {CONFIG_PATH}").pack(anchor="w", pady=(0, 10))

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", padx=(0, 12))
        ttk.Label(left, text="Actions", style="Field.TLabel").pack(anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self.action_list = tk.Listbox(list_frame, width=34, activestyle="none", yscrollcommand=scrollbar.set)
        self.action_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.action_list.yview)
        self.action_list.bind("<<ListboxSelect>>", self._on_select)
        left_buttons = ttk.Frame(left)
        left_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(left_buttons, text="New", command=self.new_action).pack(side="left")
        ttk.Button(left_buttons, text="Duplicate", command=self.duplicate_action).pack(side="left", padx=6)
        ttk.Button(left_buttons, text="Delete", command=self.delete_action).pack(side="right")

        form = ttk.Frame(body)
        form.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(form)
        top.pack(fill="x")
        ttk.Label(top, text="Action details", style="Field.TLabel").pack(side="left")
        ttk.Checkbutton(top, text="Enabled", variable=self.enabled_var).pack(side="right")

        self._field(form, "Label", self.label_var, "label")
        self._field(form, "Command", self.command_var, "command")
        self._field(form, "Extensions", self.extensions_var, "extensions")
        self._field(form, "MIME types", self.mime_var, "mime_types")
        self._field(form, "Description", self.description_var, "description")

        selection = ttk.Frame(form)
        selection.pack(fill="x", pady=(10, 0))
        ttk.Label(selection, text="Selection", style="Field.TLabel").pack(side="left")
        self._help(selection, "selection")
        for value in ["single", "multiple", "any"]:
            ttk.Radiobutton(selection, text=value, value=value, variable=self.selection_var).pack(side="left", padx=(10, 0))
        ttk.Checkbutton(selection, text="Terminal", variable=self.terminal_var).pack(side="right", padx=(0, 8))
        self._help(selection, "terminal", side="right")
        ttk.Checkbutton(selection, text="Include directories", variable=self.include_dirs_var).pack(side="right", padx=(0, 8))
        self._help(selection, "include_dirs", side="right")

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Button(bottom, text="Save", command=self.save_current).pack(side="left")
        ttk.Button(bottom, text="Reload", command=self.reload_config).pack(side="left", padx=8)
        ttk.Button(bottom, text="Open JSON", command=self.open_json).pack(side="left", padx=8)
        ttk.Button(bottom, text="Restart Nautilus", command=self.restart_nautilus).pack(side="right")

    def _help(self, parent: tk.Widget, key: str, *, side: str = "left") -> None:
        label = ttk.Label(parent, text="?", width=2)
        label.pack(side=side, padx=(4, 0))
        Tooltip(label, HELP[key])

    def _field(self, parent: tk.Widget, label: str, var: tk.StringVar, help_key: str) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(10, 0))
        left = ttk.Frame(frame)
        left.pack(fill="x")
        ttk.Label(left, text=label, style="Field.TLabel").pack(side="left")
        self._help(left, help_key)
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(fill="x", pady=(3, 0))

    def reload_config(self) -> None:
        self.config_data = load_config()
        self.current_index = None
        self._refresh_list()
        self._clear_form()
        self.status_var.set("Reloaded actions.json.")

    def _refresh_list(self) -> None:
        self.action_list.delete(0, tk.END)
        for action in self.config_data.get("actions", []):
            prefix = "✓ " if action.get("enabled", True) else "  "
            self.action_list.insert(tk.END, prefix + str(action.get("label") or "(no label)"))

    def _on_select(self, _event=None) -> None:
        selection = self.action_list.curselection()
        if not selection:
            return
        self.current_index = int(selection[0])
        self._load_form(self.config_data.get("actions", [])[self.current_index])

    def _load_form(self, action: dict[str, Any]) -> None:
        self.enabled_var.set(bool(action.get("enabled", True)))
        self.label_var.set(str(action.get("label", "")))
        self.command_var.set(str(action.get("command", "")))
        self.selection_var.set(str(action.get("selection", "single")))
        self.extensions_var.set(list_to_csv(action.get("extensions", [])))
        self.mime_var.set(list_to_csv(action.get("mime_types", [])))
        self.description_var.set(str(action.get("description", "")))
        self.terminal_var.set(bool(action.get("terminal", False)))
        self.include_dirs_var.set(bool(action.get("include_dirs", False)))

    def _clear_form(self) -> None:
        self._load_form(DEFAULT_ACTION)

    def _form_action(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled_var.get()),
            "label": self.label_var.get().strip(),
            "command": self.command_var.get().strip(),
            "selection": self.selection_var.get(),
            "extensions": csv_to_list(self.extensions_var.get(), extensions=True),
            "mime_types": csv_to_list(self.mime_var.get()),
            "description": self.description_var.get().strip(),
            "terminal": bool(self.terminal_var.get()),
            "include_dirs": bool(self.include_dirs_var.get()),
        }

    def save_current(self) -> None:
        actions = self.config_data.setdefault("actions", [])
        if self.current_index is None:
            actions.append(self._form_action())
            self.current_index = len(actions) - 1
        else:
            actions[self.current_index] = self._form_action()
        backup = save_config(self.config_data)
        self._refresh_list()
        self.action_list.selection_clear(0, tk.END)
        self.action_list.selection_set(self.current_index)
        self.status_var.set(f"Saved. Backup: {backup.name}" if backup else "Saved.")

    def new_action(self) -> None:
        self.current_index = None
        self.action_list.selection_clear(0, tk.END)
        self._clear_form()
        self.status_var.set("New action ready. Edit it, then Save.")

    def duplicate_action(self) -> None:
        if self.current_index is None:
            messagebox.showinfo("Nothing selected", "Select an action to duplicate.")
            return
        action = dict(self.config_data["actions"][self.current_index])
        action["label"] = f"{action.get('label', 'Action')} Copy"
        self.config_data.setdefault("actions", []).append(action)
        self.current_index = len(self.config_data["actions"]) - 1
        save_config(self.config_data)
        self._refresh_list()
        self.action_list.selection_set(self.current_index)
        self._load_form(action)
        self.status_var.set("Duplicated and saved.")

    def delete_action(self) -> None:
        if self.current_index is None:
            messagebox.showinfo("Nothing selected", "Select an action to delete.")
            return
        action = self.config_data["actions"][self.current_index]
        if not messagebox.askyesno("Delete action", f"Delete this action?\n\n{action.get('label', '(no label)')}"):
            return
        self.config_data["actions"].pop(self.current_index)
        self.current_index = None
        save_config(self.config_data)
        self._refresh_list()
        self._clear_form()
        self.status_var.set("Deleted and saved.")

    def open_json(self) -> None:
        ensure_config()
        subprocess.Popen(["xdg-open", str(CONFIG_PATH)])

    def restart_nautilus(self) -> None:
        try:
            subprocess.run(["nautilus", "-q"], check=False)
            self.status_var.set("Nautilus restarted.")
        except Exception as exc:
            messagebox.showerror("Could not restart Nautilus", str(exc))


def main() -> int:
    app = NautilusActionsGui()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
