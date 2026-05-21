"""Testes para ações de bloqueio (Invasor de Sistema)."""

from sqlmodel import Session

from jogo.db.models import Character, Clue, Game, Team
from jogo.game_data import (
    ClueCategory,
    ClueVeracity,
    Equipe,
    Profissao,
)
from jogo import actions as actions_mod


class TestBlockOpponentClassify:
    """Testes para bloqueio de classificação por Invasor de Sistema."""

    def test_invasor_blocks_opponent_classification(self, session: Session):
        """Invasor de Sistema bloqueia classificação do time adversário."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        # Team1 (POLICIA) com Invasor
        team1 = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team1)
        session.commit()
        session.refresh(team1)

        # Team2 (DETETIVES) que será bloqueado
        team2 = Team(game_id=game.id, equipe=Equipe.DETETIVES)
        session.add(team2)
        session.commit()
        session.refresh(team2)

        # Invasor de Sistema em team1
        invasor = Character(
            game_id=game.id,
            equipe=team1.equipe,
            profissao=Profissao.INVASOR_SISTEMA,
            nome="Test",
            sobrenome="Invasor",
            idade=30,
            genero="M",
            avatar_seed="seed",
            personalidade="normal",
            is_npc=False,
        )
        session.add(invasor)
        session.commit()
        session.refresh(invasor)

        # Executa ação de bloqueio contra team2
        result = actions_mod.execute_action(
            session,
            game,
            invasor,
            team1,
            {"target_team_id": team2.id},
        )

        assert result.get("ok")

        # Verifica que team2 foi bloqueada
        session.refresh(team2)
        assert team2.classification_blocked_until_cycle is not None
        assert team2.classification_blocked_until_cycle > game.current_cycle

    def test_blocked_team_cannot_classify(self, session: Session):
        """Time bloqueado não pode classificar pistas."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.DETETIVES)
        team.classification_blocked_until_cycle = 2  # Bloqueado até ciclo 2
        session.add(team)
        session.commit()
        session.refresh(team)

        # Classificador em team
        classificador = Character(
            game_id=game.id,
            equipe=team.equipe,
            profissao=Profissao.ANALISTA_OCORRENCIAS,
            nome="Test",
            sobrenome="Classificador",
            idade=30,
            genero="M",
            avatar_seed="seed",
            personalidade="normal",
            is_npc=False,
        )
        session.add(classificador)
        session.commit()
        session.refresh(classificador)

        # Cria uma pista revelada
        clue = Clue(
            game_id=game.id,
            categoria=ClueCategory.LINHA_TEMPO,
            veracidade=ClueVeracity.VERDADEIRA,
            conteudo="Test clue",
            revealed_at_cycle=1,
        )
        session.add(clue)
        session.commit()
        session.refresh(clue)

        # Tenta classificar (deve falhar)
        result = actions_mod.execute_action(
            session,
            game,
            classificador,
            team,
            {
                "target_clue_id": clue.id,
                "classified_veracity": ClueVeracity.VERDADEIRA.value,
            },
        )

        assert not result.get("ok")
        assert "bloqueada" in result.get("error", "").lower()

    def test_classification_unblocked_after_cycle(self, session: Session):
        """Bloqueio de classificação expira após o ciclo especificado."""
        game = Game()
        game.status = "playing"
        game.current_cycle = 2
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.DETETIVES)
        team.classification_blocked_until_cycle = 1  # Bloqueio expirou no ciclo 1
        session.add(team)
        session.commit()
        session.refresh(team)

        classificador = Character(
            game_id=game.id,
            equipe=team.equipe,
            profissao=Profissao.ANALISTA_OCORRENCIAS,
            nome="Test",
            sobrenome="Classificador",
            idade=30,
            genero="M",
            avatar_seed="seed",
            personalidade="normal",
            is_npc=False,
        )
        session.add(classificador)
        session.commit()
        session.refresh(classificador)

        clue = Clue(
            game_id=game.id,
            categoria=ClueCategory.LINHA_TEMPO,
            veracidade=ClueVeracity.VERDADEIRA,
            conteudo="Test clue",
            revealed_at_cycle=1,
        )
        session.add(clue)
        session.commit()
        session.refresh(clue)

        # Tenta classificar (deve funcionar pois bloqueio expirou)
        result = actions_mod.execute_action(
            session,
            game,
            classificador,
            team,
            {
                "target_clue_id": clue.id,
                "classified_veracity": ClueVeracity.VERDADEIRA.value,
            },
        )

        assert result.get("ok")
