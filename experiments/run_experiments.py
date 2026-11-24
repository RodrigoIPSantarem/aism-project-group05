"""Experiências apresentadas na Secção 5 do relatório do projeto.

E1  Dataset sintético: cada empresa de teste produz o comportamento para que foi desenhada?
E2  Base manual: concordância com as 13 empresas que o grupo analisou à mão (aplicação manual do protocolo).
E3  Universo de mercado real (110 empresas da SEC): cobertura dos dados e veredictos.
E4  Salvaguardas: dados em falta, citações inventadas, números inventados, crítica sem fim, sem modelo de linguagem.
E5  Custo da coordenação: mensagens e tempo por análise (a partir das execuções da E1 e da E2; gráfico em make_figures.py).

O modelo de linguagem é substituído por modelos simulados (experiments/llm_scripted.py), para que os resultados
sejam reprodutíveis e isolem as camadas dos dados, das regras, da avaliação e da coordenação.

Utilização:  python experiments/run_experiments.py              (tudo; a E3 descarrega dados, cerca de 1 hora)
             python experiments/run_experiments.py --rapido     (só E1, E2 e E4)
             python experiments/run_experiments.py --so e1,e4   (só as experiências indicadas)
Os nomes das colunas dos ficheiros CSV ficam em inglês curto, como identificadores.
"""
import argparse, copy, csv, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from config import TICKERS_E3                                            # noqa: E402
from experiments.llm_scripted import (AlwaysObjectingCritic, FabricatedNumberLLM, FabricatedQuoteLLM,  # noqa: E402
                                      ScriptedLLM)
from nucleo.analisar import analisar                                          # noqa: E402

OUT = RAIZ / "experiments" / "results"
MANUAL_V424 = {"VICI": "VICI Properties", "ROL": "Rollins", "BMI": "Badger Meter", "MSFT": "Microsoft", "AZN": "AstraZeneca",
               "SPOT": "Spotify", "CL": "Colgate-Palmolive", "ASML": "ASML", "KRZ.IR": "Kerry Group", "SNY": "Sanofi",
               "MA": "Mastercard", "PG": "Procter & Gamble", "NVO": "Novo Nordisk"}

def correr(ticker, fonte, llm):
    t0 = time.perf_counter()
    try: r = analisar(ticker, 10, fonte, llm, mostrar=False)
    except Exception as e: r = {"performativa": "failure", "motivo": f"{type(e).__name__}: {e}"}
    return r, time.perf_counter() - t0

def resumo(ticker, r, dt, grupo=""):
    if r.get("performativa") == "failure":
        return {"ticker": ticker, "group": grupo, "ok": False, "error": str(r.get("motivo", ""))[:160], "seconds": round(dt, 1)}
    d = r.get("dados") or {}; e = d.get("empresa") or {}; av = r.get("avaliacao") or {}
    org = d.get("origem_dados") or {}
    anos = d.get("anos") or []; n_campos = len(d.get("series") or {})
    fonte = str(e.get("fonte") or "")
    tipo = ("SEC US-GAAP" if "US-GAAP" in fonte else "SEC IFRS" if "SEC" in fonte else "ESEF" if "ESEF" in fonte
            else "Yahoo" if "Yahoo" in fonte else "sintético" if "sint" in fonte.lower() else fonte[:20])
    reserva = sum(1 for k, x in org.items() if str(x).startswith(("yfinance", "Alpha")))
    motivo = (r.get("motivos") or [""])[0]
    return {"ticker": ticker, "group": grupo, "ok": True, "company": (e.get("nome") or "")[:40], "source": tipo,
            "currency": e.get("moeda_relatorio") or "", "years": len(anos), "cells": n_campos * len(anos),
            "missing": len(d.get("em_falta") or []), "filled_by_fallback": reserva,
            "v427": (r.get("oportunidade") or {}).get("categoria"), "gates_passed": r.get("portoes_ok"),
            "v427_reason": motivo[:160], "tace": av.get("tace"), "pmc": av.get("pmc"), "price": av.get("preco"),
            "messages": len(r.get("_msgs") or []), "revisions": r.get("revisoes", 0), "seconds": round(dt, 1)}

def escrever(nome, linhas):
    OUT.mkdir(parents=True, exist_ok=True)
    if not linhas: return
    campos = sorted({k for l in linhas for k in l}, key=lambda k: list(linhas[0]).index(k) if k in linhas[0] else 99)
    with (OUT / f"{nome}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos); w.writeheader(); w.writerows(linhas)

# ─────────────────────────────── E1 dataset sintético
ESPERADO = {
    "AURORA": ("franquia excelente abaixo do preço máximo: COMPRAR", lambda r: r["v427"] == "COMPRAR"),
    "BOREAL": ("excelente, preço um pouco acima do valor: esperar (caixa dedicada)", lambda r: r["v427"] == "CAIXA DEDICADA"),
    "CASTOR": ("excelente mas muito cara: esperar (caixa dedicada)", lambda r: r["v427"] == "CAIXA DEDICADA"),
    "DUNA": ("empresa muito boa: passa os Portões de qualidade", lambda r: r["v427"] in ("COMPRAR", "CAIXA DEDICADA")),
    "ESTEIO": ("empresa razoável perto do valor justo: não comprar", lambda r: r["v427"] != "COMPRAR"),
    "FAROL": ("empresa fraca: rejeitar", lambda r: r["v427"] == "REJEITAR"),
    "GRANITO": ("fluxo de caixa operacional negativo: rejeitar na triagem T7", lambda r: r["v427"] == "REJEITAR" and "T7" in r["v427_reason"]),
    "HORIZONTE": ("energia: fora do método (Passo 0)", lambda r: r["v427"] == "REJEITAR" and "Passo 0" in r["v427_reason"]),
    "IRIS": ("diluição de 19% em 3 anos: rejeitar na triagem T6", lambda r: r["v427"] == "REJEITAR" and "T6" in r["v427_reason"]),
    "JADE": ("goodwill alto, só por si, não é regra de rejeição na v4.27", lambda r: "goodwill" not in r["v427_reason"].lower()),
    "LINCE": ("beta alto é ignorado pela v4.27", lambda r: "beta" not in r["v427_reason"].lower()),
    "MARE": ("transportes: fora do método (Passo 0)", lambda r: r["v427"] == "REJEITAR" and "Passo 0" in r["v427_reason"]),
    "NEVOA": ("fluxo de caixa apagado em 3 de 5 anos: dados insuficientes, nada inventado",
              lambda r: r["v427"] == "REJEITAR" and r["missing"] > 0),
    "ORLA": ("só 3 anos de histórico: dados insuficientes", lambda r: r["v427"] == "REJEITAR"),
    "PRISMA": ("rótulos desconhecidos mapeados pelo Coletor", lambda r: r["years"] >= 5 and r["missing"] < r["cells"]),
    "QUARTZO": ("promessas da gestão não contam: rejeitar na triagem T3", lambda r: r["v427"] == "REJEITAR" and "T3" in r["v427_reason"]),
    "SILEX": ("dados incoerentes (lucro acima da receita): rejeitar", lambda r: r["v427"] == "REJEITAR"),
    "TEJO": ("beta não divulgado: a análise continua", lambda r: r["gates_passed"] is not None),
    "NVO": ("5 anos e sem lucro bruto: dados insuficientes", lambda r: r["v427"] == "REJEITAR"),
}

def e1():
    linhas = []
    for t, (desc, teste) in ESPERADO.items():
        r, dt = correr(t, "sintetico", ScriptedLLM())
        s = resumo(t, r, dt, "sintético"); s["expected"] = desc
        s["passed"] = bool(s.get("ok") and teste(s)); linhas.append(s)
        print(f"E1 {t:9} {'PASSOU' if s['passed'] else 'FALHOU'}  {s.get('v427')}  {s.get('v427_reason', '')[:70]}")
    escrever("e1_synthetic", linhas); return linhas

# ─────────────────────────────── E2 base manual (análise à mão: todas NÃO COMPRAR)
def e2():
    linhas = []
    for t, nome in MANUAL_V424.items():
        r, dt = correr(t, "sec", ScriptedLLM())
        s = resumo(t, r, dt, "base manual"); s["manual"] = "NÃO COMPRAR"; s["name"] = nome
        s["agrees_manual"] = bool(s.get("ok") and s.get("v427") != "COMPRAR")
        linhas.append(s); escrever("e2_manual_baseline", linhas)      # gravado a cada empresa
        print(f"E2 {t:7} {s.get('v427')} (manual NÃO COMPRAR) · {s.get('error', '')[:60]}", flush=True)
    return linhas

# ─────────────────────────────── E3 universo de mercado real
def e3(grupos=None, saltar=()):
    linhas = []; ja = set(saltar)
    fc = OUT / "e3_universe.csv"
    if fc.exists():                                   # retomar uma execução interrompida
        with fc.open(encoding="utf-8") as f: linhas = list(csv.DictReader(f))
        ja |= {l["ticker"] for l in linhas}
    for g, lst in TICKERS_E3.items():
        if grupos and g not in grupos: continue
        for t in lst:
            if t in ja: continue
            r, dt = correr(t, "sec", ScriptedLLM()); s = resumo(t, r, dt, g); linhas.append(s); ja.add(t)
            print(f"E3 {g[:12]:12} {t:9} {'ok' if s['ok'] else 'ERRO'} {s.get('source', '')} {s.get('years', '')} anos "
                  f"{s.get('v427')} {s.get('seconds')}s", flush=True)
            escrever("e3_universe", linhas)
    return linhas

# ─────────────────────────────── E4 salvaguardas
def _apagar(ticker, campos, anos):
    """Cópia de uma empresa sintética com alguns campos apagados (o sistema não os pode inventar)."""
    import fontes.sintetico as sint
    orig = sint._sint_obter
    def falso(t):
        b = copy.deepcopy(orig(t))
        if t.upper() == ticker:
            for a in anos:
                for c in campos: b["financials"].get(str(a), {}).pop(c, None)
        return b
    return orig, falso

def e4():
    import agentes.coletor as col
    out = []
    def caso(nome, passou, evidencia):
        out.append({"guardrail": nome, "passed": bool(passou), "evidence": evidencia[:220]})
        print(f"E4 {'PASSOU' if passou else 'FALHOU'}  {nome}: {evidencia[:110]}")
    cat = lambda r: (r.get("oportunidade") or {}).get("categoria")
    # G1 dados em falta: apagar o fluxo de caixa operacional dos últimos 3 anos do caso COMPRAR
    orig, falso = _apagar("AURORA", ["Operating Cash Flow", "fco"], [2023, 2024, 2025])
    col._sint_obter = falso
    try: r, _ = correr("AURORA", "sintetico", ScriptedLLM())
    finally: col._sint_obter = orig
    d = r.get("dados") or {}; fco = (d.get("series") or {}).get("fco") or {}
    inventado = any(fco.get(a) is not None for a in (2023, 2024, 2025))
    caso("G1 fluxo de caixa apagado não é inventado", not inventado and cat(r) != "COMPRAR",
         f"FCO 2023-2025 = {[fco.get(a) for a in (2023, 2024, 2025)]}; veredicto {cat(r)}")
    # G2 citação de preços inventada: o teste C3 não passa e o caso COMPRAR deixa de passar o Portão P8
    r, _ = correr("AURORA", "sintetico", FabricatedQuoteLLM())
    c3 = next((x for x in (r.get("testes") or {}).get("C", []) if x["id"] == "C3"), {})
    caso("G2 citação inventada rejeitada (teste C3)", c3.get("resposta") != "Sim" and cat(r) != "COMPRAR",
         f"C3 = {c3.get('resposta')}; veredicto {cat(r)}")
    # G3 número inventado pelo Avaliador: assinalado e transformado em objeção pelo Crítico
    r, _ = correr("AURORA", "sintetico", FabricatedNumberLLM())
    ver = ((r.get("dados") or {}).get("analise_qualitativa") or {}).get("verificacao") or []
    obj = [o["descricao"] for o in (r.get("critica") or {}).get("objecoes") or [] if "não vieram dos dados" in o["descricao"]]
    caso("G3 número que não está nos dados é assinalado pelo Crítico", bool(ver) and bool(obj), "; ".join(obj) or "não assinalado")
    # G4 um Crítico que objeta sempre: no máximo uma revisão, e depois o fluxo termina
    r, _ = correr("AURORA", "sintetico", AlwaysObjectingCritic())
    rej = [m for m in r.get("_msgs") or [] if m["performativa"] == "reject-proposal"]
    caso("G4 ciclo de crítica limitado (máx. 1 revisão)", r.get("revisoes") == 1 and len(rej) == 1,
         f"revisões {r.get('revisoes')}; mensagens reject-proposal {len(rej)}; total de mensagens {len(r.get('_msgs') or [])}")
    # G5 sem modelo de linguagem: nunca comprar sem as verificações qualitativas
    r, _ = correr("AURORA", "sintetico", None)
    caso("G5 sem modelo de linguagem: falha em segurança (sem COMPRAR)", cat(r) != "COMPRAR", f"veredicto {cat(r)}")
    # G6 dados incoerentes assinalados
    r, _ = correr("SILEX", "sintetico", ScriptedLLM())
    inc = (r.get("dados") or {}).get("inconsistencias") or []
    caso("G6 dados incoerentes assinalados e rejeitados", bool(inc) and cat(r) == "REJEITAR", f"{len(inc)} incoerências; veredicto {cat(r)}")
    escrever("e4_guardrails", out); return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--rapido", action="store_true"); ap.add_argument("--so", default="")
    a = ap.parse_args()
    so = set(a.so.split(",")) if a.so else {"e1", "e2", "e3", "e4"}
    res = {}
    if "e1" in so: res["e1"] = e1()
    if "e4" in so: res["e4"] = e4()
    if "e2" in so: res["e2"] = e2()
    if "e3" in so and not a.rapido: res["e3"] = e3()
    print("resultados em", OUT)
