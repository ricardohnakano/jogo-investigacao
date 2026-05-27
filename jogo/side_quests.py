"""Mini-jogos por ciclo: Mastermind, Labirinto, Maior ou Menor.

Cada equipe recebe SIDE_QUESTS_PER_CYCLE quests por ciclo.
O jogador reivindica (lock 60s), joga, recebe recompensa ao vencer.
Locks expirados são liberados na próxima consulta (lazy expiry).
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from jogo.db.models import Character, Clue, Game, SideQuest, Team
from jogo.game_data import (
    ACTION_LOCK_TIMEOUT_SECONDS,
    HIGHER_LOWER_MAX_ATTEMPTS_HARD,
    HIGHER_LOWER_MAX_ATTEMPTS_NORMAL,
    HIGHER_LOWER_RANGE_HARD,
    HIGHER_LOWER_RANGE_NORMAL,
    LABYRINTH_SIZE_HARD,
    LABYRINTH_SIZE_NORMAL,
    MASTERMIND_DIGITS_HARD,
    MASTERMIND_DIGITS_NORMAL,
    MASTERMIND_MAX_ATTEMPTS_HARD,
    MASTERMIND_MAX_ATTEMPTS_NORMAL,
    SIDE_QUESTS_PER_CYCLE,
    SideQuestDifficulty,
    SideQuestKind,
    SideQuestReward,
    SideQuestStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Maze generation (recursive backtracking)
# ---------------------------------------------------------------------------

def _generate_maze(size: int) -> list[list[int]]:
    """Retorna grade (2*size+1)×(2*size+1): 0=livre, 1=parede.

    Salas ficam nas posições ímpares: (2r+1, 2c+1).
    Paredes entre salas (r,c) e (r+dr,c+dc): (2r+1+dr, 2c+1+dc).
    """
    n = 2 * size + 1
    grid = [[1] * n for _ in range(n)]
    for r in range(size):
        for c in range(size):
            grid[r * 2 + 1][c * 2 + 1] = 0

    visited = [[False] * size for _ in range(size)]

    def carve(r: int, c: int) -> None:
        visited[r][c] = True
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        random.shuffle(dirs)
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and not visited[nr][nc]:
                grid[r * 2 + 1 + dr][c * 2 + 1 + dc] = 0
                carve(nr, nc)

    carve(0, 0)
    return grid


# ---------------------------------------------------------------------------
# State builders per kind
# ---------------------------------------------------------------------------

def _mastermind_state(difficulty: SideQuestDifficulty) -> dict:
    """Create initial Mastermind game state with secret and attempt log."""
    digits = MASTERMIND_DIGITS_HARD if difficulty == SideQuestDifficulty.HARD else MASTERMIND_DIGITS_NORMAL
    max_attempts = (
        MASTERMIND_MAX_ATTEMPTS_HARD if difficulty == SideQuestDifficulty.HARD
        else MASTERMIND_MAX_ATTEMPTS_NORMAL
    )
    secret = "".join(str(random.randint(1, 6)) for _ in range(digits))
    return {"secret": secret, "digits": digits, "max_attempts": max_attempts, "attempts": []}


def _higher_lower_state(difficulty: SideQuestDifficulty) -> dict:
    """Create initial Higher/Lower game state with secret and attempt log."""
    range_max = HIGHER_LOWER_RANGE_HARD if difficulty == SideQuestDifficulty.HARD else HIGHER_LOWER_RANGE_NORMAL
    max_attempts = (
        HIGHER_LOWER_MAX_ATTEMPTS_HARD if difficulty == SideQuestDifficulty.HARD
        else HIGHER_LOWER_MAX_ATTEMPTS_NORMAL
    )
    secret = random.randint(1, range_max)
    return {"secret": secret, "range_max": range_max, "max_attempts": max_attempts, "attempts": []}


def _labyrinth_state(difficulty: SideQuestDifficulty) -> dict:
    """Create initial Labyrinth game state with maze grid and player position."""
    size = LABYRINTH_SIZE_HARD if difficulty == SideQuestDifficulty.HARD else LABYRINTH_SIZE_NORMAL
    grid = _generate_maze(size)
    return {"size": size, "grid": grid, "pos": [0, 0], "goal": [size - 1, size - 1]}


def _make_state(kind: SideQuestKind, difficulty: SideQuestDifficulty) -> dict:
    """Create quest state dict based on quest kind and difficulty."""
    if kind == SideQuestKind.MASTERMIND:
        return _mastermind_state(difficulty)
    if kind == SideQuestKind.HIGHER_LOWER:
        return _higher_lower_state(difficulty)
    return _labyrinth_state(difficulty)


# ---------------------------------------------------------------------------
# Reward selection (60/40 split)
# ---------------------------------------------------------------------------

_REWARD_WEIGHTS = [
    (SideQuestReward.REVEAL_EXTRA_CLUE, 0.6),
    (SideQuestReward.BLOCK_OPPONENT_CHARACTER, 0.4),
]


def _pick_reward() -> SideQuestReward:
    """Randomly choose reward (60% reveal clue, 40% block opponent)."""
    roll = random.random()
    acc = 0.0
    for reward, weight in _REWARD_WEIGHTS:
        acc += weight
        if roll < acc:
            return reward
    return SideQuestReward.REVEAL_EXTRA_CLUE


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_for_cycle(session: Session, game_id: str, cycle: int) -> None:
    """Cria SIDE_QUESTS_PER_CYCLE quests para cada equipe no ciclo dado."""
    from jogo.engine import get_teams

    teams = get_teams(session, game_id)
    all_kinds = list(SideQuestKind)

    for team in teams:
        hard_count = team.side_quest_hard_count
        team.side_quest_hard_count = 0
        session.add(team)

        kinds = random.sample(all_kinds, k=min(SIDE_QUESTS_PER_CYCLE, len(all_kinds)))
        for i in range(SIDE_QUESTS_PER_CYCLE):
            kind = kinds[i % len(kinds)]
            difficulty = (
                SideQuestDifficulty.HARD if i < hard_count else SideQuestDifficulty.NORMAL
            )
            state = _make_state(kind, difficulty)
            sq = SideQuest(
                game_id=game_id,
                team_id=team.id,
                cycle=cycle,
                kind=kind,
                difficulty=difficulty,
                reward=_pick_reward(),
                state_json=json.dumps(state, ensure_ascii=False),
            )
            session.add(sq)

    session.commit()


# ---------------------------------------------------------------------------
# Lock management
# ---------------------------------------------------------------------------

def expire_stale_locks(session: Session, game_id: str) -> None:
    """Devolve ao status PENDING quests cujo lock expirou."""
    cutoff = _utcnow() - timedelta(seconds=ACTION_LOCK_TIMEOUT_SECONDS)
    stale = list(
        session.exec(
            select(SideQuest).where(
                SideQuest.game_id == game_id,
                SideQuest.status == SideQuestStatus.IN_PROGRESS,
                SideQuest.locked_at <= cutoff,  # type: ignore[operator]
            )
        ).all()
    )
    for sq in stale:
        sq.status = SideQuestStatus.PENDING
        sq.locked_by_player_id = None
        sq.locked_at = None
        session.add(sq)
    if stale:
        session.commit()


def claim(session: Session, sq: SideQuest, player_id: str) -> tuple[bool, str]:
    """Tenta reservar uma quest. Retorna (sucesso, mensagem_erro)."""
    if sq.status == SideQuestStatus.COMPLETED:
        return False, "Quest já concluída"
    if sq.status == SideQuestStatus.EXPIRED:
        return False, "Quest expirada"
    if sq.status == SideQuestStatus.IN_PROGRESS:
        if sq.locked_by_player_id == player_id:
            return True, ""
        return False, "Quest em andamento por outro jogador"
    sq.status = SideQuestStatus.IN_PROGRESS
    sq.locked_by_player_id = player_id
    sq.locked_at = _utcnow()
    session.add(sq)
    session.commit()
    return True, ""


def release(session: Session, sq: SideQuest, player_id: str) -> None:
    if sq.locked_by_player_id != player_id:
        return
    sq.status = SideQuestStatus.PENDING
    sq.locked_by_player_id = None
    sq.locked_at = None
    session.add(sq)
    session.commit()


# ---------------------------------------------------------------------------
# Submit handlers per kind
# ---------------------------------------------------------------------------

def _submit_mastermind(sq: SideQuest, body: dict) -> dict:
    """Evaluate Mastermind guess and return bulls/cows feedback."""
    state = json.loads(sq.state_json)
    secret: str = state["secret"]
    digits: int = state["digits"]
    max_attempts: int = state["max_attempts"]
    guess = str(body.get("guess", ""))

    if len(guess) != digits or not guess.isdigit():
        return {"ok": False, "error": f"Palpite deve ter exatamente {digits} dígitos (1–6)"}

    bulls = sum(g == s for g, s in zip(guess, secret))
    cows = sum(min(guess.count(d), secret.count(d)) for d in set(guess)) - bulls
    state["attempts"].append({"guess": guess, "bulls": bulls, "cows": cows})
    won = bulls == digits
    lost = not won and len(state["attempts"]) >= max_attempts

    return {
        "ok": True, "bulls": bulls, "cows": cows,
        "won": won, "lost": lost,
        "attempts_used": len(state["attempts"]),
        "max_attempts": max_attempts,
        "state": state,
    }


def _submit_higher_lower(sq: SideQuest, body: dict) -> dict:
    """Evaluate Higher/Lower guess and return hint (acertou/maior/menor)."""
    state = json.loads(sq.state_json)
    secret: int = state["secret"]
    range_max: int = state["range_max"]
    max_attempts: int = state["max_attempts"]

    try:
        guess = int(body.get("guess", 0))
    except (TypeError, ValueError):
        return {"ok": False, "error": "Palpite deve ser um número inteiro"}

    if guess < 1 or guess > range_max:
        return {"ok": False, "error": f"Número deve ser entre 1 e {range_max}"}

    if guess == secret:
        result, won = "acertou", True
    elif guess < secret:
        result, won = "maior", False
    else:
        result, won = "menor", False

    state["attempts"].append({"guess": guess, "result": result})
    lost = not won and len(state["attempts"]) >= max_attempts

    return {
        "ok": True, "result": result, "won": won, "lost": lost,
        "attempts_used": len(state["attempts"]),
        "max_attempts": max_attempts,
        "state": state,
    }


_MAZE_DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def _submit_labyrinth(sq: SideQuest, body: dict) -> dict:
    """Process Labyrinth move and return updated position or goal reached."""
    state = json.loads(sq.state_json)
    r, c = state["pos"]
    size: int = state["size"]
    grid: list[list[int]] = state["grid"]
    goal: list[int] = state["goal"]
    move = str(body.get("move", ""))

    if move not in _MAZE_DIRS:
        return {"ok": False, "error": "Movimento inválido (up/down/left/right)"}

    dr, dc = _MAZE_DIRS[move]
    new_r, new_c = r + dr, c + dc
    wall_r, wall_c = r * 2 + 1 + dr, c * 2 + 1 + dc

    if not (0 <= new_r < size and 0 <= new_c < size) or grid[wall_r][wall_c] == 1:
        return {"ok": True, "moved": False, "pos": [r, c], "won": False, "state": state}

    state["pos"] = [new_r, new_c]
    won = [new_r, new_c] == goal
    return {"ok": True, "moved": True, "pos": [new_r, new_c], "won": won, "state": state}


def submit(session: Session, game: Game, sq: SideQuest, body: dict) -> dict:
    """Processa envio do jogador. Aplica recompensa se venceu."""
    if sq.status != SideQuestStatus.IN_PROGRESS:
        return {"ok": False, "error": "Quest não está em andamento"}

    if sq.kind == SideQuestKind.MASTERMIND:
        result = _submit_mastermind(sq, body)
    elif sq.kind == SideQuestKind.HIGHER_LOWER:
        result = _submit_higher_lower(sq, body)
    else:
        result = _submit_labyrinth(sq, body)

    if not result.get("ok"):
        return result

    sq.state_json = json.dumps(result["state"], ensure_ascii=False)

    if result.get("won"):
        sq.status = SideQuestStatus.COMPLETED
        sq.completed_at = _utcnow()
        sq.locked_by_player_id = None
        sq.locked_at = None
        session.add(sq)
        result["reward_result"] = _apply_reward(session, game, sq)
    elif result.get("lost"):
        sq.status = SideQuestStatus.EXPIRED
        sq.locked_by_player_id = None
        sq.locked_at = None
        session.add(sq)
    else:
        sq.locked_at = _utcnow()
        session.add(sq)

    session.commit()
    return result


# ---------------------------------------------------------------------------
# Reward application
# ---------------------------------------------------------------------------

def _apply_reward(session: Session, game: Game, sq: SideQuest) -> dict:
    """Apply quest reward: reveal clue or block opponent character."""
    if sq.reward == SideQuestReward.REVEAL_EXTRA_CLUE:
        clue = session.exec(
            select(Clue)
            .where(
                Clue.game_id == game.id,
                Clue.revealed_at_cycle.is_(None),  # type: ignore[attr-defined]
            )
            .order_by(Clue.id)
            .limit(1)
        ).first()
        if clue:
            clue.revealed_at_cycle = game.current_cycle
            session.add(clue)
            return {"kind": "reveal_extra_clue", "clue_id": clue.id}
        return {"kind": "reveal_extra_clue", "clue_id": None}

    # BLOCK_OPPONENT_CHARACTER
    all_teams = list(session.exec(select(Team).where(Team.game_id == game.id)).all())
    opponent_ids = [t.id for t in all_teams if t.id != sq.team_id]
    if not opponent_ids:
        return {"kind": "block_opponent_character", "character_id": None}

    target_team_id = random.choice(opponent_ids)
    target_team = session.get(Team, target_team_id)
    candidates = list(
        session.exec(
            select(Character).where(
                Character.game_id == game.id,
                Character.equipe == target_team.equipe,
                Character.eliminated == False,  # noqa: E712
                Character.blocked_until_cycle.is_(None),  # type: ignore[attr-defined]
            )
        ).all()
    )
    if candidates:
        target = random.choice(candidates)
        target.blocked_until_cycle = game.current_cycle + 1
        session.add(target)
        return {"kind": "block_opponent_character", "character_id": target.id}
    return {"kind": "block_opponent_character", "character_id": None}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def quests_for_team(
    session: Session, game_id: str, team_id: int, cycle: int
) -> list[SideQuest]:
    """Fetch all side quests for team in given cycle."""
    return list(
        session.exec(
            select(SideQuest).where(
                SideQuest.game_id == game_id,
                SideQuest.team_id == team_id,
                SideQuest.cycle == cycle,
            ).order_by(SideQuest.id)
        ).all()
    )
