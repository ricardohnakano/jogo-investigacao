"""Geração de imagem da cena do crime via DALL-E 3 + degradador Pillow.

Fluxo:
  generate_and_degrade(game_id, prompt) → chama DALL-E (ou mock) e grava
  data/games/{game_id}/image_original.png + image_stage_1..6.png

Degradação: downscale para `quality%` e upscale de volta (NEAREST) —
  cria efeito de pixelização progressiva que vai revelando a imagem.

Mock mode (JOGO_MOCK_LLM=1): gera placeholder com Pillow, sem API.
"""

from __future__ import annotations

import base64
import io
import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from jogo.config import settings
from jogo.game_data import IMAGE_STAGES


GAMES_DIR = Path("data/games")
ORIGINAL_FILENAME = "image_original.png"
STAGE_FILENAME_TPL = "image_stage_{n}.png"


def is_mock_mode() -> bool:
    return os.environ.get("JOGO_MOCK_LLM", "").strip() in ("1", "true", "yes")


def image_dir(game_id: str) -> Path:
    return GAMES_DIR / game_id


def stage_path(game_id: str, stage: int) -> Path:
    """stage: 1..len(IMAGE_STAGES)"""
    return image_dir(game_id) / STAGE_FILENAME_TPL.format(n=stage)


def original_path(game_id: str) -> Path:
    return image_dir(game_id) / ORIGINAL_FILENAME


def generate_and_degrade(game_id: str, prompt: str) -> None:
    """Gera imagem original e os 6 estágios degradados. Bloqueante — use asyncio.to_thread."""
    game_dir = image_dir(game_id)
    game_dir.mkdir(parents=True, exist_ok=True)

    img = _mock_image(prompt) if is_mock_mode() else _call_dalle(prompt)
    img.save(original_path(game_id))

    for stage_n, quality in enumerate(IMAGE_STAGES, start=1):
        _degrade(img, quality).save(stage_path(game_id, stage_n))


def _degrade(img: Image.Image, quality: float) -> Image.Image:
    """Pixeliza imagem: downscale para `quality` da resolução original e upscale de volta."""
    w, h = img.size
    small_w = max(1, int(w * quality))
    small_h = max(1, int(h * quality))
    small = img.resize((small_w, small_h), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST)


def _mock_image(prompt: str) -> Image.Image:
    """Placeholder noir gerado com Pillow — sem API."""
    size = 1024
    img = Image.new("RGB", (size, size), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)

    # Grade estilo cena de crime
    for x in range(0, size, 64):
        draw.line([(x, 0), (x, size)], fill=(30, 30, 40), width=1)
    for y in range(0, size, 64):
        draw.line([(0, y), (size, y)], fill=(30, 30, 40), width=1)

    # Cruz central (fita de isolamento)
    draw.rectangle([size // 2 - 6, 80, size // 2 + 6, size - 80], fill=(220, 180, 0))
    draw.rectangle([80, size // 2 - 6, size - 80, size // 2 + 6], fill=(220, 180, 0))

    # Texto
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_body = font_title

    draw.text((size // 2, 140), "CENA DO CRIME", fill=(220, 180, 0), font=font_title, anchor="mm")
    draw.text((size // 2, 210), "[MOCK MODE]", fill=(160, 160, 160), font=font_body, anchor="mm")

    lines = textwrap.wrap(prompt[:200], width=48)
    for i, line in enumerate(lines[:6]):
        draw.text((size // 2, 820 + i * 36), line, fill=(120, 120, 140), font=font_body, anchor="mm")

    return img


def _call_dalle(prompt: str) -> Image.Image:
    """Chama DALL-E 3 via OpenAI SDK e retorna PIL Image."""
    from openai import OpenAI

    api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não configurada. Configure em .env ou use JOGO_MOCK_LLM=1."
        )

    client = OpenAI(api_key=api_key)
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
        response_format="b64_json",
    )
    image_bytes = base64.b64decode(response.data[0].b64_json)
    return Image.open(io.BytesIO(image_bytes))


def build_prompt(local: str, objeto: str, historia: str) -> str:
    """Monta prompt de imagem noir para DALL-E."""
    resumo = historia[:300].replace("\n", " ") if historia else ""
    return (
        f"Crime scene photograph, noir detective style, dark cinematic lighting, "
        f"photorealistic, no people present, ultra-detailed evidence scene. "
        f"Setting: {local}. "
        f"A {objeto} is prominently visible. "
        f"Context: {resumo}"
    )
