"""Distribuição e visibilidade de pistas por ciclo.

Fluxo:
  1. assign_ficha_civil_targets(session, game_id) — roda uma vez no início do
     ciclo 1: liga cada Clue FICHA_CIVIL a um Character via target_character_id.
  2. reveal_for_cycle(session, game_id, cycle) — roda a cada ciclo: marca
     revealed_at_cycle nas Clues de OBJETO_LOCAL e LINHA_TEMPO conforme o
     cronograma fixo definido em CYCLE_CLUE_SCHEDULE.
  3. visible_clues(session, game_id) — retorna todas as Clues já reveladas.

FICHA_CIVIL são reveladas via ação Interrogador (not aqui).
"""

from __future__ import annotations

import random
from typing import Optional

from sqlmodel import Session, select

from jogo.db.models import Character, Clue
from jogo.game_data import (
    ClueCategory,
    ClueVeracity,
    FuncaoEspecial,
    TOTAL_CYCLES,
)

CC = ClueCategory
CV = ClueVeracity

# Pistas automáticas reveladas por ciclo (OBJETO_LOCAL e LINHA_TEMPO apenas).
# Índice 0 = ciclo 1. Cada slot é uma tupla (categoria, veracidade).
# OL tem 3V + 2EN + 2FA; LT tem 3V + 2EN + 2FA.
CYCLE_CLUE_SCHEDULE: list[list[tuple[CC, CV]]] = [
    # ciclo 1
    [(CC.OBJETO_LOCAL, CV.VERDADEIRA), (CC.LINHA_TEMPO, CV.VERDADEIRA),
     (CC.OBJETO_LOCAL, CV.ENGANOSA), (CC.LINHA_TEMPO, CV.ENGANOSA)],
    # ciclo 2
    [(CC.OBJETO_LOCAL, CV.VERDADEIRA), (CC.OBJETO_LOCAL, CV.FALSA)],
    # ciclo 3
    [(CC.LINHA_TEMPO, CV.VERDADEIRA), (CC.LINHA_TEMPO, CV.FALSA)],
    # ciclo 4
    [(CC.OBJETO_LOCAL, CV.VERDADEIRA), (CC.OBJETO_LOCAL, CV.ENGANOSA)],
    # ciclo 5
    [(CC.LINHA_TEMPO, CV.VERDADEIRA), (CC.LINHA_TEMPO, CV.ENGANOSA)],
    # ciclo 6
    [(CC.OBJETO_LOCAL, CV.FALSA), (CC.LINHA_TEMPO, CV.FALSA)],
]


def assign_ficha_civil_targets(session: Session, game_id: str) -> None:
    """Liga cada Clue FICHA_CIVIL a um Character. Idempotente."""
    already = session.exec(
        select(Clue).where(
            Clue.game_id == game_id,
            Clue.categoria == CC.FICHA_CIVIL,
            Clue.target_character_id.isnot(None),  # type: ignore[attr-defined]
        )
    ).first()
    if already:
        return

    chars = list(
        session.exec(
            select(Character).where(Character.game_id == game_id)
        ).all()
    )
    criminoso = next(
        (c for c in chars if c.funcao_especial == FuncaoEspecial.CRIMINOSO), None
    )
    cumplices = [c for c in chars if c.funcao_especial == FuncaoEspecial.CUMPLICE]
    vitima = next(
        (c for c in chars if c.funcao_especial == FuncaoEspecial.VITIMA), None
    )

    involved_ids = {c.id for c in [criminoso, vitima, *cumplices] if c}
    not_involved = [c for c in chars if c.id not in involved_ids]

    rng = random.Random(game_id + "_fc")
    rng.shuffle(not_involved)

    clues = list(
        session.exec(
            select(Clue)
            .where(Clue.game_id == game_id, Clue.categoria == CC.FICHA_CIVIL)
            .order_by(Clue.id)
        ).all()
    )

    verdadeiras = [c for c in clues if c.veracidade == CV.VERDADEIRA]
    enganosas = [c for c in clues if c.veracidade == CV.ENGANOSA]
    falsas = [c for c in clues if c.veracidade == CV.FALSA]
    inuteis = [c for c in clues if c.veracidade == CV.INUTIL]

    assignments: list[tuple[Clue, Optional[int]]] = []
    ni_iter = iter(not_involved)
    v_idx = 0

    # Verdadeiras → criminoso (2) depois cúmplices (1 cada), resto para inocentes
    if criminoso and len(verdadeiras) >= 2:
        assignments += [(verdadeiras[0], criminoso.id), (verdadeiras[1], criminoso.id)]
        v_idx = 2
    elif criminoso and verdadeiras:
        assignments.append((verdadeiras[0], criminoso.id))
        v_idx = 1

    for cumplice in cumplices:
        if v_idx < len(verdadeiras):
            assignments.append((verdadeiras[v_idx], cumplice.id))
            v_idx += 1

    while v_idx < len(verdadeiras):
        ni = next(ni_iter, None)
        if ni is None:
            break
        assignments.append((verdadeiras[v_idx], ni.id))
        v_idx += 1

    for clue in enganosas:
        ni = next(ni_iter, None)
        assignments.append((clue, ni.id if ni else None))

    for clue in falsas:
        ni = next(ni_iter, None)
        assignments.append((clue, ni.id if ni else None))

    all_shuffled = chars.copy()
    rng.shuffle(all_shuffled)
    for clue, char in zip(inuteis, all_shuffled):
        assignments.append((clue, char.id))

    for clue, char_id in assignments:
        if char_id is not None:
            clue.target_character_id = char_id
            session.add(clue)

    session.commit()


def reveal_for_cycle(session: Session, game_id: str, cycle: int) -> None:
    """Marca revealed_at_cycle nas Clues do ciclo. Idempotente."""
    if not (1 <= cycle <= TOTAL_CYCLES):
        return

    slots = CYCLE_CLUE_SCHEDULE[cycle - 1]
    for categoria, veracidade in slots:
        clue = session.exec(
            select(Clue)
            .where(
                Clue.game_id == game_id,
                Clue.categoria == categoria,
                Clue.veracidade == veracidade,
                Clue.revealed_at_cycle.is_(None),  # type: ignore[attr-defined]
            )
            .order_by(Clue.id)
            .limit(1)
        ).first()
        if clue:
            clue.revealed_at_cycle = cycle
            session.add(clue)

    session.commit()


def visible_clues(session: Session, game_id: str) -> list[Clue]:
    """Retorna todas as Clues já reveladas, ordenadas por ciclo e id."""
    return list(
        session.exec(
            select(Clue)
            .where(
                Clue.game_id == game_id,
                Clue.revealed_at_cycle.isnot(None),  # type: ignore[attr-defined]
            )
            .order_by(Clue.revealed_at_cycle, Clue.id)
        ).all()
    )


def visible_clues_by_category(
    session: Session, game_id: str
) -> dict[ClueCategory, list[Clue]]:
    """Group all revealed clues by category."""
    all_clues = visible_clues(session, game_id)
    result: dict[ClueCategory, list[Clue]] = {c: [] for c in ClueCategory}
    for clue in all_clues:
        result[clue.categoria].append(clue)
    return result


def validate_clue_targets(session: Session, game_id: str) -> list[str]:
    """QoL: Valida que todas as pistas FICHA_CIVIL têm target_character_id.

    Retorna lista de problemas encontrados (vazia = OK).
    """
    problems = []
    clues = list(
        session.exec(
            select(Clue).where(
                Clue.game_id == game_id,
                Clue.categoria == CC.FICHA_CIVIL,
            )
        ).all()
    )

    for clue in clues:
        if clue.target_character_id is None:
            problems.append(f"Clue {clue.id} (FICHA_CIVIL) sem target_character_id")

    return problems
