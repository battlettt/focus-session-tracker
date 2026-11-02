"""Plain test runner: finds tests/test_*.py and calls every test_* function.

Usage: python3 run_tests.py   (no pytest needed; pytest also works)
"""

import importlib
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent


def main():
    sys.path.insert(0, str(ROOT))
    passed, failed = 0, []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        module = importlib.import_module(f"tests.{path.stem}")
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            test = getattr(module, name)
            if not callable(test):
                continue
            try:
                test()
            except Exception:
                failed.append(f"{path.stem}.{name}")
                print(f"FAIL {path.stem}.{name}")
                traceback.print_exc()
            else:
                passed += 1
    print(f"\n{passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
