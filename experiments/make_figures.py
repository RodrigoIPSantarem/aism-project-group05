"""Desenha os gráficos do relatório a partir de experiments/results/*.csv.

Utilização: python experiments/make_figures.py              (português, em experiments/results/figures)
            python experiments/make_figures.py --lingua en  (inglês, em experiments/results/figures_en)
Precisa do matplotlib: pip install -r experiments/requirements-experiments.txt
"""
import argparse, csv, re, statistics
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RES = Path(__file__).resolve().parent / "results"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
AZUL, VERDE, LARANJA, CINZA, VERMELHO = "#1565C0", "#2E7D32", "#E65100", "#9E9E9E", "#C62828"

# Textos dos gráficos nas duas línguas
T = {
 "pt": {"v427": {"COMPRAR": "COMPRAR", "CAIXA DEDICADA": "CAIXA DEDICADA\n(qualidade OK,\npreço alto)", "REJEITAR": "REJEITAR"},
        "rev": "REVISÃO\nMANUAL",
        "n_empresas": "número de empresas", "veredictos": "Veredictos de {n} empresas reais (preços de 13 de novembro de 2026)",
        "n_rejeitadas": "número de empresas rejeitadas", "motivos": "Primeiro motivo de rejeição na v4.27 ({n} empresas rejeitadas)",
        "minimo": "mínimo (5 anos)", "anos": "anos de demonstrações financeiras", "cobertura": "Anos de dados obtidos, por fonte principal",
        "segundos": "segundos por análise (descarga dos dados + regras)", "empresas": "análises",
        "tempo": "Tempo de execução (mediana {m:.0f} s)", "mensagens_x": "mensagens FIPA-ACL por análise",
        "mensagens": "Mensagens por análise (E1 e E2, {n} análises)", "feito": "gráficos gravados em",
        "caminho": {4: "4\nrejeição\nimediata", 5: "5\nrejeição pelo\nAvaliador", 6: "6\nfluxo\ncompleto", 8: "8\ncom uma\nrevisão", 2: "2\nsem dados"},
        "segundos_e2": "segundos por análise (dados reais da SEC)", "tempo_e2": "Tempo por empresa real (E2, mediana {m:.0f} s)",
        "dec": ",",
        "cat": {"outro": "outro", "passo0": "Passo 0: fora do método\n(cíclica, REIT, MLP)", "dados": "dados insuficientes",
                "triagem": "triagem rápida {t}", "portoes": "Portões de qualidade (P1-P10)",
                "circulo": "círculo de competência", "commodity": "regra de commodity"}},
 "en": {"v427": {"COMPRAR": "BUY", "CAIXA DEDICADA": "WAIT\n(quality OK,\nprice too high)", "REJEITAR": "REJECT"},
        "rev": "MANUAL\nREVIEW",
        "n_empresas": "number of companies", "veredictos": "Verdicts for {n} real companies (13 November 2026 prices)",
        "n_rejeitadas": "number of rejected companies", "motivos": "First reason for rejection under v4.27 ({n} rejected companies)",
        "minimo": "minimum (5 years)", "anos": "years of financial statements", "cobertura": "Years of data obtained, by primary source",
        "segundos": "seconds per analysis (data download + rules)", "empresas": "analyses",
        "tempo": "Run time (median {m:.0f} s)", "mensagens_x": "FIPA-ACL messages per analysis",
        "mensagens": "Messages per analysis (E1 and E2, {n} analyses)", "feito": "figures written to",
        "caminho": {4: "4\nimmediate\nrejection", 5: "5\nrejected by\nValuator", 6: "6\nfull\nflow", 8: "8\nwith one\nrevision", 2: "2\nno data"},
        "segundos_e2": "seconds per analysis (real SEC data)", "tempo_e2": "Time per real company (E2, median {m:.0f} s)",
        "dec": ".",
        "cat": {"outro": "other", "passo0": "Step 0: outside the method\n(cyclical, REIT, MLP)", "dados": "insufficient data",
                "triagem": "quick screen {t}", "portoes": "quality gates (P1-P10)",
                "circulo": "circle of competence", "commodity": "commodity rule"}},
}

def ler(nome):
    f = RES / f"{nome}.csv"
    if not f.exists(): return []
    with f.open(encoding="utf-8") as fh: return list(csv.DictReader(fh))

def categoria_motivo(m: str, lingua: str = "pt") -> str:
    """Primeiro motivo de uma rejeição na v4.27, agrupado pelo passo do protocolo."""
    c = T[lingua]["cat"]
    if not m: return c["outro"]
    if m.startswith("Passo 0"): return c["passo0"]
    if "dados insuficientes" in m.lower() or "anos de demonstrações" in m or "Dados insuficientes" in m or "incompleto" in m:
        return c["dados"]
    t = re.match(r"Triagem (T\d)", m)
    if t: return c["triagem"].format(t=t.group(1))
    if m.startswith("Portões falhados"): return c["portoes"]
    if m.startswith("Passo -1") or "Círculo" in m: return c["circulo"]
    if "Regra de Commodity" in m or "commodity" in m.lower(): return c["commodity"]
    return c["outro"]

def fig_veredictos(e3, L, pasta):
    ok = [l for l in e3 if l.get("ok") == "True"]
    c27 = Counter(l["v427"] for l in ok)
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    chaves = list(L["v427"]); vals = [c27.get(k, 0) for k in chaves]
    b = ax.bar([L["v427"][k] for k in chaves], vals, color=[VERDE, LARANJA, VERMELHO], alpha=0.85)
    ax.bar_label(b, padding=2); ax.set_ylabel(L["n_empresas"]); ax.set_ylim(0, max(vals + [1]) * 1.18)
    ax.set_title(L["veredictos"].format(n=len(ok)), fontsize=10)
    fig.tight_layout(); fig.savefig(pasta / "fig3_verdicts.png", dpi=200); plt.close(fig)

def fig_motivos(e3, L, pasta, lingua):
    ok = [l for l in e3 if l.get("ok") == "True" and l["v427"] == "REJEITAR"]
    cnt = Counter(categoria_motivo(l["v427_reason"], lingua) for l in ok)
    itens = sorted(cnt.items(), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(7, 3.6))
    b = ax.barh([k for k, _ in itens], [v for _, v in itens], color=AZUL, alpha=0.85)
    ax.bar_label(b, padding=2); ax.set_xlabel(L["n_rejeitadas"])
    ax.set_title(L["motivos"].format(n=len(ok)), fontsize=10)
    ax.set_xlim(0, max(cnt.values() or [1]) * 1.15)
    fig.tight_layout(); fig.savefig(pasta / "fig4_rejection_reasons.png", dpi=200); plt.close(fig)

def fig_cobertura(e3, L, pasta):
    ok = [l for l in e3 if l.get("ok") == "True"]
    por = {}
    for l in ok: por.setdefault(l["source"], []).append(int(l["years"]))
    ordem = [s for s in ("SEC US-GAAP", "SEC IFRS", "ESEF", "Yahoo") if s in por]
    fig, ax = plt.subplots(figsize=(7, 3.3))
    ax.boxplot([por[s] for s in ordem], showmeans=True, widths=0.5)
    ax.set_xticks(range(1, len(ordem) + 1), [f"{s}\n(n = {len(por[s])})" for s in ordem])
    ax.axhline(5, color=VERMELHO, ls="--", lw=1); ax.text(len(ordem) + 0.42, 5.15, L["minimo"], color=VERMELHO, fontsize=8, ha="right")
    ax.set_ylabel(L["anos"]); ax.set_ylim(0, 11)
    ax.set_title(L["cobertura"], fontsize=10)
    fig.tight_layout(); fig.savefig(pasta / "fig5_coverage.png", dpi=200); plt.close(fig)

def fig_custo(L, pasta):
    """E5: mensagens FIPA-ACL por análise na versão de 5 agentes (execuções da E1 e da E2)."""
    e1, e2 = ler("e1_synthetic"), ler("e2_manual_baseline")
    msg = [int(l["messages"]) for l in e1 + e2 if l.get("ok") == "True" and l.get("messages")]
    msg += [2 for l in e1 + e2 if l.get("ok") == "False"]          # o Coletor falhou: pedido e failure
    if not msg: return
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    c = Counter(msg); ks = sorted(c)
    b = ax.bar([L["caminho"].get(k, str(k)) for k in ks], [c[k] for k in ks], color=AZUL, alpha=0.85, width=0.6)
    ax.bar_label(b, padding=2); ax.set_ylabel(L["empresas"]); ax.set_ylim(0, max(c.values()) * 1.2)
    ax.set_title(L["mensagens"].format(n=len(msg)), fontsize=10); ax.tick_params(axis="x", labelsize=8.5)
    fig.tight_layout(); fig.savefig(pasta / "fig6_cost.png", dpi=200); plt.close(fig)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--lingua", choices=["pt", "en"], default="pt")
    lingua = ap.parse_args().lingua
    pasta = RES / ("figures" if lingua == "pt" else "figures_en"); pasta.mkdir(parents=True, exist_ok=True)
    L = T[lingua]
    # só as empresas cujos dados vieram da SEC: é a fonte real que o programa usa (o dataset sintético está na E1)
    e3 = [l for l in ler("e3_universe") if l.get("source", "").startswith("SEC")]
    if e3:
        fig_veredictos(e3, L, pasta); fig_motivos(e3, L, pasta, lingua); fig_cobertura(e3, L, pasta); fig_custo(L, pasta)
        print(L["feito"], pasta)
    else: print("corre primeiro experiments/run_experiments.py (faltam os resultados da E3)")
