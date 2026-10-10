# Создаёт ярлык «VibeC» на рабочем столе: запускает VibeC.exe, иконка VC
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot   # корень VibeC (tools/ .. )
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "VibeC.lnk"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = Join-Path $repo "VibeC.exe"
$lnk.WorkingDirectory = $repo
$lnk.IconLocation = (Join-Path $repo "assets\vibec.ico") + ",0"
$lnk.Description = "VibeC — портал курса (сервер + браузер)"
$lnk.Save()

Write-Output "OK: $lnkPath -> $($lnk.TargetPath)"
