"""Schemas Pydantic dos outputs do LLM.

Cada schema define exatamente o que o LLM precisa retornar pra cada etapa
da pipeline. `client.messages.parse()` valida o output contra eles.
"""

from pydantic import BaseModel, Field


class StoryOutput(BaseModel):
    """Etapa 1: história canônica + personalidade do criminoso + relações."""

    historia_completa: str = Field(
        description=(
            "Narrativa do crime em prosa, 4-8 frases. Inclui motivação, "
            "execução e detalhes que justifiquem o objeto encontrado no local."
        )
    )
    personalidade_criminoso: list[str] = Field(
        min_length=3,
        max_length=3,
        description=(
            "3 características de personalidade do criminoso, "
            "consistentes com o motivacional do crime"
        ),
    )
    relacao_criminoso_vitima: str = Field(
        description=(
            "Como criminoso e vítima se conheciam (ex: 'colegas de trabalho', "
            "'irmãos', 'ex-amantes'). NUNCA 'desconhecidos'."
        )
    )
    relacao_criminoso_cumplices: list[str] = Field(
        default_factory=list,
        description=(
            "Como o criminoso conhece cada cúmplice, em ordem. "
            "Lista vazia se não há cúmplices. NUNCA 'desconhecidos'."
        ),
    )


class ObjetoLocalCluesOutput(BaseModel):
    """Etapa 2: 9 dicas principais + 15 falsas extras sobre objeto/local."""

    dicas_uteis: list[str] = Field(
        min_length=3, max_length=3,
        description=(
            "3 pistas VERDADEIRAS e relevantes sobre objeto ou local — cada "
            "uma deve, sozinha ou cruzada com outras, ajudar a identificar "
            "objeto OU local. Ex: 'A taça é de cristal e estava sobre a mesa "
            "principal'."
        ),
    )
    dicas_enganosas: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 pistas verdadeiras mas que sugerem hipótese errada se vistas "
            "isoladamente (ex: detalhes verdadeiros que parecem incriminar "
            "outro local)."
        ),
    )
    dicas_falsas: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 pistas FALSAS mas explicáveis (testemunha confusa, pista "
            "plantada). Cada pista falsa deve ter explicação plausível."
        ),
    )
    dicas_inuteis: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 pistas verdadeiras mas irrelevantes — dão cor ao mundo mas "
            "não ajudam a resolver."
        ),
    )
    extras_falsas: list[str] = Field(
        min_length=15, max_length=15,
        description=(
            "15 pistas falsas adicionais sobre OUTROS objetos e locais "
            "(distrações). Cada uma sugere um local ou objeto diferente "
            "que NÃO é o real."
        ),
    )


class FichaCivilCluesOutput(BaseModel):
    """Etapa 3: 11 dicas sobre fichas civis de criminoso + cúmplices."""

    dicas_uteis: list[str] = Field(
        min_length=5, max_length=5,
        description=(
            "5 pistas VERDADEIRAS sobre criminoso/cúmplices que, cruzadas, "
            "permitam identificá-los (ex: 'O suspeito tinha acesso ao prédio "
            "fora do horário comercial')."
        ),
    )
    dicas_enganosas: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 pistas verdadeiras mas que apontam pra suspeitos errados "
            "se vistas isoladamente."
        ),
    )
    dicas_falsas: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 pistas falsas mas explicáveis (ex: testemunha confundiu "
            "pessoas, álibi adulterado)."
        ),
    )
    dicas_inuteis: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 pistas verdadeiras mas que não ajudam a identificar os "
            "envolvidos (ex: cor da camisa do segurança)."
        ),
    )


class LinhaTempoCluesOutput(BaseModel):
    """Etapa 4: 9 eventos da linha do tempo do crime + 2 distrações."""

    eventos_uteis: list[str] = Field(
        min_length=3, max_length=3,
        description=(
            "3 eventos VERDADEIROS e relevantes da linha do tempo do crime "
            "(formato: 'HH:MM — descrição'). Devem permitir reconstruir o "
            "fato quando cruzados com outras pistas."
        ),
    )
    eventos_enganosos: list[str] = Field(
        min_length=2, max_length=2,
        description=(
            "2 eventos verdadeiros mas que sugerem culpado errado se vistos "
            "isoladamente."
        ),
    )
    eventos_falsos: list[str] = Field(
        min_length=2, max_length=2,
        description="2 eventos FALSOS mas explicáveis.",
    )
    eventos_inuteis: list[str] = Field(
        min_length=2, max_length=2,
        description="2 eventos verdadeiros mas irrelevantes pro caso.",
    )
    distracao_personagem_1: list[str] = Field(
        min_length=4, max_length=6,
        description=(
            "Linha do tempo (4-6 eventos) de outro personagem NÃO envolvido "
            "no crime. Realista mas irrelevante."
        ),
    )
    distracao_personagem_1_nome: str = Field(
        description="Nome+sobrenome do personagem da distração 1 (deve estar entre os 24 personagens fornecidos)."
    )
    distracao_personagem_2: list[str] = Field(
        min_length=4, max_length=6,
        description="Linha do tempo de OUTRO personagem NÃO envolvido.",
    )
    distracao_personagem_2_nome: str = Field(
        description="Nome+sobrenome do personagem da distração 2."
    )


class CharacterCommentsOutput(BaseModel):
    """Etapa 5: comentários sobre cada um dos 24 personagens."""

    comentarios: dict[str, str] = Field(
        description=(
            "Dicionário onde a chave é o valor do enum Profissao "
            "(ex: 'investigador_chefe') e o valor é um comentário curto "
            "(1-2 frases) sobre como esse personagem é visto pelos outros. "
            "Deve ter exatamente 24 entradas (uma por profissão)."
        )
    )
