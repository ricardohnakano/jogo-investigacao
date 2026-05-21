# Testes e Migrações — Jogo Investigativo

## Testes (pytest)

### Executar testes
```bash
pytest tests/ -v
```

### Cobertura
```bash
pytest tests/ --cov=jogo --cov-report=html
```

### Estrutura

**`tests/conftest.py`** — Fixtures compartilhadas:
- `session_fixture`: SQLite in-memory para cada teste
- `client_fixture`: FastAPI TestClient com session mockada
- `game_with_teams`: Jogo com 2 times e 3 players cada
- `game_with_characters`: Jogo com 24 personagens gerados

**`tests/test_game_logic.py`** — 3 testes essenciais:

1. **TestCanStart** (4 testes)
   - Verifica lógica `engine.can_start()` — min players, pronto, profissão
   - Casos: insuficientes times, insuficientes players, não prontos, sucesso

2. **TestExecuteActionTeamXref** (1 teste)
   - Valida que `actions.execute_action()` rejeita cross-ref inválida (character.team_id != request.team.id)

3. **TestSideQuestSubmit** (2 testes)
   - Mastermind resposta correta → `won=True`, `bulls=4`
   - Mastermind resposta formato errado → `ok=False`

### Testes de pistas (test_clues.py)

**TestClueRevealSchedule** (1 teste):
- `test_clue_reveal_schedule_cycles_1_to_6`: Valida que `reveal_for_cycle()` marca `revealed_at_cycle` corretamente para cada ciclo conforme `CYCLE_CLUE_SCHEDULE`

**TestClassifiedVeracityElimination** (2 testes):
- `test_classified_non_verdadeira_eliminates_clue`: Verifica que pistas classificadas como NÃO-VERDADEIRA (FALSA, ENGANOSA, etc) são automaticamente eliminadas
- `test_classified_verdadeira_not_eliminated`: Confirma que pistas classificadas como VERDADEIRA NÃO são eliminadas

**TestFichaCivilTargetAssignment** (2 testes):
- `test_ficha_civil_targets_assigned_to_characters`: Valida que `assign_ficha_civil_targets()` liga todas as pistas de ficha civil a personagens
- `test_assign_ficha_civil_idempotent`: Confirma que a função é idempotente (segunda chamada não altera atribuições)

### Testes de bloqueio de ações (test_actions_blocking.py)

**TestBlockOpponentClassify** (3 testes):
- `test_invasor_blocks_opponent_classification`: Invasor de Sistema bloqueia classificação do time adversário
- `test_blocked_team_cannot_classify`: Time bloqueado não consegue executar ações de classificação
- `test_classification_unblocked_after_cycle`: Bloqueio expira automaticamente após o ciclo especificado

### Testes de side quests (test_side_quests.py)

**TestHigherLowerQuest** (3 testes):
- `test_higher_lower_correct_answer_wins`: Resposta correta resulta em vitória
- `test_higher_lower_higher_hint`: Palpite menor que segredo retorna dica "maior"
- `test_higher_lower_max_attempts_lost`: Exceder max_attempts resulta em perda

**TestLabyrinthQuest** (3 testes):
- `test_labyrinth_valid_move`: Movimento válido atualiza posição no labirinto
- `test_labyrinth_invalid_move_direction`: Direção inválida retorna erro
- `test_labyrinth_reach_goal_wins`: Alcançar meta resulta em vitória

### Testes de fluxo completo (test_game_flow.py)

**TestFullGameFlow** (2 testes):
- `test_complete_game_flow_6_cycles`: Valida fluxo completo de jogo: lobby → ready → playing → 6 cycles → finished
- `test_multiple_teams_can_act`: Múltiplos times podem executar ações no mesmo ciclo

### Testes de recompensas (test_rewards.py)

**TestRewardApplication** (4 testes):
- `test_reveal_extra_clue_reward`: Recompensa REVEAL_EXTRA_CLUE revela uma pista não-revelada
- `test_block_opponent_character_reward`: Recompensa BLOCK_OPPONENT_CHARACTER bloqueia personagem adversário
- `test_no_reward_on_loss`: Nenhuma recompensa quando side quest é perdida
- `test_reward_distribution_ratio`: Recompensas seguem proporção 60/40

### Testes de degradação de imagem (test_image.py)

**TestImageDegradation** (7 testes):
- `test_image_stages_progression`: IMAGE_STAGES contém 6 fatores de degradação
- `test_image_stages_values`: Valores específicos [0.02, 0.06, 0.14, 0.25, 0.39, 0.56]
- `test_current_image_stage_by_cycle`: Estágio progride de 1-6 por ciclo
- `test_image_stage_bonus_increases_quality`: Bonus de imagem avança estágio
- `test_image_stage_capped_at_max`: Estágio não excede máximo (6)
- `test_image_stage_cycle_progression`: Ciclos 1-6 geram estágios 1-6
- `test_image_stage_with_mid_cycle_bonus`: Bonus aplicado mid-game melhora qualidade

### Testes de modo mock do LLM (test_llm_mock.py)

**TestLLMMockMode** (5 testes):
- `test_mock_mode_loads_fixtures`: JOGO_MOCK_LLM=1 carrega fixtures JSON
- `test_mock_mode_enabled_with_env_var`: Modo mock habilitado via variável de ambiente
- `test_mock_mode_disabled_without_env_var`: Sem variável, usa client real
- `test_generate_respects_mock_mode`: generate() respeita modo mock
- `test_mock_fixture_structure`: Fixtures JSON têm estrutura válida

### Testes de pipeline narrativo (test_narrative.py)

**TestNarrativePipeline** (7 testes):
- `test_game_has_local_objeto_motivacional`: Game tem local, objeto, motivacional
- `test_clue_categories_distributed`: Pistas distribuídas entre 3 categorias
- `test_clue_veracity_distribution`: Pistas com diferentes níveis de veracidade
- `test_characters_have_narrative_fields`: Personagens têm campos narrativos completos
- `test_criminal_victim_accomplices_setup`: Criminoso, vítima e cúmplices identificados
- `test_clue_target_character_reference`: Pista de ficha civil referencia personagem
- `test_large_clue_set_generation`: Sistema gera 35+ pistas sem erro

**Total: 46 testes implementados**
- 7 game logic
- 5 clues (distribuição/classificação)
- 3 actions blocking
- 6 side quests
- 2 game flow
- 4 rewards
- 7 image degradation
- 5 LLM mock mode
- 7 narrative pipeline

## Migrações (Alembic)

### Setup
```bash
alembic revision --autogenerate -m "Initial schema from SQLModel"
alembic upgrade head
```

### Estructura
```
alembic/
├── versions/        # Migration scripts (.py)
├── env.py           # Alembic environment config
└── script.py.mako   # Template para novas migrations
```

### Fluxo típico
1. Modifique `jogo/db/models.py` (add column, table, etc)
2. Gere migration: `alembic revision --autogenerate -m "Add column X"`
3. Revise arquivo gerado em `alembic/versions/`
4. Rode: `alembic upgrade head`

### Downgrade
```bash
alembic downgrade -1  # volta uma migration
alembic downgrade base  # volta tudo
```

### Configuração banco de dados
- Default: `sqlite:///./data/game.db` (veja `jogo/db/session.py`)
- Alembic usa mesma URL via `alembic.ini` (sqlalchemy.url)

### Notas importantes
- **Sem autogenerate crítico em prod**: review sempre migrations geradas antes de rodar
- **Bloking changes**: considere strategy para zero-downtime (backfill, create novo campo, rename)
- **Backup before migrate**: `cp data/game.db data/game.db.backup` antes de `upgrade head`

## CI/CD (Próximos passos)

Adicionar ao `.github/workflows/`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov
```

## Referências
- [Pytest docs](https://docs.pytest.org/)
- [Alembic docs](https://alembic.sqlalchemy.org/)
- [SQLModel + Alembic](https://sqlmodel.tiangolo.com/tutorial/migrations/)
