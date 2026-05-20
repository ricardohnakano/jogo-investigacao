from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from jogo.api import pages, ws
from jogo.config import settings
from jogo.db.models import Game, GameStatus
from jogo.db.session import engine as db_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Rehidrata tasks de ciclo para partidas em andamento (resiliência a restart)
    from jogo import engine as game_engine
    with Session(db_engine) as session:
        active = session.exec(
            select(Game).where(Game.status == GameStatus.PLAYING)
        ).all()
        for game in active:
            game_engine.schedule_cycle_task(game.id)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(pages.router)
app.include_router(ws.router)
