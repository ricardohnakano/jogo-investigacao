import secrets
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class GameStatus(str, Enum):
    LOBBY = "lobby"
    TEAM_SELECTION = "team_selection"
    CHAR_SELECTION = "char_selection"
    GENERATING = "generating"
    READY_CHECK = "ready_check"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _gen_game_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _gen_host_token() -> str:
    return secrets.token_urlsafe(24)


class Game(SQLModel, table=True):
    id: str = Field(default_factory=_gen_game_id, primary_key=True, max_length=8)
    status: GameStatus = Field(default=GameStatus.LOBBY)
    host_token: str = Field(default_factory=_gen_host_token, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    paused_at: Optional[datetime] = None
    current_cycle: int = 0
