"""Avaliação e decisão pelo Protocolo v4.27 (Secções 8 e 9):

8.0  r = taxa do Estado a 10 anos, sem prémio de risco, piso de 7%. Lucros base sem itens extraordinários.
8.1  Etapa A — Valor Intrínseco por Owner Earnings = NI + D&A - capex de MANUTENÇÃO - SBC + variação do fundo de maneio;
     OE0 = média por ação de 5 anos; g = mínimo (CAGR LPA ; CAGR lucro ; ROE x retenção ; 15%), CONSTANTE nos anos 1-10;
     g terminal = mínimo (2,5% ; g/2).
8.2  Etapa B — Equity Bond: EB1 rendimento inicial e Valor-Obrigação; EB2 TACE pelos Métodos I (LPA) e II (ROE), a mais
     baixa; EB3 P_EB = preço máximo para 15% ao ano.
8.3  PMC = mínimo (VI ; P_EB ; Valor-Obrigação).
9    Compra = Triagem + Círculo + Setor + 10 Portões + 4 condições de preço. Tamanho: 15% com Franquia e TACE >= 20%; senão 10%.
"""
import statistics
from config import (ANOS_PROJECAO, CAIXA_V, COMPRAR_V, G_TERMINAL_MAX, G_TETO, PE_ALVO_MAX, PE_NEUTRO, PL_MAXIMO,
                    REJEITAR_V, TACE_ALTA_CONVICCAO, TACE_MINIMA, TAXA_DESCONTO_MIN)
from nucleo.metricas import _anos, _extraordinarios, _val
from nucleo.util import _num


def _taxa_desconto(taxa10):
    """Taxa de desconto r = a taxa do Estado a 10 anos, nunca abaixo do piso do protocolo (TAXA_DESCONTO_MIN)."""
    return round(max(taxa10 or 0.0, TAXA_DESCONTO_MIN), 2)

def _v(d, c, a, zero=False):
    """Valor de uma linha das demonstrações num ano (None se faltar; com zero=True um valor em falta conta como 0)."""
    x = _val(d, c, a)
    return 0.0 if (x is None and zero) else x

def _anos_ok(d):
    """Anos em que a extração dos dados é considerada utilizável (ordenados)."""
    return [a for a in _anos(d) if _val(d, "receita", a) is not None and _val(d, "resultado_liquido", a) is not None]

def lucro_base(d, a):
    """Lucro líquido sem itens extraordinários (Secção 8.0): ajuste por EBT sem itens não usuais quando difere mais de 10%;
    sem esse dado, o resultado das operações continuadas (exclui operações descontinuadas)."""
    x, cont = _v(d, "resultado_liquido", a), _v(d, "rl_continuadas", a)
    pt, ebt = _v(d, "resultado_antes_impostos", a), _v(d, "ebt_sem_extra", a)
    if x is None: return None, None
    if pt and ebt is not None and pt > 0 and abs(pt - ebt) > 0.10 * abs(pt):
        return x * ebt / pt, f"{a}: lucro ajustado por itens extraordinários (x{_num(ebt / pt, 2)})"
    if ebt is None and cont is not None and x and abs(x - cont) > 0.10 * abs(x):
        return cont, f"{a}: lucro das operações continuadas (exclui operações descontinuadas)"
    return x, None

def lpa_ajustado(d):
    """LPA de cada ano com lucros base; anos anómalos sem dados de itens extraordinários ficam assinalados (calibração)."""
    lpa, rl, notas = {}, {}, []
    for a in _anos_ok(d):
        x, nota = lucro_base(d, a); ac = _v(d, "acoes_diluidas", a)
        if x is None: continue
        rl[a] = x
        if nota: notas.append(nota)
        if ac: lpa[a] = x / ac
    # depois do ajuste por itens antes de impostos, um ano ainda anómalo face aos vizinhos é um choque que o ajuste não apanha
    # (ex.: ganho ou perda fiscal extraordinária): fica fora das médias e dos extremos do CAGR (calibração do sistema)
    ext = _extraordinarios(lpa) if len(lpa) >= 4 else set()
    for a in sorted(ext): notas.append(f"{a}: LPA anómalo face aos anos vizinhos mesmo depois do ajuste (ex.: choque fiscal); fora das médias (calibração)")
    return lpa, rl, ext, notas

def dpa_por_ano(d):
    """Dividendo por ação de cada ano: o valor reportado ou, se faltar, dividendos pagos a dividir pelas ações diluídas."""
    out = {}
    for a in _anos_ok(d):
        x = _v(d, "dividendo_por_acao", a)
        if x is None and _v(d, "dividendos_pagos", a) is not None and _v(d, "acoes_diluidas", a):
            x = _v(d, "dividendos_pagos", a) / _v(d, "acoes_diluidas", a)
        out[a] = x
    return out

def _cagr_extremos(vals: dict, excluir=frozenset()):
    """Crescimento anual composto entre o primeiro e o último ano da série (precisa de 3 anos ou mais; anos extraordinários podem ser excluídos). Devolve a taxa e uma nota."""
    pts = [(a, v) for a, v in sorted(vals.items()) if v is not None and a not in excluir]
    if len(pts) < 3: return None, "menos de 3 anos"
    (a0, v0), (a1, v1) = pts[0], pts[-1]
    if v0 <= 0 or v1 <= 0: return None, f"valor não positivo em {a0 if v0 <= 0 else a1}"
    return 100 * ((v1 / v0) ** (1 / (a1 - a0)) - 1), f"{a0} -> {a1}"

def _roe_medio_e_validade(d):
    """Devolve (ROE médio, válido?, nota). A série é inválida se algum ano tiver capitais próprios não positivos ou se o ROE reportado for mais de 1,25x o corrigido (recompras a distorcer)."""
    rep, cor = [], []
    for a in _anos_ok(d):
        cp, rl, ap = _v(d, "capitais_proprios", a), _v(d, "resultado_liquido", a), _v(d, "acoes_proprias", a, True)
        if cp is None or cp <= 0 or rl is None: return None, False, "capitais próprios não positivos em algum ano"
        rep.append(100 * rl / cp); cor.append(100 * rl / (cp + abs(ap)))
    if len(rep) < 3: return None, False, "sem dados"
    valido = statistics.median(rep) <= 1.25 * statistics.median(cor)
    return statistics.mean(rep), valido, ("" if valido else "ROE reportado acima de 1,25x o corrigido (distorcido por recompras)")

def owner_earnings(d, setor="padrao"):
    """Bancos e seguradoras (Secção 8.1): OE = lucro líquido por ação. Restantes: ver abaixo."""
    if setor in ("banco", "seguradora"):
        out = {a: _v(d, "resultado_liquido", a) / _v(d, "acoes_diluidas", a) for a in _anos_ok(d)
               if _v(d, "resultado_liquido", a) is not None and _v(d, "acoes_diluidas", a)}
        return out, [], {}
    return _owner_earnings_empresa(d)

def _owner_earnings_empresa(d):
    """OE por ação (carta de 1986; v4.27): só se desconta o capex de MANUTENÇÃO. Sem separação na empresa:
    capex <= depreciação -> capex total; capex > depreciação -> depreciação, mas só se a receita cresceu nesse ano."""
    out, notas, crescimento = {}, [], {}
    anos = _anos_ok(d)
    for i, a in enumerate(anos):
        rl, da, cap, ac = _v(d, "resultado_liquido", a), _v(d, "da", a), _v(d, "capex", a), _v(d, "acoes_diluidas", a)
        if None in (rl, da, cap) or not ac: continue
        cap = abs(cap); rec0 = _v(d, "receita", anos[i - 1]) if i > 0 else None; rec1 = _v(d, "receita", a)
        if cap > da and rec0 is not None and rec1 is not None and rec1 > rec0:
            cap_m = da; crescimento[a] = cap - da
        else: cap_m = cap
        sbc, wc = _v(d, "sbc", a), _v(d, "var_fundo_maneio", a)
        if sbc is None: notas.append(f"{a}: SBC sem dados")
        if wc is None: notas.append(f"{a}: variação do fundo de maneio sem dados")
        out[a] = (rl + da - cap_m - (sbc or 0) + (wc or 0)) / ac
    return out, notas, crescimento

def avaliar(d, alvo_pct=20.0, setor="padrao"):
    """Valorização (Passos 5 e 6 do protocolo): valor intrínseco por desconto de Owner Earnings, rendimento inicial, TACE a 10 anos nos dois métodos (a mais baixa conta), escada de preços e Preço Máximo de Compra (PMC = mínimo entre VI, P_EB e Valor-Obrigação). Tudo em código determinista; o modelo de linguagem não calcula."""
    notas = []
    preco = d["pontuais"].get("preco_atual"); taxa10 = d["pontuais"].get("taxa_10_anos")
    r = _taxa_desconto(taxa10)
    if taxa10 is not None and taxa10 < TAXA_DESCONTO_MIN: notas.append(f"taxa a 10 anos {_num(taxa10, 2)}% abaixo do piso: r = 7%")
    lpa, rl, ext, n_lpa = lpa_ajustado(d); notas += n_lpa
    g_i, det_i = _cagr_extremos(lpa, ext)
    g_ii, det_ii = _cagr_extremos(rl, ext)
    roe_m, roe_ok, det_roe = _roe_medio_e_validade(d)
    payout = statistics.mean([min(max((dpa_por_ano(d).get(a) or 0) / l, 0.0), 1.0) for a, l in lpa.items() if l and l > 0] or [0.0])
    g_iii = roe_m * (1 - payout) if (roe_m is not None and roe_ok) else None
    cand = {"(i) CAGR do LPA": g_i, "(ii) CAGR do lucro líquido": g_ii, "(iii) ROE x (1 - payout)": g_iii, "(iv) teto": G_TETO}
    validos = [v for v in cand.values() if v is not None]
    g = max(0.0, min(validos)) if validos else 0.0
    g_term = min(G_TERMINAL_MAX, g / 2)
    # Etapa A
    oe, n_oe, cres = owner_earnings(d, setor)
    if setor in ("banco", "seguradora"): notas.append(f"{setor}: Owner Earnings = lucro líquido por ação (Secção 8.1)")
    for chave in ("SBC sem dados", "variação do fundo de maneio sem dados"):
        an = [x.split(":")[0] for x in n_oe if chave in x]
        if an: notas.append(f"{chave} em {an[0]}" + (f"–{an[-1]}" if len(an) > 1 else "") + (" (não deduzida)" if chave.startswith("SBC") else " (considerada zero)"))
    if cres: notas.append("capex de crescimento separado (capex acima da depreciação em anos de receita a crescer): "
                          + "; ".join(f"{a}: {_num(v / 1e6, 0)} M" for a, v in sorted(cres.items())[-5:]))
    oe_ult = [v for _, v in sorted(oe.items())][-5:]
    oe0 = statistics.mean(oe_ult) if oe_ult else None
    vi = None
    if oe0 and oe0 > 0:
        gg, gt, rr = g / 100, g_term / 100, r / 100
        pv, fl = 0.0, oe0
        for t in range(1, ANOS_PROJECAO + 1):
            fl *= 1 + gg; pv += fl / (1 + rr) ** t              # g constante nos anos 1-10 (v4.27)
        vi = round(pv + fl * (1 + gt) / (rr - gt) / (1 + rr) ** ANOS_PROJECAO, 2)
    # EB1
    anos = _anos_ok(d); ult = anos[-1] if anos else None
    ac = _v(d, "acoes_diluidas", ult) if ult else None
    ebt = None
    if ult: ebt = _v(d, "ebt_sem_extra", ult) if _v(d, "ebt_sem_extra", ult) is not None else _v(d, "resultado_antes_impostos", ult)
    ebt_pa = ebt / ac if ebt is not None and ac else None
    rend_ini = 100 * ebt_pa / preco if ebt_pa is not None and preco else None
    rl_rep = _v(d, "resultado_liquido", ult) if ult else None
    lpa_rep = rl_rep / ac if rl_rep and ac else None
    rend_apos = 100 * lpa_rep / preco if lpa_rep and preco else None
    vo = round(ebt_pa / (taxa10 / 100), 2) if ebt_pa and taxa10 else None
    # EB2
    mk = d.get("mercado") or {}; pl_fim = mk.get("pl_fim_ano") or {}
    pl_hist = statistics.mean(pl_fim.values()) if pl_fim else d["pontuais"].get("pl_medio_historico")
    if not pl_fim and pl_hist: notas.append("P/L-alvo a partir do P/L médio histórico da fonte (sem preços de fim de exercício)")
    pe_alvo = min(pl_hist, PE_ALVO_MAX) if pl_hist else None
    if pe_alvo is None: pe_alvo = PE_NEUTRO; notas.append(f"sem P/L histórico: P/L-alvo neutro de {_num(PE_NEUTRO, 0)}")
    base = [v for a, v in sorted(lpa.items()) if a not in ext][-5:]
    lpa_base = statistics.mean(base) if base else None
    if base and base[-1] < lpa_base:
        # Lucros a cair: a média de 5 anos inclui anos melhores do que o atual e inflaciona a TACE. Parte-se do último LPA.
        notas.append(f"LPA base = último LPA ({_num(base[-1], 2)}), inferior à média de 5 anos ({_num(lpa_base, 2)}): lucros a cair")
        lpa_base = base[-1]
    dpa_atual = dpa_por_ano(d).get(ult) if ult else None
    gg = g / 100
    soma_dpa = sum((dpa_atual or 0) * (1 + gg) ** t for t in range(1, 11))
    metodos = {}
    if lpa_base and lpa_base > 0 and preco:
        lpa10 = lpa_base * (1 + gg) ** 10; p10 = lpa10 * pe_alvo        # crescimento constante (v4.27)
        metodos["I"] = {"lpa_base": lpa_base, "lpa10": lpa10, "preco10": p10, "tace": 100 * (((p10 + soma_dpa) / preco) ** 0.1 - 1)}
    if g_iii is not None and preco and ult:
        cp = _v(d, "capitais_proprios", ult)
        if cp and ac and cp > 0:
            c = min(roe_m * (1 - payout), G_TETO) / 100
            vpa10 = (cp / ac) * (1 + c) ** 10; lpa10 = vpa10 * roe_m / 100; p10 = lpa10 * pe_alvo
            metodos["II"] = {"c": 100 * c, "vpa10": vpa10, "lpa10": lpa10, "preco10": p10, "tace": 100 * (((p10 + soma_dpa) / preco) ** 0.1 - 1)}
    else: notas.append("Método II não aplicado: " + (det_roe or "crescimento sustentável inválido"))
    m_baixo = min(metodos, key=lambda k: metodos[k]["tace"]) if metodos else None
    tace = metodos[m_baixo]["tace"] if m_baixo else None
    total10 = metodos[m_baixo]["preco10"] + soma_dpa if m_baixo else None
    p_eb = round(total10 / (1 + TACE_MINIMA / 100) ** 10, 2) if total10 else None
    valor_eb = round(total10 / (1 + r / 100) ** 10, 2) if total10 else None
    caminhos = {"VI": vi, "P_EB": p_eb, "Valor-Obrigação": vo}
    disp = {k: v for k, v in caminhos.items() if v is not None}
    pmc = min(disp.values()) if disp else None
    limitante = min(disp, key=disp.get) if disp else None
    diverg = round(100 * abs(vi - valor_eb) / vi, 1) if vi and valor_eb else None
    escada = {t: round(total10 / (1 + t / 100) ** 10, 2) for t in sorted({10, 12, 15, 20, 25, round(alvo_pct)})} if total10 else {}
    pl_atual = preco / lpa_rep if preco and lpa_rep and lpa_rep > 0 else None
    return {"r": r, "taxa10": taxa10, "g": round(g, 2), "g_candidatos": {k: (round(v, 2) if v is not None else None) for k, v in cand.items()},
            "g_detalhes": {"(i)": det_i, "(ii)": det_ii, "(iii)": det_roe or f"ROE médio {_num(roe_m, 1)}%, payout {_num(100 * payout, 0)}%"},
            "g_terminal": round(g_term, 2), "oe_por_ano": {a: round(v, 4) for a, v in oe.items()}, "oe0": oe0, "vi": vi,
            "capex_crescimento": cres, "ebt_por_acao": ebt_pa, "rend_inicial": rend_ini, "rend_apos_impostos": rend_apos,
            "valor_obrigacao": vo, "pe_alvo": pe_alvo, "pl_hist_medio": pl_hist, "dpa_atual": dpa_atual, "soma_dpa": soma_dpa,
            "metodos": metodos, "metodo_tace": m_baixo, "tace": round(tace, 2) if tace is not None else None,
            "p_eb": p_eb, "valor_equity_bond": valor_eb, "divergencia_pct": diverg, "pmc": pmc, "pmc_limitante": limitante,
            "caminhos": caminhos, "escada": escada, "alvo_pct": alvo_pct, "pl_atual": pl_atual, "pl_max_10a": max(pl_fim.values()) if pl_fim else None,
            "preco": preco, "anos_extraordinarios": sorted(ext), "notas": notas}

def condicoes_preco(av):
    """As quatro condições de preço do protocolo (C1p a C4p): preço <= PMC, rendimento inicial >= taxa do Estado, TACE >= mínimo e P/L abaixo de 40 e do máximo dos últimos 10 anos."""
    p = av.get("preco"); c = []
    def cond(id_, txt, ok, det): c.append({"id": id_, "descricao": txt, "ok": bool(ok), "detalhe": det})
    cond("C1p", "Preço atual <= Preço Máximo de Compra = mínimo (VI ; P_EB ; Valor-Obrigação)",
         p is not None and av.get("pmc") is not None and p <= av["pmc"], f"preço {_num(p)} vs PMC {_num(av.get('pmc'))}")
    cond("C2p", "Rendimento inicial >= taxa do Estado a 10 anos",
         av.get("rend_inicial") is not None and av.get("taxa10") is not None and av["rend_inicial"] >= av["taxa10"],
         f"{_num(av.get('rend_inicial'), 2)}% vs {_num(av.get('taxa10'), 2)}%")
    cond("C3p", f"TACE a 10 anos >= {_num(TACE_MINIMA, 0)}% (a mais baixa dos dois métodos)",
         av.get("tace") is not None and av["tace"] >= TACE_MINIMA, f"TACE {_num(av.get('tace'), 1)}% (método {av.get('metodo_tace') or '-'})")
    pl, mx = av.get("pl_atual"), av.get("pl_max_10a")
    cond("C4p", "P/L atual < 40 e abaixo do máximo dos últimos 10 anos",
         pl is not None and pl < PL_MAXIMO and (mx is None or pl < mx), f"P/L {_num(pl, 1)} (máximo de 10 anos {_num(mx, 1)})")
    return c

def gatilhos_venda(av):
    """Secção 7, ponto 3 (se a posição já for detida): vende-se a posição, sujeito ao Filtro Fiscal."""
    g = []
    if av.get("pl_atual") is not None and av["pl_atual"] >= PL_MAXIMO: g.append(f"P/L {_num(av['pl_atual'], 1)} >= 40")
    if av.get("vi") and av.get("preco") and av["preco"] > 2 * av["vi"]: g.append(f"preço acima de 2x o valor intrínseco ({_num(2 * av['vi'])})")
    if av.get("tace") is not None and av.get("taxa10") is not None and av["tace"] < av["taxa10"]:
        g.append(f"TACE {_num(av['tace'], 1)}% abaixo da taxa do Estado ({_num(av['taxa10'], 2)}%)")
    return g

def veredicto_final(rejeicao, condicoes, franquia, tace):
    """Passo 8 (Secção 9): COMPRAR / CAIXA DEDICADA / REJEITAR e tamanho da posição (9.1)."""
    if rejeicao:
        return {"categoria": REJEITAR_V, "cor": "nao", "descricao": rejeicao, "limite": None}
    limite = "15% (Franquia e TACE >= 20%)" if franquia and tace is not None and tace >= TACE_ALTA_CONVICCAO else "10%"
    falhas = [c for c in condicoes if not c["ok"]]
    if falhas:
        return {"categoria": CAIXA_V, "cor": "cond", "limite": limite,
                "descricao": "Passa a Triagem e os 10 Portões; o preço ainda não: " + "; ".join(c["detalhe"] for c in falhas)
                             + ". O capital espera em Caixa Dedicada, com alerta de preço no PMC."}
    return {"categoria": COMPRAR_V, "cor": "ok", "limite": limite,
            "descricao": f"Passa a Triagem, os 10 Portões e as quatro condições de preço. Limite no momento da compra: {limite}."}
