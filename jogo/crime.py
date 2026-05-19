"""Sorteio interno do crime e geração das 24 fichas civis.

Sem LLM aqui — só random + listas seed. O contexto narrativo
(história completa, dicas, relações detalhadas) entra no PR 4.
"""
import random
from typing import Optional

from sqlmodel import Session, select

from jogo import seed
from jogo.db.models import Character, Game, Player, Team
from jogo.game_data import (
    EQUIPE_DE_PROFISSAO,
    PROB_CUMPLICE_1,
    PROB_CUMPLICE_2,
    FuncaoEspecial,
    Profissao,
)


def _random_personalidade(rng: random.Random) -> str:
    traits = rng.sample(seed.personalities(), k=3)
    return ", ".join(traits)


def _random_age(rng: random.Random) -> int:
    return rng.randint(22, 65)


def _random_name(rng: random.Random, genero: str) -> tuple[str, str]:
    pool = seed.names_male() if genero == "m" else seed.names_female()
    return rng.choice(pool), rng.choice(seed.surnames())


def _avatar_seed_from(genero: str, nome: str, sobrenome: str) -> str:
    """Seed determinística pro avatar (iniciais + cor procedural por enquanto)."""
    return f"{genero}:{nome}:{sobrenome}"


def _pick_funcoes(
    rng: random.Random,
) -> dict[Profissao, FuncaoEspecial]:
    """Escolhe criminoso, vítima e cúmplices em equipes diferentes."""
    all_profs = list(Profissao)
    rng.shuffle(all_profs)

    assigned: dict[Profissao, FuncaoEspecial] = {}
    used_equipes: set = set()

    def take_one(forbidden_equipes: set) -> Optional[Profissao]:
        for p in all_profs:
            if p in assigned:
                continue
            if EQUIPE_DE_PROFISSAO[p] in forbidden_equipes:
                continue
            return p
        return None

    crim = take_one(set())
    if crim is None:
        raise RuntimeError("Não foi possível alocar criminoso")
    assigned[crim] = FuncaoEspecial.CRIMINOSO
    used_equipes.add(EQUIPE_DE_PROFISSAO[crim])

    vit = take_one(used_equipes)
    if vit is None:
        raise RuntimeError("Não foi possível alocar vítima")
    assigned[vit] = FuncaoEspecial.VITIMA
    used_equipes.add(EQUIPE_DE_PROFISSAO[vit])

    if rng.random() < PROB_CUMPLICE_1:
        c1 = take_one(used_equipes)
        if c1 is not None:
            assigned[c1] = FuncaoEspecial.CUMPLICE
            used_equipes.add(EQUIPE_DE_PROFISSAO[c1])
            if rng.random() < PROB_CUMPLICE_2:
                c2 = take_one(used_equipes)
                if c2 is not None:
                    assigned[c2] = FuncaoEspecial.CUMPLICE
                    used_equipes.add(EQUIPE_DE_PROFISSAO[c2])

    return assigned


def generate(
    session: Session,
    game: Game,
    rng: Optional[random.Random] = None,
) -> None:
    """Sorteia o crime e cria as 24 fichas civis. Idempotente: aborta se já gerou."""
    if game.local is not None:
        return
    if rng is None:
        rng = random.Random()

    game.local = rng.choice(seed.locations())
    game.objeto = rng.choice(seed.objects())
    game.motivacional = rng.choice(seed.motives())

    funcoes = _pick_funcoes(rng)

    players_by_prof: dict[Profissao, Player] = {}
    teams = list(
        session.exec(select(Team).where(Team.game_id == game.id)).all()
    )
    for team in teams:
        players = list(
            session.exec(
                select(Player).where(Player.team_id == team.id)
            ).all()
        )
        for p in players:
            if p.profissao:
                players_by_prof[p.profissao] = p

    for profissao in Profissao:
        equipe = EQUIPE_DE_PROFISSAO[profissao]
        funcao = funcoes.get(profissao, FuncaoEspecial.NENHUMA)
        human = players_by_prof.get(profissao)

        if human:
            nome_humano = (human.nome or "").strip()
            partes = nome_humano.split(" ", 1)
            nome = partes[0] or rng.choice(seed.names_male())
            sobrenome = (
                partes[1] if len(partes) > 1 else rng.choice(seed.surnames())
            )
            genero = "?"
        else:
            genero = rng.choice(["m", "f"])
            nome, sobrenome = _random_name(rng, genero)

        char = Character(
            game_id=game.id,
            profissao=profissao,
            equipe=equipe,
            is_npc=human is None,
            player_id=human.id if human else None,
            nome=nome,
            sobrenome=sobrenome,
            idade=_random_age(rng),
            genero=genero,
            avatar_seed=_avatar_seed_from(genero, nome, sobrenome),
            personalidade=_random_personalidade(rng),
            funcao_especial=funcao,
        )
        session.add(char)

    session.commit()
    session.refresh(game)


def validate_generated(session: Session, game_id: str) -> list[str]:
    """Retorna lista de problemas — vazio = OK. Útil em testes e PR 4 (LLM)."""
    problems: list[str] = []
    chars = list(
        session.exec(
            select(Character).where(Character.game_id == game_id)
        ).all()
    )

    if len(chars) != 24:
        problems.append(f"esperado 24 characters, achou {len(chars)}")

    criminosos = [c for c in chars if c.funcao_especial == FuncaoEspecial.CRIMINOSO]
    if len(criminosos) != 1:
        problems.append(f"esperado 1 criminoso, achou {len(criminosos)}")

    vitimas = [c for c in chars if c.funcao_especial == FuncaoEspecial.VITIMA]
    if len(vitimas) != 1:
        problems.append(f"esperado 1 vítima, achou {len(vitimas)}")

    especiais = [
        c for c in chars if c.funcao_especial != FuncaoEspecial.NENHUMA
    ]
    equipes = [c.equipe for c in especiais]
    if len(set(equipes)) != len(equipes):
        problems.append("criminoso/vítima/cúmplices devem estar em equipes diferentes")

    cumplices = [c for c in chars if c.funcao_especial == FuncaoEspecial.CUMPLICE]
    if len(cumplices) > 2:
        problems.append(f"máx 2 cúmplices, achou {len(cumplices)}")

    return problems
