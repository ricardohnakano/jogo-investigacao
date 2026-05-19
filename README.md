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
uvicorn jogo.main:app --reload
```

Abrir `http://localhost:8000` no navegador. Os celulares dos jogadores devem estar na mesma rede Wi-Fi e escanear o QR code mostrado na tela inicial.

## Estado atual

**PR 1 — skeleton.** Tela inicial cria/continua jogo, mostra QR code com o IP local, e abre uma página placeholder por partida. Sem state machine, sem LLM, sem WebSocket ainda — fundação pra crescer.

## Estrutura

```
jogo/
  config.py          # settings (env)
  main.py            # FastAPI app + lifespan
  db/
    models.py        # SQLModel — Game
    session.py       # engine SQLite
  api/
    pages.py         # rotas HTML
  utils/
    qr.py            # QR code + IP local
templates/           # Jinja2
static/              # CSS, JS
data/                # SQLite + artefatos por partida (criado em runtime)
```
