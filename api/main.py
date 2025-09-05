
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, mood

app = FastAPI(title="MindPal API", version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat.router)
app.include_router(mood.router)
