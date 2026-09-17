<#
  ohmyPM 서버 생존 감시 — 서버 **밖**에서 돈다(2026-09-17).

  왜 필요한가: 2026-09-15 새벽 이후 서버가 내려간 것을 이틀 넘게 아무도 몰랐다.
  "안 봐도 안 놓친다"가 목표인 도구가 자기 생존은 사람 눈에 맡기고 있었다.
  서버 안의 장치는 서버가 죽으면 같이 죽으므로, 감시는 예약 작업으로 바깥에 둔다.

  하는 일:
   - 30분마다(예약 작업) 대시보드 API를 찔러 본다.
   - 살아 있으면 로그 한 줄. 죽어 있으면 텔레그램으로 알린다.
     같은 알림을 30분마다 반복하지 않게, 처음 죽은 것을 알린 뒤에는 6시간마다 한 번만 다시 알린다.
     다시 살아나면 회복도 알린다.
   - 재시작은 하지 않는다 — 원인을 모른 채 자동으로 되살리면 실패가 조용해진다.
     (설계 결정 2026-09-17 평가: "죽었으면 텔레그램을 보내는 정도면 된다")

  등록: scripts\register_watchdog.ps1   해제: -Remove
  수동 실행: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\watchdog.ps1
#>
$ErrorActionPreference = 'Continue'
$root  = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logs  = Join-Path $root 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
$log   = Join-Path $logs 'watchdog.log'
$state = Join-Path $logs 'watchdog.state'      # "up" 또는 "down <마지막 알림 시각(epoch)>"
$url   = 'http://127.0.0.1:8123/api/projects'
$now   = Get-Date
$stamp = $now.ToString('yyyy-MM-dd HH:mm:ss')

function Write-Log([string]$msg) { Add-Content -Path $log -Value "$stamp | $msg" -Encoding utf8 }

# .env에서 텔레그램 설정을 읽는다(파이썬 설정 로더와 같은 파일, 같은 키)
$token = ''; $chat = ''
$envFile = Join-Path $root '.env'
if (Test-Path $envFile) {
  foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*TELEGRAM_BOT_TOKEN\s*=\s*(.+?)\s*$') { $token = $Matches[1].Trim('"',"'") }
    if ($line -match '^\s*TELEGRAM_CHAT_ID\s*=\s*(.+?)\s*$')   { $chat  = $Matches[1].Trim('"',"'") }
  }
}

function Send-Telegram([string]$text) {
  if (-not $token -or -not $chat) { Write-Log "텔레그램 미설정 — 알림 생략: $text"; return }
  try {
    $body = @{ chat_id = $chat; text = $text }
    Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$token/sendMessage" -Body $body -TimeoutSec 15 | Out-Null
    Write-Log "텔레그램 발송: $text"
  } catch {
    Write-Log "텔레그램 발송 실패: $($_.Exception.Message)"
  }
}

# 살아 있나
$up = $false
try {
  $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 8
  if ($r.StatusCode -eq 200) { $up = $true }
} catch { $up = $false }

$prev = if (Test-Path $state) { (Get-Content $state -Raw).Trim() } else { '' }
$epoch = [int][double]::Parse((Get-Date -UFormat %s))

if ($up) {
  Write-Log "정상 — $url 응답 200"
  if ($prev -like 'down*') { Send-Telegram "[ohmyPM 감시] 대시보드 서버가 다시 살아났습니다 ($stamp)" }
  Set-Content -Path $state -Value 'up' -Encoding utf8
} else {
  Write-Log "정지 — $url 무응답"
  $notify = $true
  if ($prev -like 'down*') {
    $last = [int]($prev -split ' ')[1]
    if (($epoch - $last) -lt 6*3600) { $notify = $false }   # 6시간 안에는 다시 안 보낸다
  }
  if ($notify) {
    Send-Telegram "[ohmyPM 감시] 대시보드 서버가 내려가 있습니다 ($stamp). 야간 배치·스캔이 돌지 않습니다. 켜기: scripts\run_ohmypm.cmd"
    Set-Content -Path $state -Value "down $epoch" -Encoding utf8
  }
}
