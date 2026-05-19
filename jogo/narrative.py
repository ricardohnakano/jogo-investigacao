"""Pipeline de geração narrativa via LLM.

5 etapas:
1. História completa + personalidade do criminoso + relações
2. Dicas de objeto/local (9 + 15 extras)
3. Dicas de ficha civil (11)
4. Dicas de linha do tempo (9 + 2 distrações)
5. Comentários sobre os 24 personagens

Cada etapa é uma chamada estruturada ao LLM (com retry e validação).
"""

from __future__ import annotations

from sqlmodel import Session, select

from jogo import llm, validators
from jogo.db.models import Character, Clue, Game
from jogo.game_data import (
    EQUIPE_LABEL,
    PROFISSAO_INFO,
    ClueCategory,
    ClueVeracity,
    FuncaoEspecial,
    Profissao,
)
from jogo.narrative_schemas import (
    CharacterCommentsOutput,
    FichaCivilCluesOutput,
    LinhaTempoCluesOutput,
    ObjetoLocalCluesOutput,
    StoryOutput,
)


SYSTEM_CACHED = """Você é o roteirista de um jogo de investigação criminal em grupo, em português brasileiro.

**O mundo**
Existem 4 equipes investigativas (Policiais, Detetives Particulares, Jornalistas Investigativos, Agência de Inteligência), cada uma com 6 profissões. Os jogadores assumem essas profissões.

Em cada partida há:
- 1 criminoso (uma profissão)
- 1 vítima (profissão diferente, equipe diferente)
- 0 a 2 cúmplices (profissões diferentes, equipes diferentes do criminoso e da vítima)
- 1 local do crime
- 1 objeto encontrado no local
- 1 motivacional do crime

**Sua tarefa**
Gerar conteúdo narrativo de altíssima qualidade pro jogo: história verossímil, dicas que se cruzem coerentemente, personagens com personalidade.

**Regras estritas**
1. As pistas marcadas como VERDADEIRAS devem ser de fato coerentes com a história canônica.
2. Pistas ENGANOSAS são fatos verdadeiros mas que, isolados, sugerem hipóteses erradas.
3. Pistas FALSAS são plantadas, adulteradas ou produto de confusão — devem ter explicação plausível.
4. Pistas INÚTEIS são verdadeiras mas não ajudam a resolver o caso (dão cor ao mundo).
5. Nenhuma pista isolada pode entregar a solução inteira.
6. O caso deve ser resolvível em até 60 minutos cruzando 3+ pistas úteis.
7. Use tom realista, não melodramático. Vocabulário brasileiro.
8. Nunca inclua nomes que não estão entre os 24 personagens fornecidos.
9. Critério para "criminoso/cúmplices/vítima em equipes diferentes" já está garantido pelo sistema — não vacile nesse ponto.
"""


def _ctx_personagens(characters: list[Character]) -> str:
    """Formata os 24 personagens para o prompt."""
    lines: list[str] = []
    for c in characters:
        funcao = c.funcao_especial.value if c.funcao_especial != FuncaoEspecial.NENHUMA else "-"
        lines.append(
            f"- {c.nome} {c.sobrenome} | {PROFISSAO_INFO[c.profissao][0]} | "
            f"{EQUIPE_LABEL[c.equipe]} | {c.idade}a | {c.genero} | {funcao}"
        )
    return "\n".join(lines)


def _ctx_envolvidos(characters: list[Character]) -> dict:
    """Acha criminoso/vítima/cúmplices."""
    by_func = {f: [c for c in characters if c.funcao_especial == f]
               for f in [FuncaoEspecial.CRIMINOSO, FuncaoEspecial.VITIMA, FuncaoEspecial.CUMPLICE]}
    crim = by_func[FuncaoEspecial.CRIMINOSO][0]
    vit = by_func[FuncaoEspecial.VITIMA][0]
    cumplices = by_func[FuncaoEspecial.CUMPLICE]
    return {"criminoso": crim, "vitima": vit, "cumplices": cumplices}


def _format_envolvido(c: Character) -> str:
    return (
        f"{c.nome} {c.sobrenome}, {c.idade} anos, {PROFISSAO_INFO[c.profissao][0]} "
        f"({EQUIPE_LABEL[c.equipe]})"
    )


def generate_story(
    game: Game, characters: list[Character]
) -> StoryOutput:
    env = _ctx_envolvidos(characters)
    crim, vit, cumplices = env["criminoso"], env["vitima"], env["cumplices"]

    cumplices_str = (
        "\n".join(f"  - Cúmplice: {_format_envolvido(c)}" for c in cumplices)
        if cumplices else "  (sem cúmplices)"
    )

    user = f"""Construa a história canônica do crime:

**Dados sorteados**
- Criminoso: {_format_envolvido(crim)}
- Vítima: {_format_envolvido(vit)}
- Cúmplices:
{cumplices_str}
- Local do crime: {game.local}
- Objeto encontrado: {game.objeto}
- Motivacional: {game.motivacional}

**Você deve produzir**
1. `historia_completa`: 4-8 frases narrando o crime — motivo, planejamento, execução, e por que o objeto está no local.
2. `personalidade_criminoso`: 3 características consistentes com o motivacional. Ex: motivacional de vingança → "rancoroso, paciente, calculista".
3. `relacao_criminoso_vitima`: como criminoso e vítima se conheciam. Nunca "desconhecidos".
4. `relacao_criminoso_cumplices`: como o criminoso conhece cada cúmplice (uma string por cúmplice, na ordem fornecida acima). Lista vazia se sem cúmplices."""

    return llm.generate(
        StoryOutput,
        system_cached=SYSTEM_CACHED,
        user=user,
        step_name="story",
        validators=[validators.validate_story(len(cumplices))],
    )


def generate_objeto_local_clues(
    game: Game, characters: list[Character], story: StoryOutput
) -> ObjetoLocalCluesOutput:
    user = f"""Gere as dicas de OBJETO/LOCAL do crime.

**Verdade canônica**
- Local: {game.local}
- Objeto: {game.objeto}
- História: {story.historia_completa}

Produza:
- 3 dicas VERDADEIRAS e relevantes (úteis pra cruzar e descobrir local+objeto)
- 2 dicas ENGANOSAS (fatos reais que sugerem hipótese errada se vistos isolados)
- 2 dicas FALSAS (testemunhas confusas, pistas plantadas) — cada uma com explicação plausível embutida
- 2 dicas INÚTEIS (verdadeiras mas irrelevantes — cor do mundo)
- 15 EXTRAS_FALSAS sobre OUTROS locais/objetos (distrações que apontem pra coisas diferentes do real)

Crucial: as 3 verdadeiras devem ser suficientes pra um time atento cruzar e identificar local+objeto. Mas nenhuma sozinha entrega tudo."""

    return llm.generate(
        ObjetoLocalCluesOutput,
        system_cached=SYSTEM_CACHED,
        user=user,
        step_name="objeto_local",
        validators=[validators.validate_objeto_local_clues],
    )


def generate_ficha_civil_clues(
    characters: list[Character], story: StoryOutput
) -> FichaCivilCluesOutput:
    env = _ctx_envolvidos(characters)
    crim, vit, cumplices = env["criminoso"], env["vitima"], env["cumplices"]

    cumplices_str = (
        "\n".join(f"  - {_format_envolvido(c)}" for c in cumplices)
        if cumplices else "  (sem cúmplices)"
    )

    user = f"""Gere as dicas de FICHA CIVIL sobre criminoso e cúmplices.

**Verdade canônica**
- Criminoso: {_format_envolvido(crim)}
  Personalidade: {", ".join(story.personalidade_criminoso)}
  Relação com vítima: {story.relacao_criminoso_vitima}
- Cúmplices:
{cumplices_str}
- Vítima: {_format_envolvido(vit)}
- Resumo: {story.historia_completa}

Produza:
- 5 dicas VERDADEIRAS (5+ úteis pra identificar criminoso e cúmplices quando cruzadas — comportamento, acesso, hábitos, conexões)
- 2 dicas ENGANOSAS (verdades sobre OUTROS personagens que parecem incriminá-los)
- 2 dicas FALSAS (álibis adulterados, testemunhas confusas)
- 2 dicas INÚTEIS (verdadeiras mas que não identificam quem cometeu)

Cada dica é um trecho de ficha/comportamento (ex: "Tinha acesso à sala dos servidores fora do horário comercial")."""

    return llm.generate(
        FichaCivilCluesOutput,
        system_cached=SYSTEM_CACHED,
        user=user,
        step_name="ficha_civil",
        validators=[validators.validate_ficha_civil_clues],
    )


def generate_linha_tempo_clues(
    game: Game, characters: list[Character], story: StoryOutput
) -> LinhaTempoCluesOutput:
    env = _ctx_envolvidos(characters)
    envolvidos_nomes = {
        f"{c.nome} {c.sobrenome}"
        for c in [env["criminoso"], env["vitima"], *env["cumplices"]]
    }
    all_nomes = {f"{c.nome} {c.sobrenome}" for c in characters}

    user = f"""Gere a LINHA DO TEMPO do crime + 2 distrações.

**Verdade canônica**
- Local: {game.local}
- Objeto: {game.objeto}
- Resumo: {story.historia_completa}

**Personagens disponíveis** (todos os 24):
{_ctx_personagens(characters)}

**Envolvidos no crime (NÃO use nas distrações):**
{", ".join(sorted(envolvidos_nomes))}

Produza:
- 3 eventos VERDADEIROS úteis da linha do tempo do crime (formato 'HH:MM — descrição')
- 2 eventos ENGANOSOS (verdadeiros mas sugerem suspeito errado)
- 2 eventos FALSOS (com explicação plausível)
- 2 eventos INÚTEIS (verdadeiros mas irrelevantes)
- 2 LINHAS DO TEMPO DISTRAÇÃO de OUTROS personagens NÃO envolvidos (escolha 2 distintos da lista acima que NÃO estão entre os envolvidos). Cada uma com 4-6 eventos plausíveis pro dia. Reporte o nome completo de cada um."""

    return llm.generate(
        LinhaTempoCluesOutput,
        system_cached=SYSTEM_CACHED,
        user=user,
        step_name="linha_tempo",
        validators=[validators.validate_linha_tempo_clues(all_nomes, envolvidos_nomes)],
    )


def generate_character_comments(
    characters: list[Character], story: StoryOutput
) -> CharacterCommentsOutput:
    user = f"""Gere um comentário curto (1-2 frases) sobre cada um dos 24 personagens.

**Personagens:**
{_ctx_personagens(characters)}

**Contexto do crime:**
{story.historia_completa}

Cada comentário descreve como o personagem é visto pelos outros (reputação, hábitos visíveis, traços que aparecem em conversa). Não revele função especial. Inclua os 24, indexados pelo VALOR DO ENUM da profissão:
{", ".join(p.value for p in Profissao)}

Output: um dict com exatamente 24 entradas em `comentarios`."""

    return llm.generate(
        CharacterCommentsOutput,
        system_cached=SYSTEM_CACHED,
        user=user,
        step_name="comentarios",
        validators=[validators.validate_character_comments],
    )


def _persist_clues(
    session: Session,
    game_id: str,
    category: ClueCategory,
    items: dict[ClueVeracity, list[str]],
) -> None:
    for veracity, contents in items.items():
        for c in contents:
            session.add(Clue(
                game_id=game_id,
                categoria=category,
                veracidade=veracity,
                conteudo=c,
            ))


def generate_all(session: Session, game: Game) -> None:
    """Pipeline completa: gera tudo e persiste no banco. Idempotente."""
    if game.historia_completa:
        return

    characters = list(
        session.exec(select(Character).where(Character.game_id == game.id)).all()
    )
    if len(characters) != 24:
        raise RuntimeError(
            f"generate_all chamado mas há {len(characters)} characters (esperado 24)"
        )

    story = generate_story(game, characters)
    objeto_local = generate_objeto_local_clues(game, characters, story)
    ficha_civil = generate_ficha_civil_clues(characters, story)
    linha_tempo = generate_linha_tempo_clues(game, characters, story)
    comentarios = generate_character_comments(characters, story)

    game.historia_completa = story.historia_completa
    session.add(game)

    env = _ctx_envolvidos(characters)
    crim, vit, cumplices = env["criminoso"], env["vitima"], env["cumplices"]
    crim.personalidade = ", ".join(story.personalidade_criminoso)
    crim.relacao_com_vitima = story.relacao_criminoso_vitima
    vit.relacao_com_vitima = "(vítima)"
    session.add(crim)
    session.add(vit)
    for c, rel in zip(cumplices, story.relacao_criminoso_cumplices):
        c.relacao_com_vitima = rel
        session.add(c)

    chars_by_prof: dict[str, Character] = {c.profissao.value: c for c in characters}
    for prof_value, com in comentarios.comentarios.items():
        char = chars_by_prof.get(prof_value)
        if char:
            char.comentario = com
            session.add(char)

    _persist_clues(session, game.id, ClueCategory.OBJETO_LOCAL, {
        ClueVeracity.VERDADEIRA: objeto_local.dicas_uteis,
        ClueVeracity.ENGANOSA: objeto_local.dicas_enganosas,
        ClueVeracity.FALSA: objeto_local.dicas_falsas + objeto_local.extras_falsas,
        ClueVeracity.INUTIL: objeto_local.dicas_inuteis,
    })
    _persist_clues(session, game.id, ClueCategory.FICHA_CIVIL, {
        ClueVeracity.VERDADEIRA: ficha_civil.dicas_uteis,
        ClueVeracity.ENGANOSA: ficha_civil.dicas_enganosas,
        ClueVeracity.FALSA: ficha_civil.dicas_falsas,
        ClueVeracity.INUTIL: ficha_civil.dicas_inuteis,
    })

    distracao_1 = [f"[{linha_tempo.distracao_personagem_1_nome}] {e}" for e in linha_tempo.distracao_personagem_1]
    distracao_2 = [f"[{linha_tempo.distracao_personagem_2_nome}] {e}" for e in linha_tempo.distracao_personagem_2]
    _persist_clues(session, game.id, ClueCategory.LINHA_TEMPO, {
        ClueVeracity.VERDADEIRA: linha_tempo.eventos_uteis,
        ClueVeracity.ENGANOSA: linha_tempo.eventos_enganosos,
        ClueVeracity.FALSA: linha_tempo.eventos_falsos + distracao_1 + distracao_2,
        ClueVeracity.INUTIL: linha_tempo.eventos_inuteis,
    })

    session.commit()


def validate_persisted(session: Session, game_id: str) -> list[str]:
    """Sanity checks pós-persistência. Útil em testes e debug."""
    from jogo.game_data import CLUE_COUNTS

    problems: list[str] = []
    clues = list(session.exec(select(Clue).where(Clue.game_id == game_id)).all())

    for category, by_ver in CLUE_COUNTS.items():
        for veracity, expected in by_ver.items():
            n = sum(1 for c in clues if c.categoria == category and c.veracidade == veracity)
            min_expected = expected
            if n < min_expected:
                problems.append(
                    f"{category.value}/{veracity.value}: esperava >={min_expected}, achou {n}"
                )
    return problems
