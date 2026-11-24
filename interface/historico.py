"""Histórico persistente: guarda cada análise completa em saidas/historico."""
import datetime, json
from config import RAIZ
from interface.tema import COR, cor_veredicto


class HistoricoMixin:
    """Histórico persistente: cada análise completa fica guardada em saidas/historico e aparece na lista da janela principal."""

    def _sel_hist(self,_):
        s=self._lhist.curselection()
        if s and s[0]<len(self._hist):
            r=self._hist[s[0]]
            if r.get("_ticker"): self._vt.set(r["_ticker"])
            self._mostrar(r)

    _PASTA_HIST=RAIZ/"saidas"/"historico"

    def _hist_rotulo(self, r):
        op=(r.get("oportunidade") or {}).get("categoria") or ("ERRO" if r.get("performativa")=="failure" else "?")
        q=r.get("_quando","")            # "AAAA-MM-DD hh:mm": hoje mostra a hora, nos outros dias mostra o dia
        if len(q)>=16: q=q[11:16] if q[:10]==datetime.date.today().isoformat() else f"{q[8:10]}/{q[5:7]}"
        return f"{q} {r.get('_ticker',''):<7} {op}"

    def _hist_inserir(self, r):
        self._hist.insert(0,r); self._lhist.insert(0,self._hist_rotulo(r))
        self._lhist.itemconfig(0,fg=cor_veredicto((r.get("oportunidade") or {}).get("categoria") or "ERRO"))
        if len(self._hist)>200: self._hist.pop(); self._lhist.delete(self._lhist.size()-1)

    def _add_hist(self, ticker, r, origem="analise"):
        """Guarda TUDO (relatório, dados, avaliação, mensagens FIPA-ACL e pensamento dos agentes) em disco."""
        r["_ticker"]=r.get("_ticker") or ticker; r["_origem"]=origem
        r.setdefault("_quando",datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        try:
            self._PASTA_HIST.mkdir(parents=True,exist_ok=True)
            nome=f"{r['_quando'].replace(':','').replace(' ','_')}_{r['_ticker']}.json"
            (self._PASTA_HIST/nome).write_text(json.dumps(r,ensure_ascii=False,default=str),encoding="utf-8")
        except Exception as e:
            self._lest.config(text=f"Histórico não guardado em disco: {e}",fg=COR["nao"])
        self._hist_inserir(r)

    def _carregar_historico(self):
        if not self._PASTA_HIST.exists(): return
        for f in sorted(self._PASTA_HIST.glob("*.json"),key=lambda p:p.stat().st_mtime)[-200:]:
            try: self._hist_inserir(json.loads(f.read_text(encoding="utf-8")))
            except Exception: continue
            if self._hist and self._hist[0].get("v424") is not None:      # análise da versão antiga (com a v4.24): não se mostra
                self._hist.pop(0); self._lhist.delete(0)
