Write-Host "Starting Photo Backup API..."

# ---------- Python check ----------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is not installed. Download from https://python.org"
    exit 1
}

# ---------- Virtualenv ----------
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment"
    python -m venv venv
}

# ---------- Activate venv ----------
.\venv\Scripts\Activate.ps1

# ---------- Dependencies ----------
Write-Host "Installing dependencies (if needed)"
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt | Out-Null

# ---------- Get local IP ----------
$IP = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "169.*" -and $_.IPAddress -ne "127.0.0.1" } |
    Select-Object -First 1 -ExpandProperty IPAddress)

$PORT = $env:PORT
if (-not $PORT) { $PORT = 3000 }

Write-Host ""
Write-Host "Server will be available at:"
Write-Host "http://$IP`:$PORT"
Write-Host ""

# ---------- First run user ----------
if (-not (Test-Path "users.db")) {
    Write-Host "First run detected - create a user"

    $username = Read-Host "Username"
    $password = Read-Host "Password" -AsSecureString
    $confirm  = Read-Host "Confirm password" -AsSecureString

    $plain1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
    )

    $plain2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirm)
    )

    if ($plain1 -ne $plain2) {
        Write-Host "Passwords do not match"
        exit 1
    }

    Start-Process -NoNewWindow python -ArgumentList "-m uvicorn main:app --port $PORT" | Out-Null
    Start-Sleep 2

    Invoke-RestMethod `
        -Uri "http://127.0.0.1:$PORT/auth/create-user" `
        -Method POST `
        -ContentType "application/json" `
        -Body "{ `"username`": `"$username`", `"password`": `"$plain1`" }"

    Get-Process python | Stop-Process -Force
    Write-Host "User created"
}

# ---------- Run server ----------
Write-Host "Starting API"
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
