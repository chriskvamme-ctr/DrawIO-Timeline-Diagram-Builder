# Nautilus Custom Actions Helper

This is the small Nautilus/GNOME Files extension used by Jira Draw.io Timeline Builder.

## Install

```bash
bash install.sh
```

The installer places files under:

```text
~/.local/share/nautilus-python/extensions/
~/.local/bin/nca-settings
~/.config/nautilus-custom-actions/actions.json
```

## Settings

Open the terminal settings editor with:

```bash
nca-settings
```

The Timeline Builder repo also includes a GUI editor:

```bash
python3 tools/nautilus_actions_gui.py
```

## Placeholders

Use these in action commands:

- `{path}` first selected file/folder, shell-quoted
- `{paths}` all selected files/folders, shell-quoted
- `{dir}` directory of the first selected item
- `{raw_path}` unquoted first path, only for advanced use

Do not wrap `{path}` or `{paths}` in quotes. The extension shell-quotes them for you.
