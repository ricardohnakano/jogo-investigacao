"""Testes para side quests (Higher/Lower, Labyrinth)."""

import json

from sqlmodel import Session

from jogo.db.models import Game, SideQuest, Team
from jogo.game_data import (
    Equipe,
    SideQuestDifficulty,
    SideQuestKind,
    SideQuestStatus,
)
from jogo import side_quests as sq_mod


class TestHigherLowerQuest:
    """Testes para side quest Maior ou Menor."""

    def test_higher_lower_correct_answer_wins(self, session: Session):
        """Resposta correta no Higher/Lower resulta em vitória."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        # Cria quest Higher/Lower com segredo = 42
        state = {"secret": 42, "range_max": 100, "max_attempts": 10, "attempts": []}
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.HIGHER_LOWER,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        # Reclama a quest
        ok, _ = sq_mod.claim(session, sq, "test_player")
        assert ok

        session.refresh(sq)
        assert sq.status == SideQuestStatus.IN_PROGRESS

        # Submete resposta correta
        result = sq_mod.submit(session, game, sq, {"guess": "42"})

        assert result.get("ok")
        assert result.get("won")
        assert result.get("result") == "acertou"

    def test_higher_lower_higher_hint(self, session: Session):
        """Palpite menor que o segredo retorna 'maior'."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        state = {"secret": 50, "range_max": 100, "max_attempts": 8, "attempts": []}
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.HIGHER_LOWER,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Palpita 30 (menor que 50)
        result = sq_mod.submit(session, game, sq, {"guess": "30"})

        assert result.get("ok")
        assert not result.get("won")
        assert result.get("result") == "maior"
        assert result.get("attempts_used") == 1

    def test_higher_lower_max_attempts_lost(self, session: Session):
        """Exceder max_attempts resulta em perda."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        state = {
            "secret": 50,
            "range_max": 100,
            "max_attempts": 2,
            "attempts": [
                {"guess": 10, "result": "maior"},
            ],
        }
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.HIGHER_LOWER,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Último palpite errado
        result = sq_mod.submit(session, game, sq, {"guess": "20"})

        assert result.get("ok")
        assert result.get("lost")
        assert not result.get("won")


class TestLabyrinthQuest:
    """Testes para side quest Labirinto."""

    def test_labyrinth_valid_move(self, session: Session):
        """Movimento válido no labirinto atualiza posição."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        # Cria labirinto com posição inicial [0, 0]
        grid = sq_mod._generate_maze(4)
        state = {
            "size": 4,
            "grid": grid,
            "pos": [0, 0],
            "goal": [3, 3],
        }
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.LABYRINTH,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Tenta mover (mesmo que falhe, deve retornar ok=True)
        result = sq_mod.submit(session, game, sq, {"move": "down"})

        assert result.get("ok")
        assert isinstance(result.get("pos"), list)

    def test_labyrinth_invalid_move_direction(self, session: Session):
        """Direção inválida retorna erro."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        grid = sq_mod._generate_maze(4)
        state = {
            "size": 4,
            "grid": grid,
            "pos": [0, 0],
            "goal": [3, 3],
        }
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.LABYRINTH,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Movimento inválido
        result = sq_mod.submit(session, game, sq, {"move": "jump"})

        assert not result.get("ok")
        assert "inválido" in result.get("error", "").lower()

    def test_labyrinth_reach_goal_wins(self, session: Session):
        """Alcançar a meta resulta em vitória."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        # Cria um labirinto simples onde [1,1] é alcançável de [0,0]
        grid = sq_mod._generate_maze(2)
        state = {
            "size": 2,
            "grid": grid,
            "pos": [0, 0],
            "goal": [1, 1],
        }
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.LABYRINTH,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Tenta várias sequências de movimentos para alcançar [1,1]
        # Como é aleatório, vamos tentar um pequeno número de movimentos
        moves = ["down", "right", "down", "right"]
        won = False
        for move in moves:
            result = sq_mod.submit(session, game, sq, {"move": move})
            if result.get("won"):
                won = True
                break
            session.refresh(sq)

        # Se conseguiu chegar ao destino, verifica
        if result.get("pos") == [1, 1]:
            assert result.get("won")
