import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Mantém WebSockets agrupados por game_id e faz broadcast."""

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, game_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[game_id].add(ws)

    async def disconnect(self, game_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[game_id].discard(ws)
            if not self._rooms[game_id]:
                del self._rooms[game_id]

    async def broadcast(self, game_id: str, message: str) -> None:
        async with self._lock:
            conns = list(self._rooms.get(game_id, ()))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms[game_id].discard(ws)


manager = ConnectionManager()
