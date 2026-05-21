"""Execução de ações dos personagens durante o game loop.

execute_action(session, game, character, team, body) aplica o efeito
server-side da ação, cria o registro em Action e marca character.action_used.

Ações físicas (Delegado, Oficial, Ex-policial) apenas registram o uso.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlmodel import Session, select

from jogo.db.models import Action, Character, Clue, Game, GameStatus, Team
from jogo.game_data import (
    ActionKind,
    ClueCategory,
    ClueVeracity,
    FuncaoEspecial,
    IMAGE_STAGES,
    Profissao,
)

# ---------------------------------------------------------------------------
# Mapeamentos profissão → ação / categoria
# ---------------------------------------------------------------------------

PROFISSAO_TO_ACTION: dict[Profissao, ActionKind] = {
    Profissao.INVESTIGADOR_CHEFE: ActionKind.ELIMINATE_CHARACTER,
    Profissao.DETETIVE_PRINCIPAL: ActionKind.ELIMINATE_CHARACTER,
    Profissao.EDITOR_CHEFE: ActionKind.ELIMINATE_CHARACTER,
    Profissao.COORDENADOR: ActionKind.ELIMINATE_CHARACTER,

    Profissao.PERITO_CRIMINAL: ActionKind.REVEAL_TRUE_CLUE,
    Profissao.DIRETOR_INVESTIGATIVO: ActionKind.REVEAL_TRUE_CLUE,
    Profissao.ANALISTA_METADADOS: ActionKind.REVEAL_TRUE_CLUE,

    Profissao.INTERROGADOR: ActionKind.INTERROGATE,

    Profissao.ANALISTA_OCORRENCIAS: ActionKind.CLASSIFY_CLUE,
    Profissao.ESPECIALISTA_FRAUDE: ActionKind.CLASSIFY_CLUE,
    Profissao.ESPECIALISTA_VIGILANCIA: ActionKind.CLASSIFY_CLUE,
    Profissao.CHECADOR_FATOS: ActionKind.CLASSIFY_CLUE,
    Profissao.ANALISTA_COMPORTAMENTAL: ActionKind.CLASSIFY_CLUE,
    Profissao.ENGENHEIRO_SOCIAL: ActionKind.CLASSIFY_CLUE,
    Profissao.COLUNISTA: ActionKind.CLASSIFY_CLUE,

    Profissao.INFILTRADOR: ActionKind.STEAL_ELIMINATED_CLUES,
    Profissao.REPORTER_CAMPO: ActionKind.STEAL_ELIMINATED_CLUES,

    Profissao.INVASOR_SISTEMA: ActionKind.BLOCK_OPPONENT_CLASSIFY,
    Profissao.HACKER: ActionKind.LOCK_SIDE_QUESTS_HARD,

    Profissao.OFICIAL_CAMPO: ActionKind.PHYSICAL_ROOM_ACCESS,
    Profissao.EX_POLICIAL: ActionKind.PHYSICAL_ROOM_ACCESS,
    Profissao.DELEGADO: ActionKind.PHYSICAL_DETAIN,

    Profissao.CRIPTOGRAFO: ActionKind.REVEAL_ACCOMPLICES_COUNT,
    Profissao.FOTOJORNALISTA: ActionKind.IMPROVE_IMAGE,
}

PROFISSAO_TO_CATEGORY: dict[Profissao, ClueCategory] = {
    Profissao.PERITO_CRIMINAL: ClueCategory.OBJETO_LOCAL,
    Profissao.DIRETOR_INVESTIGATIVO: ClueCategory.FICHA_CIVIL,
    Profissao.ANALISTA_METADADOS: ClueCategory.OBJETO_LOCAL,
    Profissao.ANALISTA_OCORRENCIAS: ClueCategory.LINHA_TEMPO,
    Profissao.ESPECIALISTA_FRAUDE: ClueCategory.OBJETO_LOCAL,
    Profissao.ESPECIALISTA_VIGILANCIA: ClueCategory.LINHA_TEMPO,
    Profissao.CHECADOR_FATOS: ClueCategory.OBJETO_LOCAL,
    Profissao.ANALISTA_COMPORTAMENTAL: ClueCategory.FICHA_CIVIL,
    Profissao.ENGENHEIRO_SOCIAL: ClueCategory.FICHA_CIVIL,
    Profissao.COLUNISTA: ClueCategory.FICHA_CIVIL,
    Profissao.INFILTRADOR: ClueCategory.OBJETO_LOCAL,
    Profissao.REPORTER_CAMPO: ClueCategory.FICHA_CIVIL,
}


# ---------------------------------------------------------------------------
# Handlers por ActionKind
# ---------------------------------------------------------------------------

def _handle_eliminate(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    char_id = body.get("target_character_id")
    if not char_id:
        return {"ok": False, "error": "target_character_id obrigatório"}
    target = session.get(Character, int(char_id))
    if not target or target.game_id != game.id:
        return {"ok": False, "error": "Personagem não encontrado"}
    if target.eliminated:
        return {"ok": False, "error": "Personagem já eliminado"}
    target.eliminated = True
    session.add(target)
    return {"ok": True, "eliminated_id": target.id}


def _handle_reveal_true_clue(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    categoria = PROFISSAO_TO_CATEGORY.get(character.profissao)
    if not categoria:
        return {"ok": False, "error": "Categoria não mapeada para esta profissão"}
    clue = session.exec(
        select(Clue)
        .where(
            Clue.game_id == game.id,
            Clue.categoria == categoria,
            Clue.veracidade == ClueVeracity.VERDADEIRA,
            Clue.revealed_at_cycle.is_(None),  # type: ignore[attr-defined]
        )
        .order_by(Clue.id)
        .limit(1)
    ).first()
    if not clue:
        return {"ok": False, "error": "Nenhuma pista verdadeira não revelada disponível"}
    clue.revealed_at_cycle = game.current_cycle
    session.add(clue)
    return {"ok": True, "revealed_clue_id": clue.id}


def _handle_interrogate(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    char_id = body.get("target_character_id")
    if not char_id:
        return {"ok": False, "error": "target_character_id obrigatório"}
    target = session.get(Character, int(char_id))
    if not target or target.game_id != game.id:
        return {"ok": False, "error": "Personagem não encontrado"}

    clues = list(
        session.exec(
            select(Clue).where(
                Clue.game_id == game.id,
                Clue.categoria == ClueCategory.FICHA_CIVIL,
                Clue.target_character_id == target.id,
                Clue.revealed_at_cycle.is_(None),  # type: ignore[attr-defined]
            )
        ).all()
    )
    for clue in clues:
        clue.revealed_at_cycle = game.current_cycle
        session.add(clue)
    return {"ok": True, "revealed_count": len(clues), "target_id": target.id}


def _handle_classify(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    if (
        team.classification_blocked_until_cycle is not None
        and team.classification_blocked_until_cycle > game.current_cycle
    ):
        return {"ok": False, "error": "Classificação bloqueada pelo Invasor de sistema"}

    clue_id = body.get("target_clue_id")
    veracity_str = body.get("classified_veracity")
    if not clue_id or not veracity_str:
        return {"ok": False, "error": "target_clue_id e classified_veracity obrigatórios"}

    try:
        classified_veracity = ClueVeracity(veracity_str)
    except ValueError:
        return {"ok": False, "error": f"Veracidade inválida: {veracity_str}"}

    clue = session.get(Clue, int(clue_id))
    if not clue or clue.game_id != game.id:
        return {"ok": False, "error": "Pista não encontrada"}
    if clue.classified:
        return {"ok": False, "error": "Pista já classificada"}
    if clue.revealed_at_cycle is None:
        return {"ok": False, "error": "Pista ainda não revelada"}

    categoria = PROFISSAO_TO_CATEGORY.get(character.profissao)
    if categoria and clue.categoria != categoria:
        return {"ok": False, "error": f"Esta profissão só classifica pistas de {categoria.value}"}

    clue.classified = True
    clue.classified_by_team_id = team.id
    clue.classified_at_cycle = game.current_cycle
    clue.classified_veracity = classified_veracity
    if classified_veracity != ClueVeracity.VERDADEIRA:
        clue.eliminated = True
        clue.eliminated_at_cycle = game.current_cycle
    session.add(clue)
    return {"ok": True, "clue_id": clue.id, "classified_as": classified_veracity.value}


def _handle_steal(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    target_team_id = body.get("target_team_id")
    if not target_team_id:
        return {"ok": False, "error": "target_team_id obrigatório"}

    target_team = session.get(Team, int(target_team_id))
    if not target_team or target_team.game_id != game.id or target_team.id == team.id:
        return {"ok": False, "error": "Time alvo inválido"}

    categoria = PROFISSAO_TO_CATEGORY.get(character.profissao, ClueCategory.OBJETO_LOCAL)
    clues = list(
        session.exec(
            select(Clue).where(
                Clue.game_id == game.id,
                Clue.categoria == categoria,
                Clue.eliminated == True,  # noqa: E712
                Clue.classified_by_team_id == target_team.id,
                Clue.stolen_by_team_id.is_(None),  # type: ignore[attr-defined]
            )
        ).all()
    )
    for clue in clues:
        clue.stolen_by_team_id = team.id
        session.add(clue)
    return {"ok": True, "stolen_count": len(clues)}


def _handle_block(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    target_team_id = body.get("target_team_id")
    if not target_team_id:
        return {"ok": False, "error": "target_team_id obrigatório"}

    target_team = session.get(Team, int(target_team_id))
    if not target_team or target_team.game_id != game.id or target_team.id == team.id:
        return {"ok": False, "error": "Time alvo inválido"}

    target_team.classification_blocked_until_cycle = game.current_cycle + 1
    session.add(target_team)
    return {"ok": True, "blocked_team_id": target_team.id, "until_cycle": game.current_cycle + 1}


def _handle_lock_side_quests(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    target_team_id = body.get("target_team_id")
    if not target_team_id:
        return {"ok": False, "error": "target_team_id obrigatório"}
    target_team = session.get(Team, int(target_team_id))
    if not target_team or target_team.game_id != game.id or target_team.id == team.id:
        return {"ok": False, "error": "Time alvo inválido"}
    target_team.side_quest_hard_count = 3
    session.add(target_team)
    return {"ok": True, "locked_team_id": target_team.id}


def _handle_physical(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    return {"ok": True}


def _handle_reveal_accomplices(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    game.accomplices_count_revealed = True
    session.add(game)
    n = sum(
        1 for c in session.exec(
            select(Character).where(
                Character.game_id == game.id,
                Character.funcao_especial == FuncaoEspecial.CUMPLICE,
            )
        ).all()
    )
    return {"ok": True, "accomplices_count": n}


def _handle_improve_image(
    session: Session, game: Game, character: Character, team: Team, body: dict
) -> dict:
    max_bonus = len(IMAGE_STAGES) - 1
    if game.image_stage_bonus < max_bonus:
        game.image_stage_bonus += 1
        session.add(game)
        return {"ok": True, "new_bonus": game.image_stage_bonus}
    return {"ok": True, "new_bonus": game.image_stage_bonus, "already_max": True}


_HANDLERS = {
    ActionKind.ELIMINATE_CHARACTER: _handle_eliminate,
    ActionKind.REVEAL_TRUE_CLUE: _handle_reveal_true_clue,
    ActionKind.INTERROGATE: _handle_interrogate,
    ActionKind.CLASSIFY_CLUE: _handle_classify,
    ActionKind.STEAL_ELIMINATED_CLUES: _handle_steal,
    ActionKind.BLOCK_OPPONENT_CLASSIFY: _handle_block,
    ActionKind.LOCK_SIDE_QUESTS_HARD: _handle_lock_side_quests,
    ActionKind.PHYSICAL_ROOM_ACCESS: _handle_physical,
    ActionKind.PHYSICAL_DETAIN: _handle_physical,
    ActionKind.REVEAL_ACCOMPLICES_COUNT: _handle_reveal_accomplices,
    ActionKind.IMPROVE_IMAGE: _handle_improve_image,
}


# ---------------------------------------------------------------------------
# Ponto de entrada público
# ---------------------------------------------------------------------------

def execute_action(
    session: Session,
    game: Game,
    character: Character,
    team: Team,
    body: dict,
) -> dict:
    """Aplica a ação do personagem. Retorna dict {ok, ...}.

    Pré-condições verificadas aqui:
    - game.status == PLAYING
    - character.action_used == False
    - character.eliminated == False
    """
    if character.equipe != team.equipe:
        return {"ok": False, "error": "Personagem não pertence ao seu time"}
    if game.status != GameStatus.PLAYING:
        return {"ok": False, "error": "Jogo não está em andamento"}
    if character.eliminated:
        return {"ok": False, "error": "Personagem eliminado não pode agir"}
    if character.action_used:
        return {"ok": False, "error": "Ação já utilizada neste ciclo"}
    if (
        character.blocked_until_cycle is not None
        and character.blocked_until_cycle >= game.current_cycle
    ):
        return {"ok": False, "error": "Personagem bloqueado por side quest adversário"}

    kind = PROFISSAO_TO_ACTION.get(character.profissao)
    if kind is None:
        return {"ok": False, "error": "Profissão sem ação mapeada"}

    handler = _HANDLERS[kind]
    result = handler(session, game, character, team, body)

    if not result.get("ok"):
        return result

    action = Action(
        game_id=game.id,
        cycle=game.current_cycle,
        character_id=character.id,
        team_id=team.id,
        kind=kind,
        target_character_id=_safe_int(body.get("target_character_id")),
        target_clue_id=_safe_int(body.get("target_clue_id")),
        target_team_id=_safe_int(body.get("target_team_id")),
        result_json=json.dumps(result),
    )
    session.add(action)
    character.action_used = True
    session.add(character)
    session.commit()

    return {"ok": True, "kind": kind.value, **result}


def _safe_int(val: object) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def action_kind_for(profissao: Profissao) -> Optional[ActionKind]:
    return PROFISSAO_TO_ACTION.get(profissao)


def category_for(profissao: Profissao) -> Optional[ClueCategory]:
    return PROFISSAO_TO_CATEGORY.get(profissao)
