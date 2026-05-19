from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from jogo import engine
from jogo.config import settings
from jogo.db.models import Game, GameStatus, Player, Team
from jogo.db.session import get_session
from jogo.game_data import (
    EQUIPE_LABEL,
    PROFISSAO_INFO,
    PROFISSOES_POR_EQUIPE,
    Equipe,
    Profissao,
)
from jogo.realtime import manager
from jogo.utils.qr import generate_qr_data_url, get_local_ip

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.globals["EQUIPE_LABEL"] = EQUIPE_LABEL
templates.env.globals["PROFISSAO_INFO"] = PROFISSAO_INFO


def _local_url(path: str = "") -> str:
    return f"http://{get_local_ip()}:{settings.port}{path}"


def _ctx_roster(session: Session, game: Game) -> dict:
    teams = engine.get_teams(session, game.id)
    teams_data = []
    for t in teams:
        players = engine.get_players(session, t.id)
        teams_data.append({"team": t, "players": players})
    return {
        "game": game,
        "teams_data": teams_data,
        "can_start": engine.can_start(session, game.id),
    }


async def _broadcast_update(session: Session, game: Game) -> None:
    engine.sync_status(session, game)
    ctx = _ctx_roster(session, game)
    html = templates.get_template("_ws_update.html").render(ctx)
    await manager.broadcast(game.id, html)


@router.get("/", response_class=HTMLResponse)
def lobby(request: Request):
    return templates.TemplateResponse(
        request,
        "lobby.html",
        {"local_url": _local_url(), "qr_data_url": generate_qr_data_url(_local_url())},
    )


@router.post("/games")
def create_game(session: Session = Depends(get_session)):
    game = Game()
    session.add(game)
    session.commit()
    session.refresh(game)
    return RedirectResponse(url=f"/jogo/{game.id}", status_code=303)


@router.get("/jogo/{game_id}", response_class=HTMLResponse)
def game_entry(
    game_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    """Tela do computador: escolhe equipe ou mostra status geral."""
    game = session.get(Game, game_id.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    engine.sync_status(session, game)
    teams = engine.get_teams(session, game.id)
    taken = {t.equipe for t in teams}
    available = [e for e in Equipe if e not in taken]

    if game.status in (GameStatus.PLAYING, GameStatus.COUNTDOWN, GameStatus.FINISHED):
        return templates.TemplateResponse(
            request, "playing.html", {"game": game}
        )

    return templates.TemplateResponse(
        request,
        "game_entry.html",
        {
            "game": game,
            "available": available,
            "taken": taken,
            "teams": teams,
        },
    )


@router.post("/jogo/{game_id}/equipe")
async def pick_equipe(
    game_id: str,
    equipe: Equipe = Form(...),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    existing = [t for t in engine.get_teams(session, game.id) if t.equipe == equipe]
    if existing:
        return RedirectResponse(
            url=f"/jogo/{game.id}/sala/{existing[0].id}", status_code=303
        )

    team = Team(game_id=game.id, equipe=equipe)
    session.add(team)
    session.commit()
    session.refresh(team)

    await _broadcast_update(session, game)
    return RedirectResponse(
        url=f"/jogo/{game.id}/sala/{team.id}", status_code=303
    )


@router.get("/jogo/{game_id}/sala/{team_id}", response_class=HTMLResponse)
def team_room(
    game_id: str,
    team_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    team = session.get(Team, team_id)
    if not game or not team or team.game_id != game.id:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    engine.sync_status(session, game)

    if game.status in (GameStatus.PLAYING, GameStatus.COUNTDOWN, GameStatus.FINISHED):
        return templates.TemplateResponse(
            request, "playing.html", {"game": game, "team": team}
        )

    join_url = _local_url(f"/entrar/{game.id}/sala/{team.id}")
    return templates.TemplateResponse(
        request,
        "team_room.html",
        {
            "game": game,
            "team": team,
            "join_url": join_url,
            "qr_data_url": generate_qr_data_url(join_url),
            **_ctx_roster(session, game),
        },
    )


@router.get("/entrar/{game_id}/sala/{team_id}", response_class=HTMLResponse)
def player_landing(
    game_id: str,
    team_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    team = session.get(Team, team_id)
    if not game or not team or team.game_id != game.id:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    return templates.TemplateResponse(
        request, "player_join.html", {"game": game, "team": team}
    )


@router.post("/entrar/{game_id}/sala/{team_id}")
async def join_team(
    game_id: str,
    team_id: int,
    nome: str = Form(...),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    team = session.get(Team, team_id)
    if not game or not team or team.game_id != game.id:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    player = Player(team_id=team.id, nome=nome.strip()[:40])
    session.add(player)
    session.commit()
    session.refresh(player)

    await _broadcast_update(session, game)

    response = RedirectResponse(url="/jogador", status_code=303)
    response.set_cookie("player_id", player.id, max_age=86400, httponly=True)
    return response


@router.get("/jogador", response_class=HTMLResponse)
def player_page(
    request: Request,
    player_id: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    if not player_id:
        return RedirectResponse(url="/", status_code=303)

    player = session.get(Player, player_id)
    if not player:
        response = RedirectResponse(url="/", status_code=303)
        response.delete_cookie("player_id")
        return response

    team = session.get(Team, player.team_id)
    game = session.get(Game, team.game_id) if team else None
    if not team or not game:
        raise HTTPException(status_code=404, detail="Jogo ou equipe não encontrados")

    engine.sync_status(session, game)

    if game.status in (GameStatus.PLAYING, GameStatus.COUNTDOWN, GameStatus.FINISHED):
        return templates.TemplateResponse(
            request,
            "playing.html",
            {"game": game, "team": team, "player": player},
        )

    teammates = engine.get_players(session, team.id)
    taken_profs = {
        p.profissao for p in teammates
        if p.profissao and p.id != player.id
    }
    available_profs = [
        p for p in PROFISSOES_POR_EQUIPE[team.equipe] if p not in taken_profs
    ]

    return templates.TemplateResponse(
        request,
        "player.html",
        {
            "game": game,
            "team": team,
            "player": player,
            "available_profs": available_profs,
            "teammates": teammates,
        },
    )


@router.post("/jogador/profissao")
async def set_profission(
    profissao: Profissao = Form(...),
    player_id: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    if not player_id:
        raise HTTPException(status_code=401, detail="Sem sessão de jogador")
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jogador não encontrado")

    team = session.get(Team, player.team_id)
    if profissao not in PROFISSOES_POR_EQUIPE[team.equipe]:
        raise HTTPException(status_code=400, detail="Profissão não pertence à equipe")

    teammates = engine.get_players(session, team.id)
    if any(p.profissao == profissao and p.id != player.id for p in teammates):
        raise HTTPException(status_code=409, detail="Profissão já escolhida")

    player.profissao = profissao
    session.add(player)
    session.commit()

    game = session.get(Game, team.game_id)
    await _broadcast_update(session, game)
    return RedirectResponse(url="/jogador", status_code=303)


@router.post("/jogador/pronto")
async def toggle_ready(
    player_id: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    if not player_id:
        raise HTTPException(status_code=401, detail="Sem sessão de jogador")
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jogador não encontrado")
    if not player.profissao:
        raise HTTPException(status_code=400, detail="Escolha uma profissão antes")

    player.ready = not player.ready
    session.add(player)
    session.commit()

    team = session.get(Team, player.team_id)
    game = session.get(Game, team.game_id)

    if (
        engine.can_start(session, game.id)
        and game.status != GameStatus.COUNTDOWN
    ):
        engine.start_countdown(session, game)
        engine.schedule_countdown_task(game.id)

    await _broadcast_update(session, game)
    return RedirectResponse(url="/jogador", status_code=303)


@router.get("/health")
def health() -> Response:
    return Response(content="ok", media_type="text/plain")
