"""Preprocess song lyrics from an Excel file for interpretation/summarization.

Features:
- Reads an .xlsx file with columns: song_id, lyrics
- Removes duplicate lyric lines while preserving original order
- Preserves line-break structure
- Normalizes whitespace
- Optional lowercasing (enabled by default)
- Writes a CSV containing cleaned_lyrics and basic line statistics

Note: Implemented with the Python standard library only (no external deps).
"""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REQUIRED_COLUMNS = {"song_id", "lyrics"}


def excel_col_to_index(cell_ref: str) -> int:
    """Convert an Excel cell reference like 'AB12' to a 0-based column index."""
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch.upper()) - ord("A") + 1)
    return col - 1


def normalize_line(line: str, lowercase: bool = True) -> str:
    """Normalize a single lyric line by trimming and collapsing whitespace."""
    normalized = re.sub(r"\s+", " ", line).strip()
    if lowercase:
        normalized = normalized.lower()
    return normalized


def deduplicate_lines(lines: Iterable[str], lowercase: bool = True) -> tuple[list[str], int, int]:
    """Deduplicate lines exactly after normalization while preserving order."""
    seen: set[str] = set()
    cleaned_lines: list[str] = []

    for raw_line in lines:
        line = normalize_line(raw_line, lowercase=lowercase)

        if line == "":
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if line in seen:
            continue

        seen.add(line)
        cleaned_lines.append(line)

    if cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    num_lines = sum(1 for line in cleaned_lines if line)
    num_unique_lines = len({line for line in cleaned_lines if line})
    return cleaned_lines, num_lines, num_unique_lines


def clean_lyrics_text(lyrics: str, lowercase: bool = True) -> tuple[str, int, int]:
    """Clean one lyrics field and return cleaned text + stats."""
    lines = str(lyrics).splitlines()
    cleaned_lines, num_lines, num_unique_lines = deduplicate_lines(lines, lowercase=lowercase)
    cleaned_lyrics = "\n".join(cleaned_lines)
    return cleaned_lyrics, num_lines, num_unique_lines


def parse_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    """Read the shared string table from an XLSX archive."""
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for si in root.findall("x:si", NS):
        text_nodes = si.findall(".//x:t", NS)
        values.append("".join(node.text or "" for node in text_nodes))
    return values


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    """Extract text value from a worksheet cell element."""
    cell_type = cell.attrib.get("t")
    value_node = cell.find("x:v", NS)
    if value_node is None:
        is_node = cell.find("x:is", NS)
        if is_node is not None:
            return "".join(node.text or "" for node in is_node.findall(".//x:t", NS))
        return ""

    raw = value_node.text or ""
    if cell_type == "s":
        idx = int(raw)
        return shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
    return raw


def read_xlsx_records(input_path: Path) -> list[dict[str, str]]:
    """Read rows from the first worksheet of an XLSX as dicts keyed by header row."""
    with zipfile.ZipFile(input_path) as zf:
        shared_strings = parse_shared_strings(zf)
        sheet_xml = zf.read("xl/worksheets/sheet1.xml")

    root = ET.fromstring(sheet_xml)
    rows = root.findall(".//x:sheetData/x:row", NS)
    if not rows:
        return []

    header_cells = rows[0].findall("x:c", NS)
    headers_by_col: dict[int, str] = {}
    for cell in header_cells:
        ref = cell.attrib.get("r", "")
        col_idx = excel_col_to_index(ref)
        headers_by_col[col_idx] = cell_value(cell, shared_strings).strip()

    records: list[dict[str, str]] = []
    for row in rows[1:]:
        record: dict[str, str] = {h: "" for h in headers_by_col.values()}
        for cell in row.findall("x:c", NS):
            ref = cell.attrib.get("r", "")
            col_idx = excel_col_to_index(ref)
            header = headers_by_col.get(col_idx)
            if header is None:
                continue
            record[header] = cell_value(cell, shared_strings)
        records.append(record)

    return records


def process_records(records: list[dict[str, str]], lowercase: bool = True) -> list[dict[str, str | int]]:
    """Validate and process lyric records."""
    if not records:
        return []

    missing = REQUIRED_COLUMNS - set(records[0].keys())
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    output: list[dict[str, str | int]] = []
    for row in records:
        song_id = row.get("song_id", "")
        lyrics = row.get("lyrics", "")
        cleaned_lyrics, num_lines, num_unique_lines = clean_lyrics_text(lyrics, lowercase=lowercase)
        output.append(
            {
                "song_id": song_id,
                "lyrics": lyrics,
                "cleaned_lyrics": cleaned_lyrics,
                "num_lines": num_lines,
                "num_unique_lines": num_unique_lines,
            }
        )
    return output


def write_csv(records: list[dict[str, str | int]], output_path: Path) -> None:
    """Write processed records to CSV."""
    fieldnames = ["song_id", "lyrics", "cleaned_lyrics", "num_lines", "num_unique_lines"]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def resolve_default_input(path_str: str) -> Path:
    requested = Path(path_str)
    if requested.exists():
        return requested

    fallback_candidates = [Path("songs lyrics.xlsx"), Path("song lyrics.xlsx")]
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate

    return requested


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess song lyrics for interpretation/summarization.")
    parser.add_argument("--input", default="songs lyrics.xlsx", help="Path to input XLSX file.")
    parser.add_argument("--output", default="cleaned_song_lyrics.csv", help="Path to output CSV file.")
    parser.add_argument("--no-lowercase", action="store_true", help="Disable lowercasing during normalization.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = resolve_default_input(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    records = read_xlsx_records(input_path)
    processed = process_records(records, lowercase=not args.no_lowercase)
    write_csv(processed, output_path)

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows processed: {len(processed)}")


if __name__ == "__main__":
    main()
