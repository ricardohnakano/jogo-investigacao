"""Testes essenciais da lógica de jogo."""

import pytest
from sqlmodel import Session

from jogo.db.models import Game, Team, Player, Character, Action, SideQuest
from jogo.game_data import (
    Equipe,
    Profissao,
    FuncaoEspecial,
    ActionKind,
    SideQuestKind,
    SideQuestStatus,
    SideQuestDifficulty,
)
from jogo import engine as engine_mod
from jogo import actions as actions_mod
from jogo import side_quests as sq_mod


class TestCanStart:
    """Teste da lógica can_start() — verificação de min players."""

    def test_can_start_needs_min_teams(self, session: Session, game_with_teams):
        """Jogo precisa de >= 2 teams para começar."""
        game, teams = game_with_teams
        # Começo: 2 times, mas players ainda não prontos
        assert not engine_mod.can_start(session, game.id)

    def test_can_start_needs_min_players_per_team(self, session: Session):
        """Cada time precisa de >= 3 players."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        # Adiciona 2 players (insuficiente)
        for i in range(2):
            p = Player(team_id=team.id, nome=f"P{i}")
            session.add(p)
        session.commit()

        assert not engine_mod.can_start(session, game.id)

    def test_can_start_needs_all_ready(self, session: Session):
        """Todos os players precisam estar prontos e com profissão."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        for eq in [Equipe.POLICIA, Equipe.DETETIVES]:
            team = Team(game_id=game.id, equipe=eq)
            session.add(team)
        session.commit()

        teams = engine_mod.get_teams(session, game.id)
        for team in teams:
            for i in range(3):
                p = Player(
                    team_id=team.id,
                    nome=f"P{i}",
                    profissao=list(Profissao)[i],
                    ready=(i < 2),  # apenas 2 de 3 prontos
                )
                session.add(p)
        session.commit()

        assert not engine_mod.can_start(session, game.id)

    def test_can_start_success(self, session: Session):
        """Sucesso: 2+ teams, 3+ players cada, todos com prof e ready."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        for eq in [Equipe.POLICIA, Equipe.DETETIVES]:
            team = Team(game_id=game.id, equipe=eq)
            session.add(team)
        session.commit()

        teams = engine_mod.get_teams(session, game.id)
        for team in teams:
            profs = list(Profissao)[:3]
            for i, prof in enumerate(profs):
                p = Player(
                    team_id=team.id,
                    nome=f"P{i}",
                    profissao=prof,
                    ready=True,
                )
                session.add(p)
        session.commit()

        assert engine_mod.can_start(session, game.id)


class TestExecuteActionTeamXref:
    """Teste de execute_action() — validação de team ownership."""

    def test_action_validates_character_team_xref(self, session: Session):
        """Action falha se character.team_id != request.team.id."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        team1 = Team(game_id=game.id, equipe=Equipe.POLICIA)
        team2 = Team(game_id=game.id, equipe=Equipe.DETETIVES)
        session.add_all([team1, team2])
        session.commit()
        session.refresh(team1)
        session.refresh(team2)

        # Character em team1
        char = Character(
            game_id=game.id,
            equipe=team1.equipe,
            profissao=Profissao.INVESTIGADOR_CHEFE,
            nome="Test",
            sobrenome="Char",
            idade=30,
            genero="M",
            avatar_seed="seed",
            personalidade="normal",
            is_npc=False,
        )
        session.add(char)
        session.commit()
        session.refresh(char)

        # Game em PLAYING, character action-ready
        from datetime import datetime, timezone
        game.status = "playing"
        game.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(game)
        session.commit()

        # Tentativa de action por team2 (xref inválida)
        result = actions_mod.execute_action(
            session,
            game,
            char,
            team2,  # team ERRADA
            {"target_character_id": char.id},
        )

        # deve falhar (team não bate)
        assert not result.get("ok")


class TestSideQuestSubmit:
    """Teste de side_quest submit() — mastermind answer check."""

    def test_mastermind_correct_answer(self, session: Session):
        """Mastermind: resposta correta = won."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        import json
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.MASTERMIND,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(
                {
                    "secret": "1234",
                    "digits": 4,
                    "max_attempts": 8,
                    "attempts": [],
                }
            ),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        # Claim a quest
        ok, _ = sq_mod.claim(session, sq, "test_player")
        assert ok

        session.refresh(sq)
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()

        # Submit resposta correta
        result = sq_mod.submit(session, game, sq, {"guess": "1234"})

        assert result.get("ok")
        assert result.get("won")
        assert result.get("bulls") == 4  # 4 acertos em posição

    def test_mastermind_wrong_format_rejected(self, session: Session):
        """Mastermind: resposta com formato errado = erro."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        import json
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.MASTERMIND,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(
                {
                    "secret": "1234",
                    "digits": 4,
                    "max_attempts": 8,
                    "attempts": [],
                }
            ),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        # Claim
        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Submit formato inválido (3 dígitos em vez de 4)
        result = sq_mod.submit(session, game, sq, {"guess": "123"})

        assert not result.get("ok")
        assert "dígitos" in result.get("error", "").lower()
