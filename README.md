# RISC-V 기능 시뮬레이터

Python 3.10 이상과 표준 라이브러리만 사용한다. 압축을 푼 뒤 `simulator.py`가 있는 폴더에서 바로 실행할 수 있다. 빌드와 패키지 설치는 필요 없다.

## 실행

인수는 순서대로 명령어 바이너리 경로와 데이터 바이너리 경로다. 포함된 예제는 다음과 같이 실행한다.

**Windows PowerShell**

```powershell
python simulator.py tests/fixtures/partial_word/text.bin tests/fixtures/partial_word/data.bin
```

**Linux · macOS**

```sh
python3 simulator.py tests/fixtures/partial_word/text.bin tests/fixtures/partial_word/data.bin
```

이 예제의 표준 출력은 다음 한 줄이다.

```text
PC 0x00040018 invalid instruction 0xfeedface
```

현재 작업 디렉터리에 1,024바이트의 `data.out`이 생성된다. 기존 파일이 있으면 덮어쓴다. 예제의 결과는 `tests/fixtures/partial_word/expected_data.out`과 같다.

## 입력과 종료 규칙

- 지원 명령어는 `add`, `sub`, `addi`, `and`, `or`, `andi`, `ori`, `lui`, `lw`, `sw`, `beq`, `bne`, `blt`, `bge`다.
- `text.bin`은 4~1,024바이트이며 크기가 4의 배수이고 마지막 워드는 0이다. 첫 명령어 주소와 초기 PC는 모두 `0x00040000`이다.
- `data.bin`은 0~1,024바이트다. 시작 주소는 `0x10000000`이며 파일 뒤의 남은 공간은 0으로 채운다. 레지스터 32개는 0에서 시작하고 x0는 항상 0이다.
- 명령어와 데이터 워드는 모두 little-endian이다. 인출은 적재된 text 안에서, LW·SW는 data 안에서 정렬된 4바이트 단위로 수행한다.
- 지원하지 않는 명령을 인출하면 정상 종료한다. 표준 출력에는 인출 당시 PC와 명령어 값을 `0x`와 소문자 16진수 8자리로 표시한다. 단어 사이는 공백 하나이고 끝은 LF 한 바이트다. 데이터 덤프는 `0x10000000`~`0x100003ff`의 원시 바이트다.
- 정상 명령을 1,000,000개 실행한 뒤에도 다음 명령을 인출한다. 그 명령이 invalid이면 정상 종료하고, 지원 명령이면 실행 한도 초과로 종료한다. 정상 종료 코드는 0이다. 잘못된 인수, 파일 접근 실패, 유효 범위를 벗어난 인출·메모리 접근, 실행 한도 초과는 표준 오류와 0이 아닌 종료 코드로 알린다.

## 검증

아래 명령은 프로젝트 최상위 폴더에서 실행한다. Linux와 macOS에서는 `python` 자리에 `python3`를 사용한다. 첫 번째 명령의 ZIP 경로에는 제공받은 원본 파일의 위치를 넣는다.

```sh
python tests/check_official.py "../test_input_5sets.zip"
python tests/run_tests.py
python tests/check_mixed.py
```

첫째 명령은 공개 5세트의 표준 출력과 메모리 덤프를 바이트 단위로 비교한다. 둘째 명령은 자체 입력 15개로 연산, 분기, 워드 경계, invalid 판별과 실행 한도를 검사한다. 셋째 명령은 고정 시드로 혼합 프로그램 128개를 생성하고, 생성 과정에서 따로 계산한 결과와 대조한다. 각 검증은 임시 폴더에서 실행된다.

## 파일 배치

| 경로 | 내용 |
|---|---|
| `simulator.py` | 시뮬레이터 전체 소스와 명령행 진입점 |
| `report.pdf` | 구현 위치, 설계, 검증 결과와 AI 활용 내역 |
| `tests/fixtures/` | 사례별 text.bin·data.bin과 정상 종료 사례의 기대 출력 |
| `tests/CASES.md` | 각 자체 입력의 목적과 기대값 계산 과정 |
| `tests/run_tests.py`, `tests/generate_cases.py` | 자체 테스트 실행 및 입력·기대 출력 재생성 |
| `tests/check_official.py`, `tests/check_mixed.py` | 공식 ZIP 검사 및 고정 시드 혼합 검증 |
| `photo/` | 프로젝트 실행 중 팀원 전원이 함께 찍은 사진을 넣는 폴더 |

## 팀 정보

| 팀원 이름 | 담당 역할 | AI 활용자 이름 |
|---|---|---|
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
