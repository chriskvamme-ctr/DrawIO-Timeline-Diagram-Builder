"""DrawIO Timeline Diagram Builder package."""

__all__ = ["__version__"]

try:
    from pathlib import Path

    __version__ = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
except OSError:  # pragma: no cover
    __version__ = "unknown"
