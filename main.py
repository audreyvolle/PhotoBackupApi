import os
import sqlite3
import shutil
import re
from datetime import datetime, timedelta
from typing import List
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()

# --------------------
# CONFIG
# --------------------
DB_PATH = "./users.db" 

SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_ME")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

PHOTO_ROOT = os.getenv("PHOTO_STORAGE_PATH")

if not PHOTO_ROOT:
    raise RuntimeError("PHOTO_STORAGE_PATH is not set in .env")

PHOTO_ROOT = os.path.abspath(PHOTO_ROOT)

os.makedirs(PHOTO_ROOT, exist_ok=True)

app = FastAPI(title="Photo Backup API")

origins = [
    "capacitor://localhost",
    "http://localhost",
    "http://localhost:8100"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")



# --------------------
# DATABASE
# --------------------
def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        db.commit()

init_db()

# --------------------
# AUTH HELPERS
# --------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def require_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --------------------
# MODELS
# --------------------
class LoginRequest(BaseModel):
    username: str
    password: str

# --------------------
# AUTH ENDPOINTS
# --------------------
@app.post("/auth/login")
def login(data: LoginRequest):
    with get_db() as db:
        row = db.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (data.username,)
        ).fetchone()

    if not row or not verify_password(data.password, row[0]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(data.username)
    return {"token": token}

@app.post("/auth/create-user")
def create_user(data: LoginRequest):
    with get_db() as db:
        try:
            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (data.username, hash_password(data.password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="User already exists")

    return {"status": "created"}

# --------------------
# HEALTH
# --------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# --------------------
# PHOTO HELPERS
# --------------------
def photo_path_from_hash(username: str, photo_id: str, timestamp: str, ext: str) -> Path:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    year = f"{dt.year:04d}"

    base = user_photo_root(username)
    year_dir = base / year
    year_dir.mkdir(parents=True, exist_ok=True)

    return year_dir / f"{photo_id}{ext}"

def user_photo_root(username: str) -> Path:
    safe = "".join(c for c in username if c.isalnum() or c in ("-", "_"))
    path = Path(PHOTO_ROOT) / safe
    path.mkdir(parents=True, exist_ok=True)
    return path

def safe_identifier(identifier: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", identifier)

# --------------------
# PHOTO ENDPOINTS
# --------------------
@app.get("/photos/identifiers")
def list_identifiers(authorization: str = Header(None)):
    username = require_token(authorization)
    root = user_photo_root(username)

    identifiers = []

    for _, _, files in os.walk(root):
        for f in files:
            if f.startswith("."):
                continue
            identifiers.append(os.path.splitext(f)[0])

    return {
        "count": len(identifiers),
        "identifiers": identifiers
    }

@app.post("/photos/upload")
def upload_photo(
    file: UploadFile = File(...),
    hash: str = Header(...),
    timestamp: str = Header(...),
    authorization: str = Header(None)
):
    username = require_token(authorization)

    ext = os.path.splitext(file.filename)[1] or ".jpg"

    try:
        photo_id = safe_identifier(hash.lower())
        final_path = photo_path_from_hash(
            username=username,
            photo_id=photo_id,
            timestamp=timestamp,
            ext=ext
        )

        if os.path.exists(final_path):
            return {"status": "exists"}

        with open(final_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"status": "ok"}
    except Exception as e:
        print(f"ERROR: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})
