#!/usr/bin/env python3
"""Validate concrete-input coverage and local links in a biological-prior README."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse


INPUT_HEADING = re.compile(r"^### Input(?: file)?:\s+(.+?)\s*$", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
EXPLICIT_ANCHOR = re.compile(r"<(?:a|span)\s+(?:[^>]*?\s)?(?:id|name)=[\"']([^\"']+)[\"']", re.I)
FENCED_CODE = re.compile(r"^(```|~~~).*?^\1\s*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"(?<!`)`[^`\n]+`(?!`)")


def normalize_heading(value: str) -> str:
    value = value.strip().strip("`")
    match = re.fullmatch(r"\[[^\]]+\]\(([^)]+)\)", value)
    return match.group(1) if match else value


def without_fenced_code(text: str) -> str:
    return FENCED_CODE.sub("", text)


def prose_only(text: str) -> str:
    return INLINE_CODE.sub("", without_fenced_code(text))


def read_inventory(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def repository_root(readme: Path) -> Path:
    for candidate in (readme.parent, *readme.parents):
        if (candidate / ".git").exists():
            return candidate.resolve()
    return readme.parent.resolve()


def markdown_anchors(path: Path) -> set[str]:
    text = path.read_text(errors="replace")
    anchors = set(EXPLICIT_ANCHOR.findall(text))
    counts: Counter[str] = Counter()
    for heading in HEADING.findall(text):
        label = re.sub(r"<[^>]+>", "", heading)
        label = re.sub(r"[`*_~]", "", label).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", label, flags=re.UNICODE)
        slug = re.sub(r"[\s\-]+", "-", slug).strip("-")
        suffix = counts[slug]
        anchors.add(slug if suffix == 0 else f"{slug}-{suffix}")
        counts[slug] += 1
    return anchors


def local_link_failures(
    readme: Path, text: str, root: Path
) -> tuple[int, int, list[str], list[str]]:
    local_count = 0
    external_count = 0
    failures: list[str] = []
    fragment_failures: list[str] = []

    for raw in MARKDOWN_LINK.findall(text):
        target = raw.strip().split(maxsplit=1)[0].strip("<>")
        parsed = urlparse(target)
        if parsed.scheme or target.startswith("mailto:"):
            external_count += 1
            continue
        local_count += 1
        resolved = (
            (readme.parent / unquote(parsed.path)).resolve()
            if parsed.path
            else readme
        )
        try:
            resolved.relative_to(root)
        except ValueError:
            failures.append(f"OUTSIDE_SCOPE {target} -> {resolved}")
            continue
        if not resolved.exists():
            failures.append(f"MISSING {target} -> {resolved}")
            continue
        if parsed.fragment and resolved.suffix.lower() in {".md", ".markdown"}:
            fragment = unquote(parsed.fragment)
            if fragment not in markdown_anchors(resolved):
                fragment_failures.append(f"UNRESOLVED_FRAGMENT {target}")

    return local_count, external_count, failures, fragment_failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("readme", type=Path)
    parser.add_argument(
        "--expected-inputs",
        required=True,
        type=Path,
        help="newline-delimited concrete build-time input identities",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        help="repository boundary; defaults to the nearest ancestor containing .git",
    )
    args = parser.parse_args()

    readme = args.readme.resolve()
    root = args.repository_root.resolve() if args.repository_root else repository_root(readme)
    text = readme.read_text()
    documented = [
        normalize_heading(value)
        for value in INPUT_HEADING.findall(without_fenced_code(text))
    ]
    expected = read_inventory(args.expected_inputs)
    duplicates = sorted(name for name, count in Counter(documented).items() if count > 1)
    missing = sorted(set(expected) - set(documented))
    extra = sorted(set(documented) - set(expected))

    link_text = prose_only(text)
    links = MARKDOWN_LINK.findall(link_text)
    local_count, external_count, link_failures, fragment_failures = local_link_failures(
        readme, link_text, root
    )

    print(f"documented_input_sections={len(documented)}")
    print(f"expected_build_inputs={len(expected)}")
    print(f"missing_inputs={len(missing)}")
    print(f"extra_inputs={len(extra)}")
    print(f"duplicate_input_sections={len(duplicates)}")
    print(f"markdown_links={len(links)}")
    print(f"local_links={local_count}")
    print(f"external_links={external_count}")
    print(f"missing_local_targets={len(link_failures)}")
    print(f"unresolved_local_fragments={len(fragment_failures)}")

    for label, values in (
        ("MISSING_INPUT", missing),
        ("EXTRA_INPUT", extra),
        ("DUPLICATE_INPUT", duplicates),
    ):
        for value in values:
            print(f"{label} {value}")
    for failure in link_failures:
        print(failure)
    for failure in fragment_failures:
        print(failure)

    failed = bool(missing or extra or duplicates or link_failures or fragment_failures)
    print(f"structural_contract_status={'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
