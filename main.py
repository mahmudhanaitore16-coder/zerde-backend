import os
import uuid
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai


DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL env is missing")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY env is missing")


# Gemini конфигурация
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


app = FastAPI(title="Friday AI Backend")


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------- Schemas --------

class RegisterRequest(BaseModel):
    username: str


class ChatRequest(BaseModel):
    token: str
    message: str


class AssistantNameRequest(BaseModel):
    token: str
    assistant_name: str


# -------- Helpers --------

def get_user_by_token(token: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, username, assistant_name FROM users WHERE token=%s", (token,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


# -------- Routes --------

@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}


# Register
@app.post("/register")
def register(body: RegisterRequest):

    username = body.username
    token = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (id, username, token) VALUES (%s,%s,%s)",
            (user_id, username, token),
        )
        conn.commit()

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="username already exists")

    cur.close()
    conn.close()

    return {
        "message": "User created",
        "token": token
    }


# Profile
@app.get("/me")
def me(token: str):

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "id": user[0],
        "username": user[1],
        "assistant_name": user[2]
    }


# Change assistant name
@app.post("/assistant-name")
def change_assistant_name(body: AssistantNameRequest):

    token = body.token
    name = body.assistant_name

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET assistant_name=%s WHERE token=%s",
        (name, token)
    )

    conn.commit()

    cur.close()
    conn.close()

    return {"message": "assistant name updated"}


# CHAT (Gemini AI)
@app.post("/chat")
def chat(body: ChatRequest):

    token = body.token
    message = body.message

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = user[0]
    assistant_name = user[2] if user[2] else "Friday"

    # Gemini AI жауап
    try:
        response = model.generate_content(message)
        ai_reply = response.text
    except Exception as e:
        ai_reply = "AI жауап бере алмады."

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages (user_id, user_message, bot_response) VALUES (%s,%s,%s)",
        (user_id, message, ai_reply)
    )

    conn.commit()

    cur.close()
    conn.close()

    return {
        "assistant": assistant_name,
        "reply": ai_reply
    }


# Message history
@app.get("/messages")
def get_messages(token: str):

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = user[0]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_message, bot_response, created_at FROM messages WHERE user_id=%s ORDER BY created_at DESC LIMIT 50",
        (user_id,)
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for r in rows:
        result.append({
            "user_message": r[0],
            "bot_response": r[1],
            "created_at": str(r[2])
        })

    return {"messages": result}
