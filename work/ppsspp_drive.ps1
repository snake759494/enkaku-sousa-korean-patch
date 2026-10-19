# Drive PPSSPP for in-game checks: boot an ISO, press keys, take F12 screenshots.
#
#   powershell -File work\ppsspp_drive.ps1 -Iso <iso> -Steps "circle:3000,shot:500,down:800"
#
# A step is <key>[:<ms to wait after>] or wait:<ms>.  Keys follow memstick/PSP/SYSTEM/controls.ini:
# circle=X, cross=Z, triangle=S, square=A, start=B, select=V, L=Q, R=W, arrows, shot=F12.
# Keys are sent with keybd_event and a held press (SendKeys letters do not reach the game).
# Nothing is sent unless PPSSPP is the foreground window, so other apps never get keystrokes.
param([string]$Iso, [string]$Steps, [int]$Boot = 16)

Add-Type -Namespace W -Name K -MemberDefinition @'
[DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
'@

$VK = @{ up = 0x26; down = 0x28; left = 0x25; right = 0x27; circle = 0x58; cross = 0x5A;
         triangle = 0x53; square = 0x41; start = 0x42; select = 0x56; ltrig = 0x51; rtrig = 0x57; shot = 0x7B }
$shotDir = 'D:\psp\ppsspp_win\memstick\PSP\SCREENSHOT'

function Press([byte]$vk) {
    [W.K]::keybd_event($vk, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 120
    [W.K]::keybd_event($vk, 0, 2, [UIntPtr]::Zero)
}
function FgPid { $id = [uint32]0; [void][W.K]::GetWindowThreadProcessId([W.K]::GetForegroundWindow(), [ref]$id); return $id }

$before = @(Get-ChildItem $shotDir).Count
$p = Start-Process -FilePath 'D:\psp\ppsspp_win\PPSSPPWindows64.exe' -ArgumentList @('--windowed', "`"$Iso`"") `
        -WorkingDirectory 'D:\psp\ppsspp_win' -PassThru
Start-Sleep -Seconds $Boot
foreach ($s in $Steps.Split(',')) {
    $parts = $s.Trim().Split(':'); $name = $parts[0]; $wait = 1000
    if ($parts.Length -gt 1) { $wait = [int]$parts[1] }
    if ($name -eq 'wait') { Start-Sleep -Milliseconds $wait; continue }
    if ((FgPid) -ne $p.Id) {
        $p.Refresh(); [W.K]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
        [W.K]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 500
    }
    if ((FgPid) -ne $p.Id) { Write-Output ("ABORT: foreground pid " + (FgPid) + " is not PPSSPP; no keys sent"); break }
    Press $VK[$name]
    Start-Sleep -Milliseconds $wait
}
Stop-Process -Id $p.Id -Force
$after = @(Get-ChildItem $shotDir | Sort-Object LastWriteTime)
$after | Select-Object -Last ($after.Count - $before) | ForEach-Object { $_.Name }
