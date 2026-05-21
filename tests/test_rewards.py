"""Testes para aplicação de recompensas de side quests."""

import json
import random

from sqlmodel import Session, select

from jogo.db.models import Character, Clue, Game, SideQuest, Team
from jogo.game_data import (
    ClueCategory,
    ClueVeracity,
    Equipe,
    SideQuestDifficulty,
    SideQuestKind,
    SideQuestStatus,
)
from jogo import side_quests as sq_mod


class TestRewardApplication:
    """Testes para aplicação de recompensas ao vencer side quests."""

    def test_reveal_extra_clue_reward(self, session: Session):
        """Recompensa REVEAL_EXTRA_CLUE revela uma pista não-revelada."""
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

        # Cria pista não revelada
        clue = Clue(
            game_id=game.id,
            categoria=ClueCategory.OBJETO_LOCAL,
            veracidade=ClueVeracity.VERDADEIRA,
            conteudo="Hidden clue",
            revealed_at_cycle=None,
        )
        session.add(clue)
        session.commit()
        session.refresh(clue)

        # Cria side quest com recompensa REVEAL_EXTRA_CLUE
        state = {
            "secret": "1234",
            "digits": 4,
            "max_attempts": 8,
            "attempts": [],
        }
        sq = SideQuest(
            game_id=game.id,
            team_id=team.id,
            cycle=1,
            kind=SideQuestKind.MASTERMIND,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="reveal_extra_clue",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Submete resposta correta
        result = sq_mod.submit(session, game, sq, {"guess": "1234"})

        assert result.get("ok")
        assert result.get("won")
        assert result.get("reward_result") is not None

        # Verifica que uma pista foi revelada
        session.refresh(clue)
        assert clue.revealed_at_cycle is not None

    def test_block_opponent_character_reward(self, session: Session):
        """Recompensa BLOCK_OPPONENT_CHARACTER bloqueia personagem adversário."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team1 = Team(game_id=game.id, equipe=Equipe.POLICIA)
        team2 = Team(game_id=game.id, equipe=Equipe.DETETIVES)
        session.add_all([team1, team2])
        session.commit()
        session.refresh(team1)
        session.refresh(team2)

        # Cria personagem em team2
        char = Character(
            game_id=game.id,
            equipe=team2.equipe,
            profissao="INVESTIGADOR_CHEFE",
            nome="Target",
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

        # Cria side quest com recompensa BLOCK_OPPONENT_CHARACTER
        state = {
            "secret": 42,
            "range_max": 100,
            "max_attempts": 10,
            "attempts": [],
        }
        sq = SideQuest(
            game_id=game.id,
            team_id=team1.id,
            cycle=1,
            kind=SideQuestKind.HIGHER_LOWER,
            difficulty=SideQuestDifficulty.NORMAL,
            reward="block_opponent_character",
            state_json=json.dumps(state),
        )
        session.add(sq)
        session.commit()
        session.refresh(sq)

        sq_mod.claim(session, sq, "test_player")
        session.refresh(sq)

        # Submete resposta correta
        result = sq_mod.submit(session, game, sq, {"guess": "42"})

        assert result.get("ok")
        assert result.get("won")
        assert result.get("reward_result") is not None

        # Verifica que um personagem adversário foi bloqueado
        blocked_char = session.get(Character, char.id)
        assert blocked_char.blocked_until_cycle is not None

    def test_no_reward_on_loss(self, session: Session):
        """Nenhuma recompensa é aplicada se perder a side quest."""
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

        clue = Clue(
            game_id=game.id,
            categoria=ClueCategory.OBJETO_LOCAL,
            veracidade=ClueVeracity.VERDADEIRA,
            conteudo="Hidden clue",
            revealed_at_cycle=None,
        )
        session.add(clue)
        session.commit()

        state = {
            "secret": 50,
            "range_max": 100,
            "max_attempts": 1,
            "attempts": [],
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

        # Submete resposta errada (perda imediata)
        result = sq_mod.submit(session, game, sq, {"guess": "10"})

        assert result.get("ok")
        assert result.get("lost")
        assert result.get("reward_result") is None

        # Verifica que nenhuma pista foi revelada
        session.refresh(clue)
        assert clue.revealed_at_cycle is None

    def test_reward_distribution_ratio(self, session: Session):
        """Recompensas seguem distribuição 60/40."""
        # Executa múltiplas seleções de recompensa e verifica a proporção
        rewards = [sq_mod._pick_reward() for _ in range(100)]

        reveal_count = sum(
            1 for r in rewards
            if r.value == "reveal_extra_clue"
        )
        block_count = sum(
            1 for r in rewards
            if r.value == "block_opponent_character"
        )

        # Com 100 amostras, esperamos aproximadamente 60 reveals e 40 blocks
        # Permitindo variação de ±15 (intervalo de confiança razoável)
        assert 45 <= reveal_count <= 75, f"Expect ~60 reveals, got {reveal_count}"
        assert 25 <= block_count <= 55, f"Expect ~40 blocks, got {block_count}"
