"""Testes Buffett do Protocolo v4.27 (Secção 6.2) e os 10 Portões (Secção 6.3).

Cada teste responde Sim, Parcial ou Não (sem pontos). Regras aplicadas:
- Medido em cada ano da janela (10 anos se houver; mínimo 5), nunca TTM; a mediana escolhe a resposta.
- Regra de Consistência proporcional: para Sim, o limiar de Sim tem de ser cumprido em 70% dos anos; senão, Parcial.
- Um teste que não se aplica ao setor ou ao modelo fica "não aplicável" e não conta contra a empresa.
- Os Portões passam com Sim ou Parcial. Sem dados não há prova: o Portão não passa.
"""
import statistics
from config import (CONSISTENCIA_MIN, FRANQUIA_PERGUNTAS, KE_MINIMO, NAO_, PARCIAL, PORTOES, SIM, TAXA_LEGAL_IMPOSTO,
                    TESTES_POR_ANO)
from nucleo.metricas import _anos, _val
from nucleo.util import _num

NA, SEM_DADOS = "não aplicável", "sem dados"
PASSA = (SIM, PARCIAL, NA)

def _v(d, c, a, zero=False):
    x = _val(d, c, a)
    return 0.0 if (x is None and zero) else x

def _anos_ok(d):
    return [a for a in _anos(d) if _val(d, "receita", a) is not None and _val(d, "resultado_liquido", a) is not None]

def _resposta(v, direcao, lim_sim, lim_parcial):
    """Converte um valor numérico em Sim / Parcial / Não conforme dois limiares do protocolo ('maior' = quanto mais alto melhor; 'menor' = quanto mais baixo melhor). Sem valor devolve None (Sem dados)."""
    if v is None: return None
    if direcao == "maior": return SIM if v >= lim_sim else (PARCIAL if v >= lim_parcial else NAO_)
    sim = v < lim_sim if lim_sim == 0.80 else v <= lim_sim       # A9: "< 0,80"
    return SIM if sim else (PARCIAL if v <= lim_parcial else NAO_)

def _cumpre_sim(v, direcao, lim_sim):
    """Verdadeiro se o valor atinge o limiar do 'Sim'. Exceção do protocolo: o teste A9 usa '< 0,80' (estrito), todos os outros usam '<=' ou '>='."""
    return v >= lim_sim if direcao == "maior" else (v < lim_sim if lim_sim == 0.80 else v <= lim_sim)

def _t(id_, nome, resposta, valor=None, anos=None, nota=""):
    """Cria o dicionário de um teste (id, nome, resposta Sim/Parcial/Não/Sem dados, valor mostrado, valores por ano e nota). É o formato que a parte qualitativa do Avaliador, o Crítico e o relatório leem."""
    return {"id": id_, "nome": nome, "resposta": resposta, "valor": valor, "anos": anos or {}, "nota": nota}

def _cagr(v0, v1, n):
    """Taxa de crescimento anual composta, em %. Só é definida com valores positivos e pelo menos um ano de intervalo."""
    if v0 is None or v1 is None or v0 <= 0 or v1 <= 0 or n <= 0: return None
    return 100 * ((v1 / v0) ** (1 / n) - 1)

# ─────────────────────────────── rácios anuais do Bloco A
def divida_lp(d, a):
    """Dívida de longo prazo não corrente ("Long-Term Debt" no mapa de dados da v4.27); reserva: dívida total."""
    x = _v(d, "divida_lp", a)
    return x if x is not None else _v(d, "divida_total", a)

def roe_corrigido(d, a):
    """ROE corrigido: resultado líquido a dividir pelos capitais próprios ajustados das ações próprias (recompras fazem o ROE normal subir sem o negócio melhorar)."""
    cp, ap, rl = _v(d, "capitais_proprios", a), _v(d, "acoes_proprias", a, True), _v(d, "resultado_liquido", a)
    if cp is None or rl is None: return None
    base = cp + abs(ap)
    return 100 * rl / base if base > 0 else None

def _racio(d, id_, a):
    """Calcula o rácio de um teste anual (A1 a A12) a partir das linhas das demonstrações; devolve None se faltar algum dado."""
    rec, lb, rl = _v(d, "receita", a), _v(d, "lucro_bruto", a), _v(d, "resultado_liquido", a)
    if id_ == "A1": return None if not rec or lb is None else 100 * lb / rec
    if id_ in ("A2", "A3", "A4"):
        x = _v(d, {"A2": "sga", "A3": "rd", "A4": "da"}[id_], a)
        return None if x is None or not lb or lb <= 0 else 100 * x / lb
    if id_ == "A5":
        ebit, juros = _v(d, "ebit", a), _v(d, "juros", a)
        if juros is None: juros = 0.0 if (_v(d, "divida_total", a) or 0) == 0 else None   # sem dívida, sem juros
        if juros is None or ebit is None: return None
        return float("inf") if ebit <= 0 else 100 * abs(juros) / ebit
    if id_ == "A6": return None if not rec or rl is None else 100 * rl / rec
    if id_ == "A8":
        div, cx = divida_lp(d, a), _v(d, "caixa", a, True)
        if div is None or rl is None: return None
        if cx >= div: return 0.0                                       # caixa líquida
        return float("inf") if rl <= 0 else div / rl
    if id_ == "A9":
        pas, cp, ap = _v(d, "passivo_total", a), _v(d, "capitais_proprios", a), _v(d, "acoes_proprias", a, True)
        if pas is None or cp is None: return None
        base = cp + abs(ap)
        return float("inf") if base <= 0 else pas / base
    if id_ == "A10":
        cp = _v(d, "capitais_proprios", a)
        if cp is None or rl is None: return None
        if cp > 0: return 100 * rl / cp                                # v4.27: ROE reportado (o corrigido é mostrado ao lado)
        return roe_corrigido(d, a)                                     # capitais próprios negativos: o reportado não tem sentido
    if id_ == "A12":
        cap = _v(d, "capex", a)
        if cap is None or rl is None: return None
        return float("inf") if rl <= 0 else 100 * abs(cap) / rl
    return None

def _nao_aplicavel(id_, modelo, setor, d):
    """Diz se um teste não faz sentido para este modelo de negócio ou setor (p. ex. margens num negócio de baixo custo M3, ou inventário num banco). Devolve o motivo ou None."""
    if modelo == "M3" and id_ in ("A1", "A6"): return "M3 (baixo custo): margens trocadas por volume"
    if setor in ("banco", "seguradora") and id_ in ("A1", "A2", "A3", "A4", "A5", "A6", "A8", "A9", "A12", "A14", "A15"):
        return f"não se aplica a {setor}s (Secção 6.2)"
    if id_ == "A3" and all(_val(d, "rd", a) is None for a in _anos(d)): return "sem linha própria de I&D (o custo está no SG&A, em A2)"
    return None

def _teste_anual(d, id_, modelo, setor):
    """Aplica um teste do Bloco A que se avalia ano a ano: calcula o rácio de cada ano, classifica cada ano em Sim/Parcial/Não 
    e dá a resposta final pela regra do protocolo (maioria dos anos)."""
    nome, direcao, lim_sim, lim_parcial = TESTES_POR_ANO[id_]
    m = _nao_aplicavel(id_, modelo, setor, d)
    if m: return _t(id_, nome, NA, nota=m)
    anos = {a: _racio(d, id_, a) for a in _anos_ok(d)}
    vals = [v for v in anos.values() if v is not None]
    if len(vals) < 3: return _t(id_, nome, SEM_DADOS, anos=anos)
    med = statistics.median(vals)
    resp = _resposta(med, direcao, lim_sim, lim_parcial); nota = ""
    cumpre = sum(1 for v in vals if _cumpre_sim(v, direcao, lim_sim))
    if resp == SIM and cumpre / len(vals) < CONSISTENCIA_MIN:
        resp = PARCIAL; nota = f"Regra de Consistência: limiar do Sim cumprido em {cumpre} de {len(vals)} anos (exige 70%)"
    if id_ == "A10":
        cor = [x for x in (roe_corrigido(d, a) for a in anos) if x is not None]
        if cor: nota = (nota + "; " if nota else "") + f"ROE corrigido (com ações próprias) mediano {_num(statistics.median(cor), 1)}%"
    return _t(id_, nome, resp, round(med, 2) if med != float("inf") else med, anos, nota)

# ─────────────────────────────── testes de série do Bloco A
def _a7(lpa):
    """A7: conta as quedas do LPA entre anos consecutivos. Sim = no máximo 1 queda em 9 variações; Parcial = até 3 em 9 
    (proporcional se a série for mais curta); qualquer prejuízo = Não. Precisa de pelo menos 5 anos."""
    serie = [(a, v) for a, v in sorted(lpa.items()) if v is not None]
    if len(serie) < 5: return _t("A7", "LPA consistente", SEM_DADOS)
    vals = [v for _, v in serie]; prej = any(v <= 0 for v in vals)
    var = len(vals) - 1; quedas = sum(1 for x, y in zip(vals, vals[1:]) if y < x)
    max_sim, max_parcial = int(var / 9), int(var / 3)            # 1 em 9 (0 em 4); 3 em 9 (1 em 4)
    if prej: resp = NAO_
    elif quedas <= max_sim: resp = SIM
    elif quedas <= max_parcial: resp = PARCIAL
    else: resp = NAO_
    return _t("A7", "LPA consistente (quedas nas variações anuais)", resp,
              f"{quedas} queda(s) em {var} variações" + (", com prejuízo" if prej else ", sem prejuízos"), dict(serie),
              f"Sim: no máximo {max_sim}; Parcial: até {max_parcial}")

def _a11(d, lpa, dpa):
    """A11: crescimento anual composto (CAGR) dos resultados transitados: Sim >= 7%, Parcial >= 0%. 
    Se as recompras os encolhem apesar de o lucro crescer, usa em alternativa o LPA retido (LPA - dividendo por ação)."""
    anos = _anos_ok(d)
    re_ = [(a, _v(d, "resultados_transitados", a)) for a in anos if _v(d, "resultados_transitados", a) is not None]
    rl = [(a, _v(d, "resultado_liquido", a)) for a in anos]
    nota = ""; cagr = None
    if len(re_) >= 4: cagr = _cagr(re_[0][1], re_[-1][1], re_[-1][0] - re_[0][0])
    lucro_cresce = len(rl) >= 4 and rl[0][1] and rl[-1][1] and rl[0][1] > 0 and rl[-1][1] > rl[0][1]
    if (cagr is None or cagr < 0) and lucro_cresce:
        ret = [(a, lpa[a] - (dpa.get(a) or 0)) for a in anos if lpa.get(a) is not None]
        if len(ret) >= 4:
            v0 = (ret[0][1] + ret[1][1]) / 2; v1 = (ret[-2][1] + ret[-1][1]) / 2
            cagr = _cagr(v0, v1, (ret[-1][0] + ret[-2][0]) / 2 - (ret[0][0] + ret[1][0]) / 2)
            nota = "recompras encolhem os resultados transitados: usado o LPA retido (LPA - DPA)"
    if cagr is None: return _t("A11", "Lucros retidos (CAGR)", SEM_DADOS, nota=nota)
    return _t("A11", "Lucros retidos (CAGR)", SIM if cagr >= 7 else (PARCIAL if cagr >= 0 else NAO_), round(cagr, 2), nota=nota)

def _a13(d):
    """A13 (detetor de mentiras): compara a taxa efetiva de imposto com a taxa legal da moeda (mediana >= 80% da legal) e o 
    imposto pago em caixa com o imposto contabilizado (>= 80%). Cumprir as duas = Sim, uma = Parcial."""
    moeda = (d.get("mercado") or {}).get("moeda") or d["empresa"].get("moeda") or "USD"
    legal_f = TAXA_LEGAL_IMPOSTO.get(moeda, TAXA_LEGAL_IMPOSTO["USD"])
    efe, leg, desp, pago, n_pago = [], [], 0.0, 0.0, 0
    for a in _anos_ok(d)[-5:]:
        imp, pt = _v(d, "imposto", a), _v(d, "resultado_antes_impostos", a)
        if imp is not None and pt and pt > 0: efe.append(100 * imp / pt); leg.append(legal_f(int(a)))
        ip = _v(d, "imposto_pago", a)
        if ip is not None and imp is not None: pago += abs(ip); desp += imp; n_pago += 1
    if len(efe) < 3: return _t("A13", "Imposto pago (detetor de mentiras)", SEM_DADOS)
    c1 = statistics.median(efe) >= 0.8 * statistics.median(leg)
    c2 = (pago >= 0.8 * desp) if n_pago >= 3 and desp > 0 else None
    if c2 is None:
        resp = PARCIAL if c1 else NAO_; nota = "imposto pago em caixa sem dados: só a taxa efetiva foi avaliada"
    else:
        resp = SIM if (c1 and c2) else (PARCIAL if (c1 or c2) else NAO_); nota = ""
    val = f"taxa efetiva mediana {_num(statistics.median(efe), 1)}% (legal {_num(statistics.median(leg), 0)}%)"
    if c2 is not None: val += f"; pago / contabilizado {_num(100 * pago / desp, 0)}%"
    return _t("A13", "Imposto pago (detetor de mentiras)", resp, val,
              nota=(nota + "; " if nota else "") + "créditos fiscais legítimos documentados não contam contra")

def _a14(d):
    """A14: compara o crescimento do inventário com o da receita (CAGR) e conta episódios de inventário que sobe mais de 25% e depois cai mais de 15%. Sim = diferença <= 2 pontos e nenhum episódio. Não se aplica se o inventário for menos de 2% da receita."""
    anos = _anos_ok(d)
    inv = [(a, _v(d, "inventario", a)) for a in anos if _v(d, "inventario", a) is not None]
    rec = {a: _v(d, "receita", a) for a in anos}
    if len(inv) < 4 or statistics.median([v / rec[a] for a, v in inv if rec.get(a)]) < 0.02:
        return _t("A14", "Inventário", NA, nota="sem inventário relevante")
    n = inv[-1][0] - inv[0][0]
    ci, cr = _cagr(inv[0][1], inv[-1][1], n), _cagr(rec[inv[0][0]], rec[inv[-1][0]], n)
    if ci is None or cr is None: return _t("A14", "Inventário", SEM_DADOS)
    vals = [v for _, v in inv]
    ep = sum(1 for i in range(1, len(vals) - 1) if vals[i] > 1.25 * vals[i - 1] and vals[i + 1] < 0.85 * vals[i])
    dif = ci - cr
    resp = SIM if (dif <= 2 and ep == 0) else (PARCIAL if (dif <= 5 and ep <= 1) else NAO_)
    return _t("A14", "Inventário", resp, f"CAGR inventário {_num(ci, 1)}% vs receita {_num(cr, 1)}%; {ep} episódio(s)")

def _a15(d):
    """A15: soma do fluxo de caixa livre (FCO - capex) a dividir pela soma de dividendos e recompras. Sim >= 1,0; Parcial >= 0,8. Precisa de 4 anos ou mais."""
    fcf = dist = 0.0; n = 0
    for a in _anos_ok(d):
        fco, cap = _v(d, "fco", a), _v(d, "capex", a)
        if fco is None or cap is None: continue
        fcf += fco - abs(cap); dist += (_v(d, "dividendos_pagos", a, True) or 0) + (_v(d, "recompras", a, True) or 0); n += 1
    if n < 4: return _t("A15", "Autofinanciamento das distribuições", SEM_DADOS)
    if dist <= 0: return _t("A15", "Autofinanciamento das distribuições", NA, nota="sem dividendos nem recompras")
    r = fcf / dist
    return _t("A15", "Autofinanciamento das distribuições", SIM if r >= 1.0 else (PARCIAL if r >= 0.8 else NAO_), round(r, 2))

# ─────────────────────────────── Sinais de Balanço (sem resposta própria)
def sinais_balanco(d):
    """Os seis Sinais de Balanço SB1 a SB6 (contas a receber a subir, ROA muito alto, dívida de curto prazo maior que a de longo, dívida a vencer elevada, caixa de origem errada, alavancagem). Não têm resposta Sim/Não própria: o Bloco C usa o número de sinais presentes no Teste da Franquia (C4)."""
    anos = _anos_ok(d); out = []
    def sinal(id_, desc, presente, det): out.append({"id": id_, "descricao": desc, "presente": bool(presente), "detalhe": det})
    cr = [(a, _v(d, "contas_receber", a) / _v(d, "receita", a)) for a in anos[-4:]
          if _v(d, "contas_receber", a) is not None and _v(d, "receita", a)]
    sinal("SB1", "Contas a receber / receita a subir 3 anos seguidos", len(cr) == 4 and all(y > x for (_, x), (_, y) in zip(cr, cr[1:])),
          " -> ".join(f"{a}: {_num(100 * v, 1)}%" for a, v in cr) if cr else "sem dados")
    roa = [100 * _v(d, "resultado_liquido", a) / _v(d, "ativos_totais", a) for a in anos[-3:]
           if _v(d, "ativos_totais", a) and _v(d, "resultado_liquido", a) is not None]
    sinal("SB2", "ROA muito alto (> 25%) com ativos pequenos: barreira de entrada fraca", roa and statistics.median(roa) > 25,
          f"ROA mediano {_num(statistics.median(roa), 1)}%" if roa else "sem dados")
    ult = anos[-1] if anos else None
    dcp, dlp = (_v(d, "divida_curto_prazo", ult), _v(d, "divida_total", ult)) if ult else (None, None)
    sinal("SB3", "Dívida de curto prazo maior do que a de longo prazo", dcp is not None and dlp is not None and dcp > dlp,
          f"curto prazo {_num((dcp or 0) / 1e6, 0)} M vs longo prazo {_num((dlp or 0) / 1e6, 0)} M" if dcp is not None else "sem dados")
    lpc = _v(d, "divida_lp_corrente", ult) if ult else None
    base = ((_v(d, "caixa", ult, True) or 0) + (_v(d, "fco", ult, True) or 0)) if ult else 0
    sinal("SB4", "Dívida de longo prazo a vencer elevada face à caixa e ao FCO (calibração: > 50%)",
          lpc is not None and base > 0 and lpc > 0.5 * base,
          f"a vencer {_num(lpc / 1e6, 0)} M vs caixa + FCO {_num(base / 1e6, 0)} M" if lpc is not None else "sem dados")
    errados = []
    for a0, a1 in zip(anos[-6:], anos[-5:]):
        # a caixa subiu mais do que o negócio reteve (FCF - dividendos - recompras) e a diferença veio de emissões
        c0, c1, fco, cap = _v(d, "caixa", a0), _v(d, "caixa", a1), _v(d, "fco", a1), _v(d, "capex", a1)
        if None in (c0, c1, fco, cap) or c1 <= c0: continue
        retido = fco - abs(cap) - (_v(d, "dividendos_pagos", a1, True) or 0) - (_v(d, "recompras", a1, True) or 0)
        emis = ((_v(d, "emissao_divida", a1, True) or 0) - (_v(d, "reembolso_divida", a1, True) or 0) + (_v(d, "emissao_acoes", a1, True) or 0))
        falta = (c1 - c0) - max(retido, 0)
        if falta > 0 and emis >= falta: errados.append(str(a1))
    sinal("SB5", "Caixa de origem errada: subiu à custa de emissão de dívida ou de ações", errados,
          ("anos: " + ", ".join(errados)) if errados else "não detetado")
    rep, cor = [], []
    for a in anos:
        cp, rl = _v(d, "capitais_proprios", a), _v(d, "resultado_liquido", a)
        if cp and cp > 0 and rl is not None:
            rep.append(100 * rl / cp); c = roe_corrigido(d, a)
            if c: cor.append(c)
    alav = rep and cor and statistics.median(cor) > 0 and statistics.median(rep) > 1.25 * statistics.median(cor)
    sinal("SB6", "Alavancagem: ROE reportado mais de 1,25x o corrigido (calibração)", alav,
          f"ROE reportado {_num(statistics.median(rep), 1)}% vs corrigido {_num(statistics.median(cor), 1)}%" if rep and cor else "sem dados")
    return out

def explicar_sinais(d, sinais, r):
    """O protocolo diz que cada Sinal de Balanço presente é registado E explicado, e que só dois ou mais SEM explicação impedem a Franquia.
    Aqui cada sinal presente tenta ser explicado com regras gerais sobre os números das demonstrações (nunca por nome de empresa);
    sem regra que o explique, fica por explicar. Limiares: calibração do protocolo. r = respostas dos testes A (A8, A9, A15)."""
    anos = _anos_ok(d)
    def exp(s, ok, texto): s["explicado"], s["explicacao"] = bool(ok), (texto if ok else "")
    for s in sinais:
        s["explicado"], s["explicacao"] = False, ""
        if not s["presente"]: continue
        if s["id"] == "SB1":       # o rácio sobe, mas pouco: as contas a receber acompanham a receita
            cr = [_v(d, "contas_receber", a) / _v(d, "receita", a) for a in anos[-4:] if _v(d, "contas_receber", a) is not None and _v(d, "receita", a)]
            if len(cr) == 4: exp(s, 100 * (cr[-1] - cr[0]) < 1.0, f"o rácio sobe só {_num(100 * (cr[-1] - cr[0]), 1)} p.p. em 3 anos (menos de 1 p.p.)")
        elif s["id"] == "SB3":     # a dívida de curto prazo está coberta pela caixa
            ult = anos[-1] if anos else None; dcp, cx = _v(d, "divida_curto_prazo", ult), _v(d, "caixa", ult)
            if dcp is not None and cx is not None: exp(s, cx >= dcp, f"a caixa ({_num(cx / 1e6, 0)} M) cobre a dívida de curto prazo ({_num(dcp / 1e6, 0)} M)")
        elif s["id"] == "SB5":     # a caixa subiu com dinheiro de fora, mas é pouco face ao que o negócio gera (calibração: até 25% do FCO desse ano)
            anos_s = [x for x in s["detalhe"].replace("anos:", "").replace(" ", "").split(",") if x.isdigit()]
            pesos = []
            for x in anos_s:
                c0, c1, fco = _v(d, "caixa", int(x) - 1), _v(d, "caixa", x), _v(d, "fco", x)
                if None in (c0, c1, fco) or fco <= 0: pesos = []; break
                retido = fco - abs(_v(d, "capex", x) or 0) - (_v(d, "dividendos_pagos", x, True) or 0) - (_v(d, "recompras", x, True) or 0)
                pesos.append((c1 - c0 - max(retido, 0)) / fco)
            if pesos and max(pesos) <= 0.25:
                exp(s, True, f"o dinheiro de fora que fez subir a caixa é no máximo {_num(100 * max(pesos), 0)}% do FCO desse ano (limite 25%): financiamento marginal face à geração própria")
        elif s["id"] == "SB6":     # o ROE reportado é inflacionado pelas ações próprias (recompras), não pela dívida
            if all(r.get(k) in (SIM, PARCIAL) for k in ("A8", "A9", "A15")):
                exp(s, True, f"a diferença vem das ações próprias (recompras), não da dívida: A8 = {r['A8']}, A9 = {r['A9']}, A15 = {r['A15']}")
    return sinais

# ─────────────────────────────── testes substitutos para bancos (Secção 6.2, calibração do protocolo)
def _teste_banco(d, id_, nome, f_racio, direcao, lim_sim, lim_parcial, reserva=None):
    """Teste anual específico de bancos (AB1, AB2): igual ao _teste_anual, mas com rácios bancários e, se faltarem dados da SEC, usa os da FDIC."""
    anos = {a: f_racio(a) for a in _anos_ok(d)}
    if reserva:                                        # reserva: rácio da FDIC para os anos sem dados da SEC
        for a, v in reserva.items():
            if anos.get(a) is None and v is not None: anos[a] = v
    vals = [v for v in anos.values() if v is not None]
    if len(vals) < 3: return _t(id_, nome, SEM_DADOS, anos=anos)
    med = statistics.median(vals); resp = _resposta(med, direcao, lim_sim, lim_parcial); nota = ""
    cumpre = sum(1 for v in vals if _cumpre_sim(v, direcao, lim_sim))
    if resp == SIM and cumpre / len(vals) < CONSISTENCIA_MIN:
        resp = PARCIAL; nota = f"Regra de Consistência: limiar do Sim cumprido em {cumpre} de {len(vals)} anos"
    return _t(id_, nome, resp, round(med, 2), anos, nota)

def _ab1_roa(d, a):
    anos = _anos_ok(d); i = anos.index(a)
    rl, at = _v(d, "resultado_liquido", a), _v(d, "ativos_totais", a)
    at0 = _v(d, "ativos_totais", anos[i - 1]) if i > 0 else None
    if rl is None or not at: return None
    return 100 * rl / ((at + at0) / 2 if at0 else at)

def _ab2_eficiencia(d, a):
    c, nii, nj = _v(d, "custos_nao_juros", a), _v(d, "margem_financeira", a), _v(d, "receitas_nao_juros", a)
    if c is None or nii is None or nj is None or nii + nj <= 0: return None
    return 100 * c / (nii + nj)

def testes_banco(d):
    """Testes AB1 (ROA) e AB2 (eficiência) que substituem os rácios industriais quando a empresa é um banco."""
    fd = (d.get("banco") or {}).get("por_ano") or {}
    return [_teste_banco(d, "AB1", "ROA (lucro / ativo médio, %)", lambda a: _ab1_roa(d, a), "maior", 1.0, 0.7,
                         {a: x.get("roa") for a, x in fd.items()}),
            _teste_banco(d, "AB2", "Rácio de eficiência (custos / proveitos, %)", lambda a: _ab2_eficiencia(d, a), "menor", 55.0, 65.0,
                         {a: x.get("eficiencia") for a, x in fd.items()})]

# ─────────────────────────────── Bloco A
def bloco_a(d, lpa, dpa, modelo="M1", setor="padrao"):
    """Bloco A (A1 a A15): qualidade financeira medida pelos números. Devolve a lista de testes; nos bancos acrescenta os testes AB."""
    t = [_teste_anual(d, i, modelo, setor) for i in ("A1", "A2", "A3", "A4", "A5", "A6")]
    t.append(_a7(lpa))
    t += [_teste_anual(d, i, modelo, setor) for i in ("A8", "A9", "A10")]
    t.append(_a11(d, lpa, dpa))
    t.append(_teste_anual(d, "A12", modelo, setor))
    t.append(_a13(d))
    t.append(_a14(d) if setor not in ("banco", "seguradora") else _t("A14", "Inventário", NA, nota=f"não se aplica a {setor}s"))
    t.append(_a15(d) if setor not in ("banco", "seguradora") else _t("A15", "Autofinanciamento", NA, nota=f"não se aplica a {setor}s"))
    if setor == "banco": t += testes_banco(d)
    return t

# ─────────────────────────────── Bloco B
def bloco_b(d, lpa, dpa, a15, a13, analise):
    """Bloco B (B1 a B5): o que a gestão fez com o dinheiro dos acionistas. B1 dólar retido e B2 rendimento dos lucros retidos; B3 recompras e número de ações; B4 integridade (mudança de auditor, reexpressões, insiders); B5 aquisições e imparidades de goodwill."""
    anos = [a for a in _anos_ok(d) if lpa.get(a) is not None]; mk = d.get("mercado") or {}; t = []
    if len(anos) >= 5:
        a0, resto = anos[0], anos[1:]
        retido = sum(lpa[a] - (dpa.get(a) or 0) for a in resto)
        pl = mk.get("pl_medio_10a") or d["pontuais"].get("pl_medio_historico")
        if retido > 0 and pl:
            r = pl * (lpa[anos[-1]] - lpa[a0]) / retido         # preço normalizado = LPA x P/L médio histórico (v4.27)
            t.append(_t("B1", "Dólar retido (preço normalizado)", SIM if r >= 1.0 else (PARCIAL if r >= 0.7 else NAO_),
                        f"{_num(r, 2)} (P/L médio {_num(pl, 1)}; LPA {a0} {_num(lpa[a0], 2)} -> {anos[-1]} {_num(lpa[anos[-1]], 2)}; "
                        f"LPA retido {_num(retido, 2)})"))
        else: t.append(_t("B1", "Dólar retido (preço normalizado)", SEM_DADOS, nota="sem P/L médio ou LPA retido não positivo"))
        if retido > 0:
            r = 100 * (lpa[anos[-1]] - lpa[a0]) / retido
            t.append(_t("B2", "Rendimento dos lucros retidos", SIM if r >= 15 else (PARCIAL if r >= 10 else NAO_), f"{_num(r, 1)}%",
                        nota="limites: calibração do protocolo"))
        else: t.append(_t("B2", "Rendimento dos lucros retidos", SEM_DADOS))
    else:
        t += [_t("B1", "Dólar retido (preço normalizado)", SEM_DADOS), _t("B2", "Rendimento dos lucros retidos", SEM_DADOS)]
    todos = _anos_ok(d)
    acs = [(a, _v(d, "acoes_diluidas", a)) for a in todos if _v(d, "acoes_diluidas", a)]
    if len(acs) >= 4:
        taxa = 100 * ((acs[-1][1] / acs[0][1]) ** (1 / (acs[-1][0] - acs[0][0])) - 1)
        pref = _v(d, "preferenciais", todos[-1], True) or 0; cp = _v(d, "capitais_proprios", todos[-1]) or 0
        pref_rel = cp > 0 and pref > 0.05 * cp                 # calibração: "relevantes" = mais de 5% dos capitais próprios
        pl_fim = mk.get("pl_fim_ano") or {}; caras = False
        if pl_fim:
            media = statistics.mean(pl_fim.values()); tot = cara = 0.0
            for a in todos:
                rc = _v(d, "recompras", a, True) or 0; tot += rc
                if pl_fim.get(a) and pl_fim[a] > 1.25 * media: cara += rc
            caras = tot > 0 and cara > 0.5 * tot
        if taxa > 1 or pref_rel: resp = NAO_
        elif taxa <= -1 and a15 in (SIM, NA) and not caras: resp = SIM
        else: resp = PARCIAL
        t.append(_t("B3", "Recompras e estrutura de capital", resp, f"ações {_num(taxa, 2)}%/ano" + ("; preferenciais relevantes" if pref_rel else "")
                    + ("; recompras concentradas em anos de P/L alto (caras)" if caras else "")))
    else: t.append(_t("B3", "Recompras e estrutura de capital", SEM_DADOS))
    gov = d.get("governanca") or {}
    sinais = ([f"mudança de auditor ({', '.join(gov['auditor'])})"] if gov.get("auditor") else []) + \
             ([f"reexpressão de contas ({', '.join(gov['reexpressao'])})"] if gov.get("reexpressao") else [])
    ins = d.get("insiders_pct"); donos = ins is not None and ins >= 1.0
    erros = (analise or {}).get("b4_evidencia_verificada")
    if sinais or a13 == NAO_: resp = NAO_
    elif a13 == SIM and erros and donos: resp = SIM
    else: resp = PARCIAL
    t.append(_t("B4", "Integridade, franqueza e mentalidade de dono", resp,
                "; ".join(sinais) if sinais else ("A13 = Não" if a13 == NAO_ else ("sem sinais de alerta na SEC (8-K 4.01/4.02)"
                if d.get("governanca") is not None else "sinais de governança não verificáveis (empresa sem 8-K na SEC)")),
                nota=f"insiders com {_num(ins, 2) + '% das ações (Yahoo; inclui acionistas com mais de 10%, não só gestores)' if ins is not None else 'participação desconhecida'}"
                     + ("" if erros else "; sem evidência verificada de admitir erros") + "; remuneração e Form 4 não verificados automaticamente"))
    gw = [v for v in (_v(d, "goodwill", a) for a in todos) if v]
    imp = sum(_v(d, "imparidades_goodwill", a, True) or 0 for a in todos)
    rec_ult = _v(d, "receita", todos[-1]) if todos else None
    n_aq = sum(1 for a in todos if (_v(d, "aquisicoes", a, True) or 0) > 0.01 * (rec_ult or 1e18))
    if gw and imp > 0.10 * max(gw): resp, det = NAO_, f"imparidades de goodwill {_num(imp / 1e6, 0)} M (> 10% do goodwill)"
    elif n_aq >= 4: resp, det = PARCIAL, f"aquisições relevantes em {n_aq} anos, sem imparidades materiais"
    else: resp, det = SIM, f"aquisições relevantes em {n_aq} ano(s); imparidades {_num(imp / 1e6, 0)} M"
    t.append(_t("B5", "Aquisições e imperativo institucional", resp, det, nota="'frequentes' = 4 ou mais anos com aquisições acima de 1% da receita (calibração)"))
    return t

# ─────────────────────────────── Bloco C (respostas verificadas do modelo + regras)
def bloco_c(prop, sinais, margem_bruta_cai_3):
    """Bloco C (C1 a C4): a parte qualitativa (modelo de negócio, produto estável, poder de preço, Teste da Franquia). A parte qualitativa do Avaliador propõe as respostas; aqui aplicam-se as regras do protocolo, p. ex. patentes forçam C2 = Não."""
    modelo = prop.get("modelo"); pat = bool(prop.get("dependente_patentes"))
    c1 = SIM if modelo in ("M1", "M2", "M3") and not pat else PARCIAL
    c2 = NAO_ if pat else prop.get("c2", PARCIAL)
    c3, n3 = prop.get("c3_verificado", NAO_), prop.get("c3_nota", "")
    if margem_bruta_cai_3: c3, n3 = NAO_, "margem bruta a cair 3 anos seguidos"
    fr = prop.get("franquia") or {}
    n_sim = sum(1 for k in FRANQUIA_PERGUNTAS if (fr.get(k) or {}).get("resposta") == "sim")
    alertas = sum(1 for s in sinais if s["presente"] and not s.get("explicado"))
    if n_sim == 4 and c3 == SIM and alertas < 2: c4, nota4 = SIM, "Franquia confirmada (4 sim, C3 = Sim, menos de 2 Sinais de Balanço por explicar)"
    elif n_sim == 4: c4, nota4 = PARCIAL, "4 sim, mas " + ("C3 não é Sim" if c3 != SIM else "2 ou mais Sinais de Balanço por explicar") + ": franquia não confirmada"
    elif n_sim == 3: c4, nota4 = PARCIAL, "3 sim em 4"
    else: c4, nota4 = NAO_, f"{n_sim} sim em 4"
    nomes = {"M1": "produto exclusivo", "M2": "serviço exclusivo", "M3": "baixo custo"}
    return [_t("C1", "Modelo de negócio Buffett", c1, f"{modelo} ({nomes.get(modelo, 'híbrido ou parcial')})" + ("; dependente de patentes" if pat else "")),
            _t("C2", "Produto estável, à prova de idiota", c2, prop.get("c2_porque", ""), nota="patentes: C2 = Não" if pat else ""),
            _t("C3", "Poder de preço (evidência concreta e datada)", c3, prop.get("c3_evidencia") or "sem evidência verificada", nota=n3),
            _t("C4", "Teste da Franquia (carta de 1991)", c4, f"{n_sim} sim em 4", nota=nota4)]

# ─────────────────────────────── os 10 Portões
def portoes(testes, setor, d):
    """Os 10 Portões: cada portão agrupa testes dos blocos A, B e C e só passa se todos tiverem resposta aceite (PASSA). Bancos e seguradoras têm portões adaptados (P3, P4, P6, P8)."""
    por_id = {t["id"]: t for t in testes}; out = []
    for pid, (pergunta, ids) in PORTOES.items():
        if setor == "banco" and pid in ("P3", "P8") and (d.get("banco") or {}).get("por_ano"):
            fd = d["banco"]["por_ano"]; anos_fd = sorted(fd); ult = fd[anos_fd[-1]]
            if pid == "P3":
                cet1, npl = ult.get("cet1"), ult.get("npl")
                passa = cet1 is not None and npl is not None and cet1 >= 12.0 and npl <= 3.0
                det = f"CET1 {_num(cet1, 2)}% (mínimo 12%) e NPL {_num(npl, 2)}% (máximo 3%) em {anos_fd[-1]}, {d['banco']['banco']}"
            else:
                nims = [(a, fd[a].get("nim")) for a in anos_fd if fd[a].get("nim") is not None]
                ult4 = [v for _, v in nims[-4:]]
                caiu3 = len(ult4) == 4 and all(y < x for x, y in zip(ult4, ult4[1:]))
                passa = bool(nims) and not (caiu3 and ult4[-1] < 1.0)
                det = "NIM " + " -> ".join(f"{a}: {_num(v, 2)}%" for a, v in nims[-4:]) + (" (em queda 3 anos e abaixo de 1%)" if not passa and nims else "")
            out.append({"id": pid, "pergunta": pergunta, "passa": passa, "detalhe": det}); continue
        if setor in ("banco", "seguradora") and pid in ("P3", "P8"):
            falta = {"banco": {"P3": "CET1 >= 12% e NPL <= 3%", "P8": "NIM sem queda 3 anos para < 1,0%"},
                     "seguradora": {"P3": "solvência >= 150%", "P8": "combined ratio (AS1)"}}[setor][pid]
            out.append({"id": pid, "pergunta": pergunta, "passa": False, "detalhe": f"exige {falta}: sem dados nas fontes gratuitas"})
            continue
        if setor in ("banco", "seguradora") and pid == "P6":
            out.append({"id": pid, "pergunta": pergunta, "passa": True, "detalhe": "não aplicável a bancos e seguradoras"}); continue
        resp = [(i, por_id[i]["resposta"]) for i in ids if i in por_id]
        passa = bool(resp) and all(r in PASSA for _, r in resp)
        det = " e ".join(f"{i} = {r}" for i, r in resp)
        if passa and setor in ("banco", "seguradora") and pid == "P4":
            ke = max(d["pontuais"].get("taxa_10_anos") or 0, 7.0, KE_MINIMO)
            roes = [100 * _v(d, "resultado_liquido", a) / _v(d, "capitais_proprios", a) for a in _anos_ok(d)[-5:]
                    if _v(d, "capitais_proprios", a) and _v(d, "capitais_proprios", a) > 0]
            ok = sum(1 for x in roes if x >= ke) >= 3
            passa = passa and ok; det += f"; ROE >= Ke ({_num(ke, 1)}%) em {sum(1 for x in roes if x >= ke)} de {len(roes)} anos"
        out.append({"id": pid, "pergunta": pergunta, "passa": passa, "detalhe": det})
    return out