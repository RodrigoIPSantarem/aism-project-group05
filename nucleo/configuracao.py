"""Configuração feita pela interface, sem terminal nem edição de ficheiros à mão.

- .env: criado automaticamente a partir do .env.example na primeira utilização; gravado pela janela Definições.
- Ollama: verificar se está a correr e se o modelo existe; descarregar o modelo pela API (/api/pull), com progresso.
"""
import json, os, shutil, urllib.request
from config import RAIZ

ENV = RAIZ / ".env"
ENV_EXEMPLO = RAIZ / ".env.example"
CHAVES_ENV = ("LLM_MODELO", "OLLAMA_URL", "SEC_USER_AGENT", "ALPHAVANTAGE_API_KEY")

# ─────────────────────────────── .env
def garantir_env():
    """Primeira utilização: cria o .env a partir do .env.example (com o Ollama local por defeito)."""
    if not ENV.exists() and ENV_EXEMPLO.exists(): shutil.copyfile(ENV_EXEMPLO, ENV)

def ler_env() -> dict:
    """Lê o .env como dicionário (as chaves que o utilizador definiu nas Definições)."""
    out = {}
    if ENV.exists():
        for l in ENV.read_text(encoding="utf-8").splitlines():
            l = l.strip()
            if l and not l.startswith("#") and "=" in l:
                k, v = l.split("=", 1); out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def gravar_env(valores: dict):
    """Atualiza as chaves no .env mantendo os comentários, e aplica-as já ao processo (sem reiniciar)."""
    garantir_env()
    linhas = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    feitas = set()
    for i, l in enumerate(linhas):
        k = l.split("=", 1)[0].strip()
        if "=" in l and not l.strip().startswith("#") and k in valores:
            linhas[i] = f"{k}={valores[k]}"; feitas.add(k)
    for k, v in valores.items():
        if k not in feitas: linhas.append(f"{k}={v}")
    ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    for k, v in valores.items(): os.environ[k] = str(v)

# ─────────────────────────────── Ollama
def url_ollama() -> str: return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")

def modelos_ollama() -> list[str] | None:
    """Modelos instalados no Ollama; None se o Ollama não estiver a correr."""
    try:
        with urllib.request.urlopen(url_ollama() + "/api/tags", timeout=8) as r:
            return [m.get("name", "") for m in json.loads(r.read().decode()).get("models", [])]
    except Exception:
        return None

def tem_modelo(modelo: str, instalados: list[str]) -> bool:
    base = modelo if ":" in modelo else modelo + ":latest"
    return modelo in instalados or base in instalados

def descarregar_modelo(modelo: str, progresso=None) -> tuple[bool, str]:
    """Descarrega o modelo pela API do Ollama. progresso(texto, fração 0-1 ou None) é chamado durante a descarga."""
    req = urllib.request.Request(url_ollama() + "/api/pull", data=json.dumps({"name": modelo, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            for linha in r:
                if not linha.strip(): continue
                ev = json.loads(linha.decode())
                if ev.get("error"): return False, ev["error"]
                tot, feito = ev.get("total"), ev.get("completed")
                if progresso:
                    if tot and feito:
                        gb = lambda x: f"{x / 1e9:.1f}".replace(".", ",")
                        progresso(f"A descarregar {modelo}: {gb(feito)} de {gb(tot)} GB ({100 * feito / tot:.0f}%)", feito / tot)
                    else: progresso(f"{modelo}: {ev.get('status', '')}", None)
                if ev.get("status") == "success": return True, "modelo descarregado"
        return True, "concluído"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────── Ollama: onde corre o modelo e afinação sem terminal
