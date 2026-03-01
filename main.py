from fastapi import FastAPI
from pydantic import BaseModel
import os
import psycopg2

app = FastAPI()


class Message(BaseModel):
    message: str
    username: str | None = "guest"


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL)


@app.get("/")
def root():
    return {"status": "Friday backend is running"}


@app.post("/chat")
def chat(data: Message):
    user_text = data.message
    username = data.username or "guest"

    # Пока бот простой жауап береді
    bot_reply = f"Сен жаздың: {user_text}"

    # Базаға сақтау
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages (username, user_message, bot_response) VALUES (%s, %s, %s)",
        (username, user_text, bot_reply)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"response": bot_reply}


@app.get("/messages")
def get_messages(limit: int = 20):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, username, user_message, bot_response, created_at "
        "FROM messages ORDER BY id DESC LIMIT %s",
        (limit,)
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    # rows -> list of dict-like output
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "username": r[1],
            "user_message": r[2],
            "bot_response": r[3],
            "created_at": str(r[4]),
        })

    return {"items": result}
