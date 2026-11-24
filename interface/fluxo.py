"""Faixa do fluxo dos agentes: os 5 agentes da proposta, desenhados num Canvas, que se acendem à medida que trabalham.

Cada caixa mostra o agente, o tipo (modelo de linguagem ou regras em Python), o estado e a última coisa que disse.
As setas mostram a performativa FIPA-ACL da última mensagem entre dois agentes. Por cima, o arco laranja é a revisão
que o Crítico pode pedir ao Avaliador (no máximo uma); por baixo, a linha vermelha é a rejeição imediata (direta ao
Decisor). É a mesma figura da proposta, mas viva: os estados mudam com as mensagens que a plataforma entrega."""
try:
    import tkinter as tk
except ImportError:      # sem interface gráfica: a linha de comandos continua a funcionar
    tk = None
from interface.tema import COR, f

AGENTES = [   # (nome interno, código, nome, tipo, cor do tipo, papel)
    ("coletor",   "A1", "Coletor",   "modelo + dados",   "llm", "obtém e normaliza os dados"),
    ("guardiao",  "A2", "Guardião",  "regras em Python", "py",  "regras de exclusão"),
    ("avaliador", "A3", "Avaliador", "modelo + cálculo", "llm", "testes, Portões e preço"),
    ("critico",   "A4", "Crítico",   "modelo + regras",  "llm", "procura falhas"),
    ("decisor",   "A5", "Decisor",   "regras + modelo",  "llm", "veredicto e relatório"),
]
_ROTULO = {"[A1": "coletor", "[A2": "guardiao", "[A3": "avaliador", "[A4": "critico", "[A5": "decisor"}
_ESTADOS = {   # estado -> (texto, cor do texto, cor e espessura do contorno)
    "espera":   ("à espera", COR["espera"], COR["borda"], 1),
    "ativo":    ("a trabalhar…", COR["dest"], COR["dest"], 3),
    "feito":    ("concluído", COR["ok"], None, 2),
    "rejeitou": ("rejeitou a empresa", COR["nao"], COR["nao"], 3),
    "revisao":  ("pediu revisão", COR["rev"], COR["rev"], 3),
    "falhou":   ("falhou", COR["nao"], COR["nao"], 3),
}


class FluxoMixin:
    """Desenha e atualiza a faixa dos agentes. Recebe as mensagens ("msg", ...) e as linhas ("log", ...) da plataforma."""

    def _fx_construir(self, pai):
        self._fx_cv = tk.Canvas(pai, height=222, bg=COR["painel"], highlightthickness=0)
        self._fx_cv.pack(fill="x")
        self._fx_cv.bind("<Configure>", lambda _: self._fx_desenhar())
        self._fx_repor()

    def _fx_repor(self):
        self._fx_estado = {a[0]: "espera" for a in AGENTES}
        self._fx_texto = {a[0]: a[5] for a in AGENTES}
        self._fx_perf = {}          # (remetente, destinatário) -> performativa da última mensagem
        self._fx_rev = False        # o Crítico pediu revisão?
        self._fx_rej = None         # quem rejeitou diretamente para o Decisor (guardiao ou avaliador)
        self._fx_fim = None         # resposta final ao utilizador (inform ou failure)
        if hasattr(self, "_fx_cv"): self._fx_desenhar()

    # ─── eventos
    def _fx_msg(self, perf, rem, dest, redesenhar=True):
        est = self._fx_estado
        if rem in est and est[rem] == "ativo": est[rem] = "feito"
        if perf == "reject-proposal": est[rem] = "revisao"; self._fx_rev = True
        if perf == "failure" and rem in est: est[rem] = "falhou"
        if dest == "decisor" and rem in ("guardiao", "avaliador") and perf == "inform":
            est[rem] = "rejeitou"; self._fx_rej = rem
        if dest in est: est[dest] = "ativo"
        if dest == "utilizador":
            self._fx_fim = perf
            for k, v in est.items():
                if v == "ativo": est[k] = "feito"
        self._fx_perf[(rem, dest)] = perf
        if redesenhar: self._fx_desenhar()

    def _fx_log(self, txt, redesenhar=True):
        s = txt.strip()
        for pref, ag in _ROTULO.items():
            if s.startswith(pref):
                corpo = s.split("]", 1)[-1].strip()
                if corpo: self._fx_texto[ag] = corpo
                if redesenhar: self._fx_desenhar()
                return

    def _fx_de_resultado(self, r):
        """Repõe a faixa a partir de um resultado guardado (histórico): mensagens e linhas pela ordem em que aconteceram."""
        self._fx_repor()
        for m in r.get("_msgs") or []: self._fx_msg(m["performativa"], m["remetente"], m["destinatario"], False)
        for l in r.get("linhas") or []: self._fx_log(l, False)
        self._fx_desenhar()

    # ─── desenho
    def _fx_desenhar(self):
        cv = self._fx_cv; cv.delete("all")
        W = max(cv.winfo_width(), 760); mx = 14; gap = max(50, min(70, W * 0.055))
        bw = (W - 2 * mx - 4 * gap) / 5; y0, y1 = 50, 186
        estreito = bw < 175                         # projetor de 1280 px: letra um pouco mais pequena nas caixas
        f_nome, f_corpo = f(11 if estreito else 12, "bold"), f(8 if estreito else 9)
        max_chars = int((bw - 18) / (6.2 if estreito else 6.8)) * 3        # cabe em três linhas
        pos = {}
        for i, (ag, cod, nome, tipo, ct, _) in enumerate(AGENTES):
            x0 = mx + i * (bw + gap); pos[ag] = (x0, x0 + bw)
        cx = lambda ag: (pos[ag][0] + pos[ag][1]) / 2
        # arco de revisão (Crítico -> Avaliador), por cima
        usado = self._fx_rev
        c = COR["rev"] if usado else COR["borda"]
        xa, xc = cx("avaliador") + 20, cx("critico") - 20
        cv.create_line(xc, y0, xc, 26, xa, 26, xa, y0, fill=c, width=2 if usado else 1, arrow="last",
                       dash=() if usado else (4, 3))
        cv.create_text((xa + xc) / 2, 15, text="reject-proposal: revisão pedida pelo Crítico (máx. 1)",
                       fill=c if usado else COR["sub"], font=f(9, "bold" if usado else ""))
        # rejeição imediata (Guardião ou Avaliador -> Decisor), por baixo
        de = self._fx_rej or "guardiao"; usado = self._fx_rej is not None
        c = COR["nao"] if usado else COR["borda"]
        xs, xd = cx(de) - (0 if usado else 0), cx("decisor")
        cv.create_line(xs, y1, xs, 204, xd, 204, xd, y1, fill=c, width=2 if usado else 1, arrow="last",
                       dash=() if usado else (4, 3))
        cv.create_text((xs + xd) / 2, 214, text=f"rejeição imediata ({'Guardião' if de == 'guardiao' else 'Avaliador'} -> Decisor)",
                       fill=c if usado else COR["sub"], font=f(9, "bold" if usado else ""))
        # setas entre agentes seguidos
        for (a, _, _, _, _, _), (b, _, _, _, _, _) in zip(AGENTES, AGENTES[1:]):
            perf = self._fx_perf.get((a, b))
            c = COR["dest"] if perf else COR["borda"]
            ym = (y0 + y1) / 2 + 4
            cv.create_line(pos[a][1] + 3, ym, pos[b][0] - 3, ym, fill=c, width=2 if perf else 1, arrow="last")
            if perf: cv.create_text((pos[a][1] + pos[b][0]) / 2, ym - 11, text=perf, fill=COR["dest"], font=f(8 if estreito else 9, "bold"))
        # caixas dos agentes
        for ag, cod, nome, tipo, ct, papel in AGENTES:
            x0, x1 = pos[ag]; est = self._fx_estado[ag]
            txt_e, cor_e, borda, esp = _ESTADOS[est]
            borda = borda or COR[ct]
            fundo = COR["painel"] if est == "espera" else COR[ct + "_f"]
            cv.create_rectangle(x0, y0, x1, y1, fill=fundo, outline=borda, width=esp)
            cv.create_rectangle(x0, y0, x1, y0 + 28, fill=COR[ct] if est != "espera" else COR["espera"], outline="")
            cv.create_text(x0 + 10, y0 + 14, anchor="w", text=f"{cod}  {nome}", fill="white", font=f_nome)
            cv.create_text(x0 + 10, y0 + 40, anchor="w", text=tipo, fill=COR[ct], font=f(9, "bold"))
            cv.create_oval(x0 + 10, y0 + 54, x0 + 20, y0 + 64, fill=cor_e, outline="")
            cv.create_text(x0 + 26, y0 + 59, anchor="w", text=txt_e, fill=cor_e, font=f(10, "bold"))
            corpo = self._fx_texto[ag]
            if len(corpo) > max_chars: corpo = corpo[:max_chars - 1].rstrip() + "…"
            cv.create_text(x0 + 10, y0 + 72, anchor="nw", text=corpo, width=bw - 18,
                           fill=COR["texto"] if est != "espera" else COR["sub"], font=f_corpo)
        # entrada e saída
        cv.create_text(mx, 40, anchor="w", text="utilizador: pedido (request)", fill=COR["sub"], font=f(8))
        fim = {"inform": "resposta ao utilizador (inform)", "failure": "falhou: resposta ao utilizador (failure)"}.get(self._fx_fim)
        if fim: cv.create_text(W - mx, 40, anchor="e", text=fim, fill=COR["nao"] if self._fx_fim == "failure" else COR["ok"], font=f(8, "bold"))
