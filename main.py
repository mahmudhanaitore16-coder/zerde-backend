import os
import uuid
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL env is missing")


client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def get_connection():
    return psycopg2.connect(DATABASE_URL)


app = FastAPI(title="Friday Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------- SCHEMAS --------

class RegisterRequest(BaseModel):
    username: str


class ChatRequest(BaseModel):
    token: str
    message: str


class AssistantNameRequest(BaseModel):
    token: str
    assistant_name: str


# -------- HELPERS --------

def get_user_by_token(token: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, username, assistant_name FROM users WHERE token = %s",
        (token,),
    )
    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


# -------- ROUTES --------

@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}


@app.post("/register")
def register(body: RegisterRequest):
    username = body.username.strip()

    if not username:
        raise HTTPException(status_code=422, detail="username is required")

    token = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (id, username, token) VALUES (%s, %s, %s)",
            (user_id, username, token),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="username already exists")
    finally:
        cur.close()
        conn.close()

    return {
        "message": "User created",
        "token": token
    }


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


@app.post("/assistant-name")
def change_assistant_name(body: AssistantNameRequest):
    token = body.token.strip()
    name = body.assistant_name.strip()

    if not token or not name:
        raise HTTPException(status_code=422, detail="token and assistant_name required")

    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET assistant_name = %s WHERE token = %s",
        (name, token)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "assistant name updated"}


# 🔥 CHAT (GROQ AI)
@app.post("/chat")
def chat(body: ChatRequest):
    token = body.token.strip()
    message = body.message.strip()

    if not token or not message:
        raise HTTPException(status_code=422, detail="token and message required")

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = user[0]
    assistant_name = user[2] if user[2] else "Friday"

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"Сенің атың {assistant_name}. Қысқа әрі түсінікті жауап бер."},
                {"role": "user", "content": message}
            ]
        )

        reply = completion.choices[0].message.content

    except Exception as e:
        reply = "AI жауап бере алмады"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages (user_id, user_message, bot_response) VALUES (%s, %s, %s)",
        (user_id, message, reply)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "assistant": assistant_name,
        "reply": reply
    }


@app.get("/messages")
def get_messages(token: str):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = user[0]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_message, bot_response, created_at
        FROM messages
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 50
        """,
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
