# Jogo Investigativo

Jogo de investigação em grupos. Roda em servidor local — host abre no laptop, jogadores conectam pelo celular via QR code.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Rodar

```bash
uvicorn jogo.main:app --host 0.0.0.0 --port 8000 --reload
```

O `--host 0.0.0.0` é obrigatório pra celulares na mesma Wi-Fi acessarem.
Por padrão uvicorn escuta só em `127.0.0.1` e o IP da rede dá `ERR_CONNECTION_REFUSED`.

Abre `http://localhost:8000` no navegador do laptop e mostra o QR code com o IP da rede pros celulares. Na primeira execução o macOS pode pedir permissão pra Python aceitar conexões — autoriza.

### Quando o schema muda

Não temos migrações de DB ainda. Se você puxar uma branch que mudou `jogo/db/models.py`, o `data/game.db` antigo vai dar 500 em queries (`no such column …`). Resolve com:

```bash
rm data/game.db
```

E reinicia. O `init_db()` recria o schema do zero.

## Estado atual

- **PR 1** — skeleton (FastAPI + SQLite + lobby com QR).
- **PR 2** — fluxo de preparação (equipe picker, sala do time, entrada de jogador, profissão, Pronto, countdown).
- **PR 3** — seed data + sorteio interno do crime (criminoso, vítima, cúmplices, local, objeto, motivacional) + 24 fichas civis. Sem LLM.

## Estrutura

```
jogo/
  config.py          # settings (env)
  main.py            # FastAPI app + lifespan
  engine.py          # state machine, countdown e generation tasks
  game_data.py       # enums (Equipe, Profissao, FuncaoEspecial), constantes
  realtime.py        # WebSocket ConnectionManager
  crime.py           # sorteio do crime + fichas civis
  seed.py            # loaders dos arquivos seed
  db/
    models.py        # SQLModel — Game, Team, Player, Character
    session.py       # engine SQLite
  api/
    pages.py         # rotas HTML
    ws.py            # handler WebSocket
  utils/
    qr.py            # QR code + IP local
templates/           # Jinja2 (base, lobby, game_entry, team_room, player, generating, playing + partials)
static/              # CSS, JS
data/
  seed/              # dados estáticos (nomes, locais, objetos, motivos…)
  game.db            # estado do jogo (criado em runtime, gitignored)
```
