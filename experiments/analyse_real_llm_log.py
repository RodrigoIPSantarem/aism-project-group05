"""E6: métricas das análises com o modelo de linguagem real (Ollama local) no portátil Windows do grupo, 13/11/2026.

Entrada: experiments/results/real_llm/session_2026-11-13.log (o registo de sessão do próprio sistema) e o registo de
divergências escrito pelo agente Comparador. Saída: experiments/results/e6_real_llm.json
Utilização: python experiments/analyse_real_llm_log.py
"""
import collections, csv, datetime, json, re, statistics
from pathlib import Path

D = Path(__file__).resolve().parent / "results"
LOG = D / "real_llm" / "session_2026-11-13.log"
PAD = re.compile(r"^(\d\d:\d\d:\d\d)\s+(\S+)\s+\[([^\]]+)\]\s+(.*)$")

def main():
    linhas = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    ev = [PAD.match(l.strip()).groups() for l in linhas if PAD.match(l.strip())]
    hora = lambda s: datetime.datetime.strptime(s, "%H:%M:%S")
    fins = [re.search(r"={5,} (\S+) · (.+?) · .*?(\d+) s", l) for l in linhas]
    total = {f.group(1): int(f.group(3)) for f in fins if f}
    inicio, dur, falhas, chamadas = {}, collections.defaultdict(list), collections.Counter(), collections.Counter()
    for h, tk, ag, msg in ev:
        a = ag.split()[0]
        if a in ("A2.5", "A24") and ("a ler" in msg or "Passo -1" in msg): inicio[(tk, a)] = hora(h); chamadas[a] += 1
        elif a in ("A2.5", "A24") and (tk, a) in inicio and ("T1 " in msg or "círculo:" in msg or "indisponível" in msg):
            d = (hora(h) - inicio.pop((tk, a))).seconds
            if "indisponível" in msg: falhas[a] += 1
            else: dur[a].append(d)
        elif "indisponível" in msg: falhas[a] += 1; chamadas[a] += 1
        elif a == "A4" and "aceite" in msg: chamadas[a] += 1
    fal25 = {tk for h, tk, ag, m in ev if ag.startswith("A2.5") and "indisponível" in m}
    ok25 = [m for h, tk, ag, m in ev if ag.startswith("A2.5") and m.startswith("T1 ") and tk not in fal25]
    ok24 = [m for h, tk, ag, m in ev if ag.startswith("A24") and "· moat:" in m]
    c = lambda lst, rx: dict(collections.Counter(re.search(rx, m).group(1) for m in lst if re.search(rx, m)))
    div = list(csv.DictReader(open(D / "real_llm" / "divergences_2026-11-13.csv", encoding="utf-8-sig"), delimiter=";"))
    s = sorted(total.values())
    out = {"analyses": len(total), "seconds_median": statistics.median(s), "seconds_p90": s[int(0.9 * len(s))], "seconds_max": max(s),
           "llm_call_seconds_median": {a: statistics.median(v) for a, v in dur.items()},
           "llm_call_seconds_max": {a: max(v) for a, v in dur.items()},
           "llm_calls_started": dict(chamadas), "llm_calls_failed": dict(falhas),
           "a25_answers_ok": len(ok25), "a25_T1": c(ok25, r"T1 (\w+)"), "a25_circle": c(ok25, r"círculo (\w+)"),
           "a25_C3": c(ok25, r"C3 (\w+)"), "a25_franchise_yes": c(ok25, r"franquia (\d)/4"),
           "a24_answers_ok": len(ok24), "a24_moat": c(ok24, r"· moat: (\w+)"), "a24_pricing_quote": c(ok24, r"poder de preço: (\w+)"),
           "v427": dict(collections.Counter(d["v427_veredicto"] for d in div)), "v424": dict(collections.Counter(d["v424_veredicto"] for d in div)),
           "same_decision": sum(d["decisao_igual"] == "True" for d in div), "same_quality": sum(d["qualidade_igual"] == "True" for d in div),
           "rows": len(div)}
    json.dump(out, open(D / "e6_real_llm.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in out.items(): print(k, ":", v)

if __name__ == "__main__":
    main()
