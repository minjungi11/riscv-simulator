"""Functional simulator for the project's 14-instruction RV32I subset."""

import sys
from pathlib import Path


TEXT_BASE = 0x00040000
DATA_BASE = 0x10000000
SEGMENT_SIZE = 1024
STEP_LIMIT = 1_000_000
MASK32 = 0xFFFFFFFF

R_OPS = {(0, 0): "add", (0, 0x20): "sub", (6, 0): "or", (7, 0): "and"}
I_OPS = {0: "addi", 6: "ori", 7: "andi"}
BRANCH_OPS = {0: "beq", 1: "bne", 4: "blt", 5: "bge"}


class SimulationError(Exception):
    """An input, address, or execution limit is outside the project model."""


def load_segment(path: Path) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(SEGMENT_SIZE + 1)
    if len(content) > SEGMENT_SIZE:
        raise SimulationError(f"{path}: segment exceeds {SEGMENT_SIZE} bytes")
    return content


def signed(value: int, width: int) -> int:
    """Interpret an unsigned bit field of the given width as two's complement."""
    sign_bit = 1 << (width - 1)
    return (value ^ sign_bit) - sign_bit


def store_immediate(word: int) -> int:
    raw = ((word >> 25) << 5) | ((word >> 7) & 0x1F)
    return signed(raw, 12)


def branch_immediate(word: int) -> int:
    # B offsets are in bytes. Bit zero is implicit in the instruction.
    raw = ((word >> 31) << 12) | (((word >> 7) & 1) << 11)
    raw |= (((word >> 25) & 0x3F) << 5) | (((word >> 8) & 0xF) << 1)
    return signed(raw, 13)


def decode(word: int) -> str | None:
    opcode = word & 0x7F
    funct3 = (word >> 12) & 7
    if opcode == 0x33:
        return R_OPS.get((funct3, word >> 25))
    if opcode == 0x13:
        return I_OPS.get(funct3)
    if opcode == 0x37:
        return "lui"
    if opcode == 0x03 and funct3 == 2:
        return "lw"
    if opcode == 0x23 and funct3 == 2:
        return "sw"
    if opcode == 0x63:
        return BRANCH_OPS.get(funct3)
    return None


def word_offset(address: int, base: int, size: int) -> int:
    offset = address - base
    if offset % 4 or not 0 <= offset <= size - 4:
        raise SimulationError(f"unaligned or out-of-range word at 0x{address:08x}")
    return offset


def read_word(data: bytearray, address: int) -> int:
    """Read an unsigned little-endian word at a data-segment address."""
    offset = word_offset(address, DATA_BASE, len(data))
    return int.from_bytes(data[offset:offset + 4], "little")


def write_word(data: bytearray, address: int, value: int) -> None:
    """Write the low 32 bits of value at a data-segment address."""
    offset = word_offset(address, DATA_BASE, len(data))
    data[offset:offset + 4] = (value & MASK32).to_bytes(4, "little")


def fetch(text: bytes, pc: int) -> int:
    offset = word_offset(pc, TEXT_BASE, len(text))
    return int.from_bytes(text[offset:offset + 4], "little")


def branch_taken(op: str, left: int, right: int) -> bool:
    if op == "beq":
        return left == right
    if op == "bne":
        return left != right
    if op == "blt":
        return signed(left, 32) < signed(right, 32)
    return signed(left, 32) >= signed(right, 32)  # bge


def execute(op: str, word: int, pc: int, regs: list[int], data: bytearray) -> int:
    rd = (word >> 7) & 31
    left = regs[(word >> 15) & 31]
    right = regs[(word >> 20) & 31]
    imm_i = signed(word >> 20, 12)
    next_pc = (pc + 4) & MASK32

    if op in ("beq", "bne", "blt", "bge"):
        if branch_taken(op, left, right):
            return (pc + branch_immediate(word)) & MASK32
        return next_pc
    if op == "sw":
        address = (left + store_immediate(word)) & MASK32
        offset = word_offset(address, DATA_BASE, len(data))
        data[offset:offset + 4] = right.to_bytes(4, "little")
        return next_pc

    if op == "lw":
        address = (left + imm_i) & MASK32
        offset = word_offset(address, DATA_BASE, len(data))
        result = int.from_bytes(data[offset:offset + 4], "little")
    elif op == "lui":
        result = word & 0xFFFFF000
    elif op == "add":
        result = left + right
    elif op == "sub":
        result = left - right
    elif op == "addi":
        result = left + imm_i
    elif op == "and":
        result = left & right
    elif op == "andi":
        result = left & imm_i
    elif op == "or":
        result = left | right
    elif op == "ori":
        result = left | imm_i
    else:
        raise AssertionError(f"missing execution rule for {op}")

    if rd != 0:
        regs[rd] = result & MASK32
    return next_pc


def simulate(text: bytes, data: bytearray) -> tuple[int, int]:
    if not text or len(text) % 4:
        raise SimulationError("text size must be a positive multiple of four")
    regs = [0] * 32
    pc = TEXT_BASE
    executed = 0
    while True:
        word = fetch(text, pc)
        op = decode(word)
        if op is None:
            return pc, word
        if executed == STEP_LIMIT:
            raise SimulationError(f"instruction limit exceeded at 0x{pc:08x}")
        pc = execute(op, word, pc, regs, data)
        executed += 1


def main(args: list[str]) -> int:
    if len(args) != 2:
        print("usage: simulator.py text.bin data.bin", file=sys.stderr)
        return 2
    try:
        text = load_segment(Path(args[0]))
        initial_data = load_segment(Path(args[1]))
        data = bytearray(SEGMENT_SIZE)
        data[:len(initial_data)] = initial_data
        pc, word = simulate(text, data)
        Path("data.out").write_bytes(data)
        line = f"PC 0x{pc:08x} invalid instruction 0x{word:08x}\n"
        sys.stdout.buffer.write(line.encode("ascii"))
    except (OSError, SimulationError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
