"""Wrapper do Anthropic SDK com prompt caching e mock mode.

`generate(schema, system, user, ...)` usa `messages.parse()` com structured
outputs. O system prompt é cacheado (5min TTL) — passe o conteúdo estável
como `system_cached` pra economizar tokens entre etapas.

Modo mock: `JOGO_MOCK_LLM=1` no env retorna fixtures pré-definidas.
Útil pra rodar E2E sem queimar API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from jogo.config import settings
from jogo.game_data import LLM_MAX_RETRIES

T = TypeVar("T", bound=BaseModel)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000

MOCK_DIR = Path("data/mock_llm")


def is_mock_mode() -> bool:
    return os.environ.get("JOGO_MOCK_LLM", "").strip() in ("1", "true", "yes")


_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key and not is_mock_mode():
            raise RuntimeError(
                "ANTHROPIC_API_KEY não configurada e JOGO_MOCK_LLM não ativo. "
                "Configure a key em .env ou rode com JOGO_MOCK_LLM=1."
            )
        _client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic(api_key="mock")
    return _client


class LLMGenerationError(RuntimeError):
    pass


def _load_mock(step: str, schema: type[T]) -> T:
    path = MOCK_DIR / f"{step}.json"
    if not path.exists():
        raise LLMGenerationError(
            f"Mock mode ativo mas fixture {path} não existe."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return schema.model_validate(data)


def generate(
    schema: type[T],
    *,
    system_cached: str,
    user: str,
    step_name: str,
    validators: Optional[list[Callable[[T], list[str]]]] = None,
    max_retries: int = LLM_MAX_RETRIES,
) -> T:
    """Gera output estruturado contra `schema`, com validação e retry.

    - `system_cached`: system prompt que será cacheado (5min TTL).
    - `user`: mensagem user com inputs específicos da etapa.
    - `validators`: lista de funções que recebem o output e retornam lista
      de problemas (vazia = OK). Se houver problemas, faz retry com feedback.
    """
    if is_mock_mode():
        return _load_mock(step_name, schema)

    client = get_client()
    validators = validators or []
    last_problems: list[str] = []

    for attempt in range(max_retries):
        user_msg = user
        if last_problems:
            user_msg += (
                "\n\nA tentativa anterior teve estes problemas:\n- "
                + "\n- ".join(last_problems)
                + "\n\nPor favor corrija."
            )

        try:
            response = client.messages.parse(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": system_cached,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_msg}],
                output_format=schema,
            )
            result = response.parsed_output
        except ValidationError as e:
            last_problems = [f"Output não bate com schema: {e}"]
            continue
        except anthropic.APIError as e:
            raise LLMGenerationError(f"Erro da API: {e}") from e

        problems: list[str] = []
        for v in validators:
            problems.extend(v(result))
        if not problems:
            return result
        last_problems = problems

    raise LLMGenerationError(
        f"Geração de '{step_name}' falhou após {max_retries} tentativas. "
        f"Últimos problemas: {last_problems}"
    )


def dump_mock(step_name: str, output: BaseModel) -> None:
    """Util pra desenvolvedor: serializa um output real e salva como mock.

    Roda uma vez com API real, dump, depois use JOGO_MOCK_LLM=1 nos testes.
    """
    MOCK_DIR.mkdir(parents=True, exist_ok=True)
    path = MOCK_DIR / f"{step_name}.json"
    path.write_text(
        json.dumps(output.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
