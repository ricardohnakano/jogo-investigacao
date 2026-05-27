# Jogo Investigativo

Um jogo de investigação colaborativo para 6–24 jogadores em 4 equipes competindo para resolver um crime. Jogadores se conectam via celular a um servidor local rodando em um laptop.

**Status**: Versão 1.0 — jogo completo com 6 ciclos, mini-games, sistema de pontos, e geração LLM de histórias.

---

## Table of Contents

- [Visão Geral](#visão-geral)
- [Setup](#setup)
- [Como Jogar](#como-jogar)
- [Arquitetura](#arquitetura)
- [Modelos de Dados](#modelos-de-dados)
- [Fluxo de Estados](#fluxo-de-estados)
- [24 Profissões e Ações](#24-profissões-e-ações)
- [Mini-Games (Side Quests)](#mini-games-side-quests)
- [Pistas (Clues)](#pistas-clues)
- [Testes](#testes)
- [Desenvolvimento](#desenvolvimento)
- [Deployment](#deployment)

---

## Visão Geral

### O Jogo

Até 4 equipes (Policiais, Detetives, Jornalistas, Hackers) competem para identificar quem cometeu um crime. A geração do crime é 100% procedural via LLM:

- **Criminoso** — personagem gerado pelo LLM com motivação, método, e alibi
- **Vítima** — pessoa que o criminoso prejudicou
- **Cúmplices** — 1–2 pessoas que ajudaram (probabilidade por ciclo)
- **24 Fichas Civis** — NPCs inocentes com relacionamentos e comentários verdadeiros/falsos

Cada ciclo dura **10 minutos**. Há **6 ciclos** no total. Cada equipe tem uma profissão única com uma ação especial por ciclo.

### Objetivos

- **Investigadores**: Eliminar o criminoso antes do fim do jogo
- **Criminoso**: Evitar ser eliminado — ou eliminar todas as pessoas inocentes (lose condition)

---

## Setup

### Requisitos

- Python 3.11+ (3.13.3 recomendado)
- Chave de API da Anthropic (https://console.anthropic.com)
- macOS, Linux, ou Windows com terminal Bash

### Instalação

```bash
# Clone o repo
git clone <repo-url>
cd jogo-investigacao

# Crie virtual env
python3 -m venv .venv
source .venv/bin/activate

# Instale dependências
pip install -e ".[dev]"

# Configure env
cp .env.example .env
# Edite .env e coloque sua ANTHROPIC_API_KEY
```

### Primeiro Jogo

```bash
# Com API real (custa ~$0.10–0.20 com prompt caching)
uvicorn jogo.main:app --host 0.0.0.0 --port 8000 --reload

# Ou em mock mode (sem gastar tokens)
JOGO_MOCK_LLM=1 uvicorn jogo.main:app --host 0.0.0.0 --port 8000 --reload
```

Abra **http://localhost:8000** no navegador do laptop. Mostra um QR code com o IP da rede (ex: `192.168.1.100:8000`). Celulares na mesma Wi-Fi scanning o QR code ou digitando o IP diretamente entram na sala.

**Nota**: `--host 0.0.0.0` é obrigatório para celulares acessarem. Por padrão uvicorn escuta só em `127.0.0.1`.

### Mock Mode

Para desenvolver sem gastar créditos Anthropic, rode com `JOGO_MOCK_LLM=1`. O jogo lê fixtures de `data/mock_llm/*.json` ao invés de chamar Claude. Para gerar novas fixtures:

1. Rode uma vez com API real (deixe uma partida chegar a "GENERATING")
2. No fim, fixtures são salvas em `data/mock_llm/`
3. Após isso, `JOGO_MOCK_LLM=1` vai usar as fixtures

---

## Como Jogar

### Fase 1: Seleção de Equipe (Lobby)

Até 4 times (2–6 jogadores por time) entram no jogo. Host clica "Iniciar" quando pronto.

### Fase 2: Seleção de Personagem

Cada jogador escolhe uma das **6 profissões** do seu time. Profissões não podem ser repetidas no mesmo time. Todos devem clicar "Pronto".

### Fase 3: Countdown (10 segundos)

Geração do crime começou. Conta regressiva exibida em tempo real.

### Fase 4: Geração (2+ minutos)

O LLM gera:
1. Sorteio do criminoso, vítima, cúmplices
2. 24 fichas civis (personagens) com nomes, idades, relacionamentos
3. História completa do crime
4. Pistas de objeto/local (OBJETO_LOCAL)
5. Pistas de ficha civil (FICHA_CIVIL)
6. Pistas de linha do tempo (LINHA_TEMPO)
7. Comentários de cada personagem sobre os outros
8. Imagem da cena do crime (via DALL-E 3)

### Fase 5: Jogando (6 Ciclos × 10 minutos)

A cada ciclo:

1. **Ações**: Cada jogador executa a ação da sua profissão (elimina personagem, classifica pista, interroga, etc.)
2. **Mini-games**: 3 side quests (Mastermind, Labyrinth, Higher/Lower) oferecem bônus para a equipe
3. **Pistas Reveladas**: Novas pistas são automaticamente reveladas conforme cronograma fixo
4. **Bloqueios Expiram**: Personagens bloqueados voltam a atuar

### Fim do Jogo

- Se criminoso é eliminado: **Time que eliminou vence**
- Se todos os inocentes são eliminados: **Criminoso vence**
- Se 6 ciclos terminam sem eliminar o criminoso: **Todos os times competem por pontuação** (melhor classificação de pistas ganha)

---

## Arquitetura

### Stack Técnico

- **Backend**: FastAPI (Python 3.13)
- **Banco de dados**: SQLite (SQLModel ORM)
- **Frontend**: Jinja2 templates + HTMX + vanilla JavaScript
- **Real-time**: WebSocket com ConnectionManager (broadcast por game/team)
- **IA**: Anthropic SDK (Claude Opus 4.7) com prompt caching
- **Imagens**: OpenAI DALL-E 3 com degradação progressiva via Pillow

### Diretório Principal

```
jogo-investigacao/
├── jogo/
│   ├── main.py                  # FastAPI app + lifespan (init_db, migrations)
│   ├── config.py                # Settings via Pydantic (env vars)
│   ├── engine.py                # State machine (9 estados), background tasks
│   ├── game_data.py             # Enums + constantes (profissões, pistas, ciclos)
│   ├── actions.py               # Execução de ações por profissão
│   ├── side_quests.py           # Mini-games (mastermind, labyrinth, higher/lower)
│   ├── crime.py                 # Sorteio do crime + fichas civis
│   ├── narrative.py             # Pipeline LLM de 5 etapas (crime → pistas)
│   ├── narrative_schemas.py     # Pydantic schemas dos outputs LLM
│   ├── image.py                 # DALL-E 3 + degradação progressiva
│   ├── clues.py                 # Visibilidade de pistas por ciclo
│   ├── llm.py                   # Wrapper Anthropic (caching + mock mode)
│   ├── realtime.py              # WebSocket ConnectionManager
│   ├── seed.py                  # Loaders de dados estáticos
│   ├── templates.py             # Template registry
│   ├── validators.py            # Validadores determinísticos (Pydantic)
│   ├── logger.py                # Logging estruturado com contexto de jogo
│   ├── db/
│   │   ├── models.py            # SQLModel: Game, Team, Player, Character, Clue, Action, SideQuest
│   │   └── session.py           # SQLite engine + session factory
│   └── api/
│       ├── pages.py             # 30+ rotas HTTP (lobby, team selection, gameplay)
│       ├── side_quests.py       # Rotas de mini-games (claim, release, submit)
│       └── ws.py                # WebSocket endpoint + heartbeat
├── tests/
│   ├── conftest.py              # pytest fixtures (in-memory DB, client)
│   ├── test_game_logic.py        # Testes de lógica central
│   ├── test_actions_blocking.py  # Testes de bloqueios de ações
│   ├── test_side_quests.py       # Testes de mini-games
│   ├── test_rewards.py           # Testes de recompensas
│   ├── test_image.py             # Testes de degradação de imagem
│   ├── test_clues.py             # Testes de pistas
│   ├── test_llm_mock.py          # Testes de mock mode
│   ├── test_narrative.py         # Testes de geração LLM
│   └── test_game_flow.py         # Testes de fluxo completo
├── alembic/
│   ├── env.py                   # Config Alembic
│   ├── script.py.mako           # Template de migração
│   └── versions/                # Migrações SQL
├── templates/                   # Jinja2 templates
├── static/
│   ├── css/                     # Estilos
│   └── js/                      # JavaScript vanilla + HTMX
├── data/
│   ├── seed/                    # Nomes, locais, objetos, motivos (CSVs)
│   ├── mock_llm/                # Fixtures LLM (gitignored)
│   └── game.db                  # SQLite (criado em runtime, gitignored)
├── pyproject.toml               # Dependências + metadados
├── .env.example                 # Template de env vars
├── README.md                    # Este arquivo
└── TESTS_AND_MIGRATIONS.md      # Guia de testes + Alembic
```

---

## Modelos de Dados

### Game

Estado global da partida.

```python
class Game(SQLModel, table=True):
    id: str                              # 6 char ID (ex: "A1B2C3")
    status: GameStatus                   # 9 estados da máquina
    host_token: str                      # Token para endpoints /host/*
    created_at: datetime
    paused_at: Optional[datetime]
    generation_started_at: Optional[datetime]
    generation_finished_at: Optional[datetime]
    countdown_started_at: Optional[datetime]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    current_cycle: int                   # 0–6
    cycle_started_at: Optional[datetime]
    
    # Geração LLM
    local: Optional[str]                 # Descrição do local do crime
    objeto: Optional[str]                # Descrição do objeto
    motivacional: Optional[str]          # Motivação do criminoso
    historia_completa: Optional[str]     # Narrativa completa
    image_ready: bool                    # Imagem gerada?
    image_stage_bonus: int               # Bônus de estágio (Fotojornalista)
    
    # Desfecho
    accomplices_count_revealed: bool     # Criptógrafo já revelou count?
    winning_team_id: Optional[int]       # Time que ganhou (se houver)
    
    characters: list[Character]
    clues: list[Clue]
```

### Team

Uma equipe (ex: Policiais, Detetives).

```python
class Team(SQLModel, table=True):
    id: Optional[int]
    game_id: str                             # FK → Game
    equipe: Equipe                           # POLICIA | DETETIVES | JORNALISTAS | HACKERS
    created_at: datetime
    
    classification_blocked_until_cycle: Optional[int]  # Invasor de Sistema bloqueia
    accusation_used: bool                    # Já acusou alguém?
    accusation_correct: Optional[bool]       # Acusação foi correta?
    accused_criminoso_character_id: Optional[int]  # Quem foi acusado
    side_quest_hard_count: int               # Quantas hard side quests completou (para limite)
    
    players: list[Player]
```

### Player

Um jogador em um time.

```python
class Player(SQLModel, table=True):
    id: str                              # UUID
    team_id: int                         # FK → Team
    profissao: Optional[Profissao]       # Nenhuma até seleção
    nome: Optional[str]                  # Nome exibido
    ready: bool                          # Clicou "Pronto"?
    created_at: datetime
    
    # Constraint: team_id + profissao deve ser unique
```

### Character

Um dos 24 personagens (fichas civis).

```python
class Character(SQLModel, table=True):
    id: Optional[int]
    game_id: str
    profissao: Profissao                 # Qual profissão tem
    equipe: Equipe                       # Qual equipe
    is_npc: bool                         # True = NPC, False = jogador
    player_id: Optional[str]             # Se jogador, qual player
    
    # Bio (gerada pelo LLM)
    nome: str
    sobrenome: str
    idade: int
    genero: str
    avatar_seed: str                     # Para avatar placeholders
    personalidade: str
    relacao_com_vitima: Optional[str]    # Se relevante
    comentario: Optional[str]            # Comentário sobre o crime
    
    funcao_especial: FuncaoEspecial      # NENHUMA | CRIMINOSO | VITIMA | CUMPLICE
    eliminated: bool                     # Foi eliminado?
    action_used: bool                    # Já executou ação este ciclo?
    blocked_until_cycle: Optional[int]   # Bloqueado (ex: por Delegado)
    created_at: datetime
```

### Clue

Uma pista (informação sobre o crime).

```python
class Clue(SQLModel, table=True):
    id: Optional[int]
    game_id: str
    categoria: ClueCategory              # OBJETO_LOCAL | FICHA_CIVIL | LINHA_TEMPO
    veracidade: ClueVeracity             # VERDADEIRA | ENGANOSA | FALSA | INUTIL
    conteudo: str                        # Texto da pista
    target_character_id: Optional[int]   # Se FICHA_CIVIL, liga a qual personagem?
    revealed_at_cycle: Optional[int]     # Ciclo em que foi revelada (None = oculta)
    
    # Classificação (times tentam classificar como V/E/F/I)
    classified: bool
    classified_by_team_id: Optional[int]
    classified_at_cycle: Optional[int]
    classified_veracity: Optional[ClueVeracity]  # O que o time disse?
    
    # Eliminação/roubo
    eliminated: bool                     # Foi marcada como errada e eliminada?
    eliminated_at_cycle: Optional[int]
    stolen_by_team_id: Optional[int]     # Infiltrador rouba pistas eliminadas
    created_at: datetime
```

### Action

Registro de cada ação executada num ciclo.

```python
class Action(SQLModel, table=True):
    id: Optional[int]
    game_id: str
    cycle: int
    character_id: int                    # Quem executou
    team_id: int                         # De qual time
    kind: ActionKind                     # ELIMINATE_CHARACTER, REVEAL_TRUE_CLUE, etc
    target_character_id: Optional[int]   # Alvo (se eliminar/interrogar)
    target_clue_id: Optional[int]        # Alvo (se classificar/roubar)
    target_team_id: Optional[int]        # Alvo (se bloquear)
    result_json: Optional[str]           # Resultado serializado (ex: respostas interrogação)
    created_at: datetime
    
    # Constraint: game_id + character_id + cycle é unique
```

### SideQuest

Um mini-game (mastermind, labyrinth, higher/lower).

```python
class SideQuest(SQLModel, table=True):
    __tablename__ = "sidequest"
    
    id: Optional[int]
    game_id: str
    team_id: int
    cycle: int
    kind: SideQuestKind                  # MASTERMIND | LABYRINTH | HIGHER_LOWER
    difficulty: SideQuestDifficulty      # NORMAL | HARD
    status: SideQuestStatus              # PENDING | IN_PROGRESS | COMPLETED | EXPIRED
    reward: SideQuestReward              # REVEAL_EXTRA_CLUE | BLOCK_OPPONENT_CHARACTER
    state_json: str                      # Estado interno (ex: tentativas restantes)
    
    locked_by_player_id: Optional[str]   # Quem está jogando
    locked_at: Optional[datetime]        # Quando começou (timeout: 60s)
    completed_at: Optional[datetime]
    created_at: datetime
```

---

## Fluxo de Estados

A máquina de estados governa todo o jogo. São 9 estados:

```
┌─────────────┐
│    LOBBY    │  ← Inicial. Esperando times entrarem.
└──────┬──────┘
       │ Mínimo 2 times com 3+ jogadores cada
       ↓
┌──────────────────┐
│ TEAM_SELECTION   │  ← Teams criados, aguardando seleção de personagem.
└──────┬───────────┘
       │ Todos selecionaram profissão
       ↓
┌──────────────────┐
│ CHAR_SELECTION   │  ← Profissões selecionadas, faltam bios dos personagens.
└──────┬───────────┘
       │ [Automático quando geração termina com sucesso]
       ↓
┌──────────────────┐
│  READY_CHECK     │  ← Geração falhou ou reset. Todos clicam "Pronto"?
└──────┬───────────┘
       │ Host clica "Iniciar"
       ↓
┌──────────────────┐
│  GENERATING      │  ← LLM gerando crime, pistas, imagem (2+ min).
└──────┬───────────┘
       │ [Automático no fim] ou erro → volta a READY_CHECK
       ↓
┌──────────────────┐
│   COUNTDOWN      │  ← Countdown de 10s antes de começar.
└──────┬───────────┘
       │ Countdown terminou
       ↓
┌──────────────────┐
│    PLAYING       │  ← Jogo rodando. Ciclos acontecem aqui.
└──────┬───────────┘
       │ [Automático a cada ciclo] ou erro → volta a READY_CHECK
       │ 6 ciclos completados → FINISHED
       ↓
┌──────────────────┐
│    FINISHED      │  ← Jogo acabou. Exibindo placar.
└──────────────────┘

PAUSED está disponível em qualquer estado (host pausa).
```

### Transitions

- **LOBBY → TEAM_SELECTION**: `can_start()` retorna True (2+ times, 3+ por time, todas profissões únicas)
- **TEAM_SELECTION → CHAR_SELECTION**: Automaticamente se há profissões e faltam bios
- **CHAR_SELECTION → READY_CHECK**: Automaticamente quando `derive_status()` acha que geração ainda não começou
- **READY_CHECK → GENERATING**: Host clica "Iniciar" ou `schedule_generation_task()` é chamado
- **GENERATING → COUNTDOWN**: Geração sucedida após espera mínima (GENERATION_MIN_SECONDS = 2s)
- **COUNTDOWN → PLAYING**: Countdown (COUNTDOWN_SECONDS = 10s) terminou
- **PLAYING → FINISHED**: `current_cycle >= TOTAL_CYCLES` (6 ciclos completados)
- **\* → PAUSED**: Host pausa
- **PAUSED → \***: Host retoma (volta ao estado anterior)

### Error Handling

Se geração falhar (LLM error, DALLE error, validation error):
1. Game volta a **READY_CHECK**
2. Host pode tentar novamente clicando "Iniciar"
3. Log contém contexto do erro para debug

---

## 24 Profissões e Ações

Cada equipe tem 6 profissões. Cada jogador escolhe uma (única por time).

### POLICIA (Policiais)

| Profissão | Ação | Implementação |
|-----------|------|-----------------|
| Investigador Chefe | Elimina 1 personagem | `ELIMINATE_CHARACTER` |
| Perito Criminal | Revela 1 pista verdadeira (objeto/local) | `REVEAL_TRUE_CLUE` com target_clue_id |
| Interrogador | Interroga adversário (5 perguntas sim/não) | `INTERROGATE`, result_json contém respostas |
| Analista de Ocorrências | Classifica 1 pista (enganosa/falsa/inútil, linha do tempo) | `CLASSIFY_CLUE` |
| Oficial de Campo | 3 minutos no cômodo adversário (físico, sem ação) | `PHYSICAL_ROOM_ACCESS` |
| Delegado | Prende 1 adversário por 5 minutos (bloqueia ação próximo ciclo) | `PHYSICAL_DETAIN`, sets `blocked_until_cycle` |

### DETETIVES (Detetives Particulares)

| Profissão | Ação | Implementação |
|-----------|------|-----------------|
| Detetive Principal | Elimina 1 personagem | `ELIMINATE_CHARACTER` |
| Ex-Policial | 3 minutos no cômodo adversário (físico) | `PHYSICAL_ROOM_ACCESS` |
| Especialista em Fraude | Classifica 1 pista (enganosa/falsa/inútil, objeto/local) | `CLASSIFY_CLUE` |
| Infiltrador | Pega dicas eliminadas de objeto/local do adversário | `STEAL_ELIMINATED_CLUES` |
| Analista Comportamental | Classifica 1 pista (enganosa/falsa/inútil, ficha civil) | `CLASSIFY_CLUE` |
| Especialista em Vigilância | Classifica 1 pista (enganosa/falsa/inútil, linha do tempo) | `CLASSIFY_CLUE` |

### JORNALISTAS (Jornalistas Investigativos)

| Profissão | Ação | Implementação |
|-----------|------|-----------------|
| Editor Chefe | Elimina 1 personagem | `ELIMINATE_CHARACTER` |
| Repórter de Campo | Pega dicas eliminadas de fichas do adversário | `STEAL_ELIMINATED_CLUES` |
| Checador de Fatos | Classifica 1 pista (enganosa/falsa/inútil, objeto/local) | `CLASSIFY_CLUE` |
| Fotojornalista | Melhora a imagem (incrementa `image_stage_bonus`) | `IMPROVE_IMAGE` |
| Diretor Investigativo | Revela 1 pista verdadeira (ficha civil) | `REVEAL_TRUE_CLUE` |
| Colunista | Classifica 1 pista (enganosa/falsa/inútil, ficha civil) | `CLASSIFY_CLUE` |

### HACKERS (Agência de Inteligência)

| Profissão | Ação | Implementação |
|-----------|------|-----------------|
| Coordenador | Elimina 1 personagem | `ELIMINATE_CHARACTER` |
| Hacker | Mantém dificuldade de 3 side quests (nenhuma vira hard) | `LOCK_SIDE_QUESTS_HARD` |
| Criptógrafo | Revela número de cúmplices | `REVEAL_ACCOMPLICES_COUNT` |
| Engenheiro Social | Classifica 1 pista (enganosa/falsa/inútil, ficha civil) | `CLASSIFY_CLUE` |
| Analista de Metadados | Revela 1 pista verdadeira (objeto/local) | `REVEAL_TRUE_CLUE` |
| Invasor de Sistema | Bloqueia adversário de classificar 1 pista próximo ciclo | `BLOCK_OPPONENT_CLASSIFY`, sets `classification_blocked_until_cycle` |

---

## Mini-Games (Side Quests)

3 mini-games são oferecidos a cada equipe a cada ciclo. Completá-los dá recompensas.

### Mastermind

Adivinhar um código de 4 ou 5 dígitos em 8–10 tentativas.

- **Normal**: 4 dígitos, 8 tentativas
- **Hard**: 5 dígitos, 10 tentativas
- **Dificuldade**: A cada tentativa, o jogo retorna quantos dígitos estão corretos (bull) e quantos existem mas em posição errada (cows)

**Estado** (`state_json`):
```json
{
  "secret": "1234",
  "attempts_left": 8,
  "attempts": [
    {"guess": "5678", "bulls": 0, "cows": 0}
  ]
}
```

### Labyrinth

Explorar um labirinto gerado proceduralmente.

- **Normal**: 4×4, 20–30 rooms
- **Hard**: 5×5, 30–40 rooms
- **Dificuldade**: Sem mapa, deve lembrar caminho; algumas rooms têm traps (volta ao início)

**Estado** (`state_json`):
```json
{
  "grid": [[0, 1, 0], [1, 1, 0], [0, 1, 2]],
  "current": [0, 0],
  "exit": [2, 2],
  "visited": [[0, 0]],
  "trapped": false
}
```

### Higher / Lower

Adivinhar um número entre 1–50 ou 1–100 em 7–10 tentativas.

- **Normal**: 1–50, 7 tentativas
- **Hard**: 1–100, 10 tentativas
- **Dificuldade**: Binário. Após cada tentativa, saber se número é maior/menor

**Estado** (`state_json`):
```json
{
  "secret": 37,
  "attempts_left": 7,
  "attempts": [
    {"guess": 25, "result": "maior"}
  ]
}
```

### Recompensas

50% das recompensas: **Revelar pista extra** (qualquer pista não revelada)
40% das recompensas: **Bloquear adversário** (próximo ciclo, um adversário não pode classificar)

---

## Pistas (Clues)

O jogo tem 3 categorias de pistas, cada uma com 4 veracidades.

### Categorias

| Categoria | Quantidade | Descrição |
|-----------|-----------|-----------|
| **OBJETO_LOCAL** | 9 + 15 falsas | Informações sobre o local e objeto do crime |
| **FICHA_CIVIL** | 13 | Relacionamentos, alibi, comentários sobre os 24 personagens |
| **LINHA_TEMPO** | 9 | Sequência de eventos que levaram ao crime |

**Total**: ~51 pistas (dependendo de geração LLM)

### Veracidades

| Veracidade | Significado |
|-----------|-----------|
| **VERDADEIRA** | Dica é 100% correta |
| **ENGANOSA** | Dica é enganosa — parece verdadeira mas é falsa (ex: "Suspeito estava no local" mas na verdade estava em outro lugar) |
| **FALSA** | Dica é completamente falsa (não aconteceu) |
| **INUTIL** | Dica é verdadeira mas completamente irrelevante (ex: "Criminoso teve café da manhã com ovos") |

### Revelação por Ciclo

A cada ciclo, novas pistas são automaticamente reveladas conforme cronograma fixo (`CYCLE_CLUE_SCHEDULE`):

```python
CYCLE_CLUE_SCHEDULE = [
    # Ciclo 1
    [
        (OBJETO_LOCAL, VERDADEIRA),
        (LINHA_TEMPO, VERDADEIRA),
        (OBJETO_LOCAL, ENGANOSA),
        (LINHA_TEMPO, ENGANOSA),
    ],
    # Ciclo 2
    [(OBJETO_LOCAL, VERDADEIRA), (OBJETO_LOCAL, FALSA)],
    # Ciclo 3
    [(LINHA_TEMPO, VERDADEIRA), (LINHA_TEMPO, FALSA)],
    # Ciclo 4
    [(OBJETO_LOCAL, VERDADEIRA), (OBJETO_LOCAL, ENGANOSA)],
    # Ciclo 5
    [(LINHA_TEMPO, VERDADEIRA), (LINHA_TEMPO, ENGANOSA)],
    # Ciclo 6
    [(OBJETO_LOCAL, FALSA), (LINHA_TEMPO, FALSA)],
]
```

### Classificação

Times tentam classificar pistas como V/E/F/I. Acertos ganham pontos; erros perdem.

---

## Testes

46 testes automatizados cobrem lógica crítica.

### Rodar Testes

```bash
# Todos os testes
pytest

# Um arquivo específico
pytest tests/test_game_logic.py

# Uma função específica
pytest tests/test_game_logic.py::TestCanStart::test_insufficient_players

# Com cobertura
pytest --cov=jogo
```

### Estrutura

```
tests/
├── conftest.py                # Fixtures (in-memory DB, client, game states)
├── test_game_logic.py          # 7 testes (can_start, action xref, side quest submit)
├── test_actions_blocking.py    # 3 testes (bloqueio de ações por Invasor)
├── test_side_quests.py         # 6 testes (mastermind, labyrinth)
├── test_rewards.py             # 4 testes (recompensas)
├── test_image.py               # 7 testes (degradação de imagem)
├── test_clues.py               # 5 testes (revelação, atribuição de targets)
├── test_llm_mock.py            # 5 testes (mock mode)
├── test_narrative.py            # 7 testes (pipeline LLM)
└── test_game_flow.py           # 2 testes (fluxo completo)
```

### Exemplos

```python
def test_can_start_insufficient_players(game_with_teams):
    """Jogo não inicia com <6 jogadores."""
    assert not can_start(game_with_teams.session, game_with_teams.game.id)

def test_execute_action_correct_team(game_with_characters):
    """Personagem só pode executar ação do próprio time."""
    # Setup: player do time A, character do time B
    result = execute_action(...)
    assert result["ok"] == False
    assert "Personagem não pertence ao seu time" in result["error"]
```

---

## Desenvolvimento

### Adicionando Nova Profissão

1. **game_data.py**: Adicione à enum `Profissao` e `PROFISSOES_POR_EQUIPE`
2. **game_data.py**: Adicione descrição em `PROFISSAO_INFO`
3. **game_data.py**: Crie `ActionKind` correspondente se necessário
4. **actions.py**: Implemente lógica em `execute_action()`
5. **tests/**: Escreva testes da ação

Exemplo: Nova profissão "Psicólogo" (Policiais):

```python
# game_data.py
class Profissao(str, Enum):
    PSICOLOGIA = "psicologia"
    # ... resto

PROFISSOES_POR_EQUIPE[Equipe.POLICIA].append(Profissao.PSICOLOGIA)

PROFISSAO_INFO[Profissao.PSICOLOGIA] = (
    "Psicólogo",
    "Descobre qual é a motivação verdadeira do criminoso",
)

class ActionKind(str, Enum):
    REVEAL_CRIMINAL_MOTIVATION = "reveal_criminal_motivation"

# actions.py
PROFISSAO_TO_ACTION = {
    # ...
    Profissao.PSICOLOGIA: ActionKind.REVEAL_CRIMINAL_MOTIVATION,
}

def execute_action(...):
    if action_kind == ActionKind.REVEAL_CRIMINAL_MOTIVATION:
        # Implementar lógica
        pass
```

### Adicionando Novo Mini-Game

1. **game_data.py**: Adicione `SideQuestKind` e configurações (digits, max attempts, etc)
2. **side_quests.py**: Implemente funções `_<name>_state()`, `_<name>_next_state()`, `_validate_<name>_submission()`
3. **side_quests.py**: Adicione ao `_KIND_TO_FUNCTIONS` dict
4. **tests/**: Escreva testes

### Adicionando Nova Categoria de Pista

1. **game_data.py**: Adicione à enum `ClueCategory`
2. **game_data.py**: Configure contagens em `CLUE_COUNTS`
3. **narrative.py**: Adicione etapa de geração LLM
4. **narrative_schemas.py**: Defina schema Pydantic para output
5. **clues.py**: Atualize `assign_ficha_civil_targets()` se necessário
6. **tests/**: Escreva testes

### Performance

**N+1 Query Optimization** (Nice-to-have, v1.1):

Evite patterns como:

```python
# ❌ Ruim: 1 query por team
teams = get_teams(session, game_id)
for team in teams:
    players = get_players(session, team.id)  # N+1
```

Prefira:

```python
# ✅ Bom: 1 query
teams = session.exec(
    select(Team)
    .where(Team.game_id == game_id)
    .options(selectinload(Team.players))
).all()
```

Locais críticos a otimizar:
- `engine.py`: `get_teams()`, `get_players()`, `all_players()`
- `actions.py`: Queries durante execução de ação
- `api/pages.py`: Rendering de game state

### Migrações (Alembic)

Setup inicial está em `alembic/`. Para criar nova migração após mudança no schema:

```bash
# Auto-detecta changes em models.py
alembic revision --autogenerate -m "Descrição da mudança"

# Aplica migrações
alembic upgrade head
```

**Status**: Esqueleto criado; migrações manuais não implementadas ainda. Para v1.1+.

---

## Deployment

### Local (Dev)

```bash
source .venv/bin/activate
uvicorn jogo.main:app --host 0.0.0.0 --port 8000
```

### Production (Futuro)

Para vender ou fazer produção, considerar:

1. **Database**: Migrar SQLite → PostgreSQL
2. **Auth**: Host token via QR code está OK; considerar rate limiting
3. **Rate Limits**: Adicionar rate limiting em endpoints críticos
4. **Secrets**: `.env` não deve ser commitado; usar secret manager
5. **HTTPS**: Reverse proxy (nginx) com Let's Encrypt
6. **Logging**: Logging estruturado + APM (Sentry, DataDog)
7. **Monitoring**: Health checks, uptime monitoring
8. **Storage**: Imagens → S3 ou similar (atualmente em disk)

### Notas de Segurança

- **Host Token**: 24 caracteres URL-safe. Regenerado por game. OK para amigos; production precisa de OAuth.
- **WebSocket**: Sem auth a nível de socket. Confiança é implícita (QR code é semi-público).
- **SQL Injection**: SQLModel/SQLAlchemy previnem via parametrização.
- **Rate Limiting**: Não implementado. Production adiciona em endpoints de ação.
- **Imagem**: DALL-E via OpenAI (seguro). Locale/objeto/história são user-generated → sanitizar antes de log.

---

## Próximas Melhorias (v1.1+)

- ✅ **P0 (Critical)**: Geração LLM deadlock, DALLE failure, profession race condition, WebSocket detection — FEITO
- ✅ **P1 (Important)**: Logging context, pytest smoke tests, Alembic skeleton — FEITO
- ✅ **P2 (Nice-to-have)**: N+1 optimization, concurrent action tests — DOCUMENTADO
- 🔄 **v1.1 Roadmap**:
  - [ ] Implementar N+1 optimization
  - [ ] Ativar Alembic migrações automáticas
  - [ ] Adicionar testes de race condition (concurrent actions)
  - [ ] Suportar observer mode (assistir sem jogar)
  - [ ] Admin dashboard (logs, analytics)

---

## Contribuindo

### Code Style

- **Python**: PEP 8 (Black, Flake8)
- **Docstrings**: Google-style, uma linha por função (WHY é a prioridade)
- **Type hints**: Sempre (Pydantic, SQLModel)
- **Tests**: Mínimo uma cobertura por feature

### PR Workflow

1. Crie branch: `git checkout -b feat/your-feature`
2. Implemente + testes
3. Rode testes: `pytest`
4. Abra PR (descrição clara do porquê)
5. Code review → merge

### Reporte Bugs

Include:
- Python version (`python --version`)
- Como reproduzir (steps)
- Erro completo (screenshot + logs)
- `.env` redacted (sem API keys)

---

## Suporte

Perguntas? Issues? Abra um GitHub issue ou entre em contato.

**Última atualização**: Maio 2026
**Versão**: 1.0
