from __future__ import annotations

import argparse
import sys
from pathlib import Path


def iter_python_files(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in targets:
        path = Path(raw)
        if not path.exists():
            continue
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
    # Preserve insertion order while removing duplicates.
    seen: set[Path] = set()
    unique: list[Path] = []
    for file_path in files:
        resolved = file_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(file_path)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Python syntax without writing .pyc files."
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["backend", "tests", "scripts"],
        help="Files or directories to scan.",
    )
    args = parser.parse_args()

    files = iter_python_files(args.targets)
    if not files:
        print("No Python files found.")
        return 1

    errors = 0
    for file_path in files:
        try:
            source = file_path.read_text(encoding="utf-8")
            compile(source, str(file_path), "exec")
        except SyntaxError as exc:
            errors += 1
            print(f"[syntax-error] {file_path}:{exc.lineno}:{exc.offset} {exc.msg}")
        except Exception as exc:  # pragma: no cover - unexpected read/runtime edge
            errors += 1
            print(f"[error] {file_path}: {exc}")

    if errors:
        print(f"Syntax validation failed: {errors} file(s) with errors.")
        return 1

    print(f"Syntax validation passed: {len(files)} file(s) checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

