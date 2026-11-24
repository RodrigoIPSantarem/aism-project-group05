"""Monta os 5 agentes da proposta e corre uma análise.

Para a apresentação, o fluxo de uma análise (cada seta é uma mensagem FIPA-ACL):
  utilizador --request--> A1 Coletor --inform--> A2 Guardião --request--> A3 Avaliador --propose--> A4 Crítico
  A4 Crítico --reject-proposal--> A3 Avaliador (no máximo uma revisão) ou --inform--> A5 Decisor --inform--> utilizador.
  Se o Guardião (regras de exclusão) ou o Avaliador (pergunta eliminatória) reprovam a empresa, a mensagem vai direta
  ao Decisor, que emite REJEITAR com os motivos. Se o Coletor não consegue os dados, responde failure ao utilizador."""
import datetime, time
from pathlib import Path
from agentes.avaliador import Avaliador
from agentes.coletor import Coletor
from agentes.critico import Critico
from agentes.decisor import Decisor
from agentes.guardiao import Guardiao
from config import ANOS_ANALISE, TAXA_RENTABILIDADE_ALVO
from nucleo.plataforma import Msg, Plataforma, _registar

AGENTES = ("coletor", "guardiao", "avaliador", "critico", "decisor")      # a ordem em que aparecem na janela


def analisar(ticker, anos=ANOS_ANALISE, fonte="sintetico", llm=None, preco=None, taxa=None, mostrar=True,
             jsonl: Path|None=None, fila_ui=None, taxa_alvo: float=TAXA_RENTABILIDADE_ALVO):
    """Analisa uma empresa. fonte: "sec" (empresas dos EUA, dados oficiais) ou "sintetico" (dataset de teste).
    llm: o modelo de linguagem (Ollama); sem modelo, as perguntas qualitativas ficam indisponíveis e nunca sai COMPRAR."""
    plat=Plataforma(jsonl, mostrar, fila_ui=fila_ui, ticker=ticker)
    t0=time.monotonic()
    modelo=f"{getattr(llm,'backend','?')}:{getattr(llm,'modelo','?')}" if llm else "sem modelo"
    _registar(f"{'='*20} {ticker.upper()} · fonte {fonte} · {anos} anos · modelo {modelo} · início {'='*20}")
    # 1) criar e registar os 5 agentes; os que usam o modelo de linguagem recebem `llm`, o Guardião é Python puro
    for ag in (Coletor(llm),Guardiao(),Avaliador(llm),Critico(llm),Decisor(llm)): plat.reg(ag)
    ts=datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # 2) a conversa começa com um pedido do utilizador ao Coletor; tudo o resto são respostas entre agentes
    pedido=Msg("request","utilizador","coletor",
               {"ticker":ticker.upper(),"anos":anos,"fonte":fonte,"preco":preco,"taxa":taxa,"taxa_alvo":taxa_alvo},
               conv=f"{ticker.upper()}-{ts}")
    rsp=plat.executar(pedido)       # 3) a plataforma entrega mensagens até chegar a resposta final ao utilizador
    # 4) se algo correu com limitações (modelo indisponível, por exemplo), o relatório diz-o antes da nota académica
    if plat.avisos and "relatorio" in rsp.conteudo:
        rel=rsp.conteudo["relatorio"].split("\n")
        corte=next((i for i,l in enumerate(rel) if l.startswith("Demonstração académica")),len(rel))
        rsp.conteudo["relatorio"]="\n".join(rel[:corte]+["Avisos de execução (esta análise correu com limitações):"]
                                            +[f"  {a}" for a in plat.avisos]+[""]+rel[corte:])
    op=(rsp.conteudo.get("oportunidade") or {}).get("categoria","-")      # COMPRAR, CAIXA DEDICADA, REJEITAR...
    _registar(f"{'='*20} {ticker.upper()} · {op} · Portões {rsp.conteudo.get('portoes_ok','-')}/10 · "
              f"{int(time.monotonic()-t0)} s{' · '+str(len(plat.avisos))+' aviso(s)' if plat.avisos else ''} {'='*20}")
    # 5) o resultado devolvido à interface: veredicto e relatório, mais as linhas, mensagens e eventos para mostrar o diálogo
    msgs=[{k:x[k] for k in ("id","performativa","remetente","destinatario")} for x in plat.msgs]  # conteúdo completo fica no JSONL
    return {"performativa":rsp.perf,**rsp.conteudo,"linhas":plat.linhas,"_msgs":msgs,
            "_eventos":plat.eventos,"_avisos":plat.avisos,"_segundos":round(time.monotonic()-t0,1),
            "_quando":datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),"_ticker":ticker.upper(),"_fonte":fonte,"_anos":anos}
