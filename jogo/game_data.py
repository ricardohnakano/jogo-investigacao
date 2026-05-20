from enum import Enum


class Equipe(str, Enum):
    POLICIA = "policia"
    DETETIVES = "detetives"
    JORNALISTAS = "jornalistas"
    HACKERS = "hackers"


EQUIPE_LABEL = {
    Equipe.POLICIA: "Policiais",
    Equipe.DETETIVES: "Detetives Particulares",
    Equipe.JORNALISTAS: "Jornalistas Investigativos",
    Equipe.HACKERS: "Agência de Inteligência",
}


class Profissao(str, Enum):
    INVESTIGADOR_CHEFE = "investigador_chefe"
    PERITO_CRIMINAL = "perito_criminal"
    INTERROGADOR = "interrogador"
    ANALISTA_OCORRENCIAS = "analista_ocorrencias"
    OFICIAL_CAMPO = "oficial_campo"
    DELEGADO = "delegado"

    DETETIVE_PRINCIPAL = "detetive_principal"
    EX_POLICIAL = "ex_policial"
    ESPECIALISTA_FRAUDE = "especialista_fraude"
    INFILTRADOR = "infiltrador"
    ANALISTA_COMPORTAMENTAL = "analista_comportamental"
    ESPECIALISTA_VIGILANCIA = "especialista_vigilancia"

    EDITOR_CHEFE = "editor_chefe"
    REPORTER_CAMPO = "reporter_campo"
    CHECADOR_FATOS = "checador_fatos"
    FOTOJORNALISTA = "fotojornalista"
    DIRETOR_INVESTIGATIVO = "diretor_investigativo"
    COLUNISTA = "colunista"

    COORDENADOR = "coordenador"
    HACKER = "hacker"
    CRIPTOGRAFO = "criptografo"
    ENGENHEIRO_SOCIAL = "engenheiro_social"
    ANALISTA_METADADOS = "analista_metadados"
    INVASOR_SISTEMA = "invasor_sistema"


PROFISSOES_POR_EQUIPE: dict[Equipe, list[Profissao]] = {
    Equipe.POLICIA: [
        Profissao.INVESTIGADOR_CHEFE,
        Profissao.PERITO_CRIMINAL,
        Profissao.INTERROGADOR,
        Profissao.ANALISTA_OCORRENCIAS,
        Profissao.OFICIAL_CAMPO,
        Profissao.DELEGADO,
    ],
    Equipe.DETETIVES: [
        Profissao.DETETIVE_PRINCIPAL,
        Profissao.EX_POLICIAL,
        Profissao.ESPECIALISTA_FRAUDE,
        Profissao.INFILTRADOR,
        Profissao.ANALISTA_COMPORTAMENTAL,
        Profissao.ESPECIALISTA_VIGILANCIA,
    ],
    Equipe.JORNALISTAS: [
        Profissao.EDITOR_CHEFE,
        Profissao.REPORTER_CAMPO,
        Profissao.CHECADOR_FATOS,
        Profissao.FOTOJORNALISTA,
        Profissao.DIRETOR_INVESTIGATIVO,
        Profissao.COLUNISTA,
    ],
    Equipe.HACKERS: [
        Profissao.COORDENADOR,
        Profissao.HACKER,
        Profissao.CRIPTOGRAFO,
        Profissao.ENGENHEIRO_SOCIAL,
        Profissao.ANALISTA_METADADOS,
        Profissao.INVASOR_SISTEMA,
    ],
}


PROFISSAO_INFO: dict[Profissao, tuple[str, str]] = {
    Profissao.INVESTIGADOR_CHEFE: (
        "Investigador chefe",
        "Elimina 1 personagem",
    ),
    Profissao.PERITO_CRIMINAL: (
        "Perito criminal",
        "Tem 1 informação verdadeira de objeto/local",
    ),
    Profissao.INTERROGADOR: (
        "Interrogador",
        "Chama uma pessoa do time adversário e faz 5 perguntas sim/não",
    ),
    Profissao.ANALISTA_OCORRENCIAS: (
        "Analista de ocorrências",
        "Classifica 1 dica enganosa/falsa/inútil sobre a linha do tempo",
    ),
    Profissao.OFICIAL_CAMPO: (
        "Oficial de campo",
        "Pode ficar 3 minutos no cômodo do time adversário",
    ),
    Profissao.DELEGADO: (
        "Delegado",
        "Pode prender uma pessoa do outro time por 5 minutos",
    ),
    Profissao.DETETIVE_PRINCIPAL: (
        "Detetive principal",
        "Elimina 1 personagem",
    ),
    Profissao.EX_POLICIAL: (
        "Ex-policial",
        "Pode ficar 3 minutos no cômodo do time adversário",
    ),
    Profissao.ESPECIALISTA_FRAUDE: (
        "Especialista em fraude",
        "Classifica 1 dica enganosa/falsa/inútil sobre o objeto/local",
    ),
    Profissao.INFILTRADOR: (
        "Infiltrador",
        "Pega as dicas eliminadas de objeto/local do time adversário",
    ),
    Profissao.ANALISTA_COMPORTAMENTAL: (
        "Analista comportamental",
        "Classifica 1 dica enganosa/falsa/inútil sobre as fichas civis",
    ),
    Profissao.ESPECIALISTA_VIGILANCIA: (
        "Especialista em vigilância",
        "Classifica 1 dica enganosa/falsa/inútil sobre a linha do tempo",
    ),
    Profissao.EDITOR_CHEFE: (
        "Editor chefe",
        "Elimina 1 personagem",
    ),
    Profissao.REPORTER_CAMPO: (
        "Repórter de campo",
        "Pega as dicas eliminadas de fichas do time adversário",
    ),
    Profissao.CHECADOR_FATOS: (
        "Checador de fatos",
        "Classifica 1 informação enganosa/falsa/inútil de objeto/local",
    ),
    Profissao.FOTOJORNALISTA: (
        "Fotojornalista",
        "Melhora a imagem das fotos",
    ),
    Profissao.DIRETOR_INVESTIGATIVO: (
        "Diretor investigativo",
        "Tem 1 informação verdadeira da ficha civil",
    ),
    Profissao.COLUNISTA: (
        "Colunista",
        "Classifica 1 informação enganosa/falsa/inútil das fichas civis",
    ),
    Profissao.COORDENADOR: (
        "Coordenador",
        "Elimina 1 personagem",
    ),
    Profissao.HACKER: (
        "Hacker",
        "Mantém a dificuldade de 3 side quests",
    ),
    Profissao.CRIPTOGRAFO: (
        "Criptógrafo",
        "Recebe a informação de quantos cúmplices existem no jogo",
    ),
    Profissao.ENGENHEIRO_SOCIAL: (
        "Engenheiro social",
        "Classifica 1 dica enganosa/falsa/inútil das fichas civis",
    ),
    Profissao.ANALISTA_METADADOS: (
        "Analista de metadados",
        "Tem 1 informação verdadeira do local/objeto",
    ),
    Profissao.INVASOR_SISTEMA: (
        "Invasor de sistema",
        "Impede o time adversário de classificar 1 dica no próximo ciclo",
    ),
}


def profissao_nome(p: Profissao) -> str:
    return PROFISSAO_INFO[p][0]


def profissao_acao(p: Profissao) -> str:
    return PROFISSAO_INFO[p][1]


EQUIPE_DE_PROFISSAO: dict[Profissao, Equipe] = {
    p: equipe
    for equipe, profs in PROFISSOES_POR_EQUIPE.items()
    for p in profs
}


class FuncaoEspecial(str, Enum):
    NENHUMA = "nenhuma"
    CRIMINOSO = "criminoso"
    VITIMA = "vitima"
    CUMPLICE = "cumplice"


PROB_CUMPLICE_1 = 0.80
PROB_CUMPLICE_2 = 0.60


class ClueCategory(str, Enum):
    OBJETO_LOCAL = "objeto_local"
    FICHA_CIVIL = "ficha_civil"
    LINHA_TEMPO = "linha_tempo"


class ClueVeracity(str, Enum):
    VERDADEIRA = "verdadeira"
    ENGANOSA = "enganosa"
    FALSA = "falsa"
    INUTIL = "inutil"


CLUE_COUNTS: dict[ClueCategory, dict[ClueVeracity, int]] = {
    ClueCategory.OBJETO_LOCAL: {
        ClueVeracity.VERDADEIRA: 3,
        ClueVeracity.ENGANOSA: 2,
        ClueVeracity.FALSA: 2,
        ClueVeracity.INUTIL: 2,
    },
    ClueCategory.FICHA_CIVIL: {
        ClueVeracity.VERDADEIRA: 5,
        ClueVeracity.ENGANOSA: 2,
        ClueVeracity.FALSA: 2,
        ClueVeracity.INUTIL: 2,
    },
    ClueCategory.LINHA_TEMPO: {
        ClueVeracity.VERDADEIRA: 3,
        ClueVeracity.ENGANOSA: 2,
        ClueVeracity.FALSA: 2,
        ClueVeracity.INUTIL: 2,
    },
}

EXTRA_FALSE_OBJETO_LOCAL = 15

IMAGE_STAGES = [0.02, 0.06, 0.14, 0.25, 0.39, 0.56]

TOTAL_CYCLES = 6
CYCLE_DURATION_SECONDS = 600  # 10 min; use 60 para testes rápidos

MIN_PLAYERS_PER_TEAM = 3
MIN_TEAMS = 2
MIN_TOTAL_PLAYERS = 6
MAX_TOTAL_PLAYERS = 24
COUNTDOWN_SECONDS = 10
GENERATION_MIN_SECONDS = 2
LLM_MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Side quests
# ---------------------------------------------------------------------------


class SideQuestKind(str, Enum):
    MASTERMIND = "mastermind"
    LABYRINTH = "labyrinth"
    HIGHER_LOWER = "higher_lower"


class SideQuestStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


class SideQuestDifficulty(str, Enum):
    NORMAL = "normal"
    HARD = "hard"


class SideQuestReward(str, Enum):
    REVEAL_EXTRA_CLUE = "reveal_extra_clue"
    BLOCK_OPPONENT_CHARACTER = "block_opponent_character"


SIDE_QUESTS_PER_CYCLE = 3
ACTION_LOCK_TIMEOUT_SECONDS = 60

MASTERMIND_DIGITS_NORMAL = 4
MASTERMIND_DIGITS_HARD = 5
MASTERMIND_MAX_ATTEMPTS_NORMAL = 8
MASTERMIND_MAX_ATTEMPTS_HARD = 10

HIGHER_LOWER_RANGE_NORMAL = 50
HIGHER_LOWER_RANGE_HARD = 100
HIGHER_LOWER_MAX_ATTEMPTS_NORMAL = 7
HIGHER_LOWER_MAX_ATTEMPTS_HARD = 10

LABYRINTH_SIZE_NORMAL = 4
LABYRINTH_SIZE_HARD = 5


class ActionKind(str, Enum):
    ELIMINATE_CHARACTER = "eliminate_character"
    REVEAL_TRUE_CLUE = "reveal_true_clue"
    INTERROGATE = "interrogate"
    CLASSIFY_CLUE = "classify_clue"
    STEAL_ELIMINATED_CLUES = "steal_eliminated_clues"
    BLOCK_OPPONENT_CLASSIFY = "block_opponent_classify"
    LOCK_SIDE_QUESTS_HARD = "lock_side_quests_hard"
    PHYSICAL_ROOM_ACCESS = "physical_room_access"
    PHYSICAL_DETAIN = "physical_detain"
    REVEAL_ACCOMPLICES_COUNT = "reveal_accomplices_count"
    IMPROVE_IMAGE = "improve_image"
