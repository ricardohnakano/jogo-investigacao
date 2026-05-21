"""Teste de fluxo completo do jogo: 6 ciclos com múltiplos times."""

from sqlmodel import Session, select

from jogo.db.models import (
    Character,
    Clue,
    Game,
    GameStatus,
    Player,
    Team,
)
from jogo.game_data import (
    ClueCategory,
    ClueVeracity,
    Equipe,
    FuncaoEspecial,
    Profissao,
)
from jogo import clues as clues_mod
from jogo import engine as engine_mod


class TestFullGameFlow:
    """Teste de fluxo completo com 4 times, 6 ciclos."""

    def test_complete_game_flow_6_cycles(self, session: Session):
        """Valida fluxo completo: lobby → ready → playing → 6 cycles → finished."""
        # === LOBBY: criar jogo e teams ===
        game = Game(status=GameStatus.LOBBY)
        session.add(game)
        session.commit()
        session.refresh(game)

        teams = []
        for equipe in Equipe:
            team = Team(game_id=game.id, equipe=equipe)
            session.add(team)
            teams.append(team)
        session.commit()

        # === TEAM_SELECTION: criar players e characters ===
        game.status = GameStatus.TEAM_SELECTION
        session.add(game)
        session.commit()

        profissoes = list(Profissao)[:6]
        for team in teams:
            session.refresh(team)
            for i, prof in enumerate(profissoes):
                # Player
                player = Player(
                    team_id=team.id,
                    profissao=prof,
                    nome=f"Player {team.equipe.value} {i}",
                    ready=False,
                )
                session.add(player)

                # Character
                char = Character(
                    game_id=game.id,
                    equipe=team.equipe,
                    profissao=prof,
                    nome=f"Char {team.equipe.value} {i}",
                    sobrenome="Test",
                    idade=30,
                    genero="M",
                    avatar_seed=f"seed_{team.id}_{i}",
                    personalidade="normal",
                    is_npc=False,
                )
                # Atribui funcões especiais
                if i == 0:
                    char.funcao_especial = FuncaoEspecial.CRIMINOSO
                elif i == 1:
                    char.funcao_especial = FuncaoEspecial.VITIMA
                elif i == 2:
                    char.funcao_especial = FuncaoEspecial.CUMPLICE
                session.add(char)

        session.commit()

        # === CHAR_SELECTION: todos prontos ===
        game.status = GameStatus.CHAR_SELECTION
        session.add(game)
        session.commit()

        # Todos os players marcam como prontos
        all_players = list(
            session.exec(select(Player)).all()
        )
        for player in all_players:
            player.ready = True
            session.add(player)
        session.commit()

        # === READY_CHECK: valida can_start ===
        game.status = GameStatus.READY_CHECK
        session.add(game)
        session.commit()

        can_start = engine_mod.can_start(session, game.id)
        assert can_start, "Game should be ready to start"

        # === Cria pistas ===
        for cat in [ClueCategory.OBJETO_LOCAL, ClueCategory.LINHA_TEMPO]:
            for ver in [ClueVeracity.VERDADEIRA, ClueVeracity.ENGANOSA, ClueVeracity.FALSA]:
                for i in range(2):
                    clue = Clue(
                        game_id=game.id,
                        categoria=cat,
                        veracidade=ver,
                        conteudo=f"{cat.value}_{ver.value}_{i}",
                    )
                    session.add(clue)
        session.commit()

        # === GENERATING → COUNTDOWN → PLAYING ===
        game.status = GameStatus.PLAYING
        game.current_cycle = 1
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        game.started_at = now
        session.add(game)
        session.commit()
        session.refresh(game)

        # === Revela pistas para cada ciclo ===
        for cycle in range(1, 7):
            game.current_cycle = cycle
            session.add(game)
            session.commit()

            clues_mod.reveal_for_cycle(session, game.id, cycle)

            # Verifica que pistas foram reveladas
            visible = clues_mod.visible_clues(session, game.id)
            if cycle == 1:
                # Ciclo 1 revela 4 pistas
                assert len(visible) >= 1, f"Cycle {cycle} should have revealed clues"
            elif cycle == 2:
                # Ciclo 2 revela mais 2 pistas
                assert len(visible) >= 2, f"Cycle {cycle} should have more revealed clues"

        # === Atribui pistas de ficha civil ===
        clues_mod.assign_ficha_civil_targets(session, game.id)

        # === Marca jogo como finalizado ===
        game.status = GameStatus.FINISHED
        game.current_cycle = 6
        session.add(game)
        session.commit()

        # === Validações finais ===
        session.refresh(game)
        assert game.status == GameStatus.FINISHED
        assert game.current_cycle == 6

        # Verifica que todos os personagens existem
        all_chars = list(
            session.exec(select(Character).where(Character.game_id == game.id)).all()
        )
        assert len(all_chars) == 24, "Game should have 24 characters"

        # Verifica que todos os times existem
        all_teams = list(
            session.exec(select(Team).where(Team.game_id == game.id)).all()
        )
        assert len(all_teams) == 4, "Game should have 4 teams"

    def test_multiple_teams_can_act(self, session: Session):
        """Valida que múltiplos times podem executar ações no mesmo ciclo."""
        game = Game(status=GameStatus.PLAYING)
        game.current_cycle = 1
        session.add(game)
        session.commit()
        session.refresh(game)

        # Cria 2 times
        team1 = Team(game_id=game.id, equipe=Equipe.POLICIA)
        team2 = Team(game_id=game.id, equipe=Equipe.DETETIVES)
        session.add_all([team1, team2])
        session.commit()
        session.refresh(team1)
        session.refresh(team2)

        # 2 personagens em cada time
        char1a = Character(
            game_id=game.id,
            equipe=team1.equipe,
            profissao=Profissao.INVESTIGADOR_CHEFE,
            nome="Char1a",
            sobrenome="T1",
            idade=30,
            genero="M",
            avatar_seed="s1a",
            personalidade="normal",
            is_npc=False,
        )
        char1b = Character(
            game_id=game.id,
            equipe=team1.equipe,
            profissao=Profissao.DETETIVE_PRINCIPAL,
            nome="Char1b",
            sobrenome="T1",
            idade=31,
            genero="M",
            avatar_seed="s1b",
            personalidade="normal",
            is_npc=False,
        )
        char2a = Character(
            game_id=game.id,
            equipe=team2.equipe,
            profissao=Profissao.INVESTIGADOR_CHEFE,
            nome="Char2a",
            sobrenome="T2",
            idade=30,
            genero="M",
            avatar_seed="s2a",
            personalidade="normal",
            is_npc=False,
        )
        char2b = Character(
            game_id=game.id,
            equipe=team2.equipe,
            profissao=Profissao.DETETIVE_PRINCIPAL,
            nome="Char2b",
            sobrenome="T2",
            idade=31,
            genero="M",
            avatar_seed="s2b",
            personalidade="normal",
            is_npc=False,
        )
        session.add_all([char1a, char1b, char2a, char2b])
        session.commit()
        session.refresh(char1a)
        session.refresh(char1b)
        session.refresh(char2a)
        session.refresh(char2b)

        # Team1 executa ação contra character de team2
        from jogo import actions as actions_mod
        result1 = actions_mod.execute_action(
            session,
            game,
            char1a,
            team1,
            {"target_character_id": char2a.id},
        )
        assert result1.get("ok")

        # Team2 executa ação contra character de team1 (não o que foi eliminado)
        session.refresh(char1b)
        result2 = actions_mod.execute_action(
            session,
            game,
            char2b,
            team2,
            {"target_character_id": char1b.id},
        )
        assert result2.get("ok")

        # Ambas as ações foram registradas
        from jogo.db.models import Action
        actions = list(
            session.exec(
                select(Action).where(Action.game_id == game.id)
            ).all()
        )
        assert len(actions) == 2
