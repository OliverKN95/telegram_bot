import os
from fastapi import FastAPI
from app.routers import schedules
from app.utils.scheduler import start_scheduler, stop_scheduler

app = FastAPI(
    title="Web Scraper Telegram Bot",
    description="API modular para corridas programadas y scraping diario",
    version="1.3.0",
)

app.include_router(schedules.router)


@app.on_event("startup")
async def startup_event() -> None:
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    stop_scheduler()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "telegram-bot"}
