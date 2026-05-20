import asyncio
from datetime import datetime, timezone

from sqlmodel import Session, select

from jogo.db.models import Game, GameStatus, Player, Team
from jogo.db.session import engine as db_engine
from jogo.game_data import (
    COUNTDOWN_SECONDS,
    GENERATION_MIN_SECONDS,
    MIN_PLAYERS_PER_TEAM,
    MIN_TEAMS,
    MIN_TOTAL_PLAYERS,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_teams(session: Session, game_id: str) -> list[Team]:
    return list(
        session.exec(select(Team).where(Team.game_id == game_id)).all()
    )


def get_players(session: Session, team_id: int) -> list[Player]:
    return list(
        session.exec(select(Player).where(Player.team_id == team_id)).all()
    )


def all_players(session: Session, game_id: str) -> list[Player]:
    return list(
        session.exec(
            select(Player).join(Team).where(Team.game_id == game_id)
        ).all()
    )


def can_start(session: Session, game_id: str) -> bool:
    """Verifica se condições mínimas pra iniciar o jogo foram atendidas."""
    teams = get_teams(session, game_id)
    if len(teams) < MIN_TEAMS:
        return False

    all_p = all_players(session, game_id)
    if len(all_p) < MIN_TOTAL_PLAYERS:
        return False

    counts = [len(get_players(session, t.id)) for t in teams if t.id]
    if any(c < MIN_PLAYERS_PER_TEAM for c in counts):
        return False
    if max(counts) - min(counts) > 1:
        return False

    if any(p.profissao is None for p in all_p):
        return False
    if not all(p.ready for p in all_p):
        return False

    return True


def derive_status(session: Session, game: Game) -> GameStatus:
    """Computa o status do jogo a partir do estado do banco."""
    if game.finished_at:
        return GameStatus.FINISHED
    if game.started_at:
        return GameStatus.PLAYING
    if game.countdown_started_at:
        return GameStatus.COUNTDOWN
    if game.generation_started_at:
        return GameStatus.GENERATING
    if game.paused_at:
        return GameStatus.PAUSED

    teams = get_teams(session, game.id)
    if len(teams) < MIN_TEAMS:
        return GameStatus.TEAM_SELECTION

    all_p = all_players(session, game.id)
    if not all_p or any(p.profissao is None for p in all_p):
        return GameStatus.CHAR_SELECTION

    return GameStatus.READY_CHECK


def sync_status(session: Session, game: Game) -> bool:
    """Atualiza game.status se diferente do derivado. Retorna True se mudou."""
    new_status = derive_status(session, game)
    if game.status != new_status:
        game.status = new_status
        session.add(game)
        session.commit()
        session.refresh(game)
        return True
    return False


def start_generation(session: Session, game: Game) -> None:
    game.generation_started_at = _utcnow()
    game.status = GameStatus.GENERATING
    session.add(game)
    session.commit()


def finish_generation(session: Session, game: Game) -> None:
    game.generation_finished_at = _utcnow()
    session.add(game)
    session.commit()


def start_countdown(session: Session, game: Game) -> None:
    game.countdown_started_at = _utcnow()
    game.status = GameStatus.COUNTDOWN
    session.add(game)
    session.commit()


def start_game(session: Session, game: Game) -> None:
    game.started_at = _utcnow()
    game.status = GameStatus.PLAYING
    session.add(game)
    session.commit()


def countdown_remaining_seconds(game: Game) -> int:
    if not game.countdown_started_at:
        return COUNTDOWN_SECONDS
    elapsed = (_utcnow() - game.countdown_started_at).total_seconds()
    return max(0, COUNTDOWN_SECONDS - int(elapsed))


_countdown_tasks: dict[str, asyncio.Task] = {}
_generation_tasks: dict[str, asyncio.Task] = {}


def _on_task_done(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)


async def _run_countdown(game_id: str) -> None:
    from jogo.realtime import manager

    with Session(db_engine) as session:
        for _ in range(COUNTDOWN_SECONDS + 2):
            game = session.get(Game, game_id)
            if not game or game.status != GameStatus.COUNTDOWN:
                return
            session.refresh(game)
            remaining = countdown_remaining_seconds(game)
            html = (
                f'<div id="countdown" hx-swap-oob="outerHTML">'
                f'<div class="countdown-big">{remaining}</div>'
                f'</div>'
            )
            await manager.broadcast(game_id, html)
            if remaining <= 0:
                start_game(session, game)
                reload_html = (
                    '<div id="reload-trigger" hx-swap-oob="outerHTML">'
                    '<script>setTimeout(()=>location.reload(),200)</script>'
                    '</div>'
                )
                await manager.broadcast(game_id, reload_html)
                return
            await asyncio.sleep(1)


async def _broadcast_step(game_id: str, label: str) -> None:
    from jogo.realtime import manager
    html = (
        f'<div id="generating-step" hx-swap-oob="outerHTML">'
        f'<p class="muted">{label}</p>'
        f'</div>'
    )
    await manager.broadcast(game_id, html)


async def _run_generation(game_id: str) -> None:
    from jogo import crime, narrative
    from jogo.realtime import manager

    with Session(db_engine) as session:
        game = session.get(Game, game_id)
        if not game or game.status != GameStatus.GENERATING:
            return

        await _broadcast_step(game_id, "Sorteando personagens e dados do crime…")
        crime.generate(session, game)
        crime_problems = crime.validate_generated(session, game.id)
        if crime_problems:
            raise RuntimeError(f"Sorteio inválido: {crime_problems}")

        await _broadcast_step(game_id, "Construindo a história, dicas e linha do tempo (pode levar até 1 minuto)…")
        await asyncio.to_thread(narrative.generate_all, session, game)
        narrative_problems = narrative.validate_persisted(session, game.id)
        if narrative_problems:
            raise RuntimeError(f"Narrativa inválida: {narrative_problems}")

        await _broadcast_step(game_id, "Gerando imagem da cena do crime…")
        session.refresh(game)
        from jogo import image as img_module
        prompt = img_module.build_prompt(
            game.local or "",
            game.objeto or "",
            game.historia_completa or "",
        )
        await asyncio.to_thread(img_module.generate_and_degrade, game.id, prompt)
        game.image_ready = True
        session.add(game)
        session.commit()

        finish_generation(session, game)

        elapsed = (_utcnow() - game.generation_started_at).total_seconds()
        remaining = max(0.0, GENERATION_MIN_SECONDS - elapsed)
        if remaining > 0:
            await asyncio.sleep(remaining)

        session.refresh(game)
        start_countdown(session, game)

    reload_html = (
        '<div id="reload-trigger" hx-swap-oob="outerHTML">'
        '<script>setTimeout(()=>location.reload(),200)</script>'
        '</div>'
    )
    await manager.broadcast(game_id, reload_html)

    schedule_countdown_task(game_id)


def schedule_countdown_task(game_id: str) -> None:
    """Inicia (ou substitui) a task de countdown em background."""
    existing = _countdown_tasks.get(game_id)
    if existing and not existing.done():
        return
    task = asyncio.create_task(_run_countdown(game_id))
    task.add_done_callback(_on_task_done)
    _countdown_tasks[game_id] = task


def schedule_generation_task(game_id: str) -> None:
    """Inicia (ou substitui) a task de geração do crime em background."""
    existing = _generation_tasks.get(game_id)
    if existing and not existing.done():
        return
    task = asyncio.create_task(_run_generation(game_id))
    task.add_done_callback(_on_task_done)
    _generation_tasks[game_id] = task
