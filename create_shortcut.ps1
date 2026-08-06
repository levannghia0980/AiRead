$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "AIREAD.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "d:\NENGHIA0980\AIREAD\Run_AIREAD.bat"
$Shortcut.WorkingDirectory = "d:\NENGHIA0980\AIREAD"
$Shortcut.Description = "Khoi chay ung dung AIREAD"
$Shortcut.Save()
Write-Host "Shortcut created at $ShortcutPath"
