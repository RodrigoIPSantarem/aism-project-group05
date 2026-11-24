# Sistema Multiagente de Investimentos — AISM Grupo 05

Um sistema multiagente que aplica um protocolo pessoal de investimento em valor (inspirado em Warren Buffett, versão v4.27) a
uma empresa cotada. Dada uma empresa e um período de análise (5 ou 10 anos), cinco agentes que trocam mensagens FIPA-ACL recolhem os
dados, aplicam as regras de exclusão, avaliam o negócio e o preço, criticam a avaliação e decidem. O resultado é um veredicto
(COMPRAR, CAIXA DEDICADA ou REJEITAR, os três do protocolo) com os motivos e as objeções do Crítico.

*Projeto académico de Agentes Inteligentes e Sistemas Multiagentes (ESGTS, Universidade Politécnica de Santarém).
Não constitui aconselhamento financeiro.*

**Elementos do grupo:** Rodrigo Silva (240000762) · Guilherme Caçador (240000675)

**Repositório:** https://github.com/RodrigoIPSantarem/aism-project-group05

---

## Os 5 agentes

| Agente | O que faz | Usa |
|---|---|---|
| A1 Coletor | obtém os dados financeiros (SEC ou dataset sintético) e normaliza-os; o que não encontra fica «em falta» | dados + modelo (só para reconhecer rótulos) |
| A2 Guardião | aplica as regras de exclusão do protocolo (dados insuficientes, setor, Triagem); se uma disparar, a empresa vai direta ao Decisor | só regras em Python |
| A3 Avaliador | responde às perguntas qualitativas com o modelo (citações verificadas) e calcula os testes, os 10 Portões e o preço máximo de compra | modelo + cálculo em Python |
| A4 Crítico | procura falhas na avaliação (contradições com os números, números que não vieram dos dados); pode pedir **uma** revisão | regras + modelo |
| A5 Decisor | aplica as regras de decisão e escreve o relatório | regras + modelo (só uma síntese) |

O modelo de linguagem corre no computador (Ollama, `qwen2.5:7b`, temperatura 0). O veredicto é sempre das regras.

## 1. Instalação

| Requisito | Notas |
|---|---|
| Python 3.10 ou mais recente, com Tkinter | Testado com o Python 3.12.3. No Windows, marcar "Add python.exe to PATH" no instalador. |
| `yfinance` | `pip install -r requirements.txt` (o arranque no Windows faz isto sozinho). |
| Ollama + modelo `qwen2.5:7b` | Gratuito e local: instalar em https://ollama.com e depois `ollama pull qwen2.5:7b` (ou deixar a interface descarregá-lo). |
| Contas / chaves de API | **Nenhuma obrigatória.** Opcional: uma chave gratuita da Alpha Vantage (dados de reserva). |

A configuração fica num ficheiro `.env`, criado automaticamente a partir do `.env.example` na primeira vez que o programa corre e
alterável na janela **Definições**. A SEC pede um nome e um email em cada pedido (`SEC_USER_AGENT`); não é preciso conta.
**O `.env` está no `.gitignore`: nunca o enviar para o repositório.**

```bash
git clone https://github.com/RodrigoIPSantarem/aism-project-group05.git
cd aism-project-group05
pip install -r requirements.txt
ollama pull qwen2.5:7b
```

## 2. Como correr

**Interface gráfica** (`python main.py`, ou duplo clique em `Abrir.pyw` no Windows):

1. Abrir o Ollama e depois o programa. No canto superior direito deve aparecer "Modelo qwen2.5:7b: pronto". Se o Ollama só abrir
   depois, basta voltar à janela do programa: o estado é verificado outra vez sozinho.
2. À esquerda, escolher a empresa (ticker), a fonte (dataset sintético ou SEC) e **5 ou 10 anos**, e carregar em **Analisar**.
3. Ao centro, as 5 caixas dos agentes acendem-se à medida que recebem mensagens, com a performativa em cada seta; o arco laranja
   é a revisão pedida pelo Crítico e a linha vermelha é a rejeição imediata. Por baixo aparece o veredicto, o preço atual, o preço
   máximo de compra, a TACE e os Portões, com o motivo. Os separadores têm o relatório completo, os Portões e testes, o
   pensamento dos agentes (ao vivo) e a lista das mensagens FIPA-ACL.

**Linha de comandos:**

| O quê | Comando |
|---|---|
| Analisar uma empresa real (SEC) | `python main.py KO` (`--anos 5` para 5 anos) |
| Analisar uma empresa sintética | `python main.py AURORA` |
| Listar as empresas sintéticas | `python main.py --listar` |
| Testes das regras (sem Ollama nem rede) | `python -m pytest -q` ou `python tests/test_agentes.py --so-regras` |
| As 19 empresas sintéticas com o modelo real (Ollama aberto; devolve `saidas/teste_sinteticos.json`) | `python tests/test_agentes.py` |
| Empresas reais da SEC com o modelo real (Ollama aberto; devolve `saidas/teste_real.json`) | `python experiments/teste_real.py` (`--tickers KO,PG` para só algumas) |
| Repetir as experiências do relatório | `python experiments/run_experiments.py --rapido` (E1, E2 e E4; a E2 descarrega 13 empresas da SEC) ou sem `--rapido` (E1 a E4; a E3 demora cerca de 1 hora) |
| Redesenhar os gráficos do relatório | `pip install -r experiments/requirements-experiments.txt`, `python experiments/make_figures.py` e `python experiments/make_architecture.py` (`--lingua en` nos gráficos para a versão inglesa) |

Na linha de comandos, se o Ollama não estiver a correr ou o modelo não estiver instalado, o programa avisa logo e termina.

**Casos de erro para demonstração.** Não se escrevem dados errados à mão: o dataset sintético tem empresas desenhadas para falhar
de maneiras diferentes. Todas acabam em `REJEITAR` sem inventar valores.

| Ticker | O que falha | Resultado |
|---|---|---|
| `NEVOA` | fluxo de caixa apagado em 3 dos 5 anos | só 3 anos completos: dados insuficientes (nada é inventado) |
| `ORLA` | só 3 anos de histórico | dados insuficientes |
| `SILEX` | lucro acima da receita (dados incoerentes) | o Coletor assinala e o Guardião rejeita |
| `GRANITO` | fluxo de caixa operacional negativo em 2 anos | rejeição imediata na Triagem T7 |
| `IRIS` | diluição de cerca de 19% em 3 anos | rejeição imediata na Triagem T6 |
| `HORIZONTE`, `MARE` | energia e transportes, fora do método | rejeição imediata no Passo 0 |

A experiência E4 (`python experiments/run_experiments.py --rapido`) mostra também o sistema a travar modelos simulados que inventam
uma citação, citam números que não existem ou objetam sempre (no máximo uma revisão).

## 3. Resultado esperado

Na linha de comandos (`python main.py AURORA`), cada agente diz o que está a fazer:

```
AURORA [A1 Coletor]    514 valores, 0 em falta
AURORA [A2 Guardião]   setor padrao: Triagem (T2–T7), Regra de Commodity e filtros base aprovados
AURORA [A3 Avaliador]  T1 Sim, círculo Sim, Wrigley Sim, modelo M1, C3 Sim, franquia 4/4 sim
AURORA [A3 Avaliador]  Portões 10/10 · franquia sim · TACE 17,0% · PMC 31,53 (P_EB)
AURORA [A4 Crítico]    sem objeções: aceite
AURORA [A5 Decisor]    COMPRAR · Portões 10/10 · TACE 17,0%
```

A seguir aparece o relatório completo, passo a passo como no protocolo. Veredictos: `COMPRAR`, `CAIXA DEDICADA` (bom negócio,
mas o preço ainda não é atrativo: esperar), e `REJEITAR`. Se um COMPRAR ou CAIXA DEDICADA tiver uma ressalva (o modelo discordou de si próprio
ou o Crítico manteve uma objeção grave), o veredicto é o mesmo e o relatório junta-lhe a palavra RESSALVA com o motivo.

| Ficheiro | Conteúdo |
|---|---|
| `saidas/<TICKER>.jsonl` | todas as mensagens FIPA-ACL da análise, com o conteúdo (auditoria) |
| `saidas/logs/sessao_AAAA-MM-DD.log` | registo de todos os agentes, com o ticker em cada linha |
| `saidas/historico/` | cada análise feita na interface, em JSON (aparece na lista "Histórico") |
| `saidas/exportacoes/` | relatórios exportados pela interface (TXT e JSON) |

Há um guia do protocolo em `docs/LEIA-ME.md` e um roteiro para a apresentação em `docs/GUIA_APRESENTACAO.md`.

## 4. Dados

Não é preciso descarregar nenhum dataset à mão: o Coletor vai buscar os dados no momento da análise a fontes gratuitas e guarda
uma cópia em `dados/cache_*` (que não vai para o repositório).

| Fonte | O quê | Acesso |
|---|---|---|
| SEC EDGAR `companyfacts` e relatórios | demonstrações financeiras 10-K / 20-F / 40-F em XBRL (US-GAAP ou IFRS) e texto do relatório anual | gratuito, domínio público, cabeçalho com nome e email |
| Yahoo Finance (`yfinance`) | preços, dividendos, câmbios e dados de reserva para linhas em falta na SEC | gratuito, sem chave |
| Tesouro dos EUA, Bundesbank, FRED | taxas de juro das obrigações do Estado a 10 anos | gratuito, sem chave |
| FDIC BankFind | rácios regulatórios dos bancos americanos (CET1, NPL, NIM) | gratuito, sem chave |
| `dados/empresas_sinteticas.json` | 19 empresas sintéticas (10 anos cada) desenhadas para testar cada regra e cada caso de falha | incluído |

Os resultados das experiências (CSV e gráficos) estão em `experiments/results/`: gráficos em português em `figures/` e da versão
inglesa do relatório em `figures_en/`. Os nomes das colunas dos CSV ficam em inglês curto, como identificadores.

## 5. Estrutura do repositório

```
main.py                 ponto de entrada: interface gráfica, ou linha de comandos (python main.py TICKER)
Abrir.pyw / Abrir.bat   arranque no Windows (duplo clique; instala o que faltar na primeira vez)
config.py               parâmetros do Protocolo v4.27 (limiares da Triagem, testes, Portões, preço) e lista da experiência E3
agentes/                os 5 agentes: coletor (A1), guardiao (A2), avaliador (A3, com a parte do modelo em qualitativa.py),
                        critico (A4), decisor (A5)
nucleo/                 plataforma FIPA-ACL (plataforma.py), montagem dos agentes (analisar.py), cliente do modelo (llm.py),
                        testes e Portões (testes.py), preço (valorizacao.py), configuração do .env e do Ollama (configuracao.py)
fontes/                 SEC (sec.py, xbrl.py), mercado (mercado.py), reservas (reserva.py), FDIC (fdic.py), texto dos
                        relatórios (qualitativas.py), dataset sintético (sintetico.py)
interface/              janela Tkinter: app.py (janela principal), fluxo.py (as 5 caixas dos agentes), pensamento.py,
                        historico.py, tema.py (cores e letra)
dados/                  dataset sintético (as caches são criadas aqui durante a execução)
tests/                  test_agentes.py: testes das regras (sem Ollama) e as 19 empresas sintéticas com o modelo real (JSON)
experiments/            experiências do relatório: modelos simulados, script das experiências, gráficos, resultados
docs/                   guia do protocolo e roteiro da apresentação
```

## 6. Grupo

Rodrigo Silva (240000762) e Guilherme Caçador (240000675) · contacto: 240000762@esg.ipsantarem.pt

Licença: MIT (ver `LICENSE`).