# Task Scheduler entry for the election-night loop (SPEC section on the home-page live updates).
# This script only registers or removes the task when a person runs it; it never runs the loop itself.
# Kept ASCII-only: Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page.
#
# Register (after the dry run checks out; run in a terminal PowerShell; -Prefix is the CEC fragment URL minus the 17-digit area code):
#   powershell -ExecutionPolicy Bypass -File scripts\live_loop_task.ps1 -Prefix https://www.cec.gov.tw/zh-TW/TC
#   Rehearsal: add -Epoch rehearsal -Extra '--out-dir rehearsal --home-name index.html --date 2026-11-27 --test-banner'
# Status:  Get-ScheduledTaskInfo -TaskName einfo-election-live-loop
# Pause:   Disable-ScheduledTask -TaskName einfo-election-live-loop   (resume with Enable-ScheduledTask)
# Remove:  powershell -ExecutionPolicy Bypass -File scripts\live_loop_task.ps1 -Uninstall
#
# Runs live_loop.py --once every 30 seconds for 12 hours: two triggers, each repeating every minute (the Task Scheduler
# minimum), the second one 30 s after the first (11-27; before that every 1 or 2 minutes; a round takes about 26 s).
# If the previous round is still running the new one is skipped, so a slow round falls back to about one a minute
# (IgnoreNew; the loop also holds a file lock). A round running longer than 10 minutes is killed.
# Runs only while the user is logged on (git credentials live in the user session).
# Python runs inside a headless console host, so no window pops up: the venv's pythonw.exe is a launcher that starts the
# console python.exe, which opened a Windows Terminal window every round (11-28).
param(
  [string]$Prefix,
  [string]$Epoch = "2026-11-28",
  [string]$Extra = "",
  [datetime]$Start = (Get-Date).AddMinutes(1),
  [switch]$Uninstall
)
$name = "einfo-election-live-loop"
if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false
  Write-Output "Removed task $name"
  return
}
if (-not $Prefix) { throw "Give -Prefix (the CEC fragment URL without the 17-digit area code)" }
$dir = Split-Path -Parent $PSScriptRoot   # the election-2026 folder
$py = Join-Path $env:USERPROFILE ".venvs\research-lab\Scripts\python.exe"
$arguments = "-I `"$dir\scripts\live_loop.py`" --once --prefix $Prefix --epoch $Epoch $Extra".Trim()
$action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\conhost.exe" -Argument "--headless `"$py`" $arguments" -WorkingDirectory $dir
$trigger = @($Start, $Start.AddSeconds(30)) | ForEach-Object {
  New-ScheduledTaskTrigger -Once -At $_ -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Hours 12) }
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
  -Description "einfo-widgets election-2026 live loop" -Force | Out-Null
Write-Output "Registered $name : $py $arguments (every 30 seconds from $Start)"
