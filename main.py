import os
import uuid
from typing import Optional, List

import psycopg2
from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL env is missing")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id uuid PRIMARY KEY,
        username text UNIQUE NOT NULL,
        token text UNIQUE NOT NULL,
        assistant_name text DEFAULT 'Friday',
        created_at timestamptz DEFAULT now()
    );
    """)

    # messages table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id bigserial PRIMARY KEY,
        user_id uuid REFERENCES users(id) ON DELETE CASCADE,
        user_message text NOT NULL,
        bot_response text,
        created_at timestamptz DEFAULT now()
    );
    """)

    conn.commit()
    cur.close()
    conn.close()


app = FastAPI(title="Friday Backend")

# CORS (сенің localhost web үшін керек)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # кейін production-та нақты доменге қысып тастайсың
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# --------- Schemas ---------
class RegisterRequest(BaseModel):
    username: str


class RegisterResponse(BaseModel):
    message: str
    token: str


class MeRequest(BaseModel):
    token: str


class ChangeAssistantNameRequest(BaseModel):
    token: str
    assistant_name: str


class ChatRequest(BaseModel):
    token: str
    message: str


# --------- Helpers ---------
def get_user_by_token(token: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE token = %s", (token,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def fake_ai_reply(user_text: str, assistant_name: str) -> str:
    # Қазір “демо жауап”. Кейін Gemini/OpenAI қосқанда осы жерді ауыстырамыз.
    return f"{assistant_name}: Сен жаздың — {user_text}"


# --------- Routes ---------
@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}


@app.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest):
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="username is required")

    new_token = str(uuid.uuid4())
    new_id = str(uuid.uuid4())

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (id, username, token) VALUES (%s, %s, %s) RETURNING token",
            (new_id, username, new_token),
        )
        created = cur.fetchone()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="username already exists")
    finally:
        cur.close()
        conn.close()

    return {"message": "User created", "token": created["token"]}


@app.get("/me")
def me(token: str):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "id": str(user["id"]),
        "username": user["username"],
        "assistant_name": user.get("assistant_name") or "Friday",
        "created_at": str(user["created_at"]),
    }


@app.post("/assistant-name")
def change_assistant_name(body: ChangeAssistantNameRequest):
    token = body.token.strip()
    name = body.assistant_name.strip()

    if not token or not name:
        raise HTTPException(status_code=422, detail="token and assistant_name required")

    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    conn = get_connection()
    cur = conn.cursor()
    execute(
        "UPDATE users SET assistant_name = %s WHERE token = %s",
        (name, token),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"message": "assistant_name updated", "assistant_name": name}


@app.post("/chat")
def chat(body: ChatRequest):
    token = body.token.strip()
    msg = body.message.strip()
    if not token or not msg:
        raise HTTPException(status_code=422, detail="token and message required")

    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    assistant_name = user.get("assistant_name") or "Friday"
    bot_reply = fake_ai_reply(msg, assistant_name)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (user_id, user_message, bot_response) VALUES (%s, %s, %s)",
        (str(user["id"]), msg, bot_reply),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"reply": bot_reply}


@app.get("/messages")
def get_messages(token: str, limit: int = 50):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    limit = max(1, min(limit, 200))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_message, bot_response, created_at
        FROM messages
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT %s
        """,
        (str(user["id"]), limit),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return {"messages": rows}
