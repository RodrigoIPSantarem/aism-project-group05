"""Fonte FDIC (Federal Deposit Insurance Corporation): rácios regulatórios dos bancos americanos, gratuitos e sem chave.

O Protocolo v4.27 pede, para bancos, CET1 >= 12% e crédito malparado (NPL) <= 3% no Portão P3, e a margem financeira
(NIM) no Portão P8. Estes rácios não estão nos 10-K em XBRL (só aparecem os mínimos regulamentares), mas a FDIC publica-os
para cada banco a partir dos relatórios trimestrais ao supervisor (call reports).
Limite: os rácios são do banco principal do grupo (a instituição com depósitos), não do grupo consolidado.
"""
import re, urllib.parse
from fontes.mercado import _get_web

_BASE = "https://banks.data.fdic.gov/api"
_VAZIAS = {"CO", "CORP", "CORPORATION", "INC", "COMPANY", "THE", "GROUP", "HOLDINGS", "HOLDING", "DE", "MN", "NY", "NA", "N", "A", "OF"}
CAMPOS = {"RBCT1CER": "cet1", "NCLNLSR": "npl", "NIMY": "nim", "EEFFR": "eficiencia", "ROA": "roa", "ROE": "roe", "ASSET": "ativo_mil"}

_ABREV = {"FINL": "FINANCIAL", "BCORP": "BANCORP", "BANCORPORATION": "BANCORP", "SVCS": "SERVICES", "SVC": "SERVICES",
          "NATL": "NATIONAL", "HLDGS": "HOLDINGS", "GRP": "GROUP", "BK": "BANK", "AMER": "AMERICAN", "NY": "NEW YORK"}
_CURTAS = {}                                                          # FINANCIAL -> [FINL], BANCORP -> [BCORP, BANCORPORATION]
for _k, _v in _ABREV.items():
    if " " not in _v: _CURTAS.setdefault(_v, []).append(_k)

def _tokens(nome: str) -> set:
    """Palavras do nome normalizadas: sem estado (/DE/), sem pontuação, abreviaturas da FDIC expandidas, "U S" -> "US"."""
    n = re.sub(r"[\\/][A-Z]{2}[\\/]?", " ", (nome or "").upper()).replace(".", "").replace("&", " ")
    ws = re.sub(r"[^A-Z0-9 ]", " ", n).split()
    juntas, buf = [], ""
    for w in ws:                                       # letras soltas seguidas formam uma palavra ("U S" -> "US")
        if len(w) == 1: buf += w; continue
        if buf: juntas.append(buf); buf = ""
        juntas.append(w)
    if buf: juntas.append(buf)
    out = set()
    for w in juntas: out.update(_ABREV.get(w, w).split())
    return {w for w in out if w not in _VAZIAS}

def banco_principal(nome_grupo: str):
    """Instituição com mais ativos cujo grupo (NAMEHCR) tem o nome mais parecido com o da empresa cotada."""
    alvo = _tokens(nome_grupo)
    if not alvo: return None
    palavras = []
    for w in sorted(alvo, key=len):                   # palavras curtas e distintivas primeiro (ex.: PNC)
        palavras += [w] + _CURTAS.get(w, [])
    melhor = None
    for palavra in palavras[:8]:
        filtro = f"NAMEHCR:{palavra}* AND ACTIVE:1"
        url = (f"{_BASE}/institutions?filters={urllib.parse.quote(filtro)}&fields=CERT,NAME,NAMEHCR,ASSET"
               "&sort_by=ASSET&sort_order=DESC&limit=25")
        try: r = _get_web(url, f"fdic_inst_{palavra}.json", validade_h=24 * 30)
        except Exception: continue
        for x in r.get("data", []):
            dd = x["data"]; t = _tokens(dd.get("NAMEHCR", ""))
            sim = len(alvo & t) / max(len(alvo | t), 1)
            chave = (sim, dd.get("ASSET") or 0)
            if sim >= 0.6 and (melhor is None or chave > melhor[0]): melhor = (chave, dd)
        if melhor and melhor[0][0] == 1.0: break
    return melhor[1] if melhor else None

def fdic_indicadores(nome_grupo: str, anos: list) -> dict | None:
    """Rácios de fim de ano (4.º trimestre) do banco principal do grupo, para os anos pedidos."""
    b = banco_principal(nome_grupo)
    if not b: return None
    a0, a1 = min(anos), max(anos)
    filtro = f"CERT:{b['CERT']} AND REPDTE:[{a0}1231 TO {a1}1231]"
    url = (f"{_BASE}/financials?filters={urllib.parse.quote(filtro)}&fields=CERT,REPDTE,{','.join(CAMPOS)}"
           "&sort_by=REPDTE&sort_order=DESC&limit=100")
    try: r = _get_web(url, f"fdic_fin_{b['CERT']}_{a0}_{a1}.json", validade_h=24 * 7)
    except Exception: return None
    por_ano = {}
    for x in r.get("data", []):
        dd = x["data"]; rep = str(dd.get("REPDTE", ""))
        if not rep.endswith("1231"): continue
        por_ano[int(rep[:4])] = {nome: (round(float(dd[c]), 3) if dd.get(c) is not None else None) for c, nome in CAMPOS.items()}
    if not por_ano: return None
    return {"cert": b["CERT"], "banco": b["NAME"], "grupo_fdic": b["NAMEHCR"], "por_ano": por_ano,
            "fonte": f"FDIC BankFind (call reports), banco principal: {b['NAME']} (CERT {b['CERT']})"}
