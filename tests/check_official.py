"""Run each official input from the ZIP in a clean directory and compare all bytes."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile


def mismatch(label, actual, expected):
    if actual == expected:
        return None
    common = min(len(actual), len(expected))
    first = next((i for i in range(common) if actual[i] != expected[i]), common)
    return (f"{label}: first mismatch at byte {first}, "
            f"actual/expected lengths {len(actual)}/{len(expected)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample_zip", type=Path, help="Path to test_input_5sets.zip")
    args = parser.parse_args()
    program = Path(__file__).resolve().parents[1] / "simulator.py"
    command = [sys.executable, str(program)]
    passed = 0
    with ZipFile(args.sample_zip) as archive, tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cases = sorted(
            p.rsplit("/", 1)[0] for p in archive.namelist()
            if p.startswith("test_input_5sets/set") and p.endswith("/expected_stdout.txt")
        )
        if len(cases) != 5:
            raise ValueError(f"expected five sample sets, found {len(cases)}")
        for case in cases:
            name = case.rsplit("/", 1)[1]
            inputs = root / name / "input files"
            cwd = root / name / "run"
            inputs.mkdir(parents=True)
            cwd.mkdir()
            text, data = inputs / "text.bin", inputs / "data.bin"
            text.write_bytes(archive.read(case + "/text.bin"))
            data.write_bytes(archive.read(case + "/data.bin"))
            expected_stdout = archive.read(case + "/expected_stdout.txt")
            expected_data = archive.read(case + "/expected_data.out")
            if len(expected_data) != 1024:
                raise ValueError(f"{name}: wrong fixture size: {len(expected_data)}")
            out = cwd / "data.out"
            out.write_bytes(b"!" * 1025)
            try:
                run = subprocess.run(command + [str(text), str(data)], cwd=cwd,
                                     capture_output=True, timeout=15)
            except subprocess.TimeoutExpired:
                print(f"FAIL {name}: timeout")
                continue
            errors = []
            if run.returncode != 0:
                errors.append(f"exit {run.returncode}, stderr={run.stderr!r}")
            errors.append(mismatch("stdout", run.stdout, expected_stdout))
            errors.append(mismatch("data.out", out.read_bytes(), expected_data)
                          if out.is_file() else "data.out missing")
            errors = [e for e in errors if e is not None]
            if errors:
                print(f"FAIL {name}: " + " | ".join(errors))
            else:
                passed += 1
                print(f"PASS {name}: {run.stdout.decode('ascii').strip()}, data.out 1024/1024")
    print(f"{passed}/{len(cases)} official sets passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
