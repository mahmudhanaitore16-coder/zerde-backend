import os
from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI()

# ENV арқылы API key аламыз
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

genai.configure(api_key=GEMINI_API_KEY)

# ДҰРЫС модель (v1beta compatible)
model = genai.GenerativeModel("gemini-1.5-flash-latest")


class Message(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "ZERDE backend is running 🚀"}


@app.post("/chat")
def chat(data: Message):
    try:
        response = model.generate_content(data.message)
        return response.text
    except Exception as e:
        return {"error": str(e)}
