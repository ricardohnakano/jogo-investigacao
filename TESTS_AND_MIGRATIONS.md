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

Total: 10 testes implementados (7 game logic + 3 clues)

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
