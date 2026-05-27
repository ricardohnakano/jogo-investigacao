import asyncio
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket


class ConnectionManager:
    """WebSockets agrupados por game_id, com suporte a broadcast por equipe."""

    def __init__(self) -> None:
        # game_id → set of (WebSocket, team_id|None)
        self._rooms: dict[str, set[tuple[WebSocket, Optional[int]]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(
        self, game_id: str, ws: WebSocket, team_id: Optional[int] = None
    ) -> None:
        """Register WebSocket connection for game room."""
        await ws.accept()
        async with self._lock:
            self._rooms[game_id].add((ws, team_id))

    async def disconnect(self, game_id: str, ws: WebSocket) -> None:
        """Unregister WebSocket connection from game room."""
        async with self._lock:
            self._rooms[game_id] = {
                (w, t) for w, t in self._rooms[game_id] if w is not ws
            }
            if not self._rooms[game_id]:
                del self._rooms[game_id]

    async def broadcast(self, game_id: str, message: str) -> None:
        """Send message to all connections in a game room."""
        async with self._lock:
            conns = list(self._rooms.get(game_id, ()))
        dead: list[WebSocket] = []
        for ws, _ in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                self._rooms[game_id] = {
                    (w, t) for w, t in self._rooms[game_id] if w not in dead
                }

    async def broadcast_to_team(
        self, game_id: str, team_id: int, message: str
    ) -> None:
        """Send message to all connections in a specific team."""
        async with self._lock:
            conns = [
                (w, t)
                for w, t in self._rooms.get(game_id, ())
                if t == team_id
            ]
        dead: list[WebSocket] = []
        for ws, _ in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                self._rooms[game_id] = {
                    (w, t) for w, t in self._rooms[game_id] if w not in dead
                }


manager = ConnectionManager()
