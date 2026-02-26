from fastapi import FastAPI
from pydantic import BaseModel
import os
import google.generativeai as genai

app = FastAPI()

genai.configure(api_key=os.getenv(""))
model = genai.GenerativeModel("gemini-1.5-flash")

class Message(BaseModel):
    message: str

@app.get("/")
def root():
    return {"status": "ZERDE backend is running"}

@app.post("/chat")
def chat(data: Message):
    response = model.generate_content(data.message)
    return {"response": response.text}
