$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$taskName = 'ComicsMeta-Local-8765'
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$hostScript = Join-Path $projectDir 'server_host.py'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Actions.Arguments -notlike "*$hostScript*") {
    throw 'A different app owns this task name. No changes made.'
}
try {
    $null = Invoke-RestMethod 'http://127.0.0.1:8765/api/state' -TimeoutSec 4
    Write-Output 'Comics Meta is already running: http://127.0.0.1:8765/'
    exit 0
} catch {}
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument ('"' + $hostScript + '"') -WorkingDirectory $projectDir
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$null = Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Description 'On-demand Comics Meta server, independent of the launching client. No automatic sign-in trigger.' -Force
Start-ScheduledTask -TaskName $taskName
Write-Output 'Comics Meta started: http://127.0.0.1:8765/'
