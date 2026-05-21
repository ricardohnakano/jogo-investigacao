"""Testes para geração e degradação de imagens."""

from jogo.game_data import IMAGE_STAGES
from jogo import engine as engine_mod


class TestImageDegradation:
    """Testes para progressão de degradação de imagem por ciclo."""

    def test_image_stages_progression(self):
        """Valida que IMAGE_STAGES contém 6 estágios de degradação."""
        assert len(IMAGE_STAGES) == 6
        assert all(isinstance(factor, float) for factor in IMAGE_STAGES)
        # Fatores devem estar em ordem crescente (mais degradado)
        assert IMAGE_STAGES == sorted(IMAGE_STAGES)

    def test_image_stages_values(self):
        """Valida valores específicos dos estágios de degradação."""
        expected = [0.02, 0.06, 0.14, 0.25, 0.39, 0.56]
        assert IMAGE_STAGES == expected

    def test_current_image_stage_by_cycle(self):
        """Valida progressão do estágio de imagem por ciclo."""
        from jogo.db.models import Game

        game = Game()

        # Ciclo 1 → estágio 1
        game.current_cycle = 1
        game.image_stage_bonus = 0
        stage = engine_mod.current_image_stage(game)
        assert stage == 1

        # Ciclo 2 → estágio 2
        game.current_cycle = 2
        stage = engine_mod.current_image_stage(game)
        assert stage == 2

        # Ciclo 6 → estágio 6
        game.current_cycle = 6
        stage = engine_mod.current_image_stage(game)
        assert stage == 6

    def test_image_stage_bonus_increases_quality(self):
        """Bonus de imagem avança estágio (melhora qualidade)."""
        from jogo.db.models import Game

        game = Game()
        game.current_cycle = 1
        game.image_stage_bonus = 0

        # Sem bonus: estágio 0
        stage_without_bonus = engine_mod.current_image_stage(game)

        # Com bonus: estágio mais avançado
        game.image_stage_bonus = 2
        stage_with_bonus = engine_mod.current_image_stage(game)

        assert stage_with_bonus > stage_without_bonus

    def test_image_stage_capped_at_max(self):
        """Estágio de imagem não excede o máximo (6)."""
        from jogo.db.models import Game

        game = Game()
        game.current_cycle = 6
        game.image_stage_bonus = 10  # Bonus excessivo

        stage = engine_mod.current_image_stage(game)
        # min(6 + 10, 6) = 6, não 16
        assert stage == 6

    def test_image_stage_cycle_progression(self):
        """Verifica progressão natural de imagem por ciclo sem bonus."""
        from jogo.db.models import Game

        game = Game()
        game.image_stage_bonus = 0

        stages = []
        for cycle in range(1, 7):
            game.current_cycle = cycle
            stage = engine_mod.current_image_stage(game)
            stages.append(stage)

        # Ciclos 1-6 devem ter estágios 1-6
        assert stages == [1, 2, 3, 4, 5, 6]

    def test_image_stage_with_mid_cycle_bonus(self):
        """Bonus aplicado mid-game melhora qualidade."""
        from jogo.db.models import Game

        game = Game()
        game.current_cycle = 3

        # Sem bonus: estágio 2
        game.image_stage_bonus = 0
        stage_before = engine_mod.current_image_stage(game)

        # Após bonus (ex: action de Fotojornalista): estágio 3
        game.image_stage_bonus = 1
        stage_after = engine_mod.current_image_stage(game)

        assert stage_after == stage_before + 1
