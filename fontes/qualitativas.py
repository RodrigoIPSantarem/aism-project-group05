"""Contexto qualitativo para a parte qualitativa do Avaliador: Wikipedia, notícias RSS e Item 1 do 10-K."""
import json, re, time, urllib.error, urllib.request
from fontes.sec import _CACHE_SEC, _URL_TICK, _sec_get


def _wiki_resumo(nome_empresa: str, ticker: str) -> str:
    """Resumo da Wikipedia (API gratuita, ilimitada, sem chave).
    Passo 1: pesquisa pelo nome → obtém o título exato.
    Passo 2: vai buscar o resumo com o título encontrado."""
    import urllib.parse
    limpo = re.sub(r"\b(Holdings?|Inc\.?|Corp\.?|Co\.?|Ltd\.?|PLC|S\.?A\.?|N\.?V\.?)\b","",
                   nome_empresa, flags=re.I).strip()
    termos_pesquisa = list(dict.fromkeys(t for t in [limpo, nome_empresa] if t.strip()))
    ua = "AISM-projeto/1.0 (academic project)"

    def _search(termo):
        url = (f"https://en.wikipedia.org/w/api.php?action=opensearch"
               f"&search={urllib.parse.quote(termo)}&limit=3&format=json&namespace=0")
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())[1]  # lista de títulos

    def _summary(titulo):
        """Resumo curto da Wikipédia em formato texto."""
        url = (f"https://en.wikipedia.org/api/rest_v1/page/summary/"
               f"{urllib.parse.quote(titulo.replace(' ','_'))}")
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        return d.get("extract","") if d.get("type")=="standard" else ""

    palavras = set(re.sub(r"[^a-z ]", "", limpo.lower()).split()) - {"the","and","of","for","a"}

    # Termos de pesquisa: vários formatos para aumentar as hipóteses
    termos = []
    for t in termos_pesquisa:
        termos += [t, t+" Inc.", t+" company"]
    termos = list(dict.fromkeys(termos))

    for termo in termos:
        try:
            titulos = _search(termo)
            for titulo in titulos[:3]:
                tl = titulo.lower()
                # Aceitar se partilhar pelo menos uma palavra relevante com o nome
                if any(p in tl for p in palavras if len(p)>3) or ticker.lower() in tl:
                    ext = _summary(titulo)
                    if ext and len(ext) > 80:
                        return ext[:1500]
        except Exception:
            continue
    return ""

def _rss_noticias(ticker: str, nome: str) -> str:
    """Notícias recentes via RSS do Yahoo Finance (gratuito, ilimitado, sem chave)."""
    import xml.etree.ElementTree as ET, urllib.parse
    resultados = []
    feeds = [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
        f"https://news.google.com/rss/search?q={urllib.parse.quote(nome+' stock')}&hl=en&gl=US&ceid=US:en",
    ]
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"AISM-projeto/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                root = ET.fromstring(r.read())
            items = root.findall(".//item")[:6]
            for item in items:
                titulo = (item.findtext("title") or "").strip()
                desc = re.sub(r"<[^>]+>","", item.findtext("description") or "").strip()[:200]
                if titulo:
                    resultados.append(f"• {titulo}: {desc}")
            if resultados: break
        except Exception:
            continue
    return "\n".join(resultados[:6])

def _sec_10k_texto(ticker: str, ua: str, cik: int|None=None) -> tuple[str,str]:
    """Texto limpo do relatório anual mais recente na SEC (10-K, 20-F ou 40-F), em cache 30 dias, e a data do exercício."""
    try:
        import html as _html
        if cik is None:
            tick=_sec_get(_URL_TICK,ua,"company_tickers.json")
            lin=next((l for l in tick.values() if l["ticker"].upper()==ticker.upper()),None)
            if not lin: return "",""
            cik=int(lin["cik_str"])
        subs=_sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",ua,f"subs_{cik}.json")
        rec=subs.get("filings",{}).get("recent",{})
        idx=next((i for i,f in enumerate(rec.get("form",[])) if f in ("10-K","20-F","40-F")),None)
        if idx is None: return "",""
        data=(rec.get("reportDate") or rec["filingDate"])[idx]
        fc=_CACHE_SEC/f"10k_{cik}.txt"
        if fc.exists() and time.time()-fc.stat().st_mtime<30*86400:
            return fc.read_text(encoding="utf-8"),data
        acc=rec["accessionNumber"][idx].replace("-",""); doc=rec["primaryDocument"][idx]
        req=urllib.request.Request(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}",headers={"User-Agent":ua})
        with urllib.request.urlopen(req,timeout=40) as r: html=r.read().decode("utf-8","replace")
        texto=re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>"," ",html)
        texto=re.sub(r"<[^>]+>"," ",texto)
        texto=_html.unescape(texto).replace("\u2019","'").replace("\u201c",'"').replace("\u201d",'"')
        texto=re.sub(r"\s+"," ",texto)
        fc.write_text(texto,encoding="utf-8")
        return texto,data
    except Exception:
        return "",""

_SEP_ITEM = r"[\s.:\-\u2013\u2014\"\u201c\u201d']+"

def extrair_item1(texto: str, limite: int = 3000) -> str:
    """Descrição do negócio: Item 1 do 10-K ou Item 4 ("Information on the Company") do 20-F.

    O Item 1 real tem normalmente 20 mil caracteres ou mais, e o índice do relatório repete os títulos em poucas linhas.
    Por isso procura-se o primeiro título "Item 1 Business" que NÃO é do índice (sem "Item 1A" ou "Item 2" logo a seguir) e
    lê-se o início da secção. Se não houver título, devolve texto vazio: antes devolvia-se o início do ficheiro, que nos
    relatórios com XBRL embutido são etiquetas contabilísticas e deixavam o modelo sem ver os produtos da empresa."""
    for ini, indice in ((r"item" + r"\s*1" + _SEP_ITEM + r"b\s?usiness", r"item\s*1a|item\s*2\b"),
                        (r"item\s*4" + _SEP_ITEM + r"information (?:on|about)", r"item\s*4a|item\s*5\b")):
        for m in re.finditer(ini, texto, re.I):
            seg = texto[m.end():m.end() + limite + 300]
            if re.search(indice, seg[:300], re.I): continue                   # linha do índice
            seg = re.split(r"item\s*1a" + _SEP_ITEM + r"risk|item\s*4a" + _SEP_ITEM + r"unresolved", seg, 1, flags=re.I)[0]
            if len(seg) >= 500: return seg[:limite].strip()
    return ""

def _sec_item1(ticker: str, ua: str, cik: int|None=None) -> str:
    texto,_=_sec_10k_texto(ticker,ua,cik)
    return extrair_item1(texto) if texto else ""

_PADROES_PRECO=re.compile(r"(prisstigninger?|prisforhøjelser?|højere priser|prisjustering(er)?|priseffekt|prismix|pris/mix|higher (net )?pric|price increase|increased pric|pricing (action|increase)|favorable pric|"
                          r"price/mix|price, product|price and mix|net price realization|positive pric|pricing contributed|"
                          r"pricing benefit|pricing of|from pricing|due to pricing|pricing initiatives|net selling price|price effect|"
                          r"price growth|pricing growth|underlying price|price-led|price realisation|price realization|"
                          r"hausses? de prix|augmentations? de(s)? prix|effet prix|aumentos? de(os)? preços|subidas? de(os)? preços|"
                          r"hausses? tarifaires?|augmentations? tarifaires?|politique tarifaire|prix moyens? de vente|"
                          r"inflação (alimentar|do cabaz)|deflação do cabaz|preços médios|"
                          r"efeito preço|subidas? de precios|aumentos? de precios|efecto precio|preiserh[öo]hung|preiseffekt|"
                          r"preissteigerung|aumenti di prezzo|aumento dei prezzi|effetto prezzo|prisstigning|prisforh[øo]jelse|"
                          r"prijsverhoging|prijseffect)",re.I)

def _mdna(texto: str) -> str:
    """Secção Item 7 (MD&A): da ocorrência do título com mais texto até ao "Item 7A. Quantitative" seguinte."""
    melhor=""
    for ini,fim in ((r"item\s*7[\s.:\-]+\W?management",r"item\s*7a[\s.:\-]+quantitative"),
                    (r"item\s*5[\s.:\-]+operating and financial review",r"item\s*6[\s.:\-]+directors")):
        fins=[m.start() for m in re.finditer(fim,texto,re.I)]
        for m in re.finditer(ini,texto,re.I):
            prox=next((f for f in fins if f>m.end()),None)
            trecho=texto[m.end():prox if prox else m.end()+150000]
            if len(trecho)>len(melhor): melhor=trecho
    return melhor

# frases sobre o preço das ações, opções ou dividendos não são evidência de poder de preço
# Frases sobre repassar aumentos de preço dos FORNECEDORES (distribuidores): é repasse de custos, não poder de preço.
_REPASSE_CUSTOS=re.compile(r"\b(vendor|supplier|manufacturer)s?['\u2019]?\s+(price|cost)s?\s+increases?|"
                           r"pass(?:es|ed|ing)?\s+(?:on\s+|along\s+)?(?:the\s+)?(?:industry|vendor|supplier|manufacturer)\s+(?:price|cost)\s+increases?|"
                           r"through\s+(?:our|the)\s+supply\s+chain",re.I)

def eh_repasse_custos(frase) -> bool:
    return bool(frase and _REPASSE_CUSTOS.search(str(frase)))

_EXCLUIR_PRECO=re.compile(r"\b(actions?|options?|aktiekurs|aktieoptioner|udbytte|share price|stock price|dividend|dividende|aç(ão|ões) próprias|cours de bourse|"
                          r"exercise price|strike|warrants?|preço de exercício)\b",re.I)

def _frases_preco(texto: str, cabecalho: str) -> str:
    """Frases sobre preços praticados, com prioridade às que têm números (percentagens, pontos)."""
    frases=[f.strip() for f in re.split(r"(?<=[.;])\s+",texto)]
    cand=[f for f in frases if 40<len(f)<450 and _PADROES_PRECO.search(f) and not _EXCLUIR_PRECO.search(f) and not eh_repasse_custos(f)]
    cand.sort(key=lambda f:(0 if re.search(r"\d+([.,]\d+)?\s*(%|percent|points|p\.p\.|pp)",f) else 1))
    vistas,escolhidas=set(),[]
    for f in cand:
        chave=f[:70].lower()
        if chave in vistas: continue
        vistas.add(chave); escolhidas.append(f)
        if len(escolhidas)>=6: break
    return (f"[{cabecalho}]\n"+"\n".join(f"- {f}" for f in escolhidas)) if escolhidas else ""

def _sec_evidencia_preco(ticker: str, ua: str, cik: int|None=None) -> str:
    """Frases do MD&A (10-K Item 7; 20-F Item 5) sobre preços praticados (teste C3: evidência concreta e datada)."""
    texto,data=_sec_10k_texto(ticker,ua,cik)
    if not texto: return ""
    sec=_mdna(texto)
    if len(sec)<20000: sec=texto          # 20-F em formato de relatório anual: o Item 5 remete para outras páginas
    return _frases_preco(sec,f"relatório anual na SEC, exercício terminado em {data}")
