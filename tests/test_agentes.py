"""Testes dos 5 agentes. Não há modelos simulados: onde o modelo de linguagem entra, é sempre o Ollama real.

  python tests/test_agentes.py                  1) testes das regras (segundos, sem Ollama nem rede)
                                                2) as 19 empresas sintéticas com o Ollama real -> saidas/teste_sinteticos.json
  python tests/test_agentes.py --so-regras      só a parte 1
  python tests/test_agentes.py --tickers AURORA,BOREAL   só estas sintéticas na parte 2
  python tests/test_agentes.py --refazer        ignora o que já está no ficheiro de saída
  python -m pytest -q                           só a parte 1 (as funções teste_*)

A parte 2 não "passa" nem "falha": cada empresa sintética foi desenhada para um comportamento (campo "esperado" do JSON) e o
ficheiro mostra o que o modelo real fez, com o campo "como_esperado". Se parar a meio, volte a correr: continua onde ficou.
"""
import argparse, datetime, json, pathlib, sys, time
RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from nucleo.analisar import analisar
from agentes.qualitativa import _completar, _como_resposta, _frases_numeradas, _numerar

def cat(r): return (r.get("oportunidade") or {}).get("categoria")

# ─────────────────────────────── parte 1: regras (sem modelo de linguagem)
def teste_formatos():
    # esquema novo e antigo são aceites; um valor solto herda o resto do campo
    novo = _completar({"t1": "sim", "wrigley": {"resposta": "nao", "porque": "x"}, "circulo": {"resposta": "sim"}}, {})
    assert novo["t1"]["resposta"] == "sim" and novo["wrigley"]["resposta"] == "nao"
    antigo = _completar({"circulo": {"resposta": "sim", "wrigley": "nao"}}, {})
    assert antigo["wrigley"]["resposta"] == "nao"
    assert _como_resposta({"t1": "Sim", "wrigley": "Não"})["wrigley"]["resposta"] == "nao"
    f = _frases_numeradas({"Frases sobre preços (relatório anual)": _numerar("[x]\n- A subiu 3%.\n- B subiu 5%.")})
    assert f == {1: "A subiu 3%.", 2: "B subiu 5%."}, f

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
    r = analisar("AURORA", 10, "sintetico", None, mostrar=False); d = r["dados"]     # sem modelo: só interessam os números
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

def teste_rejeicao_imediata():
    """Uma regra de exclusão do Guardião salta o Avaliador e o Crítico (caminho vermelho da proposta); não chega a usar o modelo."""
    r = analisar("GRANITO", 10, "sintetico", None, mostrar=False)
    assert cat(r) == "REJEITAR" and "T7" in r["motivos"][0]
    assert [m["destinatario"] for m in r["_msgs"]] == ["coletor", "guardiao", "decisor", "utilizador"]

def teste_dados_em_falta_nao_inventados():
    """NEVOA tem o FCO apagado em 3 de 5 anos: fica em falta e a empresa é rejeitada por dados insuficientes."""
    r = analisar("NEVOA", 10, "sintetico", None, mostrar=False)
    fco = r["dados"]["series"].get("fco") or {}
    assert cat(r) == "REJEITAR" and sum(1 for v in fco.values() if v is None) >= 3 and r["dados"]["em_falta"]

def teste_sem_modelo_nunca_compra():
    r = analisar("AURORA", 10, "sintetico", None, mostrar=False)
    assert cat(r) == "REJEITAR" and "indisponível" in r["motivos"][0]

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

# ─────────────────────────────── parte 2: as 19 empresas sintéticas com o modelo real (devolve JSON)
# comportamento para que cada empresa foi desenhada (dados/empresas_sinteticas.json) e o que se espera do veredicto final
ESPERADO = {
    "AURORA": ("franquia excelente abaixo do preço máximo", ("COMPRAR",)),
    "BOREAL": ("excelente, preço um pouco acima do valor: esperar", ("CAIXA DEDICADA",)),
    "CASTOR": ("excelente mas muito cara: esperar", ("CAIXA DEDICADA",)),
    "DUNA": ("empresa muito boa: passa os Portões de qualidade", ("COMPRAR", "CAIXA DEDICADA")),
    "ESTEIO": ("empresa razoável perto do valor justo: não comprar", ("CAIXA DEDICADA", "REJEITAR", "REVISÃO MANUAL")),
    "FAROL": ("empresa fraca: rejeitar", ("REJEITAR",)),
    "GRANITO": ("fluxo de caixa operacional negativo: rejeitar na triagem T7", ("REJEITAR",)),
    "HORIZONTE": ("energia: fora do método (Passo 0)", ("REJEITAR",)),
    "IRIS": ("diluição de 19% em 3 anos: rejeitar na triagem T6", ("REJEITAR",)),
    "JADE": ("goodwill alto, só por si, não é regra de rejeição na v4.27", None),
    "LINCE": ("beta alto é ignorado pela v4.27", None),
    "MARE": ("transportes: fora do método (Passo 0)", ("REJEITAR",)),
    "NEVOA": ("fluxo de caixa apagado em 3 de 5 anos: dados insuficientes, nada inventado", ("REJEITAR",)),
    "ORLA": ("só 3 anos de histórico: dados insuficientes", ("REJEITAR",)),
    "PRISMA": ("rótulos desconhecidos mapeados pelo Coletor", None),
    "QUARTZO": ("promessas da gestão não contam: rejeitar na triagem T3", ("REJEITAR",)),
    "SILEX": ("dados incoerentes (lucro acima da receita): rejeitar", ("REJEITAR",)),
    "TEJO": ("beta não divulgado: a análise continua", None),
    "NVO": ("5 anos e sem lucro bruto: dados insuficientes", ("REJEITAR",)),
}

def correr_sinteticos(argv):
    from experiments.teste_real import resumir, guardar            # o mesmo formato de JSON do teste com empresas reais
    from nucleo.configuracao import garantir_env, modelos_ollama, tem_modelo
    from nucleo.llm import _criar_llm
    from nucleo.util import _carregar_env
    p = argparse.ArgumentParser(description="As empresas sintéticas com o modelo real; devolve um JSON.")
    p.add_argument("--tickers"); p.add_argument("--refazer", action="store_true")
    p.add_argument("--saida", default=str(RAIZ / "saidas" / "teste_sinteticos.json"))
    a = p.parse_args(argv)
    garantir_env(); _carregar_env()
    llm = _criar_llm(RAIZ / "dados" / "cache_llm"); inst = modelos_ollama()
    if inst is None: print("ERRO: o Ollama não está a correr. Abra o Ollama, espere uns 20 s e volte a correr."); return 2
    if not tem_modelo(llm.modelo, inst): print(f"ERRO: o modelo {llm.modelo} não está instalado: ollama pull {llm.modelo}"); return 2
    lista = [t.strip().upper() for t in (a.tickers.split(",") if a.tickers else ESPERADO) if t.strip()]
    saida = pathlib.Path(a.saida); feitas = {}
    if saida.exists() and not a.refazer:
        try: feitas = {l["ticker"]: l for l in json.loads(saida.read_text(encoding="utf-8")).get("empresas", []) if l.get("ok")}
        except Exception: feitas = {}
    meta = {"data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "modelo": f"{llm.backend}:{llm.modelo}", "anos": 10, "pedidas": lista}
    linhas = [feitas[t] for t in lista if t in feitas]; t_total = time.perf_counter()
    try:
        for i, t in enumerate(lista, 1):
            if t in feitas: continue
            print(f"[{i}/{len(lista)}] {t} (sintético) ...", flush=True)
            n0 = len(llm.metricas); t0 = time.perf_counter()
            try: r = analisar(t, 10, "sintetico", llm, mostrar=False, jsonl=RAIZ / "saidas" / f"{t}.jsonl")
            except Exception as e: r = {"performativa": "failure", "motivo": f"{type(e).__name__}: {e}"}
            linha = resumir(t, "sintetico", r, time.perf_counter() - t0, len(llm.metricas) - n0)
            desc, ok = ESPERADO.get(t, ("", None))
            linha["esperado"] = desc
            linha["como_esperado"] = (linha.get("veredicto_final") in ok) if ok and linha.get("ok") else None   # None: sem veredicto fixo para comparar
            linhas.append(linha); meta["terminado_em"] = datetime.datetime.now().strftime("%H:%M")
            guardar(saida, meta, linhas)
            print(f"      {linha.get('veredicto_final', 'ERRO')} · {linha.get('segundos')} s · {linha.get('chamadas_ao_modelo', 0)} chamadas ao modelo"
                  + ("" if linha["como_esperado"] is None else (" · como esperado" if linha["como_esperado"] else " · DIFERENTE do esperado")), flush=True)
    except KeyboardInterrupt:
        print("\nInterrompido: o que já foi feito está guardado; volte a correr para continuar.")
    meta["segundos_total"] = round(time.perf_counter() - t_total); guardar(saida, meta, linhas)
    print(f"\nFeito. Envie-me este ficheiro: {saida}"); return 0

def correr_regras():
    for nome, f in list(globals().items()):
        if nome.startswith("teste_"):
            f(); print(f"PASSOU {nome}")

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    args = sys.argv[1:]
    correr_regras()
    if "--so-regras" not in args: sys.exit(correr_sinteticos(args))