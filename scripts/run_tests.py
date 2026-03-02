from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import unittest
from pathlib import Path


def _pytest_available() -> bool:
    return importlib.util.find_spec("pytest") is not None


def _run_with_pytest(argv: list[str]) -> int:
    import pytest  # type: ignore

    return int(pytest.main(argv))


def _load_suite_from_file(path: Path, loader: unittest.TestLoader) -> unittest.TestSuite:
    module_name = "_local_test_" + str(path).replace("\\", "_").replace("/", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)


def _run_with_unittest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run test files/dirs with unittest fallback.",
        add_help=True,
    )
    parser.add_argument("targets", nargs="*", default=["tests"])
    parser.add_argument("-q", "--quiet", action="store_true")
    args, _unknown = parser.parse_known_args(argv)

    loader = unittest.TestLoader()
    master = unittest.TestSuite()

    for raw in args.targets:
        path = Path(raw)
        if path.is_file() and path.suffix == ".py":
            master.addTests(_load_suite_from_file(path, loader))
        elif path.is_dir():
            master.addTests(loader.discover(start_dir=str(path), pattern="test*.py"))
        else:
            print(f"Skipping missing target: {raw}")

    verbosity = 1 if args.quiet else 2
    result = unittest.TextTestRunner(verbosity=verbosity).run(master)
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    argv = sys.argv[1:]
    if _pytest_available():
        return _run_with_pytest(argv)
    print("pytest not found; falling back to unittest.")
    return _run_with_unittest(argv)


if __name__ == "__main__":
    raise SystemExit(main())
