from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from jogo.db.models import Character, Game, Player, Team
from jogo.db.session import get_session
from jogo.realtime import manager

router = APIRouter()


@router.websocket("/ws/{game_id}")
async def ws_game(
    websocket: WebSocket,
    game_id: str,
    session: Session = Depends(get_session),
):
    game_id = game_id.upper()
    game = session.get(Game, game_id)
    if not game:
        await websocket.close(code=4404)
        return

    # Identifica equipe via cookie player_id (None se for tela de host/equipe)
    team_id: int | None = None
    player_id = websocket.cookies.get("player_id", "")
    if player_id:
        player = session.get(Player, player_id)
        if player:
            team_id = player.team_id

    await manager.connect(game_id, websocket, team_id=team_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(game_id, websocket)
