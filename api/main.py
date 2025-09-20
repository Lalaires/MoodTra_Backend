
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, mood
from api.bootstrap import prepare_runtime_tmp
from .routers import strategy_emotion

prepare_runtime_tmp()

app = FastAPI(title="MindPal API", version="1.0.0")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://mindpal.me",
    "https://www.mindpal.me",
    "https://iteration1.mindpal.me",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization", "x-session-id", "x-account-id"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(chat.router)
app.include_router(mood.router)
app.include_router(strategy_emotion.router)