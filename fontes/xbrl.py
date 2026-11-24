"""Partes comuns às fontes XBRL (SEC EDGAR, em US-GAAP ou IFRS):
conceitos IFRS de cada linha e a construção das demonstrações anuais com os valores derivados.
Nenhum valor é estimado: só se deriva uma linha a partir de outras linhas do mesmo relatório."""
import datetime

FORMAS_ANUAIS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

def ano_fiscal(fim: str) -> int:
    """Ano fiscal a que pertence uma data de fecho (fechos no início de janeiro ou de fevereiro contam para o ano anterior)."""
    d = datetime.date.fromisoformat(fim[:10])
    return d.year - 1 if d.month == 1 or (d.month == 2 and d.day <= 7) else d.year

# Conceitos IFRS (taxonomia ifrs-full), com os MESMOS rótulos usados para a US-GAAP. "MOEDA" é substituída pela moeda do relatório.
CONC_IFRS = {
    "Revenue": (["Revenue", "RevenueFromContractsWithCustomers"], "MOEDA", "fluxo"),
    "Net Income": (["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"], "MOEDA", "fluxo"),
    "EPS Diluted": (["DilutedEarningsLossPerShare", "DilutedEarningsLossPerShareFromContinuingOperations", "BasicAndDilutedEarningsLossPerShare",
                     "BasicEarningsLossPerShare"], "MOEDA/shares", "fluxo"),
    "Operating Income": (["ProfitLossFromOperatingActivities"], "MOEDA", "fluxo"),
    "Pretax Income": (["ProfitLossBeforeTax"], "MOEDA", "fluxo"),
    "Interest Expense": (["InterestExpense", "FinanceCosts", "InterestExpenseOnBorrowings"], "MOEDA", "fluxo"),
    "D&A": (["DepreciationAndAmortisationExpense", "AdjustmentsForDepreciationAndAmortisationExpense",
             "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss",
             "AdjustmentsForDepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss",
             "AdjustmentsForDepreciationAndAmortisationExpenseAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"], "MOEDA", "fluxo"),
    "Depreciation": (["DepreciationExpense", "DepreciationPropertyPlantAndEquipment"], "MOEDA", "fluxo"),
    "Amortization": (["AmortisationExpense", "AmortisationIntangibleAssetsOtherThanGoodwill"], "MOEDA", "fluxo"),
    "Gross Profit": (["GrossProfit"], "MOEDA", "fluxo"),
    "Cost of Revenue": (["CostOfSales", "CostOfMerchandiseSold"], "MOEDA", "fluxo"),
    "Operating Cash Flow": (["CashFlowsFromUsedInOperatingActivities"], "MOEDA", "fluxo"),
    "Capital Expenditures": (["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PurchaseOfPropertyPlantAndEquipment",
                              "PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets",
                              "PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssets"], "MOEDA", "fluxo"),
    "Total Debt": (["Borrowings", "LongtermBorrowings", "NoncurrentPortionOfNoncurrentBorrowings"], "MOEDA", "stock"),
    "Cash & Equivalents": (["CashAndCashEquivalents"], "MOEDA", "stock"),
    "Shareholders' Equity": (["EquityAttributableToOwnersOfParent", "Equity"], "MOEDA", "stock"),
    "Total Assets": (["Assets"], "MOEDA", "stock"),
    "Goodwill": (["Goodwill"], "MOEDA", "stock"),
    "Diluted Shares Outstanding": (["AdjustedWeightedAverageShares", "WeightedAverageShares"], "shares", "fluxo"),
    "Dividend Per Share": (["DividendsRecognisedAsDistributionsToOwnersPerShare", "DividendsPaidOrdinarySharesPerShare"], "MOEDA/shares", "fluxo"),
    "sga": (["SellingGeneralAndAdministrativeExpense"], "MOEDA", "fluxo"),
    "Selling Marketing": (["SellingExpense", "DistributionCosts"], "MOEDA", "fluxo"),
    "General Admin": (["AdministrativeExpense", "GeneralAndAdministrativeExpense"], "MOEDA", "fluxo"),
    "rd": (["ResearchAndDevelopmentExpense"], "MOEDA", "fluxo"),
    "passivo_total": (["Liabilities"], "MOEDA", "stock"),
    "Equity incl NCI": (["Equity"], "MOEDA", "stock"),
    "acoes_proprias": (["TreasuryShares"], "MOEDA", "stock"),
    "resultados_transitados": (["RetainedEarnings"], "MOEDA", "stock"),
    "imposto": (["IncomeTaxExpenseContinuingOperations"], "MOEDA", "fluxo"),
    "imposto_pago": (["IncomeTaxesPaidRefundClassifiedAsOperatingActivities", "IncomeTaxesPaidRefund"], "MOEDA", "fluxo"),
    "inventario": (["Inventories", "CurrentInventoriesHeldForSale"], "MOEDA", "stock"),
    "dividendos_pagos": (["DividendsPaidClassifiedAsFinancingActivities", "DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities",
                          "DividendsPaid"], "MOEDA", "fluxo"),
    "recompras": (["PaymentsToAcquireOrRedeemEntitysShares", "PurchaseOfTreasuryShares"], "MOEDA", "fluxo"),
    "sbc": (["AdjustmentsForSharebasedPayments", "ExpenseFromSharebasedPaymentTransactionsWithEmployees",
             "ExpenseFromSharebasedPaymentTransactions"], "MOEDA", "fluxo"),
    "Operating Capital Change": (["IncreaseDecreaseInWorkingCapital"], "MOEDA", "fluxo"),
    "contas_receber": (["TradeAndOtherCurrentReceivables", "CurrentTradeReceivables"], "MOEDA", "stock"),
    "divida_curto_prazo": (["ShorttermBorrowings", "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"], "MOEDA", "stock"),
    "divida_lp_corrente": (["CurrentPortionOfLongtermBorrowings", "CurrentPortionOfNoncurrentBorrowings"], "MOEDA", "stock"),
    "divida_lp": (["LongtermBorrowings", "NoncurrentPortionOfNoncurrentBorrowings"], "MOEDA", "stock"),
    "emissao_divida": (["ProceedsFromBorrowingsClassifiedAsFinancingActivities", "ProceedsFromNoncurrentBorrowings"], "MOEDA", "fluxo"),
    "reembolso_divida": (["RepaymentsOfBorrowingsClassifiedAsFinancingActivities", "RepaymentsOfNoncurrentBorrowings"], "MOEDA", "fluxo"),
    "emissao_acoes": (["ProceedsFromIssuingShares"], "MOEDA", "fluxo"),
    "imparidades_goodwill": (["ImpairmentLossRecognisedInProfitOrLossGoodwill"], "MOEDA", "fluxo"),
    "aquisicoes": (["CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities"], "MOEDA", "fluxo"),
    "preferenciais": ([], "MOEDA", "stock"),
    "intangiveis": (["IntangibleAssetsOtherThanGoodwill"], "MOEDA", "stock"),
    "ativo_corrente": (["CurrentAssets"], "MOEDA", "stock"),
    "passivo_corrente": (["CurrentLiabilities"], "MOEDA", "stock"),
    "Asset Impairment": (["ImpairmentLossRecognisedInProfitOrLoss", "ImpairmentLossRecognisedInProfitOrLossGoodwill"], "MOEDA", "fluxo"),
    "rl_continuadas": (["ProfitLossFromContinuingOperationsAttributableToOwnersOfParent", "ProfitLossFromContinuingOperations"], "MOEDA", "fluxo"),
}
# Linhas que só servem para derivar outras (não entram nas demonstrações)
AUXILIARES = {"Operating Income", "Pretax Income", "Interest Expense", "D&A", "Depreciation", "Amortization", "Cost of Revenue", "Asset Impairment",
              "Pretax Domestic", "Pretax Foreign",
              "EPS Diluted", "Selling Marketing", "General Admin", "Equity incl NCI", "Operating Capital Change"}
# Pagamentos que algumas empresas reportam com sinal negativo: guardados sempre como valor positivo
POSITIVOS = {"Capital Expenditures", "dividendos_pagos", "recompras", "aquisicoes", "imposto_pago", "reembolso_divida",
             "Interest Expense", "acoes_proprias", "imposto"}

def construir_demonstracoes(series: dict, anos: list) -> tuple[dict, dict]:
    """series: {rótulo: {ano: valor}}. Devolve ({ano: {rótulo: valor}}, origem) com as linhas derivadas assinaladas."""
    fin, origem = {}, {}
    for a in anos:
        if (series.get("Pretax Income") or {}).get(a) is None and (series.get("Pretax Domestic") or {}).get(a) is not None \
                and (series.get("Pretax Foreign") or {}).get(a) is not None:
            series.setdefault("Pretax Income", {})[a] = series["Pretax Domestic"][a] + series["Pretax Foreign"][a]
            origem[("resultado_antes_impostos", a)] = "derivado: resultado antes de impostos doméstico + estrangeiro"
        g = lambda k: (series.get(k) or {}).get(a)
        ln = {}
        for rot, ser in series.items():
            if rot in AUXILIARES: continue
            v = ser.get(a)
            if v is not None and rot in POSITIVOS and rot != "imposto": v = abs(v)
            ln[rot] = "N/A" if v is None else (-v if rot == "Capital Expenditures" else v)
        da = g("D&A")
        if da is None and g("Depreciation") is not None:
            da = g("Depreciation") + (g("Amortization") or 0); origem[("EBITDA", a)] = "derivado: D&A = depreciação + amortização"
        if da is not None: da = abs(da)
        juros = abs(g("Interest Expense")) if g("Interest Expense") is not None else None
        if g("Operating Income") is not None and da is not None:
            ln["EBITDA"] = g("Operating Income") + da
        elif g("Pretax Income") is not None and da is not None:
            ln["EBITDA"] = g("Pretax Income") + (juros or 0) + da
            origem[("EBITDA", a)] = "derivado: resultado antes de impostos + juros + D&A"
        else: ln["EBITDA"] = "N/A"
        ln["D&A"] = "N/A" if da is None else da
        ln["Interest Expense"] = "N/A" if juros is None else juros
        ln["ebit"] = "N/A" if g("Operating Income") is None else g("Operating Income")
        ln["resultado_antes_impostos"] = "N/A" if g("Pretax Income") is None else g("Pretax Income")
        # v4.27 (mapa de dados): sem "EBT Excluding Unusual Items", usar Pretax Income + Asset Impairment Charge
        imp = g("Asset Impairment")
        if g("Pretax Income") is not None and imp and abs(imp) > 0:
            ln["ebt_sem_extra"] = g("Pretax Income") + abs(imp)
            origem[("ebt_sem_extra", a)] = "derivado: resultado antes de impostos + imparidades (Pretax Income + Asset Impairment Charge, v4.27)"
        ln["lpa_diluido"] = "N/A" if g("EPS Diluted") is None else g("EPS Diluted")
        if ln.get("sga", "N/A") == "N/A" and (g("Selling Marketing") is not None or g("General Admin") is not None):
            ln["sga"] = abs(g("Selling Marketing") or 0) + abs(g("General Admin") or 0)
            origem[("sga", a)] = "derivado: vendas e marketing + gerais e administrativos"
        if ln.get("rd") not in (None, "N/A"): ln["rd"] = abs(ln["rd"])
        if ln.get("sga") not in (None, "N/A"): ln["sga"] = abs(ln["sga"])
        if ln.get("passivo_total", "N/A") == "N/A" and g("Total Assets") is not None:
            cp = g("Equity incl NCI") if g("Equity incl NCI") is not None else g("Shareholders' Equity")
            if cp is not None: ln["passivo_total"] = g("Total Assets") - cp; origem[("passivo_total", a)] = "derivado: ativo total - capitais próprios"
        ln["var_fundo_maneio"] = "N/A" if g("Operating Capital Change") is None else -g("Operating Capital Change")
        if ln.get("Diluted Shares Outstanding", "N/A") == "N/A" and g("Net Income") and g("EPS Diluted"):
            ln["Diluted Shares Outstanding"] = round(g("Net Income") / g("EPS Diluted"))
            origem[("Diluted Shares Outstanding", a)] = "derivado: resultado líquido / LPA diluído"
        # Coerência dos valores por ação: alguns relatórios etiquetam o LPA ou o dividendo com a escala errada (x1000, x1 000 000)
        rl_, ac_ = g("Net Income"), ln.get("Diluted Shares Outstanding")
        lpa_calc = rl_ / ac_ if isinstance(ac_, (int, float)) and ac_ and rl_ is not None else None
        lpa_r = ln.get("lpa_diluido")
        if lpa_calc and isinstance(lpa_r, (int, float)) and lpa_r and not 0.2 < lpa_r / lpa_calc < 5:
            esc = next((e for e in (1e3, 1e6) if 0.9 < lpa_calc / lpa_r / e < 1.1), None)
            if esc:      # o LPA está certo e as ações vêm em milhares ou milhões (ex.: Badger Meter até 2022): corrigir as ações
                ln["Diluted Shares Outstanding"] = ac_ * esc
                origem[("Diluted Shares Outstanding", a)] = (f"ações do relatório em {'milhares' if esc == 1e3 else 'milhões'} "
                                                             f"(lucro / LPA confirma): multiplicadas por {esc:,.0f}".replace(",", " "))
                lpa_calc = lpa_calc / esc
            else:
                origem[("lpa_diluido", a)] = f"LPA do relatório ({lpa_r:g}) incoerente com lucro / ações ({lpa_calc:.3g}): ignorado"
                ln["lpa_diluido"] = "N/A"
        dpa_ = ln.get("Dividend Per Share")
        ref = max(abs(lpa_calc or 0), abs(ln["lpa_diluido"]) if isinstance(ln.get("lpa_diluido"), (int, float)) else 0)
        if isinstance(dpa_, (int, float)) and ref and dpa_ > 5 * ref:
            origem[("Dividend Per Share", a)] = f"dividendo por ação do relatório ({dpa_:g}) incoerente com o LPA ({ref:.3g}): ignorado"
            ln["Dividend Per Share"] = "N/A"
        if ln.get("Gross Profit", "N/A") == "N/A" and g("Cost of Revenue") is not None and g("Revenue") is not None:
            ln["Gross Profit"] = g("Revenue") - abs(g("Cost of Revenue")); origem[("Gross Profit", a)] = "derivado: receita - custo das vendas"
        fin[str(a)] = ln
    return fin, origem
