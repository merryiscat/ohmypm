# ohmyPM SessionStart 훅 — 오르카에서 이 방을 열면 대시보드 서버가 떠 있게 한다.
# 이미 127.0.0.1:8123을 누가 듣고 있으면 아무것도 하지 않는다(중복 기동 방지).
# 포트 확인은 .NET으로 한다 — Get-NetTCPConnection은 매칭이 없으면 에러를 뱉어 분기가 지저분해진다.
# 기동 직후엔 아직 포트를 못 잡은 상태라(uvicorn 부팅 1~2초) 바인딩될 때까지 기다렸다 보고한다.
# 이 창을 안 두면 세션 두 개가 몇 초 안에 열릴 때 둘 다 띄우고 진 쪽이 10048로 죽는다(2026-09-16 실측).
# 창 없는 기동(pythonw)이라 로그는 logs\server_console.log로 간다. 끄기: scripts\stop_ohmypm.cmd
# 한글 출력이 깨지지 않도록 stdout을 UTF-8로 고정 (파일 자체도 UTF-8 BOM으로 저장할 것)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$port = 8123
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path   # 저장소 위치는 이 스크립트 자리에서 구한다

function Test-Listening {
    $ls = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    return [bool]($ls | Where-Object { $_.Port -eq $port })
}

if (Test-Listening) { exit 0 }

$pyw = Join-Path $root '.venv\Scripts\pythonw.exe'
$app = Join-Path $root 'scripts\run_ohmypm_hidden.py'
if (-not (Test-Path $pyw)) {
    Write-Output "[ohmypm] 대시보드 서버를 못 띄웠다 - $pyw 없음. 저장소에서 'uv sync'를 먼저 실행하라고 사용자에게 알려라."
    exit 0
}

try {
    Start-Process -FilePath $pyw -ArgumentList "`"$app`"" -WorkingDirectory $root -WindowStyle Hidden | Out-Null
} catch {
    Write-Output "[ohmypm] 대시보드 서버 기동 실패 - $($_.Exception.Message)"
    exit 0
}

foreach ($i in 1..40) {          # 최대 8초 (200ms x 40)
    Start-Sleep -Milliseconds 200
    if (Test-Listening) {
        Write-Output "[ohmypm] 대시보드 서버 기동 - http://127.0.0.1:$port (로그 logs\server_console.log / 끄기 scripts\stop_ohmypm.cmd)"
        exit 0
    }
}
Write-Output "[ohmypm] 대시보드 서버가 8초 안에 127.0.0.1:$port 를 못 잡았다. logs\server_console.log 확인이 필요하다고 사용자에게 알려라."
exit 0
