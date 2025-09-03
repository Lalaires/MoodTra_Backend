from fastapi import FastAPI
from .routers import chat, mood

app = FastAPI(title="MindPal API")

app.include_router(chat.router)
app.include_router(mood.router)

@app.get("/healthz")
def healthz():
    return {"ok": True}
