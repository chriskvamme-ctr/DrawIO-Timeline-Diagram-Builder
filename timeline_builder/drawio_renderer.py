"""Deterministic draw.io and SVG rendering from validated timeline JSON."""
from __future__ import annotations

import json
import re
import textwrap
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from . import __version__
from .validation import validate_render_preflight

LANE_ORDER = ["incident", "date", "component_replacement", "other"]
LANE_LABELS = {
    "incident": "INCIDENT",
    "date": "DATE",
    "component_replacement": "COMPONENT REPLACEMENT",
    "other": "OTHER",
}
LANE_STYLES = {
    "incident": "fillColor=#d9d2e9;strokeColor=#8e7cc3;fontColor=#111111;rounded=1;arcSize=10;whiteSpace=wrap;html=1;spacing=8;overflow=hidden;shadow=0;",
    "date": "fillColor=#d9ead3;strokeColor=#93c47d;fontStyle=1;fontSize=15;rounded=1;arcSize=10;whiteSpace=wrap;html=1;overflow=hidden;shadow=0;",
    "component_replacement": "fillColor=#fff2cc;strokeColor=#f1c232;fontColor=#111111;rounded=1;arcSize=10;whiteSpace=wrap;html=1;spacing=8;overflow=hidden;shadow=0;",
    "other": "fillColor=#eeeeee;strokeColor=#999999;fontColor=#111111;rounded=1;arcSize=10;whiteSpace=wrap;html=1;spacing=8;overflow=hidden;shadow=0;",
}
BACKGROUND_STYLE = "fillColor=#fafafa;strokeColor=#dddddd;"
LANE_TITLE_STYLE = "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;rotation=270;fontStyle=1;fontSize=12;fontColor=#333333;"
LANE_BG_STYLES = {
    "incident": "fillColor=#f3effa;strokeColor=#d5cce8;rounded=0;",
    "date": "fillColor=#f0f7ed;strokeColor=#d6ead0;rounded=0;",
    "component_replacement": "fillColor=#fff8e5;strokeColor=#f6e4a6;rounded=0;",
    "other": "fillColor=#f7f7f7;strokeColor=#e0e0e0;rounded=0;",
}
CONNECTOR_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeColor=#999999;endArrow=none;"
TITLE_STYLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=20;"

LEFT_MARGIN = 120
TOP_MARGIN = 48
LANE_LABEL_WIDTH = 60
CONTENT_LEFT = LEFT_MARGIN + LANE_LABEL_WIDTH
DATE_X_GAP = 285
DATE_CARD_WIDTH = 180
DATE_CARD_HEIGHT = 50
EVENT_CARD_WIDTH = 240
EVENT_CARD_HEIGHT = 96
LANE_HEIGHT = 170
CARD_VERTICAL_GAP = 14
DATE_TOP_OFFSET = 48
EVENT_TOP_OFFSET = 34
BOTTOM_MARGIN = 60
RIGHT_MARGIN = 90


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def pretty_date_label(value: str) -> str:
    return parse_date(value).strftime("%b %d, %Y").upper()


def truncate_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _list_label(values: Any, *, prefix: str = "", max_items: int = 2) -> str:
    if not isinstance(values, list):
        return ""
    cleaned = [str(value).strip() for value in values if str(value or "").strip()]
    if not cleaned:
        return ""
    shown = cleaned[:max_items]
    label = ", ".join(f"{prefix}{value}" for value in shown)
    if len(cleaned) > max_items:
        label += f" +{len(cleaned) - max_items}"
    return label


def _source_label(event: dict[str, Any]) -> str:
    rows = _list_label(event.get("source_rows"), prefix="R", max_items=2)
    fields = _list_label(event.get("source_fields"), max_items=1)
    if rows and fields:
        return f"Src: {rows} · {fields}"
    if rows:
        return f"Src: {rows}"
    if fields:
        return f"Src: {fields}"
    return ""


ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


def _ticket_value(event: dict[str, Any]) -> str:
    """Return the best available ticket key for visual display.

    AI-created patch events are allowed to carry a null issue_key, so the renderer
    also falls back to obvious Jira keys embedded in title/details/event_id.
    """
    for key in ("issue_key", "ticket", "ticket_key"):
        value = str(event.get(key) or "").strip()
        if not value or value.lower() in {"none", "null", "n/a"}:
            continue
        if value.lower().startswith("ticket:"):
            value = value.split(":", 1)[1].strip()
        if value:
            return value

    for key in ("title", "details", "event_id"):
        match = ISSUE_KEY_RE.search(str(event.get(key) or ""))
        if match:
            return match.group(0)
    return ""


def _ticket_label(event: dict[str, Any]) -> str:
    issue_key = _ticket_value(event)
    return f"Ticket: {issue_key}" if issue_key else ""


def _extract_datetime(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""

    # Jira style: 04/Feb/22 11:13 AM; keep only the timestamp, not author/account text.
    import re

    match = re.search(r"\b(\d{1,2}/[A-Za-z]{3}/\d{2,4})\s+(\d{1,2}:\d{2})(?:\s*([AP]M))?\b", text, re.IGNORECASE)
    if match:
        suffix = f" {match.group(3).upper()}" if match.group(3) else ""
        return f"{match.group(1)} {match.group(2)}{suffix}"

    # ISO-like timestamp: 2026-02-04 11:13 or 2026-02-04T11:13.
    match = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2})[T\s]+(\d{1,2}:\d{2})", text)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    # Date-only Jira style is still better than showing no source date.
    match = re.search(r"\b(\d{1,2}/[A-Za-z]{3}/\d{2,4})\b", text)
    if match:
        return match.group(1)

    return ""


def _event_datetime_label(event: dict[str, Any]) -> str:
    for key in ("source_datetime", "display_datetime", "created", "timestamp"):
        found = _extract_datetime(event.get(key))
        if found:
            return found
    for key in ("details", "title"):
        found = _extract_datetime(event.get(key))
        if found:
            return found
    date_value = str(event.get("date") or "")
    if date_value:
        try:
            return parse_date(date_value).strftime("%d/%b/%y")
        except ValueError:
            return date_value
    return ""


def _wrap_display_text(value: Any, *, width: int, max_lines: int) -> list[str]:
    """Wrap display text before it reaches draw.io.

    draw.io does not always wrap HTML labels consistently after import, especially
    when a label contains multiple div/font elements. Manual line breaks keep long
    titles inside the card instead of letting them visually spill over the edge.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return []

    lines: list[str] = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(
            paragraph,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=True,
            drop_whitespace=True,
        ) or [paragraph]
        lines.extend(wrapped)

    if len(lines) <= max_lines:
        return lines

    kept = lines[:max_lines]
    remainder = " ".join(lines[max_lines - 1 :])
    kept[-1] = truncate_text(remainder, width)
    return kept


def _card_display_parts(event: dict[str, Any]) -> dict[str, list[str] | str]:
    title_lines = _wrap_display_text(event.get("title"), width=30, max_lines=2) or ["Untitled event"]
    ticket = truncate_text(_ticket_label(event), 42)
    source = truncate_text(_source_label(event), 42)
    return {"title_lines": title_lines, "ticket": ticket, "source": source}


def card_visible_lines(event: dict[str, Any]) -> list[str]:
    """Only the compact visual label. Full source text remains in cell metadata/JSON."""
    parts = _card_display_parts(event)
    lines = list(parts["title_lines"])
    for key in ("ticket", "source"):
        value = str(parts[key] or "")
        if value:
            lines.append(value)
    return lines


def html_card_text(event: dict[str, Any]) -> str:
    """Compact visible card: wrapped title, ticket, and compact source reference only."""
    parts = _card_display_parts(event)
    title_lines = [escape(line) for line in parts["title_lines"]]
    title_html = "<br/>".join(title_lines)
    html_parts = [
        "<div style='white-space:normal;word-wrap:break-word;line-height:1.1;'>"
        f"<b>{title_html}</b></div>"
    ]
    ticket = str(parts["ticket"] or "")
    source = str(parts["source"] or "")
    if ticket:
        html_parts.append(f"<div><font color='#444444' style='font-size:11px'>{escape(ticket)}</font></div>")
    if source:
        html_parts.append(f"<div><font color='#777777' style='font-size:9px'>{escape(source)}</font></div>")
    return "".join(html_parts)


def cell_metadata(event: dict[str, Any]) -> dict[str, str]:
    return {
        "eventId": str(event.get("event_id") or ""),
        "sourceRows": ",".join(str(x) for x in event.get("source_rows", [])),
        "sourceFields": ",".join(str(x) for x in event.get("source_fields", [])),
        "issueKey": str(event.get("issue_key") or ""),
        "component": str(event.get("component") or ""),
        "eventDate": str(event.get("date") or ""),
        "sourceDateTime": _event_datetime_label(event),
        "details": str(event.get("details") or ""),
    }

def add_cell(
    parent: ET.Element,
    cell_id: int,
    value: str,
    style: str,
    *,
    vertex: bool = False,
    edge: bool = False,
    parent_id: str = "1",
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
    source: int | None = None,
    target: int | None = None,
    extra_attrib: dict[str, str] | None = None,
) -> ET.Element:
    attrib: dict[str, str] = {"id": str(cell_id), "value": value, "style": style, "parent": str(parent_id)}
    if extra_attrib:
        attrib.update({key: str(val) for key, val in extra_attrib.items() if val is not None})
    if vertex:
        attrib["vertex"] = "1"
    if edge:
        attrib["edge"] = "1"
    if source is not None:
        attrib["source"] = str(source)
    if target is not None:
        attrib["target"] = str(target)

    cell = ET.SubElement(parent, "mxCell", attrib)
    if vertex or edge:
        geo_attrib = {"as": "geometry"}
        if edge:
            geo_attrib["relative"] = "1"
        else:
            geo_attrib.update({"x": str(x), "y": str(y), "width": str(width), "height": str(height)})
        ET.SubElement(cell, "mxGeometry", geo_attrib)
    return cell


def lane_heights_for(events_by_lane_date: dict[tuple[str, str], list[dict[str, Any]]], dates: list[str]) -> dict[str, int]:
    heights = {"date": LANE_HEIGHT}
    for lane in ["incident", "component_replacement", "other"]:
        max_stack = max((len(events_by_lane_date.get((lane, date), [])) for date in dates), default=0)
        needed = max(1, max_stack)
        heights[lane] = max(LANE_HEIGHT, 48 + needed * EVENT_CARD_HEIGHT + (needed - 1) * CARD_VERTICAL_GAP + 24)
    return heights


def build_document(data: dict[str, Any]) -> ET.ElementTree:
    errors = validate_render_preflight(data)
    if errors:
        raise ValueError("Timeline JSON is not renderable:\n" + "\n".join(f"- {error}" for error in errors))

    events = list(data.get("events", []))
    dates = sorted({event["date"] for event in events})

    events_by_lane_date: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_lane_date[(event["lane"], event["date"])].append(event)

    lane_heights = lane_heights_for(events_by_lane_date, dates)
    lane_y: dict[str, int] = {}
    current_y = TOP_MARGIN
    for lane in LANE_ORDER:
        lane_y[lane] = current_y
        current_y += lane_heights[lane]

    total_height = current_y + BOTTOM_MARGIN
    total_width = CONTENT_LEFT + max(1, len(dates)) * DATE_X_GAP + RIGHT_MARGIN

    mxfile = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "modified": datetime.now(timezone.utc).isoformat(),
            "agent": f"jira-drawio-timeline-builder/{__version__}",
            "version": __version__,
            "type": "device",
        },
    )
    diagram = ET.SubElement(mxfile, "diagram", {"id": "timeline-page", "name": str(data.get("unit_id", "Timeline"))})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1434",
            "dy": "794",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(total_width),
            "pageHeight": str(total_height),
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    next_id = 2

    # draw.io/mxGraph z-order is controlled by cell order in the XML root:
    # later cells render in front of earlier cells. Keep connectors behind all
    # cards by collecting cells into buckets, then appending them in one place.
    background_cells = ET.Element("cell-bucket")
    lane_cells = ET.Element("cell-bucket")
    edge_cells = ET.Element("cell-bucket")
    date_card_cells = ET.Element("cell-bucket")
    event_card_cells = ET.Element("cell-bucket")

    add_cell(background_cells, next_id, "", BACKGROUND_STYLE, vertex=True, x=0, y=0, width=total_width, height=total_height)
    next_id += 1

    title = escape(f"{data.get('unit_id', 'UNKNOWN UNIT')} - INCIDENT TIMELINE")
    start = escape(str(data.get("date_range", {}).get("start", "")))
    end = escape(str(data.get("date_range", {}).get("end", "")))
    add_cell(background_cells, next_id, f"<b>{title}</b><div>{start} to {end}</div>", TITLE_STYLE, vertex=True, x=CONTENT_LEFT, y=8, width=700, height=34)
    next_id += 1

    for lane in LANE_ORDER:
        y = lane_y[lane]
        height = lane_heights[lane]
        add_cell(lane_cells, next_id, "", LANE_BG_STYLES[lane], vertex=True, x=CONTENT_LEFT, y=y, width=total_width - CONTENT_LEFT - RIGHT_MARGIN / 2, height=height)
        next_id += 1
        add_cell(lane_cells, next_id, escape(LANE_LABELS[lane]), LANE_TITLE_STYLE, vertex=True, x=LEFT_MARGIN, y=y, width=LANE_LABEL_WIDTH, height=height)
        next_id += 1

    date_marker_ids: dict[str, int] = {}
    for index, date_value in enumerate(dates):
        x = CONTENT_LEFT + index * DATE_X_GAP + 24
        y = lane_y["date"] + DATE_TOP_OFFSET
        date_marker_ids[date_value] = next_id
        add_cell(date_card_cells, next_id, escape(pretty_date_label(date_value)), LANE_STYLES["date"], vertex=True, x=x, y=y, width=DATE_CARD_WIDTH, height=DATE_CARD_HEIGHT)
        next_id += 1

    for lane in ["incident", "component_replacement", "other"]:
        for index, date_value in enumerate(dates):
            day_events = events_by_lane_date.get((lane, date_value), [])
            if not day_events:
                continue
            x = CONTENT_LEFT + index * DATE_X_GAP + 18
            base_y = lane_y[lane] + EVENT_TOP_OFFSET
            for stack_index, event in enumerate(day_events):
                y = base_y + stack_index * (EVENT_CARD_HEIGHT + CARD_VERTICAL_GAP)
                event_cell_id = next_id
                add_cell(event_card_cells, next_id, html_card_text(event), LANE_STYLES[lane], vertex=True, x=x, y=y, width=EVENT_CARD_WIDTH, height=EVENT_CARD_HEIGHT, extra_attrib=cell_metadata(event))
                next_id += 1
                add_cell(edge_cells, next_id, "", CONNECTOR_STYLE, edge=True, source=event_cell_id, target=date_marker_ids[date_value])
                next_id += 1

    for bucket in (background_cells, lane_cells, edge_cells, date_card_cells, event_card_cells):
        for cell in list(bucket):
            root.append(cell)

    return ET.ElementTree(mxfile)


def render_data(data: dict[str, Any], output_drawio: Path) -> None:
    tree = build_document(data)
    output = Path(output_drawio)
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output, encoding="utf-8", xml_declaration=True)


def render(input_json: Path, output_drawio: Path) -> None:
    with Path(input_json).open("r", encoding="utf-8") as file:
        data = json.load(file)
    render_data(data, output_drawio)


def render_svg_data(data: dict[str, Any], output_svg: Path) -> None:
    """Generate a simple dependency-free SVG preview from timeline JSON."""
    errors = validate_render_preflight(data)
    if errors:
        raise ValueError("Timeline JSON is not renderable:\n" + "\n".join(f"- {error}" for error in errors))

    events = list(data.get("events", []))
    dates = sorted({event["date"] for event in events})
    events_by_lane_date: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_lane_date[(event["lane"], event["date"])].append(event)
    lane_heights = lane_heights_for(events_by_lane_date, dates)
    lane_y: dict[str, int] = {}
    current_y = TOP_MARGIN
    for lane in LANE_ORDER:
        lane_y[lane] = current_y
        current_y += lane_heights[lane]
    total_height = current_y + BOTTOM_MARGIN
    total_width = CONTENT_LEFT + max(1, len(dates)) * DATE_X_GAP + RIGHT_MARGIN

    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": str(total_width), "height": str(total_height), "viewBox": f"0 0 {total_width} {total_height}"})
    ET.SubElement(root, "rect", {"x": "0", "y": "0", "width": str(total_width), "height": str(total_height), "fill": "#f5f5f5"})
    title = f"{data.get('unit_id', 'UNKNOWN UNIT')} - INCIDENT TIMELINE"
    ET.SubElement(root, "text", {"x": str(CONTENT_LEFT), "y": "26", "font-size": "20", "font-weight": "700"}).text = title
    ET.SubElement(root, "text", {"x": str(CONTENT_LEFT), "y": "43", "font-size": "12", "fill": "#555"}).text = f"{data.get('date_range', {}).get('start', '')} to {data.get('date_range', {}).get('end', '')}"

    fills = {"incident": "#d9d2e9", "date": "#d9ead3", "component_replacement": "#fff2cc", "other": "#eeeeee"}
    strokes = {"incident": "#8e7cc3", "date": "#93c47d", "component_replacement": "#f1c232", "other": "#999999"}
    lane_fills = {"incident": "#f3effa", "date": "#f0f7ed", "component_replacement": "#fff8e5", "other": "#f7f7f7"}
    lane_strokes = {"incident": "#d5cce8", "date": "#d6ead0", "component_replacement": "#f6e4a6", "other": "#e0e0e0"}
    for lane in LANE_ORDER:
        y = lane_y[lane]
        height = lane_heights[lane]
        ET.SubElement(root, "rect", {"x": str(CONTENT_LEFT), "y": str(y), "width": str(total_width - CONTENT_LEFT - RIGHT_MARGIN / 2), "height": str(height), "fill": lane_fills[lane], "stroke": lane_strokes[lane]})
        ET.SubElement(root, "text", {"x": str(LEFT_MARGIN + 8), "y": str(y + 24), "font-size": "12", "font-weight": "700"}).text = LANE_LABELS[lane]

    date_positions: dict[str, tuple[int, int]] = {}
    for index, date_value in enumerate(dates):
        x = CONTENT_LEFT + index * DATE_X_GAP + 24
        y = lane_y["date"] + DATE_TOP_OFFSET
        date_positions[date_value] = (x + DATE_CARD_WIDTH // 2, y + DATE_CARD_HEIGHT // 2)
        _svg_card(root, x, y, DATE_CARD_WIDTH, DATE_CARD_HEIGHT, pretty_date_label(date_value), "", fills["date"], strokes["date"], bold=True)

    for lane in ["incident", "component_replacement", "other"]:
        for index, date_value in enumerate(dates):
            day_events = events_by_lane_date.get((lane, date_value), [])
            x = CONTENT_LEFT + index * DATE_X_GAP + 18
            base_y = lane_y[lane] + EVENT_TOP_OFFSET
            for stack_index, event in enumerate(day_events):
                y = base_y + stack_index * (EVENT_CARD_HEIGHT + CARD_VERTICAL_GAP)
                center = date_positions[date_value]
                ET.SubElement(root, "line", {"x1": str(x + EVENT_CARD_WIDTH // 2), "y1": str(y + EVENT_CARD_HEIGHT), "x2": str(center[0]), "y2": str(center[1]), "stroke": "#999999", "stroke-width": "1"})
                title_count = len(_card_display_parts(event)["title_lines"])
                _svg_card_lines(root, x, y, EVENT_CARD_WIDTH, EVENT_CARD_HEIGHT, card_visible_lines(event), fills[lane], strokes[lane], title_line_count=title_count)

    output = Path(output_svg)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def _svg_card(root: ET.Element, x: int, y: int, width: int, height: int, title: str, details: str, fill: str, stroke: str, *, bold: bool = False) -> None:
    ET.SubElement(root, "rect", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "rx": "8", "ry": "8", "fill": fill, "stroke": stroke})
    ET.SubElement(root, "text", {"x": str(x + 10), "y": str(y + 23), "font-size": "12", "font-weight": "700" if bold else "400"}).text = title
    if details:
        ET.SubElement(root, "text", {"x": str(x + 10), "y": str(y + 45), "font-size": "10", "fill": "#555"}).text = details


def _svg_card_lines(
    root: ET.Element,
    x: int,
    y: int,
    width: int,
    height: int,
    lines: list[str],
    fill: str,
    stroke: str,
    *,
    title_line_count: int = 1,
) -> None:
    ET.SubElement(root, "rect", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "rx": "8", "ry": "8", "fill": fill, "stroke": stroke})
    cursor = y + 18
    for index, line in enumerate(lines[:4]):
        is_title = index < title_line_count
        attrs = {
            "x": str(x + 10),
            "y": str(cursor),
            "font-size": "12" if is_title else ("11" if line.startswith("Ticket:") else "9"),
            "fill": "#111" if is_title else "#555",
        }
        if is_title:
            attrs["font-weight"] = "700"
        ET.SubElement(root, "text", attrs).text = line
        cursor += 14 if is_title else 16
        if index + 1 == title_line_count:
            cursor += 2


def render_svg(input_json: Path, output_svg: Path) -> None:
    with Path(input_json).open("r", encoding="utf-8") as file:
        data = json.load(file)
    render_svg_data(data, output_svg)
