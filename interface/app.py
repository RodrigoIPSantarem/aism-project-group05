"""Janela principal: escolher a empresa, ver os 5 agentes a trabalhar e ler o resultado.

Organização da janela (de cima para baixo, à direita):
  1. Fluxo dos agentes: as 5 caixas da proposta (Coletor, Guardião, Avaliador, Crítico, Decisor), que se acendem à medida
     que recebem mensagens FIPA-ACL (interface/fluxo.py).
  2. Resultado: veredicto em destaque, preço atual, preço máximo de compra, TACE e Portões, com o motivo principal.
  3. Separadores: relatório completo, Portões e testes, pensamento dos agentes (ao vivo) e a lista de mensagens FIPA-ACL.
À esquerda: empresa, fonte de dados, anos, o botão Analisar e o histórico das análises.
A análise corre numa thread à parte; os agentes falam com a janela por uma fila de eventos (nunca mexem nela diretamente)."""
import datetime, json, os, queue, threading, time
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:      # sem interface gráfica: a linha de comandos continua a funcionar
    tk=messagebox=ttk=None
from config import ANOS_ANALISE, RAIZ
from fontes.sintetico import _sint_listar
from interface.fluxo import FluxoMixin
from interface.historico import HistoricoMixin
from interface.pensamento import PensamentoMixin
from interface.tema import COR, FMO, FTI, FUI, cor_veredicto, f, fmo
from nucleo.analisar import analisar
from nucleo.configuracao import descarregar_modelo, garantir_env, gravar_env, ler_env, modelos_ollama, tem_modelo
from nucleo.llm import _criar_llm
from nucleo.util import _carregar_env, _num

_TENTATIVAS_ARRANQUE=4      # verificações do Ollama ao abrir a janela, com 3 s entre elas, antes de mostrar o aviso
SUGESTOES_SEC=["KO","PG","CL","MA","V","MSFT","AAPL","ROL","ADP","NVO","ASML"]     # exemplos para a fonte SEC
_COR_PERF={"request":"#1F5FA8","inform":"#1B7A45","propose":"#6A3FA0","reject-proposal":"#B35A00",
           "accept-proposal":"#1B7A45","refuse":"#C42B2B","failure":"#C42B2B"}


class App(FluxoMixin, PensamentoMixin, HistoricoMixin, tk.Tk if tk else object):
    """Janela principal (Tkinter)."""
    def __init__(self):
        super().__init__()
        garantir_env(); _carregar_env()             # primeira utilização: o .env é criado sozinho
        self.title("Sistema Multiagente de Investimentos · AISM Grupo 5")
        self.configure(bg=COR["fundo"]); self.minsize(1180,700); self.geometry("1400x860")
        try: self.state("zoomed")                   # Windows: abre maximizada (melhor para projetar)
        except tk.TclError: pass
        self._llm=_criar_llm(RAIZ/"dados"/"cache_llm")
        self._fila: queue.Queue=queue.Queue()           # resultado final da análise
        self._fila_agentes: queue.Queue=queue.Queue()   # eventos em tempo real dos agentes (mensagens, linhas, conclusões)
        self._fila_cfg: queue.Queue=queue.Queue()       # verificação e descarga do modelo
        self._thread: threading.Thread|None=None
        self._hist: list[dict]=[]; self._ult: dict|None=None; self._msgs_vivas: list=[]
        self._estilo(); self._construir()
        self._carregar_empresas(); self._carregar_historico()
        self.after(150,self._poll); self.after(80,self._poll_agentes); self.after(250,self._poll_cfg)
        self.after(700,lambda: self._verificar_modelo(True,0))       # Ollama a correr? modelo descarregado?
        self.protocol("WM_DELETE_WINDOW",self._sair)
        self.bind("<FocusIn>",self._ao_focar)        # voltar à janela depois de abrir o Ollama: verifica outra vez

    # ─── construção
    def _estilo(self):
        st=ttk.Style()
        try: st.theme_use("clam")
        except tk.TclError: pass
        st.configure("TNotebook",background=COR["fundo"],borderwidth=0,tabmargins=(0,4,0,0))
        st.configure("TNotebook.Tab",background="#DCE3ED",foreground=COR["sub"],padding=(16,7),font=f(10,"bold"),borderwidth=0)
        st.map("TNotebook.Tab",background=[("selected",COR["painel"])],foreground=[("selected",COR["dest"])])
        st.configure("TCombobox",fieldbackground=COR["ent"],background=COR["ent"],foreground=COR["texto"],arrowsize=16,padding=4)
        st.configure("Horizontal.TProgressbar",background=COR["dest"],troughcolor="#DCE3ED",borderwidth=0,thickness=6)
        self.option_add("*TCombobox*Listbox.font",f(11))

    def _construir(self):
        # barra do título
        t=tk.Frame(self,bg=COR["topo"],padx=18,pady=10); t.pack(fill="x")
        # os da direita primeiro: se a janela for estreita, é o subtítulo que encolhe, nunca o estado do modelo
        tk.Button(t,text="Definições",font=f(10),bg="#2E5280",fg="white",relief="flat",cursor="hand2",bd=0,
                  activebackground="#3A6699",activeforeground="white",command=self._definicoes,padx=12,pady=3).pack(side="right",padx=(10,0))
        self._ltopo=tk.Label(t,text=f"Modelo: {self._llm.modelo}",font=f(10,"bold"),bg=COR["topo"],fg="#B9C8DC")
        self._ltopo.pack(side="right",padx=6)
        tk.Label(t,text="Sistema Multiagente de Investimentos",font=FTI,bg=COR["topo"],fg="white").pack(side="left")
        tk.Label(t,text="   Protocolo v4.27 · AISM, Grupo 5",font=f(10),bg=COR["topo"],fg="#B9C8DC").pack(side="left",pady=(4,0))
        corpo=tk.Frame(self,bg=COR["fundo"]); corpo.pack(fill="both",expand=True)
        corpo.columnconfigure(1,weight=1); corpo.rowconfigure(0,weight=1)
        esq=tk.Frame(corpo,bg=COR["painel"],width=300,highlightthickness=1,highlightbackground=COR["borda"])
        esq.grid(row=0,column=0,sticky="nsew",padx=(12,6),pady=12); esq.pack_propagate(False)
        dir_=tk.Frame(corpo,bg=COR["fundo"]); dir_.grid(row=0,column=1,sticky="nsew",padx=(6,12),pady=12)
        dir_.columnconfigure(0,weight=1); dir_.rowconfigure(2,weight=1)
        self._esq(esq); self._dir(dir_)

    def _esq(self,p):
        def titulo(txt,pady=(14,4)):
            tk.Label(p,text=txt,font=f(9,"bold"),bg=COR["painel"],fg=COR["sub"]).pack(anchor="w",padx=16,pady=pady)
        titulo("1. EMPRESA (TICKER)",(16,4))
        self._vt=tk.StringVar(value="AURORA")
        self._cb=ttk.Combobox(p,textvariable=self._vt,font=f(14,"bold"),width=18)
        self._cb.pack(padx=16,fill="x")
        self._cb.bind("<<ComboboxSelected>>",self._sel_emp); self._cb.bind("<KeyRelease>",self._sel_emp)
        self._cb.bind("<Return>",lambda _:self._analisar())
        self._lnome=tk.Label(p,text="",font=f(9),bg=COR["painel"],fg=COR["sub"],wraplength=260,justify="left")
        self._lnome.pack(anchor="w",padx=16,pady=(4,0))

        titulo("2. FONTE DOS DADOS")
        self._vf=tk.StringVar(value="sintetico")
        for txt,val in (("Dataset sintético (casos de teste)","sintetico"),("SEC: empresas reais dos EUA","sec")):
            tk.Radiobutton(p,text=txt,variable=self._vf,value=val,bg=COR["painel"],fg=COR["texto"],font=f(10),
                           selectcolor=COR["ent"],activebackground=COR["painel"],highlightthickness=0,
                           command=self._chg_fonte).pack(anchor="w",padx=12)

        titulo("3. ANOS DE HISTÓRICO")
        self._vanos=tk.IntVar(value=ANOS_ANALISE)
        fr=tk.Frame(p,bg=COR["painel"]); fr.pack(anchor="w",padx=12)
        for a in (5,10):
            tk.Radiobutton(fr,text=f"{a} anos",variable=self._vanos,value=a,bg=COR["painel"],fg=COR["texto"],font=f(10),
                           selectcolor=COR["ent"],activebackground=COR["painel"],highlightthickness=0).pack(side="left",padx=(0,14))

        self._btn=tk.Button(p,text="Analisar",font=f(14,"bold"),bg=COR["dest"],fg="white",relief="flat",cursor="hand2",bd=0,
                            activebackground="#174A85",activeforeground="white",command=self._analisar,pady=9)
        self._btn.pack(fill="x",padx=16,pady=(20,6))
        self._bar=ttk.Progressbar(p,mode="indeterminate",style="Horizontal.TProgressbar"); self._bar.pack(fill="x",padx=16)
        self._lest=tk.Label(p,text="",font=f(9),bg=COR["painel"],fg=COR["sub"],wraplength=260,justify="left")
        self._lest.pack(anchor="w",padx=16,pady=(4,0))

        tk.Button(p,text="Exportar o relatório",font=f(10),bg="#E4EAF2",fg=COR["texto"],relief="flat",cursor="hand2",bd=0,
                  activebackground="#D5DEEA",command=self._exportar,pady=5).pack(side="bottom",fill="x",padx=16,pady=(6,14))
        titulo("HISTÓRICO (clicar para rever)",(18,4))
        fh=tk.Frame(p,bg=COR["painel"]); fh.pack(fill="both",expand=True,padx=16)
        sh=tk.Scrollbar(fh,orient="vertical")
        self._lhist=tk.Listbox(fh,font=fmo(FMO[1]-1),bg="#F7F9FC",fg=COR["texto"],relief="flat",highlightthickness=1,
                               highlightbackground=COR["borda"],selectbackground="#CFE0F5",selectforeground=COR["texto"],
                               activestyle="none",yscrollcommand=sh.set)
        sh.config(command=self._lhist.yview); sh.pack(side="right",fill="y"); self._lhist.pack(fill="both",expand=True)
        self._lhist.bind("<<ListboxSelect>>",self._sel_hist)

    def _dir(self,p):
        # 1) fluxo dos agentes
        cf=tk.Frame(p,bg=COR["painel"],highlightthickness=1,highlightbackground=COR["borda"]); cf.grid(row=0,column=0,sticky="ew")
        cab=tk.Frame(cf,bg=COR["painel"]); cab.pack(fill="x",padx=14,pady=(8,0))
        tk.Label(cab,text="Os 5 agentes e as mensagens entre eles",font=f(11,"bold"),bg=COR["painel"],fg=COR["texto"]).pack(side="left")
        for cor,txt in ((COR["py"],"só regras em Python"),(COR["llm"],"usa o modelo de linguagem")):
            tk.Label(cab,text=f"  {txt}",font=f(9),bg=COR["painel"],fg=COR["sub"]).pack(side="right")
            tk.Label(cab,text="  ",bg=cor,width=2).pack(side="right",padx=(10,0))
        self._fx_construir(cf)
        # 2) resultado
        rb=tk.Frame(p,bg=COR["painel"],highlightthickness=1,highlightbackground=COR["borda"],padx=18,pady=12)
        rb.grid(row=1,column=0,sticky="ew",pady=10); rb.columnconfigure(1,weight=1)
        self._lv=tk.Label(rb,text="Pronto",font=f(20,"bold"),bg=COR["painel"],fg=COR["sub"],anchor="w")
        self._lv.grid(row=0,column=0,sticky="w")
        tiles=tk.Frame(rb,bg=COR["painel"]); tiles.grid(row=0,column=1,sticky="e")
        self._tiles={}
        for k,rot in (("preco","Preço atual"),("pmc","Preço máx. compra"),("tace","TACE"),("portoes","Portões")):
            fr=tk.Frame(tiles,bg="#F5F8FC",padx=11,pady=5,highlightthickness=1,highlightbackground="#E1E7EF")
            fr.pack(side="left",padx=(8,0))
            tk.Label(fr,text=rot,font=f(9),bg="#F5F8FC",fg=COR["sub"]).pack(anchor="w")
            v=tk.Label(fr,text="–",font=f(15,"bold"),bg="#F5F8FC",fg=COR["texto"]); v.pack(anchor="w")
            n=tk.Label(fr,text="",font=f(8),bg="#F5F8FC",fg=COR["sub"]); n.pack(anchor="w")
            self._tiles[k]=(v,n)
        self._lemp=tk.Label(rb,text="Escolhe uma empresa e carrega em Analisar.",font=f(11),bg=COR["painel"],fg=COR["sub"],anchor="w")
        self._lemp.grid(row=1,column=0,columnspan=2,sticky="w",pady=(2,0))
        self._lmotivo=tk.Label(rb,text="",font=f(10),bg=COR["painel"],fg=COR["texto"],anchor="w",justify="left",wraplength=900)
        self._lmotivo.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(8,0))
        rb.bind("<Configure>",lambda e: self._lmotivo.config(wraplength=max(e.width-40,400)))
        # 3) separadores
        nb=ttk.Notebook(p); nb.grid(row=2,column=0,sticky="nsew"); self._nb=nb
        self._fr_rel=tk.Frame(nb,bg=COR["painel"]); nb.add(self._fr_rel,text="Relatório")
        self._fr_pont=tk.Frame(nb,bg=COR["painel"]); nb.add(self._fr_pont,text="Portões e testes")
        self._fr_pens=tk.Frame(nb,bg=COR["painel"]); nb.add(self._fr_pens,text="Pensamento dos agentes (ao vivo)")
        self._fr_msgs=tk.Frame(nb,bg=COR["painel"]); nb.add(self._fr_msgs,text="Mensagens FIPA-ACL")
        self._txt_r=self._mk_txt(self._fr_rel)
        self._txt_pens=self._mk_txt_pens(self._fr_pens)
        self._cv=tk.Canvas(self._fr_pont,bg=COR["painel"],highlightthickness=0)
        sc2=tk.Scrollbar(self._fr_pont,orient="vertical",command=self._cv.yview)
        self._cv.configure(yscrollcommand=sc2.set); sc2.pack(side="right",fill="y"); self._cv.pack(fill="both",expand=True)
        self._cv.bind("<Configure>",lambda _:self._redesenhar_pont())
        self._txt_m=self._mk_txt(self._fr_msgs)
        for perf,cor in _COR_PERF.items(): self._txt_m.tag_config("p_"+perf,foreground=cor,font=fmo(None,"bold"))
        self._limpar_resultado()

    def _mk_txt(self,pai):
        f_=tk.Frame(pai,bg=COR["painel"]); f_.pack(fill="both",expand=True)
        sc=tk.Scrollbar(f_,orient="vertical")
        t=tk.Text(f_,bg=COR["painel"],fg=COR["texto"],font=fmo(),relief="flat",padx=16,pady=12,wrap="word",
                  yscrollcommand=sc.set,state="disabled",cursor="arrow",selectbackground="#CFE0F5")
        sc.config(command=t.yview); sc.pack(side="right",fill="y"); t.pack(fill="both",expand=True)
        for tag,cor,negrito in (("ok",COR["ok"],True),("nao",COR["nao"],True),("cond",COR["cond"],True),("dest",COR["dest"],True),
                                ("sub",COR["sub"],False),("disp",COR["nao"],False),("oks",COR["ok"],False),("av",COR["cond"],False)):
            t.tag_config(tag,foreground=cor,font=fmo(None,"bold") if negrito else fmo())
        return t

    # ─── empresas e fonte
    def _carregar_empresas(self):
        self._emps={e["ticker"]:e for e in _sint_listar()}
        self._chg_fonte()

    def _sel_emp(self,_=None):
        tk_=self._vt.get().split(" ")[0].strip().upper()
        e=self._emps.get(tk_) if self._vf.get()=="sintetico" else None
        if e: self._lnome.config(text=f"{e['name']}. {e.get('_caso','')}")
        elif self._vf.get()=="sec": self._lnome.config(text="Dados oficiais da SEC (relatórios 10-K e 20-F). O preço e a taxa do Estado vêm do Yahoo Finance.")
        else: self._lnome.config(text="Este ticker não existe no dataset sintético.")

    def _chg_fonte(self):
        if self._vf.get()=="sintetico":
            self._cb["values"]=list(self._emps)
            if self._vt.get().upper() not in self._emps: self._vt.set("AURORA" if "AURORA" in self._emps else next(iter(self._emps),""))
        else:
            self._cb["values"]=SUGESTOES_SEC
            if self._vt.get().upper() in self._emps: self._vt.set("KO")
        self._sel_emp()

    # ─── modelo de linguagem: verificação e descarga, sem terminal
    def _estado_modelo(self, texto, tipo):
        cor={"ok":"#8BE0AE","cond":"#FFD27A","nao":"#FF9E9E","sub":"#B9C8DC"}[tipo]
        self._ltopo.config(text=texto,fg=cor)

    def _ao_focar(self, ev):
        """Se o modelo ainda aparece como indisponível, volta a perguntar ao Ollama quando a janela ganha o foco (no máximo de 5 em 5 s)."""
        if ev.widget is not self: return
        agora=time.time()
        if agora-getattr(self,"_ult_foco",0)<5: return
        self._ult_foco=agora
        txt=self._ltopo.cget("text")
        if "não está" in txt or "em falta" in txt or "A ligar" in txt: self._verificar_modelo(False)

    def _verificar_modelo(self, perguntar=True, tentativa=None):
        """Pergunta ao Ollama (noutra thread) se está a correr e se tem o modelo. `tentativa` só é dada no arranque: o Ollama
        pode ainda estar a iniciar, por isso falhar à primeira não é erro (ver _resultado_verificacao)."""
        modelo=os.environ.get("LLM_MODELO") or "qwen2.5:7b"
        if tentativa==0: self._estado_modelo("A verificar o Ollama…","sub")
        threading.Thread(target=lambda: self._fila_cfg.put(("verif",modelo,modelos_ollama(),perguntar,tentativa)),daemon=True).start()

    def _poll_cfg(self):
        """As tarefas em segundo plano não mexem na janela: deixam mensagens nesta fila, lida aqui (thread principal)."""
        try:
            while True:
                ev=self._fila_cfg.get_nowait()
                if ev[0]=="verif": self._resultado_verificacao(*ev[1:])
                elif ev[0]=="prog": self._lest.config(text=ev[1],fg=COR["sub"])
                elif ev[0]=="fim":
                    ok,msg=ev[1],ev[2]
                    self._bar_parar(); self._btn.config(state="normal")
                    self._lest.config(text=("Modelo pronto." if ok else f"Falhou a descarga: {msg}"),fg=COR["ok"] if ok else COR["nao"])
                    self._verificar_modelo(perguntar=False)
        except queue.Empty: pass
        self.after(250,self._poll_cfg)

    def _resultado_verificacao(self, modelo, inst, perguntar, tentativa=None):
        if inst is None:
            if tentativa is not None and tentativa<_TENTATIVAS_ARRANQUE-1:
                self._estado_modelo(f"A ligar ao Ollama ({tentativa+1}/{_TENTATIVAS_ARRANQUE})…","cond")
                self.after(3000,lambda: self._verificar_modelo(perguntar,tentativa+1)); return
            self._estado_modelo("Ollama não está a correr","nao")
            if perguntar:
                messagebox.showwarning("Ollama não está a correr",
                    "O programa usa o Ollama para o modelo de linguagem (gratuito, corre no computador).\n\n"
                    "1. Descarrega e instala o Ollama em ollama.com.\n"
                    "2. Abre o Ollama (fica junto ao relógio do Windows).\n"
                    "3. Volta a esta janela: o estado é verificado outra vez sozinho.")
            if tentativa is not None:       # continua a verificar em silêncio: assim que o Ollama abrir, o estado muda sozinho
                self.after(15000,lambda: self._verificar_modelo(False,_TENTATIVAS_ARRANQUE-1))
            return
        if tem_modelo(modelo,inst):
            self._llm=_criar_llm(RAIZ/"dados"/"cache_llm"); self._estado_modelo(f"Modelo {modelo}: pronto","ok"); return
        self._estado_modelo(f"Modelo {modelo} em falta","cond")
        if perguntar and messagebox.askyesno("Descarregar o modelo",
                f"O modelo {modelo} ainda não está neste computador.\n\nDescarregar agora? (alguns GB; só da primeira vez)"):
            self._descarregar(modelo)

    def _descarregar(self, modelo):
        self._btn.config(state="disabled"); self._bar_iniciar()
        def tarefa():
            ok,msg=descarregar_modelo(modelo,lambda txt,_f: self._fila_cfg.put(("prog",txt)))
            self._fila_cfg.put(("fim",ok,msg))
        threading.Thread(target=tarefa,daemon=True).start()

    def _definicoes(self):
        """Janela de Definições: grava o .env por ti (modelo, endereço do Ollama, identificação para a SEC, chave opcional)."""
        env=ler_env(); w=tk.Toplevel(self); w.title("Definições"); w.configure(bg=COR["painel"]); w.transient(self); w.grab_set()
        w.resizable(False,False)
        inst=modelos_ollama() or []
        campos={}
        def linha(rotulo, chave, valor, ajuda="", opcoes=None):
            fr=tk.Frame(w,bg=COR["painel"]); fr.pack(fill="x",padx=18,pady=(12,0))
            tk.Label(fr,text=rotulo,font=f(10,"bold"),bg=COR["painel"],fg=COR["texto"]).pack(anchor="w")
            v=tk.StringVar(value=valor)
            if opcoes is not None: e=ttk.Combobox(fr,textvariable=v,values=opcoes,width=46,font=f(10))
            else: e=tk.Entry(fr,textvariable=v,width=50,bg="#F7F9FC",fg=COR["texto"],insertbackground=COR["texto"],relief="flat",
                             font=f(10),highlightthickness=1,highlightbackground=COR["borda"])
            e.pack(anchor="w",fill="x",pady=(3,0),ipady=3)
            if ajuda: tk.Label(fr,text=ajuda,font=f(9),bg=COR["painel"],fg=COR["sub"],wraplength=440,justify="left").pack(anchor="w")
            campos[chave]=v
        linha("Modelo de linguagem","LLM_MODELO",env.get("LLM_MODELO") or "qwen2.5:7b",
              "Instalados: "+(", ".join(inst) if inst else "nenhum (ou o Ollama não está a correr)")+". O relatório usa o qwen2.5:7b.",
              opcoes=sorted(set(inst)|{"qwen2.5:7b","qwen2.5:3b"}))
        linha("Endereço do Ollama","OLLAMA_URL",env.get("OLLAMA_URL") or "http://localhost:11434")
        linha("Identificação para a SEC (nome e email)","SEC_USER_AGENT",env.get("SEC_USER_AGENT") or "",
              "A SEC pede um nome e um email em cada pedido; não é preciso conta.")
        linha("Chave da Alpha Vantage (opcional)","ALPHAVANTAGE_API_KEY",env.get("ALPHAVANTAGE_API_KEY",""),
              "Gratuita em alphavantage.co. Só completa o histórico de algumas empresas da SEC.")
        fb=tk.Frame(w,bg=COR["painel"]); fb.pack(fill="x",padx=18,pady=16)
        def guardar():
            gravar_env({k:v.get().strip() for k,v in campos.items()})
            self._llm=_criar_llm(RAIZ/"dados"/"cache_llm"); w.destroy(); self._verificar_modelo(perguntar=True)
        tk.Button(fb,text="Guardar e verificar o modelo",font=f(10,"bold"),bg=COR["dest"],fg="white",relief="flat",cursor="hand2",
                  command=guardar,padx=14,pady=5).pack(side="left")
        tk.Button(fb,text="Cancelar",font=f(10),bg="#E4EAF2",fg=COR["texto"],relief="flat",cursor="hand2",
                  command=w.destroy,padx=12,pady=5).pack(side="right")

    # ─── análise
    def _analisar(self):
        if self._thread and self._thread.is_alive(): return
        fonte=self._vf.get(); ticker=self._vt.get().split(" ")[0].strip().upper()
        if not ticker: messagebox.showwarning("Ticker","Escreve um ticker (ex.: AURORA no dataset sintético, ou KO na SEC)."); return
        if fonte=="sintetico" and ticker not in self._emps:
            messagebox.showwarning("Ticker",f"{ticker} não existe no dataset sintético. Para uma empresa real escolhe a fonte SEC."); return
        modelo=self._llm.modelo; inst=modelos_ollama()
        if inst is None or not tem_modelo(modelo,inst):
            self._resultado_verificacao(modelo,inst,True); return
        anos=self._vanos.get(); llm=self._llm
        self._btn.config(state="disabled",text="A analisar…"); self._lest.config(text=f"A analisar {ticker} ({anos} anos)…",fg=COR["sub"])
        self._bar_iniciar(); self._limpar(ticker)
        def tarefa():
            try:
                r=analisar(ticker,anos,fonte,llm,mostrar=False,jsonl=RAIZ/"saidas"/f"gui_{ticker}.jsonl",fila_ui=self._fila_agentes)
                self._fila.put(("ok",ticker,r))
            except Exception as ex:
                self._fila.put(("erro",ticker,f"{type(ex).__name__}: {ex}"))
        self._thread=threading.Thread(target=tarefa,daemon=True); self._thread.start()

    def _poll(self):
        try:
            tipo,ticker,dados=self._fila.get_nowait()
            self._bar_parar(); self._btn.config(state="normal",text="Analisar")
            if tipo=="erro":
                self._lest.config(text=f"Erro: {dados}",fg=COR["nao"])
                self._lv.config(text="ERRO",fg=COR["nao"]); self._lmotivo.config(text=dados)
            else:
                seg=dados.get("_segundos"); self._lest.config(text=f"Concluído em {_num(seg,0)} s." if seg is not None else "",fg=COR["sub"])
                self._mostrar(dados); self._add_hist(ticker,dados)
        except queue.Empty: pass
        self.after(150,self._poll)

    def _poll_agentes(self):
        """Eventos ao vivo: as mensagens acendem os agentes no fluxo e entram na lista FIPA-ACL; as linhas e as conclusões
        vão para o pensamento dos agentes."""
        try:
            while True:
                ev=self._fila_agentes.get_nowait()
                if ev[0]=="msg":
                    _,perf,rem,dest,ts=ev; self._fx_msg(perf,rem,dest)
                    self._msg_linha(len(self._msgs_vivas)+1,perf,rem,dest); self._msgs_vivas.append(ev)
                else:
                    if ev[0]=="log": self._fx_log(ev[1])
                    self._desenhar_ev(ev)
        except queue.Empty: pass
        self.after(80,self._poll_agentes)

    def _bar_iniciar(self): self._bar.config(mode="indeterminate"); self._bar.start(12)
    def _bar_parar(self): self._bar.stop(); self._bar.config(mode="determinate",value=0)

    # ─── mostrar
    def _limpar_resultado(self):
        self._lv.config(text="Pronto",fg=COR["sub"])
        self._lemp.config(text="Escolhe uma empresa e carrega em Analisar.",fg=COR["sub"])
        for v,n in self._tiles.values(): v.config(text="–",fg=COR["texto"]); n.config(text="")
        self._lmotivo.config(text="")

    def _limpar(self, ticker):
        self._ult=None; self._limpar_resultado(); self._fx_repor(); self._msgs_vivas=[]
        self._lv.config(text="A analisar…",fg=COR["dest"]); self._lemp.config(text=ticker,fg=COR["texto"])
        for t in (self._txt_r,self._txt_m,self._txt_pens):
            t.config(state="normal"); t.delete("1.0","end"); t.config(state="disabled")
        self._cv.delete("all"); self._nb.select(self._fr_pens)
        while not self._fila_agentes.empty():
            try: self._fila_agentes.get_nowait()
            except queue.Empty: break

    def _mostrar(self,r):
        self._ult=r; self._fx_de_resultado(r)
        if r.get("performativa")=="failure":
            self._limpar_resultado(); self._lv.config(text="SEM DADOS",fg=COR["nao"])
            self._lemp.config(text=r.get("_ticker") or "",fg=COR["texto"])
            self._lmotivo.config(text=f"O Coletor não conseguiu os dados: {r.get('motivo','')}")
            self._preencher_msgs(r); self._repor_pensamento(r); return
        self._preencher_destaque(r)
        self._preencher_rel(r); self._redesenhar_pont(); self._preencher_msgs(r); self._repor_pensamento(r)
        self._nb.select(self._fr_rel)

    def _preencher_destaque(self, r):
        d=r.get("dados") or {}; av=r.get("avaliacao") or {}; tst=r.get("testes") or {}; op=r.get("oportunidade") or {}
        e=d.get("empresa") or {}; moeda=(d.get("mercado") or {}).get("moeda") or e.get("moeda") or ""
        cat=op.get("categoria","-"); cor=cor_veredicto(cat)
        self._lv.config(text=cat,fg=cor)
        anos=d.get("anos") or []
        self._lemp.config(text=f"{e.get('nome') or r.get('_ticker','')} ({e.get('ticker') or r.get('_ticker','')}) · "
                               f"{len(anos)} anos ({anos[0]}–{anos[-1]})" if anos else (e.get("nome") or r.get("_ticker","")),fg=COR["texto"])
        preco,pmc,tace=av.get("preco"),av.get("pmc"),av.get("tace")
        if preco is None: preco=(d.get("mercado") or {}).get("preco")
        self._tile("preco",f"{_num(preco)}" if preco is not None else "–",moeda)
        if pmc:
            ok=preco is not None and preco<=pmc
            self._tile("pmc",_num(pmc),("preço abaixo do máximo" if ok else f"falta descer {_num((1-pmc/preco)*100,0)}%") if preco else moeda,
                       COR["ok"] if ok else COR["cond"])
        else: self._tile("pmc","–","não calculado" if not av else "")
        if tace is not None: self._tile("tace",f"{_num(tace,1)}%","mínimo 15% ao ano",COR["ok"] if tace>=15 else (COR["cond"] if tace>=10 else COR["nao"]))
        else: self._tile("tace","–","")
        if tst:
            falham=[p["id"] for p in tst.get("portoes",[]) if not p["passa"]]
            self._tile("portoes",f"{10-len(falham)}/10",("falham "+", ".join(falham)) if falham else "todos passam",COR["ok"] if not falham else COR["nao"])
        else: self._tile("portoes","–","não avaliados")
        motivo=op.get("descricao") or (r.get("motivos") or [""])[0]
        self._lmotivo.config(text=("Porquê: " if motivo else "")+motivo[:400])

    def _tile(self, k, valor, nota="", cor=None):
        v,n=self._tiles[k]; v.config(text=valor,fg=cor or COR["texto"]); n.config(text=nota)

    def _wr(self,t,txt,tag=""):
        t.config(state="normal"); t.insert("end",txt,tag) if tag else t.insert("end",txt); t.config(state="disabled")

    def _preencher_rel(self,r):
        t=self._txt_r; t.config(state="normal"); t.delete("1.0","end")
        for ln in r.get("relatorio","").splitlines():
            x=ln.strip()
            if ln.startswith("VEREDICTO"): tag="ok" if ": COMPRAR" in ln else ("cond" if any(k in ln for k in ("CAIXA DEDICADA","REVISÃO MANUAL")) else "nao")
            elif ln.startswith(("RESUMO PARA DECISÃO","Passo ","RELATÓRIO")) or ln.startswith("  => ") or x.startswith(("Bloco C","=")): tag="dest"
            elif ln.startswith(("  Ao preço atual","  Preço Máximo de Compra","  Para ","  10 Portões")): tag="cond"
            elif " FALHA " in ln or "[!]" in ln or x.startswith("[ ]") or " NÃO " in ln or ln.startswith("  REJEIÇÃO"): tag="disp"
            elif " PASSA " in ln or x.startswith("[x]") or " Sim " in ln: tag="oks"
            elif " Parcial " in ln or "Verificação" in ln or "sem dados" in ln: tag="av"
            elif x.startswith("- ") or x.startswith("Nota:"): tag="sub"
            else: tag=""
            self._wr(t,ln+"\n",tag)
        t.config(state="disabled"); t.see("1.0")

    def _redesenhar_pont(self):
        cv=self._cv; cv.delete("all")
        if not self._ult: return
        tst=self._ult.get("testes")
        if not tst:
            cv.create_text(24,30,anchor="w",fill=COR["sub"],font=f(11),
                           text="Sem testes: a empresa foi rejeitada antes da avaliação (ver o motivo no relatório).")
            return
        larg=max(cv.winfo_width(),700); xl=24; xr=min(max(int(larg*0.45),380),560); y=14; hl=26
        cores={"Sim":COR["ok"],"Parcial":COR["cond"],"Não":COR["nao"]}
        def titulo(txt):
            nonlocal y
            cv.create_text(xl,y+10,anchor="w",fill=COR["dest"],font=f(11,"bold"),text=txt); y+=hl+4
        def linha(rotulo,resp,valor,cor):
            nonlocal y
            cv.create_text(xl,y+11,anchor="w",fill=COR["texto"],font=f(10),text=rotulo if len(rotulo)<=70 else rotulo[:69]+"…")
            cv.create_rectangle(xr,y+2,xr+96,y+21,fill=cor,outline="")
            cv.create_text(xr+48,y+11,fill="white",font=f(9,"bold"),text=resp)
            cv.create_text(xr+108,y+11,anchor="w",fill=COR["sub"],font=f(9),text=valor if len(valor)<=90 else valor[:89]+"…"); y+=hl
        titulo("Os 10 Portões (todos têm de passar para se poder comprar)")
        for p in tst["portoes"]:
            linha(f"{p['id']}  {p['pergunta']}","PASSA" if p["passa"] else "FALHA",p["detalhe"],COR["ok"] if p["passa"] else COR["nao"])
        y+=10
        for nome,chave in (("Bloco A: vantagem competitiva durável","A"),("Bloco B: gestão e alocação de capital","B"),
                           ("Bloco C: durabilidade do negócio","C")):
            titulo(nome)
            for t in tst[chave]:
                v=t["valor"]; vs=_num(v,2) if isinstance(v,(int,float)) and v!=float("inf") else ("" if v is None else str(v))
                linha(f"{t['id']}  {t['nome']}",t["resposta"] if t["resposta"] in cores else t["resposta"][:12],vs,cores.get(t["resposta"],COR["espera"]))
            y+=10
        pres=[x for x in tst["sinais"] if x["presente"] and not x.get("explicado")]
        cv.create_text(xl,y+8,anchor="w",fill=COR["cond"] if pres else COR["sub"],font=f(10),
                       text="Sinais de Balanço por explicar: "+(", ".join(x["id"]+" "+x["descricao"][:40] for x in pres) if pres else "nenhum"))
        cv.config(scrollregion=(0,0,larg,y+40))

    def _msg_linha(self, n, perf, rem, dest):
        t=self._txt_m
        self._wr(t,f"{n:>3}  ","sub"); self._wr(t,f"{rem:<11}"); self._wr(t," -> ","sub"); self._wr(t,f"{dest:<11}  ")
        self._wr(t,f"{perf}\n","p_"+perf if perf in _COR_PERF else ""); t.see("end")

    def _preencher_msgs(self,r):
        t=self._txt_m; t.config(state="normal"); t.delete("1.0","end"); t.config(state="disabled")
        self._wr(t,"Cada linha é uma mensagem FIPA-ACL entregue pela plataforma (o conteúdo completo fica em saidas/*.jsonl).\n\n","sub")
        for i,m in enumerate(r.get("_msgs",[]),1): self._msg_linha(i,m.get("performativa",""),m.get("remetente",""),m.get("destinatario",""))
        if not r.get("_msgs"): self._wr(t,"Sem mensagens registadas.\n","sub")
        t.see("1.0")

    def _exportar(self):
        """Exporta a última análise para saidas/exportacoes (TXT legível e JSON completo)."""
        if not self._ult: messagebox.showinfo("Exportar","Faz primeiro uma análise."); return
        r=self._ult; ticker=r.get("_ticker") or "empresa"
        ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pasta=RAIZ/"saidas"/"exportacoes"; pasta.mkdir(parents=True,exist_ok=True)
        fj=pasta/f"{ticker}_{ts}.json"; ft=pasta/f"{ticker}_{ts}.txt"
        d=r.get("dados") or {}
        payload={"exportado":datetime.datetime.now().isoformat(timespec="seconds"),"ticker":ticker,"anos":d.get("anos",[]),
                 "veredicto":(r.get("oportunidade") or {}).get("categoria"),"portoes_ok":r.get("portoes_ok"),
                 "relatorio":r.get("relatorio",""),"avaliacao":r.get("avaliacao"),"critica":r.get("critica"),"testes":r.get("testes"),
                 "revisoes":r.get("revisoes",0),"mensagens_fipa":r.get("_msgs",[]),
                 "dados":{k:d.get(k) for k in ("series","pontuais","em_falta","inconsistencias")}}
        fj.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        linhas=[r.get("relatorio",""),"","MENSAGENS FIPA-ACL"]+[
            f"{i:>3}  {m.get('remetente',''):<11} -> {m.get('destinatario',''):<11}  {m.get('performativa','')}" for i,m in enumerate(r.get("_msgs",[]),1)]
        ft.write_text("\n".join(linhas),encoding="utf-8")
        messagebox.showinfo("Exportado",f"Relatório exportado para a pasta saidas/exportacoes:\n\n{ft.name}\n{fj.name}")

    def _sair(self):
        if not (self._thread and self._thread.is_alive()) or messagebox.askokcancel("Sair","Há uma análise a decorrer. Fechar mesmo assim?"):
            self.destroy()