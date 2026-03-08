#!/usr/bin/env bash
set -e

echo "Photo Backup API starting…"

# ---------- Python check ----------
if ! command -v python3 &>/dev/null; then
  echo "Python 3 is required but not installed"
  exit 1
fi

# ---------- Virtualenv ----------
if [ ! -d "venv" ]; then
  echo "Creating virtual environment"
  python3 -m venv venv
fi

source venv/bin/activate

# ---------- Dependencies ----------
echo "Installing dependencies (if needed)"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

# ---------- Detect IP ----------
IP=$(python3 - << 'EOF'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80))
    print(s.getsockname()[0])
finally:
    s.close()
EOF
)

PORT=${PORT:-3000}

echo ""
echo "Server will be available at:"
echo "   http://$IP:$PORT"
echo ""

# ---------- First run user setup ----------
if [ ! -f "users.db" ]; then
  echo "👤 First run detected — create a user"
  read -p "Username: " USERNAME
  read -s -p "Password: " PASSWORD
  echo ""
  read -s -p "Confirm password: " CONFIRM
  echo ""

  if [ "$PASSWORD" != "$CONFIRM" ]; then
    echo "Passwords do not match"
    exit 1
  fi

  uvicorn main:app --host 127.0.0.1 --port $PORT &
  PID=$!
  sleep 2

  curl -s -X POST http://127.0.0.1:$PORT/auth/create-user \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" >/dev/null

  kill $PID
  sleep 1

  echo "User created"
  echo ""
fi

# ---------- Run server ----------
echo "Starting API"
uvicorn main:app --host 0.0.0.0 --port $PORT
