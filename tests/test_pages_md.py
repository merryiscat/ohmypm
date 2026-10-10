"""화면의 마크다운 변환 md() — 표 처리. 화면 JS는 Python 문자열(_HTML) 안에 있어서,
md 함수 부분만 잘라 node로 돌려 본다. node가 없는 PC에서는 건너뛴다."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.web.routers.pages import _HTML  # noqa: E402

NODE = shutil.which("node")


def _md_source() -> str:
    """_HTML에서 'function md(' 부터 첫 줄머리 '}' 까지를 잘라 낸다."""
    m = re.search(r"^function md\(src\)\{.*?^\}", _HTML, re.S | re.M)
    assert m, "md 함수를 찾지 못했다 — 이름이나 모양이 바뀌었으면 이 테스트도 고칠 것"
    return m.group(0)


def render(text: str) -> str:
    js = _md_source() + f"\nprocess.stdout.write(md({json.dumps(text)}));"
    out = subprocess.run([NODE, "-e", js], capture_output=True, timeout=20)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    return out.stdout.decode("utf-8")


pytestmark = pytest.mark.skipif(not NODE, reason="node 없음")


def test_table_with_header():
    h = render("| 이름 | 판정 |\n|---|---|\n| 가 | 나 |")
    assert "<thead><tr><th>이름</th><th>판정</th></tr></thead>" in h
    assert "<tbody><tr><td>가</td><td>나</td></tr></tbody>" in h


def test_table_without_header():
    h = render("| 가 | 나 |\n| 다 | 라 |")
    assert "<thead>" not in h
    assert h.count("<tr>") == 2


def test_table_then_normal_line():
    h = render("| 가 | 나 |\n|---|---|\n| 1 | 2 |\n그다음 문단")
    assert h.index("</table>") < h.index("그다음 문단")


def test_pipe_inside_code_and_escaped_pipe_stay_in_one_cell():
    h = render("| 명령 | 뜻 |\n|---|---|\n| `a|b` | 또는 \\| 이것 |")
    assert "<td><code>a|b</code></td>" in h
    assert "<td>또는 | 이것</td>" in h


def test_row_missing_trailing_pipe_stays_in_table():
    h = render("| 가 | 나 |\n|---|---|\n| 1 | 2")
    assert "<td>1</td><td>2</td>" in h
