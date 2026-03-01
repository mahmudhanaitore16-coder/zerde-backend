from fastapi import FastAPI
from pydantic import BaseModel, Field
from datetime import datetime

app = FastAPI(
    title="Friday backend",
    description=(
        "⚠️ Privacy notice:\n"
        "- Бұл сервиске жіберілген хабарламалар серверде өңделеді.\n"
        "- Тестілеу/сапаны жақсарту үшін хабарламалар уақытша лог/сақтауға түсуі мүмкін.\n"
        "- Құпия ақпарат (пароль, карта, ЖСН т.б.) жіберме.\n"
        "- Қызметті қолдану арқылы осы шарттарға келісесің."
    ),
    version="1.0.0",
)

class ChatRequest(BaseModel):
    username: str | None = Field(default=None, description="Қолданушы аты (міндетті емес)")
    message: str = Field(..., min_length=1, description="Қолданушы хабарламасы")

@app.get("/")
def root():
    return {
        "status": "Friday backend is running",
        "notice": "Құпия ақпарат жіберме. Хабарламалар өңделуі/логқа түсуі мүмкін."
    }

@app.post("/chat")
def chat(data: ChatRequest):
    
    return {
        "response": f"Сен жаздың: {data.message}",
        "notice": "⚠️ Құпия ақпарат жіберме. Хабарламалар өңделуі/логқа түсуі мүмкін.",
        "server_time": datetime.utcnow().isoformat() + "Z"
    }
