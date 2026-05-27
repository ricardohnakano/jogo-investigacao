"""Logger simples para erros e eventos importantes.

QoL: Estrutura de logs para rastrear o que deu errado durante gameplay.
"""

import logging
import sys
from datetime import datetime

# Configure root logger
logger = logging.getLogger("jogo")
logger.setLevel(logging.DEBUG)

# Console handler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def log_error(game_id: str, message: str, exception: Exception = None) -> None:
    """Log erro com contexto do jogo."""
    if exception:
        logger.error(f"[GAME {game_id}] {message}: {exception}")
    else:
        logger.error(f"[GAME {game_id}] {message}")


def log_warning(game_id: str, message: str) -> None:
    """Log aviso com contexto do jogo."""
    logger.warning(f"[GAME {game_id}] {message}")


def log_info(game_id: str, message: str) -> None:
    """Log info com contexto do jogo."""
    logger.info(f"[GAME {game_id}] {message}")


def log_debug(game_id: str, message: str) -> None:
    """Log debug com contexto do jogo."""
    logger.debug(f"[GAME {game_id}] {message}")
