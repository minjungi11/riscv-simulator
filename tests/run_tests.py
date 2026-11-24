"""실제 명령행에서 자체 입력을 실행하고 표준 출력과 메모리를 바이트 단위로 비교한다."""

from pathlib import Path
import subprocess
import sys
import tempfile


TESTS = Path(__file__).resolve().parent
SIMULATOR = TESTS.parent / "simulator.py"


def verify(case, output_dir):
    command = [sys.executable, str(SIMULATOR),
               str(case / "text.bin"), str(case / "data.bin")]
    dump = output_dir / "data.out"
    dump.write_bytes(b"\xcc" * 1051)  # 기존 파일도 정확히 1,024바이트로 덮어써야 한다.
    result = subprocess.run(command, cwd=output_dir, capture_output=True, timeout=60)
    if case.name == "limit_exceeded":
        if result.returncode <= 0:
            return f"expected abnormal exit, got {result.returncode}"
        return None
    if result.returncode != 0:
        return f"exit {result.returncode}: {result.stderr!r}"
    expected_line = (case / "expected_stdout.txt").read_bytes()
    if result.stdout != expected_line:
        return f"stdout: expected {expected_line!r}, got {result.stdout!r}"
    expected_memory = (case / "expected_data.out").read_bytes()
    actual_memory = dump.read_bytes()
    if len(expected_memory) != 1024 or len(actual_memory) != 1024:
        return f"data.out size: expected {len(expected_memory)}, got {len(actual_memory)}"
    for address, (expected, actual) in enumerate(zip(expected_memory, actual_memory)):
        if expected != actual:
            return (f"data.out offset 0x{address:03x}: "
                    f"expected 0x{expected:02x}, got 0x{actual:02x}")
    return None


def main():
    cases = sorted(case for case in (TESTS / "fixtures").iterdir() if case.is_dir())
    if not cases:
        raise SystemExit("no test fixtures found")
    failures = 0
    for case in cases:
        with tempfile.TemporaryDirectory() as temporary:
            try:
                problem = verify(case, Path(temporary))
            except (OSError, subprocess.TimeoutExpired) as error:
                problem = str(error)
        if problem is None:
            print(f"PASS {case.name}")
        else:
            print(f"FAIL {case.name}: {problem}")
            failures += 1
    print(f"{len(cases) - failures}/{len(cases)} passed")
    return int(failures != 0)


if __name__ == "__main__":
    sys.exit(main())
