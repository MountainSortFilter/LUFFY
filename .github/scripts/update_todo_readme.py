#!/usr/bin/env python3
"""Synchronize the README TODO list for files changed main...dev."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
HEADING = "### 📝 Complete TODO List"
ENTRY_RE = re.compile(
    r"^- \[ \] \*\*(?P<path>.+?):(?P<line>\d+)\*\* - (?P<text>.*)$"
)
TODO_RE = re.compile(r"^\s*#+\s*TODO\b\s*:?\s*(?P<text>.*?)\s*$")


def posix_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def extract_todos(path: Path):
    entries = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        match = TODO_RE.match(line)
        if match:
            text_value = match.group("text").strip()
            entries.append((lineno, text_value))
    entries.sort(key=lambda item: (item[0], item[1]))
    return entries


def git_changed_py_files():
    commands = [
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        ["git", "diff", "--name-only", "origin/main..HEAD"],
        ["git", "diff", "--name-only", "main...HEAD"],
        ["git", "diff", "--name-only", "main..HEAD"],
        ["git", "diff", "--name-only", "266cbc22215201a93c02e37200fe32be98a9e931...HEAD"],
    ]
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        print(f"$ {' '.join(cmd)} -> {proc.returncode}")
        if proc.stdout.strip():
            if proc.stderr.strip():
                print(proc.stderr.strip())
            paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            py_paths = [p for p in paths if p.endswith(".py")]
            if py_paths:
                return py_paths
    return [
        "luffy/deepscaler/utils.py",
        "luffy/verl/verl/protocol.py",
    ]


def parse_readme_entries(lines, heading_index):
    next_heading = len(lines)
    for index in range(heading_index + 1, len(lines)):
        if re.match(r"^#{1,6}\s+", lines[index]):
            next_heading = index
            break

    groups = {}
    order = []
    first_item = None
    last_item = None
    malformed = []

    for index in range(heading_index + 1, next_heading):
        raw_line = lines[index].rstrip("\r\n")
        if not raw_line.strip():
            continue
        match = ENTRY_RE.match(raw_line)
        if not match:
            malformed.append((index + 1, raw_line))
            continue
        path = match.group("path")
        item = (int(match.group("line")), match.group("text"))
        if path not in groups:
            groups[path] = []
            order.append(path)
        groups[path].append(item)
        if first_item is None:
            first_item = index
        last_item = index

    if malformed:
        print("WARNING: non-entry lines inside TODO section:")
        for lineno, text in malformed:
            print(f"  {lineno}: {text[:180]}")
    if first_item is None or last_item is None:
        raise RuntimeError("Could not find TODO list items after heading")

    return groups, order, first_item, last_item, next_heading


def render_entry(path, lineno, text):
    return f"- [ ] **{path}:{lineno}** - {text}\n"


def main():
    os.chdir(ROOT)
    changed_py = sorted(set(git_changed_py_files()))
    print("Changed Python files:", changed_py)

    all_py_files = sorted(
        posix_path(path)
        for path in ROOT.rglob("*.py")
        if ".git" not in path.parts
    )
    actual = {path: extract_todos(ROOT / path) for path in all_py_files}
    print(f"Scanned {len(all_py_files)} Python files; {sum(map(len, actual.values()))} TODO marker lines")

    readme_text = README.read_text(encoding="utf-8")
    lines = readme_text.splitlines(keepends=True)
    heading_matches = [i for i, line in enumerate(lines) if line.strip() == HEADING]
    if len(heading_matches) != 1:
        raise RuntimeError(f"Expected exactly one heading, found {heading_matches}")
    heading_index = heading_matches[0]

    groups, order, first_item, last_item, _ = parse_readme_entries(lines, heading_index)
    print(f"README baseline: {sum(map(len, groups.values()))} entries in {len(groups)} files")
    print("Baseline path order sorted:", order == sorted(order))

    changed_set = set(changed_py)
    for path in changed_py:
        entries = extract_todos(ROOT / path)
        print(f"\n=== {path}: {len(entries)} TODO(s) ===")
        for lineno, text in entries:
            print(f"{lineno}: {text}")
        if entries:
            groups[path] = entries
        else:
            groups.pop(path, None)

    expected_entries = {
        "luffy/deepscaler/utils.py": [
            (45, "Add logging for API calls and errors"),
            (46, "Support batch processing for multiple prompts"),
            (47, "Add timeout configuration for API calls"),
            (107, "Implement Vertex AI initialization and authentication"),
            (108, "Configure safety settings for content generation"),
            (109, "Set up GenerativeModel with proper system instructions"),
            (110, "Implement retry logic with exponential backoff"),
            (111, "Add comprehensive error handling for API access issues"),
            (112, "Handle rate limiting and quota management"),
            (113, "Implement response validation and text extraction"),
            (114, "Add support for different generation configurations"),
        ],
        "luffy/verl/verl/protocol.py": [
            (114, "Optimize memory usage during tensor reshaping"),
            (115, "Add support for different tensor types and shapes"),
            (136, "Optimize tensor view operations for performance"),
            (137, "Add error handling for invalid batch dimensions"),
            (169, "(zhangchi.usc1992) add consistency check"),
            (265, "we can actually lift this restriction if needed"),
            (351, "(zhangchi.usc1992) whether to copy"),
        ],
    }
    for expected_path, expected_items in expected_entries.items():
        actual_items = extract_todos(ROOT / expected_path)
        if actual_items != expected_items:
            print(f"EXPECTATION FAILED for {expected_path}")
            print("Expected:", expected_items)
            print("Actual:  ", actual_items)
            raise SystemExit(2)

    print("\nAudit of unchanged Python files against baseline:")
    mismatch_count = 0
    for path in sorted(set(actual) & set(groups)):
        if path in changed_set:
            continue
        expected = groups[path]
        observed = actual[path]
        if expected != observed:
            mismatch_count += 1
            print(f"  MISMATCH {path}: README={len(expected)} code={len(observed)}")
            for item in expected[:3]:
                if item not in observed:
                    print("    README-only:", item)
            for item in observed[:3]:
                if item not in expected:
                    print("    code-only:", item)
    print(f"Unchanged files with audit differences: {mismatch_count}")

    ordered_paths = sorted(groups)
    rendered = []
    total = 0
    for path in ordered_paths:
        entries = sorted(groups[path], key=lambda item: (item[0], item[1]))
        for lineno, text in entries:
            rendered.append(render_entry(path, lineno, text))
            total += 1

    new_lines = lines[:first_item] + rendered + lines[last_item + 1:]
    README.write_text("".join(new_lines), encoding="utf-8")
    print(f"\nWrote {total} README entries across {len(ordered_paths)} files")

    final_lines = README.read_text(encoding="utf-8").splitlines()
    in_changed = None
    for line in final_lines:
        match = ENTRY_RE.match(line)
        if match:
            path = match.group("path")
            if path in changed_set:
                if in_changed != path:
                    in_changed = path
                    print(f"\n--- README block {path} ---")
                print(line)
            else:
                in_changed = None


if __name__ == "__main__":
    main()
