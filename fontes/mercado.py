"""Dados de mercado automáticos: preço, histórico e dividendos (Yahoo Finance) e Tesouro a 10 anos."""
import datetime, json, statistics, time, urllib.error, urllib.request, math, re
from config import RAIZ


# Fontes gratuitas, sem chave e sem limite diário:
#   Preço, histórico mensal e dividendos: Yahoo Finance (endpoint público de gráficos)
#   Taxa do Tesouro a 10 anos: Departamento do Tesouro dos EUA (CSV oficial); reserva: Yahoo ^TNX
_UA_WEB={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
_CACHE_MERC=RAIZ/"dados"/"cache_mercado"

def _get_web(url, nome_cache=None, validade_h=12, json_=True):
    """Pedido HTTP com cache em disco (validade em horas) para não repetir pedidos às mesmas páginas."""
    if nome_cache:
        _CACHE_MERC.mkdir(parents=True,exist_ok=True)
        fc=_CACHE_MERC/nome_cache
        if fc.exists() and time.time()-fc.stat().st_mtime<validade_h*3600:
            txt=fc.read_text(encoding="utf-8"); return json.loads(txt) if json_ else txt
    req=urllib.request.Request(url,headers=_UA_WEB)
    with urllib.request.urlopen(req,timeout=20) as r: txt=r.read().decode("utf-8","replace")
    if nome_cache: (_CACHE_MERC/nome_cache).write_text(txt,encoding="utf-8")
    return json.loads(txt) if json_ else txt

def _yahoo_chart(simbolo, alcance="10y", intervalo="1mo"):
    """Série de preços do Yahoo Finance para um símbolo."""
    import urllib.parse
    url=(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(simbolo)}"
         f"?range={alcance}&interval={intervalo}&events=div%7Csplit")
    d=_get_web(url,f"yahoo_{simbolo.replace('^','_')}_{alcance}_{intervalo}_v2.json",validade_h=6)
    res=(d.get("chart") or {}).get("result")
    if not res: raise ValueError(f"Yahoo Finance sem dados para {simbolo}")
    return res[0]

def _taxa_10_anos() -> tuple[float|None,str]:
    """Taxa do Tesouro dos EUA a 10 anos (a taxa de desconto de referência quando as contas são em dólares)."""
    ano=datetime.date.today().year
    for a in (ano,ano-1):
        try:
            url=(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
                 f"{a}/all?type=daily_treasury_yield_curve&field_tdr_date_value={a}&page&_format=csv")
            txt=_get_web(url,f"tesouro_{a}.csv",validade_h=12,json_=False)
            linhas=[l for l in txt.splitlines() if l.strip()]
            cab=[c.strip().strip('"') for c in linhas[0].split(",")]
            i10=cab.index("10 Yr"); ult=linhas[1].split(",")
            return float(ult[i10]),f"Tesouro dos EUA ({ult[0]})"
        except Exception:
            continue
    try:
        r=_yahoo_chart("^TNX","5d","1d")
        return round(float(r["meta"]["regularMarketPrice"]),3),"Yahoo Finance ^TNX"
    except Exception:
        return None,"indisponível"

def _mensais(res) -> dict:
    """{(ano,mês): fecho} a partir da resposta do Yahoo."""
    out={}
    for ts,c in zip(res.get("timestamp") or [],(res.get("indicators",{}).get("quote") or [{}])[0].get("close") or []):
        if c is None: continue
        dt=datetime.datetime.fromtimestamp(ts,datetime.timezone.utc)
        out[(dt.year,dt.month)]=c
    return out

def _beta(ticker) -> float|None:
    """Beta da ação (sensibilidade ao mercado), do Yahoo; usado só no custo do capital dos bancos."""
    try:
        a=_mensais(_yahoo_chart(ticker,"5y","1mo")); m=_mensais(_yahoo_chart("^GSPC","5y","1mo"))
    except Exception:
        return None
    chaves=sorted(set(a)&set(m))
    ra,rm=[],[]
    for k0,k1 in zip(chaves,chaves[1:]):
        ra.append(a[k1]/a[k0]-1); rm.append(m[k1]/m[k0]-1)
    if len(ra)<24: return None
    ma,mm=statistics.mean(ra),statistics.mean(rm)
    cov=sum((x-ma)*(y-mm) for x,y in zip(ra,rm))/(len(ra)-1)
    var=statistics.variance(rm)
    return round(cov/var,2) if var else None

def _mercado(ticker: str, fin: dict) -> dict:
    """Preço atual, P/L médio histórico, dividendos por ano e beta, a partir do Yahoo Finance.
    fin: {ano: {"Net Income":..., "Diluted Shares Outstanding":...}} vindo da SEC."""
    out={"preco":None,"moeda":None,"data_preco":None,"fonte_preco":"Yahoo Finance",
         "pl_medio":None,"pl_por_ano":{},"dividendos_por_ano":{},"beta":None}
    try:
        res=_yahoo_chart(ticker,"10y","1mo")
    except Exception as e:
        out["erro"]=str(e); return out
    meta=res.get("meta",{})
    out["preco"]=meta.get("regularMarketPrice"); out["moeda"]=meta.get("currency")
    if meta.get("regularMarketTime"):
        out["data_preco"]=datetime.datetime.fromtimestamp(meta["regularMarketTime"],datetime.timezone.utc).strftime("%Y-%m-%d")
    mens=_mensais(res); out["mensal"]={f"{y}-{m:02d}":c for (y,m),c in mens.items()}
    for ev in (res.get("events",{}).get("dividends") or {}).values():
        a=datetime.datetime.fromtimestamp(ev["date"],datetime.timezone.utc).year
        out["dividendos_por_ano"][a]=round(out["dividendos_por_ano"].get(a,0)+ev["amount"],4)
    pls=[]
    for a,linha in fin.items():
        try:
            rl=float(linha.get("Net Income")); ac=float(linha.get("Diluted Shares Outstanding"))
        except (TypeError,ValueError):
            continue
        precos=[c for (y,_),c in mens.items() if y==int(a)]
        if rl>0 and ac>0 and len(precos)>=6:
            pl=statistics.mean(precos)/(rl/ac)
            if 0<pl<80: out["pl_por_ano"][int(a)]=round(pl,1); pls.append(pl)
    if pls: out["pl_medio"]=round(statistics.median(pls),1)   # mediana: robusta a anos com lucro anómalo
    out["beta"]=None          # v4.27: o beta não é usado (Buffett considera-o uma medida errada de risco)
    return out


# ═══ Moedas, ADR e taxa do Estado na moeda do relatório (empresas não americanas)
_PENCE = {"GBp": ("GBP", 0.01), "GBX": ("GBP", 0.01), "ZAc": ("ZAR", 0.01), "ILA": ("ILS", 0.01)}

def _moeda_base(m):
    """Bolsas que cotam em centésimos (Londres em pence): devolve (moeda, escala)."""
    return _PENCE.get(m, (m, 1.0)) if m else (m, 1.0)

def _fx_mensal(de: str, para: str):
    """Câmbio de 'de' para 'para' (quantas unidades de 'para' vale 1 'de'): (atual, {(ano, mês): fecho}) do Yahoo."""
    if not de or not para or de == para: return 1.0, {}
    res = _yahoo_chart(f"{de}{para}=X", "10y", "1mo")
    atual = res.get("meta", {}).get("regularMarketPrice")
    mens = _mensais(res)
    if atual is None and mens: atual = mens[max(mens)]
    if atual is None: raise ValueError(f"câmbio {de}/{para} indisponível")
    return float(atual), mens

_RACIOS = [0.1, 0.2, 0.25, 1 / 3, 0.5, 1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 50, 100]

def _racio_adr(preco, moeda_preco, lpa_ult, acoes_ult, moeda_fin, fx_fin_para_preco, info):
    """Quantas ações representa um ADR. Método principal: capitalização (preço do ADR x n.º de ações / capitalização
    do Yahoo), que não depende do crescimento dos lucros. Reserva: LPA do Yahoo por ADR (últimos 12 meses) face ao LPA
    do último exercício, menos fiável quando os lucros crescem depressa. Arredonda-se para um rácio usual."""
    snap = lambda r: min(_RACIOS, key=lambda x: abs(math.log(r / x)))
    mc, eps = info.get("marketCap"), info.get("trailingEps")
    r_cap = preco * acoes_ult / float(mc) if mc and acoes_ult and preco else None
    r_eps = float(eps) / (lpa_ult * fx_fin_para_preco) if eps and lpa_ult and lpa_ult > 0 and fx_fin_para_preco else None
    if r_cap and r_cap > 0:
        escolhido = snap(r_cap); desvio = abs(math.log(r_cap / escolhido))
        nota = f"capitalização indica {r_cap:.2f}" + (f"; LPA indica {r_eps:.2f}" if r_eps else "")
        if desvio > 0.15: nota += " (longe de um rácio usual: confirmar)"
        return escolhido, f"1 ADR = {escolhido:g} ação(ões) ({nota})"
    if r_eps and r_eps > 0:
        escolhido = snap(r_eps)
        return escolhido, f"1 ADR = {escolhido:g} ação(ões) (só pelo LPA, {r_eps:.2f}: confirmar o rácio do ADR)"
    return 1.0, "rácio ADR desconhecido: assumido 1 ADR = 1 ação (confirmar)"

_FRED_PAIS = {"GBP": "GB", "CHF": "CH", "JPY": "JP", "SEK": "SE", "NOK": "NO", "CAD": "CA", "AUD": "AU", "KRW": "KR",
              "NZD": "NZ", "PLN": "PL", "CZK": "CZ", "HUF": "HU", "MXN": "MX", "ILS": "IL"}

def _bund_10_anos():
    """Bund a 10 anos (Bundesbank, rendimento diário da curva de taxas), como pede o protocolo para EUR e DKK."""
    url = ("https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"
           "?lastNObservations=5&format=csv")
    txt = _get_web(url, "bund_10a.csv", validade_h=12, json_=False)
    obs = [l.split(";") for l in txt.splitlines() if re.match(r"^\d{4}-\d{2}-\d{2};", l)]
    obs = [(d, v) for d, v, *_ in obs if v.strip() and v.strip() != "."]
    d, v = obs[-1]
    return float(v.replace(",", ".")), f"Bund a 10 anos, Bundesbank ({d})"

def _taxa_10_anos_moeda(moeda: str):
    """Taxa do Estado a 10 anos na moeda do relatório (Secção 8.0 da v4.27): USD -> Tesouro dos EUA; EUR e DKK -> Bund;
    outras moedas -> obrigação do próprio Estado (OECD, via FRED). Sem série gratuita: Bund, assinalado no relatório."""
    if moeda in (None, "USD"): return _taxa_10_anos()
    if moeda in ("EUR", "DKK"):
        try: return _bund_10_anos()
        except Exception: pass
    pais = _FRED_PAIS.get(moeda)
    if pais:
        try:
            txt = _get_web(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01{pais}M156N", f"fred_{pais}.csv", validade_h=24, json_=False)
            linhas = [l.split(",") for l in txt.splitlines()[1:] if "," in l and l.split(",")[1] not in ("", ".")]
            d, v = linhas[-1][:2]
            return float(v), f"obrigação do Estado a 10 anos ({pais}, OCDE via FRED, {d})"
        except Exception: pass
    try:
        v, f = _bund_10_anos()
        return v, f + f" — aproximação: sem série gratuita para {moeda} (calibração)"
    except Exception:
        v, f = _taxa_10_anos()
        return v, (f + f" — aproximação: sem série gratuita para {moeda}") if v is not None else f

