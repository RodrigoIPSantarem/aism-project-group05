"""Parte qualitativa do A3 Avaliador: as perguntas de julgamento do Protocolo v4.27, respondidas com o modelo de linguagem.

- Triagem, pergunta 1: percebo o produto e porque é que o cliente o compra?
- Passo -1, Círculo de Competência: prevejo o negócio a 10 anos? Teste Wrigley; patentes (> 50% da receita com patente
  a expirar em menos de 10 anos -> rejeitar); tecnologia (o que conta é porque o cliente volta).
- Passo 1: modelo M1/M2/M3; Regra de Commodity (c): serviço que depende de talentos individuais; dependência de patentes.
- Bloco C: C2 (produto estável), C3 (poder de preço, com citação verificada) e C4 (Teste da Franquia, 4 perguntas).

O modelo propõe; as regras verificam: uma citação usada como evidência tem de existir nas fontes, palavra por palavra.

Para a apresentação: na proposta, o Avaliador é "modelo de linguagem + cálculo em Python". Este ficheiro é a parte do modelo
(Ollama, local); agentes/avaliador.py junta-lhe a parte de cálculo. Os cuidados contra "alucinações":
1) o modelo só vê textos reais (relatório anual 10-K, perfil, Wikipedia) e factos calculados; 2) a evidência de poder de
preço (C3) tem de ser uma frase que exista nas fontes (`citacao_verificada`); 3) números que o modelo cite e que não estejam
nos dados são assinalados (`_numeros_nao_verificados`); 4) se a 1.ª leitura diz "não" a T1, Círculo ou Wrigley, há uma
2.ª leitura com outra formulação, e se discordam a decisão fica para o utilizador (`_segunda_leitura`).
"""
import json, os, re, statistics
from config import AN_CHARS_ITEM1, AN_CHARS_PERFIL, AN_CHARS_PRECOS, FRANQUIA_PERGUNTAS, NAO_, PARCIAL, SIM
from fontes.qualitativas import eh_repasse_custos, _rss_noticias, _sec_evidencia_preco, _sec_item1, _wiki_resumo
from nucleo.llm import ErroLLM
from nucleo.metricas import _anos, _evidencia_fosso, _resumo
from nucleo.util import _ao90, _numeros_nao_verificados

_PERSONA_AN = """Pensas como um analista do método de Warren Buffett: procuras negócios simples, com marcas ou serviços que os
clientes voltam a comprar, margens e retornos altos durante anos, pouca dívida e uma gestão que pensa como dona.
Usas apenas os textos e factos fornecidos; nunca inventas dados. Quando os textos descrevem o negócio, respondes com
base neles, mesmo que a empresa tenha vários segmentos ou várias marcas. Escreves em português europeu, segundo o
Acordo Ortográfico de 1990 (ação, atual, ótimo, setor), de forma simples."""

_SIS_AN = _PERSONA_AN + """

Tarefa: respondes às perguntas qualitativas do Protocolo v4.27 (Método Buffett) sobre esta empresa. Em cada pergunta
escreve primeiro a justificação ("porque") e só depois a resposta.

TRIAGEM 1: "O produto ou serviço da empresa e a razão de o cliente o comprar percebem-se a partir dos textos?"
  Não é uma pergunta sobre o futuro nem sobre a tua confiança. Escreve em "produto" o que a empresa vende e em
  "cliente_volta_porque" a razão de o cliente comprar. Responde "sim" sempre que os textos o permitam, mesmo que o
  negócio seja complexo, técnico ou tenha vários segmentos. Responde "nao" só se os textos não deixarem perceber
  o que a empresa vende (por exemplo, uma holding sem atividade descrita).
CÍRCULO DE COMPETÊNCIA: "Consigo prever razoavelmente como este negócio vai gerar dinheiro daqui a 10 anos?"
  Tecnologia: o que conta é porque o cliente volta (Buffett comprou a Apple como produto de consumo com clientes
  fiéis); só é "nao" se a tese exigir prever uma tecnologia, regulação ou ciclo que muda sem aviso.
  patentes_mais_de_metade: true só se mais de 50% da receita depende de produtos com patente a expirar em menos de 10 anos.
TESTE WRIGLEY (campo "wrigley", com a sua própria justificação): "O produto essencial que vende hoje será, com elevada
  probabilidade, reconhecível daqui a 15 anos?" "sim" para marcas e produtos estáveis (bebidas, higiene, ferramentas,
  serviços recorrentes); "nao" só com uma razão concreta (moda, tecnologia que se renova a cada poucos anos, patente que expira).
MODELO: "M1" produto exclusivo (Coca-Cola, Wrigley, Hershey, P&G); "M2" serviço exclusivo prestado por uma instituição
  (Moody's, American Express); "M3" baixo custo (Costco, Walmart); "hibrido" se for misto ou parcial.
  servico_de_talentos: true se o serviço depende de talentos individuais que levam os clientes quando saem.
  dependente_patentes: true se a vantagem depende de patentes com prazo.
C2 Produto estável e "à prova de idiota": "sim" = mesmo produto há 10+ anos, previsível a 15, sobreviveria a má gestão;
  "parcial" = muda gradualmente; "nao" = reinvenção constante, patentes ou gestão excecional.
C3 Poder de preço: "sim" = evidência CONCRETA e DATADA de subida de preços sem perda relevante de volume; "parcial" =
  evidência parcial; "nao" = sem evidência. Se houver a lista "FRASES SOBRE PREÇOS", escolhe em "frase" o NÚMERO da
  melhor frase (ou null); se não houver lista, em "evidencia" COPIA EXATAMENTE uma frase dos textos, sem alterar palavras.
C4 Teste da Franquia (carta de 1991), sim ou nao em cada uma:
  f1 o produto ou serviço é necessário ou desejado?  f2 o cliente considera que não tem substituto próximo?
  f3 o preço não é regulado?  f4 um concorrente com capital ilimitado continuaria sem conseguir tirar-lhe os clientes?
B4: se um texto mostrar a gestão a admitir um erro publicamente, copia essa frase em "b4_evidencia"; senão null.
Concorrência, promoções e descontos são normais em marcas e não fazem de um produto uma commodity.
Responde APENAS com JSON:
{"t1":{"produto":"<frase>","cliente_volta_porque":"<frase>","resposta":"sim"|"nao"},
"circulo":{"porque":"<frase>","resposta":"sim"|"nao","patentes_mais_de_metade":false},
"wrigley":{"porque":"<frase>","resposta":"sim"|"nao"},
"modelo":"M1"|"M2"|"M3"|"hibrido","modelo_porque":"<frase>","servico_de_talentos":false,"dependente_patentes":false,
"c2":{"porque":"<frase>","resposta":"sim"|"parcial"|"nao"},
"c3":{"porque":"<frase>","frase":<número ou null>,"evidencia":"<frase copiada ou null>","resposta":"sim"|"parcial"|"nao"},
"franquia":{"f1":{"porque":"<frase>","resposta":"sim"|"nao"},"f2":{...},"f3":{...},"f4":{...}},
"b4_evidencia":null}"""
_SIS_AN_REV = _SIS_AN + """

O Crítico (Charlie Munger) contestou partes da tua análise. Reexamina SÓ os pontos contestados, com os mesmos textos
e factos, e devolve o JSON completo, acrescentando "alteracoes":["<o que mudou e porquê>"]."""

# Segunda leitura: outra formulação, curta e sem tom de rejeição, só quando a primeira disse "não" a T1, Círculo ou Wrigley.
_SIS_AN2 = _PERSONA_AN + """

Tarefa: segunda leitura de três perguntas sobre esta empresa, com uma formulação diferente. Verificas uma conclusão
anterior; não procures razões para rejeitar a empresa nem para a aceitar: responde ao que os textos mostram.
1. produto: o que vende a empresa e a quem? Descreve numa frase. "descreve": true se os textos o permitem.
2. cliente_volta: existe um motivo concreto para o cliente voltar a comprar (marca, hábito, necessidade, custo de
   mudança, rede)? "sim" ou "nao".
3. mesmo_em_15_anos: o produto essencial que a empresa vende hoje ainda será reconhecível daqui a 15 anos?
   "sim" se o negócio é estável; "nao" só com uma razão concreta (moda, tecnologia que se renova a cada poucos
   anos, patente que expira); "incerto" se os textos não chegam.
Responde APENAS com JSON:
{"produto":"<frase>","descreve":true|false,"cliente_volta":{"porque":"<frase>","resposta":"sim"|"nao"},
"mesmo_em_15_anos":{"porque":"<frase>","resposta":"sim"|"nao"|"incerto"}}"""

def _normalizar(t: str) -> str:
    t = (t or "").lower().replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[^\w%$.,' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def citacao_verificada(cit, fontes_txt: str) -> bool:
    """A citação do modelo existe mesmo nas fontes? Compara sem maiúsculas nem pontuação e exige pelo menos 25 caracteres:
    é a defesa principal contra evidência inventada."""
    if not cit or str(cit).strip().lower() in ("null", "none", ""): return False
    c = _normalizar(str(cit)).strip(" .,")
    return len(c) >= 25 and c[:160] in _normalizar(fontes_txt)

def _sn(x, tres=False):
    x = str(x or "").lower()
    if tres and x.startswith("p"): return PARCIAL
    return SIM if x.startswith("s") else NAO_

def _min(x):
    """"Sim"/"Não"/"Parcial" guardados -> "sim"/"nao"/"parcial" do esquema que o modelo devolve."""
    return {"sim": "sim", "não": "nao", "nao": "nao", "parcial": "parcial"}.get(str(x or "").strip().lower(), "nao")

def _como_resposta(a):
    """A análise guardada no mesmo formato JSON que o modelo devolve (usado ao pedir a revisão)."""
    fr = a.get("franquia") or {}
    return {"t1": {"resposta": _min(a.get("t1")), "produto": a.get("t1_produto", ""), "cliente_volta_porque": a.get("t1_cliente", ""),
                   "porque": a.get("t1_porque", "")},
            "circulo": {"resposta": _min(a.get("circulo")), "patentes_mais_de_metade": bool(a.get("patentes_mais_de_metade")),
                        "porque": a.get("circulo_porque", "")},
            "wrigley": {"resposta": _min(a.get("wrigley")), "porque": a.get("wrigley_porque", "")},
            "modelo": a.get("modelo"), "modelo_porque": a.get("modelo_porque", ""),
            "servico_de_talentos": bool(a.get("servico_de_talentos")), "dependente_patentes": bool(a.get("dependente_patentes")),
            "c2": {"resposta": _min(a.get("c2")), "porque": a.get("c2_porque", "")},
            "c3": {"resposta": _min(a.get("c3_modelo")), "evidencia": a.get("c3_citacao_proposta"), "porque": a.get("c3_porque", "")},
            "franquia": {k: {"resposta": (fr.get(k) or {}).get("resposta", "nao"), "porque": (fr.get(k) or {}).get("porque", "")}
                         for k in FRANQUIA_PERGUNTAS},
            "b4_evidencia": a.get("b4_evidencia_verificada")}

def _completar(rsp, base):
    """O modelo às vezes devolve "sim" em vez de {"resposta": "sim", ...}. Aceita as duas formas: um valor solto herda
    o resto do campo da análise anterior; um campo em falta ou ilegível mantém-se como estava."""
    if not isinstance(rsp, dict): return dict(base)
    out = dict(rsp)
    for k in ("t1", "circulo", "c2", "c3"):
        v, b = out.get(k), base.get(k) or {}
        out[k] = v if isinstance(v, dict) else ({**b, "resposta": v} if isinstance(v, str) and v.strip() else dict(b))
    v, b = out.get("wrigley"), base.get("wrigley") or {}
    # esquema antigo: o Teste Wrigley dentro de "circulo"
    if v is None and isinstance(out["circulo"].get("wrigley"), str): v = out["circulo"]["wrigley"]
    out["wrigley"] = v if isinstance(v, dict) else ({**b, "resposta": v} if isinstance(v, str) and v.strip() else dict(b))
    fr, bfr = out.get("franquia"), base.get("franquia") or {}
    fr = fr if isinstance(fr, dict) else {}
    out["franquia"] = {k: (fr[k] if isinstance(fr.get(k), dict) else
                           ({**(bfr.get(k) or {}), "resposta": fr[k]} if isinstance(fr.get(k), str) and fr[k].strip() else dict(bfr.get(k) or {})))
                       for k in FRANQUIA_PERGUNTAS}
    return out

def _distribuidor(d):
    """Distribuição por grosso (SIC 50xx e 51xx) ou indústria "Distribution" no Yahoo."""
    e = (d or {}).get("empresa") or {}; sic = e.get("sic")
    try: sic = int(sic) if sic is not None else None
    except (TypeError, ValueError): sic = None
    return (sic is not None and 5000 <= sic <= 5199) or "distribution" in str(e.get("industria_yf") or "").lower()

def _numerar(texto):
    """As frases de preços ("- frase") passam a "1. frase": o modelo escolhe o número em vez de as copiar."""
    linhas, n, out = (texto or "").splitlines(), 0, []
    for ln in linhas:
        if ln.startswith("- "): n += 1; out.append(f"{n}. {ln[2:]}")
        else: out.append(ln)
    return "\n".join(out) if n else ""

def _frases_numeradas(fontes):
    return {int(m.group(1)): m.group(2).strip() for ln in (fontes.get("Frases sobre preços (relatório anual)") or "").splitlines()
            if (m := re.match(r"(\d+)\. (.+)", ln))}

def _factos(d):
    r = _resumo(d); ev = _evidencia_fosso(d)
    mb = [v for v in r["margem_bruta_anual"].values() if v is not None]
    return {"anos": f"{_anos(d)[0]}-{_anos(d)[-1]}" if _anos(d) else "n/d", "evidencia_quantitativa": ev["factos"] or ["sem dados"],
            "margem_bruta_mediana_pct": round(statistics.median(mb), 1) if mb else None,
            "margem_liquida_mediana_pct": r["margem_liquida_pct"], "roe_mediano_pct": r["roe_pct"],
            "crescimento_receita_pct": r["crescimento_receita_pct"],
            "participacao_dos_gestores_pct": d.get("insiders_pct")}

class AnaliseQualitativa:
    """Mistura (mixin) usada pelo Avaliador: pergunta ao modelo, valida a resposta e decide se uma pergunta eliminatória falha.
    As chamadas ao modelo usam o nome "analista" (cache em disco e modelos simulados das experiências continuam válidos)."""
    _LLM = "analista"

    def _fontes(self, d):
        """Os textos que o modelo pode ler: perfil, secção de negócio do relatório anual (Item 1 do 10-K da SEC),
        frases sobre preços, Wikipedia e notícias (só contexto). Cada texto tem um limite de tamanho (config.py)."""
        e = d["empresa"]; ticker, nome = e.get("ticker", ""), e.get("nome", "")
        sec = "SEC" in str(e.get("fonte", "")); cik = e.get("cik")
        ua = os.environ.get("SEC_USER_AGENT", "Rodrigo Silva 240000762@esg.ipsantarem.pt")
        perfil = ((d.get("resumo_negocio") or "") + "\n" + (d.get("texto_gestao") or "")).strip()
        precos = _sec_evidencia_preco(ticker, ua, cik) if sec else ""
        negocio = _sec_item1(ticker, ua, cik) if sec else (d.get("negocio_relatorio") or "")
        return {"Perfil do negócio": perfil[:AN_CHARS_PERFIL],
                "Negócio (relatório anual)": negocio[:AN_CHARS_ITEM1],
                "Frases sobre preços (relatório anual)": _numerar(precos)[:AN_CHARS_PRECOS],
                "Wikipedia": _wiki_resumo(nome, ticker)[:700], "Notícias recentes (só contexto)": _rss_noticias(ticker, nome)[:500]}

    def _mensagem(self, d, fontes):
        """Monta o pedido ao modelo: identificação da empresa, factos calculados dos relatórios e os textos."""
        b = [f"Empresa: {d['empresa'].get('nome')} ({d['empresa'].get('ticker')}) · setor: {d['empresa'].get('setor') or 'N/A'}",
             "=== FACTOS (calculados dos relatórios) ===\n" + json.dumps(_factos(d), ensure_ascii=False, default=str)]
        return "\n\n".join(b + [f"=== {k.upper()} ===\n{v}" for k, v in fontes.items() if v])

    def _validar(self, rsp, fontes, mensagem, d=None):
        """Verifica e normaliza a resposta do modelo: nada do que ele diz entra sem passar por aqui. Em C3 (poder de preço)
        só vale se a citação existir nas fontes e tiver números; repasse de custos não conta; um distribuidor nunca é M1."""
        txt = "\n".join(v for k, v in fontes.items() if v and not k.startswith("Notícias"))
        rsp = _completar(rsp, {})
        t1, ci, c2, c3, wr = rsp["t1"], rsp["circulo"], rsp["c2"], rsp["c3"], rsp["wrigley"]
        modelo = rsp.get("modelo") if rsp.get("modelo") in ("M1", "M2", "M3", "hibrido") else "hibrido"
        evid = c3.get("evidencia") if c3.get("evidencia") not in (None, "null") else None
        num = c3.get("frase")
        try: num = int(num) if num not in (None, "", "null") else None
        except (TypeError, ValueError): num = None
        cand = _frases_numeradas(fontes)
        if num is not None and num in cand: evid = cand[num]      # a citação é a frase da lista: existe nas fontes por construção
        verif = citacao_verificada(evid, txt); c3m = _sn(c3.get("resposta"), True)
        if verif and eh_repasse_custos(evid):
            c3v, n3 = NAO_, "a frase descreve repasse de aumentos de preço dos fornecedores (repasse de custos), não poder de preço: C3 = Não"
        elif not verif: c3v, n3 = NAO_, ("citação não encontrada nas fontes: C3 = Não" if evid else "sem citação de evidência: C3 = Não")
        elif c3m == SIM and not re.search(r"\d", str(evid)): c3v, n3 = PARCIAL, "evidência sem números nem data: C3 = Parcial"
        elif c3m == NAO_: c3v, n3 = PARCIAL, "citação verificada mas o modelo não a considerou suficiente: C3 = Parcial"
        else: c3v, n3 = c3m, "citação verificada no texto da fonte"
        fr = {}
        for k in FRANQUIA_PERGUNTAS:
            x = rsp["franquia"].get(k) or {}
            fr[k] = {"resposta": "sim" if str(x.get("resposta", "")).lower().startswith("s") else "nao", "porque": _ao90(str(x.get("porque", "")))}
        if _distribuidor(d):
            # Um distribuidor revende produtos de terceiros: não tem produto exclusivo, e o cliente pode comprar a outro distribuidor.
            if modelo == "M1": modelo = "hibrido"; rsp["modelo_porque"] = "distribuidor: revende produtos de terceiros, não tem produto exclusivo (M1 corrigido para híbrido)"
            fr["f2"] = {"resposta": "nao", "porque": "distribuidor: o cliente pode comprar os mesmos produtos a outro distribuidor"}
        b4 = rsp.get("b4_evidencia")
        t1_porque = str(t1.get("porque") or "").strip() or " ".join(
            str(x) for x in (t1.get("produto"), t1.get("cliente_volta_porque")) if x)
        textos = " ".join([t1_porque, str(wr.get("porque", "")), str(ci.get("porque", "")), str(rsp.get("modelo_porque", "")),
                           str(c2.get("porque", "")), str(c3.get("porque", ""))] + [f["porque"] for f in fr.values()])
        verificacoes = []
        nv = _numeros_nao_verificados(textos, mensagem)
        if nv: verificacoes.append("números citados que não estão nos dados: " + ", ".join(nv))
        return {"t1": _sn(t1.get("resposta", "sim")), "t1_porque": _ao90(t1_porque),
                "t1_produto": _ao90(str(t1.get("produto") or "")), "t1_cliente": _ao90(str(t1.get("cliente_volta_porque") or "")),
                "circulo": _sn(ci.get("resposta", "sim")), "wrigley": _sn(wr.get("resposta", "sim")),
                "wrigley_porque": _ao90(str(wr.get("porque", ""))),
                "patentes_mais_de_metade": bool(ci.get("patentes_mais_de_metade")), "circulo_porque": _ao90(str(ci.get("porque", ""))),
                "modelo": modelo, "modelo_porque": _ao90(str(rsp.get("modelo_porque", ""))),
                "servico_de_talentos": bool(rsp.get("servico_de_talentos")), "dependente_patentes": bool(rsp.get("dependente_patentes")),
                "c2": _sn(c2.get("resposta"), True), "c2_porque": _ao90(str(c2.get("porque", ""))),
                "c3_modelo": c3m, "c3_verificado": c3v, "c3_evidencia": evid if verif else None, "c3_citacao_proposta": evid,
                "c3_porque": _ao90(str(c3.get("porque", ""))), "c3_nota": n3, "franquia": fr,
                "b4_evidencia_verificada": b4 if citacao_verificada(b4, txt) else None, "verificacao": verificacoes,
                "alteracoes": [_ao90(str(a)) for a in (rsp.get("alteracoes") or [])]}

    def _segunda_leitura(self, prop, msg):
        """Quando a 1.ª leitura diz "não" a T1, Círculo ou Wrigley, faz uma 2.ª leitura com outra formulação. Se as duas
        discordam, a empresa não é rejeitada: fica com dúvida e vai para REVISÃO MANUAL (decide o utilizador)."""
        nao = [k for k in ("t1", "circulo", "wrigley") if prop.get(k) == NAO_]
        if not nao or not self.llm: return
        try: r2 = self.llm.json(self._LLM + "_2", _SIS_AN2, msg)
        except ErroLLM: return
        if not isinstance(r2, dict): return
        def _r(k):
            v = r2.get(k); v = v.get("resposta") if isinstance(v, dict) else v
            return str(v or "").strip().lower()
        def _p(k):
            v = r2.get(k); return str(v.get("porque", "")) if isinstance(v, dict) else ""
        descreve = r2.get("descreve") in (True, "true", "sim"); volta = _r("cliente_volta").startswith("s"); mesmo = _r("mesmo_em_15_anos").startswith("s")
        duv = []
        if "t1" in nao and descreve and volta:
            duv.append({"campo": "t1", "primeira": prop["t1_porque"], "segunda": f"{r2.get('produto', '')} {_p('cliente_volta')}".strip()})
        if "circulo" in nao and volta and mesmo:
            duv.append({"campo": "circulo", "primeira": prop["circulo_porque"], "segunda": _p("mesmo_em_15_anos") or _p("cliente_volta")})
        if "wrigley" in nao and mesmo:
            duv.append({"campo": "wrigley", "primeira": prop.get("wrigley_porque", ""), "segunda": _p("mesmo_em_15_anos")})
        prop["segunda_leitura"] = {"produto": _ao90(str(r2.get("produto", ""))), "descreve": descreve,
                                   "cliente_volta": _ao90(_p("cliente_volta")), "cliente_volta_resposta": "sim" if volta else "nao",
                                   "mesmo_em_15_anos": _ao90(_p("mesmo_em_15_anos")), "mesmo_em_15_anos_resposta": _r("mesmo_em_15_anos")}
        if duv:
            for x in duv: x["primeira"], x["segunda"] = _ao90(x["primeira"]), _ao90(x["segunda"])
            prop["duvidas"] = duv

    def _propor(self, d, objecoes=None, anterior=None):
        """Uma ronda de análise: chama o modelo (ou, se houver objeções do Crítico, pede-lhe que reexamine só os pontos
        contestados), valida a resposta e, na 1.ª ronda, faz a 2.ª leitura. Se o modelo falha, marca `indisponivel`."""
        fontes = self._fontes(d); msg = self._mensagem(d, fontes); rsp = {}
        if self.llm:
            try:
                if objecoes:
                    base = _como_resposta(anterior)
                    rsp = self.llm.json(self._LLM + "_rev", _SIS_AN_REV, msg + "\n\n=== A TUA ANÁLISE ANTERIOR ===\n"
                                        + json.dumps(base, ensure_ascii=False, default=str)
                                        + "\n\n=== OBJEÇÕES DO CRÍTICO ===\n" + json.dumps(objecoes, ensure_ascii=False))
                    rsp = _completar(rsp, base)
                else: rsp = self.llm.json(self._LLM, _SIS_AN, msg)
            except ErroLLM as e:
                self.dizer(f"modelo indisponível ({e})"); rsp = {"_falhou": True}
        prop = self._validar(rsp, fontes, msg, d)
        if rsp.get("_falhou") or not rsp: prop["indisponivel"] = True
        elif not objecoes: self._segunda_leitura(prop, msg)
        elif anterior and anterior.get("duvidas"):                   # a revisão não deve perder as dúvidas da 1.ª ronda
            prop["segunda_leitura"] = anterior.get("segunda_leitura")
            prop["duvidas"] = [x for x in anterior["duvidas"] if prop.get(x["campo"]) == NAO_]
        prop["fontes_usadas"] = [k for k, v in fontes.items() if v]
        prop["evidencia"] = _evidencia_fosso(d); prop["textos_fontes"] = {k: v[:600] for k, v in fontes.items() if v}
        return prop

    def _emitir(self, prop, revisao=False):
        if self.plat:
            self.plat.emitir("avaliador_qualitativa", "avaliador",
                             {**{k: v for k, v in prop.items() if k != "textos_fontes"}, "revisao": revisao,
                              "textos_fontes": {k: v[:300] for k, v in (prop.get("textos_fontes") or {}).items()}})

    @staticmethod
    def rejeicao(prop, guardiao):
        """Perguntas qualitativas que excluem a empresa (um "não" basta)."""
        if prop.get("indisponivel"): return "Análise qualitativa indisponível (o modelo falhou): repetir a análise"
        duv = {x["campo"] for x in prop.get("duvidas") or []}
        if prop["t1"] == NAO_ and "t1" not in duv: return f"Triagem T1 (não se percebe o produto nem porque o cliente o compra): {prop['t1_porque']}"
        if prop["circulo"] == NAO_ and "circulo" not in duv: return f"Passo -1: fora do Círculo de Competência — {prop['circulo_porque']}"
        if prop["wrigley"] == NAO_ and "wrigley" not in duv: return f"Passo -1: falha no Teste Wrigley — {prop.get('wrigley_porque') or prop['circulo_porque']}"
        if prop["patentes_mais_de_metade"]: return "Passo -1: mais de 50% da receita depende de patentes a expirar em menos de 10 anos"
        if prop["servico_de_talentos"]: return "Passo 1: Regra de Commodity (c) — serviço que depende de talentos individuais"
        if guardiao.get("t5_pendente") and prop["modelo"] != "M3":
            return "Triagem T5: margem bruta abaixo de 20% e o negócio não é de baixo custo (M3)"
        return None
