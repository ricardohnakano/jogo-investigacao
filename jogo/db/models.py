import secrets
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel

from jogo.game_data import ClueCategory, ClueVeracity, Equipe, FuncaoEspecial, Profissao


class GameStatus(str, Enum):
    LOBBY = "lobby"
    TEAM_SELECTION = "team_selection"
    CHAR_SELECTION = "char_selection"
    READY_CHECK = "ready_check"
    GENERATING = "generating"
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
    generation_started_at: Optional[datetime] = None
    generation_finished_at: Optional[datetime] = None
    countdown_started_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    current_cycle: int = 0

    local: Optional[str] = None
    objeto: Optional[str] = None
    motivacional: Optional[str] = None
    historia_completa: Optional[str] = None

    teams: list["Team"] = Relationship(back_populates="game")
    characters: list["Character"] = Relationship(back_populates="game")
    clues: list["Clue"] = Relationship(back_populates="game")


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


class Character(SQLModel, table=True):
    """Representa uma das 24 fichas civis (humanos + NPCs)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(foreign_key="game.id", index=True)
    profissao: Profissao
    equipe: Equipe
    is_npc: bool = True
    player_id: Optional[str] = Field(
        default=None, foreign_key="player.id", index=True
    )

    nome: str
    sobrenome: str
    idade: int
    genero: str
    avatar_seed: str
    personalidade: str
    relacao_com_vitima: Optional[str] = None
    comentario: Optional[str] = None

    funcao_especial: FuncaoEspecial = Field(default=FuncaoEspecial.NENHUMA)
    eliminated: bool = False
    action_used: bool = False
    created_at: datetime = Field(default_factory=_utcnow)

    game: Optional[Game] = Relationship(back_populates="characters")


class Clue(SQLModel, table=True):
    """Pista gerada por LLM (objeto/local, ficha civil, linha do tempo)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(foreign_key="game.id", index=True)
    categoria: ClueCategory
    veracidade: ClueVeracity
    conteudo: str
    target_character_id: Optional[int] = Field(
        default=None, foreign_key="character.id", index=True
    )
    revealed_at_cycle: Optional[int] = None
    classified: bool = False
    classified_by_team_id: Optional[int] = Field(
        default=None, foreign_key="team.id"
    )
    eliminated: bool = False
    created_at: datetime = Field(default_factory=_utcnow)

    game: Optional[Game] = Relationship(back_populates="clues")
