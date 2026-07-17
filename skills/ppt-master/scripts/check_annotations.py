#!/usr/bin/env python3
"""
PPT Master - SVG Annotation Checker

Scans SVG files for edit annotations (data-edit-target / data-edit-annotation attributes)
and prints a human-readable summary. Used by AI agents to discover pending annotations.

Usage:
    python3 scripts/check_annotations.py <project_dir>
    python3 scripts/check_annotations.py <svg_file>

Examples:
    python3 scripts/check_annotations.py projects/my-project
    python3 scripts/check_annotations.py projects/my-project/svg_output/slide_01.svg

Dependencies:
    None (only uses standard library)
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from console_encoding import configure_utf8_stdio

configure_utf8_stdio()


def scan_svg_file(svg_path: Path) -> tuple[list[dict], str | None]:
    """Scan a single SVG file for element and page annotations.

    Returns (element_annotations, page_annotation).
    """
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return [], None

    root = tree.getroot()
    annotations = []

    # Element-level annotations (data-edit-target="true")
    for elem in root.iter():
        if elem.get('data-edit-target') == 'true':
            tag = elem.tag
            if '}' in tag:
                tag = tag.split('}', 1)[1]

            content_preview = ''
            if tag == 'text' and elem.text:
                content_preview = elem.text.strip()[:50]

            annotations.append({
                'element_id': elem.get('id', '(no id)'),
                'tag': tag,
                'annotation': elem.get('data-edit-annotation', ''),
                'content_preview': content_preview,
            })

    # Page-level annotation (data-edit-target="page" on root SVG)
    page_annotation = None
    if root.get('data-edit-target') == 'page':
        page_annotation = root.get('data-edit-annotation') or None

    return annotations, page_annotation


def scan_directory(dir_path: Path) -> tuple[dict[str, list[dict]], dict[str, str], list[dict]]:
    """Scan all SVG files in svg_output/ for element and page annotations.

    Returns (element_annotations_by_file, page_annotations_by_file, global_annotations).
    """
    svg_dir = dir_path / 'svg_output'
    if not svg_dir.exists():
        return {}, {}, []

    elem_results = {}
    page_results = {}
    for svg_file in sorted(svg_dir.glob('*.svg')):
        annotations, page_annotation = scan_svg_file(svg_file)
        if annotations:
            elem_results[svg_file.name] = annotations
        if page_annotation:
            page_results[svg_file.name] = page_annotation

    # Global annotations from live_preview/global_annotations.json
    global_path = dir_path / 'live_preview' / 'global_annotations.json'
    global_annotations = []
    if global_path.is_file():
        try:
            with open(global_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if isinstance(data, list):
                global_annotations = data
        except (OSError, json.JSONDecodeError):
            pass

    return elem_results, page_results, global_annotations


def print_results(elem_results: dict[str, list[dict]], page_results: dict[str, str], global_annotations: list[dict]) -> None:
    """Print annotation results in human-readable format."""
    global_count = len(global_annotations)
    page_count = len(page_results)
    elem_total = sum(len(anns) for anns in elem_results.values())
    total = elem_total + page_count + global_count

    if total == 0:
        print("[OK] No annotations found.")
        return

    print(f"Found {total} annotation(s): {elem_total} element, {page_count} page, {global_count} global\n")

    # Global annotations first
    if global_annotations:
        print("═══ Global Annotations (apply to ALL slides) ═══")
        for i, entry in enumerate(global_annotations):
            idx = entry.get('index', i)
            print(f"  [G{idx}] {entry.get('annotation', '')}")
        print()

    # Page annotations
    if page_results:
        print("═══ Page-Level Annotations ═══")
        for filename, annotation in page_results.items():
            print(f"  {filename}")
            print(f"    → {annotation}")
        print()

    # Element annotations
    if elem_results:
        print("═══ Element Annotations ═══")
        for filename, annotations in elem_results.items():
            print(f"  {filename}")
            for i, ann in enumerate(annotations, 1):
                content = f' "{ann["content_preview"]}"' if ann['content_preview'] else ''
                print(f"    [{i}] <{ann['tag']} id=\"{ann['element_id']}\">{content}")
                print(f"        → {ann['annotation']}")
            print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Check SVG files for edit annotations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('path', help='Project directory or single SVG file path')
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    if target.is_file() and target.suffix == '.svg':
        annotations, page_annotation = scan_svg_file(target)
        elem_results = {target.name: annotations} if annotations else {}
        page_results = {target.name: page_annotation} if page_annotation else {}
        global_annotations = []
    elif target.is_dir():
        elem_results, page_results, global_annotations = scan_directory(target)
    else:
        print(f"Error: Expected a project directory or .svg file, got: {target}", file=sys.stderr)
        return 1

    print_results(elem_results, page_results, global_annotations)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
