"""Utilitários: formatação de números, normalização de rótulos, verificação de números citados pelo modelo e ortografia (AO90)."""
import json, os, re
from pathlib import Path
from config import RAIZ


def _num(v, casas=2, sfx=""):
    """Formata um número ao estilo português (vírgula decimal e espaço nos milhares); None aparece como 'n/d'."""
    if v is None: return "n/d"
    if v == float("inf"): return "infinito"
    return f"{v:,.{casas}f}{sfx}".replace(",", " ").replace(".", ",")

def _pct(v, casas=1): return "n/d" if v is None else f"{_num(v, casas)}%"

_CAMPOS_SERIE = {
    "receita":"Receita total","resultado_liquido":"Resultado líquido","ebitda":"EBITDA",
    "fco":"Fluxo caixa operacional","capex":"CapEx (positivo)","divida_total":"Dívida total",
    "caixa":"Caixa","capitais_proprios":"Capitais próprios","ativos_totais":"Ativo total",
    "goodwill":"Goodwill","acoes_diluidas":"Ações diluídas","dividendo_por_acao":"Dividendo/ação",
    "lucro_bruto":"Lucro bruto","juros":"Despesa de juros","da":"Depreciação e amortização",
    "sga":"SG&A",
    "rd":"I&D",
    "ebit":"Resultado operacional",
    "passivo_total":"Passivo total",
    "acoes_proprias":"Ações próprias (valor)",
    "resultados_transitados":"Resultados transitados",
    "imposto":"Imposto do exercício",
    "imposto_pago":"Imposto pago em caixa",
    "resultado_antes_impostos":"Resultado antes de impostos",
    "ebt_sem_extra":"Resultado antes de impostos sem itens extraordinários",
    "inventario":"Inventário",
    "dividendos_pagos":"Dividendos pagos",
    "recompras":"Recompra de ações",
    "sbc":"Remuneração em ações (SBC)",
    "var_fundo_maneio":"Variação do fundo de maneio (sinal do mapa de fluxos)",
    "contas_receber":"Contas a receber",
    "divida_curto_prazo":"Dívida de curto prazo",
    "divida_lp_corrente":"Dívida de longo prazo a vencer",
    "emissao_divida":"Emissão de dívida",
    "emissao_acoes":"Emissão de ações",
    "imparidades_goodwill":"Imparidades de goodwill",
    "aquisicoes":"Aquisições de negócios",
    "preferenciais":"Ações preferenciais",
    "lpa_diluido":"LPA diluído (reportado)",
    "reembolso_divida":"Reembolso de dívida",
    "rl_continuadas":"Resultado líquido das operações continuadas",
    "divida_lp":"Dívida de longo prazo (não corrente)",
    "margem_financeira":"Margem financeira (juros recebidos - juros pagos)",
    "receitas_nao_juros":"Receitas que não são juros",
    "custos_nao_juros":"Custos que não são juros (operacionais)",
    "credito_total":"Crédito a clientes (bruto)",
    "credito_malparado":"Crédito malparado (nonaccrual)",
    "depositos":"Depósitos",
    "intangiveis":"Intangíveis (sem goodwill)",
    "ativo_corrente":"Ativo corrente",
    "passivo_corrente":"Passivo corrente",
}
# Campos que muitas empresas não têm (sem I&D, sem ações próprias, sem preferenciais...): a ausência não é
# "dado em falta"; os testes tratam-na como zero ou "não aplicável", conforme o protocolo.
CAMPOS_OPCIONAIS = {"rd","acoes_proprias","preferenciais","emissao_acoes","emissao_divida","imparidades_goodwill",
                    "aquisicoes","divida_curto_prazo","divida_lp_corrente","inventario","var_fundo_maneio",
                    "ebt_sem_extra","imposto_pago","dividendo_por_acao","lpa_diluido","dividendos_pagos","recompras",
                    "reembolso_divida","rl_continuadas","divida_lp",
                    "margem_financeira","receitas_nao_juros","custos_nao_juros","credito_total","credito_malparado","depositos",
                    "intangiveis","ativo_corrente","passivo_corrente"}
_CAMPOS_PONT = {"preco_atual","moat_score","pl_medio_historico","taxa_10_anos"}   # v4.27: o beta não é usado
_SIN = {
    "receita":["revenue","revenues","total revenue","sales","net sales","receita","vendas","turnover"],
    "resultado_liquido":["net income","net earnings","net profit","profit attributable to owners of the parent",
                         "resultado liquido","lucro liquido","profit"],
    "ebitda":["ebitda"],
    "fco":["operating cash flow","cash from operations","net cash provided by operating activities",
           "cash generated from operating activities","fco"],
    "capex":["capital expenditures","capex","purchase of property, plant and equipment","investimento"],
    "divida_total":["total debt","debt","long-term debt","borrowings","divida total"],
    "caixa":["cash & equivalents","cash and equivalents","cash at bank","caixa"],
    "capitais_proprios":["shareholders' equity","shareholders equity","total equity","equity","capitais proprios"],
    "ativos_totais":["total assets","assets","ativo total"],
    "goodwill":["goodwill"],
    "acoes_diluidas":["diluted shares outstanding","weighted average number of diluted shares outstanding",
                      "shares outstanding (diluted)","diluted shares","acoes diluidas"],
    "dividendo_por_acao":["dividend per share","dividends per share","dividendo por acao"],
    "lucro_bruto":["gross profit","lucro bruto","margem bruta absoluta"],
    "juros":["interest expense","juros","despesa de juros"],
    "da":["d&a","depreciation & amortization","depreciation and amortization","depreciacao e amortizacao"],
    "sga":["sga"],
    "rd":["rd"],
    "ebit":["ebit"],
    "passivo_total":["passivo_total"],
    "acoes_proprias":["acoes_proprias"],
    "resultados_transitados":["resultados_transitados"],
    "imposto":["imposto"],
    "imposto_pago":["imposto_pago"],
    "resultado_antes_impostos":["resultado_antes_impostos"],
    "ebt_sem_extra":["ebt_sem_extra"],
    "inventario":["inventario"],
    "dividendos_pagos":["dividendos_pagos"],
    "recompras":["recompras"],
    "sbc":["sbc"],
    "var_fundo_maneio":["var_fundo_maneio"],
    "contas_receber":["contas_receber"],
    "divida_curto_prazo":["divida_curto_prazo"],
    "divida_lp_corrente":["divida_lp_corrente"],
    "emissao_divida":["emissao_divida"],
    "emissao_acoes":["emissao_acoes"],
    "imparidades_goodwill":["imparidades_goodwill"],
    "aquisicoes":["aquisicoes"],
    "preferenciais":["preferenciais"],
    "lpa_diluido":["lpa_diluido"],
    "reembolso_divida":["reembolso_divida"],
    "rl_continuadas":["rl_continuadas"],
    "divida_lp":["divida_lp"],
    "margem_financeira":["margem_financeira"],
    "receitas_nao_juros":["receitas_nao_juros"],
    "custos_nao_juros":["custos_nao_juros"],
    "credito_total":["credito_total"],
    "credito_malparado":["credito_malparado"],
    "depositos":["depositos"],
    "intangiveis":["intangiveis"],
    "ativo_corrente":["ativo_corrente"],
    "passivo_corrente":["passivo_corrente"],
}
_IDX = {s.lower(): c for c, lst in _SIN.items() for s in lst}
_IDX.update({c: c for c in _CAMPOS_SERIE})        # o nome interno do campo também é um rótulo válido
_MULT = {"k":1e3,"m":1e6,"b":1e9,"t":1e12}
_VAZIO = {"","-","—","n/a","na","nan","null","none","em falta"}

def _campo(rotulo: str) -> str | None:
    """Procura o nome interno do campo (p. ex. 'receita') a partir do rótulo que vem da fonte."""
    return _IDX.get(re.sub(r"\s+"," ", rotulo.strip().lower()))

def _ler(bruto) -> float | None:
    """Converte um valor vindo de uma fonte ou do modelo (texto, 'n/d', número) em float, ou None se não for um número."""
    if bruto is None or isinstance(bruto, bool): return None
    if isinstance(bruto, (int,float)): return float(bruto)
    t = str(bruto).strip().lower().replace(" ","")
    if t in _VAZIO: return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",","").replace("$","").replace("€","").rstrip("%")
    mult = 1.0
    if t and t[-1] in _MULT: mult, t = _MULT[t[-1]], t[:-1]
    try: v = float(t) * mult
    except ValueError: return None
    return -v if neg else v

def _moat(b) -> int | None:
    """Converte a classificação de fosso económico dada pelo modelo numa pontuação inteira."""
    if b is None: return None
    m = {"wide":2,"wide moat":2,"2":2,"narrow":1,"narrow moat":1,"1":1,"none":0,"nenhum":0,"0":0}
    return m.get(str(b).strip().lower())

# Regra do sistema: o modelo só pode citar números que existem nos dados que recebeu.
_NUM_RE=re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)*(?![\w])")
_CONSTANTES_PERMITIDAS={0,1,2,3,4,5,6,7,8,9,10,12,15,20,25,30,40,50,75,80,85,100,1988,1990}

def _numeros_de(obj) -> list[float]:
    """Lista todos os números que aparecem num objeto (dados ou texto); serve para verificar se um texto do modelo só usa números reais."""
    txt=json.dumps(obj,ensure_ascii=False,default=str) if not isinstance(obj,str) else obj
    out=[]
    for t in _NUM_RE.findall(txt):
        t=t.replace(" ","")
        if t.count(",")==1 and t.count(".")==0: t=t.replace(",",".")
        elif t.count(".")>=1 and t.count(",")==1: t=t.replace(".","").replace(",",".")
        else: t=t.replace(",","")
        try: out.append(float(t))
        except ValueError: pass
    return out

def _numeros_nao_verificados(texto: str, contexto) -> list[str]:
    """Números do texto que não aparecem nos dados (tolerância de arredondamento, escalas M/mil M e percentagens)."""
    if not texto: return []
    refs=_numeros_de(contexto)
    variantes=set()
    for v in refs:
        for x in (v,v*100,v/100,v/1e6,v/1e9,v/1e3):
            variantes.add(x); variantes.add(abs(x))
    falhas=[]
    for x in _numeros_de(texto):
        if x in _CONSTANTES_PERMITIDAS or (1900<=x<=2100 and x==int(x)): continue
        if not any(abs(x-v)<=max(0.06,0.006*abs(v)) for v in variantes):
            falhas.append(_num(x,2).rstrip("0").rstrip(","))
    return sorted(set(falhas))

_AO90=[("actualmente","atualmente"),("actuais","atuais"),("actual","atual"),("acções","ações"),("acção","ação"),
       ("atractiv","atrativ"),("óptim","ótim"),("direcção","direção"),("projecção","projeção"),("efectiv","efetiv"),
       ("exactamente","exatamente"),("exacto","exato"),("colectiv","coletiv"),("protecção","proteção"),
       ("selecção","seleção"),("objectiv","objetiv"),("aspecto","aspeto"),("perspectiva","perspetiva"),
       ("respectiv","respetiv"),("factor","fator"),("sector","setor"),("adopt","adot"),("óptica","ótica"),
       ("baptism","batism"),("reacção","reação"),("detect","detet"),("contractual","contratual")]

def _ao90(txt):
    """Corrige grafias anteriores ao Acordo Ortográfico de 1990 que o modelo às vezes produz."""
    if not isinstance(txt,str): return txt
    for velho,novo in _AO90:
        txt=re.sub(velho,novo,txt); txt=re.sub(velho.capitalize(),novo.capitalize(),txt)
    return txt

def _carregar_env(cam: Path|None=None):
    """Lê o ficheiro .env (chaves e definições do utilizador) e põe-no nas variáveis de ambiente; nunca é copiado para os entregáveis."""
    cam=cam or RAIZ/".env"
    if not cam.exists(): return
    for l in cam.read_text(encoding="utf-8").splitlines():
        l=l.strip()
        if l and not l.startswith("#") and "=" in l:
            k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))
