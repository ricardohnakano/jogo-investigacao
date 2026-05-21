from datetime import timedelta
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import func
from sqlmodel import Session, select

from jogo import actions as actions_mod
from jogo import clues as clues_mod
from jogo import engine
from jogo.config import settings
from jogo.db.models import Action, Character, Game, GameStatus, Player, SideQuest, Team
from jogo.db.session import get_session
from jogo.game_data import (
    PROFISSAO_INFO,
    PROFISSOES_POR_EQUIPE,
    ClueCategory,
    Equipe,
    FuncaoEspecial,
    Profissao,
    SideQuestStatus,
    TOTAL_CYCLES,
)
from jogo.realtime import manager
from jogo.templates import templates
from jogo.utils.qr import generate_qr_data_url, get_local_ip

router = APIRouter()


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
    response = RedirectResponse(url=f"/jogo/{game.id}", status_code=303)
    response.set_cookie("host_token", game.host_token, max_age=86400 * 7, httponly=True)
    return response


@router.get("/jogo/{game_id}", response_class=HTMLResponse)
def game_entry(
    game_id: str,
    request: Request,
    host_token: str = Cookie(default=""),
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

    if game.status == GameStatus.GENERATING:
        return templates.TemplateResponse(
            request, "generating.html", {"game": game}
        )
    if game.status == GameStatus.FINISHED:
        ctx = _result_context(session, game, is_host=_host_auth(game, host_token))
        return templates.TemplateResponse(request, "result.html", ctx)
    if game.status == GameStatus.PLAYING:
        ctx = _playing_context(session, game)
        return templates.TemplateResponse(request, "playing.html", ctx)

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
    host_token: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    team = session.get(Team, team_id)
    if not game or not team or team.game_id != game.id:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    engine.sync_status(session, game)

    if game.status == GameStatus.GENERATING:
        return templates.TemplateResponse(
            request, "generating.html", {"game": game, "team": team}
        )
    if game.status == GameStatus.FINISHED:
        ctx = _result_context(session, game, is_host=_host_auth(game, host_token))
        return templates.TemplateResponse(request, "result.html", ctx)
    if game.status == GameStatus.PLAYING:
        ctx = _playing_context(session, game, team=team)
        return templates.TemplateResponse(request, "playing.html", ctx)

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

    if game.status == GameStatus.GENERATING:
        return templates.TemplateResponse(
            request,
            "generating.html",
            {"game": game, "team": team, "player": player},
        )
    if game.status == GameStatus.FINISHED:
        ctx = _result_context(session, game)
        return templates.TemplateResponse(request, "result.html", ctx)
    if game.status == GameStatus.PLAYING:
        ctx = _playing_context(session, game, team=team, player=player)
        return templates.TemplateResponse(request, "playing.html", ctx)

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
        and game.status == GameStatus.READY_CHECK
    ):
        engine.start_generation(session, game)
        engine.schedule_generation_task(game.id)
        reload_html = (
            '<div id="reload-trigger" hx-swap-oob="outerHTML">'
            '<script>setTimeout(()=>location.reload(),200)</script>'
            '</div>'
        )
        await manager.broadcast(game.id, reload_html)

    await _broadcast_update(session, game)
    return RedirectResponse(url="/jogador", status_code=303)


def _get_character_for_player(
    session: Session, player: Player
) -> Optional[Character]:
    if not player.profissao:
        return None
    return session.exec(
        select(Character).where(
            Character.game_id == session.get(Team, player.team_id).game_id,
            Character.profissao == player.profissao,
        )
    ).first()


def _playing_context(
    session: Session,
    game: Game,
    team: Optional[Team] = None,
    player: Optional[Player] = None,
) -> dict:
    characters = list(
        session.exec(
            select(Character).where(Character.game_id == game.id).order_by(Character.id)
        ).all()
    )
    clues_by_cat = clues_mod.visible_clues_by_category(session, game.id)
    all_teams = engine.get_teams(session, game.id)

    character: Optional[Character] = None
    action_kind: Optional[str] = None
    action_targets: dict = {}

    if player and team:
        character = _get_character_for_player(session, player)
        if character and not character.action_used and not character.eliminated:
            kind = actions_mod.action_kind_for(character.profissao)
            if kind:
                action_kind = kind.value
                ak = actions_mod.ActionKind
                if kind == ak.ELIMINATE_CHARACTER:
                    action_targets["target_characters"] = [
                        c for c in characters if not c.eliminated and c.id != character.id
                    ]
                elif kind == ak.INTERROGATE:
                    action_targets["target_characters"] = [
                        c for c in characters if not c.eliminated
                    ]
                elif kind == ak.CLASSIFY_CLUE:
                    cat = actions_mod.category_for(character.profissao)
                    action_targets["classifiable_clues"] = [
                        c for c in clues_by_cat.get(cat, []) if not c.classified
                    ]
                    action_targets["classify_category"] = cat.value if cat else ""
                elif kind in (
                    ak.STEAL_ELIMINATED_CLUES,
                    ak.BLOCK_OPPONENT_CLASSIFY,
                    ak.LOCK_SIDE_QUESTS_HARD,
                ):
                    action_targets["opponent_teams"] = [
                        t for t in all_teams if t.id != team.id
                    ]

    return {
        "game": game,
        "team": team,
        "player": player,
        "character": character,
        "characters": characters,
        "clues_objeto_local": clues_by_cat.get(
            clues_mod.ClueCategory.OBJETO_LOCAL, []
        ),
        "clues_linha_tempo": clues_by_cat.get(
            clues_mod.ClueCategory.LINHA_TEMPO, []
        ),
        "clues_ficha_civil": clues_by_cat.get(
            clues_mod.ClueCategory.FICHA_CIVIL, []
        ),
        "image_stage": engine.current_image_stage(game),
        "remaining_seconds": engine.cycle_remaining_seconds(game),
        "cycles_total": TOTAL_CYCLES,
        "action_kind": action_kind,
        "all_teams": all_teams,
        **action_targets,
    }


# ---------------------------------------------------------------------------
# Result context
# ---------------------------------------------------------------------------

_FUNCAO_LABEL = {
    FuncaoEspecial.CRIMINOSO: "Criminoso",
    FuncaoEspecial.VITIMA: "Vítima",
    FuncaoEspecial.CUMPLICE: "Cúmplice",
}

_CATEGORIA_LABEL = {
    ClueCategory.OBJETO_LOCAL: "Objeto / Local",
    ClueCategory.FICHA_CIVIL: "Ficha Civil",
    ClueCategory.LINHA_TEMPO: "Linha do Tempo",
}

_FUNCAO_ORDER = {
    FuncaoEspecial.CRIMINOSO: 0,
    FuncaoEspecial.VITIMA: 1,
    FuncaoEspecial.CUMPLICE: 2,
}


def _classified_by_map(session: Session, game_id: str, all_teams: list[Team]) -> dict:
    team_map = {t.id: t for t in all_teams}
    from jogo.db.models import Clue
    clues = list(
        session.exec(
            select(Clue).where(
                Clue.game_id == game_id,
                Clue.classified_by_team_id.isnot(None),  # type: ignore[attr-defined]
            )
        ).all()
    )
    result = {}
    for c in clues:
        t = team_map.get(c.classified_by_team_id)
        if t:
            from jogo.game_data import EQUIPE_LABEL
            result[c.id] = EQUIPE_LABEL[t.equipe]
    return result


def _result_context(session: Session, game: Game, is_host: bool = False) -> dict:
    from jogo.db.models import Clue

    characters = list(
        session.exec(
            select(Character).where(Character.game_id == game.id).order_by(Character.id)
        ).all()
    )
    key_characters = sorted(
        [c for c in characters if c.funcao_especial != FuncaoEspecial.NENHUMA],
        key=lambda c: _FUNCAO_ORDER.get(c.funcao_especial, 99),
    )
    all_clues = list(
        session.exec(
            select(Clue)
            .where(
                Clue.game_id == game.id,
                Clue.revealed_at_cycle.isnot(None),  # type: ignore[attr-defined]
            )
            .order_by(Clue.categoria, Clue.id)
        ).all()
    )
    all_teams = engine.get_teams(session, game.id)
    winner_team = next((t for t in all_teams if t.id == game.winning_team_id), None)
    classified_by = _classified_by_map(session, game.id, all_teams)

    team_stats = []
    for team in all_teams:
        quests_done = session.exec(
            select(func.count()).where(
                SideQuest.game_id == game.id,
                SideQuest.team_id == team.id,
                SideQuest.status == SideQuestStatus.COMPLETED,
            )
        ).one()
        actions_used = session.exec(
            select(func.count()).where(
                Action.game_id == game.id,
                Action.team_id == team.id,
            )
        ).one()
        team_stats.append(
            SimpleNamespace(team=team, quests_done=quests_done, actions_used=actions_used)
        )

    return {
        "game": game,
        "key_characters": key_characters,
        "all_clues": all_clues,
        "winner_team": winner_team,
        "all_teams": all_teams,
        "classified_by": classified_by,
        "team_stats": team_stats,
        "funcao_label": _FUNCAO_LABEL,
        "categoria_label": _CATEGORIA_LABEL,
        "is_host": is_host,
    }


# ---------------------------------------------------------------------------
# Host panel helpers
# ---------------------------------------------------------------------------

def _host_auth(game: Game, host_token: str) -> bool:
    return bool(host_token) and host_token == game.host_token


def _host_context(session: Session, game: Game) -> dict:
    characters = list(
        session.exec(
            select(Character).where(Character.game_id == game.id).order_by(Character.id)
        ).all()
    )
    char_map = {c.id: c for c in characters}
    key_characters = sorted(
        [c for c in characters if c.funcao_especial != FuncaoEspecial.NENHUMA],
        key=lambda c: _FUNCAO_ORDER.get(c.funcao_especial, 99),
    )
    all_teams = engine.get_teams(session, game.id)
    team_map = {t.id: t for t in all_teams}
    teams_data = [
        SimpleNamespace(team=t, players=engine.get_players(session, t.id))
        for t in all_teams
    ]
    actions = list(
        session.exec(
            select(Action)
            .where(Action.game_id == game.id)
            .order_by(Action.cycle, Action.id)
        ).all()
    )
    action_log = []
    for a in actions:
        char = char_map.get(a.character_id)
        team = team_map.get(a.team_id)
        target = char_map.get(a.target_character_id) if a.target_character_id else None
        action_log.append(
            SimpleNamespace(
                action=a,
                char_nome=f"{char.nome} {char.sobrenome}" if char else "?",
                team_equipe=team.equipe if team else None,
                target_nome=(
                    f"{target.nome} {target.sobrenome}" if target else None
                ),
            )
        )
    return {
        "game": game,
        "key_characters": key_characters,
        "teams_data": teams_data,
        "action_log": action_log,
        "funcao_label": _FUNCAO_LABEL,
    }


@router.get("/jogo/{game_id}/host", response_class=HTMLResponse)
def host_panel(
    game_id: str,
    request: Request,
    host_token: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game:
        raise HTTPException(status_code=404)
    if not _host_auth(game, host_token):
        raise HTTPException(status_code=403, detail="Token de host inválido")
    ctx = _host_context(session, game)
    return templates.TemplateResponse(request, "host.html", ctx)


@router.post("/jogo/{game_id}/host/force-cycle")
def host_force_cycle(
    game_id: str,
    host_token: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game or not _host_auth(game, host_token):
        raise HTTPException(status_code=403)
    if game.status != GameStatus.PLAYING:
        raise HTTPException(status_code=400, detail="Jogo não está em andamento")
    from jogo.engine import CYCLE_DURATION_SECONDS, _utcnow
    game.cycle_started_at = _utcnow() - timedelta(seconds=CYCLE_DURATION_SECONDS)
    session.add(game)
    session.commit()
    return RedirectResponse(url=f"/jogo/{game_id}/host", status_code=303)


@router.post("/jogo/{game_id}/host/restart-generation")
def host_restart_generation(
    game_id: str,
    host_token: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game or not _host_auth(game, host_token):
        raise HTTPException(status_code=403)
    if game.status != GameStatus.GENERATING:
        raise HTTPException(status_code=400, detail="Jogo não está em geração")
    engine.force_schedule_generation_task(game.id)
    return RedirectResponse(url=f"/jogo/{game_id}/host", status_code=303)


@router.post("/jogo/{game_id}/host/finish")
async def host_finish_game(
    game_id: str,
    host_token: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game or not _host_auth(game, host_token):
        raise HTTPException(status_code=403)
    if game.status not in (GameStatus.PLAYING, GameStatus.COUNTDOWN):
        raise HTTPException(status_code=400, detail="Jogo não pode ser finalizado agora")
    engine.finish_game(session, game, winner_team_id=None)
    from jogo.engine import _RELOAD_HTML
    await manager.broadcast(game.id, _RELOAD_HTML)
    return RedirectResponse(url=f"/jogo/{game_id}/host", status_code=303)


# ---------------------------------------------------------------------------
# Gameplay endpoints
# ---------------------------------------------------------------------------

@router.post("/jogo/{game_id}/acao")
async def perform_action(
    game_id: str,
    target_character_id: Optional[int] = Form(default=None),
    target_clue_id: Optional[int] = Form(default=None),
    target_team_id: Optional[int] = Form(default=None),
    classified_veracity: Optional[str] = Form(default=None),
    player_id: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    if not player_id:
        raise HTTPException(status_code=401, detail="Sem sessão de jogador")

    game = session.get(Game, game_id.upper())
    player = session.get(Player, player_id)
    if not game or not player:
        raise HTTPException(status_code=404)

    team = session.get(Team, player.team_id)
    if not team or team.game_id != game.id:
        raise HTTPException(status_code=403)

    character = _get_character_for_player(session, player)
    if not character:
        raise HTTPException(status_code=400, detail="Personagem não encontrado")

    body = {
        "target_character_id": target_character_id,
        "target_clue_id": target_clue_id,
        "target_team_id": target_team_id,
        "classified_veracity": classified_veracity,
    }
    result = actions_mod.execute_action(session, game, character, team, body)

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erro"))

    # Broadcast eliminação para toda a sala; outros efeitos via reload de ciclo
    kind = result.get("kind", "")
    if kind == "eliminate_character":
        session.refresh(game)
        chars = list(
            session.exec(
                select(Character).where(Character.game_id == game.id).order_by(Character.id)
            ).all()
        )
        html = templates.get_template("_characters_grid.html").render(
            {"characters": chars, "PROFISSAO_INFO": PROFISSAO_INFO}
        )
        await manager.broadcast(game.id, html)

    return RedirectResponse(url="/jogador", status_code=303)


@router.post("/jogo/{game_id}/acusacao")
async def make_accusation(
    game_id: str,
    accused_character_id: int = Form(...),
    player_id: str = Cookie(default=""),
    session: Session = Depends(get_session),
):
    if not player_id:
        raise HTTPException(status_code=401)

    game = session.get(Game, game_id.upper())
    player = session.get(Player, player_id)
    if not game or not player or game.status != GameStatus.PLAYING:
        raise HTTPException(status_code=404)

    team = session.get(Team, player.team_id)
    if not team or team.game_id != game.id:
        raise HTTPException(status_code=403)

    if team.accusation_used:
        raise HTTPException(status_code=409, detail="Equipe já fez sua acusação")

    accused = session.get(Character, accused_character_id)
    if not accused or accused.game_id != game.id:
        raise HTTPException(status_code=404, detail="Personagem não encontrado")

    correct = accused.funcao_especial == FuncaoEspecial.CRIMINOSO
    team.accusation_used = True
    team.accusation_correct = correct
    team.accused_criminoso_character_id = accused.id
    session.add(team)
    session.commit()

    if correct:
        engine.finish_game(session, game, winner_team_id=team.id)
        await manager.broadcast(game.id, (
            '<div id="reload-trigger" hx-swap-oob="outerHTML">'
            "<script>setTimeout(()=>location.reload(),200)</script>"
            "</div>"
        ))

    return RedirectResponse(url="/jogador", status_code=303)


@router.get("/jogo/{game_id}/personagens", response_class=HTMLResponse)
def personagens(
    game_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game:
        raise HTTPException(status_code=404)
    characters = list(
        session.exec(
            select(Character).where(Character.game_id == game.id).order_by(Character.id)
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "personagens.html",
        {"game": game, "characters": characters},
    )


@router.get("/jogo/{game_id}/ciclo/info")
def ciclo_info(
    game_id: str,
    session: Session = Depends(get_session),
):
    game = session.get(Game, game_id.upper())
    if not game:
        raise HTTPException(status_code=404)
    return {
        "current_cycle": game.current_cycle,
        "remaining_seconds": engine.cycle_remaining_seconds(game),
        "image_stage": engine.current_image_stage(game),
        "status": game.status.value,
    }


@router.get("/jogo/{game_id}/image/{stage}")
def crime_image(
    game_id: str,
    stage: int,
    session: Session = Depends(get_session),
):
    """Serve o estágio `stage` (1-6) da imagem degradada, ou o original (stage=0)."""
    game = session.get(Game, game_id.upper())
    if not game or not game.image_ready:
        raise HTTPException(status_code=404, detail="Imagem não disponível")

    from jogo import image as img_module

    if stage == 0:
        path = img_module.original_path(game.id)
    elif 1 <= stage <= len(img_module.IMAGE_STAGES):
        path = img_module.stage_path(game.id, stage)
    else:
        raise HTTPException(status_code=400, detail="Estágio inválido (use 0-6)")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo de imagem não encontrado")

    return FileResponse(path, media_type="image/png")


@router.get("/health")
def health() -> Response:
    return Response(content="ok", media_type="text/plain")
