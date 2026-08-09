# create_shortcut.ps1 — run this once to create a desktop shortcut for the Expense Dashboard.
# After running, double-click "Expense Dashboard" on your desktop to launch everything.

$launchScript = Join-Path $PSScriptRoot "launch.ps1"
$shortcutPath = Join-Path ([System.Environment]::GetFolderPath('Desktop')) "Expense Dashboard.lnk"

$WshShell            = New-Object -ComObject WScript.Shell
$Shortcut            = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments  = "-ExecutionPolicy Bypass -WindowStyle Normal -File `"$launchScript`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description      = "Start Expense Dashboard (Docker + FastAPI + Browser)"
$Shortcut.WindowStyle       = 1   # Normal window
$Shortcut.Save()

Write-Host "Shortcut created: $shortcutPath" -ForegroundColor Green
Write-Host "Double-click 'Expense Dashboard' on your desktop to launch the app."
