# Sistema Multiagente de Investimentos — guia do protocolo e do código

Este guia complementa o `README.md`: explica que passo do Protocolo v4.27 cabe a cada agente, como se calcula o preço e que
limites o sistema tem. Demonstração académica · não constitui aconselhamento financeiro.

## Os 5 agentes (como na proposta)

| Agente | Ficheiro | O que faz | Usa |
|---|---|---|---|
| A1 Coletor | `agentes/coletor.py` | obtém os dados (SEC ou dataset sintético), junta preço e taxa do Estado, normaliza tudo num JSON e marca o que falta como «em falta» | regras; o modelo só reconhece rótulos desconhecidos |
| A2 Guardião | `agentes/guardiao.py` | regras de exclusão: dados insuficientes, setor (Passo 0), Triagem T2–T7, Regra de Commodity | só regras em Python |
| A3 Avaliador | `agentes/avaliador.py` e `agentes/qualitativa.py` | perguntas qualitativas com o modelo (T1, Círculo, Wrigley, modelo de negócio, C2, C3, Franquia) e, em Python, os testes A, B e C, os 10 Portões e o preço | modelo + cálculo |
| A4 Crítico | `agentes/critico.py` | procura contradições entre as respostas e os números e números que não vieram dos dados; pode pedir uma revisão | regras + modelo |
| A5 Decisor | `agentes/decisor.py` | aplica as regras de decisão, escreve o relatório e uma síntese curta | regras + modelo |

A plataforma (`nucleo/plataforma.py`) entrega as mensagens FIPA-ACL entre eles e regista-as. `nucleo/analisar.py` monta os 5 agentes.

## O caminho de decisão (Secção 6 da v4.27)

| Passo | Pergunta | Quem responde | Resposta que exclui |
|---|---|---|---|
| -2 | Triagem Rápida (7 perguntas) | A2 Guardião (T2–T7, números) e A3 Avaliador (T1, com o modelo) | um "não" |
| -1 | Círculo de Competência, Teste Wrigley, patentes | A3 Avaliador (modelo, com fontes verificadas) | não |
| 0 | Setor: o método aplica-se? | A2 Guardião (SIC da SEC e setor do Yahoo) | cíclica, MLP, REIT |
| 1 | Modelo de negócio M1/M2/M3; Regra de Commodity | A3 Avaliador e A2 Guardião | commodity |
| 2–3 | Testes A1–A15, B1–B5, C1–C4: Sim / Parcial / Não | A3 Avaliador (Python, com as respostas verificadas do modelo) | — |
| 4 | Os 10 Portões | A3 Avaliador | um Portão falhado |
| 5 | Valor intrínseco, Equity Bond, Valor-Obrigação, PMC | A3 Avaliador | — |
| 6–8 | Decisão, checklist e veredito | A5 Decisor | preço acima do PMC |

O A4 Crítico (papel de Munger) confronta as respostas qualitativas do Avaliador com os números e pode devolvê-las uma vez.

Veredito: **COMPRAR** (Triagem + Portões + as quatro condições de preço CP1 a CP4), **CAIXA DEDICADA** (passa tudo menos o
preço: esperar) ou **REJEITAR**. Se o modelo discordou de si próprio ou o Crítico manteve uma objeção séria, um COMPRAR ou
CAIXA DEDICADA sai com uma *ressalva* (um aviso para confirmar antes de agir; nunca muda o veredito). Limite no momento da compra: 15% com Franquia e TACE de pelo menos 20%; 10% nos outros casos.

Diferenças em relação à proposta: a proposta descrevia o protocolo anterior (kill switches, DCF com margem de 25% e uma nota
de 0 a 100). O sistema aplica a versão atual, a v4.27, que decide por Portões e condições de preço, sem nota nem margem fixa.
A «zona condicional» da proposta corresponde, na v4.27, a CAIXA DEDICADA (bom negócio, preço ainda alto).

## Avaliação (Secção 8)
- r = taxa do Tesouro a 10 anos, sem prémio de risco, piso de **7%**; o Valor-Obrigação usa a taxa de mercado, sem piso
- Owner Earnings = lucro + D&A − capex de manutenção − SBC + variação do fundo de maneio; média por ação de 5 anos
- g = mínimo (CAGR do LPA ; CAGR do lucro ; ROE × retenção, se válido ; 15%), constante nos anos 1–10;
  g terminal = mínimo (2,5% ; g/2)
- TACE pelo Método I (LPA) e pelo Método II (ROE), usa-se a mais baixa; P/L-alvo = mínimo (média de 10 anos ; 25)
- PMC = mínimo (Valor Intrínseco ; preço para 15% ao ano ; Valor-Obrigação). Sem margem fixa. Sem beta.

## Fontes de dados

| Fonte | O quê | Chave |
|---|---|---|
| SEC EDGAR (10-K, 20-F, 40-F; US-GAAP ou IFRS) | demonstrações financeiras de empresas dos EUA e estrangeiras registadas na SEC (ADR) | não (nome e email no pedido) |
| Yahoo Finance (yfinance) | preço, dividendos, câmbios; completa linhas em falta da SEC | não |
| Tesouro dos EUA, Bundesbank, FRED | taxa do Estado a 10 anos | não |
| FDIC BankFind | bancos americanos: CET1, NPL, NIM (Portões P3 e P8) | não |
| Alpha Vantage (opcional) | completa linhas e o histórico de LPA | grátis, 25 pedidos por dia |
| `dados/empresas_sinteticas.json` | 19 empresas inventadas, cada uma desenhada para testar uma regra ou um caso de falha | incluído |

## Limites conhecidos
- Só empresas registadas na SEC (EUA e ADR). As outras não têm, em fonte gratuita e uniforme, os 5 a 10 anos de que o protocolo precisa.
- Bancos de fora dos EUA e seguradoras: CET1, NPL e solvência não existem em fonte gratuita; os Portões P3 e P8 ficam sem
  dados e a empresa é rejeitada.
- Triagem T7 (FCO) não se aplica a bancos e seguradoras: calibração por analogia com a v4.25.
- Não verificados automaticamente: remuneração dos gestores e Form 4 (B4), problema solucionável (Secção 6.4) e o cartão de
  20 decisões.
- O modelo local (qwen2.5:7b) é pequeno: as respostas qualitativas podem errar. Por isso cada citação é verificada nas fontes,
  números inventados são assinalados, o Crítico confronta as respostas com os números e o veredito é sempre das regras.
