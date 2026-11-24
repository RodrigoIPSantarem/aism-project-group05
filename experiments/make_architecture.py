"""Figura 1 do relatório: arquitetura dos 5 agentes, em português e em inglês (matplotlib).
Utilização:  python experiments/make_architecture.py [pasta_de_saida]

Segue a figura da proposta: azul = agente que usa o modelo de linguagem; verde = agente só com regras em Python;
seta laranja = revisão pedida pelo Crítico (no máximo uma); seta vermelha tracejada = rejeição imediata (direta ao Decisor)."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

T = {
 "pt": dict(ent=("ENTRADA", "ticker e anos (5 ou 10)"), fonte=("FONTE DE DADOS", "SEC EDGAR (10-K, 20-F)\nou dataset sintético"),
            a1=("A1 Coletor", "obtém e normaliza\nos dados (JSON)"), a2=("A2 Guardião", "regras de exclusão\n(triagem, setor)"),
            a3=("A3 Avaliador", "perguntas qualitativas\n+ testes, Portões, preço"), a4=("A4 Crítico", "procura falhas\n(regras + modelo)"),
            a5=("A5 Decisor", "veredicto e relatório"),
            rel=("RELATÓRIO", "COMPRAR / CAIXA DEDICADA / REVISÃO MANUAL / REJEITAR\n+ motivos e objeções do Crítico"),
            rev="reject-proposal: revisão pedida pelo Crítico (máx. 1)", rej="inform: rejeição imediata (Guardião ou Avaliador)",
            leg_llm="usa o modelo de linguagem (Ollama, qwen2.5:7b)", leg_py="só regras em Python"),
 "en": dict(ent=("INPUT", "ticker and years (5 or 10)"), fonte=("DATA SOURCE", "SEC EDGAR (10-K, 20-F)\nor synthetic dataset"),
            a1=("A1 Collector", "gets and normalises\nthe data (JSON)"), a2=("A2 Guardian", "exclusion rules\n(screen, sector)"),
            a3=("A3 Evaluator", "qualitative questions\n+ tests, Gates, price"), a4=("A4 Critic", "looks for flaws\n(rules + model)"),
            a5=("A5 Decider", "verdict and report"),
            rel=("REPORT", "BUY / DEDICATED CASH / MANUAL REVIEW / REJECT\n+ reasons and the Critic's objections"),
            rev="reject-proposal: revision requested by the Critic (max. 1)", rej="inform: immediate rejection (Guardian or Evaluator)",
            leg_llm="uses the language model (Ollama, qwen2.5:7b)", leg_py="Python rules only"),
}
LLM = ("#E4EEFA", "#2D6CB5"); PY = ("#E3F3EA", "#2E8B57"); NEU = ("#F2F4F7", "#8A94A6")
SETA, LAR, VER = "#3B4A5E", "#D9822B", "#C42B2B"

def caixa(ax, cx, cy, w, h, titulo, corpo, cores):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                fc=cores[0], ec=cores[1], lw=1.6))
    ax.text(cx, cy + h / 2 - 2.1, titulo, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#16202C")
    ax.text(cx, cy - 1.4, corpo, ha="center", va="center", fontsize=8.6, color="#2B3646", linespacing=1.25)

def seta(ax, p0, p1, txt="", cor=SETA, estilo="-", lw=1.4, dy=1.3, ha="center"):
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="-|>", color=cor, lw=lw, ls=estilo, shrinkA=0, shrinkB=0))
    if txt: ax.text((p0[0] + p1[0]) / 2 + (1.0 if ha == "left" else 0), (p0[1] + p1[1]) / 2 + dy, txt, ha=ha, va="bottom", fontsize=7.8, color=cor)

def figura(L, destino):
    fig, ax = plt.subplots(figsize=(10.5, 4.2)); ax.set_xlim(0, 110); ax.set_ylim(0, 44); ax.axis("off")
    W, H, yt, yb = 15.6, 10, 26, 8
    xs = [10, 32, 54, 76, 98]
    caixa(ax, xs[0], yt, W, H, *L["ent"], NEU); caixa(ax, xs[1], yt, W, H, *L["a1"], LLM)
    caixa(ax, xs[2], yt, W, H, *L["a2"], PY); caixa(ax, xs[3], yt, W, H, *L["a3"], LLM); caixa(ax, xs[4], yt, W, H, *L["a4"], LLM)
    caixa(ax, xs[4], yb, W, H, *L["a5"], LLM); caixa(ax, xs[0], yb, W, H, *L["fonte"], NEU)
    caixa(ax, 52, yb, 42, H, *L["rel"], NEU)
    m = W / 2 + 0.6
    for a, b, t in ((0, 1, "request"), (1, 2, "inform"), (2, 3, "request"), (3, 4, "propose")):
        seta(ax, (xs[a] + m, yt - 1), (xs[b] - m, yt - 1), t)
    seta(ax, (xs[4], yt - H / 2 - 0.6), (xs[4], yb + H / 2 + 0.6), "inform", dy=0, ha="left")
    seta(ax, (xs[4] - m, yb), (73 + 0.6, yb), "inform")
    seta(ax, (xs[0] + m, yb + 2), (xs[1] - 3, yt - H / 2 - 0.6), "", cor="#8A94A6", estilo=":")
    # revisão (Crítico -> Avaliador), por cima
    ax.plot([xs[4], xs[4], xs[3] + 3], [yt + H / 2 + 0.6, 39, 39], color=LAR, lw=1.8)
    seta(ax, (xs[3] + 3, 39), (xs[3] + 3, yt + H / 2 + 0.6), cor=LAR, lw=1.8)
    ax.text((xs[3] + xs[4]) / 2, 40, L["rev"], ha="center", va="bottom", fontsize=8.6, color="#B35A00", fontweight="bold")
    # rejeição imediata (Guardião -> Decisor), entre as duas filas
    ax.plot([xs[2], xs[2], xs[4] - 5], [yt - H / 2 - 0.6, 17, 17], color=VER, lw=1.5, ls="--")
    seta(ax, (xs[4] - 5, 17), (xs[4] - 5, yb + H / 2 + 0.6), cor=VER, estilo="--", lw=1.5)
    ax.text((xs[2] + xs[4]) / 2 - 3, 17.4, L["rej"], ha="center", va="bottom", fontsize=8.3, color=VER)
    # legenda
    for i, (txt, cores) in enumerate(((L["leg_llm"], LLM), (L["leg_py"], PY))):
        x = 1.5 + i * 40
        ax.add_patch(FancyBboxPatch((x, 39.2), 2.6, 2.2, boxstyle="round,pad=0.1", fc=cores[0], ec=cores[1], lw=1.3))
        ax.text(x + 3.6, 40.3, txt, va="center", fontsize=8.6, color="#2B3646")
    fig.tight_layout(pad=0.3); fig.savefig(destino, dpi=200); plt.close(fig)

if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "results"
    for lingua, pasta in (("pt", "figures"), ("en", "figures_en")):
        d = base / pasta; d.mkdir(parents=True, exist_ok=True)
        figura(T[lingua], d / "fig1_architecture.png"); print("gravado", d / "fig1_architecture.png")
