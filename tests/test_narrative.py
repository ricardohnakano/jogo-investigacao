"""Testes para pipeline narrativo (geração de história e pistas)."""

from sqlmodel import Session, select

from jogo.db.models import Character, Clue, Game
from jogo.game_data import (
    ClueCategory,
    ClueVeracity,
    Equipe,
    FuncaoEspecial,
    Profissao,
)
from jogo import narrative as narrative_mod


class TestNarrativePipeline:
    """Testes para geração narrativa e criação de pistas."""

    def test_game_has_local_objeto_motivacional(self, session: Session):
        """Game preenchido contém local, objeto e motivacional."""
        game = Game()
        game.local = "Casa do crime"
        game.objeto = "Faca encontrada"
        game.motivacional = "Vingança por traição"
        session.add(game)
        session.commit()
        session.refresh(game)

        assert game.local is not None
        assert game.objeto is not None
        assert game.motivacional is not None

    def test_clue_categories_distributed(self, session: Session):
        """Pistas estão distribuídas entre 3 categorias."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        # Cria pistas de cada categoria
        for categoria in ClueCategory:
            clue = Clue(
                game_id=game.id,
                categoria=categoria,
                veracidade=ClueVeracity.VERDADEIRA,
                conteudo=f"Pista {categoria.value}",
            )
            session.add(clue)
        session.commit()

        # Verifica que há 3 categorias de pistas
        categories = set()
        for clue in session.exec(
            select(Clue).where(Clue.game_id == game.id)
        ).all():
            categories.add(clue.categoria)

        assert len(categories) >= 3

    def test_clue_veracity_distribution(self, session: Session):
        """Pistas têm diferentes níveis de veracidade."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        # Cria pistas com diferentes veracidades
        for veracity in ClueVeracity:
            clue = Clue(
                game_id=game.id,
                categoria=ClueCategory.OBJETO_LOCAL,
                veracidade=veracity,
                conteudo=f"Pista {veracity.value}",
            )
            session.add(clue)
        session.commit()

        # Verifica que há múltiplas veracidades
        veracities = set()
        for clue in session.exec(
            select(Clue).where(Clue.game_id == game.id)
        ).all():
            veracities.add(clue.veracidade)

        assert len(veracities) >= 3

    def test_characters_have_narrative_fields(self, session: Session):
        """Characters preenchidos têm campos narrativos completos."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        char = Character(
            game_id=game.id,
            equipe=Equipe.POLICIA,
            profissao=Profissao.INVESTIGADOR_CHEFE,
            nome="João",
            sobrenome="Silva",
            idade=45,
            genero="M",
            avatar_seed="seed123",
            personalidade="determinado",
            relacao_com_vitima="amigo de infância",
            comentario="Sempre ajudou a comunidade",
        )
        session.add(char)
        session.commit()
        session.refresh(char)

        # Verifica campos narrativos
        assert char.nome is not None
        assert char.sobrenome is not None
        assert char.personalidade is not None
        assert char.relacao_com_vitima is not None
        assert char.comentario is not None

    def test_criminal_victim_accomplices_setup(self, session: Session):
        """Jogo tem criminoso, vítima e cúmplices identificados."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        # Cria personagens com funções especiais
        chars = []
        for i, funcao in enumerate(
            [
                FuncaoEspecial.CRIMINOSO,
                FuncaoEspecial.VITIMA,
                FuncaoEspecial.CUMPLICE,
                FuncaoEspecial.CUMPLICE,
            ]
        ):
            char = Character(
                game_id=game.id,
                equipe=Equipe.POLICIA,
                profissao=Profissao.INVESTIGADOR_CHEFE,
                nome=f"Char{i}",
                sobrenome="Test",
                idade=30,
                genero="M",
                avatar_seed=f"seed{i}",
                personalidade="normal",
                funcao_especial=funcao,
                is_npc=True,
            )
            session.add(char)
            chars.append(char)
        session.commit()

        # Verifica que há um de cada papel principal
        all_chars = list(
            session.exec(select(Character).where(Character.game_id == game.id)).all()
        )

        funcoes = [c.funcao_especial for c in all_chars]
        assert FuncaoEspecial.CRIMINOSO in funcoes
        assert FuncaoEspecial.VITIMA in funcoes
        assert funcoes.count(FuncaoEspecial.CUMPLICE) >= 1

    def test_clue_target_character_reference(self, session: Session):
        """Pista de ficha civil pode referenciar um personagem."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        char = Character(
            game_id=game.id,
            equipe=Equipe.POLICIA,
            profissao=Profissao.INVESTIGADOR_CHEFE,
            nome="Target",
            sobrenome="Char",
            idade=30,
            genero="M",
            avatar_seed="seed",
            personalidade="normal",
            is_npc=True,
        )
        session.add(char)
        session.commit()
        session.refresh(char)

        # Cria pista ligada ao personagem
        clue = Clue(
            game_id=game.id,
            categoria=ClueCategory.FICHA_CIVIL,
            veracidade=ClueVeracity.VERDADEIRA,
            conteudo="Informação sobre o personagem",
            target_character_id=char.id,
        )
        session.add(clue)
        session.commit()
        session.refresh(clue)

        # Verifica que a pista está ligada
        assert clue.target_character_id == char.id

    def test_large_clue_set_generation(self, session: Session):
        """Sistema pode gerar conjunto grande de pistas sem erro."""
        game = Game()
        session.add(game)
        session.commit()
        session.refresh(game)

        # Gera ~35 pistas (9 OL + 11 FC + 9 LT + extras)
        clue_count = 0
        for cat in [ClueCategory.OBJETO_LOCAL, ClueCategory.FICHA_CIVIL, ClueCategory.LINHA_TEMPO]:
            for ver in ClueVeracity:
                for i in range(3):
                    clue = Clue(
                        game_id=game.id,
                        categoria=cat,
                        veracidade=ver,
                        conteudo=f"{cat.value}_{ver.value}_{i}",
                    )
                    session.add(clue)
                    clue_count += 1

        session.commit()

        # Verifica que todas as pistas foram criadas
        all_clues = list(
            session.exec(select(Clue).where(Clue.game_id == game.id)).all()
        )
        assert len(all_clues) == clue_count
        assert clue_count > 30
