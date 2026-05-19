from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from jogo.db.models import Game
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

    await manager.connect(game_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(game_id, websocket)
