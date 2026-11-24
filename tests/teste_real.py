"""Teste real: analisa empresas REAIS (dados da SEC) com o modelo de linguagem real (Ollama), e guarda tudo num só JSON.
As empresas sintéticas (AURORA, BOREAL...) não entram aqui: testam-se com tests/test_agentes.py (python -m pytest -q).

O ficheiro resultante serve para analisar, empresa a empresa, o veredicto das regras, as respostas do modelo, as objeções do
Crítico e o veredicto final. Não usa nenhum modelo simulado: é o mesmo caminho da interface e da linha de comandos.

Utilização (na pasta do projeto, com o Ollama aberto):
    python experiments/teste_real.py                      (as 14 empresas por defeito, cerca de 1 hora e meia)
    python experiments/teste_real.py --tickers KO,AAPL    (só estas)
    python experiments/teste_real.py --continuar          (retoma: salta as empresas que já estão no ficheiro de saída)
    python experiments/teste_real.py --sem-cache          (pergunta sempre ao modelo, em vez de reutilizar respostas guardadas)
Por defeito analisa SEMPRE todas as empresas pedidas, de raiz. O resultado fica em saidas/teste_real.json (atualizado depois de
cada empresa). Perguntas idênticas a uma análise anterior reutilizam a resposta guardada (cache em dados/cache_llm): saem em segundos.
"""
import argparse, datetime, json, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from nucleo.analisar import analisar                                       # noqa: E402
from nucleo.configuracao import garantir_env, modelos_ollama, tem_modelo   # noqa: E402
from nucleo.llm import _criar_llm                                          # noqa: E402
from nucleo.util import _carregar_env                                      # noqa: E402

# Primeiro as que já correram no vosso computador (saem rápido, por causa da cache); depois as novas, para dar resultados cedo.
# V e ASML são rejeitadas em segundos (dados insuficientes e Passo 0): mostram os caminhos sem modelo.
POR_DEFEITO = ["KO", "AAPL", "PG", "MA", "ROL", "V", "ASML",
               "MSFT", "ROK", "AME", "POOL", "CHD", "JNJ", "UL"]

def _eventos(r, nome):
    return [e[3] for e in (r.get("_eventos") or []) if e[0] == "evento" and e[1] == nome]

def _escalares(d):
    return {k: v for k, v in (d or {}).items() if isinstance(v, (int, float, str, bool)) or v is None}

def resumir(ticker, fonte, r, dt, chamadas_llm):
    if r.get("performativa") == "failure":
        return {"ticker": ticker, "fonte": fonte, "ok": False, "erro": str(r.get("motivo", ""))[:300], "segundos": round(dt, 1)}
    op = r.get("oportunidade") or {}
    d = r.get("dados") or {}; e = d.get("empresa") or {}
    qual = (_eventos(r, "avaliador_qualitativa") or [{}])[-1]
    qual = {k: v for k, v in qual.items() if k != "textos_fontes"}           # os textos das fontes são enormes e já estão no relatório
    criticas = _eventos(r, "critico_resultado")
    decisor = (_eventos(r, "decisor_veredicto") or [{}])[-1]
    return {
        "ticker": ticker, "fonte": fonte, "ok": True, "empresa": e.get("nome"), "setor": e.get("setor"),
        "veredicto_final": op.get("categoria"),                       # o que o utilizador vê
        "veredicto_das_regras": op.get("categoria_regras") or op.get("categoria"),   # igual ao veredicto final; a ressalva vai em "decisor"/"descricao"
        "descricao": op.get("descricao"), "limite": op.get("limite"),
        "portoes_ok": r.get("portoes_ok"), "motivos": r.get("motivos"),
        "avaliacao": _escalares(r.get("avaliacao")),
        "respostas_do_modelo": qual,                                   # T1, Círculo, Wrigley, modelo, C2, C3, Franquia, dúvidas
        "rondas_do_critico": [{"objecoes": c.get("objecoes"), "graves": len(c.get("graves") or []),
                               "pediu_revisao": c.get("pediu_revisao")} for c in criticas],
        "revisoes": r.get("revisoes", (r.get("dados") or {}).get("revisoes", 0)),
        "mensagens": [m["performativa"] + ": " + m["remetente"] + " -> " + m["destinatario"] for m in (r.get("_msgs") or [])],
        "avisos": r.get("_avisos"), "segundos": r.get("_segundos", round(dt, 1)),
        "chamadas_ao_modelo": chamadas_llm,
        "decisor": decisor, "relatorio": r.get("relatorio"),
    }

def guardar(caminho, meta, linhas):
    cont = {}
    for l in linhas:
        k = l.get("veredicto_final") or ("ERRO" if not l.get("ok") else "?")
        cont[k] = cont.get(k, 0) + 1
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"meta": meta, "contagem_por_veredicto": cont, "empresas": linhas},
                                  ensure_ascii=False, indent=1, default=str), encoding="utf-8")

def main():
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    p = argparse.ArgumentParser(description="Teste real com o modelo de linguagem e a SEC; devolve um JSON.")
    p.add_argument("--tickers", help="lista separada por vírgulas (defeito: " + ",".join(POR_DEFEITO) + ")")
    p.add_argument("--anos", type=int, choices=[5, 10], default=10)
    p.add_argument("--saida", default=str(RAIZ / "saidas" / "teste_real.json"))
    p.add_argument("--continuar", action="store_true", help="retoma: salta as empresas que já estão no ficheiro de saída")
    p.add_argument("--sem-cache", action="store_true", help="pergunta sempre ao modelo, sem reutilizar respostas guardadas")
    a = p.parse_args()
    garantir_env(); _carregar_env()
    llm = _criar_llm(RAIZ / "dados" / "cache_llm")
    llm.usar_cache = not a.sem_cache
    inst = modelos_ollama()
    if inst is None: print("ERRO: o Ollama não está a correr. Abra o Ollama e volte a correr."); sys.exit(2)
    if not tem_modelo(llm.modelo, inst): print(f"ERRO: o modelo {llm.modelo} não está instalado: ollama pull {llm.modelo}"); sys.exit(2)

    print("A carregar o modelo na memória (pode demorar um minuto)...", flush=True); llm.aquecer()
    lista = [t.strip().upper() for t in (a.tickers.split(",") if a.tickers else POR_DEFEITO) if t.strip()]
    saida = Path(a.saida)
    feitas = {}
    if saida.exists() and a.continuar:
        try: feitas = {l["ticker"]: l for l in json.loads(saida.read_text(encoding="utf-8")).get("empresas", []) if l.get("ok")}
        except Exception: feitas = {}
    meta = {"data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "modelo": f"{llm.backend}:{llm.modelo}",
            "anos": a.anos, "pedidas": lista}
    linhas = [feitas[t] for t in lista if t in feitas]
    if linhas: print(f"Já feitas (ignoradas): {', '.join(l['ticker'] for l in linhas)}")
    t_total = time.perf_counter()
    try:
        for i, t in enumerate(lista, 1):
            if t in feitas: continue
            fonte = "sec"                                  # só empresas reais; as sintéticas testam-se com tests/test_agentes.py
            print(f"[{i}/{len(lista)}] {t} ({fonte}) ...", flush=True)
            n0 = len(llm.metricas); t0 = time.perf_counter()
            try: r = analisar(t, a.anos, fonte, llm, mostrar=False, jsonl=RAIZ / "saidas" / f"{t}.jsonl")
            except Exception as e: r = {"performativa": "failure", "motivo": f"{type(e).__name__}: {e}"}
            dt = time.perf_counter() - t0
            linha = resumir(t, fonte, r, dt, len(llm.metricas) - n0)
            linhas.append(linha)
            meta["terminado_em"] = datetime.datetime.now().strftime("%H:%M")
            guardar(saida, meta, linhas)                                      # guarda depois de cada empresa
            print(f"      {linha.get('veredicto_final', 'ERRO')} · {linha.get('segundos')} s · "
                  f"{linha.get('chamadas_ao_modelo', 0)} chamadas ao modelo", flush=True)
    except KeyboardInterrupt:
        print("\nInterrompido: o que já foi feito está guardado; volte a correr para continuar.")
    meta["segundos_total"] = round(time.perf_counter() - t_total)
    guardar(saida, meta, linhas)
    print(f"\nFeito. Envie-me este ficheiro: {saida}")

if __name__ == "__main__":
    main()