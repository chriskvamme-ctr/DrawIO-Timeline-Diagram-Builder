"""Jira CSV loading, column detection, and source-row handling."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

FIELD_ALIASES = {
    "source_row": ["source_row", "source row", "row", "row number"],
    "issue_key": ["issue key", "issuekey", "key", "issue id", "ticket", "ticket key"],
    "issue_type": ["issue type", "issuetype", "type"],
    "summary": ["summary", "title", "issue summary"],
    "created": ["created", "created date", "date created"],
    "resolved": ["resolved", "resolution date", "date resolved"],
    "status": ["status"],
    "assignee": ["assignee"],
    "priority": ["priority"],
    "labels": ["labels", "label"],
    "description": ["description"],
}


@dataclass(frozen=True)
class Columns:
    source_row: str | None
    issue_key: str | None
    issue_type: str | None
    summary: str | None
    created: str | None
    resolved: str | None
    status: str | None
    assignee: str | None
    priority: str | None
    labels: str | None
    description: str | None
    comments: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_row": self.source_row,
            "issue_key": self.issue_key,
            "issue_type": self.issue_type,
            "summary": self.summary,
            "created": self.created,
            "resolved": self.resolved,
            "status": self.status,
            "assignee": self.assignee,
            "priority": self.priority,
            "labels": self.labels,
            "description": self.description,
            "comments": list(self.comments),
        }


@dataclass(frozen=True)
class Comment:
    field: str
    text: str
    date: str | None


@dataclass(frozen=True)
class JiraRow:
    source_row: int
    raw: dict[str, str]
    values: dict[str, str]
    comments: list[Comment]

    def value(self, concept: str) -> str:
        return self.values.get(concept, "")


@dataclass(frozen=True)
class JiraCsv:
    path: Path
    fieldnames: list[str]
    columns: Columns
    rows: list[JiraRow]
    source_rows_generated: bool


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\ufeff", " ")).strip()


def shorten(value: Any, limit: int) -> str:
    text = compact(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


def find_column(fieldnames: list[str], concept: str) -> str | None:
    lookup = {normalized_name(name): name for name in fieldnames if name is not None}
    for alias in FIELD_ALIASES[concept]:
        match = lookup.get(normalized_name(alias))
        if match:
            return match
    return None


def comment_columns(fieldnames: list[str]) -> list[str]:
    # Jira exports Comments, Comments.1, Comments.2, ...; detect case-insensitively.
    return [name for name in fieldnames if name and "comment" in normalized_name(name)]


def detect_columns(fieldnames: list[str]) -> Columns:
    return Columns(
        source_row=find_column(fieldnames, "source_row"),
        issue_key=find_column(fieldnames, "issue_key"),
        issue_type=find_column(fieldnames, "issue_type"),
        summary=find_column(fieldnames, "summary"),
        created=find_column(fieldnames, "created"),
        resolved=find_column(fieldnames, "resolved"),
        status=find_column(fieldnames, "status"),
        assignee=find_column(fieldnames, "assignee"),
        priority=find_column(fieldnames, "priority"),
        labels=find_column(fieldnames, "labels"),
        description=find_column(fieldnames, "description"),
        comments=comment_columns(fieldnames),
    )


def parse_date(value: Any) -> str | None:
    text = compact(value)
    if not text:
        return None

    # Jira comment style: 05/May/26 4:43 AM
    match = re.search(r"\b(\d{1,2})/([A-Za-z]{3})/(\d{2,4})\b", text)
    if match:
        day = int(match.group(1))
        month = MONTHS.get(match.group(2).lower())
        year = int(match.group(3))
        if month:
            if year < 100:
                year += 2000
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return None

    # ISO style, including timestamps that begin with ISO dates.
    match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if match:
        year, month, day = [int(x) for x in match.groups()]
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    # Jira CSV style used in this project: M/D/YY or M/D/YYYY.
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", text)
    if match:
        month, day, year = [int(x) for x in match.groups()]
        if year < 100:
            year += 2000
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    # A few explicit datetime formats, avoiding dateutil as a dependency.
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text[: len(datetime.now().strftime(fmt))], fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _source_row_value(row: dict[str, str], index: int, columns: Columns) -> tuple[int, bool]:
    if columns.source_row:
        raw = compact(row.get(columns.source_row, ""))
        if raw.isdigit():
            return int(raw), False
    return index, True


def _concept_values(row: dict[str, str], columns: Columns) -> dict[str, str]:
    result: dict[str, str] = {}
    for concept in [
        "issue_key",
        "issue_type",
        "summary",
        "created",
        "resolved",
        "status",
        "assignee",
        "priority",
        "labels",
        "description",
    ]:
        column = getattr(columns, concept)
        result[concept] = compact(row.get(column, "")) if column else ""
    return result


def collect_comments(row: dict[str, str], columns: Columns, fallback_date: str | None = None) -> list[Comment]:
    comments: list[Comment] = []
    for field in columns.comments:
        text = compact(row.get(field, ""))
        if not text:
            continue
        comments.append(Comment(field=field, text=text, date=parse_date(text) or fallback_date))
    comments.sort(key=lambda comment: (comment.date or "9999-99-99", comment.field))
    return comments


def row_date(row: JiraRow) -> str | None:
    return parse_date(row.value("created")) or parse_date(row.value("resolved"))


def source_fields_for(columns: Columns, *concepts: str, fallback: str = "row") -> list[str]:
    fields = []
    for concept in concepts:
        if concept == "comments":
            fields.extend(columns.comments)
            continue
        column = getattr(columns, concept, None)
        if column:
            fields.append(column)
    return fields or [fallback]


def row_review_context(row: JiraRow, *, max_comment_chars: int = 1200) -> dict[str, Any]:
    return {
        "source_row": row.source_row,
        "issue_key": row.value("issue_key") or None,
        "issue_type": row.value("issue_type") or None,
        "summary": row.value("summary") or None,
        "created": row.value("created") or None,
        "resolved": row.value("resolved") or None,
        "status": row.value("status") or None,
        "assignee": row.value("assignee") or None,
        "priority": row.value("priority") or None,
        "labels": row.value("labels") or None,
        "description": shorten(row.value("description"), max_comment_chars) or None,
        "comments": [
            {
                "field": comment.field,
                "date": comment.date,
                "text": shorten(comment.text, max_comment_chars),
            }
            for comment in row.comments
        ],
    }


def dedupe_fieldnames(fieldnames: list[str]) -> list[str]:
    """Make CSV header names unique while preserving Jira-style comment names.

    Jira exports can contain repeated `Comment` headers. csv.DictReader would keep
    only the last duplicate, so the loader uses csv.reader and disambiguates
    duplicates as `Comment`, `Comment.1`, `Comment.2`, ... internally.
    """
    seen: dict[str, int] = {}
    result: list[str] = []
    for index, raw_name in enumerate(fieldnames, start=1):
        name = compact(raw_name) or f"column_{index}"
        count = seen.get(name, 0)
        result.append(name if count == 0 else f"{name}.{count}")
        seen[name] = count + 1
    return result


def load_jira_csv(path: Path) -> JiraCsv:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("Input CSV has no header row.") from exc
        if not header:
            raise ValueError("Input CSV has no header row.")
        fieldnames = dedupe_fieldnames([str(name) for name in header])
        raw_rows: list[dict[str, str]] = []
        for values in reader:
            row: dict[str, str] = {}
            for idx, field in enumerate(fieldnames):
                row[field] = values[idx] if idx < len(values) else ""
            # Preserve any unexpected extra cells instead of dropping them silently.
            for extra_idx, value in enumerate(values[len(fieldnames):], start=1):
                row[f"extra_column_{extra_idx}"] = value
            raw_rows.append(row)

    columns = detect_columns(fieldnames)
    rows: list[JiraRow] = []
    generated_any = False
    for index, raw in enumerate(raw_rows, start=1):
        src_row, generated = _source_row_value(raw, index, columns)
        generated_any = generated_any or generated
        values = _concept_values(raw, columns)
        fallback_date = parse_date(values.get("created")) or parse_date(values.get("resolved"))
        rows.append(
            JiraRow(
                source_row=src_row,
                raw={str(key): compact(value) for key, value in raw.items() if key is not None},
                values=values,
                comments=collect_comments(raw, columns, fallback_date),
            )
        )

    return JiraCsv(path=path, fieldnames=fieldnames, columns=columns, rows=rows, source_rows_generated=generated_any)


def write_numbered_csv(input_csv: Path, output_csv: Path, source_row_column: str = "source_row") -> int:
    """Compatibility/debug helper. Normal workflow keeps source rows in memory."""
    with Path(input_csv).open("r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.reader(infile)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("Input CSV has no header row.") from exc
        if not header:
            raise ValueError("Input CSV has no header row.")
        normalized_header = [normalized_name(name) for name in header]
        source_idx = None
        for idx, name in enumerate(normalized_header):
            if name == normalized_name(source_row_column):
                source_idx = idx
                break
        rows = list(reader)

    output_header = list(header)
    if source_idx is None:
        output_header = [source_row_column] + output_header

    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(output_header)
        for index, values in enumerate(rows, start=1):
            row_values = list(values)
            if source_idx is None:
                writer.writerow([index] + row_values)
            else:
                while len(row_values) <= source_idx:
                    row_values.append("")
                if not compact(row_values[source_idx]):
                    row_values[source_idx] = str(index)
                writer.writerow(row_values)
    return len(rows)
