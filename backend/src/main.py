import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.models.base import init_db
from src.api import router as api_router

app = FastAPI(title="Chat Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    from src.services.presence import run_afk_checker
    asyncio.create_task(run_afk_checker())
    from src.services.jabber_server import start_jabber_server
    asyncio.create_task(start_jabber_server())


@app.get("/health")
async def health():
    return {"status": "ok"}
