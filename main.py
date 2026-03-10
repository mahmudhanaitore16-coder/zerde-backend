import os
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai

app = FastAPI()

# Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


# ===== Models =====
class RegisterRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    token: str
    message: str


class AssistantNameRequest(BaseModel):
    token: str
    assistant_name: str


# ===== Helper =====
def get_user_by_token(token):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, assistant_name FROM users WHERE token=%s", (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "assistant_name": row[2],
    }


# ===== Register =====
@app.post("/register")
def register(body: RegisterRequest):
    import uuid

    token = str(uuid.uuid4())

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO users (username, password, token) VALUES (%s, %s, %s)",
        (body.username, body.password, token),
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"token": token}


# ===== Assistant Name =====
@app.post("/assistant-name")
def assistant_name(body: AssistantNameRequest):
    token = body.token.strip()
    name = body.assistant_name.strip()

    if not token or not name:
        raise HTTPException(status_code=422, detail="token and assistant_name required")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET assistant_name=%s WHERE token=%s",
        (name, token),
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"assistant_name": name}


# ===== Chat =====
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

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"You are an AI assistant named {assistant_name}. User says: {msg}",
        )

        bot_reply = response.text

    except Exception as e:
        bot_reply = f"AI error: {str(e)}"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages (user_id, user_message, bot_response) VALUES (%s,%s,%s)",
        (str(user["id"]), msg, bot_reply),
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"assistant": assistant_name, "reply": bot_reply}


# ===== Messages =====
@app.get("/messages")
def get_messages(token: str, limit: int = 50):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id,user_message,bot_response,created_at
        FROM messages
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT %s
        """,
        (str(user["id"]), limit),
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {"messages": rows}
