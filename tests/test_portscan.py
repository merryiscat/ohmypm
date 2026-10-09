"""포트 스캔 — netstat·프로세스 목록 파싱과 명령줄→프로젝트 매칭(고정 문자열, 한글 경로 포함)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import portscan  # noqa: E402

NETSTAT = """
활성 연결

  프로토콜  로컬 주소              외부 주소              상태            PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:8123         0.0.0.0:0              LISTENING       7296
  TCP    [::]:8123              [::]:0                 LISTENING       7296
  TCP    127.0.0.1:8901         0.0.0.0:0              LISTENING       4321
  TCP    192.168.0.5:51000      1.2.3.4:443            ESTABLISHED     9999
"""

PROCS = ('[{"ProcessId":7296,"Name":"pythonw.exe","CommandLine":"\\"C:\\\\Users\\\\minhy\\\\project\\\\ohmyPM\\\\.venv\\\\Scripts\\\\pythonw.exe\\" scripts\\\\run_ohmypm_hidden.py"},'
         '{"ProcessId":4321,"Name":"python.exe","CommandLine":"python C:\\\\Users\\\\minhy\\\\project\\\\state\\\\dashboard\\\\server.py"},'
         '{"ProcessId":1234,"Name":"svchost.exe","CommandLine":null}]')


def test_parse_netstat_listening_only_first_pid():
    ports = portscan._parse_netstat(NETSTAT)
    assert ports == {135: 1234, 8123: 7296, 8901: 4321}


def test_parse_procs_strips_exe_and_handles_single_object():
    procs = portscan._parse_procs(PROCS)
    assert procs[7296][0] == "pythonw" and "run_ohmypm_hidden" in procs[7296][1]
    assert procs[1234] == ("svchost", "")
    single = portscan._parse_procs('{"ProcessId":5,"Name":"node.exe","CommandLine":"node app.js"}')
    assert single == {5: ("node", "node app.js")}
    assert portscan._parse_procs("not json") == {}


def test_match_project_longest_path_and_korean():
    cands = [r"C:\Users\minhy\project", r"C:\Users\minhy\project\state", r"C:\Users\minhy\project\한글프로젝트"]
    assert portscan.match_project(r"python C:\Users\minhy\project\state\dashboard\server.py", cands) == r"C:\Users\minhy\project\state"
    assert portscan.match_project(r'"C:\Users\minhy\project\한글프로젝트\run.exe" --port 3000', cands) == r"C:\Users\minhy\project\한글프로젝트"
    assert portscan.match_project(r"C:\Users\minhy\project\statement\x.py", [r"C:\Users\minhy\project\state"]) is None
    assert portscan.match_project("", cands) is None
