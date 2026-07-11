import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import flights, incidents, webhooks, ocr, ws
from .websocket_manager import manager
from .redis_bus import subscribe_and_forward
from .database import SessionLocal
from .routers.incidents import sweep_breached_incidents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aeropulse.main")


async def _redis_to_websocket_bridge():
    """Background task: every event published to Redis gets forwarded to
    every connected admin-dashboard WebSocket client."""
    async def on_message(data: dict):
        await manager.broadcast(data)

    await subscribe_and_forward(on_message)


async def _sla_sweep_loop():
    """Background task: every 30s, check for incidents that have blown
    past their SLA deadline and auto-breach + auto-coupon them."""
    while True:
        db = SessionLocal()
        try:
            await sweep_breached_incidents(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SLA sweep failed: %s", exc)
        finally:
            db.close()
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bridge_task = asyncio.create_task(_redis_to_websocket_bridge())
    sweep_task = asyncio.create_task(_sla_sweep_loop())
    logger.info("AeroPulse API started — Redis bridge and SLA sweep running")
    yield
    bridge_task.cancel()
    sweep_task.cancel()


app = FastAPI(title="AeroPulse API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(flights.router)
app.include_router(incidents.router)
app.include_router(webhooks.router)
app.include_router(ocr.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"status": "ok"}
