from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from jogo.config import settings
from jogo.db.models import Game
from jogo.db.session import get_session
from jogo.utils.qr import generate_qr_data_url, get_local_ip

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def lobby(request: Request):
    local_url = f"http://{get_local_ip()}:{settings.port}"
    qr_data_url = generate_qr_data_url(local_url)
    return templates.TemplateResponse(
        request,
        "lobby.html",
        {"local_url": local_url, "qr_data_url": qr_data_url},
    )


@router.post("/games")
def create_game(session: Session = Depends(get_session)):
    game = Game()
    session.add(game)
    session.commit()
    session.refresh(game)
    return RedirectResponse(
        url=f"/jogo/{game.id}?host={game.host_token}",
        status_code=303,
    )


@router.get("/jogo/{game_id}", response_class=HTMLResponse)
def team_page(
    game_id: str,
    request: Request,
    host: str = "",
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    is_host = host == game.host_token
    return templates.TemplateResponse(
        request,
        "team.html",
        {"game": game, "is_host": is_host},
    )
