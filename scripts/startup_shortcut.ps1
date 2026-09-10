<#
  ohmyPM 대시보드 서버를 로그인 시 자동 실행 — 시작프로그램 바로가기 방식.

  왜 이 방식인가 (2026-09-10 실측):
   - schtasks /create /sc onlogon 은 **관리자 권한**을 요구한다(액세스 거부).
     시작프로그램 폴더는 사용자 자기 것이라 권한 승격이 필요 없다.
   - 예전엔 VBS 런처를 썼는데 최신 Windows 11에서 Windows Script Host가
     "메모리 리소스가 부족" 오류로 죽는다. pythonw.exe(GUI 서브시스템)를 직접
     가리키면 스크립트 호스트도, 창 숨김 꼼수도 필요 없다.
   - WScript.Shell **COM 객체**는 멀쩡하다(깨진 건 wscript.exe 실행기뿐)라 .lnk를 만들 수 있다.

  사용:
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\startup_shortcut.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\startup_shortcut.ps1 -Remove
#>
[CmdletBinding()]
param([switch]$Remove)

$ErrorActionPreference = 'Stop'

# 저장소 위치는 이 스크립트 자리에서 구한다 — 하드코딩 금지
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pyw  = Join-Path $root '.venv\Scripts\pythonw.exe'
$app  = Join-Path $root 'scripts\run_ohmypm_hidden.py'
$link = Join-Path ([Environment]::GetFolderPath('Startup')) 'ohmyPM.lnk'

if ($Remove) {
  if (Test-Path $link) { Remove-Item $link -Force; Write-Host "[OK] 자동 실행 해제 - $link 삭제" }
  else                 { Write-Host "[..] 등록돼 있지 않습니다 - $link 없음" }
  return
}

if (-not (Test-Path $pyw)) {
  Write-Host "[실패] $pyw 없음 - 저장소에서 'uv sync' 를 먼저 실행하세요."
  exit 1
}

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($link)
$sc.TargetPath       = $pyw
$sc.Arguments        = '"' + $app + '"'
$sc.WorkingDirectory = $root      # db_path·logs가 저장소 기준 상대경로다
$sc.Description      = 'ohmyPM dashboard server (windowless)'
$sc.Save()

Write-Host "[OK] 로그인 시 자동 실행 등록 - $link"
Write-Host "     대상   : $pyw"
Write-Host "     인자   : $app"
Write-Host "     지금 켜기: scripts\run_ohmypm.cmd (창+로그) 또는 이 바로가기 실행"
Write-Host "     끄기     : scripts\stop_ohmypm.cmd"
Write-Host "     해제     : ...startup_shortcut.ps1 -Remove"
