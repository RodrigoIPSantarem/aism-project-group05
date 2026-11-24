"""Fontes de reserva: yfinance e Alpha Vantage; preenchem só células vazias e registam a origem.
Também ajusta o n.º de ações aos desdobramentos (splits)."""
import datetime
import json, os, statistics, time
from fontes.mercado import _CACHE_MERC, _get_web, _mensais, _yahoo_chart
from fontes.sec import _af
from nucleo.metricas import _anos, _val
from nucleo.util import CAMPOS_OPCIONAIS, _ler, _num


# Ordem: 1) SEC EDGAR  2) yfinance (gratuito, sem chave)  3) Alpha Vantage (gratuito com chave, 25 pedidos/dia,
# repõe diariamente; só é usado se ALPHAVANTAGE_API_KEY estiver no .env e ainda faltarem dados).
# Só se preenchem células vazias; cada valor preenchido fica registado com a fonte. Nada é estimado pelo modelo.
_YF_MAPA={
    "receita":("income",["Total Revenue","Operating Revenue"]),
    "resultado_liquido":("income",["Net Income","Net Income Common Stockholders"]),
    "ebitda":("income",["EBITDA","Normalized EBITDA"]),
    "lucro_bruto":("income",["Gross Profit"]),
    "acoes_diluidas":("income",["Diluted Average Shares"]),
    "fco":("cash",["Operating Cash Flow"]),
    "capex":("cash",["Capital Expenditure"]),
    "divida_total":("balance",["Total Debt","Long Term Debt"]),
    "caixa":("balance",["Cash And Cash Equivalents"]),
    "capitais_proprios":("balance",["Stockholders Equity","Common Stock Equity"]),
    "ativos_totais":("balance",["Total Assets"]),
    "goodwill":("balance",["Goodwill"]),
    "juros":("income",["Interest Expense","Interest Expense Non Operating"]),
    "da":("cash",["Depreciation And Amortization","Depreciation Amortization Depletion"]),
    "sga":("income",["Selling General And Administration"]),
    "rd":("income",["Research And Development"]),
    "ebit":("income",["Operating Income"]),
    "passivo_total":("balance",["Total Liabilities Net Minority Interest"]),
    "acoes_proprias":("balance",["Treasury Stock"]),
    "resultados_transitados":("balance",["Retained Earnings"]),
    "imposto":("income",["Tax Provision"]),
    "imposto_pago":("cash",["Income Tax Paid Supplemental Data"]),
    "resultado_antes_impostos":("income",["Pretax Income"]),
    "inventario":("balance",["Inventory"]),
    "dividendos_pagos":("cash",["Cash Dividends Paid","Common Stock Dividend Paid"]),
    "recompras":("cash",["Repurchase Of Capital Stock","Common Stock Payments"]),
    "sbc":("cash",["Stock Based Compensation"]),
    "var_fundo_maneio":("cash",["Change In Working Capital"]),
    "contas_receber":("balance",["Accounts Receivable","Receivables"]),
    "divida_curto_prazo":("balance",["Current Debt","Current Debt And Capital Lease Obligation"]),
    "emissao_divida":("cash",["Long Term Debt Issuance","Issuance Of Debt"]),
    "emissao_acoes":("cash",["Common Stock Issuance"]),
    "aquisicoes":("cash",["Purchase Of Business"]),
    "preferenciais":("balance",["Preferred Stock"]),
    "lpa_diluido":("income",["Diluted EPS"]),
    "reembolso_divida":("cash",["Long Term Debt Payments","Repayment Of Debt"]),
    "rl_continuadas":("income",["Net Income Continuous Operations"]),
    "divida_lp":("balance",["Long Term Debt"]),
    "margem_financeira":("income",["Net Interest Income"]),
    "intangiveis":("balance",["Other Intangible Assets"]),
    "ativo_corrente":("balance",["Current Assets"]),
    "passivo_corrente":("balance",["Current Liabilities"]),
    "custos_nao_juros":("income",["Non Interest Expense","Other Non Interest Expense"]),
}
_ABSOLUTOS={"capex","dividendos_pagos","recompras","aquisicoes","imposto_pago","juros","reembolso_divida"}   # pagamentos vêm com sinal negativo
_AV_MAPA={
    "receita":("INCOME_STATEMENT","totalRevenue"),"resultado_liquido":("INCOME_STATEMENT","netIncome"),
    "ebitda":("INCOME_STATEMENT","ebitda"),"lucro_bruto":("INCOME_STATEMENT","grossProfit"),
    "fco":("CASH_FLOW","operatingCashflow"),"capex":("CASH_FLOW","capitalExpenditures"),
    "divida_total":("BALANCE_SHEET","shortLongTermDebtTotal"),"caixa":("BALANCE_SHEET","cashAndCashEquivalentsAtCarryingValue"),
    "capitais_proprios":("BALANCE_SHEET","totalShareholderEquity"),"ativos_totais":("BALANCE_SHEET","totalAssets"),
    "goodwill":("BALANCE_SHEET","goodwill"),
    "juros":("INCOME_STATEMENT","interestExpense"),"da":("CASH_FLOW","depreciationDepletionAndAmortization"),
}

def _yf_dados(ticker: str) -> dict|None:
    """Demonstrações anuais e perfil da empresa via biblioteca yfinance, em cache 24 h."""
    _CACHE_MERC.mkdir(parents=True,exist_ok=True)
    fc=_CACHE_MERC/f"yf2_{ticker}.json"
    if fc.exists() and time.time()-fc.stat().st_mtime<24*3600:
        return json.loads(fc.read_text(encoding="utf-8"))
    try:
        import yfinance as yf
    except ImportError:
        return {"erro":"yfinance não instalado (pip install yfinance)"}
    out={"income":{},"cash":{},"balance":{},"info":{}}
    try:
        t=yf.Ticker(ticker)
        for nome,df in (("income",t.income_stmt),("cash",t.cashflow),("balance",t.balance_sheet)):
            if df is None or df.empty: continue
            for col in df.columns:
                ano=_af(str(col.date()))
                linhas={}
                for idx,v in df[col].items():
                    try:
                        fv=float(v)
                        if fv==fv: linhas[str(idx)]=fv   # ignora NaN
                    except (TypeError,ValueError): pass
                out[nome][str(ano)]=linhas
        info=t.info or {}
        out["info"]={k:info.get(k) for k in ("beta","sector","industry","longBusinessSummary","grossMargins",
                                               "trailingPE","dividendRate","currency","longName","heldPercentInsiders",
                                               "financialCurrency","country","marketCap","sharesOutstanding","trailingEps","shortName")}
    except Exception as e:
        out["erro"]=f"yfinance: {e}"
    fc.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    return out

def _av_dados(ticker: str) -> dict|None:
    """Dados de reserva da Alpha Vantage (só se existir chave no .env)."""
    chave=os.environ.get("ALPHAVANTAGE_API_KEY","").strip()
    if not chave: return None
    out={}
    for funcao in ("INCOME_STATEMENT","BALANCE_SHEET","CASH_FLOW","EARNINGS"):
        try:
            nome=f"av_{ticker}_{funcao}.json"; url=f"https://www.alphavantage.co/query?function={funcao}&symbol={ticker}&apikey={chave}"
            em_cache=(_CACHE_MERC/nome).exists()
            for tentativa in range(2):
                if not em_cache: time.sleep(1.3)                 # plano gratuito: no máximo 1 pedido por segundo
                d=_get_web(url,nome,validade_h=24*7)
                aviso=d.get("Information") or d.get("Note")
                if not aviso: break
                (_CACHE_MERC/nome).unlink(missing_ok=True); em_cache=False   # a resposta de limite não fica em cache
                if "per day" in aviso or "daily" in aviso.lower():
                    return {"erro":"Alpha Vantage: limite diário de pedidos atingido (25 por dia no plano gratuito)"}
                time.sleep(2.0)
            lista=d.get("annualEarnings") if funcao=="EARNINGS" else d.get("annualReports")
            if lista is None: return {"erro":str(d)[:150]} if funcao!="EARNINGS" else out
            out[funcao]={str(_af(r["fiscalDateEnding"])):r for r in lista}
        except Exception as e:
            return {"erro":f"Alpha Vantage: {e}"} if funcao!="EARNINGS" else out
    return out

def _completar_dados(d: dict, ticker: str) -> None:
    """Preenche células em falta com as fontes de reserva e verifica conflitos entre fontes."""
    origem=d.setdefault("origem_dados",{})
    for k,v in (d.pop("_origem_sec",None) or {}).items():
        rot,ano=k.split("/"); campo={"EBITDA":"ebitda","Gross Profit":"lucro_bruto","Diluted Shares Outstanding":"acoes_diluidas",
                          "Dividend Per Share":"dividendo_por_acao"}.get(rot,rot)
        if campo in d["series"]: origem[f"{campo}/{ano}"]=v
    conflitos=d.setdefault("conflitos_fontes",[])
    yf=_yf_dados(ticker) or {}
    d["fontes_reserva"]={"yfinance":yf.get("erro","ok") if yf else "indisponível"}
    moeda_yf=(yf.get("info") or {}).get("financialCurrency"); moeda_rel=d["empresa"].get("moeda_relatorio")
    if yf and not yf.get("erro") and moeda_yf and moeda_rel and moeda_yf!=moeda_rel:
        d["fontes_reserva"]["yfinance"]=f"não usado: contas em {moeda_yf}, relatório em {moeda_rel}"; yf={}
    if yf and not yf.get("erro"):
        for campo,(tabela,linhas) in _YF_MAPA.items():
            for a in d["series"][campo]:
                lin=(yf.get(tabela) or {}).get(str(a)) or {}
                v=next((lin[l] for l in linhas if l in lin),None)
                if v is None: continue
                if campo in _ABSOLUTOS: v=abs(v)
                atual=d["series"][campo][a]
                if atual is None:
                    d["series"][campo][a]=v; origem[f"{campo}/{a}"]="yfinance"
                elif campo in ("receita","resultado_liquido","fco") and atual and abs(v-atual)/abs(atual)>0.10:
                    conflitos.append(f"{campo}/{a}: SEC {_num(atual/1e6,0)} M vs yfinance {_num(v/1e6,0)} M (usado SEC)")
        for a in d["series"]["ebt_sem_extra"]:       # Secção 8.0: lucro antes de impostos sem itens não usuais
            lin=(yf.get("income") or {}).get(str(a)) or {}
            pt,inus=lin.get("Pretax Income"),lin.get("Total Unusual Items")
            if pt is not None and (d["series"]["ebt_sem_extra"][a] is None or "imparidades" in str(origem.get(f"ebt_sem_extra/{a}",""))):
                d["series"]["ebt_sem_extra"][a]=pt-(inus or 0.0); origem[f"ebt_sem_extra/{a}"]="yfinance (resultado antes de impostos - itens não usuais)"
        info=yf.get("info") or {}
        if info.get("heldPercentInsiders") is not None: d["insiders_pct"]=round(100*float(info["heldPercentInsiders"]),2)
        d["empresa"]["setor_yf"]=info.get("sector"); d["empresa"]["industria_yf"]=info.get("industry")
        if (d["empresa"].get("setor") in (None,"N/A")) and info.get("sector"):
            d["empresa"]["setor"]=f"{info['sector']} / {info.get('industry') or ''}".strip(" /")
        if info.get("longBusinessSummary"): d["resumo_negocio"]=info["longBusinessSummary"]
    falta=[(c,a) for c,s in d["series"].items() for a,v in s.items() if v is None and c not in CAMPOS_OPCIONAIS]
    if any(v is None for v in d["series"]["acoes_diluidas"].values()): falta.append(("acoes_diluidas","*"))
    if falta:
        av=_av_dados(ticker)
        d["fontes_reserva"]["alpha_vantage"]=("sem chave no .env" if av is None else av.get("erro","ok"))
        if av and not av.get("erro"):
            for c,a in falta:
                if c not in _AV_MAPA: continue
                funcao,chave=_AV_MAPA[c]
                bruto=((av.get(funcao) or {}).get(str(a)) or {}).get(chave)
                v=_ler(bruto)
                if v is None: continue
                d["series"][c][a]=abs(v) if c in _ABSOLUTOS else v; origem[f"{c}/{a}"]="Alpha Vantage"
            # LPA anual reportado (Alpha Vantage EARNINGS): completa o LPA e as ações de anos antigos que a SEC só
            # tem por classe de ações (ex.: Visa, Hershey)
            for a in d["series"]["lpa_diluido"]:
                ganho=((av.get("EARNINGS") or {}).get(str(a)) or {}).get("reportedEPS")
                v=_ler(ganho)
                if v is None: continue
                if d["series"]["lpa_diluido"][a] is None:
                    d["series"]["lpa_diluido"][a]=v; origem[f"lpa_diluido/{a}"]="Alpha Vantage (EARNINGS)"
                rl=d["series"]["resultado_liquido"].get(a)
                if d["series"]["acoes_diluidas"].get(a) is None and rl and v>0:
                    d["series"]["acoes_diluidas"][a]=rl/v; origem[f"acoes_diluidas/{a}"]="derivado: lucro / LPA (Alpha Vantage)"
    d["em_falta"]=[f"{c}/{a}" for c,s in d["series"].items() for a,v in s.items() if v is None and c not in CAMPOS_OPCIONAIS]
    d["em_falta"]+=[c for c,v in d["pontuais"].items() if v is None]

def _pl_de_dados(ticker: str, d: dict) -> None:
    """P/L de fim de exercício (preço no mês de fecho / LPA desse ano), como o "PE Ratio" anual do protocolo.
    Guarda também os preços de fim de exercício e o preço do início da janela."""
    conv=(d.get("mercado") or {}).get("mensal_convertido")
    if conv: mens={(int(k[:4]),int(k[5:7])):v for k,v in conv.items()}
    else:
        try: mens=_mensais(_yahoo_chart(ticker,"10y","1mo"))
        except Exception: return
    if not mens: return
    fim=d.get("fim_exercicio") or {}
    pl_fim,preco_fim,pl_medio_ano={},{},{}
    for a in _anos(d):
        rl,ac=_val(d,"resultado_liquido",a),_val(d,"acoes_diluidas",a)
        try: mes=int(str(fim.get(str(a)) or f"{a}-12-31")[5:7]); ano_f=int(str(fim.get(str(a)) or f"{a}")[:4])
        except ValueError: mes,ano_f=12,int(a)
        p=mens.get((ano_f,mes))
        if p is not None: preco_fim[int(a)]=round(p,2)
        if rl and ac and rl>0 and ac>0:
            lpa=rl/ac
            if p is not None and 0<p/lpa<200: pl_fim[int(a)]=round(p/lpa,1)
            precos=[c for (y,_),c in mens.items() if y==int(a)]
            if len(precos)>=6 and 0<statistics.mean(precos)/lpa<200: pl_medio_ano[int(a)]=round(statistics.mean(precos)/lpa,1)
    chaves=sorted(mens); (y0,m0)=chaves[0]
    mk=d.get("mercado") if d.get("mercado") is not None else {}
    mk.update({"pl_fim_ano":pl_fim,"preco_fim_ano":preco_fim,"pl_por_ano":pl_medio_ano,
               "preco_inicio_janela":{"data":f"{y0}-{m0:02d}","preco":round(mens[(y0,m0)],2)}})
    if pl_fim:
        media=round(statistics.mean(pl_fim.values()),1)
        mk["pl_medio_10a"]=media; mk["pl_max_10a"]=max(pl_fim.values()); mk["pl_medio"]=media
        d["pontuais"]["pl_medio_historico"]=media
        d["em_falta"]=[x for x in d["em_falta"] if x!="pl_medio_historico"]
    d["mercado"]=mk

def _ajustar_desdobramentos(d: dict, ticker: str) -> None:
    """Desdobramentos de ações (splits): a SEC guarda o n.º de ações de anos antigos na base da época,
    mas os preços do Yahoo vêm ajustados. Sem este ajuste, o LPA antigo fica inflacionado (ex.: NVDA, P/L 0,8).
    Para cada ano, escolhe-se o fator de split que põe o n.º de ações na mesma base dos anos recentes."""
    import math
    try: res=_yahoo_chart(ticker,"10y","1mo")
    except Exception: return
    splits=[]
    for ev in ((res.get("events") or {}).get("splits") or {}).values():
        try:
            dt=datetime.datetime.fromtimestamp(ev["date"],datetime.timezone.utc).date()
            splits.append((dt,float(ev["numerator"])/float(ev["denominator"])))
        except (KeyError,TypeError,ZeroDivisionError): continue
    if not splits: return
    acoes=d["series"]["acoes_diluidas"]; anos=sorted(acoes)
    recentes=[acoes[a] for a in anos[-2:] if acoes[a]]
    if not recentes: return
    ref=statistics.median(recentes); origem=d.setdefault("origem_dados",{}); notas=d.setdefault("ajustes_split",[])
    for a in anos:
        s=acoes[a]
        if not s: continue
        candidatos={1.0}
        for limite in (datetime.date(int(a),1,1),datetime.date(int(a),12,31)):
            f=1.0
            for dt,r in splits:
                if dt>limite: f*=r
            candidatos.add(f)
        melhor=min(candidatos,key=lambda m:abs(math.log(s*m/ref)))
        if melhor!=1.0 and abs(math.log(s/ref))-abs(math.log(s*melhor/ref))>math.log(1.5):
            acoes[a]=s*melhor; origem[f"acoes_diluidas/{a}"]=f"ajuste de desdobramento x{_num(melhor,0)} (Yahoo)"
            dpa=d["series"].get("dividendo_por_acao",{}).get(a)
            if dpa and f"dividendo_por_acao/{a}" not in origem:
                d["series"]["dividendo_por_acao"][a]=dpa/melhor
            notas.append(f"{a}: ações x{_num(melhor,0)}")
