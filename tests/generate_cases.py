"""자체 테스트 입력과 독립적으로 계산한 기대 출력을 fixtures/에 기록한다."""

from pathlib import Path
import struct


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def lui(rd, upper):
    return (upper << 12) | (rd << 7) | 0x37


def i_type(opcode, funct3, rd, rs1, immediate):
    return ((immediate & 0xfff) << 20 | rs1 << 15 | funct3 << 12 |
            rd << 7 | opcode)


def addi(rd, rs1, immediate):
    return i_type(0x13, 0, rd, rs1, immediate)


def lw(rd, rs1, offset):
    return i_type(0x03, 2, rd, rs1, offset)


def r_type(funct7, funct3, rd, rs1, rs2):
    return (funct7 << 25 | rs2 << 20 | rs1 << 15 | funct3 << 12 |
            rd << 7 | 0x33)


def sw(rs2, rs1, offset):
    offset &= 0xfff
    return ((offset >> 5) << 25 | rs2 << 20 | rs1 << 15 | 2 << 12 |
            (offset & 31) << 7 | 0x23)


def branch(funct3, rs1, rs2, displacement):
    offset = displacement & 0x1fff
    return ((offset >> 12) << 31 | ((offset >> 5) & 63) << 25 |
            rs2 << 20 | rs1 << 15 | funct3 << 12 |
            ((offset >> 1) & 15) << 8 | ((offset >> 11) & 1) << 7 | 0x63)


def write_case(name, words, data, *, pc=None, invalid=0, expected_prefix=None):
    directory = FIXTURES / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "text.bin").write_bytes(struct.pack(f"<{len(words)}I", *words))
    (directory / "data.bin").write_bytes(data)
    if pc is None:  # 실행 한도 초과는 비정상 종료 코드만 비교한다.
        return
    prefix = data if expected_prefix is None else expected_prefix
    (directory / "expected_data.out").write_bytes(prefix.ljust(1024, b"\0"))
    line = f"PC 0x{pc:08x} invalid instruction 0x{invalid:08x}\n"
    (directory / "expected_stdout.txt").write_bytes(line.encode("ascii"))


def arithmetic():
    words = [
        lui(1, 0x10000), lui(2, 0x80000), addi(3, 2, -1),
        r_type(0, 0, 4, 2, 2),        # add  x4,x2,x2
        r_type(0x20, 0, 5, 3, 2),     # sub  x5,x3,x2
        addi(6, 0, -2048), addi(7, 0, 2047),
        i_type(0x13, 7, 8, 5, -2048), # andi x8,x5,-2048
        i_type(0x13, 6, 9, 7, -2048), # ori  x9,x7,-2048
        r_type(0, 7, 10, 3, 9),       # and  x10,x3,x9
        r_type(0, 6, 11, 2, 8),       # or   x11,x2,x8
    ]
    words.extend(sw(reg, 1, 4 * (reg - 2)) for reg in range(2, 12))
    words.extend([
        addi(0, 0, 314), sw(0, 1, 40), lw(0, 1, 0), sw(0, 1, 44),
        lui(0, 0x12345), sw(0, 1, 48),
        r_type(0x20, 0, 0, 7, 3), sw(0, 1, 52), sw(31, 1, 56), 0,
    ])
    registers = [0x80000000, 0x7fffffff, 0, 0xffffffff, 0xfffff800, 2047,
                 0xfffff800, 0xffffffff, 0x7fffffff, 0xfffff800, 0, 0, 0, 0, 0]
    write_case("alu_and_x0", words, b"\xaa" * 60, pc=0x40078,
               expected_prefix=struct.pack("<15I", *registers))


def branches():
    words = [
        lui(1, 0x10000), addi(2, 0, -2), addi(3, 0, 1),
        addi(4, 4, 2), addi(2, 2, 1), branch(4, 2, 3, -8),  # blt
        branch(5, 2, 3, 8), 0, addi(5, 0, -1),              # bge taken
        branch(5, 5, 3, 8), sw(4, 1, 0),                    # bge untaken
        branch(4, 3, 5, 8), sw(5, 1, 4),                    # blt untaken
        branch(0, 2, 3, 8), 0, branch(1, 2, 3, 8), sw(2, 1, 8),
        branch(0, 5, 3, 8), sw(3, 1, 12), branch(1, 5, 3, 8), 0,
        sw(4, 1, 16), 0,
    ]
    write_case("branch_paths", words, b"", pc=0x40058,
               expected_prefix=struct.pack("<5I", 6, 0xffffffff, 1, 1, 6))


def memory():
    words = [
        lui(1, 0x10000), addi(2, 1, 2047), addi(2, 2, 1),
        lw(3, 2, -2048), lw(4, 1, 1020), sw(4, 2, -2048), sw(3, 1, 1020),
        branch(0, 0, 0, 992),
    ] + [0] * 248
    initial = bytes(range(256)) * 4
    swapped = initial[-4:] + initial[4:-4] + initial[:4]
    write_case("full_segments", words, initial, pc=0x403fc, expected_prefix=swapped)

    words = [lui(1, 0x10000), lw(2, 1, 0), addi(2, 2, 1), sw(2, 1, 8),
             lw(3, 1, 4), sw(3, 1, 12), 0xfeedface, sw(2, 1, 0), 0]
    write_case("partial_word", words, bytes.fromhex("78 56 34 12 ab ef"),
               pc=0x40018, invalid=0xfeedface,
               expected_prefix=bytes.fromhex("78 56 34 12 ab ef 00 00 "
                                             "79 56 34 12 ab ef 00 00"))


def invalid_encodings():
    # 아래 값은 모두 지원 명령과 opcode를 공유하거나 다른 RV32I opcode를 쓴다.
    invalid_words = {
        "mul": 0x022081b3, "bad_or_funct7": 0x4020e1b3, "xor": 0x0020c1b3,
        "slli": 0x00109193, "lb": 0x00008183, "sb": 0x00208023,
        "bltu": 0x0020e463, "auipc": 0x00000197,
    }
    for name, word in invalid_words.items():
        words = [lui(1, 0x10000), addi(2, 0, 73), sw(2, 1, 0),
                 word, sw(2, 1, 4), 0]
        write_case(f"invalid_{name}", words, b"", pc=0x4000c,
                   invalid=word, expected_prefix=b"\x49")
    write_case("invalid_at_entry", [0], b"", pc=0x40000)


def instruction_limit():
    setup_and_loop = [lui(1, 122), addi(1, 1, 287),
                      addi(1, 1, -1), branch(1, 1, 0, -4)]
    write_case("limit_exact", setup_and_loop + [0], b"", pc=0x40010)
    write_case("limit_exceeded", setup_and_loop + [addi(2, 0, 1), 0], b"")


if __name__ == "__main__":
    arithmetic()
    branches()
    memory()
    invalid_encodings()
    instruction_limit()
