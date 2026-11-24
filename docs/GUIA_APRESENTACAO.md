# Guia para apresentar o projeto

Roteiro para a apresentação e a defesa: o que mostrar, por onde começar no código e que perguntas se podem esperar.
Os comentários no código (cabeçalho de cada ficheiro e as notas "Para a apresentação") seguem a mesma ordem.

## 1. Ideia em duas frases

O protocolo de investimento de valor do Rodrigo (v4.27, inspirado em Buffett) é uma sequência de passos com regras fixas e
algumas perguntas de julgamento. Cada passo foi entregue a um de 5 agentes, que só comunicam por mensagens FIPA-ACL; o agente
que filtra e o que critica são independentes do que avalia, por isso nenhum valida o próprio trabalho.

## 2. Fluxo de uma análise

| Passo | Agente | Mensagem que recebe → que envia | Usa o modelo? |
|---|---|---|---|
| 1 | A1 Coletor | `request` do utilizador → `inform` ao Guardião (ou `failure` se não há dados) | só para rótulos desconhecidos |
| 2 | A2 Guardião | `inform` → `request` ao Avaliador, ou `inform` direto ao Decisor (rejeição imediata) | não |
| 3 | A3 Avaliador | `request` → `propose` ao Crítico, ou `inform` ao Decisor (pergunta eliminatória falhada) | sim (perguntas qualitativas) |
| 4 | A4 Crítico | `propose` → `reject-proposal` ao Avaliador (no máximo uma vez) ou `inform` ao Decisor | regras + modelo |
| 5 | A5 Decisor | `inform` → `inform` ao utilizador, com o veredicto e o relatório | só a síntese de 3 frases |

Se o Crítico pede uma segunda revisão, o Avaliador responde `refuse` (`MAX_REVISOES = 1` em `config.py`) e o fluxo termina.

## 3. Demonstração (5 minutos)

1. Abrir o Ollama e o programa (`Abrir.pyw`). No canto superior direito: "Modelo qwen2.5:7b: pronto".
2. **Caso que compra:** fonte "Dataset sintético", `AURORA`, 10 anos, Analisar. Mostrar as 5 caixas a acender, as setas com as
   performativas e o resultado (COMPRAR, preço máximo de compra, TACE, Portões 10/10).
3. **Rejeição imediata:** `GRANITO` (fluxo de caixa negativo). O Guardião rejeita, a linha vermelha acende e o Avaliador e o
   Crítico ficam "à espera": não gastam tempo nem modelo.
4. **Caso de falha da proposta (dados em falta):** `NEVOA` (fluxo de caixa apagado em 3 de 5 anos). O Coletor marca «em falta»,
   o Guardião rejeita por dados insuficientes: nada é inventado. `SILEX` (lucro acima da receita) mostra os dados incoerentes.
5. **Empresa real:** fonte "SEC", `KO` ou `PG`. Separadores "Portões e testes" e "Mensagens FIPA-ACL".
6. **Salvaguardas contra o modelo (no terminal):** `python experiments/run_experiments.py --rapido` corre a E4, com modelos
   simulados que inventam uma citação, citam números que não existem ou objetam sempre.

## 4. Decisões de desenho que convém saber justificar

- **O modelo nunca calcula nem decide.** Contas, limiares e veredicto são Python; o modelo responde a perguntas qualitativas, cada
  citação é verificada nas fontes e os números que não vieram dos dados são assinalados (`_numeros_nao_verificados`).
- **Repetibilidade:** temperatura 0 e cache em disco por pergunta (`nucleo/llm.py`).
- **Só Ollama, local:** nenhum dado sai do computador; não há chaves nem custos de API.
- **Registo de auditoria:** cada análise grava todas as mensagens num `.jsonl` em `saidas/`, e o registo da sessão em `saidas/logs/`.
- **Falhar de forma visível:** sem 5 anos de dados completos, a análise é rejeitada com o motivo; sem modelo, nunca sai COMPRAR.

## 5. Perguntas prováveis

- **Porque agentes e não funções?** Cada agente tem uma responsabilidade e um contrato (mensagens); a conversa fica auditável e o
  Crítico pode devolver trabalho ao Avaliador, o que não cabe num pipeline linear.
- **O modelo não pode errar?** Pode. Por isso só responde a perguntas qualitativas, com citação verificada, e o Crítico confronta-o
  com os números. O veredicto final nunca depende dele.
- **Porque não há nota de 0 a 100 como na proposta?** A proposta descrevia a versão anterior do protocolo. A v4.27, aplicada
  aqui, decide por Portões e condições de preço; a zona condicional passou a ser CAIXA DEDICADA.
- **Como se sabe que funciona?** E1 (19 empresas sintéticas, cada uma com o comportamento esperado), E2 (13 empresas analisadas à
  mão), E3 (108 empresas reais da SEC) e E4 (salvaguardas). Os testes sem rede nem Ollama: `python tests/test_agentes.py`.
