# Jogo Investigativo

Jogo de investigação em grupos. Roda em servidor local — host abre no laptop, jogadores conectam pelo celular via QR code.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edite `.env` e coloque sua `ANTHROPIC_API_KEY` (pegue em https://console.anthropic.com).
A geração da história e das dicas usa Claude Opus 4.7 — uma partida consome ~$0.10–0.20 com prompt caching.

### Sem API key (mock mode)

Pra desenvolver/testar sem gastar créditos, rode com:

```bash
JOGO_MOCK_LLM=1 uvicorn jogo.main:app --host 0.0.0.0 --port 8000 --reload
```

Isso lê fixtures de `data/mock_llm/*.json`. Pra gerar fixtures novas: rode uma vez com API real, depois chame `jogo.llm.dump_mock(step_name, output)` no Python.

## Rodar

```bash
uvicorn jogo.main:app --host 0.0.0.0 --port 8000 --reload
```

O `--host 0.0.0.0` é obrigatório pra celulares na mesma Wi-Fi acessarem.
Por padrão uvicorn escuta só em `127.0.0.1` e o IP da rede dá `ERR_CONNECTION_REFUSED`.

Abra `http://localhost:8000` no navegador do laptop e mostra o QR code com o IP da rede pros celulares. Na primeira execução o macOS pode pedir permissão pra Python aceitar conexões — autoriza.

### Quando o schema muda

Não temos migrações de DB ainda. Se você puxar uma branch que mudou `jogo/db/models.py`, o `data/game.db` antigo vai dar 500 em queries (`no such column …`). Resolve com:

```bash
rm data/game.db
```

E reinicia. O `init_db()` recria o schema do zero.

## Estado atual

- **PR 1** — skeleton (FastAPI + SQLite + lobby com QR).
- **PR 2** — fluxo de preparação (equipe picker, sala do time, entrada de jogador, profissão, Pronto, countdown).
- **PR 3** — seed data + sorteio interno do crime + 24 fichas civis. Sem LLM.
- **PR 4** — pipeline LLM: história canônica, dicas (4 categorias × 4 veracidades), personalidade do criminoso ligada ao motivacional, relações, comentários sobre os 24 personagens. Validators determinísticos + retry com feedback.

## Estrutura

```
jogo/
  config.py            # settings (env)
  main.py              # FastAPI app + lifespan
  engine.py            # state machine, countdown e generation tasks
  game_data.py         # enums + constantes (incluindo ClueCategory/ClueVeracity)
  realtime.py          # WebSocket ConnectionManager
  crime.py             # sorteio do crime + fichas civis (PR 3)
  seed.py              # loaders dos arquivos seed
  llm.py               # wrapper Anthropic com caching e mock mode (PR 4)
  narrative.py         # pipeline de 5 etapas com LLM (PR 4)
  narrative_schemas.py # schemas Pydantic dos outputs do LLM (PR 4)
  validators.py        # validators determinísticos (PR 4)
  db/
    models.py          # SQLModel — Game, Team, Player, Character, Clue
    session.py         # engine SQLite
  api/
    pages.py           # rotas HTML
    ws.py              # handler WebSocket
  utils/
    qr.py              # QR code + IP local
templates/             # Jinja2
static/                # CSS, JS
data/
  seed/                # dados estáticos (nomes, locais, objetos, motivos…)
  mock_llm/            # fixtures pro JOGO_MOCK_LLM (gitignored)
  game.db              # estado do jogo (criado em runtime, gitignored)
```
