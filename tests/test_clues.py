"""Testes para distribuição e classificação de pistas."""

from sqlmodel import Session, select

from jogo.db.models import Character, Clue, Game, Team
from jogo.game_data import (
    ClueCategory,
    ClueVeracity,
    Equipe,
    Profissao,
)
from jogo import actions as actions_mod
from jogo import clues as clues_mod


class TestClueRevealSchedule:
    """Testes para agendamento automático de revelação de pistas."""

    def test_clue_reveal_schedule_cycles_1_to_6(self, session: Session):
        """Verifica que reveal_for_cycle() marca revealed_at_cycle correto."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()

        # Cria pistas para cada categoria e veracidade
        clues_data = [
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.VERDADEIRA),
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.VERDADEIRA),
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.VERDADEIRA),
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.ENGANOSA),
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.ENGANOSA),
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.FALSA),
            (ClueCategory.OBJETO_LOCAL, ClueVeracity.FALSA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.VERDADEIRA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.VERDADEIRA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.VERDADEIRA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.ENGANOSA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.ENGANOSA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.FALSA),
            (ClueCategory.LINHA_TEMPO, ClueVeracity.FALSA),
        ]

        for categoria, veracidade in clues_data:
            clue = Clue(
                game_id=game.id,
                categoria=categoria,
                veracidade=veracidade,
                conteudo=f"{categoria.value}_{veracidade.value}",
            )
            session.add(clue)
        session.commit()

        # Revela pistas para cada ciclo
        expected_reveals = [
            # ciclo 1: 2 OL + 2 LT (1 VERDADEIRA cada, 1 ENGANOSA cada)
            [(ClueCategory.OBJETO_LOCAL, ClueVeracity.VERDADEIRA),
             (ClueCategory.LINHA_TEMPO, ClueVeracity.VERDADEIRA),
             (ClueCategory.OBJETO_LOCAL, ClueVeracity.ENGANOSA),
             (ClueCategory.LINHA_TEMPO, ClueVeracity.ENGANOSA)],
            # ciclo 2: 2 OL (1 VERDADEIRA, 1 FALSA)
            [(ClueCategory.OBJETO_LOCAL, ClueVeracity.VERDADEIRA),
             (ClueCategory.OBJETO_LOCAL, ClueVeracity.FALSA)],
            # ciclo 3: 2 LT (1 VERDADEIRA, 1 FALSA)
            [(ClueCategory.LINHA_TEMPO, ClueVeracity.VERDADEIRA),
             (ClueCategory.LINHA_TEMPO, ClueVeracity.FALSA)],
            # ciclo 4: 2 OL (1 VERDADEIRA, 1 ENGANOSA)
            [(ClueCategory.OBJETO_LOCAL, ClueVeracity.VERDADEIRA),
             (ClueCategory.OBJETO_LOCAL, ClueVeracity.ENGANOSA)],
            # ciclo 5: 2 LT (1 VERDADEIRA, 1 ENGANOSA)
            [(ClueCategory.LINHA_TEMPO, ClueVeracity.VERDADEIRA),
             (ClueCategory.LINHA_TEMPO, ClueVeracity.ENGANOSA)],
            # ciclo 6: 2 clues (1 FALSA OL, 1 FALSA LT)
            [(ClueCategory.OBJETO_LOCAL, ClueVeracity.FALSA),
             (ClueCategory.LINHA_TEMPO, ClueVeracity.FALSA)],
        ]

        for cycle, expected in enumerate(expected_reveals, start=1):
            clues_mod.reveal_for_cycle(session, game.id, cycle)

        # Verifica que cada clue foi revelada no ciclo esperado
        all_clues = list(
            session.exec(
                select(Clue).where(Clue.game_id == game.id)
            ).all()
        )
        revealed_by_cycle = {}
        for clue in all_clues:
            if clue.revealed_at_cycle:
                if clue.revealed_at_cycle not in revealed_by_cycle:
                    revealed_by_cycle[clue.revealed_at_cycle] = []
                revealed_by_cycle[clue.revealed_at_cycle].append(
                    (clue.categoria, clue.veracidade)
                )

        # Verifica que pistas foram reveladas em todos os 6 ciclos
        assert len(revealed_by_cycle) == 6

        # Verifica que ciclo 1 revelou 4 pistas (2 OL, 2 LT)
        assert len(revealed_by_cycle[1]) == 4


class TestClassifiedVeracityElimination:
    """Testes para eliminação automática de pistas mal classificadas."""

    def test_classified_non_verdadeira_eliminates_clue(self, session: Session):
        """Pista classificada como não-VERDADEIRA é eliminada."""
        game = Game()
        game.status = "playing"
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        # Cria um personagem para executar a ação
        char = Character(
            game_id=game.id,
            equipe=team.equipe,
            profissao=Profissao.ANALISTA_OCORRENCIAS,  # classifica LINHA_TEMPO
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

        # Cria uma pista verdadeira
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

        # Classifica como FALSA (não-verdadeira) via ação
        result = actions_mod.execute_action(
            session,
            game,
            char,
            team,
            {
                "target_clue_id": clue.id,
                "classified_veracity": ClueVeracity.FALSA.value,
            },
        )

        assert result.get("ok")

        # Verifica que a pista foi eliminada
        session.refresh(clue)
        assert clue.eliminated
        assert clue.eliminated_at_cycle == game.current_cycle
        assert clue.classified_veracity == ClueVeracity.FALSA

    def test_classified_verdadeira_not_eliminated(self, session: Session):
        """Pista classificada como VERDADEIRA não é eliminada."""
        game = Game()
        game.status = "playing"
        session.add(game)
        session.commit()
        session.refresh(game)

        team = Team(game_id=game.id, equipe=Equipe.POLICIA)
        session.add(team)
        session.commit()
        session.refresh(team)

        char = Character(
            game_id=game.id,
            equipe=team.equipe,
            profissao=Profissao.ANALISTA_OCORRENCIAS,
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

        # Classifica como VERDADEIRA
        result = actions_mod.execute_action(
            session,
            game,
            char,
            team,
            {
                "target_clue_id": clue.id,
                "classified_veracity": ClueVeracity.VERDADEIRA.value,
            },
        )

        assert result.get("ok")

        # Verifica que a pista NÃO foi eliminada
        session.refresh(clue)
        assert not clue.eliminated
        assert clue.eliminated_at_cycle is None
        assert clue.classified_veracity == ClueVeracity.VERDADEIRA
