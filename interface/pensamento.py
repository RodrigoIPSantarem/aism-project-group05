"""Painel 'Pensamento dos Agentes': desenho dos eventos ao vivo e a partir do histórico."""
import queue, sys
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:      # sem interface gráfica: a linha de comandos continua a funcionar
    tk=messagebox=ttk=None
from interface.tema import COR, FMO, fmo
from nucleo.util import _num


class PensamentoMixin:
    """Painel do pensamento dos agentes: mostra em tempo real as mensagens FIPA-ACL e o que cada agente diz."""

    def _mk_txt_pens(self, pai):
        """Painel de pensamento dos agentes: texto ao vivo, com uma cor por agente (tema claro, legível num projetor)."""
        f=tk.Frame(pai,bg=COR["painel"]); f.pack(fill="both",expand=True)
        sc=tk.Scrollbar(f,orient="vertical")
        t=tk.Text(f,bg=COR["painel"],fg=COR["texto"],font=fmo(),relief="flat",padx=14,pady=10,wrap="word",
                  yscrollcommand=sc.set,state="disabled",cursor="arrow",selectbackground="#CFE0F5")
        sc.config(command=t.yview); sc.pack(side="right",fill="y"); t.pack(fill="both",expand=True)
        ags={      # uma cor por agente (azul: usam o modelo; verde: só regras em Python)
            "coletor":   ("#1F5FA8","A1"),
            "guardiao":  ("#1B7A45","A2"),
            "avaliador": ("#6A3FA0","A3"),
            "critico":   ("#B35A00","A4"),
            "decisor":   ("#A0204F","A5"),
        }
        for ag,(cor,_) in ags.items():
            t.tag_config(f"hdr_{ag}",foreground=cor,font=fmo(None,"bold"))
            t.tag_config(f"bod_{ag}",foreground=cor)
        t.tag_config("ts",foreground="#8A94A6")
        t.tag_config("campo",foreground="#4A5568")
        t.tag_config("valor_ok",foreground=COR["ok"])
        t.tag_config("valor_nao",foreground=COR["nao"])
        t.tag_config("valor_cond",foreground=COR["cond"])
        t.tag_config("secao",foreground="#7A8699",font=fmo(FMO[1]-1))
        t.tag_config("fonte_txt",foreground="#55657A",font=fmo(FMO[1]-1))
        t.tag_config("sub",foreground=COR["sub"])
        self._pens_ags=ags
        return t

    def _pens_wr(self, txt, tag=""):
        t=getattr(self,"_alvo_pens",None) or self._txt_pens
        t.config(state="normal")
        if tag: t.insert("end",txt,tag)
        else: t.insert("end",txt)
        t.config(state="disabled")
        t.see("end")

    def _pens_secao(self, agente, ts, titulo):
        cor,label=self._pens_ags.get(agente,("#888","??"))
        self._pens_wr("\n")
        self._pens_wr(f"[{ts}] ",    "ts")
        self._pens_wr(f"[{label}] ", f"hdr_{agente}")
        self._pens_wr(f"{titulo}\n", f"hdr_{agente}")

    def _pens_linha(self, agente, campo, valor, tag_val="", larg=28):
        """Uma linha 'campo  valor'. O campo é alinhado em `larg` colunas mas nunca é cortado, e há sempre um espaço antes do valor."""
        self._pens_wr(f"  {campo:<{larg}} ", "campo")
        self._pens_wr(f"{valor}\n", tag_val if tag_val else f"bod_{agente}")

    def _desenhar_ev(self, ev):
        if ev[0]=="log":
            _,txt,ts=ev
            ag=""; rotulos={"[A1":"coletor","[A2":"guardiao","[A3":"avaliador","[A4":"critico","[A5":"decisor"}
            for pref,nome in rotulos.items():
                if txt.strip().startswith(pref): ag=nome; break
            self._pens_wr(f"[{ts}] ","ts")
            self._pens_wr(f"{txt.strip()}\n", f"hdr_{ag}" if ag else "")
        elif ev[0]=="evento":
            _,tipo,agente,dados,ts=ev
            try: self._renderizar_evento(tipo,agente,dados,ts)
            except Exception as e: self._pens_wr(f"  (evento {tipo} não apresentado: {e})\n","sub")

    def _poll_agentes(self):
        """Lê eventos da fila de agentes e escreve no painel de pensamento em tempo real."""
        try:
            while True: self._desenhar_ev(self._fila_agentes.get_nowait())
        except queue.Empty:
            pass
        self.after(100,self._poll_agentes)

    def _repor_pensamento(self, r):
        """Volta a desenhar o pensamento dos agentes guardado com o resultado (histórico)."""
        while not self._fila_agentes.empty():
            try: self._fila_agentes.get_nowait()
            except queue.Empty: break
        t=self._txt_pens; t.config(state="normal"); t.delete("1.0","end"); t.config(state="disabled")
        evs=r.get("_eventos") or []
        if not evs: self._pens_wr("Sem registo do pensamento dos agentes para esta análise.\n","sub")
        for ev in evs: self._desenhar_ev(ev)
        t.see("1.0")

    def _renderizar_evento(self, tipo, agente, dados, ts):
        """Renderiza um evento estruturado no painel de pensamento."""
        if tipo=="coletor_resultado":
            self._pens_secao(agente,ts,f"Dados recolhidos — {dados['empresa']} ({dados['ticker']})")
            self._pens_linha(agente,"Fonte",dados.get("fonte",""))
            self._pens_linha(agente,"Anos analisados",str(dados.get("anos",[])))
            em=[x for x in dados.get("em_falta",[]) if x!="moat_score"]   # o moat é avaliado pelo Avaliador a seguir
            self._pens_linha(agente,"Em falta (todas as fontes)",f"{len(em)} campo(s)" if em else "nenhum",
                             "valor_cond" if em else "valor_ok")
            if em: self._pens_linha(agente,"  Campos em falta",", ".join(em[:8])+("…" if len(em)>8 else ""))
            inc=dados.get("inconsistencias",[])
            if inc:
                self._pens_linha(agente,"Inconsistências",str(len(inc)),"valor_nao")
                for x in inc: self._pens_linha(agente,"  →",x,"valor_nao")
            m=dados.get("mapeados_modelo",{})
            if m: self._pens_linha(agente,"Mapeados pelo modelo","; ".join(f"{k}→{v}" for k,v in m.items()))
            # Série de dados principais
            sr=dados.get("series_resumo",{})
            if sr:
                self._pens_wr("  --- Dados financeiros ---\n","secao")
                for campo,vals in sr.items():
                    if vals:
                        anos_vals=" | ".join(f"{a}: {_num(v,0)}" for a,v in sorted(vals.items())[-3:])
                        self._pens_linha(agente,f"  {campo}",anos_vals)
            org=dados.get("origem_dados") or {}
            if org or dados.get("fontes_reserva"):
                self._pens_wr("  --- Fontes de reserva ---\n","secao")
                por={}
                for k,f in org.items(): por.setdefault(f,[]).append(k)
                for f,ks in por.items(): self._pens_linha(agente,f"  {f}",f"{len(ks)}: {', '.join(sorted(ks)[:6])}{' …' if len(ks)>6 else ''}","valor_cond")
                for fnt,est in (dados.get("fontes_reserva") or {}).items():
                    self._pens_linha(agente,f"  {fnt}",est,"valor_ok" if est=="ok" else "valor_cond")
            for c in dados.get("conflitos") or []: self._pens_linha(agente,"  Conflito entre fontes",c,"valor_nao")
            ext=dados.get("anos_extraordinarios") or {}
            for tipo_e,vals in ext.items():
                for a,v in (vals or {}).items(): self._pens_linha(agente,f"  Ano extraordinário ({tipo_e})",f"{a}: {_num(v)} — excluído dos lucros normalizados","valor_cond")
            mk=dados.get("mercado") or {}
            if mk:
                self._pens_wr("  --- Mercado (automático) ---\n","secao")
                self._pens_linha(agente,"  Preço",f"{_num(mk.get('preco'))} {mk.get('moeda') or ''} · {mk.get('fonte_preco','')} {mk.get('data_preco') or ''}")
                self._pens_linha(agente,"  Tesouro 10 anos",f"{_num(mk.get('taxa_10a'),2)}% · {mk.get('fonte_taxa','')}")
                pla=mk.get("pl_por_ano") or {}
                if pla: self._pens_linha(agente,"  P/L por ano"," | ".join(f"{a}: {_num(v,1)}" for a,v in sorted(pla.items())))
                self._pens_linha(agente,"  P/L médio histórico",_num(mk.get("pl_medio"),1))
            pt=dados.get("pontuais",{})
            if pt:
                self._pens_wr("  --- Dados pontuais ---\n","secao")
                for k,v in pt.items():
                    if v is not None: self._pens_linha(agente,f"  {k}",str(v))

        elif tipo=="guardiao_resultado":
            aprov=dados.get("aprovada")
            self._pens_secao(agente,ts,"Triagem Rápida, Setor e Regra de Commodity — "+("APROVADA" if aprov else "REJEITADA"))
            self._pens_linha(agente,"Setor (Passo 0)",f"{dados.get('setor','-')} · {dados.get('origem_setor','')}",
                             "valor_nao" if dados.get("setor")=="fora_metodo" else "")
            for q in dados.get("triagem",[])+dados.get("base",[]):
                r_=q["resposta"]; tag="valor_ok" if r_=="sim" else ("valor_nao" if r_ in ("não","sem dados") else "valor_cond")
                self._pens_linha(agente,f"  {q['id']} [{r_}]",q.get("detalhe",""),tag)
            for x in dados.get("dados_insuficientes",[]): self._pens_linha(agente,"  DADOS",x,"valor_nao")

        elif tipo=="avaliador_qualitativa":
            self._pens_secao(agente,ts,("Revisão pedida pelo Crítico — " if dados.get("revisao") else "")
                             +"Parte qualitativa (modelo): T1, Círculo de Competência, modelo de negócio e Teste da Franquia")
            self._pens_linha(agente,"Fontes lidas",", ".join(dados.get("fontes_usadas",[])) or "nenhuma")
            cor=lambda x:"valor_ok" if x=="Sim" else ("valor_cond" if x=="Parcial" else "valor_nao")
            self._pens_linha(agente,"T1 percebo o produto?",dados.get("t1","-"),cor(dados.get("t1")))
            if dados.get("t1_porque"): self._pens_wr(f"  {dados['t1_porque']}\n","fonte_txt")
            self._pens_linha(agente,"Círculo de Competência",dados.get("circulo","-"),cor(dados.get("circulo")))
            self._pens_linha(agente,"Teste Wrigley",dados.get("wrigley","-"),cor(dados.get("wrigley")))
            if dados.get("circulo_porque"): self._pens_wr(f"  {dados['circulo_porque']}\n","fonte_txt")
            self._pens_linha(agente,"Modelo de negócio",f"{dados.get('modelo')} — {dados.get('modelo_porque','')}")
            self._pens_linha(agente,"Patentes / talentos",("dependente de patentes" if dados.get("dependente_patentes") else "sem dependência de patentes")
                             +(" · serviço de talentos individuais" if dados.get("servico_de_talentos") else ""))
            self._pens_linha(agente,"C2 produto estável",f"{dados.get('c2')} — {dados.get('c2_porque','')}",cor(dados.get("c2")))
            self._pens_linha(agente,"C3 poder de preço",f"{dados.get('c3_verificado')} (proposto {dados.get('c3_modelo')}) — {dados.get('c3_nota','')}",
                             cor(dados.get("c3_verificado")))
            if dados.get("c3_citacao_proposta"): self._pens_wr(f"  Citação: \"{str(dados['c3_citacao_proposta'])[:300]}\"\n","fonte_txt")
            for k,f_ in (dados.get("franquia") or {}).items():
                self._pens_linha(agente,f"  Franquia {k}",f"{f_['resposta']} — {f_['porque']}","valor_ok" if f_["resposta"]=="sim" else "valor_nao")
            ev=dados.get("evidencia") or {}
            if ev.get("factos"): self._pens_linha(agente,"Evidência numérica",f"{ev.get('nivel')} — {'; '.join(ev['factos'])}")
            for a in dados.get("alteracoes") or []: self._pens_linha(agente,"  Alteração",a,"valor_cond")
            for v in dados.get("verificacao") or []: self._pens_linha(agente,"  Verificação",v,"valor_cond")
            for nome,txt in (dados.get("textos_fontes") or {}).items():
                self._pens_wr(f"  --- {nome} ---\n","secao"); self._pens_wr(f"  {txt[:260]}…\n","fonte_txt")

        elif tipo=="avaliador_proposta":
            tst,av,cond=dados.get("testes") or {},dados.get("avaliacao") or {},dados.get("condicoes") or []
            self._pens_secao(agente,ts,("Recálculo após revisão — " if dados.get("revisao") else "")+"Parte de cálculo (Python): testes, 10 Portões e preço")
            cor={"Sim":"valor_ok","Parcial":"valor_cond","Não":"valor_nao"}
            larg=min(max([len(f"  {t['id']} {t['nome']}") for c_ in ("A","B","C") for t in tst.get(c_,[])] or [28]),52)   # coluna dos nomes: larga o bastante para não os cortar
            for chave in ("A","B","C"):
                for t in tst.get(chave,[]):
                    v=t["valor"]; vs=_num(v,2) if isinstance(v,(int,float)) and v!=float("inf") else ("" if v is None else str(v))
                    self._pens_linha(agente,f"  {t['id']} {t['nome']}",f"{t['resposta']}  {vs[:300]}",cor.get(t["resposta"],"secao"),larg)
            pres=[x for x in tst.get("sinais",[]) if x["presente"] and not x.get("explicado")]
            self._pens_linha(agente,"Sinais de Balanço por explicar",", ".join(f"{x['id']} {x['descricao'][:40]}" for x in pres) or "nenhum",
                             "valor_cond" if pres else "valor_ok")
            self._pens_wr("  --- os 10 Portões ---\n","secao")
            for p_ in tst.get("portoes",[]):
                self._pens_linha(agente,f"  {p_['id']} {'PASSA' if p_['passa'] else 'FALHA'}",f"{p_['pergunta']} · {p_['detalhe']}",
                                 "valor_ok" if p_["passa"] else "valor_nao")
            self._pens_wr("  --- Secção 8: preço ---\n","secao")
            gc=av.get("g_candidatos") or {}
            self._pens_linha(agente,"  g (constante 10 anos)",f"{_num(av.get('g'),2)}%  ("+"; ".join(f"{k.split(')')[0]+')'} {_num(v,1) if v is not None else 'inválido'}" for k,v in gc.items())+")")
            self._pens_linha(agente,"  Owner Earnings/ação",f"{_num(av.get('oe0'),3)} -> VI {_num(av.get('vi'))}")
            self._pens_linha(agente,"  Rendimento inicial",f"{_num(av.get('rend_inicial'),2)}% vs Estado {_num(av.get('taxa10'),2)}% -> Valor-Obrigação {_num(av.get('valor_obrigacao'))}")
            for k,mm in (av.get("metodos") or {}).items():
                self._pens_linha(agente,f"  TACE método {k}",f"{_num(mm['tace'],2)}% (preço daqui a 10 anos {_num(mm['preco10'])})")
            self._pens_linha(agente,"  PMC = mínimo",f"{_num(av.get('pmc'))} (limitado por {av.get('pmc_limitante')})","valor_ok")
            for c_ in cond: self._pens_linha(agente,f"  {c_['id'][:2]}",("sim — " if c_["ok"] else "NÃO — ")+c_["detalhe"],"valor_ok" if c_["ok"] else "valor_nao")

        elif tipo=="critico_resultado":
            obs=dados.get("objecoes",[]); graves=dados.get("graves",[])
            self._pens_secao(agente,ts,f"Munger revê a análise — {len(obs)} objeção(ões), {len(graves)} grave(s)")
            if not obs: self._pens_linha(agente,"Resultado","sem objeções","valor_ok")
            for o in obs:
                grav=o.get("gravidade",""); tag="valor_nao" if grav=="grave" else ("valor_cond" if grav=="media" else "bod_critico")
                self._pens_linha(agente,f"  [{grav.upper()}] {o.get('campo') or ''}",f"{o.get('descricao','')} ({o.get('origem','')})",tag)
            if dados.get("pediu_revisao"): self._pens_wr("  -> devolve ao Avaliador para rever (reject-proposal)\n","valor_nao")

        elif tipo=="decisor_veredicto":
            ver=dados.get("veredicto") or {}
            tag={"ok":"valor_ok","cond":"valor_cond","nao":"valor_nao"}.get(ver.get("cor"),"")
            self._pens_secao(agente,ts,"Passo 8 — veredicto")
            self._pens_linha(agente,"VEREDICTO",ver.get("categoria",""),tag)
            self._pens_wr(f"  {ver.get('descricao','')}\n","fonte_txt")
            if ver.get("limite"): self._pens_linha(agente,"Limite no momento da compra",ver["limite"])