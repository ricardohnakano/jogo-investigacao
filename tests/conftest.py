"""Pytest fixtures para testes do jogo."""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from jogo.db.models import Game, Team, Player, Character
from jogo.db.session import get_session
from jogo.game_data import Equipe, Profissao, FuncaoEspecial
from jogo.main import app


@pytest.fixture(name="session")
def session_fixture():
    """Fixture que retorna sessão SQLite in-memory para testes."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Fixture que retorna cliente HTTP FastAPI com session mockada."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    from fastapi.testclient import TestClient
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="game_with_teams")
def game_with_teams_fixture(session: Session):
    """Fixture: jogo com 2 times (Polícia e Detetives) e 3 jogadores por time."""
    game = Game()
    session.add(game)
    session.commit()
    session.refresh(game)

    teams = []
    for equipe in [Equipe.POLICIA, Equipe.DETETIVES]:
        team = Team(game_id=game.id, equipe=equipe)
        session.add(team)
        teams.append(team)

    session.commit()
    for team in teams:
        session.refresh(team)
        for i in range(3):
            player = Player(
                team_id=team.id,
                nome=f"Jogador {team.equipe.value}_{i}",
                profissao=list(Profissao)[i],  # primeiras 3 profissões da equipe
            )
            session.add(player)
    session.commit()

    return game, teams


@pytest.fixture(name="game_with_characters")
def game_with_characters_fixture(session: Session):
    """Fixture: jogo com 24 personagens (6 por equipe × 4 equipes)."""
    from jogo.db.models import Character
    from jogo.game_data import PROFISSOES_POR_EQUIPE

    game = Game()
    session.add(game)
    session.commit()
    session.refresh(game)

    chars = []
    for equipe, profs in PROFISSOES_POR_EQUIPE.items():
        for i, prof in enumerate(profs):
            char = Character(
                game_id=game.id,
                equipe=equipe,
                profissao=prof,
                nome=f"Personagem_{equipe.value}_{i}",
                sobrenome="Test",
                idade=30 + i,
                genero="M" if i % 2 == 0 else "F",
                avatar_seed=f"seed_{equipe.value}_{i}",
                personalidade="normal",
                is_npc=(i > 0),  # primeiro é jogável, resto NPC
            )
            session.add(char)
            chars.append(char)
    session.commit()

    return game, chars
