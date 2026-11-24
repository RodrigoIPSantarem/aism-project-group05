"""Cliente do modelo de linguagem (Ollama, a correr no computador) e personas Buffett e Munger."""
import hashlib, json, os, re, threading, time, urllib.error, urllib.request
from pathlib import Path
from config import LLM_NUM_CTX, LLM_NUM_PREDICT


class ErroLLM(Exception): pass

def _extrair_json(txt):
    """O modelo às vezes responde com texto à volta do JSON ou dentro de ```: isola o primeiro objeto {...} e converte-o. Sem JSON levanta ValueError (o pedido é repetido)."""
    limpo=re.sub(r"```(?:json)?","",txt).strip()
    i,f=limpo.find("{"),limpo.rfind("}")
    if i==-1 or f<=i: raise ValueError("sem JSON")
    return json.loads(limpo[i:f+1])

def _post_http(url, corpo, hdrs, timeout):
    """POST com corpo JSON ao Ollama. Traduz os erros de rede em ErroLLM com uma mensagem que o utilizador percebe (Ollama desligado, modelo a carregar)."""
    req=urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                headers={"content-type":"application/json",**hdrs}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise ErroLLM(f"{url} → {e.code}: {e.read().decode('utf-8','replace')[:200]}") from e
    except urllib.error.URLError as e:
        raise ErroLLM(f"Sem ligação a {url} ({e.reason}). Ollama está a correr?") from e
    except OSError as e:
        raise ErroLLM(f"Ligação interrompida ({e}). Modelo ainda a carregar?") from e

class LLM:
    """Cliente do modelo (Ollama). Um só pedido de cada vez (a análise e a calibração não competem pela memória),
    o modelo fica carregado entre pedidos e, se o Ollama reiniciar o processo do modelo, espera e tenta de novo."""
    _trinco=threading.Lock()
    ESPERAS=(5,15,30,60)            # segundos entre tentativas quando a ligação falha
    backend="ollama"                # os modelos simulados dos testes têm outro valor; serve para saber se o modelo é real

    def __init__(self, modelo, cache: Path):
        self.modelo, self.cache = modelo, cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.falhas=0
        self.usar_cache=True      # False: pergunta sempre ao modelo (a resposta nova também fica guardada)
        self.metricas=[]          # uma entrada por chamada ao modelo: tokens e segundos a ler, a escrever e a carregar
        self._ult=None

    def _url(self): return os.environ.get("OLLAMA_URL","http://localhost:11434").rstrip("/")

    def _ollama_vivo(self) -> bool:
        """Pergunta ao Ollama quais os modelos que tem; serve para o 'acordar' e saber se está a responder."""
        try:
            with urllib.request.urlopen(self._url()+"/api/tags",timeout=10) as r: return r.status==200
        except Exception: return False

    def _descarregar_modelo(self):
        """Pede ao Ollama para descarregar o modelo (keep_alive 0): o processo do modelo que rebentou é deitado fora e o próximo pedido
        arranca um novo, limpo. Se não for possível, não faz mal: a próxima tentativa segue na mesma."""
        try: _post_http(self._url()+"/api/generate",{"model":self.modelo,"keep_alive":0},{},30)
        except Exception: pass

    def aquecer(self):
        """Carrega o modelo na memória e espera que acabe, ANTES do primeiro pedido real. Um pedido que chega a um modelo ainda a
        arrancar pode levar um erro 500 (o processo do modelo ainda não responde); assim esse pedido só chega com tudo pronto.
        Usa o mesmo contexto dos pedidos reais, para o Ollama não ter de recarregar o modelo."""
        try: _post_http(self._url()+"/api/generate",{"model":self.modelo,"prompt":"","stream":False,"keep_alive":"30m",
                                                     "options":{"num_ctx":LLM_NUM_CTX}},{},300)
        except Exception: pass

    def _chamar(self, sistema, msg):
        """Uma chamada ao Ollama: temperatura 0 (mesma pergunta, mesma resposta) e formato JSON. Guarda tempos e tokens da chamada para as métricas."""
        r=_post_http(self._url()+"/api/chat",{"model":self.modelo,"stream":False,"format":"json","keep_alive":"30m",
                          "options":{"temperature":0,"num_ctx":LLM_NUM_CTX,"num_predict":LLM_NUM_PREDICT},
                          "messages":[{"role":"system","content":sistema},
                                      {"role":"user","content":msg}]},{},600)
        ns=lambda k: (r.get(k) or 0)/1e9
        self._ult={"leu_tokens":r.get("prompt_eval_count") or 0,"leu_s":ns("prompt_eval_duration"),
                   "escreveu_tokens":r.get("eval_count") or 0,"escreveu_s":ns("eval_duration"),
                   "carregar_s":ns("load_duration"),"total_s":ns("total_duration")}
        return r.get("message",{}).get("content","")

    def json(self, agente, sistema, msg, tentativas=5):
        """Pede ao modelo uma resposta JSON. Há cache em disco (agente + modelo + pergunta): a mesma pergunta nunca é feita duas vezes, o que torna as análises repetíveis. Se a ligação falha espera e tenta de novo; se o JSON vem mal formado repete o pedido."""
        ch=hashlib.sha256(f"{self.modelo}|{sistema}|{msg}".encode()).hexdigest()[:24]
        fc=self.cache/f"{agente}_{ch}.json"
        if self.usar_cache and fc.exists(): return json.loads(fc.read_text(encoding="utf-8"))
        pedido,erro=msg,None
        with LLM._trinco:
            for i in range(tentativas):
                try:
                    self._ult=None; t0=time.monotonic()
                    r=_extrair_json(self._chamar(sistema,pedido))
                    self._registar_metricas(agente,i+1,time.monotonic()-t0)
                    fc.write_text(json.dumps(r,ensure_ascii=False,indent=1),encoding="utf-8"); return r
                except ErroLLM as e:
                    erro=e; self.falhas+=1
                    if i<tentativas-1:
                        espera=self.ESPERAS[min(i,len(self.ESPERAS)-1)]
                        linha=f"   [modelo] falha de ligação ao Ollama ({str(e)[:90]}…); nova tentativa em {espera} s (descarrego o modelo para arrancar um processo novo)"
                        try:
                            from nucleo.plataforma import _registar
                            _registar(linha)                   # fica também no registo da sessão (a interface não tem terminal)
                        except Exception: print(linha)
                        self._descarregar_modelo()             # o processo do modelo rebentou: o próximo pedido arranca um novo
                        time.sleep(espera)
                        self._ollama_vivo()   # acorda o servidor antes de repetir
                        self.aquecer()        # e carrega o modelo já, para o pedido seguinte não apanhar um processo a meio do arranque
                except (ValueError,json.JSONDecodeError) as e:
                    erro=e; pedido=msg+"\n\nResponde APENAS com o objeto JSON pedido."
        raise ErroLLM(f"{agente}: falhou após {tentativas} tentativas ({erro})")

    def _registar_metricas(self, agente, tentativa, segundos):
        """Regista no registo da sessão onde foi o tempo da chamada: ler o pedido, escrever a resposta, carregar o modelo."""
        m={"agente":agente,"tentativa":tentativa,"segundos":round(segundos,1),**(self._ult or {})}
        self.metricas.append(m)
        if not self._ult: return
        f=lambda x: f"{x:.1f}".replace(".",",")
        vel=lambda t,s: f"{f(t/s)} tokens/s" if s else "n/d"
        linha=(f"{'LLM':<6} [modelo]        {agente}: leu {m['leu_tokens']} tokens em {f(m['leu_s'])} s ({vel(m['leu_tokens'],m['leu_s'])}) · "
               f"escreveu {m['escreveu_tokens']} tokens em {f(m['escreveu_s'])} s ({vel(m['escreveu_tokens'],m['escreveu_s'])}) · "
               f"carregar {f(m['carregar_s'])} s · total {f(segundos)} s" + (f" · tentativa {tentativa}" if tentativa>1 else ""))
        try:
            from nucleo.plataforma import _registar
            _registar(linha)
        except Exception: print(linha)

    def resumo_velocidade(self) -> str:
        """Velocidade média de escrita das últimas chamadas (o que mais pesa no tempo de uma análise)."""
        ult=[m for m in self.metricas[-6:] if m.get("escreveu_s")]
        if not ult: return ""
        t=sum(m["escreveu_tokens"] for m in ult); s=sum(m["escreveu_s"] for m in ult)
        return f"{t/s:.1f} tokens/s".replace(".",",")

# Princípios resumidos por palavras nossas a partir das cartas aos acionistas da Berkshire Hathaway.
_PERSONA_BUFFETT="""Pensas e decides como Warren Buffett, presidente da Berkshire Hathaway. Aplicas sempre estes princípios:
1. Círculo de competência: só avalias negócios que compreendes; quando não compreendes, dizes que não sabes.
2. Fosso económico: procuras vantagens duradouras (marca, rede, custo de mudança, custo baixo, patente ou licença)
   que protegem margens e retorno sobre o capital durante décadas. Negócios de commodity não têm fosso.
3. Owner Earnings: interessa o dinheiro que o dono pode retirar do negócio, não o lucro contabilístico.
4. Gestão: valorizas quem aloca bem o capital: retorno alto sobre o capital, pouca dívida, recompras sem diluição.
5. Preço: preferes uma empresa extraordinária a um preço justo a uma empresa medíocre a um preço extraordinário,
   mas exiges sempre margem de segurança.
6. O mercado está ao teu serviço, não te orienta: ignoras previsões macro e o humor da bolsa.
7. Primeira regra: não perder dinheiro.
8. Compras como se fosses ficar com o negócio para sempre.
Usas apenas os números e factos fornecidos; nunca inventas dados. Escreves em português europeu, segundo o
Acordo Ortográfico de 1990 (ação, atual, ótimo, setor), de forma simples."""

_PERSONA_MUNGER="""Pensas como Charlie Munger, sócio de Warren Buffett. Usas a inversão: em vez de perguntares porque é que
o investimento vai correr bem, perguntas como pode correr mal e o que tornaria a tese falsa. Desconfias de crescimento
extrapolado, de múltiplos altos e de histórias sem números. És curto e direto. Usas apenas os dados fornecidos.
Escreves em português europeu, segundo o Acordo Ortográfico de 1990."""

def _criar_llm(pasta: Path) -> LLM:
    """O modelo escolhido nas Definições (LLM_MODELO). Criar o cliente não liga ao Ollama: quem precisa verifica antes."""
    return LLM(os.environ.get("LLM_MODELO","qwen2.5:7b"), pasta)