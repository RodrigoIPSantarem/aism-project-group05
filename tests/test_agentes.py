"""Testes dos 5 agentes, sem Ollama nem rede (dados sintéticos e modelos simulados).
Correr: python tests/test_agentes.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from experiments.llm_scripted import ScriptedLLM
from nucleo.analisar import analisar
from agentes.qualitativa import _completar, _como_resposta, _frases_numeradas, _numerar

def cat(r): return (r.get("oportunidade") or {}).get("categoria")

class PrimeiraLeituraNega(ScriptedLLM):
    """1.ª leitura: T1 e Wrigley "não" (como o qwen 7B fazia). 2.ª leitura: percebe o produto e acha-o estável."""
    def __init__(self, segunda_sim=True): super().__init__(); self.segunda_sim = segunda_sim
    def json(self, agente, sistema, msg, tentativas=3):
        if agente == "analista":
            r = super().json(agente, sistema, msg, tentativas); self._count(agente)
            r["t1"] = {"produto": "?", "cliente_volta_porque": "?", "porque": "não percebo", "resposta": "nao"}
            r["wrigley"] = {"porque": "incerto", "resposta": "nao"}; return r
        if agente == "analista_2":
            self._count(agente); s = "sim" if self.segunda_sim else "nao"
            return {"produto": "Vende software a empresas.", "descreve": self.segunda_sim,
                    "cliente_volta": {"porque": "contratos anuais", "resposta": s}, "mesmo_em_15_anos": {"porque": "estável", "resposta": s}}
        return super().json(agente, sistema, msg, tentativas)

def teste_formatos():
    # esquema novo e antigo são aceites; um valor solto herda o resto do campo
    novo = _completar({"t1": "sim", "wrigley": {"resposta": "nao", "porque": "x"}, "circulo": {"resposta": "sim"}}, {})
    assert novo["t1"]["resposta"] == "sim" and novo["wrigley"]["resposta"] == "nao"
    antigo = _completar({"circulo": {"resposta": "sim", "wrigley": "nao"}}, {})
    assert antigo["wrigley"]["resposta"] == "nao"
    assert _como_resposta({"t1": "Sim", "wrigley": "Não"})["wrigley"]["resposta"] == "nao"
    f = _frases_numeradas({"Frases sobre preços (relatório anual)": _numerar("[x]\n- A subiu 3%.\n- B subiu 5%.")})
    assert f == {1: "A subiu 3%.", 2: "B subiu 5%."}, f

def teste_sem_regressao():
    r = analisar("AURORA", 10, "sintetico", ScriptedLLM(), mostrar=False)
    assert cat(r) == "COMPRAR", cat(r)

def teste_segunda_leitura():
    r = analisar("AURORA", 10, "sintetico", PrimeiraLeituraNega(True), mostrar=False)
    aq = r["dados"]["analise_qualitativa"]
    assert aq["t1"] == "Não" and aq["wrigley"] == "Não"
    assert {x["campo"] for x in aq["duvidas"]} == {"t1", "wrigley"}, aq.get("duvidas")
    assert cat(r) == "REVISÃO MANUAL", cat(r)
    assert "Segunda leitura" in r["relatorio"]

def teste_duas_leituras_concordam():
    r = analisar("AURORA", 10, "sintetico", PrimeiraLeituraNega(False), mostrar=False)
    assert cat(r) == "REJEITAR", cat(r)          # as duas leituras dizem não: a rejeição mantém-se
    assert not r["dados"]["analise_qualitativa"].get("duvidas")

def teste_item1():
    from fontes.qualitativas import extrair_item1
    lixo = "0000062709 us-gaap:TreasuryStockCommonMember 2024-12-31 http://fasb.org/us-gaap/2025#Assets " * 40
    indice = "Table of Contents Item 1. Business 3 Item 1A. Risk Factors 12 Item 2. Properties 20 "
    corpo = "ITEM 1. BUSINESS. Acme sells branded soft drinks and snacks in 90 countries. " + "Customers buy them every week. " * 120
    t = lixo + indice + corpo + " ITEM 1A. RISK FACTORS Competition may hurt us."
    x = extrair_item1(t)
    assert x.lstrip(". ").startswith("Acme sells branded") and "us-gaap" not in x and "Risk Factors" not in x and len(x) <= 3000, x[:100]
    assert extrair_item1(lixo + indice) == ""                  # só índice e etiquetas: vazio, nunca lixo

def teste_repasse_e_distribuidor():
    from fontes.qualitativas import eh_repasse_custos
    pool = "We generally pass industry price increases through our supply chain and may make purchases ahead of vendor price increases."
    assert eh_repasse_custos(pool)
    assert not eh_repasse_custos("These include selective price increases and supply chain initiatives.")
    assert not eh_repasse_custos("We raised prices by 5% in 2024 with no loss of volume.")
    from agentes.qualitativa import AnaliseQualitativa
    d = {"empresa": {"sic": 5090, "industria_yf": "Industrial Distribution"}}
    fontes = {"Frases sobre preços (relatório anual)": "[x]\n1. " + pool}
    rsp = {"t1": {"resposta": "sim"}, "circulo": {"resposta": "sim"}, "wrigley": {"resposta": "sim"}, "modelo": "M1", "modelo_porque": "x",
           "c2": {"resposta": "sim"}, "c3": {"frase": 1, "resposta": "sim", "porque": "x"},
           "franquia": {k: {"resposta": "sim", "porque": "x"} for k in ("f1", "f2", "f3", "f4")}}
    p = AnaliseQualitativa()._validar(rsp, fontes, "", d)
    assert p["modelo"] == "hibrido" and p["franquia"]["f2"]["resposta"] == "nao"
    assert p["c3_verificado"] == "Não" and "repasse" in p["c3_nota"], p["c3_nota"]
    p2 = AnaliseQualitativa()._validar(rsp, fontes, "", {"empresa": {"sic": 2300, "industria_yf": "Apparel Retail"}})
    assert p2["modelo"] == "M1" and p2["franquia"]["f2"]["resposta"] == "sim"      # fora da distribuição: igual a antes

def teste_lpa_base():
    import nucleo.valorizacao as V
    from nucleo.analisar import analisar
    r = analisar("AURORA", 10, "sintetico", ScriptedLLM(), mostrar=False); d = r["dados"]
    lpa0, rl0, ext0, n0 = V.lpa_ajustado(d); anos = sorted(lpa0)
    orig = V.lpa_ajustado
    try:
        V.lpa_ajustado = lambda dd: ({a: (20.0 if i < len(anos) - 1 else 10.0) for i, a in enumerate(anos)}, rl0, set(), [])   # lucros a cair no último ano
        av = V.avaliar(d)
    finally: V.lpa_ajustado = orig
    assert abs(av["metodos"]["I"]["lpa_base"] - 10.0) < 1e-9 and any("lucros a cair" in n for n in av["notas"]), av["metodos"]["I"]

def teste_critico_revisao_e_cp():
    from agentes.decisor import Decisor
    ver = {"categoria": "COMPRAR", "cor": "ok", "limite": "10%", "descricao": "Passa tudo."}
    # uma objeção grave mantida pelo Crítico: o programa não compra sozinho
    cr = {"objecoes": [{"gravidade": "grave", "campo": "franquia", "descricao": "F4 contrariada pelos dados"}, {"gravidade": "baixa", "campo": None, "descricao": "x"}]}
    r = Decisor._ressalvas(ver, {}, {}, cr)
    assert r["categoria"] == "REVISÃO MANUAL" and "Crítico" in r["descricao"] and r["categoria_regras"] == "COMPRAR"
    # objeções médias ou baixas ficam no relatório, mas não travam o veredicto das regras
    media = {"objecoes": [{"gravidade": "media", "campo": "franquia", "descricao": "discutível"}, {"gravidade": "media", "campo": None, "descricao": "x"}]}
    assert Decisor._ressalvas(ver, {}, {}, media)["categoria"] == "COMPRAR"
    assert Decisor._ressalvas(ver, {}, {}, None)["categoria"] == "COMPRAR"
    # a CAIXA DEDICADA também passa a REVISÃO MANUAL com uma objeção grave, e mantém o veredicto das regras
    cx = Decisor._ressalvas({**ver, "categoria": "CAIXA DEDICADA"}, {}, {}, cr)
    assert cx["categoria"] == "REVISÃO MANUAL" and cx["categoria_regras"] == "CAIXA DEDICADA"
    # uma empresa rejeitada pelas regras nunca passa a REVISÃO MANUAL
    assert Decisor._ressalvas({**ver, "categoria": "REJEITAR"}, {}, {}, cr)["categoria"] == "REJEITAR"
    r2 = analisar("AURORA", 10, "sintetico", ScriptedLLM(), mostrar=False)
    assert "CP1 sim" in r2["relatorio"] and "C1 sim" not in r2["relatorio"].split("Condições de preço:")[1].split("\n")[0]

def teste_fluxo_cinco_agentes():
    """A conversa segue a proposta: Coletor, Guardião, Avaliador, Crítico, Decisor, e só estes cinco."""
    r = analisar("AURORA", 10, "sintetico", ScriptedLLM(), mostrar=False)
    seq = [(m["performativa"], m["remetente"], m["destinatario"]) for m in r["_msgs"]]
    assert seq == [("request", "utilizador", "coletor"), ("inform", "coletor", "guardiao"), ("request", "guardiao", "avaliador"),
                   ("propose", "avaliador", "critico"), ("inform", "critico", "decisor"), ("inform", "decisor", "utilizador")], seq

def teste_rejeicao_imediata():
    """Uma regra de exclusão do Guardião salta o Avaliador e o Crítico (caminho vermelho da proposta)."""
    r = analisar("GRANITO", 10, "sintetico", ScriptedLLM(), mostrar=False)
    assert cat(r) == "REJEITAR" and "T7" in r["motivos"][0]
    assert [m["destinatario"] for m in r["_msgs"]] == ["coletor", "guardiao", "decisor", "utilizador"]

def teste_revisao_limitada():
    """Um Crítico que objeta sempre: uma só revisão (reject-proposal) e o fluxo termina."""
    from experiments.llm_scripted import AlwaysObjectingCritic
    r = analisar("AURORA", 10, "sintetico", AlwaysObjectingCritic(), mostrar=False)
    rej = [m for m in r["_msgs"] if m["performativa"] == "reject-proposal"]
    assert r["revisoes"] == 1 and len(rej) == 1 and rej[0]["destinatario"] == "avaliador"

def teste_dados_em_falta_nao_inventados():
    """NEVOA tem o FCO apagado em 3 de 5 anos: fica em falta e a empresa é rejeitada por dados insuficientes."""
    r = analisar("NEVOA", 10, "sintetico", ScriptedLLM(), mostrar=False)
    fco = r["dados"]["series"].get("fco") or {}
    assert cat(r) == "REJEITAR" and sum(1 for v in fco.values() if v is None) >= 3 and r["dados"]["em_falta"]

def teste_sem_modelo_nunca_compra():
    r = analisar("AURORA", 10, "sintetico", None, mostrar=False)
    assert cat(r) == "REJEITAR" and "indisponível" in r["motivos"][0]

def teste_dezanove_casos_sinteticos():
    """Os 19 casos da E1 (uma empresa sintética por comportamento esperado) dão o resultado desenhado."""
    from experiments.run_experiments import ESPERADO, correr, resumo
    falhas = []
    for t, (desc, ok) in ESPERADO.items():
        r, dt = correr(t, "sintetico", ScriptedLLM()); s = resumo(t, r, dt, "sintético")
        if not (s.get("ok") and ok(s)): falhas.append(f"{t}: {desc} (deu {s.get('v427')})")
    assert not falhas, falhas

def teste_sinais_explicados_por_regras():
    """Cada Sinal de Balanço presente é explicado (ou não) só pelos números, sem nomes de empresas: caixa financiada por dinheiro de fora
    que é pouco face ao FCO fica explicada; muito face ao FCO fica por explicar; ROA muito alto nunca é explicado por regra."""
    from nucleo.testes import explicar_sinais, sinais_balanco
    def dados(emis_div, reemb):
        anos = list(range(2019, 2025)); z = lambda v: {str(a): v for a in anos}
        s = {"receita": z(1000.0), "resultado_liquido": z(100.0), "ativos_totais": z(1000.0), "capitais_proprios": z(500.0),
             "fco": z(100.0), "capex": z(-10.0), "dividendos_pagos": z(0.0), "recompras": z(0.0), "emissao_acoes": z(0.0),
             "emissao_divida": z(0.0), "reembolso_divida": z(0.0), "caixa": z(100.0), "contas_receber": z(100.0)}
        s["caixa"]["2024"] = 340.0; s["emissao_divida"]["2024"] = emis_div; s["reembolso_divida"]["2024"] = reemb
        return {"anos": anos, "series": s}
    r = {"A8": "Sim", "A9": "Sim", "A15": "Sim"}
    def sb(d, rr=r, id_="SB5"): return next(x for x in explicar_sinais(d, sinais_balanco(d), rr) if x["id"] == id_)
    muito = dados(500.0, 0.0)                                   # caixa +240 com 90 retidos: 150 vêm de fora = 150% do FCO (100)
    assert sb(muito)["presente"] and not sb(muito)["explicado"]
    pouco = dados(20.0, 0.0); pouco["series"]["caixa"]["2024"] = 205.0   # caixa +105 com 90 retidos: 15 de fora = 15% do FCO
    assert sb(pouco)["presente"] and sb(pouco)["explicado"]
    sem_sinal = dados(500.0, 0.0); sem_sinal["series"]["caixa"]["2024"] = 120.0   # sobe só 20, o retido chega
    assert not sb(sem_sinal)["presente"]
    assert not sb(muito, {"A8": "Não", "A9": "Sim", "A15": "Sim"}, "SB6")["explicado"]   # sem testes de dívida a aguentar, SB6 nunca é explicado

if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("teste_"):
            out = f(); print(f"PASSOU {nome}" + (f" {out}" if out else ""))