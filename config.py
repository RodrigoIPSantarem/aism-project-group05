"""Parâmetros do Protocolo de Investimentos v4.27 — Método Buffett Integral (Triagem, Setor, testes, Portões, preço) e lista da experiência E3."""
from pathlib import Path


RAIZ = Path(__file__).resolve().parent

ANOS_ANALISE    = 10   # v4.27 (Secção 6.1): usar 10 anos sempre que disponíveis
ANOS_MINIMOS    = 5    # v4.27: com menos de 5 anos de demonstrações, rejeitar
CAMPOS_ESSENCIAIS = ["receita", "resultado_liquido", "fco"]
MAX_FALTA_ESSENCIAIS = 0.2

# ═══ Passo -2 — Triagem Rápida (Secção 6.0): 7 perguntas de sim ou não; um "não" e a empresa sai
TRIAGEM = {
    "T1": "Percebo o produto e porque é que o cliente o compra?",
    "T2": "O LPA não teve prejuízos e está mais alto do que há 5–10 anos?",
    "T3": "O ROE médio é de pelo menos 15%?",
    "T4": "A dívida de longo prazo paga-se com 4 anos de lucro ou menos?",
    "T5": "A margem bruta é de pelo menos 20%, ou é um negócio claro de baixo custo?",
    "T6": "O número de ações não subiu mais de 10% em 3 anos?",
    "T7": "O fluxo de caixa operacional foi positivo em todos os anos?",
}
TRIAGEM_ROE_MIN = 15.0; TRIAGEM_DIVIDA_ANOS = 4.0; TRIAGEM_MARGEM_BRUTA = 20.0; TRIAGEM_DILUICAO = 10.0

# ═══ Passo 0 — Setor (Secção 6.0). Cíclicas, MLPs e REITs ficam fora do método; bancos e seguradoras ficam dentro,
# com respostas próprias para três Portões (CET1, NPL, solvência: dados que as fontes gratuitas não dão).
SIC_BANCOS       = [(6020,6036),(6111,6163),(6172,6172),(6199,6199)]
SIC_SEGURADORAS  = [(6311,6399),(6411,6411)]
SIC_REIT         = [(6798,6798)]
# SIC 2830-2836 (farmacêuticas) e 2840-2844 (higiene e cosmética: P&G, Colgate) NÃO são químicos de base.
# Quando o Yahoo dá setor e indústria, é essa a classificação usada (o SIC é só reserva).
SIC_FORA_METODO  = [(1000,1499),(2400,2499),(2600,2699),(2800,2829),(2850,2899),(2900,2999),(3200,3399),(3674,3674),
                    (3711,3716),(4011,4013),(4210,4231),(4400,4499),(4512,4581),(4610,4619)]
YF_FORA_METODO_SETORES = {"Energy","Basic Materials"}
YF_FORA_METODO_INDUSTRIAS = ("Semiconductor","Airlines","Trucking","Marine Shipping","Railroads","Integrated Freight",
                             "Auto Manufacturers","Chemicals","Steel","Aluminum","Copper","Gold","Silver","Oil & Gas",
                             "Coal","Paper","Lumber","Building Materials","Agricultural Inputs","REIT","Real Estate")
PT_FORA_METODO = ("energia","mineração","mineracao","materiais","química","quimica","transportes","semicondutor","siderurgia","imobili")
KE_MINIMO = 10.0                 # Ke de bancos e seguradoras = máximo (r ; 10%), sem beta

# ═══ Passo 1 — Regra de Commodity (Secção 6.1)
COMMODITY_MARGEM_BRUTA = 20.0; COMMODITY_ROE = 15.0; COMMODITY_ANOS_LPA_MAU = 3

# ═══ Passos 2 e 3 — Testes Buffett: Sim, Parcial ou Não (Secção 6.2). (direção, limiar do Sim, limiar do Parcial)
TESTES_POR_ANO = {
    "A1": ("Margem bruta (lucro bruto / receita, %)",           "maior", 40.0, 20.0),
    "A2": ("SG&A / lucro bruto (%)",                            "menor", 30.0, 80.0),
    "A3": ("I&D / lucro bruto (%)",                             "menor", 10.0, 20.0),
    "A4": ("Depreciação / lucro bruto (%)",                     "menor", 10.0, 20.0),
    "A5": ("Juros / resultado operacional (%)",                 "menor", 15.0, 30.0),
    "A6": ("Margem líquida (%)",                                "maior", 20.0, 10.0),
    "A8": ("Dívida LP / lucro líquido (x)",                     "menor", 3.0, 4.0),
    "A9": ("Passivo / (capitais próprios + ações próprias) (x)","menor", 0.80, 1.50),
    "A10":("ROE (%)",                                           "maior", 20.0, 15.0),
    "A12":("Capex / lucro líquido (%)",                         "menor", 25.0, 50.0),
}
CONSISTENCIA_MIN = 0.70        # Regra de Consistência proporcional: Sim exige o limiar em 70% dos anos (7 de 10; 4 de 5)
TAXA_LEGAL_IMPOSTO = {"USD": lambda ano: 35.0 if ano<=2017 else 21.0, "DKK": lambda ano: 22.0, "EUR": lambda ano: 21.0}
SIM, PARCIAL, NAO_ = "Sim", "Parcial", "Não"
FRANQUIA_PERGUNTAS = {
    "f1": "O produto ou serviço é necessário ou desejado?",
    "f2": "O cliente considera que não tem substituto próximo?",
    "f3": "O preço não é regulado?",
    "f4": "Se um concorrente tivesse capital ilimitado, continuaria sem conseguir tirar-lhe os clientes?",
}
# ═══ Passo 4 — os 10 Portões de Buffett (Secção 6.3): passam com Sim ou Parcial; falhar um é rejeição
PORTOES = {
    "P1":  ("Tem uma franquia ou vantagem identificável?", ("C1","C4")),
    "P2":  ("Os lucros são fortes e com tendência de alta?", ("A7",)),
    "P3":  ("É financiada de forma conservadora?", ("A8",)),
    "P4":  ("Obtém consistentemente um ROE alto?", ("A10",)),
    "P5":  ("Consegue reter os lucros?", ("A11",)),
    "P6":  ("Gasta pouco para manter as operações?", ("A12",)),
    "P7":  ("Reinveste bem os lucros retidos?", ("B2",)),
    "P8":  ("Consegue subir preços com a inflação?", ("C3",)),
    "P9":  ("Os lucros retidos aumentam o valor?", ("B1",)),
    "P10": ("A gestão é íntegra e pensa como dona?", ("B4",)),
}

# ═══ Passo 5 — Avaliação (Secção 8)
ANOS_PROJECAO     = 10
TAXA_DESCONTO_MIN = 7.0         # r = taxa do Estado a 10 anos, sem prémio de risco, piso de 7%
G_TERMINAL_MAX    = 2.5         # g terminal = mínimo (2,5% ; g/2)
G_TETO            = 15.0
PE_ALVO_MAX       = 25.0        # P/L-alvo = mínimo (média de 10 anos ; 25x)
PE_NEUTRO         = 15.0        # só se não houver P/L histórico (assinalado no relatório)
TACE_MINIMA       = 15.0        # TACE >= 15% (BUF cap. 25)
TACE_ALTA_CONVICCAO = 20.0      # Secção 9.1: 15% do portefólio com Franquia e TACE >= 20%
PL_MAXIMO         = 40.0        # Secções 7 e 9
DIVERGENCIA_MAX   = 20.0        # validação cruzada VI vs Valor Equity Bond
TAXA_RENTABILIDADE_ALVO = 0.20  # alvo próprio do utilizador (só informativo: a decisão usa 15%)
MAX_REVISOES      = 1
# Quanto texto a parte qualitativa do Avaliador lê (caracteres por fonte) e o contexto pedido ao modelo. Valores maiores leem mais do relatório anual
# mas tornam cada chamada mais lenta; com o Ollama, num_ctx 8192 cabe em 8 GB de memória gráfica com o qwen2.5:7b.
AN_CHARS_PERFIL = 2200; AN_CHARS_ITEM1 = 3000; AN_CHARS_PRECOS = 2800
LLM_NUM_CTX = 8192; LLM_NUM_PREDICT = 1400

# ═══ Passo 8 — Veredicto
COMPRAR_V = "COMPRAR"; CAIXA_V = "CAIXA DEDICADA"; REJEITAR_V = "REJEITAR"
COMPRAR="COMPRAR"; NAO="NAO_COMPRAR"; COND="CAIXA_DEDICADA"
NOMES = {COMPRAR:"COMPRAR", COND:"CAIXA DEDICADA", NAO:"NÃO COMPRAR"}

# Lista fixa de 110 empresas da SEC (EUA e ADR) usada na experiência E3 (experiments/run_experiments.py).
TICKERS_E3 = {
    "Consumo básico":    ["PG","KO","PEP","CL","KMB","GIS","HSY","MKC","SJM","CHD"],
    "Saúde":             ["JNJ","ABT","MDT","TMO","DHR","SYK","BSX","ZBH","ISRG","EW"],
    "Tecnologia":        ["MSFT","AAPL","GOOGL","META","ADBE","CRM","NOW","INTU","CDNS","SNPS"],
    "Pagamentos":        ["V","MA","AXP","PYPL","FI","FIS","GPN","WEX","JKHY","FOUR"],
    "Industrial":        ["HON","MMM","GE","CAT","DE","EMR","ITW","PH","ROK","AME"],
    "Consumo discric.":  ["NKE","MCD","SBUX","YUM","CMG","DPZ","POOL","ROST","TJX","ULTA"],
    "Financeiro":        ["BRK-B","JPM","BAC","WFC","C","GS","MS","BLK","SCHW","ICE"],
    "Utilities":         ["NEE","SO","DUK","AEP","XEL","WEC","ES","ETR","FE","PPL"],
    "Imobiliário":       ["AMT","PLD","CCI","EQIX","PSA","O","VICI","SPG","AVB","EQR"],
    "Energia":           ["XOM","CVX","COP","EOG","SLB","MPC","VLO","PSX","OXY","HAL"],
    "ADR (20-F na SEC)": ["NVO","ASML","TSM","SAP","UL","NVS","TM","BABA","DEO","SONY"],
}