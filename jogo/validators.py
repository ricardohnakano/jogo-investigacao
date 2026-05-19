"""Validators determinísticos para outputs do LLM.

Cada validator recebe um output Pydantic e retorna lista de problemas
(vazia = OK). Em caso de problema, `llm.generate` faz retry com feedback.
"""

from jogo.game_data import PROFISSOES_POR_EQUIPE, Profissao
from jogo.narrative_schemas import (
    CharacterCommentsOutput,
    FichaCivilCluesOutput,
    LinhaTempoCluesOutput,
    ObjetoLocalCluesOutput,
    StoryOutput,
)


def validate_story(num_cumplices: int):
    def _check(out: StoryOutput) -> list[str]:
        problems: list[str] = []
        if len(out.personalidade_criminoso) != 3:
            problems.append(
                f"personalidade_criminoso precisa ter 3 itens, achou {len(out.personalidade_criminoso)}"
            )
        if "desconhecid" in out.relacao_criminoso_vitima.lower():
            problems.append(
                "relacao_criminoso_vitima não pode ser 'desconhecidos'"
            )
        if len(out.relacao_criminoso_cumplices) != num_cumplices:
            problems.append(
                f"relacao_criminoso_cumplices precisa ter {num_cumplices} itens "
                f"(número de cúmplices), achou {len(out.relacao_criminoso_cumplices)}"
            )
        for i, r in enumerate(out.relacao_criminoso_cumplices):
            if "desconhecid" in r.lower():
                problems.append(
                    f"relacao_criminoso_cumplices[{i}] não pode ser 'desconhecidos'"
                )
        return problems

    return _check


def validate_objeto_local_clues(out: ObjetoLocalCluesOutput) -> list[str]:
    problems: list[str] = []
    expected = {
        "dicas_uteis": 3, "dicas_enganosas": 2, "dicas_falsas": 2,
        "dicas_inuteis": 2, "extras_falsas": 15,
    }
    for field, n in expected.items():
        got = len(getattr(out, field))
        if got != n:
            problems.append(f"{field} precisa ter {n} itens, achou {got}")
    for field in ["dicas_uteis", "dicas_enganosas", "dicas_falsas",
                  "dicas_inuteis", "extras_falsas"]:
        for i, c in enumerate(getattr(out, field)):
            if not c.strip():
                problems.append(f"{field}[{i}] está vazio")
            if len(c) > 500:
                problems.append(f"{field}[{i}] muito longo (>{500} chars)")
    return problems


def validate_ficha_civil_clues(out: FichaCivilCluesOutput) -> list[str]:
    problems: list[str] = []
    expected = {
        "dicas_uteis": 5, "dicas_enganosas": 2, "dicas_falsas": 2,
        "dicas_inuteis": 2,
    }
    for field, n in expected.items():
        got = len(getattr(out, field))
        if got != n:
            problems.append(f"{field} precisa ter {n} itens, achou {got}")
    return problems


def validate_linha_tempo_clues(
    valid_names: set[str], envolvidos: set[str]
):
    def _check(out: LinhaTempoCluesOutput) -> list[str]:
        problems: list[str] = []
        expected = {
            "eventos_uteis": 3, "eventos_enganosos": 2, "eventos_falsos": 2,
            "eventos_inuteis": 2,
        }
        for field, n in expected.items():
            got = len(getattr(out, field))
            if got != n:
                problems.append(f"{field} precisa ter {n} itens, achou {got}")

        for nome_field in ["distracao_personagem_1_nome", "distracao_personagem_2_nome"]:
            nome = getattr(out, nome_field).strip()
            if nome not in valid_names:
                problems.append(
                    f"{nome_field}='{nome}' não está entre os 24 personagens"
                )
            if nome in envolvidos:
                problems.append(
                    f"{nome_field}='{nome}' é criminoso/vítima/cúmplice — escolha um personagem NÃO envolvido"
                )
        if out.distracao_personagem_1_nome == out.distracao_personagem_2_nome:
            problems.append(
                "distracao_personagem_1_nome e _2_nome devem ser personagens diferentes"
            )
        return problems

    return _check


def validate_character_comments(out: CharacterCommentsOutput) -> list[str]:
    problems: list[str] = []
    valid_profs = {p.value for p in Profissao}
    keys = set(out.comentarios.keys())
    missing = valid_profs - keys
    extra = keys - valid_profs
    if missing:
        problems.append(f"comentarios faltando para: {sorted(missing)}")
    if extra:
        problems.append(f"comentarios com chaves inválidas: {sorted(extra)}")
    for prof, com in out.comentarios.items():
        if not com.strip():
            problems.append(f"comentario para {prof} está vazio")
        if len(com) > 300:
            problems.append(f"comentario para {prof} muito longo (>300 chars)")
    return problems


__all__ = [
    "validate_story",
    "validate_objeto_local_clues",
    "validate_ficha_civil_clues",
    "validate_linha_tempo_clues",
    "validate_character_comments",
    "PROFISSOES_POR_EQUIPE",
]
