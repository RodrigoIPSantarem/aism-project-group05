"""Plataforma FIPA-ACL: mensagens, entrega entre agentes, registo de eventos e de execução.

Para a apresentação: é aqui que está o "multiagente" do projeto. Em vez de funções que se chamam umas às outras, cada
agente (Coletor, Guardião, Avaliador, Crítico, Decisor) é um objeto que só comunica por mensagens
FIPA-ACL (Msg). A Plataforma faz de correio: recebe uma mensagem, entrega-a ao destinatário, recolhe as respostas e
volta a entregar, até uma mensagem chegar ao "utilizador". Cada mensagem fica registada num ficheiro .jsonl (auditoria).

Performativas usadas (atos de fala da norma FIPA-ACL):
  request          pedir a outro agente que faça algo (p. ex. o Decisor pede ao Coletor os dados);
  inform           dar um facto ou um resultado;
  propose          propor uma resposta que o outro pode aceitar ou rejeitar (o Avaliador propõe, o Crítico avalia);
  reject-proposal  recusar a proposta, com motivo (o Crítico devolve ao Avaliador);
  accept-proposal  aceitar a proposta (definida pela norma; neste fluxo a aceitação é o inform do Crítico ao Decisor);
  refuse           o agente recusa fazer o pedido (o Avaliador, quando já esgotou as revisões);
  failure          o agente tentou e não conseguiu (o Coletor, quando a empresa não está na fonte).
"""
import dataclasses, datetime, itertools, json, threading
from pathlib import Path
from config import RAIZ
from nucleo.llm import LLM


PERFORMATIVAS={"request","inform","propose","reject-proposal","accept-proposal","refuse","failure"}
_ctr=itertools.count(1)      # contador global: dá a cada mensagem um identificador único (m1, m2, ...)

@dataclasses.dataclass
class Msg:
    """Uma mensagem FIPA-ACL. Campos: performativa, remetente, destinatário, conteúdo (um dicionário), identificador da
    conversa (conv) e a mensagem a que responde (resp_a), para se poder reconstruir o diálogo."""
    perf: str; rem: str; dest: str; conteudo: dict
    conv: str=""; resp_a: str|None=None
    id: str=dataclasses.field(default_factory=lambda:f"m{next(_ctr)}")
    def __post_init__(self):
        # só são aceites as performativas da lista acima: uma errada é um erro de programação e falha logo
        if self.perf not in PERFORMATIVAS: raise ValueError(f"Performativa inválida: {self.perf}")
    # resposta a esta mensagem: o remetente passa a destinatário, a conversa mantém-se e resp_a aponta para esta
    def r(self, perf, dest, conteudo): return Msg(perf,self.dest,dest,conteudo,self.conv,self.id)
    def d(self): return {"id":self.id,"performativa":self.perf,"remetente":self.rem,
                         "destinatario":self.dest,"conteudo":self.conteudo}

_REGISTO=RAIZ/"saidas"/"logs"/f"sessao_{datetime.date.today().isoformat()}.log"
_TRINCO_REGISTO=threading.Lock()   # várias empresas podem ser analisadas em paralelo: o trinco evita linhas misturadas

def _registar(linha: str):
    """Escreve no terminal e no ficheiro de registo da sessão (saidas/logs)."""
    print(linha)
    try:
        with _TRINCO_REGISTO:
            _REGISTO.parent.mkdir(parents=True,exist_ok=True)
            with _REGISTO.open("a",encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')} {linha}\n")
    except OSError: pass     # se não der para escrever o registo, a análise continua

class Plataforma:
    """O correio entre agentes. Guarda também o que a interface precisa de mostrar: linhas de texto, avisos e eventos."""
    def __init__(self, jsonl: Path|None=None, mostrar=True, fila_ui=None, ticker=""):
        self.agentes={}; self.msgs=[]; self.linhas=[]; self.jsonl=jsonl; self.ticker=ticker.upper()
        self.avisos=[]        # falhas de execução (ex.: modelo indisponível) que o relatório deve mostrar
        self.fila_ui=fila_ui  # queue.Queue opcional para emitir eventos à interface
        self.eventos=[]       # todos os eventos ficam guardados com o resultado (histórico)
        if jsonl: jsonl.parent.mkdir(parents=True,exist_ok=True); jsonl.write_text("",encoding="utf-8")
    def reg(self, ag): ag.plat=self; self.agentes[ag.nome]=ag      # registar um agente: passa a poder receber mensagens
    def dizer(self, txt):
        """O que os agentes 'dizem' enquanto trabalham (aparece no terminal, no registo e na janela principal)."""
        self.linhas.append(txt); _registar(f"{self.ticker:<6} {txt}")
        if "indisponível" in txt or "descartad" in txt: self.avisos.append(txt.strip())
        ev=("log", txt, datetime.datetime.now().strftime("%H:%M:%S"))
        self.eventos.append(ev)
        if self.fila_ui: self.fila_ui.put(ev)
    def emitir(self, tipo: str, agente: str, dados: dict):
        """Emite um evento estruturado para a interface em tempo real."""
        ev=("evento", tipo, agente, json.loads(json.dumps(dados,default=str)), datetime.datetime.now().strftime("%H:%M:%S"))
        self.eventos.append(ev)
        if self.fila_ui: self.fila_ui.put(ev)
    def _log(self, m):
        """Guarda a mensagem na memória e, se houver ficheiro, uma linha JSON com a hora (UTC): é o registo de auditoria."""
        self.msgs.append(m.d())
        if self.jsonl:
            with self.jsonl.open("a",encoding="utf-8") as f:
                f.write(json.dumps({"instante":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                    **m.d()},ensure_ascii=False)+"\n")
    def executar(self, primeira: Msg) -> Msg:
        """Ciclo de entrega: tira a primeira mensagem da fila, regista-a, entrega-a ao destinatário e põe na fila as respostas
        dele. Termina quando uma mensagem é dirigida ao 'utilizador' (a resposta final) ou, por segurança, ao fim de 100 mensagens."""
        fila=[primeira]; n=0
        while fila:
            m=fila.pop(0); self._log(m)
            if self.fila_ui:       # a janela acende o agente que recebe a mensagem e mostra a seta entre os dois
                self.fila_ui.put(("msg", m.perf, m.rem, m.dest, datetime.datetime.now().strftime("%H:%M:%S")))
            if m.dest=="utilizador": return m
            n+=1
            if n>100: raise RuntimeError("Limite de mensagens atingido.")      # evita conversas infinitas entre agentes
            ag=self.agentes.get(m.dest)
            if not ag: raise RuntimeError(f"Agente desconhecido: {m.dest}")
            fila.extend(ag.receber(m))
        raise RuntimeError("Conversa sem resposta.")

class Agente:
    """Classe base de todos os agentes. Cada agente tem um nome (o endereço das mensagens), um rótulo (o que aparece nos
    registos, p. ex. 'A1 Coletor') e, se precisar, o modelo de linguagem. Só tem de implementar `receber`: recebe uma
    mensagem e devolve a lista de mensagens que quer enviar a seguir."""
    nome=""; rotulo=""
    def __init__(self, llm: LLM|None=None): self.llm=llm; self.plat: Plataforma|None=None
    def dizer(self, txt):
        if self.plat: self.plat.dizer(f"{self.rotulo:<15} {txt}")
    def receber(self, m: Msg) -> list[Msg]: raise NotImplementedError
