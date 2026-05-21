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

**Total: 23 testes implementados**
- 7 game logic + 5 clues + 3 actions blocking + 6 side quests + 2 game flow

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
