# Sistema Multiagente de Investimentos — AISM Grupo 05

Projeto académico da unidade curricular **Agentes Inteligentes e Sistemas Multiagentes**, da Escola Superior de Gestão e Tecnologia de Santarém, Universidade Politécnica de Santarém.

O programa analisa uma empresa cotada segundo o Protocolo de Investimentos v4.27, inspirado no investimento em valor. Cinco agentes cooperam através de mensagens ao estilo FIPA-ACL. O resultado é um relatório explicável com um de três vereditos: **COMPRAR**, **CAIXA DEDICADA** ou **REJEITAR**.

> **Aviso:** este é um projeto académico para demonstração de um sistema multiagente. Não executa ordens de compra ou venda e não constitui aconselhamento financeiro.

**Elementos do grupo:** Rodrigo Silva (240000762) e Guilherme Caçador (240000675)
**Repositório:** https://github.com/RodrigoIPSantarem/aism-project-group05

## Índice

- [O que o sistema faz](#o-que-o-sistema-faz)
- [Como funciona uma análise](#como-funciona-uma-análise)
- [Os cinco agentes](#os-cinco-agentes)
- [Dados utilizados](#dados-utilizados)
- [Instalação](#instalação)
- [Executar o programa](#executar-o-programa)
- [Testes e experiências](#testes-e-experiências)
- [Resultados e ficheiros gerados](#resultados-e-ficheiros-gerados)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Configuração](#configuração)
- [Limitações conhecidas](#limitações-conhecidas)
- [Resolução de problemas](#resolução-de-problemas)
- [Documentação adicional](#documentação-adicional)

## O que o sistema faz

Dada uma empresa e um período de análise de 5 ou 10 anos, o sistema:

1. Obtém e normaliza dados financeiros, de mercado e, quando disponíveis, dados qualitativos.
2. Verifica se existem dados suficientes e aplica filtros de exclusão.
3. Avalia qualitativamente o negócio e calcula os testes financeiros do protocolo.
4. Verifica a avaliação através de um agente Crítico.
5. Aplica as regras finais e produz um relatório com os dados, os cálculos, as mensagens e os motivos do veredito.

O sistema tem dois caminhos de dados:

- **Empresas reais:** dados recolhidos sobretudo da SEC EDGAR, com informação complementar de serviços financeiros públicos.
- **Empresas sintéticas:** 19 empresas incluídas no repositório, construídas para demonstrar comportamentos e casos de erro específicos.

O modelo de linguagem é executado localmente através do Ollama. É usado para algumas perguntas qualitativas e para escrever uma síntese curta. Os cálculos e o veredito final são determinados por código Python. As respostas qualitativas do modelo podem afetar a análise — por exemplo, uma resposta eliminatória pode levar à rejeição — e são verificadas por regras, fontes e pelo agente Crítico.

## Como funciona uma análise

O ponto de entrada é uma mensagem do utilizador ao Coletor. A plataforma entrega cada mensagem ao respetivo agente e regista as mensagens trocadas.

    Utilizador
        │ request
        ▼
    A1 Coletor ── inform ──► A2 Guardião ── request ──► A3 Avaliador
                                 │                           │
                      rejeição imediata                    propose
                                 │                           ▼
                                 └──────────────────────► A5 Decisor ◄── inform ── A4 Crítico
                                                             │
                                                         veredito
                                                             ▼
                                                         Utilizador

Quando o Crítico encontra um problema que justifica correção, pode enviar uma mensagem reject-proposal ao Avaliador. O Avaliador revê a proposta e envia-a novamente ao Crítico. Este ciclo tem um limite de **uma revisão** para impedir que os agentes entrem num ciclo infinito. O fluxo também termina cedo quando uma regra de exclusão é acionada.

Cada mensagem tem uma performativa, um emissor, um destinatário, um identificador e o conteúdo. A plataforma implementa a troca de mensagens necessária a este projeto, inspirada na FIPA-ACL; não é uma implementação completa da plataforma JADE ou de toda a norma FIPA.

## Os cinco agentes

| Agente | Responsabilidade | Papel do modelo de linguagem |
|---|---|---|
| **A1 Coletor** | Obtém os dados financeiros, de mercado e qualitativos; normaliza unidades, anos e proveniência; assinala valores em falta e incoerências. | Pode ajudar a reconhecer rótulos financeiros desconhecidos. Não inventa valores em falta. |
| **A2 Guardião** | Aplica verificações de suficiência dos dados, regras de setor, Triagem numérica T2–T7, filtros base e regras de exclusão. Se uma regra falhar, envia a rejeição diretamente ao Decisor. | Não usa o modelo para as decisões deste agente. |
| **A3 Avaliador** | Responde às perguntas qualitativas, calcula testes A/B/C, os 10 Portões, a avaliação financeira e o preço máximo de compra. | Usa o modelo para perguntas de julgamento e evidência textual; Python faz as contas e aplica os limiares. |
| **A4 Crítico** | Procura contradições entre a avaliação, as respostas qualitativas e os dados; pode pedir uma revisão ao Avaliador. | Combina verificações por regras com uma análise do modelo. |
| **A5 Decisor** | Aplica as regras finais, determina o veredito e prepara o relatório. | Pode escrever uma síntese curta a partir de factos já determinados. Não pode alterar o veredito. |

### Perguntas e cálculos principais

O protocolo inclui uma Triagem Rápida, regras por setor e modelo de negócio, testes financeiros e qualitativos, 10 Portões e condições de preço. Entre os pontos analisados estão o crescimento dos lucros por ação, o ROE, a dívida, as margens, a diluição das ações e o fluxo de caixa operacional.

Na avaliação, o código calcula, entre outros elementos:

- Owner Earnings por ação e valor intrínseco;
- crescimento usado nas projeções e valor terminal;
- TACE pelos métodos previstos no protocolo;
- preço para o retorno anual exigido;
- Valor-Obrigação e Preço Máximo de Compra (PMC).

O PMC corresponde ao mais baixo entre os limites calculados pelo método de valor intrínseco, pelo retorno anual exigido e pelo Valor-Obrigação. O relatório mostra as premissas e valores usados. Consulte a versão v4.27 do protocolo para a definição completa de cada regra; os parâmetros implementados estão em config.py.

### Vereditos

- **COMPRAR:** passa os filtros, os Portões e as condições de preço aplicáveis.
- **CAIXA DEDICADA:** passa os critérios de qualidade, mas o preço atual ainda não cumpre as condições de compra; significa esperar segundo o protocolo.
- **REJEITAR:** falha uma regra eliminatória, não tem dados suficientes ou não consegue concluir as verificações exigidas.

Se houver uma dúvida entre duas leituras qualitativas ou uma objeção grave mantida pelo Crítico, o relatório acrescenta uma **RESSALVA**. Na versão atual, a ressalva não cria um quarto veredito nem muda a categoria determinada pelas regras.

## Dados utilizados

| Fonte | Utilização | Acesso |
|---|---|---|
| **SEC EDGAR** | Demonstrações e relatórios anuais de empresas registadas na SEC; usa dados XBRL e documentos como 10-K, 20-F e 40-F. | Gratuito. Os pedidos incluem identificação de contacto no cabeçalho SEC_USER_AGENT. |
| **Yahoo Finance / yfinance** | Preços, dividendos, câmbios e preenchimento de alguns valores em falta. | Gratuito, sem chave de API; disponibilidade e cobertura podem variar. |
| **Tesouro dos EUA, Bundesbank e FRED** | Taxas de referência das obrigações a 10 anos, conforme a moeda e disponibilidade. | Fontes públicas. |
| **FDIC BankFind** | Indicadores regulatórios de bancos dos EUA, como CET1, NPL e NIM. | Gratuito. |
| **Alpha Vantage** | Fonte opcional para complementar alguns dados. | Chave gratuita opcional, sujeita aos limites do serviço. |
| **Dataset sintético** | 19 empresas artificiais para reproduzir regras e situações de falha. | Incluído em dados/empresas_sinteticas.json. |

Os dados em falta permanecem em falta; o sistema não pede ao modelo para adivinhar valores financeiros. Quando uma fonte complementar preenche um campo, o sistema regista a sua origem. Os dados descarregados são guardados em cache local para evitar pedidos repetidos.

A análise de empresas reais exige acesso à Internet para consultar as fontes de dados. As chamadas ao modelo de linguagem são enviadas para o servidor Ollama configurado, que por defeito corre no próprio computador.

## Instalação

### Requisitos

- Windows, macOS ou Linux.
- Python **3.10 ou superior**.
- Tkinter para usar a interface gráfica. Em algumas distribuições Linux, Tkinter pode ter de ser instalado separadamente.
- Ollama instalado e em execução para as análises que usam o modelo.
- O modelo qwen2.5:7b, ou outro modelo compatível configurado no programa.
- Ligação à Internet para recolher dados de empresas reais e instalar dependências.

A aplicação usa principalmente a biblioteca padrão do Python. A dependência da aplicação listada em requirements.txt é yfinance. As dependências de geração de gráficos das experiências estão separadas em experiments/requirements-experiments.txt.

### Instalação no Windows

1. Instala Python 3.10 ou superior e seleciona **Add python.exe to PATH** no instalador.
2. Instala o Ollama a partir de https://ollama.com.
3. Abre o PowerShell na pasta do projeto e instala as dependências:

~~~powershell
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
~~~

4. Inicia o Ollama. No Windows, normalmente fica a correr em segundo plano junto ao relógio.
5. Abre Abrir.pyw com duplo clique ou executa:

~~~powershell
python main.py
~~~

Abrir.bat procura pythonw ou pyw e tenta iniciar a interface sem mostrar a consola. Abrir.pyw instala as dependências de requirements.txt que estiverem em falta e cria o ficheiro .env na primeira utilização.

### Instalação em macOS ou Linux

Na pasta do projeto:

~~~bash
python3 -m pip install -r requirements.txt
ollama pull qwen2.5:7b
python3 main.py
~~~

Se Python não incluir Tkinter, instala o pacote Tkinter fornecido pela tua distribuição. Também podes usar a linha de comandos sem interface gráfica, desde que Python e Ollama estejam configurados.

### Modelo mais pequeno

A interface oferece qwen2.5:3b como alternativa. Um modelo mais pequeno pode usar menos recursos, mas pode responder de forma diferente às perguntas qualitativas. Para uma análise académica reproduzível, regista qual o modelo utilizado.

## Executar o programa

### Interface gráfica

~~~powershell
python main.py
~~~

Também podes abrir Abrir.pyw ou Abrir.bat no Windows.

1. Espera que o indicador do modelo mostre que está pronto.
2. Escolhe a fonte dos dados: dataset sintético ou SEC.
3. Escolhe uma empresa e o período de 5 ou 10 anos.
4. Carrega em **Analisar**.
5. Consulta o resultado, o relatório, os testes e Portões, os eventos dos agentes e as mensagens.

A interface inclui uma lista de empresas, o estado do Ollama, o fluxo visual dos agentes, o veredito, o preço atual, o PMC, a TACE, o histórico e opções para exportar relatórios.

### Linha de comandos

~~~powershell
# Ver as empresas sintéticas
python main.py --listar

# Analisar uma empresa sintética
python main.py AURORA

# Analisar uma empresa real da SEC
python main.py KO

# Usar apenas 5 anos de dados
python main.py KO --anos 5

# Escolher explicitamente a fonte
python main.py AURORA --fonte sintetico
python main.py KO --fonte sec

# Definir manualmente preço, taxa de referência ou alvo informativo
python main.py KO --preco 60 --taxa 4.2 --alvo 20

# Ver todas as opções
python main.py --help
~~~

A fonte auto é a predefinição: se o ticker existir no dataset sintético, usa esse dataset; caso contrário, tenta a SEC. O alvo fornecido com --alvo é informativo e pode ser diferente do retorno usado nas condições do protocolo. Os parâmetros completos estão descritos na ajuda do comando.

O comando de análise individual verifica se o servidor Ollama está acessível e se o modelo escolhido está instalado. Sem o Ollama ou sem o modelo, o comando termina com uma mensagem de erro.

### Empresas sintéticas úteis para demonstração

| Ticker | Caso demonstrado |
|---|---|
| AURORA | Caso construído para ilustrar uma empresa de qualidade com resultado potencial de compra. |
| GRANITO | Fluxo de caixa operacional negativo; exemplo de rejeição pela Triagem T7. |
| NEVOA | Fluxo de caixa em falta em vários anos; demonstra que o sistema não inventa valores. |
| ORLA | Histórico inferior ao mínimo exigido. |
| SILEX | Dados incoerentes, como lucro superior à receita. |
| IRIS | Diluição de ações acima do limite da Triagem T6. |
| HORIZONTE e MARE | Setores fora do âmbito do método usado no projeto. |

Os resultados exatos dependem dos dados, das regras atuais e das respostas qualitativas do modelo. Para demonstrações, usa primeiro o dataset sintético; uma análise SEC depende da rede e das fontes externas.

## Testes e experiências

Há três tipos diferentes de execução. Os testes das regras não precisam do Ollama; os lotes com modelo real precisam dele; as experiências reproduzíveis usam modelos simulados.

### Testes das regras

~~~powershell
# Testa regras e fluxo sem modelo real; não requer SEC nem Ollama
python tests/test_agentes.py --so-regras
~~~

Também é possível usar pytest, se estiver instalado:

~~~powershell
python -m pytest -q
~~~

pytest não está listado em requirements.txt; o comando direto com --so-regras não precisa dessa dependência.

### Dataset sintético com Ollama real

~~~powershell
# Corre os testes das regras e depois analisa as 19 empresas sintéticas com o modelo
python tests/test_agentes.py

# Executa apenas algumas empresas
python tests/test_agentes.py --tickers AURORA,BOREAL

# Retoma as empresas ainda não concluídas no JSON de saída
python tests/test_agentes.py --continuar

# Não reutiliza as respostas qualitativas guardadas em cache
python tests/test_agentes.py --sem-cache
~~~

O lote aquece o modelo antes de cada empresa e pede ao Ollama para o descarregar entre análises. Isto mantém o modelo disponível durante os vários pedidos de cada empresa e reduz a acumulação de memória entre empresas. A descarga é uma tentativa de libertar o modelo; se o servidor Ollama falhar, consulta o respetivo registo. O lote pode demorar mais porque o modelo precisa de voltar a carregar.

As respostas bem-sucedidas do modelo são guardadas em dados/cache_llm. O JSON de teste fica em saidas/teste_sinteticos.json. A opção --continuar usa esse JSON para saltar empresas já concluídas; por omissão, o teste volta a analisar a lista indicada, mas pode reutilizar respostas do cache.

### Empresas reais com Ollama

~~~powershell
# Analisa a lista predefinida de empresas reais
python experiments/teste_real.py

# Analisa apenas os tickers indicados
python experiments/teste_real.py --tickers KO,AAPL

# Escolhe 5 ou 10 anos
python experiments/teste_real.py --anos 5

# Ignora resultados já existentes no JSON de saída
python experiments/teste_real.py --refazer

# Escolhe outro ficheiro de saída
python experiments/teste_real.py --saida saidas/lote_teste.json

# Variante em tests/: retoma os resultados existentes e pode desativar a cache LLM
python tests/teste_real.py --tickers KO,AAPL --continuar
python tests/teste_real.py --sem-cache
~~~

O teste guarda os resultados em saidas/teste_real.json e atualiza o ficheiro após cada empresa. A entrada principal documentada é experiments/teste_real.py; tests/teste_real.py é uma variante que oferece --continuar e --sem-cache. Ambas aquecem o modelo para cada empresa e pedem ao Ollama para o descarregar depois da análise. Na entrada principal, as análises concluídas são ignoradas por defeito; --refazer volta a analisá-las. Na variante em tests/, só são ignoradas quando se usa --continuar.

### Experiências reprodutíveis com modelo simulado

~~~powershell
# E1, E2 e E4, sem chamar o Ollama para responder às perguntas qualitativas
python experiments/run_experiments.py --rapido

# Só experiências específicas
python experiments/run_experiments.py --so e1,e4

# Todas as experiências implementadas, incluindo E3
python experiments/run_experiments.py
~~~

- **E1:** testa o comportamento esperado das empresas sintéticas.
- **E2:** compara com o conjunto de empresas analisadas manualmente pelo grupo; consulta dados reais da SEC.
- **E3:** analisa um universo de empresas SEC definido em config.py; pode demorar bastante e depende da rede.
- **E4:** testa salvaguardas, incluindo dados em falta, citações e números inventados, crítica repetida e ausência de modelo.
- **E5:** métricas do custo de coordenação derivadas dos resultados E1 e E2 e apresentadas pelos gráficos.
- **E6:** análises históricas com o modelo Ollama real; os registos existentes estão em experiments/results/real_llm/.

E1–E4 substituem o modelo de linguagem por modelos programados para responder de forma controlada. Isto permite repetir os cenários sem depender da velocidade, disponibilidade ou variabilidade do modelo real. E5 é calculada a partir dos dados existentes e não é um comando separado no script principal.

### Gerar gráficos

~~~powershell
python -m pip install -r experiments/requirements-experiments.txt
python experiments/make_figures.py
python experiments/make_architecture.py
~~~

Os gráficos são guardados em experiments/results/figures/ e experiments/results/figures_en/. Para gerar a figura de arquitetura em inglês:

~~~powershell
python experiments/make_architecture.py --lingua en
~~~

O script make_figures.py lê os CSVs existentes em experiments/results/. Para regenerar os gráficos, executa primeiro as experiências necessárias se os CSVs não existirem ou estiverem desatualizados.

## Resultados e ficheiros gerados

| Caminho | Conteúdo |
|---|---|
| saidas/<TICKER>.jsonl | Mensagens FIPA-ACL da última análise individual desse ticker. Uma nova análise com o mesmo nome substitui este registo. |
| saidas/gui_<TICKER>.jsonl | Mensagens da última análise desse ticker feita pela interface; também é substituído na próxima análise do mesmo ticker. |
| saidas/logs/sessao_AAAA-MM-DD.log | Registo da sessão com mensagens e tempos dos agentes. |
| saidas/logs/erro_arranque.log | Erro detalhado se Abrir.pyw não conseguir iniciar a interface. |
| saidas/historico/ | Análises guardadas pela interface em JSON. |
| saidas/exportacoes/ | Relatórios exportados pela interface em TXT e JSON. |
| saidas/teste_sinteticos.json | Resultados do lote sintético com Ollama real. |
| saidas/teste_real.json | Resultados do lote de empresas reais com Ollama. |
| dados/cache_llm/ | Respostas em cache do modelo, organizadas por agente, modelo e pedido. |
| dados/cache_sec/, dados/cache_mercado/ | Respostas em cache das fontes de dados. |
| experiments/results/*.csv | Resultados das experiências e dados usados para os gráficos. |

As pastas saidas/ e as caches locais são geradas durante a execução e estão excluídas do Git. Não coloques credenciais, ficheiros .env ou dados pessoais nesses diretórios se tencionas partilhar o conteúdo.

## Estrutura do repositório

~~~text
.
├── Abrir.bat                         Arranque simples no Windows
├── Abrir.pyw                         Prepara dependências e abre a interface
├── main.py                           Ponto de entrada: interface ou linha de comandos
├── config.py                         Parâmetros do protocolo e universo E3
├── requirements.txt                  Dependências da aplicação
├── .env.example                      Exemplo de configuração local
├── .gitignore                        Exclui configuração e dados gerados
├── agentes/
│   ├── coletor.py                    A1: recolha e normalização dos dados
│   ├── guardiao.py                   A2: filtros e regras de exclusão
│   ├── avaliador.py                  A3: coordenação da avaliação
│   ├── qualitativa.py                Perguntas qualitativas do A3 e validação
│   ├── critico.py                    A4: revisão crítica
│   └── decisor.py                    A5: veredito e relatório
├── nucleo/
│   ├── analisar.py                   Monta os agentes e inicia o fluxo
│   ├── plataforma.py                 Mensagens, fila, eventos e registos
│   ├── llm.py                        Cliente Ollama, cache e recuperação de falhas
│   ├── configuracao.py               Configuração local e controlo do Ollama
│   ├── testes.py                     Testes financeiros e 10 Portões
│   ├── valorizacao.py                Avaliação e condições de preço
│   ├── metricas.py                   Métricas e dados financeiros derivados
│   └── util.py                       Formatação, validações e carregamento do .env
├── fontes/
│   ├── sec.py                        SEC EDGAR e recolha de demonstrações
│   ├── xbrl.py                       Normalização das demonstrações XBRL
│   ├── mercado.py                    Preços, taxas, câmbios e dados de mercado
│   ├── reserva.py                    yfinance e Alpha Vantage
│   ├── fdic.py                       Indicadores regulatórios de bancos dos EUA
│   ├── qualitativas.py               Texto dos relatórios e contexto qualitativo
│   └── sintetico.py                  Leitura do dataset incluído
├── interface/
│   ├── app.py                        Janela principal e controlos
│   ├── fluxo.py                      Diagrama animado dos agentes
│   ├── pensamento.py                 Eventos e atividade dos agentes
│   ├── historico.py                  Histórico local
│   └── tema.py                       Cores e tipos de letra
├── dados/
│   └── empresas_sinteticas.json      19 empresas para demonstração e testes
├── tests/
│   ├── test_agentes.py               Testes das regras e lote sintético com Ollama
│   └── teste_real.py                 Variante do lote real com --continuar e --sem-cache
├── experiments/
│   ├── llm_scripted.py               Modelos simulados para experiências
│   ├── run_experiments.py             Experiências E1–E4
│   ├── teste_real.py                  Lote de empresas reais com Ollama
│   ├── analyse_real_llm_log.py        Métricas dos registos E6 do modelo real
│   ├── requirements-experiments.txt   Dependências adicionais para gráficos
│   ├── make_figures.py                Gráficos dos resultados
│   ├── make_architecture.py           Figura da arquitetura
│   └── results/                       CSVs, gráficos PT/EN e registos E6
├── docs/
│   └── LEIA-ME.md                     Explicação detalhada do protocolo
└── LICENSE                            Licença MIT
~~~

## Configuração

Na primeira utilização, o programa cria .env a partir de .env.example. O .env é local e está excluído do Git.

| Variável | Predefinição | Para que serve |
|---|---|---|
| LLM_MODELO | qwen2.5:7b | Modelo Ollama a utilizar. |
| OLLAMA_URL | http://localhost:11434 | Endereço HTTP do servidor Ollama. |
| SEC_USER_AGENT | preencher com nome e email de contacto | Identificação incluída nos pedidos à SEC. |
| ALPHAVANTAGE_API_KEY | vazio | Chave opcional para uma fonte complementar. |

O programa carrega estas variáveis para o processo quando inicia. Variáveis de ambiente do Windows/macOS/Linux já definidas podem prevalecer sobre os valores do .env. A janela Definições permite escolher o modelo, o endereço do Ollama e os dados opcionais sem editar o ficheiro manualmente.

Não publiques o .env nem chaves de API. Para a SEC não é necessária uma chave, mas é necessário um SEC_USER_AGENT com identificação de contacto.

## Limitações conhecidas

- O universo de empresas reais está limitado a empresas com dados disponíveis na SEC, incluindo alguns emitentes estrangeiros registados nos EUA. Um ticker de uma bolsa fora desse universo pode não ser encontrado.
- A cobertura de certas rubricas varia por empresa, taxonomia contabilística, moeda e período. O sistema rejeita empresas sem os dados essenciais que o protocolo exige.
- Alguns indicadores regulatórios de bancos e seguradoras não estão disponíveis nas fontes gratuitas usadas; nesses casos certos Portões podem não ser avaliáveis.
- As perguntas qualitativas do modelo podem estar erradas. As citações são verificadas contra o texto obtido, os números sem suporte são assinalados e o Crítico procura contradições, mas estas medidas não tornam o modelo infalível.
- As experiências com modelo simulado medem a lógica do fluxo e das regras, não a qualidade de um modelo real.
- As experiências E2, E3 e E6 foram feitas com versões anteriores do sistema, não foram repetidas com a versão final e não são apresentadas no relatório.
- O projeto não faz backtesting financeiro com dados históricos point-in-time e não demonstra que os vereditos produzam retornos positivos.

## Resolução de problemas

### A interface diz que o Ollama não está a correr

Confirma se o servidor responde no endereço configurado:

~~~powershell
Invoke-RestMethod http://localhost:11434/api/tags
ollama list
~~~

Se a API estiver noutro endereço, compara-o com Definições > Endereço do Ollama e com OLLAMA_URL no .env. O Ollama pode demorar alguns segundos a iniciar quando o Windows começa.

### A ligação fecha durante uma análise

Se a API responde, mas surge WinError 10054 durante a geração, o servidor foi alcançado mas a ligação fechou durante o pedido. Consulta o registo do servidor no Windows:

~~~powershell
Get-Content "$env:LOCALAPPDATA\Ollama\server.log" -Tail 100
ollama ps
~~~

Ollama ps mostra o modelo que está carregado e o processador usado. Se houver pressão de recursos, tenta qwen2.5:3b nas Definições ou fecha outras aplicações que estejam a usar o Ollama. Os lotes de teste do projeto pedem ao servidor para descarregar o modelo entre empresas, mas uma falha do processo ainda pode interromper uma análise.

### A análise real falha ao recolher dados

- Confirma a ligação à Internet.
- Confirma que SEC_USER_AGENT tem nome e email.
- A empresa pode não estar registada na SEC ou pode não ter o histórico necessário.
- Os serviços de mercado podem estar temporariamente indisponíveis; a análise pode ficar com campos em falta.

### O relatório indica dados em falta

O sistema mantém os valores em falta como desconhecidos. Consulta a secção de proveniência do relatório para ver a fonte de cada rubrica. Uma rejeição por falta de dados é comportamento intencional do protocolo, não substitui os valores por estimativas.

## Documentação adicional

- docs/LEIA-ME.md: relação entre os passos da v4.27 e os agentes, resumo da avaliação e limitações.
- LICENSE: licença MIT.
