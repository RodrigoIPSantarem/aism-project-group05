"""A2 Guardião (Python puro): o que o Protocolo v4.27 decide antes da análise completa.

Passo -2  Triagem Rápida (Secção 6.0): 7 perguntas de sim ou não. As perguntas 2 a 7 são numéricas e respondidas aqui;
          a pergunta 1 ("percebo o produto?") é qualitativa e fica para o Avaliador. Sem exceções (carta de 1980).
Passo 0   Setor: cíclicas (mineiras, energia, semicondutores, materiais, químicos, transportes), MLPs e REITs ficam fora
          do método; bancos e seguradoras ficam dentro, com respostas próprias em três Portões.
Passo 1   Regra de Commodity, critérios (a) e (b); o (c) é do Avaliador.
Base      Lucro líquido positivo no último exercício; histórico mínimo de 5 anos.

Para a apresentação: este agente não usa o modelo de linguagem. São regras determinísticas do protocolo, por isso o
resultado é sempre o mesmo para os mesmos dados (reprodutível e auditável). Se a empresa reprova, o Guardião manda a
razão diretamente ao Decisor (inform) e o Avaliador nem chega a gastar tempo; se passa, faz request ao Avaliador.
"""
import statistics
from config import (ANOS_MINIMOS, CAMPOS_ESSENCIAIS, COMMODITY_ANOS_LPA_MAU, COMMODITY_MARGEM_BRUTA, COMMODITY_ROE,
                    MAX_FALTA_ESSENCIAIS, PT_FORA_METODO, SIC_BANCOS, SIC_FORA_METODO, SIC_REIT, SIC_SEGURADORAS, TRIAGEM,
                    TRIAGEM_DILUICAO, TRIAGEM_DIVIDA_ANOS, TRIAGEM_MARGEM_BRUTA, TRIAGEM_ROE_MIN,
                    YF_FORA_METODO_INDUSTRIAS, YF_FORA_METODO_SETORES)
from nucleo.metricas import _anos, _dilui_3, _margem_bruta_anual, _ult, _val
from nucleo.plataforma import Agente, Msg
from nucleo.util import _num
from nucleo.valorizacao import lpa_ajustado

SIM_, NAO_, PEND, NA_ = "sim", "não", "pendente", "não aplicável"

def _verif_dados(d):
    """Os dados chegam completos? Mínimo de 5 anos com receita, resultado e fluxo de caixa operacional, no máximo 20% de
    valores essenciais em falta, último ano completo, e preço e taxa a 10 anos disponíveis. Devolve a lista de motivos."""
    motivos = []; anos = _anos(d)
    compl = [a for a in anos if all(_val(d, c, a) is not None for c in CAMPOS_ESSENCIAIS)]
    if len(compl) < ANOS_MINIMOS:
        motivos.append(f"só {len(compl)} anos de demonstrações completas: com menos de {ANOS_MINIMOS}, rejeitar (Secção 6.1)")
    cel = len(anos) * len(CAMPOS_ESSENCIAIS)
    falta = sum(_val(d, c, a) is None for c in CAMPOS_ESSENCIAIS for a in anos)
    if cel and falta / cel > MAX_FALTA_ESSENCIAIS: motivos.append(f"{falta}/{cel} valores essenciais em falta")
    if anos and anos[-1] not in compl: motivos.append(f"último ano ({anos[-1]}) incompleto")
    for c in ("preco_atual", "taxa_10_anos"):
        if d["pontuais"].get(c) is None: motivos.append(f"{c} em falta")
    return motivos

def _no(sic, faixas): return sic is not None and any(a <= sic <= b for a, b in faixas)

def setor(d) -> tuple[str, str]:
    """Passo 0. Classificação do Yahoo (tipo GICS) quando existe; SIC da SEC como reserva."""
    e = d["empresa"]; sic = e.get("sic"); ind = e.get("industria_yf") or ""; syf = e.get("setor_yf") or ""
    origem = (f"Yahoo: {syf} / {ind}" + (f" · SIC {sic}" if sic else "")) if syf else \
             (f"SIC {sic} ({e.get('sic_desc') or ''})" if sic else f"setor: {e.get('setor') or 'n/d'}")
    if _no(sic, SIC_BANCOS) or "Banks" in ind: return "banco", origem
    if _no(sic, SIC_SEGURADORAS) or "Insurance" in ind: return "seguradora", origem
    if _no(sic, SIC_REIT) or ind.startswith("REIT"): return "fora_metodo", origem + " — REIT (Pilar Terras)"
    if syf: fora = syf in YF_FORA_METODO_SETORES or any(x in ind for x in YF_FORA_METODO_INDUSTRIAS)
    else: fora = _no(sic, SIC_FORA_METODO) or any(x in str(e.get("setor") or "").lower() for x in PT_FORA_METODO)
    return ("fora_metodo" if fora else "padrao"), origem

def _q(id_, resposta, detalhe, nota="", valor=None):
    return {"id": id_, "pergunta": TRIAGEM.get(id_, id_), "resposta": resposta, "detalhe": detalhe, "nota": nota, "valor": valor}

def triagem(d, set_):
    """Passo -2, as 7 perguntas de sim ou não (Secção 6.0). Um "não" elimina a empresa, sem exceções.
    T1 qualitativa (Avaliador) · T2 LPA positivo e a subir · T3 ROE médio mínimo · T4 dívida paga em poucos anos de lucro
    · T5 margem bruta mínima · T6 diluição de ações limitada em 3 anos · T7 fluxo de caixa operacional sempre positivo.
    Bancos e seguradoras têm respostas próprias (não aplicável) porque a dívida e o fluxo de caixa significam outra coisa."""
    lpa, _, _, _ = lpa_ajustado(d)
    anos = _anos(d); out = [_q("T1", PEND, "pergunta qualitativa: respondida pelo Avaliador (parte qualitativa, com o modelo)")]
    serie = [(a, v) for a, v in sorted(lpa.items()) if v is not None]
    if len(serie) >= 5:
        prej = [a for a, v in serie if v <= 0]; sobe = serie[-1][1] > serie[0][1]
        out.append(_q("T2", SIM_ if not prej and sobe else NAO_,
                      f"LPA {serie[0][0]} {_num(serie[0][1], 2)} -> {serie[-1][0]} {_num(serie[-1][1], 2)}" + (f"; prejuízo em {prej}" if prej else "")))
    else: out.append(_q("T2", "sem dados", f"só {len(serie)} anos de LPA nas fontes (a SEC guarda as ações por classe nalgumas empresas)",
                        "completar com a chave gratuita da Alpha Vantage no .env (histórico de LPA) ou com o roic.ai"))
    roes = []
    for a in anos:
        cp, rl = _val(d, "capitais_proprios", a), _val(d, "resultado_liquido", a)
        if cp and rl is not None:
            if cp <= 0:
                ap = abs(_val(d, "acoes_proprias", a) or 0)
                if cp + ap > 0: roes.append(100 * rl / (cp + ap))
            else: roes.append(100 * rl / cp)
    out.append(_q("T3", (SIM_ if statistics.mean(roes) >= TRIAGEM_ROE_MIN else NAO_) if roes else NAO_,
                  f"ROE médio {_num(statistics.mean(roes), 1)}%" if roes else "sem dados",
                  valor=statistics.mean(roes) if roes else None))
    if set_ in ("banco", "seguradora"):
        out.append(_q("T4", NA_, f"dívida é matéria-prima de {set_}s: medida pelos Portões próprios"))
    else:
        luc = [x for x in (_val(d, "resultado_liquido", a) for a in anos[-5:]) if x is not None and x > 0]
        div, cx = (_ult(d, "divida_lp") if _ult(d, "divida_lp") is not None else _ult(d, "divida_total")), _ult(d, "caixa") or 0
        if not luc: out.append(_q("T4", NAO_, "sem lucros positivos nos últimos 5 anos para pagar a dívida"))
        elif div is None:       # nada se inventa: sem o valor da dívida, a T4 fica sem dados (pode não ter dívida; confirmar no relatório)
            out.append(_q("T4", "sem dados", "dívida de longo prazo não reportada nas fontes", "pode não ter dívida: confirmar no relatório anual"))
        elif cx >= div: out.append(_q("T4", SIM_, "caixa líquida"))
        else:
            anos_div = div / statistics.mean(luc)
            out.append(_q("T4", SIM_ if anos_div <= TRIAGEM_DIVIDA_ANOS else NAO_, f"dívida LP = {_num(anos_div, 2)} anos de lucro médio (5 anos)",
                          valor=anos_div))
    if set_ in ("banco", "seguradora"):
        out.append(_q("T5", NA_, f"margem bruta não se aplica a {set_}s"))
    else:
        mb = [v for v in _margem_bruta_anual(d).values() if v is not None]
        if not mb: out.append(_q("T5", "sem dados", "sem lucro bruto nas fontes", "a margem bruta é obrigatória na Triagem"))
        elif statistics.median(mb) >= TRIAGEM_MARGEM_BRUTA: out.append(_q("T5", SIM_, f"margem bruta mediana {_num(statistics.median(mb), 1)}%"))
        else: out.append(_q("T5", PEND, f"margem bruta mediana {_num(statistics.median(mb), 1)}% < 20%: só passa se o Avaliador confirmar baixo custo (M3)"))
    dil = _dilui_3(d)
    out.append(_q("T6", (SIM_ if dil <= TRIAGEM_DILUICAO else NAO_) if dil is not None else NAO_,
                  f"ações {'+' if (dil or 0) > 0 else ''}{_num(dil, 1)}% em 3 anos" if dil is not None else "sem dados de ações"))
    if set_ in ("banco", "seguradora"):
        out.append(_q("T7", NA_, f"o fluxo de caixa operacional de {set_}s mistura crédito, depósitos e carteira de títulos",
                      "calibração: na v4.25 os Kill Switches bancários substituíam o do FCO; a v4.27 não o diz"))
        return out
    fco = {a: _val(d, "fco", a) for a in anos}
    neg = [a for a, v in fco.items() if v is not None and v <= 0]
    out.append(_q("T7", NAO_ if neg or all(v is None for v in fco.values()) else SIM_,
                  f"FCO não positivo em {neg}" if neg else "FCO positivo em todos os anos"))
    return out

def filtros_base(d):
    """Lucro positivo no último exercício e Regra de Commodity (critérios a e b): margem bruta e ROE baixos, ou LPA mau
    em vários anos, significam um negócio sem poder de preço. O critério (c) precisa de ler texto e fica para o Avaliador."""
    out = []; rl = _ult(d, "resultado_liquido")
    out.append({"id": "LUCRO", "pergunta": "Lucro líquido positivo nos últimos 12 meses (último exercício)",
                "resposta": SIM_ if rl and rl > 0 else NAO_, "detalhe": f"{_num((rl or 0) / 1e6, 0)} M", "nota": ""})
    anos = _anos(d)[-10:]
    mb = [v for a, v in _margem_bruta_anual(d).items() if v is not None and a in anos]
    roes = [100 * _val(d, "resultado_liquido", a) / _val(d, "capitais_proprios", a) for a in anos
            if _val(d, "capitais_proprios", a) and _val(d, "capitais_proprios", a) > 0 and _val(d, "resultado_liquido", a) is not None]
    lpa, _, _, _ = lpa_ajustado(d); serie = [lpa.get(a) for a in anos]
    maus = sum(1 for i, v in enumerate(serie) if v is not None and (v <= 0 or (i > 0 and serie[i - 1] and serie[i - 1] > 0 and v < 0.5 * serie[i - 1])))
    a_ = bool(mb and roes and statistics.mean(mb) < COMMODITY_MARGEM_BRUTA and statistics.mean(roes) < COMMODITY_ROE)
    b_ = maus >= COMMODITY_ANOS_LPA_MAU
    out.append({"id": "COMMODITY", "pergunta": "Passo 1: Regra de Commodity (a) margem bruta < 20% E ROE < 15%; (b) LPA mau em 3+ anos",
                "resposta": NAO_ if (a_ or b_) else SIM_,
                "detalhe": (f"margem bruta média {_num(statistics.mean(mb), 1)}%" if mb else "margem bruta n/d")
                           + (f", ROE médio {_num(statistics.mean(roes), 1)}%" if roes else "") + f", {maus} ano(s) de LPA com prejuízo ou queda > 50%",
                "nota": "o critério (c), serviço que depende de talentos individuais, é avaliado pelo Avaliador"})
    return out

class Guardiao(Agente):
    """Recebe os dados (inform). Se a empresa é rejeitada na Triagem, no Setor ou noutra regra eliminatória, envia o resultado direto ao Decisor (inform); se passa, pede a avaliação ao Avaliador (request)."""
    nome = "guardiao"; rotulo = "[A2 Guardião]"

    def receber(self, m: Msg) -> list[Msg]:
        """Junta as verificações (dados, setor, triagem, filtros base). Se há motivos de rejeição, informa o Decisor;
        se não, pede a avaliação ao Avaliador."""
        c = m.conteudo; d = c["dados"]
        dados_ins = _verif_dados(d); set_, origem = setor(d)
        tri = triagem(d, set_) if set_ != "fora_metodo" else []
        base = filtros_base(d) if set_ != "fora_metodo" else []
        motivos = list(dados_ins)
        if set_ == "fora_metodo": motivos.append(f"Passo 0: fora do método (cíclica, MLP ou REIT) — {origem}")
        motivos += [f"Triagem {q['id']}: {q['pergunta']} Não — {q['detalhe']}" for q in tri if q["resposta"] == NAO_]
        motivos += [f"Dados insuficientes para a Triagem {q['id']}: {q['detalhe']} ({q['nota']})" for q in tri if q["resposta"] == "sem dados"]
        motivos += [f"{q['id']}: {q['detalhe']}" for q in base if q["resposta"] == NAO_]
        res = {"aprovada": not motivos, "motivos": motivos, "setor": set_, "origem_setor": origem, "triagem": tri, "base": base,
               "dados_insuficientes": dados_ins, "t5_pendente": any(q["id"] == "T5" and q["resposta"] == PEND for q in tri)}
        if self.plat: self.plat.emitir("guardiao_resultado", "guardiao", res)     # a janela principal mostra a triagem em direto
        if not res["aprovada"]:     # reprovada: salta o Avaliador e o Crítico e vai direta ao Decisor, que emite REJEITAR
            self.dizer("rejeitada: " + "; ".join(motivos)[:220])
            return [m.r("inform", "decisor", {**c, "guardiao": res})]
        self.dizer(f"setor {set_}: Triagem (T2–T7), Regra de Commodity e filtros base aprovados"
                   + ("; T5 depende de o Avaliador confirmar baixo custo (M3)" if res["t5_pendente"] else ""))
        return [m.r("request", "avaliador", {**c, "guardiao": res})]
