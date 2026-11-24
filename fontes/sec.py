"""Fonte principal: SEC EDGAR companyfacts — relatórios anuais 10-K, 20-F e 40-F, em US-GAAP ou IFRS, em qualquer moeda.
Cobre as empresas americanas e as estrangeiras registadas na SEC (ADR). Valores derivados só a partir de outras linhas."""
import datetime, json, time, urllib.error, urllib.request
from config import RAIZ
from fontes.xbrl import CONC_IFRS, FORMAS_ANUAIS, construir_demonstracoes


_URL_TICK="https://www.sec.gov/files/company_tickers.json"
_URL_FACTS="https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json"
_CONC_SEC={
    "Revenue":(["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet","SalesRevenueGoodsNet","RevenuesNetOfInterestExpense"],"USD","fluxo"),
    "Net Income":(["NetIncomeLoss","NetIncomeLossAvailableToCommonStockholdersBasic","NetIncomeLossAvailableToCommonStockholdersDiluted","ProfitLoss"],"USD","fluxo"),
    "EPS Diluted":(["EarningsPerShareDiluted","EarningsPerShareBasicAndDiluted"],"USD/shares","fluxo"),
    "Operating Income":(["OperatingIncomeLoss"],"USD","fluxo"),
    "Pretax Income":(["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],"USD","fluxo"),
    "Interest Expense":(["InterestExpense","InterestExpenseNonoperating","InterestExpenseDebt"],"USD","fluxo"),
    "D&A":(["DepreciationDepletionAndAmortization","DepreciationAndAmortization","DepreciationAmortizationAndAccretionNet"],"USD","fluxo"),
    "Depreciation":(["Depreciation","DepreciationNonproduction"],"USD","fluxo"),
    "Amortization":(["AmortizationOfIntangibleAssets"],"USD","fluxo"),
    "Gross Profit":(["GrossProfit"],"USD","fluxo"),
    "Cost of Revenue":(["CostOfRevenue","CostOfGoodsAndServicesSold","CostOfGoodsSold"],"USD","fluxo"),
    "Operating Cash Flow":(["NetCashProvidedByUsedInOperatingActivities"],"USD","fluxo"),
    "Capital Expenditures":(["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireProductiveAssets",
                             "PaymentsForCapitalImprovements","PaymentsToAcquireOtherPropertyPlantAndEquipment"],"USD","fluxo"),
    "Total Debt":(["LongTermDebt","LongTermDebtNoncurrent","LongTermDebtAndCapitalLeaseObligations","DebtAndCapitalLeaseObligations",
                   "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities","SeniorNotes","UnsecuredLongTermDebt",
                   "LongTermNotesPayable"],"USD","stock"),
    "Cash & Equivalents":(["CashAndCashEquivalentsAtCarryingValue","CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],"USD","stock"),
    "Shareholders' Equity":(["StockholdersEquity","StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],"USD","stock"),
    "Total Assets":(["Assets"],"USD","stock"),
    "Goodwill":(["Goodwill"],"USD","stock"),
    "Diluted Shares Outstanding":(["WeightedAverageNumberOfDilutedSharesOutstanding","WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
                                   "WeightedAverageNumberOfSharesOutstandingBasic"],"shares","fluxo"),
    "Dividend Per Share":(["CommonStockDividendsPerShareDeclared","CommonStockDividendsPerShareCashPaid"],"USD/shares","fluxo"),
}
# Linhas do Método Buffett (o rótulo é o nome do campo interno)
_CONC_SEC.update({
    "sga":(["SellingGeneralAndAdministrativeExpense"],"USD","fluxo"),
    "Selling Marketing":(["SellingAndMarketingExpense"],"USD","fluxo"),
    "General Admin":(["GeneralAndAdministrativeExpense"],"USD","fluxo"),
    "rd":(["ResearchAndDevelopmentExpense","ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],"USD","fluxo"),
    "passivo_total":(["Liabilities"],"USD","stock"),
    "Equity incl NCI":(["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],"USD","stock"),
    "acoes_proprias":(["TreasuryStockValue","TreasuryStockCommonValue"],"USD","stock"),
    "resultados_transitados":(["RetainedEarningsAccumulatedDeficit"],"USD","stock"),
    "imposto":(["IncomeTaxExpenseBenefit"],"USD","fluxo"),
    "imposto_pago":(["IncomeTaxesPaidNet","IncomeTaxesPaid"],"USD","fluxo"),
    "inventario":(["InventoryNet"],"USD","stock"),
    "dividendos_pagos":(["PaymentsOfDividends","PaymentsOfDividendsCommonStock"],"USD","fluxo"),
    "recompras":(["PaymentsForRepurchaseOfCommonStock"],"USD","fluxo"),
    "sbc":(["ShareBasedCompensation","AllocatedShareBasedCompensationExpense"],"USD","fluxo"),
    "Operating Capital Change":(["IncreaseDecreaseInOperatingCapital"],"USD","fluxo"),
    "contas_receber":(["AccountsReceivableNetCurrent"],"USD","stock"),
    "divida_curto_prazo":(["ShortTermBorrowings","CommercialPaper","DebtCurrent"],"USD","stock"),
    "divida_lp_corrente":(["LongTermDebtCurrent"],"USD","stock"),
    "emissao_divida":(["ProceedsFromIssuanceOfLongTermDebt","ProceedsFromIssuanceOfDebt","ProceedsFromIssuanceOfSeniorLongTermDebt"],"USD","fluxo"),
    "emissao_acoes":(["ProceedsFromIssuanceOfCommonStock"],"USD","fluxo"),
    "imparidades_goodwill":(["GoodwillImpairmentLoss"],"USD","fluxo"),
    "aquisicoes":(["PaymentsToAcquireBusinessesNetOfCashAcquired","PaymentsToAcquireBusinessesGross",
                   "PaymentsToAcquireBusinessesAndInterestInAffiliates"],"USD","fluxo"),
    "preferenciais":(["PreferredStockValue"],"USD","stock"),
    "reembolso_divida":(["RepaymentsOfLongTermDebt","RepaymentsOfDebt","RepaymentsOfSeniorDebt"],"USD","fluxo"),
    "divida_lp":(["LongTermDebtNoncurrent","LongTermDebtAndCapitalLeaseObligations"],"USD","stock"),
    # bancos (testes AB1 e AB2 e Portões P3 e P8 da v4.27)
    "margem_financeira":(["InterestIncomeExpenseNet","InterestIncomeExpenseAfterProvisionForLoanLoss"],"USD","fluxo"),
    "receitas_nao_juros":(["NoninterestIncome"],"USD","fluxo"),
    "custos_nao_juros":(["NoninterestExpense"],"USD","fluxo"),
    "credito_total":(["FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss","LoansAndLeasesReceivableGrossCarryingAmount",
                      "LoansAndLeasesReceivableNetOfDeferredIncome","LoansAndLeasesReceivableNetReportedAmount"],"USD","stock"),
    "credito_malparado":(["FinancingReceivableExcludingAccruedInterestNonaccrual","FinancingReceivableRecordedInvestmentNonaccrualStatus",
                          "LoansAndLeasesReceivableImpairedNonperformingNonaccrualOfInterest"],"USD","stock"),
    "depositos":(["Deposits"],"USD","stock"),
    # intangíveis e liquidez corrente (balanço)
    "intangiveis":(["IntangibleAssetsNetExcludingGoodwill","FiniteLivedIntangibleAssetsNet",
                    "IndefiniteLivedIntangibleAssetsExcludingGoodwill"],"USD","stock"),
    "ativo_corrente":(["AssetsCurrent"],"USD","stock"),
    "passivo_corrente":(["LiabilitiesCurrent"],"USD","stock"),
    "Pretax Domestic":(["IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"],"USD","fluxo"),
    "Pretax Foreign":(["IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign"],"USD","fluxo"),
    "Asset Impairment":(["AssetImpairmentCharges","GoodwillAndIntangibleAssetImpairment","GoodwillImpairmentLoss",
                         "ImpairmentOfIntangibleAssetsExcludingGoodwill","ImpairmentOfLongLivedAssetsHeldForUse"],"USD","fluxo"),
    "rl_continuadas":(["IncomeLossFromContinuingOperations","IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest"],"USD","fluxo"),
})
_CONC_MAXIMO={"Revenue"}   # vários conceitos de receita: o total é o maior (os outros podem ser parcelas)
_CONC_AUXILIARES={"Operating Income","Pretax Income","Interest Expense","D&A","Depreciation","Amortization","Cost of Revenue","EPS Diluted",
                  "Selling Marketing","General Admin","Equity incl NCI","Operating Capital Change"}
_CACHE_SEC=RAIZ/"dados"/"cache_sec"; _ult_ped=0.0

def _sec_pedido(url, ua):
    """Um pedido à SEC com o cabeçalho obrigatório e o intervalo mínimo entre pedidos (sem cache)."""
    global _ult_ped
    if not ua or "@" not in ua: raise ValueError("Definir SEC_USER_AGENT com nome e email.")
    espera=0.15-(time.monotonic()-_ult_ped)
    if espera>0: time.sleep(espera)
    req=urllib.request.Request(url,headers={"User-Agent":ua})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: dados=json.loads(r.read().decode())
    except urllib.error.HTTPError as e: raise ValueError(f"SEC {e.code}: {url}") from e
    except urllib.error.URLError as e: raise ValueError(f"Sem ligação à SEC: {e.reason}") from e
    finally: _ult_ped=time.monotonic()
    return dados

def _sec_get(url, ua, nome, validade_dias=7):
    _CACHE_SEC.mkdir(parents=True,exist_ok=True)
    fc=_CACHE_SEC/nome
    if fc.exists() and time.time()-fc.stat().st_mtime<validade_dias*86400:
        return json.loads(fc.read_text(encoding="utf-8"))
    dados=_sec_pedido(url,ua); fc.write_text(json.dumps(dados),encoding="utf-8"); return dados

def _af(fim): d=datetime.date.fromisoformat(fim); return d.year-1 if d.month==1 or (d.month==2 and d.day<=7) else d.year

def _sec_serie(facts, conc, unidade, tipo, fins, tax="us-gaap"):
    """Extrai uma série anual de um conceito XBRL (p. ex. 'Revenues'), ligando cada valor ao ano fiscal pela data de fim."""
    datas={datetime.date.fromisoformat(v):a for a,v in fins.items()}; r={}
    for c in conc:
        esc={}
        for f in facts["facts"].get(tax,{}).get(c,{}).get("units",{}).get(unidade,[]):
            if f.get("form") not in FORMAS_ANUAIS: continue
            fim=datetime.date.fromisoformat(f["end"])
            if tipo=="fluxo":
                if "start" not in f or not 350<=(fim-datetime.date.fromisoformat(f["start"])).days<=380: continue
                ano=_af(f["end"])
            else:
                ano=next((a for d2,a in datas.items() if abs((d2-fim).days)<=7),None)
                if "start" in f or ano is None: continue
            if ano not in esc or f.get("filed","")>esc[ano][0]: esc[ano]=(f.get("filed",""),float(f["val"]))
        for ano,(_,v) in esc.items(): r.setdefault(ano,v)
    return r

def _sec_serie_max(facts, conc, unidade, tipo, fins, tax="us-gaap"):
    r={}
    for c in conc:
        for ano,v in _sec_serie(facts,[c],unidade,tipo,fins,tax).items():
            if ano not in r or v>r[ano]: r[ano]=v
    return r

def _taxonomia_e_moeda(facts):
    """Escolhe a taxonomia (us-gaap ou ifrs-full) e a moeda do relatório: a que tem mais anos recentes de receita e lucro."""
    melhor=None
    for tax,conc in (("us-gaap",_CONC_SEC),("ifrs-full",CONC_IFRS)):
        g=facts["facts"].get(tax,{})
        for c in conc["Revenue"][0]+conc["Net Income"][0]:
            for u,lst in (g.get(c,{}).get("units") or {}).items():
                if "/" in u or len(u)!=3: continue
                fins=[f["end"] for f in lst if f.get("form") in FORMAS_ANUAIS and "start" in f
                      and 350<=(datetime.date.fromisoformat(f["end"])-datetime.date.fromisoformat(f["start"])).days<=380]
                if not fins: continue
                chave=(max(fins)[:4],len(set(fins)))       # mais recente primeiro; depois mais anos
                if melhor is None or chave>melhor[0]: melhor=(chave,tax,u)
    return (melhor[1],melhor[2]) if melhor else ("us-gaap","USD")

_CIK_HISTORICO={"XOM":34088}

def _sec_anos_10k(facts, tax="us-gaap", moeda="USD"):
    """Descobre os anos fiscais com 10-K (ou 20-F/40-F) e as datas de fim de exercício."""
    conc=_CONC_SEC if tax=="us-gaap" else CONC_IFRS; fins={}
    for c in conc["Revenue"][0]+conc["Net Income"][0]:
        for f in facts["facts"].get(tax,{}).get(c,{}).get("units",{}).get(moeda,[]):
            if f.get("form") in FORMAS_ANUAIS and "start" in f and 350<=(datetime.date.fromisoformat(f["end"])-datetime.date.fromisoformat(f["start"])).days<=380:
                fins.setdefault(_af(f["end"]),f["end"])
    return fins

def _normalizar_nome(n: str) -> str:
    import re, unicodedata
    n=unicodedata.normalize("NFKD",n or "").encode("ascii","ignore").decode().upper()
    n=re.sub(r"[^A-Z0-9 ]+"," ",n)
    n=re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|SA|S A|AG|NV|N V|SE|AB|ASA|A S|AS|SPA|S P A|HOLDINGS?|GROUP|THE)\b"," ",n)
    return re.sub(r"\s+"," ",n).strip()

def _sec_cik_por_nome(nome: str, ua: str):
    """Para um ticker de uma bolsa estrangeira (ex.: NOVO-B.CO), procura a mesma empresa na SEC pelo nome."""
    alvo=_normalizar_nome(nome)
    if not alvo: return None
    tick=_sec_get(_URL_TICK,ua,"company_tickers.json")
    for l in tick.values():
        if _normalizar_nome(l["title"])==alvo: return int(l["cik_str"]),l["ticker"],l["title"]
    return None

def _sec_obter(ticker, ua, n_anos=10, preco=None, taxa=None, cik=None):
    """Ponto de entrada da fonte SEC: ticker -> CIK -> factos XBRL -> demonstrações normalizadas dos últimos anos."""
    tick=_sec_get(_URL_TICK,ua,"company_tickers.json")
    if cik is None:
        lin=next((l for l in tick.values() if l["ticker"].upper()==ticker.upper()),None)
        if not lin: raise ValueError(f"'{ticker}' não existe na lista da SEC.")
        cik=int(lin["cik_str"]); titulo=lin["title"]
    else:
        titulo=next((l["title"] for l in tick.values() if int(l["cik_str"])==cik),ticker)
    facts=_sec_get(_URL_FACTS.format(cik),ua,f"factos_{cik}.json")
    tax,moeda=_taxonomia_e_moeda(facts)
    fins=_sec_anos_10k(facts,tax,moeda)
    if not fins and ticker.upper() in _CIK_HISTORICO:
        cik=_CIK_HISTORICO[ticker.upper()]; facts=_sec_get(_URL_FACTS.format(cik),ua,f"factos_{cik}.json")
        tax,moeda=_taxonomia_e_moeda(facts); fins=_sec_anos_10k(facts,tax,moeda)
    sic,sic_desc=None,""; governanca={"auditor":[],"reexpressao":[]}
    try:
        subs=_sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",ua,f"subs_{cik}.json")
        sic=int(subs.get("sic")) if str(subs.get("sic") or "").isdigit() else None; sic_desc=subs.get("sicDescription") or ""
        rec=(subs.get("filings") or {}).get("recent") or {}
        limite=(datetime.date.today()-datetime.timedelta(days=3653)).isoformat()
        for forma,data,itens in zip(rec.get("form",[]),rec.get("filingDate",[]),rec.get("items",[])):
            if forma=="8-K" and data>=limite:            # 8-K item 4.01: mudança de auditor; 4.02: reexpressão de contas
                if "4.01" in (itens or ""): governanca["auditor"].append(data)
                if "4.02" in (itens or ""): governanca["reexpressao"].append(data)
    except Exception: pass
    anos=sorted(fins)[-n_anos:]
    if not anos: raise ValueError(f"{titulo} não tem relatórios anuais (10-K, 20-F, 40-F) com dados XBRL na SEC.")
    fins={a:fins[a] for a in anos}
    conc=_CONC_SEC if tax=="us-gaap" else CONC_IFRS
    series={}
    for rot,(c,u,t) in conc.items():
        u=u.replace("USD",moeda).replace("MOEDA",moeda)
        series[rot]=(_sec_serie_max if rot in _CONC_MAXIMO or rot=="Asset Impairment" else _sec_serie)(facts,c,u,t,fins,tax)
    fin,origem=construir_demonstracoes(series,anos)
    origem={k:("SEC ("+v+")") for k,v in origem.items()}
    return {"ticker":ticker.upper(),"name":titulo,"sector":"N/A","currency":moeda,"moeda_relatorio":moeda,
            "price":preco if preco is not None else "N/A","beta":"N/A","moat":"N/A",
            "historical_pe":"N/A","us10y":taxa if taxa is not None else "N/A",
            "financials":fin,"source":f"SEC EDGAR companyfacts ({'IFRS' if tax=='ifrs-full' else 'US-GAAP'}, {moeda}), CIK {cik}",
            "cik":cik,"sic":sic,"sic_desc":sic_desc,"governanca":governanca,
            "fim_exercicio":{str(a):fins[a] for a in anos},
            "_origem_sec":{f"{k[0]}/{k[1]}":v for k,v in origem.items()}}
