from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import google.generativeai as genai

app = FastAPI(title="ZERDE backend")

# --------- Request schema (message немесе text қабылдаймыз) ----------
class ChatRequest(BaseModel):
    message: str | None = None
    text: str | None = None

    def get_prompt(self) -> str:
        prompt = self.message if self.message is not None else self.text
        if prompt is None or not prompt.strip():
            raise ValueError("Send JSON with 'message' or 'text' (non-empty).")
        return prompt.strip()

# --------- Gemini config ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

# Модель атын env арқылы да ауыстыра аласың
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
model = genai.GenerativeModel(MODEL_NAME)


@app.get("/")
def root():
    return {"status": "ZERDE backend is running"}


@app.post("/chat")
def chat(data: ChatRequest):
    try:
        prompt = data.get_prompt()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        response = model.generate_content(prompt)
        return {"response": response.text}
    except Exception as e:
        # Swagger-та нақты қате көріну үшін
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")
