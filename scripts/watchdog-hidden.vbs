' 창 없이 watchdog.ps1을 실행하는 실행기 (2026-09-19).
'
' 왜 필요한가: 예약 작업이 사용자 세션에서 돌면(LogonType Interactive) powershell.exe에
' -WindowStyle Hidden을 줘도 콘솔 창이 30분마다 올라온다. 세션 0으로 옮기려면(S4U)
' 관리자 권한이 필요한데, 이 작업은 사용자 권한으로 두는 것이 등록 스크립트의 설계다.
' wscript는 콘솔을 만들지 않으므로, 여기서 창 없이(0) 띄우면 화면에 아무것도 뜨지 않는다.
'
' 예약 작업은 이것을 부른다:  wscript.exe //nologo "<이 파일>"
Option Explicit
Dim sh, fso, here
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
' 0 = 창 숨김, False = 끝날 때까지 기다리지 않는다(예약 작업은 바로 끝난다)
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & here & "\watchdog.ps1""", 0, False
