"""Busca produtos da Shopee, gera o site (pasta docs/) e posta no Pinterest.
Uso:  python atualizar.py          (usa a API de verdade)
      python atualizar.py --demo   (usa produtos de exemplo, para testar o visual)
"""
import hashlib, html, json, math, os, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
API = "https://open-api.affiliate.shopee.com.br/graphql"


def carregar_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    for chave in ["shopee_app_id", "shopee_secret", "pinterest_token", "pinterest_board_id"]:
        if os.environ.get(chave.upper()):
            cfg[chave] = os.environ[chave.upper()]
    return cfg


def consultar(cfg, query):
    corpo = json.dumps({"query": query}, separators=(",", ":"))
    ts = str(int(time.time()))
    assinatura = hashlib.sha256((cfg["shopee_app_id"] + ts + corpo + cfg["shopee_secret"]).encode()).hexdigest()
    req = urllib.request.Request(
        API, data=corpo.encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"SHA256 Credential={cfg['shopee_app_id']}, Timestamp={ts}, Signature={assinatura}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        dados = json.loads(r.read().decode())
    if dados.get("errors"):
        raise RuntimeError(f"Erro da API Shopee: {dados['errors']}")
    return dados["data"]


def numero(v, padrao=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def buscar_produtos(cfg):
    # sortType: 5 = maior comissão, 2 = mais vendidos
    vistos = {}
    for ordem in (5, 2):
        for pagina in (1, 2):
            q = ("query { productOfferV2(sortType: %d, limit: 50, page: %d) { nodes { itemId productName "
                 "commissionRate priceMin imageUrl offerLink sales ratingStar shopName } } }" % (ordem, pagina))
            for p in consultar(cfg, q)["productOfferV2"]["nodes"]:
                vistos[p["itemId"]] = p
    return filtrar(list(vistos.values()), cfg)


def filtrar(produtos, cfg):
    bons = []
    for p in produtos:
        if not p.get("offerLink") or not p.get("imageUrl"):
            continue
        if numero(p.get("sales")) < cfg["vendas_minimas"] or numero(p.get("ratingStar")) < cfg["nota_minima"]:
            continue
        # pontuação: ganho estimado por venda, com bônus por popularidade
        ganho = numero(p.get("commissionRate")) * numero(p.get("priceMin"))
        p["_score"] = ganho * (1 + math.log10(1 + numero(p.get("sales"))))
        bons.append(p)
    bons.sort(key=lambda p: p["_score"], reverse=True)
    return bons[: cfg["quantidade_produtos"]]


def produtos_demo():
    nomes = ["Fone Bluetooth sem fio", "Garrafa térmica 1L", "Luminária LED de mesa", "Organizador de gaveta",
             "Mini liquidificador portátil", "Carregador turbo 20W", "Mochila impermeável", "Ventilador de bolso"]
    return [{"itemId": str(i), "productName": n, "commissionRate": "0.12", "priceMin": str(19.9 + i * 12),
             "imageUrl": "", "offerLink": "https://shopee.com.br/", "sales": str(500 + i * 130),
             "ratingStar": "4.8", "shopName": "Loja Exemplo"} for i, n in enumerate(nomes)]


def reais(v):
    return "R$ " + f"{numero(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def vendas(v):
    n = int(numero(v))
    return f"{n/1000:.1f} mil".replace(".", ",") if n >= 1000 else str(n)


def cartao(p):
    nome = html.escape(p["productName"])
    img = (f'<img src="{html.escape(p["imageUrl"])}" alt="{nome}" loading="lazy">'
           if p.get("imageUrl") else '<div class="sem-foto"></div>')
    return f'''<a class="item" href="{html.escape(p["offerLink"])}" target="_blank" rel="sponsored noopener" data-nome="{nome.lower()}">
<div class="foto">{img}</div>
<div class="info"><h3>{nome}</h3>
<p class="preco">{reais(p.get("priceMin"))}</p>
<p class="meta">{vendas(p.get("sales"))} vendidos, nota {numero(p.get("ratingStar")):.1f}</p>
<span class="botao">Ver na Shopee</span></div></a>'''


PAGINA = '''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nome}</title><meta name="description" content="{desc}">
<style>
:root{{--fundo:#eef1f4;--tinta:#142033;--suave:#5b677a;--acento:#e8512b;--cartao:#fff}}
@media(prefers-color-scheme:dark){{:root{{--fundo:#0f1722;--tinta:#e8edf3;--suave:#9aa7b8;--cartao:#182233}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--fundo);color:var(--tinta);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{padding:48px 20px 24px;max-width:1100px;margin:auto}}
h1{{font-size:clamp(2rem,6vw,3.4rem);line-height:1.05;margin:0 0 10px;letter-spacing:-.02em}}
header p{{color:var(--suave);margin:0 0 20px;max-width:46ch}}
input{{width:100%;max-width:420px;padding:12px 14px;border-radius:10px;border:2px solid var(--suave);background:var(--cartao);color:var(--tinta);font:inherit}}
input:focus-visible,.item:focus-visible{{outline:3px solid var(--acento);outline-offset:2px}}
main{{max-width:1100px;margin:auto;padding:0 20px 40px;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}}
.item{{background:var(--cartao);border-radius:14px;overflow:hidden;text-decoration:none;color:inherit;display:flex;flex-direction:column;border:1px solid rgba(120,130,150,.25)}}
.foto{{aspect-ratio:1;background:rgba(120,130,150,.15)}}.foto img{{width:100%;height:100%;object-fit:cover;display:block}}
.sem-foto{{width:100%;height:100%}}
.info{{padding:12px 14px 16px;display:flex;flex-direction:column;gap:4px;flex:1}}
h3{{font-size:.95rem;font-weight:600;margin:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.preco{{font-size:1.25rem;font-weight:800;margin:4px 0 0}}.meta{{font-size:.8rem;color:var(--suave);margin:0}}
.botao{{margin-top:auto;padding-top:10px;color:var(--acento);font-weight:700}}
.vazio{{display:none;padding:0 20px;max-width:1100px;margin:auto;color:var(--suave)}}
footer{{max-width:1100px;margin:auto;padding:20px;color:var(--suave);font-size:.85rem;border-top:1px solid rgba(120,130,150,.3)}}
@media(hover:hover){{.item:hover{{border-color:var(--acento)}}}}
</style></head><body>
<header><h1>{nome}</h1><p>{desc}</p>
<input id="busca" type="search" placeholder="Buscar produto" aria-label="Buscar produto"></header>
<main id="lista">{cartoes}</main>
<p class="vazio" id="vazio">Nenhum produto encontrado para essa busca.</p>
<footer>Atualizado em {data}. Como afiliado da Shopee, posso receber comissão pelas compras feitas pelos links desta página, sem custo extra para você. Preços e disponibilidade podem mudar na Shopee.</footer>
<script>
const b=document.getElementById('busca'),itens=[...document.querySelectorAll('.item')],v=document.getElementById('vazio');
b.addEventListener('input',()=>{{const t=b.value.trim().toLowerCase();let n=0;
itens.forEach(i=>{{const ok=i.dataset.nome.includes(t);i.style.display=ok?'':'none';if(ok)n++}});
v.style.display=n?'none':'block'}});
</script></body></html>'''


def gerar_site(produtos, cfg):
    pasta = ROOT / "docs"
    pasta.mkdir(exist_ok=True)
    (pasta / "index.html").write_text(PAGINA.format(
        nome=html.escape(cfg["site_nome"]), desc=html.escape(cfg["site_descricao"]),
        cartoes="\n".join(cartao(p) for p in produtos),
        data=time.strftime("%d/%m/%Y")), encoding="utf-8")
    (pasta / ".nojekyll").write_text("")


def postar_pinterest(produtos, cfg):
    if not (cfg.get("pinterest_token") and cfg.get("pinterest_board_id")):
        print("Pinterest não configurado, pulando.")
        return
    arq = ROOT / "ja_postados.json"
    ja = set(json.loads(arq.read_text())) if arq.exists() else set()
    feitos = 0
    for p in produtos:
        if p["itemId"] in ja or feitos >= cfg["pins_por_execucao"]:
            continue
        corpo = {"board_id": cfg["pinterest_board_id"],
                 "title": p["productName"][:100],
                 "description": f"{p['productName']} por {reais(p.get('priceMin'))}. Veja mais ofertas no link.",
                 "link": cfg["site_url"],
                 "media_source": {"source_type": "image_url", "url": p["imageUrl"]}}
        req = urllib.request.Request("https://api.pinterest.com/v5/pins", data=json.dumps(corpo).encode(),
                                     method="POST", headers={"Content-Type": "application/json",
                                                             "Authorization": "Bearer " + cfg["pinterest_token"]})
        try:
            urllib.request.urlopen(req, timeout=30).read()
            ja.add(p["itemId"])
            feitos += 1
            print("Pin criado:", p["productName"][:50])
            time.sleep(5)
        except Exception as e:
            print("Falha ao postar pin:", e)
    arq.write_text(json.dumps(sorted(ja)))


if __name__ == "__main__":
    cfg = carregar_config()
    demo = "--demo" in sys.argv
    if not demo and not (cfg["shopee_app_id"] and cfg["shopee_secret"]):
        sys.exit("Preencha shopee_app_id e shopee_secret no config.json (ou rode com --demo).")
    produtos = produtos_demo() if demo else buscar_produtos(cfg)
    gerar_site(produtos, cfg)
    print(f"Site gerado com {len(produtos)} produtos em docs/index.html")
    if not demo:
        postar_pinterest(produtos, cfg)
