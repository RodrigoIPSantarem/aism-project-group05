"""Sistema Multiagente de Investimentos — AISM Grupo 5
Rodrigo Silva (240000762) · Guilherme Caçador (240000675)

Ponto de entrada. Interface gráfica: python main.py · Linha de comandos: python main.py KO (ou AURORA, do dataset sintético)"""
import argparse, sys
try:
    import tkinter as tk
except ImportError:      # sem interface gráfica: a linha de comandos continua a funcionar
    tk=None
from config import ANOS_ANALISE, RAIZ, TAXA_RENTABILIDADE_ALVO
from fontes.sintetico import _sint_listar
from nucleo.analisar import analisar
from nucleo.configuracao import garantir_env, modelos_ollama, tem_modelo
from nucleo.llm import _criar_llm
from nucleo.util import _carregar_env


if __name__ == "__main__":
    garantir_env(); _carregar_env()            # primeira utilização: o .env é criado a partir do .env.example
    if len(sys.argv)>1:
        p=argparse.ArgumentParser(description="Sistema Multiagente de Investimentos (5 agentes, Protocolo v4.27)")
        p.add_argument("ticker",nargs="?",help="ticker da empresa (ex.: KO) ou de uma empresa sintética (ex.: AURORA)")
        p.add_argument("--anos",type=int,choices=[5,10],default=ANOS_ANALISE,help="anos de histórico (5 ou 10; defeito 10)")
        p.add_argument("--fonte",choices=["auto","sintetico","sec"],default="auto",
                       help="auto: dataset sintético se o ticker lá existir, senão SEC")
        p.add_argument("--preco",type=float,help="opcional: por defeito é recolhido automaticamente")
        p.add_argument("--taxa",type=float,help="opcional: taxa do Estado a 10 anos em %%, por defeito automática")
        p.add_argument("--alvo",type=float,default=TAXA_RENTABILIDADE_ALVO*100,help="retorno anual desejado em %% (defeito 20)")
        p.add_argument("--listar",action="store_true",help="lista as empresas do dataset sintético")
        args=p.parse_args()
        if args.listar:
            for e in _sint_listar(): print(f"{e['ticker']:<10} {e['name']:<26} {e.get('_caso','')}")
            sys.exit(0)
        if not args.ticker: p.error("indicar o ticker ou --listar")
        llm=_criar_llm(RAIZ/"dados"/"cache_llm")
        instalados=modelos_ollama()
        if instalados is None:
            print("ERRO: o Ollama não está a correr. Abre o Ollama (ollama.com) e volta a correr o comando."); sys.exit(2)
        if not tem_modelo(llm.modelo,instalados):
            print(f"ERRO: o modelo {llm.modelo} não está instalado. Corre: ollama pull {llm.modelo}"); sys.exit(2)
        fonte=args.fonte
        if fonte=="auto":
            fonte="sintetico" if args.ticker.upper() in {e["ticker"] for e in _sint_listar()} else "sec"
        print(f"$ analisar {args.ticker.upper()} --anos {args.anos} --fonte {fonte} [modelo {llm.backend}/{llm.modelo}]")
        r=analisar(args.ticker,args.anos,fonte,llm,args.preco,args.taxa,taxa_alvo=args.alvo/100,
                   jsonl=RAIZ/"saidas"/f"{args.ticker.upper()}.jsonl")
        if r["performativa"]=="failure": print(f"Erro: {r['motivo']}"); sys.exit(1)
        print(r["relatorio"])
        sys.exit(0)
    if tk is None:
        print("Tkinter não está disponível nesta instalação do Python."); sys.exit(1)
    from interface.app import App
    App().mainloop()
