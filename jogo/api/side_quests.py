"""Endpoints HTTP para side quests (mini-jogos por ciclo)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from jogo import side_quests as sq_mod
from jogo.db.models import Game, GameStatus, Player, SideQuest, Team
from jogo.db.session import engine
from jogo.game_data import SideQuestStatus
from jogo.templates import templates

router = APIRouter(prefix="/jogo/{game_id}/side-quests")

QUEST_KIND_LABEL = {
    "mastermind": "Mastermind",
    "labyrinth": "Labirinto",
    "higher_lower": "Maior ou Menor",
}

QUEST_DIFF_LABEL = {"normal": "Normal", "hard": "Difícil"}

QUEST_REWARD_LABEL = {
    "reveal_extra_clue": "Revelar pista extra",
    "block_opponent_character": "Bloquear personagem adversário",
}

QUEST_STATUS_LABEL = {
    "pending": "Disponível",
    "in_progress": "Em andamento",
    "completed": "Concluído",
    "expired": "Expirado",
}


def _player_and_team(
    game_id: str, session: Session, player_id: str | None
) -> tuple[Player | None, Team | None]:
    if not player_id:
        return None, None
    player = session.get(Player, player_id)
    if not player:
        return None, None
    team = session.get(Team, player.team_id)
    if not team or team.game_id != game_id:
        return None, None
    return player, team


def _ctx(extra: dict | None = None) -> dict:
    base = {
        "QUEST_KIND_LABEL": QUEST_KIND_LABEL,
        "QUEST_DIFF_LABEL": QUEST_DIFF_LABEL,
        "QUEST_REWARD_LABEL": QUEST_REWARD_LABEL,
        "QUEST_STATUS_LABEL": QUEST_STATUS_LABEL,
    }
    if extra:
        base.update(extra)
    return base


@router.get("", response_class=HTMLResponse)
def list_quests(
    game_id: str,
    request: Request,
    player_id: str | None = Cookie(default=None),
):
    with Session(engine) as session:
        game = session.get(Game, game_id)
        if not game or game.status != GameStatus.PLAYING:
            raise HTTPException(404)
        player, team = _player_and_team(game_id, session, player_id)
        if not team:
            return HTMLResponse('<p class="muted">Sem equipe.</p>')

        sq_mod.expire_stale_locks(session, game_id)
        quests = sq_mod.quests_for_team(session, game_id, team.id, game.current_cycle)

        return templates.TemplateResponse(
            request,
            "_side_quests_list.html",
            _ctx({"game": game, "player": player, "quests": quests}),
        )


@router.post("/{sq_id}/claim", response_class=HTMLResponse)
def claim_quest(
    game_id: str,
    sq_id: int,
    request: Request,
    player_id: str | None = Cookie(default=None),
):
    with Session(engine) as session:
        game = session.get(Game, game_id)
        if not game or game.status != GameStatus.PLAYING:
            raise HTTPException(404)
        player, team = _player_and_team(game_id, session, player_id)
        if not player or not team:
            raise HTTPException(403, "Sem equipe")

        sq = session.get(SideQuest, sq_id)
        if not sq or sq.game_id != game_id or sq.team_id != team.id:
            raise HTTPException(404)

        sq_mod.expire_stale_locks(session, game_id)
        ok, err = sq_mod.claim(session, sq, player.id)
        if not ok:
            return HTMLResponse(f'<p class="error">{err}</p>', status_code=400)

        session.refresh(sq)
        state = json.loads(sq.state_json)
        return templates.TemplateResponse(
            request,
            "_side_quest_board.html",
            _ctx({"game": game, "sq": sq, "state": state}),
        )


@router.post("/{sq_id}/submit", response_class=HTMLResponse)
async def submit_quest(
    game_id: str,
    sq_id: int,
    request: Request,
    player_id: str | None = Cookie(default=None),
):
    form = await request.form()
    body = dict(form)

    with Session(engine) as session:
        game = session.get(Game, game_id)
        if not game or game.status != GameStatus.PLAYING:
            raise HTTPException(404)
        player, team = _player_and_team(game_id, session, player_id)
        if not player or not team:
            raise HTTPException(403)

        sq = session.get(SideQuest, sq_id)
        if not sq or sq.game_id != game_id or sq.team_id != team.id:
            raise HTTPException(404)
        if sq.locked_by_player_id != player.id:
            return HTMLResponse('<p class="error">Não é sua quest.</p>', status_code=403)

        result = sq_mod.submit(session, game, sq, body)
        if not result.get("ok"):
            state = json.loads(sq.state_json)
            return templates.TemplateResponse(
                request,
                "_side_quest_board.html",
                _ctx({"game": game, "sq": sq, "state": state, "error": result.get("error")}),
            )

        session.refresh(sq)
        state = json.loads(sq.state_json)
        reward_result = result.get("reward_result")
        return templates.TemplateResponse(
            request,
            "_side_quest_board.html",
            _ctx({
                "game": game, "sq": sq, "state": state,
                "last_result": result, "reward_result": reward_result,
            }),
        )


@router.post("/{sq_id}/release", response_class=HTMLResponse)
def release_quest(
    game_id: str,
    sq_id: int,
    request: Request,
    player_id: str | None = Cookie(default=None),
):
    with Session(engine) as session:
        game = session.get(Game, game_id)
        if not game or game.status != GameStatus.PLAYING:
            raise HTTPException(404)
        player, team = _player_and_team(game_id, session, player_id)
        if not player or not team:
            raise HTTPException(403)

        sq = session.get(SideQuest, sq_id)
        if not sq or sq.game_id != game_id or sq.team_id != team.id:
            raise HTTPException(404)

        sq_mod.release(session, sq, player.id)
        quests = sq_mod.quests_for_team(session, game_id, team.id, game.current_cycle)
        return templates.TemplateResponse(
            request,
            "_side_quests_list.html",
            _ctx({"game": game, "player": player, "quests": quests}),
        )
