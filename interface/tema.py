"""Cores e tipos de letra da interface.

Tema claro, pensado para ser lido num projetor: fundo claro, texto escuro e letra maior do que o habitual.
As cores dos agentes seguem a figura da proposta: azul para os agentes que usam o modelo de linguagem, verde para o
agente que só usa regras em Python (o Guardião)."""
import sys

COR = {
    "fundo": "#EEF2F7",      # fundo da janela
    "painel": "#FFFFFF",     # cartões e painéis
    "borda": "#CBD3DF",
    "texto": "#16202C",
    "sub": "#5A6678",        # texto secundário
    "topo": "#1F3A5F",       # barra do título (azul-marinho)
    "dest": "#1F5FA8",       # destaque e botões principais
    "ok": "#1B8A4B",         # COMPRAR, passa
    "cond": "#B86E00",       # CAIXA DEDICADA, revisão, parcial
    "nao": "#C42B2B",        # REJEITAR, falha
    "ent": "#FFFFFF",        # caixas de texto
    "llm": "#2D6CB5", "llm_f": "#E4EEFA",          # agente com modelo de linguagem
    "py": "#2E8B57", "py_f": "#E3F3EA",            # agente só com regras em Python
    "espera": "#9AA5B5", "espera_f": "#F5F7FA",    # agente ainda sem trabalho
    "rev": "#D9822B",        # pedido de revisão do Crítico (laranja, como na proposta)
}

if sys.platform == "win32":
    FUI = ("Segoe UI", 11); FMO = ("Consolas", 11); FTI = ("Segoe UI Semibold", 16)
else:
    FUI = ("DejaVu Sans", 10); FMO = ("DejaVu Sans Mono", 10); FTI = ("DejaVu Sans", 15, "bold")

def f(tam=None, peso=""):
    """Fonte da interface com outro tamanho e/ou peso (ex.: f(13, "bold"))."""
    t = (FUI[0], tam or FUI[1])
    return t + (peso,) if peso else t

def fmo(tam=None, peso=""):
    t = (FMO[0], tam or FMO[1])
    return t + (peso,) if peso else t

def cor_veredicto(categoria: str) -> str:
    """COMPRAR a verde, CAIXA DEDICADA e REVISÃO MANUAL a laranja, REJEITAR (e erros) a vermelho."""
    c = (categoria or "").upper()
    if c.startswith("COMPRAR"): return COR["ok"]
    if c.startswith(("CAIXA", "REVIS")): return COR["cond"]
    if not c: return COR["sub"]
    return COR["nao"]
