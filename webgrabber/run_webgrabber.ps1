<#
.SYNOPSIS
    Khởi chạy WebGrabber v2.0 UI
.DESCRIPTION
    Script tự động kích hoạt môi trường ảo (nếu có) và khởi chạy giao diện WebGrabber.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "   Khoi Dong WebGrabber v2.0     " -ForegroundColor White
Write-Host "=================================" -ForegroundColor Cyan

# Chuyển tới thư mục chứa script
Set-Location -Path $ScriptDir

# Tìm Python executable: Kiểm tra xem python trong venv có hoạt động không (đề phòng venv bị hỏng)
$PythonExe = "python"

function Test-PythonExe ($Path) {
    if (-Not (Test-Path $Path -PathType Leaf)) { return $false }
    try {
        $output = & $Path --version 2>&1
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

if (Test-PythonExe ".\.venv\Scripts\python.exe") {
    Write-Host "[+] Su dung Python tu moi truong ao .venv..." -ForegroundColor Yellow
    $PythonExe = ".\.venv\Scripts\python.exe"
} elseif (Test-PythonExe ".\venv\Scripts\python.exe") {
    Write-Host "[+] Su dung Python tu moi truong ao venv..." -ForegroundColor Yellow
    $PythonExe = ".\venv\Scripts\python.exe"
} else {
    Write-Host "[!] Khong tim thay moi truong ao hop le. Su dung Python mac dinh cua he thong..." -ForegroundColor Gray
}

# Chạy lệnh khởi động UI
Write-Host "[+] Kiem tra va cai dat thu vien..." -ForegroundColor Cyan
& $PythonExe -m pip install -r requirements.txt -q

Write-Host "[+] Dang cai dat browser cho Playwright..." -ForegroundColor Cyan
& $PythonExe -m playwright install chromium

Write-Host "[+] Dang mo giao dien ung dung..." -ForegroundColor Green
try {
    # PYTHONPATH để tránh lỗi module không nhận diện thư mục hiện tại
    $env:PYTHONPATH = $ScriptDir
    & $PythonExe -m webgrabber.cli.commands ui
} catch {
    Write-Host "[-] Loi khi chay WebGrabber: $_" -ForegroundColor Red
    Read-Host "Nhan Enter de thoat..."
}
