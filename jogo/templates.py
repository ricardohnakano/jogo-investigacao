from fastapi.templating import Jinja2Templates

from jogo.game_data import EQUIPE_LABEL, PROFISSAO_INFO

templates = Jinja2Templates(directory="templates")
templates.env.globals["EQUIPE_LABEL"] = EQUIPE_LABEL
templates.env.globals["PROFISSAO_INFO"] = PROFISSAO_INFO
