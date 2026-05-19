import secrets
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel

from jogo.game_data import Equipe, Profissao


class GameStatus(str, Enum):
    LOBBY = "lobby"
    TEAM_SELECTION = "team_selection"
    CHAR_SELECTION = "char_selection"
    READY_CHECK = "ready_check"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _gen_game_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _gen_host_token() -> str:
    return secrets.token_urlsafe(24)


def _gen_player_id() -> str:
    return uuid4().hex


class Game(SQLModel, table=True):
    id: str = Field(
        default_factory=_gen_game_id, primary_key=True, max_length=8
    )
    status: GameStatus = Field(default=GameStatus.LOBBY)
    host_token: str = Field(default_factory=_gen_host_token, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    paused_at: Optional[datetime] = None
    countdown_started_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    current_cycle: int = 0

    teams: list["Team"] = Relationship(back_populates="game")


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(foreign_key="game.id", index=True)
    equipe: Equipe
    created_at: datetime = Field(default_factory=_utcnow)

    game: Optional[Game] = Relationship(back_populates="teams")
    players: list["Player"] = Relationship(back_populates="team")


class Player(SQLModel, table=True):
    id: str = Field(
        default_factory=_gen_player_id, primary_key=True, max_length=32
    )
    team_id: int = Field(foreign_key="team.id", index=True)
    profissao: Optional[Profissao] = None
    nome: Optional[str] = None
    ready: bool = False
    created_at: datetime = Field(default_factory=_utcnow)

    team: Optional[Team] = Relationship(back_populates="players")
