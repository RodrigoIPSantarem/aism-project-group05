"""A5 Decisor: Passos 6, 7 e 8 do Protocolo v4.27 (Secção 9). Não há nota nem pontos:
compra-se se, e só se, a empresa passa a Triagem, o Círculo, o Setor, os 10 Portões e as quatro condições de preço.
Veredicto: COMPRAR / CAIXA DEDICADA (passa tudo menos o preço) / REJEITAR. A síntese é escrita por Buffett, mas o
veredicto é das regras e não pode ser alterado.

Para a apresentação: é aqui que todos os caminhos se encontram. Chegam ao Decisor (a) as empresas reprovadas pelo Guardião ou
pela parte qualitativa do Avaliador, (b) as aceites pelo Crítico, com Portões e avaliação. O veredicto sai de
`veredicto_final` (nucleo/valorizacao.py), que é Python puro; o modelo só escreve uma síntese de 3 frases, que é descartada se
citar números inexistentes. Depois o Decisor monta o relatório de texto (`_relatorio`) e entrega-o ao utilizador (inform)."""
import json
from config import CAIXA_V, COMPRAR, COMPRAR_V, FRANQUIA_PERGUNTAS, NAO, TACE_MINIMA
from nucleo.llm import ErroLLM, _PERSONA_BUFFETT
from nucleo.plataforma import Agente, Msg
from nucleo.util import _ao90, _num, _numeros_nao_verificados, _pct
from nucleo.valorizacao import gatilhos_venda, veredicto_final

_SIS_DEC = """Tarefa: és o Decisor. O veredicto foi decidido pelas regras do Protocolo v4.27 (Triagem, 10 Portões e preço) e
NÃO pode ser alterado. Escreve, na tua voz, uma síntese de 3 frases: a qualidade do negócio, o preço face ao Preço Máximo
de Compra e o que teria de acontecer para comprar. Não acrescentes números que não estejam no pedido.
Responde APENAS com JSON: {"sintese":"<texto>"}"""
_SIS_DEC = _PERSONA_BUFFETT + "\n\n" + _SIS_DEC
NOMES_SETOR = {"padrao": "método completo", "banco": "banco (respostas próprias em P3, P4 e P8)",
               "seguradora": "seguradora (respostas próprias em P3, P4 e P8)", "fora_metodo": "FORA DO MÉTODO"}

def _fmt(v):
    if v is None: return ""
    if isinstance(v, (int, float)): return "infinito" if v == float("inf") else _num(v, 2)
    return str(v)

def _linha_teste(t):
    out = f"  {t['id']:<4} {t['nome'][:48]:<48} {t['resposta']:<14} {_fmt(t['valor'])}"
    return out + (f"  [{t['nota']}]" if t.get("nota") else "")

def _resumo_decisao(d, tst, av, cond, ver):
    if not av: return []
    moeda = (d.get("mercado") or {}).get("moeda") or d["empresa"].get("moeda") or ""
    preco = av.get("preco"); cam = av.get("caminhos") or {}; L = ["", "-" * 76, "RESUMO PARA DECISÃO"]
    if preco is not None and av.get("tace") is not None:
        L.append(f"  Ao preço atual de {_num(preco)} {moeda}, a TACE esperada é {_num(av['tace'], 1)}% ao ano (exigência: {_num(TACE_MINIMA, 0)}%).")
    if av.get("pmc"):
        dif = (av["pmc"] / preco - 1) * 100 if preco else None
        L.append(f"  Preço Máximo de Compra = mínimo (VI {_num(cam.get('VI'))} ; P_EB {_num(cam.get('P_EB'))} ; Valor-Obrigação "
                 f"{_num(cam.get('Valor-Obrigação'))}) = {_num(av['pmc'])} {moeda}"
                 + ((f" (desconto de {_num(abs(dif), 0)}% face ao preço atual)." if dif < 0 else " (acima do preço atual).") if dif is not None else "."))
    esc = av.get("escada") or {}
    if esc and av.get("alvo_pct") in esc:
        L.append(f"  Para {_num(av['alvo_pct'], 0)}% ao ano (o teu alvo): comprar no máximo a {_num(esc[av['alvo_pct']])} {moeda}.")
    if esc: L.append("  Preço máximo por rentabilidade: " + " · ".join(f"{_num(t, 0)}% -> {_num(p)}" for t, p in esc.items()))
    if tst:
        falham = [p["id"] for p in tst["portoes"] if not p["passa"]]
        L.append(f"  10 Portões: {10 - len(falham)}/10 passam" + (f" (falham {', '.join(falham)})" if falham else "")
                 + f" · Franquia: {'sim' if tst['franquia'] else 'não confirmada'}")
    if cond: L.append("  Condições de preço: " + " · ".join(f"CP{c['id'][1]} {'sim' if c['ok'] else 'NÃO'}" for c in cond))
    L.append(f"  => {ver['categoria']}" + (f" · limite no momento da compra {ver['limite']}" if ver.get("limite") else ""))
    L.append("-" * 76)
    return L

class Decisor(Agente):
    """Recebe tudo o que foi apurado, aplica as regras do protocolo e produz o veredicto (COMPRAR, CAIXA DEDICADA ou REJEITAR) e o relatório, que segue para o utilizador."""
    nome = "decisor"; rotulo = "[A5 Decisor]"

    @staticmethod
    def _ressalvas(ver, g, aq, cr=None):
        """O veredicto é sempre um dos três do protocolo (COMPRAR, CAIXA DEDICADA ou REJEITAR) e é o das regras. Quando uma empresa que
        passa (COMPRAR ou CAIXA DEDICADA) tem uma ressalva, o veredicto não muda: junta-se-lhe um aviso (campos "ressalva" e "ressalvas")
        a pedir ao utilizador que confirme antes de agir. Ressalvas: o modelo discordou de si próprio numa pergunta qualitativa
        (segunda leitura), ou o Crítico manteve uma objeção grave."""
        if ver["categoria"] not in (COMPRAR_V, CAIXA_V): return ver
        duv = (aq or {}).get("duvidas") or []
        # Só contam as objeções graves que o Crítico manteve depois da revisão ("grave" = claramente contrariado pelos dados).
        # As médias ("discutível") e as baixas ficam listadas no relatório, mas não são ressalva: o modelo pequeno levanta
        # objeções médias a quase tudo, sobretudo a afirmações qualitativas que não consegue verificar.
        obj = [o for o in ((cr or {}).get("objecoes") or []) if o.get("gravidade") == "grave"]
        if not duv and not obj: return ver
        partes = []
        if duv: partes.append("a segunda leitura do modelo discorda da primeira em " + ", ".join(
            {"t1": "T1 (produto)", "circulo": "Círculo de Competência", "wrigley": "Teste Wrigley"}.get(x["campo"], x["campo"]) for x in duv)
            + ": lê as duas justificações no relatório")
        if obj: partes.append("o Crítico (Munger) manteve " + ("uma objeção" if len(obj) == 1 else f"{len(obj)} objeções") + " sobre " + "; ".join(
            f"{o['campo'] or 'a análise'}: {o['descricao']}" for o in obj[:2]))
        return {**ver, "descricao": ver["descricao"] + " RESSALVA, confirma antes de agir: " + "; ".join(partes) + ".",
                "ressalva": True, "ressalvas": partes, "categoria_regras": ver["categoria"]}

    def _sintese(self, factos):
        """Síntese de 3 frases na voz de Buffett. O modelo recebe só factos já decididos e não pode mudar o veredicto;
        se citar um número que não está nos factos, a síntese é descartada (o relatório sai sem ela)."""
        if not self.llm: return None
        try: txt = str(self.llm.json(self.nome, _SIS_DEC, json.dumps(factos, ensure_ascii=False, default=str)).get("sintese", ""))
        except ErroLLM: return None
        if not txt.strip(): return None
        if _numeros_nao_verificados(txt, factos):
            self.dizer("síntese descartada: cita números que não estão nos factos"); return None
        return _ao90(txt.strip())

    def _relatorio(self, d, g, aq, tst, av, cond, cr, ver, sint):
        """O relatório de texto, passo a passo como no protocolo: veredicto e resumo, Triagem (-2), Círculo (-1), Setor (0),
        Modelo (1), testes A, B e C (2 e 3), 10 Portões (4), Avaliação (5), Decisão (6), Checklist (7), dados de mercado,
        proveniência dos dados e o debate com o Crítico. Cada secção só aparece se a análise chegou a esse passo."""
        e = d["empresa"]; mk = d.get("mercado") or {}
        L = ["", "=" * 76, f"RELATÓRIO v4.27 — Método Buffett Integral: {e['nome']} ({e['ticker']}) · {e['fonte']}",
             f"Anos: {d['anos'][0] if d['anos'] else '-'} a {d['anos'][-1] if d['anos'] else '-'} ({len(d['anos'])} exercícios)", "=" * 76,
             f"VEREDICTO (Passo 8): {ver['categoria']} — {ver['descricao']}"]
        L += _resumo_decisao(d, tst, av, cond, ver)
        if sint: L += ["", "Síntese (Buffett):", f"  {sint}"]
        if g.get("triagem"):
            L += ["", "Passo -2 · Triagem Rápida (um \"não\" e a empresa sai):"]
            for q in g["triagem"]:
                resp = q["resposta"]
                if q["id"] == "T1" and aq: resp = aq["t1"].lower(); q = {**q, "detalhe": aq.get("t1_porque") or q["detalhe"]}
                if q["id"] == "T5" and q["resposta"] == "pendente" and aq: resp = "sim (M3)" if aq.get("modelo") == "M3" else "não"
                L.append(f"  {q['id']}  {resp.upper():<14} {q['pergunta']} · {q['detalhe']}")
        if aq:
            L += ["", "Passo -1 · Círculo de Competência:",
                  f"  {aq['circulo'].upper()} · Teste Wrigley: {aq['wrigley'].upper()} · patentes (> 50% da receita a expirar): "
                  f"{'SIM' if aq['patentes_mais_de_metade'] else 'não'} — {aq.get('circulo_porque', '')}"]
        if aq and aq.get("duvidas"):
            L += ["  Segunda leitura (outra formulação) discorda da primeira — a empresa não foi rejeitada por isto:"]
            for x in aq["duvidas"]:
                L += [f"    {x['campo'].upper()}: 1.ª leitura — {x['primeira']}", f"    {'':<{len(x['campo'])}}  2.ª leitura — {x['segunda']}"]
        L += ["", f"Passo 0 · Setor: {NOMES_SETOR.get(g.get('setor'), g.get('setor'))} · {g.get('origem_setor', '')}"]
        for x in g.get("dados_insuficientes") or []: L.append(f"  DADOS: {x}")
        fd = d.get("banco")
        if fd:
            L.append(f"  Indicadores regulatórios: {fd['fonte']}")
            for a in sorted(fd["por_ano"])[-5:]:
                x = fd["por_ano"][a]
                L.append(f"    {a}: CET1 {_num(x.get('cet1'), 2)}% · NPL {_num(x.get('npl'), 2)}% · NIM {_num(x.get('nim'), 2)}% · "
                         f"eficiência {_num(x.get('eficiencia'), 1)}% · ROA {_num(x.get('roa'), 2)}% · ROE {_num(x.get('roe'), 1)}%")
        elif g.get("setor") == "banco":
            L.append("  Indicadores regulatórios: sem dados (FDIC só cobre bancos americanos)")
        if aq:
            nomes = {"M1": "produto exclusivo", "M2": "serviço exclusivo", "M3": "baixo custo", "hibrido": "híbrido ou parcial"}
            L += ["", "Passo 1 · Modelo de negócio:", f"  {aq['modelo']} ({nomes.get(aq['modelo'], '')}) — {aq.get('modelo_porque', '')}",
                  f"  Dependência de patentes: {'sim (C1 = Parcial, C2 = Não)' if aq['dependente_patentes'] else 'não'} · "
                  f"serviço de talentos individuais: {'sim' if aq['servico_de_talentos'] else 'não'}"]
        for q in g.get("base") or []: L.append(f"  {q['id']:<9} {q['resposta'].upper():<5} {q['pergunta']} · {q['detalhe']}")
        if tst:
            L += ["", "Passo 2 · Bloco A — vantagem competitiva durável (Sim / Parcial / Não; não há pontos):"] + [_linha_teste(t) for t in tst["A"]]
            pres = [s for s in tst["sinais"] if s["presente"]]; por_expl = [s for s in pres if not s.get("explicado")]
            L.append(f"  Sinais de Balanço: {len(pres)} presente(s), {len(por_expl)} por explicar (2 ou mais por explicar impedem a Franquia)")
            for s in tst["sinais"]:
                L.append(f"    {'[!]' if s['presente'] and not s.get('explicado') else '[~]' if s['presente'] else '[ ]'} {s['descricao']} · {s['detalhe']}")
                if s.get("explicado"): L.append(f"          explicado: {s['explicacao']}")
            L += ["", "Passo 3 · Bloco B — gestão e alocação de capital:"] + [_linha_teste(t) for t in tst["B"]]
            L += ["         Bloco C — durabilidade do negócio:"] + [_linha_teste(t) for t in tst["C"]]
            if aq:
                for k, perg in FRANQUIA_PERGUNTAS.items():
                    f = aq["franquia"][k]; L.append(f"         {perg} {f['resposta'].upper()} — {f['porque']}")
                for v in aq.get("verificacao") or []: L.append(f"         Verificação: {v}")
            L += ["", "Passo 4 · Os 10 Portões de Buffett (passam com Sim ou Parcial; um falhado é rejeição):"]
            for p in tst["portoes"]: L.append(f"  {p['id']:<4} {'PASSA' if p['passa'] else 'FALHA':<6} {p['pergunta']} · {p['detalhe']}")
            if any(not p["passa"] and p["id"] in ("P2", "P8") for p in tst["portoes"]):
                L.append("  Problema solucionável (Secção 6.4): se a falha vem de um problema recente e pontual, documentar por escrito "
                         "(o quê, porque é pontual, porque não toca na franquia) e reavaliar. A franquia, o P3 e o FCO nunca são dispensados.")
        if av:
            L += ["", "Passo 5 · Avaliação (Secção 8):",
                  f"  r = {_num(av['r'], 2)}% (taxa do Estado a 10 anos {_pct(av['taxa10'], 2)}, sem prémio de risco, piso 7%)",
                  "  g = mínimo de: " + "; ".join(f"{k} {_num(v, 2) + '%' if v is not None else 'não válido'}" for k, v in av["g_candidatos"].items())
                  + f" -> g = {_num(av['g'], 2)}%, constante nos anos 1–10; terminal = mínimo (2,5% ; g/2) = {_num(av['g_terminal'], 2)}%",
                  f"    detalhes: (i) {av['g_detalhes']['(i)']}; (ii) {av['g_detalhes']['(ii)']}; (iii) {av['g_detalhes']['(iii)']}",
                  f"  Etapa A — Owner Earnings/ação (média de 5 anos, capex de manutenção) {_num(av['oe0'], 3)} -> Valor Intrínseco {_num(av['vi'])}",
                  f"  EB1 — rendimento inicial {_pct(av['rend_inicial'], 2)} antes de impostos ({_pct(av['rend_apos_impostos'], 2)} depois) "
                  f"vs Estado {_pct(av['taxa10'], 2)} · Valor-Obrigação {_num(av['valor_obrigacao'])}",
                  f"  EB2 — P/L-alvo {_num(av['pe_alvo'], 1)} (mínimo entre a média de 10 anos {_num(av['pl_hist_medio'], 1)} e 25) · DPA atual {_num(av['dpa_atual'], 2)}"]
            for k, mm in av["metodos"].items():
                if k == "I": L.append(f"    Método I (LPA): LPA base {_num(mm['lpa_base'], 3)} -> LPA10 {_num(mm['lpa10'], 2)} -> preço10 {_num(mm['preco10'])} -> TACE {_num(mm['tace'], 2)}%")
                else: L.append(f"    Método II (ROE): c {_num(mm['c'], 2)}% -> VPA10 {_num(mm['vpa10'], 2)} -> LPA10 {_num(mm['lpa10'], 2)} -> preço10 {_num(mm['preco10'])} -> TACE {_num(mm['tace'], 2)}%")
            L += [f"    TACE = {_num(av['tace'], 2)}% (método {av['metodo_tace'] or '-'}, o mais baixo)",
                  f"  EB3 — P_EB (preço para 15% ao ano) {_num(av['p_eb'])}",
                  f"  PMC = mínimo (VI ; P_EB ; Valor-Obrigação) = {_num(av['pmc'])} (limitado por: {av['pmc_limitante']})",
                  f"  Validação cruzada: VI {_num(av['vi'])} vs Valor Equity Bond {_num(av['valor_equity_bond'])} (divergência {_pct(av['divergencia_pct'])}"
                  + ("; acima de 20%: documentar a causa)" if (av['divergencia_pct'] or 0) > 20 else ")")]
            L += [f"  Nota: {n}" for n in av["notas"]]
        if cond:
            L += ["", "Passo 6 · Decisão (Secção 9): Triagem + Portões + as quatro condições de preço, cumulativas"]
            L += [f"  {'[x]' if c_['ok'] else '[ ]'} {c_['descricao']} · {c_['detalhe']}" for c_ in cond]
            portoes_ok = bool(tst) and all(p["passa"] for p in tst["portoes"])
            L += ["", "Passo 7 · Checklist de execução (no momento da compra):",
                  f"  {'[x]' if portoes_ok else '[ ]'} A Triagem e os 10 Portões continuam a passar com o último relatório anual",
                  f"  {'[x]' if cond[0]['ok'] else '[ ]'} Preço atual <= Preço Máximo de Compra",
                  f"  {'[x]' if all(x['ok'] for x in cond[1:]) else '[ ]'} Rendimento inicial >= taxa do Estado, TACE >= 15%, P/L < 40 e abaixo do máximo de 10 anos",
                  f"  [ ] Posição após a compra <= {ver.get('limite') or '10%'} (verificar na corretora)",
                  "  [ ] Esta compra merece um furo do cartão de 20 decisões? Registar \"Decisão n.º X de 20\""]
            gv = gatilhos_venda(av)
            L += ["", "Se a posição já for detida (Secção 7): " + ("vender a posição, sujeito ao Filtro Fiscal: " + "; ".join(gv) if gv else "nenhum gatilho de venda por preço")]
        if mk:
            L += ["", "Dados de mercado (automáticos):",
                  f"  Preço {_num(mk.get('preco'))} {mk.get('moeda', '')} · {mk.get('fonte_preco', '')} · {mk.get('data_preco', '')}"
                  + (f" · cotação original {_num(mk.get('preco_original'))} {mk.get('moeda_original')}" if mk.get("moeda_original") not in (None, mk.get("moeda")) else ""),
                  f"  Taxa a 10 anos {_pct(mk.get('taxa_10a'), 2)} · {mk.get('fonte_taxa', '')}",
                  "  P/L de fim de exercício: " + " | ".join(f"{a}: {_num(v, 1)}" for a, v in sorted((mk.get('pl_fim_ano') or {}).items())),
                  "  O beta não é usado (Buffett considera-o uma medida errada de risco)."]
            L += [f"  {x}" for x in mk.get("notas_moeda") or []]
            if av and av.get("pmc") and mk.get("moeda_original") not in (None, mk.get("moeda")):
                fx, esc, rac = mk.get("fx_cotacao_para_relatorio") or 1, mk.get("escala_cotacao") or 1, mk.get("racio_adr") or 1
                L.append(f"  PMC na moeda da cotação: {_num(av['pmc'] * rac / fx / esc)} {mk.get('moeda_original')}"
                         + (f" por ADR ({_num(rac, 0)} ação(ões))" if rac != 1 else ""))
        fonte_nota = [x for x in (e.get("nota_fonte"),) if x] + [f"também disponível: {x}" for x in e.get("outras_fontes") or []]
        if fonte_nota: L += ["", "Fonte das demonstrações:"] + [f"  {x}" for x in fonte_nota]
        org = d.get("origem_dados") or {}
        if org:
            por = {}
            for k, f in org.items(): por.setdefault(f, []).append(k)
            L += ["", "Proveniência dos dados (valores que não vieram diretamente da SEC):"]
            L += [f"  {f}: {len(ks)} — {', '.join(sorted(ks)[:6])}{' …' if len(ks) > 6 else ''}" for f, ks in por.items()]
        L += [f"  Conflito entre fontes: {cf}" for cf in d.get("conflitos_fontes") or []]
        if d.get("ajustes_split"): L.append(f"  Desdobramentos de ações ajustados: {'; '.join(d['ajustes_split'])}")
        if cr:
            L += ["", f"Crítico — Munger ({cr['revisoes']} revisão(ões) pedida(s) ao Avaliador):"]
            if cr["revisoes"]:
                L += [f"  [1.ª ronda] {o['gravidade']}: {o['descricao']} ({o.get('origem', '')})" for o in cr["objecoes_iniciais"]]
                L += [f"  Revisão do Avaliador: {a}" for a in (aq or {}).get("alteracoes") or []]
            L += [f"  [final] {o['gravidade']}: {o['descricao']} ({o.get('origem', '')})" for o in cr["objecoes"] or []]
            if not cr["objecoes"]: L.append("  sem objeções na versão final")
        L += ["", "Demonstração académica · não constitui aconselhamento financeiro.", "=" * 76]
        return "\n".join(L)

    def receber(self, m: Msg) -> list[Msg]:
        """Decide. Primeiro procura um motivo de rejeição (Guardião, parte qualitativa do Avaliador ou um Portão falhado); depois
        pede o veredicto às regras, junta as ressalvas (aviso, sem mudar o veredicto), monta o relatório e entrega-o ao utilizador."""
        c = m.conteudo; d, g = c["dados"], c["guardiao"]
        aq = d.get("analise_qualitativa"); tst = c.get("testes"); av = c.get("avaliacao"); cond = c.get("condicoes") or []; cr = c.get("critica")
        motivo = None      # o primeiro motivo de rejeição que existir, por ordem de passo do protocolo
        if not g["aprovada"]: motivo = "; ".join(g["motivos"])
        elif c.get("rejeicao_qualitativa"): motivo = c["rejeicao_qualitativa"]
        elif tst and any(not p["passa"] for p in tst["portoes"]):
            motivo = "Portões falhados: " + "; ".join(f"{p['id']} {p['pergunta']} ({p['detalhe']})" for p in tst["portoes"] if not p["passa"])
        # veredicto: COMPRAR (tudo passa) · CAIXA DEDICADA (passa tudo menos o preço) · REJEITAR (há motivo)
        ver = veredicto_final(motivo, cond, bool(tst and tst["franquia"]), (av or {}).get("tace"))
        ver = self._ressalvas(ver, g, aq, cr)
        npass = sum(1 for p in tst["portoes"] if p["passa"]) if tst else None
        self.dizer(f"{ver['categoria']}" + (f" · Portões {npass}/10" if tst else "") + (f" · TACE {_num(av['tace'], 1)}%" if av else ""))
        sint = None
        if tst and av:
            sint = self._sintese({"empresa": d["empresa"]["nome"], "veredicto": ver["categoria"], "descricao": ver["descricao"],
                                  "portoes_que_passam": npass, "franquia": tst["franquia"], "tace_pct": av.get("tace"),
                                  "preco_atual": av.get("preco"), "pmc": av.get("pmc"), "condicoes_falhadas": [x["descricao"] for x in cond if not x["ok"]]})
        rel = self._relatorio(d, g, aq, tst, av, cond, cr, ver, sint)
        if self.plat: self.plat.emitir("decisor_veredicto", "decisor", {"veredicto": ver, "portoes": (tst or {}).get("portoes"), "condicoes": cond})
        res = {"veredicto": COMPRAR if ver["categoria"] == "COMPRAR" else NAO, "portoes_ok": npass, "oportunidade": ver,
               "rejeicao_imediata": bool(motivo), "motivos": [motivo] if motivo else [ver["descricao"]], "relatorio": rel,
               "dados": d, "testes": tst, "avaliacao": av, "condicoes": cond, "critica": cr, "revisoes": (cr or {}).get("revisoes", 0), "guardiao": g}
        return [m.r("inform", "utilizador", res)]