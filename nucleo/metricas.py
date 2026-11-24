"""Métricas financeiras: ROIC, ROE, margens, Owner Earnings, lucros normalizados e evidência numérica do fosso."""
import statistics
from nucleo.util import _num


def _anos(d): return sorted(int(a) for a in d["anos"])
def _val(d, c, a): return d["series"].get(c,{}).get(str(a))
def _serie(d, c): return [( a, _val(d,c,a)) for a in _anos(d)]
def _ult(d, c):
    v=[v for _,v in _serie(d,c) if v is not None]; return v[-1] if v else None
def _med(lst): c=[v for v in lst if v is not None]; return statistics.median(c) if c else None
def _rac(a,b,s=1.0): return None if (a is None or b is None or b==0) else s*a/b

def _fcf(d):
    return {a:(None if _val(d,"fco",a) is None or _val(d,"capex",a) is None
               else _val(d,"fco",a)-_val(d,"capex",a)) for a in _anos(d)}

def _por_acao(d, serie_ou_campo):
    return {a: _rac(serie_ou_campo[a] if isinstance(serie_ou_campo,dict) else _val(d,serie_ou_campo,a),
                    _val(d,"acoes_diluidas",a)) for a in _anos(d)}

def _fco_neg_consec(d):
    maior=atual=0
    for _,v in _serie(d,"fco"):
        atual = atual+1 if (v is not None and v<0) else 0
        maior = max(maior,atual)
    return maior

def _div_ebitda(d):
    div,eb=_ult(d,"divida_total"),_ult(d,"ebitda")
    if div is None or eb is None: return None
    if eb<=0: return float("inf") if div>0 else 0.0
    return div/eb

def _dilui_3(d):
    pts=[(a,v) for a,v in _serie(d,"acoes_diluidas") if v]
    if len(pts)<2: return None
    fa,fv=pts[-1]; ia,iv=next((p for p in pts if p[0]>=fa-3),pts[0])
    return 100*(fv/iv-1)

def _gw_pct(d): return _rac(_ult(d,"goodwill"),_ult(d,"ativos_totais"),100)
def _mg_liq(d): return _med([_rac(_val(d,"resultado_liquido",a),_val(d,"receita",a),100) for a in _anos(d)])
def _roe(d):
    vs=[]
    for a in _anos(d):
        cp=_val(d,"capitais_proprios",a)
        vs.append(_rac(_val(d,"resultado_liquido",a),cp,100) if cp and cp>0 else None)
    return _med(vs)

def _roic_anual(d) -> dict:
    """ROIC por ano: resultado líquido / (capitais próprios + dívida - caixa)."""
    out={}
    for a in _anos(d):
        cp,div=_val(d,"capitais_proprios",a),_val(d,"divida_total",a)
        if cp is None or div is None: out[a]=None; continue
        inv=cp+div-(_val(d,"caixa",a) or 0)
        out[a]=_rac(_val(d,"resultado_liquido",a),inv,100) if inv>0 else None
    return out

def _roic(d): return _med(list(_roic_anual(d).values()))

def _margem_bruta_anual(d) -> dict:
    return {a:_rac(_val(d,"lucro_bruto",a),_val(d,"receita",a),100) for a in _anos(d)}

def _extraordinarios(vals: dict) -> set:
    """Anos com valor por ação anómalo face aos anos vizinhos (lucro ou perda extraordinária).
    Compara cada ano com os vizinhos e não com a mediana global, para não confundir crescimento rápido com anomalia.
    Interior: fora de 0,4x a 1,6x a média dos dois vizinhos. Extremos: fora de 0,4x a 2,5x o vizinho válido mais próximo.
    Buffett avalia lucros normalizados: estes anos não entram no crescimento nem na base da avaliação."""
    anos=[a for a in sorted(vals) if vals[a] is not None]
    if len(anos)<4: return set()
    v=[vals[a] for a in anos]; fora=set()
    for i in range(1,len(v)-1):
        ref=(v[i-1]+v[i+1])/2
        if ref>0 and (v[i]<=0 or v[i]>1.6*ref or v[i]<0.4*ref): fora.add(anos[i])
    for i,viz in ((0,range(1,len(v))),(len(v)-1,range(len(v)-2,-1,-1))):
        k=next((k for k in viz if anos[k] not in fora),None)
        if k is None: continue
        ref=v[k]
        if ref>0 and (v[i]<=0 or v[i]>2.5*ref or v[i]<0.4*ref): fora.add(anos[i])
    return fora

def _cagr_pts(pts):
    pts=[(a,v) for a,v in pts if v is not None]
    if len(pts)<2: return None
    (a0,v0),(a1,v1)=pts[0],pts[-1]
    if v0<=0 or v1<=0: return None
    return 100*((v1/v0)**(1/(a1-a0))-1)

def _cagr(d,c): return _cagr_pts(_serie(d,c))

def _cagr_suave(vals: dict) -> float | None:
    """CAGR entre a média dos 2 primeiros e dos 2 últimos anos positivos.
    Reduz o efeito de um ano anómalo (ex.: pagamento extraordinário que afunda o FCF)."""
    pts=[(a,v) for a,v in sorted(vals.items()) if v is not None and v>0]
    if len(pts)<3: return _cagr_pts(pts)
    (a0,v0),(a1,v1)=pts[0],pts[1]; (b0,w0),(b1,w1)=pts[-2],pts[-1]
    anos=((b0+b1)/2)-((a0+a1)/2)
    if anos<=0: return None
    return 100*((((w0+w1)/2)/((v0+v1)/2))**(1/anos)-1)

def _oe_por_acao(d) -> dict:
    """Owner Earnings por ação (Buffett, carta de 1986): RL + D&A - CapEx de manutenção.
    Aproximação com os dados disponíveis: FCO - CapEx total, por ação diluída."""
    out={}
    for a in _anos(d):
        fco,cap,ac=_val(d,"fco",a),_val(d,"capex",a),_val(d,"acoes_diluidas",a)
        out[a]=None if fco is None or cap is None or not ac else (fco-cap)/ac
    return out

def _payout(d) -> float:
    """Percentagem dos lucros distribuída em dividendos (mediana dos últimos 3 anos)."""
    vs=[]
    for a in _anos(d)[-3:]:
        dpa=_val(d,"dividendo_por_acao",a); rl=_val(d,"resultado_liquido",a); ac=_val(d,"acoes_diluidas",a)
        if dpa is not None and rl and ac and rl>0: vs.append(dpa/(rl/ac))
    return round(min(max(statistics.median(vs),0.0),0.9),3) if vs else 0.0

def _evidencia_fosso(d) -> dict:
    """Sinais numéricos de vantagem competitiva duradoura (Buffett: o fosso vê-se em retornos altos e persistentes).
    ROIC (sinal principal): mediana >= 15% e mínimo >= 10% = forte; mediana >= 10% = moderado.
    Margem bruta (poder de preço): mediana >= 40% e amplitude <= 10 p.p. = forte; mediana >= 30% = moderado.
    Nível forte exige ROIC forte; anos com lucro extraordinário não contam."""
    r=_resumo(d)
    ext=set(r["anos_extraordinarios"]["lpa"])
    roic=[v for a,v in r["roic_anual"].items() if v is not None and a not in ext]
    mb=[v for v in r["margem_bruta_anual"].values() if v is not None]
    sinais={}
    if len(roic)>=3:
        med,mn=statistics.median(roic),min(roic)
        sinais["roic"]={"nivel":"forte" if med>=15 and mn>=10 else ("moderado" if med>=10 else "fraco"),
                        "facto":f"ROIC mediano {_num(med,1)}%, mínimo {_num(mn,1)}% em {len(roic)} anos"}
    if len(mb)>=3:
        med,amp=statistics.median(mb),max(mb)-min(mb)
        sinais["margem_bruta"]={"nivel":"forte" if med>=40 and amp<=10 else ("moderado" if med>=30 else "fraco"),
                                "facto":f"margem bruta mediana {_num(med,1)}%, amplitude {_num(amp,1)} p.p. em {len(mb)} anos"}
    if not sinais: return {"nivel":"sem dados","sinais":{},"factos":[]}
    sr=sinais.get("roic",{}).get("nivel"); sm=sinais.get("margem_bruta",{}).get("nivel")
    if sr=="forte" and sm in (None,"forte","moderado"): nivel="forte"
    elif sr in ("forte","moderado") or sm=="forte": nivel="moderada"
    else: nivel="fraca"
    return {"nivel":nivel,"sinais":sinais,"factos":[s["facto"] for s in sinais.values()]}

def _resumo(d):
    """Resumo numérico de uma empresa (FCF, LPA, Owner Earnings, margens, ROE, ROIC, dívida/EBITDA, crescimento...). É o que a parte qualitativa do Avaliador recebe como contexto e o que o Crítico confronta com as respostas."""
    fcf=_fcf(d); fcf_a=_por_acao(d,fcf); lpa=_por_acao(d,"resultado_liquido"); oe=_oe_por_acao(d)
    ext_lpa=_extraordinarios(lpa); ext_oe=_extraordinarios(oe)
    lpa_n={a:(None if a in ext_lpa else v) for a,v in lpa.items()}
    oe_n={a:(None if a in ext_oe else v) for a,v in oe.items()}
    mb=_margem_bruta_anual(d)
    return {
        "lpa_normal":lpa_n,"oe_normal":oe_n,
        "anos_extraordinarios":{"lpa":{a:lpa[a] for a in sorted(ext_lpa)},"oe":{a:oe[a] for a in sorted(ext_oe)}},
        "roic_anual":_roic_anual(d),"margem_bruta_anual":mb,
        "anos":_anos(d), "margem_liquida_pct":_mg_liq(d), "roe_pct":_roe(d), "roic_pct":_roic(d),
        "crescimento_receita_pct":_cagr(d,"receita"), "crescimento_fcf_pct":_cagr_pts(sorted(fcf.items())),
        "crescimento_lpa_pct":_cagr_suave(lpa_n), "crescimento_oe_pct":_cagr_suave(oe_n),
        "divida_ebitda":_div_ebitda(d), "diluicao_3_anos_pct":_dilui_3(d),
        "goodwill_pct_ativos":_gw_pct(d), "fco_negativo_consecutivo":_fco_neg_consec(d),
        "fcf_anual":fcf, "fcf_por_acao":fcf_a, "lpa":lpa, "oe_por_acao":oe, "payout":_payout(d),
        "vpa_ultimo":_rac(_ult(d,"capitais_proprios"),_ult(d,"acoes_diluidas")),
        "resultado_liquido":dict(_serie(d,"resultado_liquido")),
    }
