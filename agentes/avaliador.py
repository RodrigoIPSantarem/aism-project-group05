"""A3 Avaliador: o modelo de linguagem responde às perguntas de julgamento e o Python faz as contas (Protocolo v4.27).

Parte qualitativa (agentes/qualitativa.py, com o modelo): Triagem T1, Círculo de Competência, Teste Wrigley, modelo de
negócio, C2, C3 (poder de preço com citação verificada) e Teste da Franquia.
Parte de cálculo (Python puro): Passos 2 e 3 (testes A, B e C, Sinais de Balanço), Passo 4 (os 10 Portões) e Passo 5
(Secção 8: Owner Earnings, Equity Bond, Valor-Obrigação e Preço Máximo de Compra).

Para a apresentação: o Avaliador recebe o pedido do Guardião (request) e propõe o resultado ao Crítico (propose: "proponho
estes números e estas respostas"). Se o Crítico contestar um ponto concreto (reject-proposal), o Avaliador revê só esse
ponto, no máximo MAX_REVISOES vez(es); depois disso recusa (refuse) e o Crítico segue para o Decisor. Se uma pergunta
eliminatória falha (por exemplo fora do Círculo de Competência), a mensagem vai direta ao Decisor, que emite REJEITAR.
"""
from agentes.qualitativa import AnaliseQualitativa
from config import MAX_REVISOES
from nucleo.metricas import _margem_bruta_anual
from nucleo.plataforma import Agente, Msg
from nucleo.testes import bloco_a, bloco_b, bloco_c, explicar_sinais, portoes, sinais_balanco
from nucleo.util import _num
from nucleo.valorizacao import avaliar, condicoes_preco, dpa_por_ano, lpa_ajustado


def calcular(d, setor, alvo_pct):
    """Corre os testes por blocos (A: números, B: gestão e capital, C: respostas qualitativas), os 10 Portões, a avaliação
    (Owner Earnings, Valor-Obrigação, Preço Máximo de Compra) e as condições de preço. Função pura: sem mensagens nem modelo."""
    aq = d["analise_qualitativa"]
    lpa, _, _, _ = lpa_ajustado(d); dpa = dpa_por_ano(d)
    A = bloco_a(d, lpa, dpa, aq.get("modelo", "M1"), setor)
    sinais = sinais_balanco(d)     # alertas de balanço (contas a receber, stocks, dívida de curto prazo, origem da caixa)
    if setor in ("banco", "seguradora"):          # contas a receber, dívida de curto prazo e origem da caixa não têm sentido num banco
        sinais = [s for s in sinais if s["id"] == "SB6"]
    r = {t["id"]: t["resposta"] for t in A}
    if setor not in ("banco", "seguradora"): sinais = explicar_sinais(d, sinais, r)     # cada sinal presente é explicado (ou fica por explicar)
    B = bloco_b(d, lpa, dpa, r.get("A15"), r.get("A13"), aq)
    mb = [v for _, v in sorted(_margem_bruta_anual(d).items()) if v is not None][-4:]
    cai3 = len(mb) == 4 and all(y < x for x, y in zip(mb, mb[1:]))
    C = bloco_c(aq, sinais, cai3)
    P = portoes(A + B + C, setor, d)       # os 10 Portões: todos têm de passar para se poder comprar
    franquia = next(t for t in C if t["id"] == "C4")["resposta"] == "Sim"
    av = avaliar(d, alvo_pct, setor)
    return {"A": A, "B": B, "C": C, "sinais": sinais, "portoes": P, "franquia": franquia}, av, condicoes_preco(av)


class Avaliador(AnaliseQualitativa, Agente):
    """Recebe o pedido do Guardião (request) ou a devolução do Crítico (reject-proposal). Responde às perguntas qualitativas
    com o modelo, calcula testes, Portões, valorização e condições de preço em Python e propõe o resultado ao Crítico."""
    nome = "avaliador"; rotulo = "[A3 Avaliador]"

    def receber(self, m: Msg) -> list[Msg]:
        c = m.conteudo; d = c["dados"]; g = c["guardiao"]
        if m.perf == "reject-proposal":      # o Crítico contestou: reexaminar só os pontos contestados
            rev = c.get("revisoes", 0)
            if rev >= MAX_REVISOES:
                return [m.r("refuse", "critico", {**c, "motivo": "máximo de revisões atingido"})]
            self.dizer("a rever a parte qualitativa pedida pelo Crítico…")
            ant = d["analise_qualitativa"]
            obs = [o for o in c["critica"]["objecoes"] if o.get("campo")]
            prop = self._propor(d, obs, ant)
            prop["analise_inicial"] = {k: ant.get(k) for k in ("modelo", "c2", "c3_verificado", "franquia")}
            d["analise_qualitativa"] = prop; self._emitir(prop, revisao=True)
            self.dizer(f"revisto: modelo {prop['modelo']}, C3 {prop['c3_verificado']}, franquia "
                       f"{sum(1 for x in prop['franquia'].values() if x['resposta'] == 'sim')}/4 sim")
            rev += 1
        else:                                # primeira avaliação, a pedido do Guardião
            self.dizer("perguntas qualitativas (T1, Círculo, modelo, Franquia): a ler o 10-K (Item 1), o perfil e a Wikipedia…")
            prop = self._propor(d); d["analise_qualitativa"] = prop
            n_fr = sum(1 for x in prop["franquia"].values() if x["resposta"] == "sim")
            if prop.get("indisponivel"): self.dizer("modelo de linguagem indisponível: sem respostas qualitativas")
            else: self.dizer(f"T1 {prop['t1']}, círculo {prop['circulo']}, Wrigley {prop['wrigley']}, modelo {prop['modelo']}, "
                             f"C3 {prop['c3_verificado']}, franquia {n_fr}/4 sim")
            if prop.get("duvidas"):
                self.dizer("segunda leitura discorda da primeira em: " + ", ".join(x["campo"] for x in prop["duvidas"]) + " (fica como ressalva no veredicto)")
            self._emitir(prop)
            rev = 0
        rej = self.rejeicao(prop, g)
        if rej:                               # pergunta eliminatória falhada: não vale a pena calcular, o Decisor rejeita
            self.dizer("rejeitada: " + rej[:200])
            return [m.r("inform", "decisor", {**c, "rejeicao_qualitativa": rej})]
        setor = g["setor"]
        tst, av, cond = calcular(d, setor, d.get("taxa_alvo_pct", 20.0))
        falhas = [p["id"] for p in tst["portoes"] if not p["passa"]]
        self.dizer(f"{'revisto: ' if rev else ''}Portões {10 - len(falhas)}/10" + (f" (falham {', '.join(falhas)})" if falhas else "")
                   + f" · franquia {'sim' if tst['franquia'] else 'não'} · TACE {_num(av['tace'], 1)}% · PMC {_num(av['pmc'])} ({av['pmc_limitante'] or '-'})")
        if self.plat:
            self.plat.emitir("avaliador_proposta", "avaliador", {"revisao": bool(rev), "testes": tst, "avaliacao": av, "condicoes": cond})
        return [m.r("propose", "critico", {**c, "testes": tst, "avaliacao": av, "condicoes": cond, "revisoes": rev})]