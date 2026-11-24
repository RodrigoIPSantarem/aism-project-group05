"""Fonte de dados sintética (dataset de testes)."""
import json
from config import RAIZ


def _dataset_embutido() -> list[dict]:
    caminho = RAIZ / "dados" / "empresas_sinteticas.json"
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))["empresas"]
    return []

def _sint_obter(ticker):
    for e in _dataset_embutido():
        if e["ticker"].upper()==ticker.upper():
            return {k:v for k,v in e.items() if not k.startswith("_")}
    raise ValueError(f"'{ticker}' não existe no dataset sintético.")

def _sint_listar(): return _dataset_embutido()
