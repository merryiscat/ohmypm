<#
  서버 생존 감시(scripts\watchdog.ps1)를 30분마다 도는 예약 작업으로 등록한다.
  사용자 권한 예약 작업이라 관리자 승격이 필요 없다(로그온 트리거는 승격을 요구해 시작프로그램 방식을 쓴다).

  사용:
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_watchdog.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_watchdog.ps1 -Remove
#>
[CmdletBinding()]
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$name = 'ohmyPM_watchdog'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'scripts\watchdog.ps1'

if ($Remove) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "[OK] 예약 작업 $name 해제"
  return
}

$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" `
  -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
  -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "[OK] 예약 작업 $name 등록 — 30분마다 $script"
