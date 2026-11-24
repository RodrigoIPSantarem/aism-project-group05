"""A1 Coletor: recolhe, normaliza e completa os dados.

Papel no sistema: é o primeiro agente a receber o pedido do utilizador. Vai buscar as demonstrações financeiras à fonte
escolhida (SEC ou dataset sintético), junta o preço e a taxa do Estado a 10 anos, põe tudo no mesmo esquema
(`normalizar`) e entrega-o ao Guardião (inform). Se não conseguir (p. ex. a empresa não está na SEC), responde ao utilizador
com `failure`. O que não encontra fica marcado como «em falta» (lista `em_falta`), nunca é inventado.
Regra de ouro: o modelo de linguagem nunca inventa valores; só ajuda a reconhecer o nome de uma linha (`_mapear`)."""
import os
from config import TAXA_RENTABILIDADE_ALVO
import statistics
from fontes.fdic import fdic_indicadores
from fontes.mercado import _fx_mensal, _mercado, _moeda_base, _racio_adr, _taxa_10_anos_moeda
from fontes.reserva import _ajustar_desdobramentos, _completar_dados, _pl_de_dados, _yf_dados
from fontes.sec import _sec_cik_por_nome, _sec_obter
from fontes.sintetico import _sint_obter
from nucleo.llm import ErroLLM
from nucleo.metricas import _resumo
from nucleo.plataforma import Agente, Msg
from nucleo.util import CAMPOS_OPCIONAIS, _CAMPOS_PONT, _CAMPOS_SERIE, _campo, _ler, _moat


_SIS_COL="""És o Coletor de um sistema de análise fundamental. Para cada rótulo não reconhecido,
indica o campo do esquema que mede EXATAMENTE a mesma coisa, ou null.
Nunca inventes campos nem valores. Responde só com JSON: {"mapeamentos":{"<rótulo>":"<campo ou null>"}}"""

class Coletor(Agente):
    """Recebe o pedido do utilizador (request). Recolhe os dados e envia-os ao Guardião (inform). Se a recolha falha responde ao utilizador com failure."""
    nome="coletor"; rotulo="[A1 Coletor]"

    def _bruto(self, ped):
        """Fontes de demonstrações financeiras, todas com até 10 anos:
        1) SEC pelo ticker (EUA e ADR: 10-K, 20-F, 40-F; US-GAAP ou IFRS);
        2) SEC pelo nome da empresa (ticker de bolsa estrangeira de uma empresa registada na SEC, ex.: NOVO-B.CO);
        3) dataset sintético (fonte "sintetico"), para testes e demonstração."""
        if ped.get("fonte","sintetico")!="sec": return _sint_obter(ped["ticker"])                # dados de demonstração
        # ramo SEC: primeiro pelo ticker, depois (se falhar) pelo nome da empresa
        t=ped["ticker"].strip().upper(); n=max(ped["anos"],5)
        ua=os.environ.get("SEC_USER_AGENT","Rodrigo Silva 240000762@esg.ipsantarem.pt")
        tentativas=[]; bruto=None
        try: bruto=_sec_obter(t,ua,n,ped.get("preco"),ped.get("taxa"))
        except Exception as e: tentativas.append(f"SEC pelo ticker: {e}")
        if bruto is None:
            self.dizer("a procurar a empresa na SEC pelo nome…")
            nome=((_yf_dados(t) or {}).get("info") or {}).get("longName")
            achado=_sec_cik_por_nome(nome,ua) if nome else None
            if achado:
                try:
                    bruto=_sec_obter(t,ua,n,ped.get("preco"),ped.get("taxa"),cik=achado[0])
                    bruto["nota_fonte"]=f"empresa encontrada na SEC pelo nome ({achado[2]}, ADR {achado[1]})"
                except Exception as e: tentativas.append(f"SEC pelo nome: {e}")
        if bruto is None:
            raise ValueError("sem dados na SEC — " + " | ".join(tentativas) +
                             ". A fonte SEC só tem empresas cotadas nos EUA (ou com ADR registado na SEC).")
        bruto["ticker"]=t; bruto["tentativas_fontes"]=tentativas; bruto["outras_fontes"]=[]
        self.dizer(f"fonte: {bruto['source']} · {len(bruto['financials'])} anos")
        return self._enriquecer_mercado(bruto,ped,None)

    def _enriquecer_mercado(self, bruto, ped, info=None):
        """Preço, histórico, dividendos e taxa do Estado a 10 anos na moeda do relatório.
        Se o preço vier noutra moeda (ADR em USD, Londres em pence), converte pelo câmbio de cada mês e pelo rácio do ADR."""
        # a moeda do relatório manda: o preço e a taxa do Estado são convertidos para ela, para que tudo fique na mesma unidade
        moeda_rel=bruto.get("moeda_relatorio") or "USD"
        self.dizer(f"a recolher dados de mercado (Yahoo Finance) e a taxa do Estado a 10 anos em {moeda_rel}…")
        mk=_mercado(ped["ticker"],{})
        moeda_p,escala=_moeda_base(mk.get("moeda"))
        notas=[]; fx_atual,fx_mens,racio=1.0,{},1.0
        if mk.get("preco") is not None and moeda_p and moeda_p!=moeda_rel:
            try:
                fx_atual,fx_mens=_fx_mensal(moeda_p,moeda_rel)
                notas.append(f"preço em {mk.get('moeda')} convertido para {moeda_rel} ao câmbio {fx_atual:.4f} (histórico ao câmbio de cada mês)")
            except Exception as e:
                raise ValueError(f"preço em {moeda_p} e contas em {moeda_rel}, sem câmbio disponível: {e}")
            if moeda_p=="USD":           # cotação em USD de uma empresa que reporta noutra moeda: ADR
                info=info or (_yf_dados(ped["ticker"]) or {}).get("info") or {}
                anos=sorted(bruto["financials"]); ult=bruto["financials"][anos[-1]] if anos else {}
                lpa=_ler(ult.get("lpa_diluido")); ac=_ler(ult.get("Diluted Shares Outstanding"))
                racio,nota_r=_racio_adr(mk["preco"]*escala,moeda_p,lpa,ac,moeda_rel,1/fx_atual if fx_atual else None,info)
                notas.append(nota_r)
        elif escala!=1: notas.append(f"preço em {mk.get('moeda')} (centésimos) convertido para {moeda_p}")
        conv=lambda v,fx: v*escala*fx/racio
        if mk.get("preco") is not None:
            mk["preco_original"]=mk["preco"]; mk["moeda_original"]=mk.get("moeda")
            mk["preco"]=round(conv(mk["preco"],fx_atual),4); mk["moeda"]=moeda_rel
        mensal={}
        for k,v in (mk.get("mensal") or {}).items():
            y,m_=int(k[:4]),int(k[5:7])
            mensal[k]=conv(v,fx_mens.get((y,m_),fx_atual))
        mk["mensal_convertido"]=mensal
        divs={}
        for a,v in (mk.get("dividendos_por_ano") or {}).items():
            fxs=[x for (y,_),x in fx_mens.items() if y==int(a)]
            divs[int(a)]=conv(v,statistics.mean(fxs) if fxs else fx_atual)
        mk["dividendos_por_ano"]=divs; mk["racio_adr"]=racio; mk["notas_moeda"]=notas
        mk["fx_cotacao_para_relatorio"]=fx_atual; mk["escala_cotacao"]=escala
        if ped.get("taxa") is not None: taxa,fonte_taxa=ped["taxa"],"indicada pelo utilizador"
        else:
            try: taxa,fonte_taxa=_taxa_10_anos_moeda(moeda_rel)
            except Exception as e: taxa,fonte_taxa=None,f"indisponível ({e})"
        if ped.get("preco") is None and mk.get("preco") is not None: bruto["price"]=mk["preco"]
        elif ped.get("preco") is not None: mk["preco"]=ped["preco"]; mk["fonte_preco"]="indicado pelo utilizador"
        if taxa is not None: bruto["us10y"]=taxa
        for a,linha in bruto["financials"].items():
            if linha.get("Dividend Per Share") in (None,"N/A") and int(a) in divs: linha["Dividend Per Share"]=divs[int(a)]
        bruto["currency"]=moeda_rel
        mk["taxa_10a"]=taxa; mk["fonte_taxa"]=fonte_taxa
        bruto["_mercado"]=mk
        for nt in notas: self.dizer(nt)
        return bruto

    def _mapear(self, desc, ja):
        """Único uso do modelo no Coletor: para os rótulos que o dicionário não reconhece, pergunta a que campo do esquema
        correspondem. O modelo só pode escolher um campo que exista e que ainda esteja livre; não devolve números."""
        if not desc or not self.llm: return {}
        campos="\n".join(f"- {c}: {d}" for c,d in _CAMPOS_SERIE.items())
        try:
            r=self.llm.json(self.nome,_SIS_COL,f"Campos:\n{campos}\n\nRótulos:\n"+"\n".join(f"- {x}" for x in desc))
        except ErroLLM as e:
            self.dizer(f"modelo indisponível ({e})"); return {}
        return {k:v for k,v in (r.get("mapeamentos") or {}).items()
                if k in desc and v in _CAMPOS_SERIE and v not in ja.values()}

    def normalizar(self, bruto, n_anos):
        """Passa os dados brutos (rótulos de cada fonte) para o esquema único do sistema: séries por ano (receita, resultado,
        FCO, capex, dívida...) e valores pontuais (preço, taxa a 10 anos). Regista o que falta e o que é incoerente."""
        fin=bruto.get("financials",{}); anos=sorted(fin)[-n_anos:]
        rots={r for a in anos for r in fin[a]}
        mapa={r:_campo(r) for r in rots}                       # 1.º dicionário de sinónimos (nucleo/util.py)
        desc=[r for r,c in mapa.items() if c is None]          # 2.º só o que sobra vai ao modelo
        mapa.update(self._mapear(desc,{r:c for r,c in mapa.items() if c}))
        series={c:{a:None for a in anos} for c in _CAMPOS_SERIE}
        for a in anos:
            for rot,bv in fin[a].items():
                c=mapa.get(rot)
                if c in series:
                    v=_ler(bv)
                    series[c][a]=(abs(v) if c=="capex" else v) if v is not None else None
        inc=[]       # verificações de coerência: valores impossíveis são anulados e ficam registados
        for a in anos:
            rec,rl=series["receita"][a],series["resultado_liquido"][a]
            if rec is not None and rec<=0: inc.append(f"receita/{a}: não positiva"); series["receita"][a]=None
            if rec and rl is not None and abs(rl)>rec: inc.append(f"resultado_liquido/{a}: maior que receita"); series["resultado_liquido"][a]=None
            ac=series["acoes_diluidas"][a]
            if ac is not None and ac<=0: inc.append(f"acoes_diluidas/{a}: não positivo"); series["acoes_diluidas"][a]=None
        pont={"preco_atual":_ler(bruto.get("price")),
              "moat_score":_moat(bruto.get("moat")),"pl_medio_historico":_ler(bruto.get("historical_pe")),
              "taxa_10_anos":_ler(bruto.get("us10y"))}
        if ped := bruto.get("_preco_override"): pont["preco_atual"]=ped
        if tax := bruto.get("_taxa_override"): pont["taxa_10_anos"]=tax
        em_falta=[f"{c}/{a}" for c,v in series.items() for a,x in v.items() if x is None and c not in CAMPOS_OPCIONAIS]
        em_falta+=[c for c,v in pont.items() if v is None]
        return {"empresa":{"ticker":bruto.get("ticker"),"nome":bruto.get("name"),
                           "setor":bruto.get("sector"),"moeda":bruto.get("currency"),
                           "fonte":bruto.get("source","dataset sintético"),
                           "sic":bruto.get("sic"),"sic_desc":bruto.get("sic_desc"),"moeda_relatorio":bruto.get("moeda_relatorio"),
                           "cik":bruto.get("cik"),"lei":bruto.get("lei"),"relatorio_url":bruto.get("relatorio_url"),
                           "nota_fonte":bruto.get("nota_fonte"),"outras_fontes":bruto.get("outras_fontes"),
                           "tentativas_fontes":bruto.get("tentativas_fontes")},
                "anos":[int(a) for a in anos],"series":series,"pontuais":pont,
                "em_falta":em_falta,"inconsistencias":inc,
                "mapeados_modelo":{k:v for k,v in mapa.items() if k in desc and v},
                "ignorados":[r for r in rots if mapa.get(r) is None],
                "texto_gestao":bruto.get("management_commentary"),
                "negocio_relatorio":bruto.get("negocio_relatorio"),
                "mercado":bruto.get("_mercado"),"_origem_sec":bruto.get("_origem_sec"),
                "governanca":bruto.get("governanca"),"fim_exercicio":bruto.get("fim_exercicio") or {}}

    def receber(self, m: Msg) -> list[Msg]:
        """Ponto de entrada do agente: recebe o `request` do utilizador e responde com `inform` ao Guardião (ou `failure`)."""
        ped=m.conteudo
        try:
            bruto=self._bruto(ped)
            if ped.get("preco") is not None: bruto["_preco_override"]=ped["preco"]
            if ped.get("taxa")  is not None: bruto["_taxa_override"]=ped["taxa"]
        except Exception as e:
            self.dizer(f"falhou: {e}"); return [m.r("failure","utilizador",{"motivo":str(e)})]
        dados=self.normalizar(bruto, ped["anos"])       # esquema único, seja qual for a fonte
        dados["taxa_alvo_pct"]=round(float(ped.get("taxa_alvo") or TAXA_RENTABILIDADE_ALVO)*100,2)
        if ped.get("fonte")=="sec":     # só a SEC tem fontes de reserva para preencher buracos
            antes=len(dados["em_falta"])
            self.dizer("a completar dados em falta com as fontes de reserva (yfinance, Alpha Vantage)…")
            _completar_dados(dados,ped["ticker"])
            _ajustar_desdobramentos(dados,ped["ticker"])
            _pl_de_dados(ped["ticker"],dados)
            from agentes.guardiao import setor as _setor
            if _setor(dados)[0]=="banco" and (dados["empresa"].get("moeda_relatorio") or "USD")=="USD":
                self.dizer("banco: a recolher CET1, crédito malparado e margem financeira na FDIC…")
                fd=fdic_indicadores(dados["empresa"].get("nome") or ped["ticker"],dados["anos"])
                dados["banco"]=fd
                self.dizer(fd["fonte"] if fd else "FDIC: banco do grupo não encontrado (Portões P3 e P8 ficam sem dados)")
            n_res=sum(1 for v in dados["origem_dados"].values() if v in ("yfinance","Alpha Vantage"))
            resto=len([x for x in dados["em_falta"] if x!="moat_score"])
            self.dizer(f"{max(antes-1,0)} em falta na SEC; {n_res} preenchidos por reserva; {resto} continuam em falta em todas as fontes")
        total=len(_CAMPOS_SERIE)*len(dados["anos"])+len(_CAMPOS_PONT)
        n_falta=len([x for x in dados["em_falta"] if x!="moat_score"])   # o moat é avaliado depois, pelo Avaliador
        info=[f"{total-n_falta} valores, {n_falta} em falta"]
        if dados["mapeados_modelo"]: info.append(f"{len(dados['mapeados_modelo'])} rótulos pelo modelo")
        if dados["inconsistencias"]: info.append(f"{len(dados['inconsistencias'])} inconsistências")
        self.dizer(", ".join(info))
        if self.plat:      # evento para a janela principal mostrar o resultado da recolha em tempo real
            self.plat.emitir("coletor_resultado","coletor",{
                "empresa": dados["empresa"]["nome"],
                "ticker": dados["empresa"]["ticker"],
                "fonte": dados["empresa"]["fonte"],
                "anos": dados["anos"],
                "total_valores": len(_CAMPOS_SERIE)*len(dados["anos"])+len(_CAMPOS_PONT),
                "em_falta": dados["em_falta"],
                "inconsistencias": dados["inconsistencias"],
                "mapeados_modelo": dados["mapeados_modelo"],
                "ignorados": dados["ignorados"],
                "series_resumo": {
                    c: {a: v for a,v in dados["series"].get(c,{}).items() if v is not None}
                    for c in ("receita","resultado_liquido","fco","capex","divida_total","acoes_diluidas")
                },
                "pontuais": dados["pontuais"],
                "mercado": dados.get("mercado"),
                "origem_dados": dados.get("origem_dados") or {},
                "conflitos": dados.get("conflitos_fontes") or [],
                "fontes_reserva": dados.get("fontes_reserva") or {},
                "anos_extraordinarios": _resumo(dados)["anos_extraordinarios"],
            })
        return [m.r("inform","guardiao",{"dados":dados})]
