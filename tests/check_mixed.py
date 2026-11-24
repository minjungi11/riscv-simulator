"""Compare 128 seeded programs with outcomes calculated while generating them.

Regenerate inputs and run this check from the project root with
    python tests/check_mixed.py
"""

import operator
import sys
from collections import Counter
from pathlib import Path
from random import Random
from struct import pack, unpack_from
from subprocess import run
from tempfile import TemporaryDirectory


MOD = 2**32
TEXT_BASE = 0x40000
BASE = 0x10000000
SIMULATOR = Path(__file__).resolve().parents[1] / "simulator.py"


def fields(*parts):
    """Concatenate the low bits of each (width, value) pair, MSB first."""
    word = 0
    for width, number in parts:
        word = (word << width) | (number % (1 << width))
    return word


def r_word(top, rs2, rs1, funct, rd):
    return fields((7, top), (5, rs2), (5, rs1), (3, funct), (5, rd), (7, 0x33))


def i_word(imm, rs1, funct, rd, opcode=0x13):
    return fields((12, imm), (5, rs1), (3, funct), (5, rd), (7, opcode))


def u_word(imm, rd):
    return fields((20, imm), (5, rd), (7, 0x37))


def s_word(imm, rs2, rs1, funct=2):
    return fields((7, imm >> 5), (5, rs2), (5, rs1), (3, funct), (5, imm), (7, 0x23))


def b_word(disp, rs2, rs1, funct):
    return fields((1, disp >> 12), (6, disp >> 5), (5, rs2), (5, rs1), (3, funct),
                  (4, disp >> 1), (1, disp >> 11), (7, 0x63))


ALU_R = {
    "add": (0, 0, operator.add), "sub": (32, 0, operator.sub),
    "and": (0, 7, operator.and_), "or": (0, 6, operator.or_),
}
ALU_I = {
    "addi": (0, operator.add), "andi": (7, operator.and_), "ori": (6, operator.or_),
}
BRANCH = {
    "beq": (0, operator.eq), "bne": (1, operator.ne),
    "blt": (4, operator.lt), "bge": (5, operator.ge),
}


def signed(value):
    return (value + 2**31) % MOD - 2**31


def build(case, hits):
    rng = Random(14112026 + case)
    data_length = [0, 1, 3, 4, 1023, 1024, rng.randint(0, 1024)][case % 7]
    initial = bytes(rng.randrange(256) for _ in range(data_length))
    memory = bytearray(initial.ljust(1024, b"\0"))
    regs = [0] * 32
    words = [u_word(BASE >> 12, 31), i_word(512, 31, 0, 30)]
    regs[30], regs[31] = BASE + 512, BASE
    for rd in range(1, 29):
        ix = rng.randrange(256) * 4
        words.append(i_word(ix, 31, 2, rd, 3))
        regs[rd] = unpack_from("<I", memory, ix)[0]
    # The four special values exercise signed and unsigned ordering in every batch.
    words.extend((u_word(0x80000, 1), u_word(0x80000, 2), i_word(-1, 2, 0, 2),
                  i_word(-1, 0, 0, 3), i_word(1, 0, 0, 4)))
    regs[1:5] = [0x80000000, 0x7fffffff, 0xffffffff, 1]

    choices = list(ALU_R) + list(ALU_I) + list(BRANCH) + ["lw", "sw", "lui"]
    for op in choices + rng.choices(choices, k=70):
        hits[op] += 1
        rd, a, b = (rng.randrange(29) for _ in range(3))
        if op in ALU_R:
            top, funct, calculate = ALU_R[op]
            words.append(r_word(top, b, a, funct, rd))
            val = calculate(regs[a], regs[b])
        elif op in ALU_I:
            immediate = rng.choice([-2048, -1, 0, 1, 2047, rng.randint(-2048, 2047)])
            funct, calculate = ALU_I[op]
            words.append(i_word(immediate, a, funct, rd))
            val = calculate(regs[a], immediate)
        elif op == "lui":
            immediate = rng.randrange(1 << 20)
            words.append(u_word(immediate, rd))
            val = immediate * 4096
        elif op in BRANCH:
            funct, predicate = BRANCH[op]
            if rng.random() < 0.6:
                a, b = rng.randrange(5), rng.randrange(5)
            taken = predicate(signed(regs[a]), signed(regs[b]))
            hits[f"{op}.{taken}"] += 1
            words += [b_word(8, b, a, funct), i_word(1, 29, 0, 29)]
            regs[29] += int(not taken)
            continue
        else:
            ix = rng.choice([0, 1020, rng.randrange(256) * 4])
            offset = ix - 512
            if op == "sw":
                words.append(s_word(offset, b, 30))
                memory[ix:ix + 4] = pack("<I", regs[b])
                continue
            words.append(i_word(offset, 30, 2, rd, 3))
            val = unpack_from("<I", memory, ix)[0]
        if rd:
            regs[rd] = val % MOD

    # Jump forward to the counter decrement. The backward branch then visits
    # the 13 increments twice before the count reaches zero.
    words += [i_word(3, 0, 0, 28), b_word(56, 0, 0, 0)]
    words += [i_word(1, 29, 0, 29)] * 13
    words += [i_word(-1, 28, 0, 28), b_word(-56, 0, 28, 1)]
    regs[28] = 0
    regs[29] += 26
    for reg in range(32):
        pos = 320 + reg * 4
        words.append(s_word(pos, reg, 31))
        memory[pos:pos + 4] = pack("<I", regs[reg])

    # Include recognized opcodes with unsupported function fields as well as unknown opcodes.
    invalid = (
        r_word(1, 2, 1, 0, 4), r_word(32, 2, 1, 7, 4),
        r_word(32, 2, 1, 6, 4), r_word(0, 2, 1, 4, 4),
        i_word(7, 4, 5, 4), i_word(4, 31, 1, 4, 3),
        s_word(4, 4, 31, 1), b_word(8, 0, 1, 6),
        0x00000073, 0xffffffff, 0x0000006f, 0xdeadbeef, 0,
    )[case % 13]
    stop_pc = TEXT_BASE + len(words) * 4
    words += [invalid, s_word(324, 0, 31), 0]
    assert len(words) * 4 <= 1024
    return b"".join(pack("<I", x) for x in words), initial, bytes(memory), stop_pc, invalid


def verify(total=128):
    hits = Counter()
    with TemporaryDirectory() as temp:
        root = Path(temp)
        for case in range(total):
            text, data, expected, pc, invalid = build(case, hits)
            (root / "text.bin").write_bytes(text)
            (root / "data.bin").write_bytes(data)
            (root / "data.out").write_bytes(b"poison" * 256)
            proc = run([sys.executable, str(SIMULATOR), "text.bin", "data.bin"],
                       cwd=root, capture_output=True, timeout=8)
            stdout = f"PC 0x{pc:08x} invalid instruction 0x{invalid:08x}\n".encode("ascii")
            if (proc.returncode, proc.stdout, proc.stderr) != (0, stdout, b""):
                raise AssertionError((case, proc.returncode, stdout, proc.stdout, proc.stderr))
            actual = (root / "data.out").read_bytes()
            if actual != expected:
                offset = next((i for i, (e, a) in enumerate(zip(expected, actual)) if e != a), None)
                if offset is None:
                    raise AssertionError((case, "output length", len(actual)))
                raise AssertionError((case, len(actual), offset, expected[offset:offset+4], actual[offset:offset+4]))
    print(f"{total}/{total} mixed generated programs passed; master seed 14112026")
    print(dict(sorted(hits.items())))


if __name__ == "__main__":
    verify()
