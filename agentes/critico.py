"""A4 Crítico (Charlie Munger): advogado do diabo do Avaliador.

Regras (Python) e modelo (Munger) procuram contradições entre as respostas qualitativas e os números: Teste da
Franquia que os números desmentem, modelo de negócio incompatível com as margens, evidência que não existe nas fontes.
Uma objeção grave num campo concreto devolve a análise ao Avaliador (reject-proposal), no máximo uma vez.
Pontos mecânicos (Portões sem dados, divergência entre caminhos de preço) ficam registados no relatório.

Para a apresentação: é o exemplo de negociação entre agentes. O Crítico recebe uma proposta (`propose`) do Avaliador e
responde `reject-proposal` ao Avaliador se há uma objeção grave num campo concreto (o Avaliador revê, no máximo uma vez), ou
`inform` ao Decisor. As objeções vêm de duas origens: regras em Python (`_regras`) e o modelo na persona de Charlie Munger
(`_modelo`); as do modelo são descartadas se citarem números que não existem nos dados.
"""
import json
from config import MAX_REVISOES
from nucleo.llm import ErroLLM, _PERSONA_MUNGER
from nucleo.plataforma import Agente, Msg
from nucleo.util import _ao90, _num, _numeros_nao_verificados

_SIS_CR = """Tarefa: revês as respostas qualitativas que Buffett (o Analista) deu a uma empresa segundo o Protocolo v4.27:
modelo de negócio (M1/M2/M3), produto estável (C2), poder de preço (C3), Teste da Franquia (4 perguntas) e círculo de
competência. Procura afirmações que os números ou os textos não sustentam.
Gravidade: "grave" = claramente contrariado pelos dados; "media" = discutível; "baixa" = menor.
Se concordas com um ponto, NÃO o incluas. Usa só os números fornecidos.
Responde APENAS com JSON:
{"objecoes":[{"gravidade":"grave"|"media"|"baixa","campo":"modelo"|"c2"|"c3"|"franquia"|"circulo"|null,"descricao":"<frase>"}]}"""
_SIS_CR = _PERSONA_MUNGER + "\n\n" + _SIS_CR

def _regras(tst, av, aq):
    obs = []; t = {x["id"]: x for x in tst["A"] + tst["B"] + tst["C"]}
    fortes = [i for i in ("A1", "A6", "A7", "A10", "A12") if t.get(i, {}).get("resposta") == "Sim"]
    if t["C4"]["resposta"] == "Não" and len(fortes) >= 4:
        obs.append({"gravidade": "grave", "campo": "franquia", "origem": "regra",
                    "descricao": f"o Teste da Franquia falha, mas os números mostram vantagem durável ({', '.join(fortes)} = Sim): "
                                 "reexaminar as quatro perguntas (o Portão P1 depende delas)"})
    if aq.get("modelo") in ("M1", "M2") and t.get("A1", {}).get("resposta") == "Não":
        obs.append({"gravidade": "grave", "campo": "modelo", "origem": "regra",
                    "descricao": f"modelo {aq['modelo']} com margem bruta mediana de {_num(t['A1']['valor'], 1)}%: incompatível com produto ou serviço exclusivo"})
    if aq.get("c3_citacao_proposta") and not aq.get("c3_evidencia"):
        obs.append({"gravidade": "media", "campo": None, "origem": "regra", "descricao": "a citação de poder de preço não existe nas fontes: C3 = Não"})
    for v in aq.get("verificacao") or []:          # o Avaliador usou números que não vieram dos dados (proposta, secção 7)
        obs.append({"gravidade": "media", "campo": None, "origem": "regra",
                    "descricao": f"o Avaliador justificou com números que não vieram dos dados ({v.split(': ', 1)[-1]}): não contam como prova"})
    sem = [p["id"] for p in tst["portoes"] if not p["passa"] and "sem dados" in p["detalhe"]]
    if sem: obs.append({"gravidade": "media", "campo": None, "origem": "regra", "descricao": f"Portões sem dados para decidir: {', '.join(sem)}"})
    if av.get("divergencia_pct") is not None and av["divergencia_pct"] > 20:
        obs.append({"gravidade": "media", "campo": None, "origem": "regra",
                    "descricao": f"VI e Valor Equity Bond divergem {_num(av['divergencia_pct'], 1)}%: documentar a causa (Secção 8.3)"})
    return obs

class Critico(Agente):
    """Recebe a proposta do Avaliador e procura contradições (regras e Munger). Se houver objeção grave devolve ao Avaliador (reject-proposal); caso contrário segue para o Decisor (inform)."""
    nome = "critico"; rotulo = "[A4 Crítico]"

    def _modelo(self, d, tst, aq, rev):
        """Objeções do modelo (Munger). Só vê os resultados e as respostas do Buffett, não os relatórios. Descarta o que
        não tiver gravidade e descrição válidas ou citar números inexistentes; na revisão uma objeção grave desce a média."""
        if not self.llm: return []
        ctx = {"empresa": d["empresa"].get("nome"),
               "testes": {x["id"]: {"teste": x["nome"], "resposta": x["resposta"], "valor": x["valor"]} for x in tst["A"] + tst["B"]},
               "sinais_de_balanco": [s["descricao"] for s in tst["sinais"] if s["presente"]],
               "respostas_do_buffett": {k: aq.get(k) for k in ("t1", "circulo", "circulo_porque", "modelo", "modelo_porque",
                                                               "dependente_patentes", "c2", "c2_porque", "c3_verificado", "c3_evidencia", "franquia")}}
        try: rsp = self.llm.json(self.nome + ("_r2" if rev else ""), _SIS_CR, json.dumps(ctx, ensure_ascii=False, default=str))
        except ErroLLM as e:
            self.dizer(f"modelo indisponível ({e}); só verificações em Python"); return []
        out = []
        for o in (rsp.get("objecoes") or []):
            if not (isinstance(o, dict) and o.get("descricao") and o.get("gravidade") in ("grave", "media", "baixa")): continue
            nv = _numeros_nao_verificados(str(o["descricao"]), ctx)
            if nv: self.dizer(f"objeção do modelo descartada: cita números que não existem nos dados ({', '.join(nv)})"); continue
            campo = o.get("campo") if o.get("campo") in ("modelo", "c2", "c3", "franquia", "circulo") else None
            out.append({"gravidade": "media" if (rev and o["gravidade"] == "grave") else o["gravidade"], "campo": campo,
                        "descricao": _ao90(str(o["descricao"])), "origem": "modelo"})
        return out

    def receber(self, m: Msg) -> list[Msg]:
        """Avalia a proposta do Avaliador e decide: devolver ao Avaliador (reject-proposal) ou seguir para o Decisor (inform)."""
        c = m.conteudo
        if m.perf == "refuse": return [m.r("inform", "decisor", c)]      # o Avaliador recusou rever: segue como está
        d, tst, av = c["dados"], c["testes"], c["avaliacao"]; aq = d["analise_qualitativa"]; rev = c.get("revisoes", 0)
        obs = _regras(tst, av, aq)
        campos = {o["campo"] for o in obs if o["campo"]}
        obs += [o for o in self._modelo(d, tst, aq, rev) if not o["campo"] or o["campo"] not in campos]
        graves = [o for o in obs if o["gravidade"] == "grave"]
        # só se devolve ao Avaliador se a objeção grave aponta um campo concreto e ainda há revisões disponíveis
        pede = bool([o for o in graves if o.get("campo")]) and rev < MAX_REVISOES
        crit = {"objecoes": obs, "revisoes": rev, "objecoes_iniciais": (c.get("critica") or {}).get("objecoes", obs) if rev else obs}
        if self.plat: self.plat.emitir("critico_resultado", "critico", {"objecoes": obs, "graves": graves, "revisoes": rev, "pediu_revisao": pede})
        if pede:
            alvo = next(o for o in graves if o.get("campo"))
            self.dizer(f"{alvo['descricao']}: devolvo ao Avaliador para rever")
            return [m.r("reject-proposal", "avaliador", {**c, "critica": crit})]
        self.dizer("sem objeções: aceite" if not obs else f"aceite com {len(obs)} objeção(ões), {len(graves)} grave(s)")
        return [m.r("inform", "decisor", {**c, "critica": crit})]
