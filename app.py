import io
import os
import re
import math
import json
import random
import hashlib
import datetime
import unicodedata
import importlib.util
from functools import lru_cache

import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==============================================================================
# 0. TEXTOS FIXOS DO APLICATIVO (revise com a equipe antes de usar)
# ==============================================================================
# Estes são os ÚNICOS textos de conteúdo que não vêm da pasta 'conteudos' nem
# são digitados pelo profissional. Mantenha-os curtos e genéricos.

TEXTO_FIXO_PRESCRICAO = (
    "Siga sempre a receita médica. Doses e horários são definidos pela equipe "
    "e não devem ser alterados por conta própria."
)

# ==============================================================================
# 1. CARREGAMENTO AUTOMÁTICO DE CONTEÚDOS DA PASTA 'conteudos'
# ==============================================================================
# Campos esperados em cada arquivo (todos além dos originais são opcionais,
# mas sem eles o material sai como RASCUNHO):
#   "cid": "C91.0"                      -> CID-10 do diagnóstico
#   "validacao": {"status": "validado", "revisado_por": "...", "data": "dd/mm/aaaa", "versao": "1.0"}
#   "referencias": [{"fonte": "...", "entidade": "...", "ano": "...", "url": "...",
#                    "autorizacao": "autorizada" | "nao_se_aplica" | "pendente"}]

PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
PASTA_CONTEUDOS = os.path.join(PASTA_SCRIPT, "conteudos")


def _assinatura_pasta():
    """Muda quando um arquivo de conteúdo é criado/editado (invalida o cache)."""
    if not os.path.exists(PASTA_CONTEUDOS):
        return ()
    return tuple(
        (a, os.path.getmtime(os.path.join(PASTA_CONTEUDOS, a)))
        for a in sorted(os.listdir(PASTA_CONTEUDOS))
        if a.endswith(".py") and not a.startswith("__")
    )


@st.cache_resource(show_spinner=False)
def carregar_conteudos(_assinatura):
    conteudos, erros = {}, []
    if not os.path.exists(PASTA_CONTEUDOS):
        return conteudos, erros
    for arquivo in sorted(os.listdir(PASTA_CONTEUDOS)):
        if arquivo.endswith(".py") and not arquivo.startswith("__"):
            caminho = os.path.join(PASTA_CONTEUDOS, arquivo)
            nome_modulo = arquivo[:-3]
            try:
                spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
                modulo = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modulo)
                if hasattr(modulo, "DADOS"):
                    conteudos[nome_modulo] = modulo.DADOS
            except Exception as e:
                erros.append(f"Erro ao carregar o arquivo {arquivo}: {e}")
    return conteudos, erros


def avaliar_conteudo(dados):
    """Devolve (ok, pendências). Conteúdo só é 'validado' com revisão + referências autorizadas + CID."""
    pend = []
    val = dados.get("validacao") or {}
    if str(val.get("status", "")).lower() != "validado":
        pend.append("O conteúdo ainda não foi marcado como validado pela equipe responsável.")
    elif not (val.get("revisado_por") and val.get("data")):
        pend.append("Faltam o nome do revisor e a data da validação.")
    refs = dados.get("referencias") or []
    if not refs:
        pend.append("Nenhuma referência cadastrada (protocolo, diretriz ou material oficial do serviço).")
    sem_aut = [r for r in refs if str(r.get("autorizacao", "")).lower() not in ("autorizada", "nao_se_aplica")]
    if sem_aut:
        pend.append(f"{len(sem_aut)} referência(s) sem autorização de uso confirmada.")
    if not dados.get("cid"):
        pend.append("CID-10 não informado neste conteúdo.")
    return (not pend), pend


def referencias_publicaveis(dados):
    return [r for r in (dados.get("referencias") or [])
            if str(r.get("autorizacao", "")).lower() in ("autorizada", "nao_se_aplica")]


# ==============================================================================
# 2. SISTEMA DE FONTES E MOTOR GRÁFICO
# ==============================================================================

PASTA_FONTES = os.path.join(PASTA_SCRIPT, "fonts")
URL_BASE_POPPINS = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/"


def _contexto_ssl():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _baixar_fonte(nome_arquivo, destino):
    import urllib.request
    import ssl
    os.makedirs(PASTA_FONTES, exist_ok=True)
    url = URL_BASE_POPPINS + nome_arquivo
    try:
        ctx = _contexto_ssl()
        with urllib.request.urlopen(url, context=ctx, timeout=15) as resp:
            dados = resp.read()
        with open(destino, "wb") as f:
            f.write(dados)
        return os.path.exists(destino) and os.path.getsize(destino) > 0
    except Exception:
        try:
            ctx_inseguro = ssl._create_unverified_context()
            with urllib.request.urlopen(url, context=ctx_inseguro, timeout=15) as resp:
                dados = resp.read()
            with open(destino, "wb") as f:
                f.write(dados)
            return os.path.exists(destino) and os.path.getsize(destino) > 0
        except Exception:
            return False


@lru_cache(maxsize=None)
def carregar_fonte(nome_arquivo, tamanho):
    caminhos = [
        os.path.join(PASTA_FONTES, nome_arquivo),
        f"/usr/share/fonts/truetype/google-fonts/{nome_arquivo}",
        f"C:\\Windows\\Fonts\\{nome_arquivo}",
        f"/System/Library/Fonts/{nome_arquivo}",
    ]
    for c in caminhos:
        if os.path.exists(c):
            return ImageFont.truetype(c, tamanho)

    destino = os.path.join(PASTA_FONTES, nome_arquivo)
    if _baixar_fonte(nome_arquivo, destino):
        return ImageFont.truetype(destino, tamanho)

    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


SS = 2
DPI = 150
W, H = int(8.27 * DPI) * SS, int(11.69 * DPI) * SS
COR_FUNDO = (255, 250, 240)
COR_TEXTO = (45, 40, 35)
COR_TEXTO_SUAVE = (108, 100, 90)
COR_ALERTA_BORDA = (224, 96, 79)
COR_ALERTA_FUNDO = (255, 235, 231)
MARGEM = 60 * SS
LIMITE_INFERIOR = H - 60 * SS   # abaixo disso fica o rodapé de página
ALT_LINHA = 26 * SS
ALT_VAZIO = 10 * SS


def get_fontes():
    return {
        "titulo": carregar_fonte("Poppins-Bold.ttf", 46 * SS),
        "subtitulo": carregar_fonte("Poppins-Medium.ttf", 22 * SS),
        "secao_titulo": carregar_fonte("Poppins-Bold.ttf", 26 * SS),
        "texto": carregar_fonte("Poppins-Regular.ttf", 18 * SS),
        "texto_bold": carregar_fonte("Poppins-Medium.ttf", 18 * SS),
        "rodape": carregar_fonte("Poppins-Regular.ttf", 13 * SS),
        "hospital": carregar_fonte("Poppins-Medium.ttf", 18 * SS),
        "legenda": carregar_fonte("Poppins-Medium.ttf", 10 * SS),
        "marca_grande": carregar_fonte("Poppins-Bold.ttf", 120 * SS),
        "marca_pequena": carregar_fonte("Poppins-Medium.ttf", 26 * SS),
    }


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient_vertical(size, cor_topo, cor_base):
    w, h = size
    base = Image.new("RGB", (1, h), color=0)
    px = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = lerp_color(cor_topo, cor_base, t)
    return base.resize((w, h))


def desenhar_estrela(draw, cx, cy, r_ext, r_int, cor, pontas=5, rotacao=-90):
    pontos = []
    ang = math.radians(rotacao)
    passo = math.pi / pontas
    for i in range(pontas * 2):
        raio = r_ext if i % 2 == 0 else r_int
        a = ang + i * passo
        pontos.append((cx + raio * math.cos(a), cy + raio * math.sin(a)))
    draw.polygon(pontos, fill=cor)


def desenhar_estrelas_fundo(draw, box, quantidade, cor, r_min=2, r_max=5):
    x0, y0, x1, y1 = box
    for _ in range(quantidade):
        x = random.uniform(x0, x1)
        y = random.uniform(y0, y1)
        r = random.uniform(r_min, r_max) * SS
        desenhar_estrela(draw, x, y, r, r * 0.42, cor, pontas=4)


def _compor_sombra(img_rgba, box, desenhar_forma, blur, offset):
    """Sombra desenhada só na região ao redor da caixa (bem mais rápido que a página inteira)."""
    ox, oy = offset[0] * SS, offset[1] * SS
    b = blur * SS
    pad = int(b * 3 + max(abs(ox), abs(oy)))
    x0, y0 = int(max(box[0] - pad, 0)), int(max(box[1] - pad, 0))
    x1, y1 = int(min(box[2] + pad, img_rgba.width)), int(min(box[3] + pad, img_rgba.height))
    if x1 <= x0 or y1 <= y0:
        return
    camada = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    desenhar_forma(ImageDraw.Draw(camada), [box[0] + ox - x0, box[1] + oy - y0, box[2] + ox - x0, box[3] + oy - y0])
    camada = camada.filter(ImageFilter.GaussianBlur(b))
    img_rgba.alpha_composite(camada, dest=(x0, y0))


def sombra_retangulo(img_rgba, box, radius, blur=14, opacidade=40, offset=(0, 8)):
    _compor_sombra(
        img_rgba, box,
        lambda d, bx: d.rounded_rectangle(bx, radius=radius, fill=(30, 25, 60, opacidade)),
        blur, offset,
    )


def desenhar_icone(draw, tipo, cx, cy, raio, cor_frente="#FFFFFF", cor_detalhe=None):
    if tipo == "gota":
        draw.ellipse([cx - raio, cy - raio * 0.15, cx + raio, cy + raio * 1.05], fill=cor_frente)
        draw.polygon([(cx, cy - raio * 1.25), (cx - raio * 0.78, cy - raio * 0.1), (cx + raio * 0.78, cy - raio * 0.1)], fill=cor_frente)
    elif tipo == "estrela":
        desenhar_estrela(draw, cx, cy, raio * 1.15, raio * 0.5, cor_frente, pontas=5)
    elif tipo == "escudo":
        draw.polygon([(cx, cy - raio * 1.05), (cx + raio, cy - raio * 0.5), (cx + raio, cy + raio * 0.3), (cx, cy + raio * 1.15), (cx - raio, cy + raio * 0.3), (cx - raio, cy - raio * 0.5)], fill=cor_frente)
    elif tipo == "alerta":
        draw.polygon([(cx, cy - raio * 1.1), (cx + raio * 1.05, cy + raio * 0.75), (cx - raio * 1.05, cy + raio * 0.75)], fill=cor_frente)
    elif tipo == "coracao":
        draw.ellipse([cx - raio * 1.05, cy - raio * 0.9, cx + raio * 0.05, cy + raio * 0.2], fill=cor_frente)
        draw.ellipse([cx - raio * 0.05, cy - raio * 0.9, cx + raio * 1.05, cy + raio * 0.2], fill=cor_frente)
        draw.polygon([(cx - raio * 1.0, cy - raio * 0.2), (cx + raio * 1.0, cy - raio * 0.2), (cx, cy + raio * 1.1)], fill=cor_frente)
    elif tipo == "pilula":
        draw.rounded_rectangle([cx - raio * 1.15, cy - raio * 0.6, cx + raio * 1.15, cy + raio * 0.6], radius=raio * 0.6, fill=cor_frente)
        if cor_detalhe:
            draw.line([(cx, cy - raio * 0.6), (cx, cy + raio * 0.6)], fill=cor_detalhe, width=max(2, int(raio * 0.16)))
    elif tipo == "balao":
        draw.rounded_rectangle([cx - raio * 1.1, cy - raio * 0.85, cx + raio * 1.1, cy + raio * 0.55], radius=raio * 0.4, fill=cor_frente)
        draw.polygon([(cx - raio * 0.5, cy + raio * 0.4), (cx - raio * 0.5, cy + raio * 1.1), (cx + raio * 0.1, cy + raio * 0.4)], fill=cor_frente)


def desenhar_badge(img_rgba, draw, cx, cy, raio, cor_hex, cor2_hex, icone):
    cor1, cor2 = hex_to_rgb(cor_hex), hex_to_rgb(cor2_hex)
    d = int(raio * 2)
    grad = gradient_vertical((d, d), cor1, cor2)
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d, d], fill=255)
    box = [int(cx - raio), int(cy - raio), int(cx - raio) + d, int(cy - raio) + d]

    _compor_sombra(
        img_rgba, box,
        lambda dr, bx: dr.ellipse(bx, fill=(30, 25, 60, 60)),
        6, (0, 5),
    )
    img_rgba.paste(grad, (box[0], box[1]), mask)
    desenhar_icone(draw, icone, cx, cy, raio * 0.42, cor_detalhe=cor_hex)


def quebrar_texto(draw, texto, fonte, largura_max):
    linhas_finais = []
    for paragrafo in texto.split("\n"):
        if paragrafo.strip() == "":
            linhas_finais.append("")
            continue
        palavras = paragrafo.split(" ")
        linha_atual = ""
        for palavra in palavras:
            teste = (linha_atual + " " + palavra).strip()
            if draw.textlength(teste, font=fonte) <= largura_max:
                linha_atual = teste
            else:
                if linha_atual:
                    linhas_finais.append(linha_atual)
                linha_atual = palavra
        linhas_finais.append(linha_atual)
    return linhas_finais


def preparar_linhas(draw, texto, fonte, largura):
    """Quebra o texto em linhas tipadas: 'p' parágrafo, 'b' início de item, 'bc' continuação de item, 'v' vazio."""
    res = []
    for par in texto.split("\n"):
        s = par.strip()
        if not s:
            res.append(("v", ""))
            continue
        if s.startswith(("• ", "- ", "* ")):
            corpo = s[2:].strip()
            for i, l in enumerate(quebrar_texto(draw, corpo, fonte, largura - 17 * SS)):
                res.append(("b" if i == 0 else "bc", l))
        else:
            for l in quebrar_texto(draw, s, fonte, largura):
                res.append(("p", l))
    # remove linhas vazias no começo/fim
    while res and res[0][0] == "v":
        res.pop(0)
    while res and res[-1][0] == "v":
        res.pop()
    return res


def altura_linhas(linhas, lh=ALT_LINHA, vh=ALT_VAZIO):
    return sum(vh if t == "v" else lh for t, _ in linhas)


def desenhar_linhas(draw, linhas, x, y, fonte, cor_texto, cor_bullet, lh=ALT_LINHA, vh=ALT_VAZIO):
    for tipo, linha in linhas:
        if tipo == "v":
            y += vh
            continue
        if tipo == "b":
            d = 7 * SS
            cy_b = y + lh * 0.45
            draw.ellipse([x, cy_b - d / 2, x + d, cy_b + d / 2], fill=cor_bullet)
        recuo = 17 * SS if tipo in ("b", "bc") else 0
        draw.text((x + recuo, y), linha, font=fonte, fill=cor_texto)
        y += lh
    return y


def rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def desenhar_ilustracao_dinamica(draw, tipo, box, fontes):
    x0, y0, x1, y1 = box
    w_box, h_box = x1 - x0, y1 - y0
    rounded_rect(draw, [x0, y0, x1, y1], radius=12 * SS, fill=(248, 249, 252, 255), outline=(225, 230, 240, 255), width=int(1 * SS))
    cy = y0 + h_box * 0.42

    def seta():
        cx_seta = x0 + w_box * 0.52
        draw.line([(cx_seta - 8 * SS, cy), (cx_seta + 6 * SS, cy)], fill=(180, 190, 210), width=int(2 * SS))
        draw.polygon([(cx_seta + 5 * SS, cy - 4 * SS), (cx_seta + 11 * SS, cy), (cx_seta + 5 * SS, cy + 4 * SS)], fill=(180, 190, 210))

    def legenda(cx, texto, cor):
        tw = draw.textlength(texto, font=fontes["legenda"])
        draw.text((cx - tw / 2, y1 - 22 * SS), texto, font=fontes["legenda"], fill=cor)

    if tipo == "anemia_falciforme":
        cx_norm, r_norm = x0 + w_box * 0.28, 18 * SS
        draw.ellipse([cx_norm - r_norm, cy - r_norm + 2 * SS, cx_norm + r_norm, cy + r_norm + 2 * SS], fill=(220, 180, 180, 150))
        draw.ellipse([cx_norm - r_norm, cy - r_norm, cx_norm + r_norm, cy + r_norm], fill=(235, 60, 60))
        draw.ellipse([cx_norm - r_norm * 0.5, cy - r_norm * 0.5, cx_norm + r_norm * 0.5, cy + r_norm * 0.5], fill=(250, 130, 130))
        seta()
        cx_fal, r_fal = x0 + w_box * 0.76, 20 * SS
        pontos_foice = [
            (cx_fal - r_fal * 0.6, cy - r_fal * 0.8), (cx_fal + r_fal * 0.1, cy - r_fal * 0.7),
            (cx_fal + r_fal * 0.6, cy - r_fal * 0.2), (cx_fal + r_fal * 0.7, cy + r_fal * 0.4),
            (cx_fal + r_fal * 0.3, cy + r_fal * 0.8), (cx_fal - r_fal * 0.2, cy + r_fal * 0.5),
            (cx_fal + r_fal * 0.2, cy + r_fal * 0.2), (cx_fal + r_fal * 0.1, cy - r_fal * 0.3),
            (cx_fal - r_fal * 0.6, cy - r_fal * 0.8)
        ]
        draw.polygon(pontos_foice, fill=(210, 40, 40))
        legenda(cx_norm, "Normal", (100, 110, 125))
        legenda(cx_fal, "Em foice", (190, 50, 50))

    elif tipo.startswith("leucemia"):
        # célula normal (glóbulo vermelho) -> linfoblasto (célula grande, núcleo grande)
        cx_norm, r_norm = x0 + w_box * 0.28, 18 * SS
        draw.ellipse([cx_norm - r_norm, cy - r_norm + 2 * SS, cx_norm + r_norm, cy + r_norm + 2 * SS], fill=(220, 180, 180, 150))
        draw.ellipse([cx_norm - r_norm, cy - r_norm, cx_norm + r_norm, cy + r_norm], fill=(235, 60, 60))
        draw.ellipse([cx_norm - r_norm * 0.5, cy - r_norm * 0.5, cx_norm + r_norm * 0.5, cy + r_norm * 0.5], fill=(250, 130, 130))
        seta()
        cx_l, r_l = x0 + w_box * 0.76, 21 * SS
        draw.ellipse([cx_l - r_l, cy - r_l + 2 * SS, cx_l + r_l, cy + r_l + 2 * SS], fill=(200, 190, 225, 150))
        draw.ellipse([cx_l - r_l, cy - r_l, cx_l + r_l, cy + r_l], fill=(205, 195, 235))
        draw.ellipse([cx_l - r_l * 0.78, cy - r_l * 0.78, cx_l + r_l * 0.78, cy + r_l * 0.78], fill=(112, 76, 168))
        for dx, dy in ((-0.25, -0.2), (0.22, 0.15)):
            draw.ellipse([cx_l + r_l * dx - 3 * SS, cy + r_l * dy - 3 * SS, cx_l + r_l * dx + 3 * SS, cy + r_l * dy + 3 * SS], fill=(70, 40, 120))
        legenda(cx_norm, "Normal", (100, 110, 125))
        legenda(cx_l, "Linfoblasto", (112, 76, 168))

    else:
        cx_norm, r_norm = x0 + w_box * 0.28, 20 * SS
        draw.ellipse([cx_norm - r_norm, cy - r_norm + 2 * SS, cx_norm + r_norm, cy + r_norm + 2 * SS], fill=(220, 180, 180, 150))
        draw.ellipse([cx_norm - r_norm, cy - r_norm, cx_norm + r_norm, cy + r_norm], fill=(235, 60, 60))
        draw.ellipse([cx_norm - r_norm * 0.45, cy - r_norm * 0.45, cx_norm + r_norm * 0.45, cy + r_norm * 0.45], fill=(250, 140, 140))
        seta()
        cx_micro, r_micro = x0 + w_box * 0.76, 13 * SS
        draw.ellipse([cx_micro - r_micro, cy - r_micro + 2 * SS, cx_micro + r_micro, cy + r_micro + 2 * SS], fill=(220, 180, 180, 120))
        draw.ellipse([cx_micro - r_micro, cy - r_micro, cx_micro + r_micro, cy + r_micro], fill=(220, 80, 80))
        draw.ellipse([cx_micro - r_micro * 0.7, cy - r_micro * 0.7, cx_micro + r_micro * 0.7, cy + r_micro * 0.7], fill=(248, 205, 205))
        legenda(cx_norm, "Normal", (100, 110, 125))
        legenda(cx_micro, "Alterada", (190, 60, 60))


# ------------------------------------------------------------------------------
# Blocos de conteúdo (cada bloco sabe medir e desenhar a si mesmo)
# ------------------------------------------------------------------------------

LARGURA_TEXTO = W - 2 * MARGEM - 120 * SS


def bloco_secao(dm, fontes, titulo, texto, cor, cor2, icone, ilustracao=None):
    largura = LARGURA_TEXTO - (150 * SS if ilustracao else 0)
    linhas = preparar_linhas(dm, texto, fontes["texto"], largura)
    altura = 75 * SS + altura_linhas(linhas) + 16 * SS
    if ilustracao:
        altura = max(altura, 200 * SS)

    def desenhar(img, draw, y):
        box = [MARGEM, y, W - MARGEM, y + altura]
        sombra_retangulo(img, box, 22 * SS, blur=8, opacidade=30, offset=(0, 6))
        rounded_rect(draw, box, 22 * SS, fill=(255, 255, 255, 255))
        rounded_rect(draw, [box[0], box[1] + 18 * SS, box[0] + 7 * SS, box[3] - 18 * SS], 3 * SS, fill=hex_to_rgb(cor))
        desenhar_badge(img, draw, MARGEM + 55 * SS, y + 46 * SS, 25 * SS, cor, cor2, icone)
        draw.text((MARGEM + 98 * SS, y + 24 * SS), titulo, font=fontes["secao_titulo"], fill=hex_to_rgb(cor))
        if ilustracao:
            desenhar_ilustracao_dinamica(draw, ilustracao, [W - MARGEM - 160 * SS, y + 60 * SS, W - MARGEM - 20 * SS, y + 180 * SS], fontes)
        desenhar_linhas(draw, linhas, MARGEM + 98 * SS, y + 68 * SS, fontes["texto"], COR_TEXTO, hex_to_rgb(cor))

    return {"altura": altura, "desenhar": desenhar}


def bloco_alerta(dm, fontes, titulo, itens):
    largura = LARGURA_TEXTO - 20 * SS
    blocos = [quebrar_texto(dm, item, fontes["texto_bold"], largura) for item in itens]
    altura = 72 * SS + sum(len(b) for b in blocos) * ALT_LINHA + 16 * SS

    def desenhar(img, draw, y):
        box = [MARGEM, y, W - MARGEM, y + altura]
        sombra_retangulo(img, box, 22 * SS, blur=8, opacidade=30, offset=(0, 6))
        rounded_rect(draw, box, 22 * SS, fill=COR_ALERTA_FUNDO)
        draw.rounded_rectangle(box, radius=22 * SS, outline=COR_ALERTA_BORDA, width=int(2 * SS))
        desenhar_badge(img, draw, MARGEM + 55 * SS, y + 44 * SS, 25 * SS, "#E0604F", "#F08A6F", "alerta")
        draw.text((MARGEM + 98 * SS, y + 22 * SS), titulo, font=fontes["secao_titulo"], fill=COR_ALERTA_BORDA)
        ty = y + 66 * SS
        for linhas_item in blocos:
            draw.ellipse([MARGEM + 98 * SS, ty + 8 * SS, MARGEM + 106 * SS, ty + 16 * SS], fill=COR_ALERTA_BORDA)
            for linha in linhas_item:
                draw.text((MARGEM + 118 * SS, ty), linha, font=fontes["texto_bold"], fill=(122, 46, 43))
                ty += ALT_LINHA

    return {"altura": altura, "desenhar": desenhar}


def bloco_contatos(dm, fontes, titulo, itens, cor="#3D8B5A", cor2="#6DB98A"):
    """itens: lista de (rótulo, valor). Duas colunas: rótulo em negrito / valor com quebra de linha."""
    x_rotulo = MARGEM + 98 * SS
    x_valor = x_rotulo + 200 * SS
    largura_valor = (W - MARGEM - 24 * SS) - x_valor
    linhas = [(r, quebrar_texto(dm, v, fontes["texto"], largura_valor)) for r, v in itens]
    altura = 72 * SS + sum(len(l) * ALT_LINHA + 4 * SS for _, l in linhas) + 14 * SS

    def desenhar(img, draw, y):
        box = [MARGEM, y, W - MARGEM, y + altura]
        sombra_retangulo(img, box, 22 * SS, blur=8, opacidade=30, offset=(0, 6))
        rounded_rect(draw, box, 22 * SS, fill=(255, 255, 255, 255))
        rounded_rect(draw, [box[0], box[1] + 18 * SS, box[0] + 7 * SS, box[3] - 18 * SS], 3 * SS, fill=hex_to_rgb(cor))
        desenhar_badge(img, draw, MARGEM + 55 * SS, y + 44 * SS, 25 * SS, cor, cor2, "balao")
        draw.text((MARGEM + 98 * SS, y + 22 * SS), titulo, font=fontes["secao_titulo"], fill=hex_to_rgb(cor))
        ty = y + 68 * SS
        for rotulo, ls in linhas:
            draw.text((x_rotulo, ty), rotulo, font=fontes["texto_bold"], fill=hex_to_rgb(cor))
            for l in ls:
                draw.text((x_valor, ty), l, font=fontes["texto"], fill=COR_TEXTO)
                ty += ALT_LINHA
            ty += 4 * SS

    return {"altura": altura, "desenhar": desenhar}


def bloco_duvidas(fontes):
    altura = 145 * SS

    def desenhar(img, draw, y):
        box = [MARGEM, y, W - MARGEM, y + altura]
        sombra_retangulo(img, box, 22 * SS, blur=8, opacidade=25, offset=(0, 5))
        rounded_rect(draw, box, 22 * SS, fill=(255, 255, 255, 255))
        desenhar_estrela(draw, MARGEM + 32 * SS, y + 32 * SS, 11 * SS, 5 * SS, hex_to_rgb("#E0A233"))
        draw.text((MARGEM + 52 * SS, y + 20 * SS), "Anote aqui suas dúvidas para a próxima consulta:", font=fontes["texto_bold"], fill=COR_TEXTO_SUAVE)
        for i in range(4):
            ly = y + 62 * SS + i * 24 * SS
            draw.line([(MARGEM + 28 * SS, ly), (W - MARGEM - 28 * SS, ly)], fill=(220, 212, 196), width=int(SS * 1.2))

    return {"altura": altura, "desenhar": desenhar}


def bloco_notas_finais(dm, fontes, texto):
    lh, vh = 18 * SS, 8 * SS
    linhas = preparar_linhas(dm, texto, fontes["rodape"], W - 2 * MARGEM)
    altura = 14 * SS + altura_linhas(linhas, lh, vh)

    def desenhar(img, draw, y):
        draw.line([(MARGEM, y + 4 * SS), (W - MARGEM, y + 4 * SS)], fill=(225, 215, 198), width=int(SS * 1.2))
        desenhar_linhas(draw, linhas, MARGEM, y + 14 * SS, fontes["rodape"], COR_TEXTO_SUAVE, COR_TEXTO_SUAVE, lh, vh)

    return {"altura": altura, "desenhar": desenhar}


# ------------------------------------------------------------------------------
# Páginas
# ------------------------------------------------------------------------------

def _desenhar_cabecalho(img, dados, e, fontes):
    altura_header = 210 * SS
    img.paste(gradient_vertical((W, altura_header), hex_to_rgb("#1A2550"), hex_to_rgb("#364790")), (0, 0))
    draw = ImageDraw.Draw(img)
    for _ in range(40):
        x, y = random.uniform(0, W), random.uniform(0, altura_header)
        r = random.uniform(2, 5) * SS
        desenhar_estrela(draw, x, y, r, r * 0.42, (255, 214, 130, 220), pontas=4)

    px, py, pr = W - 120 * SS, 85 * SS, 42 * SS
    draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(255, 200, 90, 230))
    draw.ellipse([px - pr * 1.6, py - pr * 0.25, px + pr * 1.6, py + pr * 0.25], outline=(255, 226, 158, 200), width=int(3 * SS))

    draw.text((MARGEM, 20 * SS), dados["hospital"].upper(), font=fontes["hospital"], fill=(210, 225, 255, 230))
    draw.text((MARGEM, 48 * SS), "Guia da Família", font=fontes["titulo"], fill=(255, 255, 255, 255))
    draw.text((MARGEM, 118 * SS), f"Paciente: {e['nome']}", font=fontes["subtitulo"], fill=(255, 226, 158, 255))

    diag = dados["titulo_diagnostico"]
    cid = dados.get("cid")
    diag_txt = f"CID-10 {cid} · {diag}" if cid else diag
    diag_w = draw.textlength(diag_txt, font=fontes["texto_bold"]) + 40 * SS
    rounded_rect(draw, [MARGEM, 152 * SS, MARGEM + diag_w, 188 * SS], 18 * SS, fill=(255, 255, 255, 240))
    draw.text((MARGEM + 20 * SS, 158 * SS), diag_txt, font=fontes["texto_bold"], fill=hex_to_rgb("#1A2550"))
    return altura_header + 24 * SS


def _desenhar_faixa_continuacao(img, e, fontes):
    altura = 54 * SS
    img.paste(gradient_vertical((W, altura), hex_to_rgb("#1A2550"), hex_to_rgb("#364790")), (0, 0))
    ImageDraw.Draw(img).text((MARGEM, 12 * SS), f"Guia da Família · {e['nome']}", font=fontes["texto_bold"], fill=(255, 255, 255, 255))
    return altura + 24 * SS


def _nova_pagina(numero, dados, e, fontes):
    img = Image.new("RGBA", (W, H), COR_FUNDO + (255,))
    random.seed(6 + numero)
    desenhar_estrelas_fundo(ImageDraw.Draw(img), (0, 0, W, H), 60, (235, 220, 190, 255), 2, 4)
    y = _desenhar_cabecalho(img, dados, e, fontes) if numero == 1 else _desenhar_faixa_continuacao(img, e, fontes)
    return img, ImageDraw.Draw(img), y


def _rodape_pagina(img, numero, total, dados, e, rascunho, fontes):
    draw = ImageDraw.Draw(img)
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    y = H - 36 * SS
    esq = f"{dados['hospital']} · Guia da Família · {e['nome']} · gerado em {hoje}"
    draw.text((MARGEM, y), esq, font=fontes["rodape"], fill=COR_TEXTO_SUAVE)
    dir_txt = f"Página {numero} de {total}"
    tw = draw.textlength(dir_txt, font=fontes["rodape"])
    draw.text((W - MARGEM - tw, y), dir_txt, font=fontes["rodape"], fill=COR_TEXTO_SUAVE)
    if rascunho:
        draw.text((MARGEM, y - 20 * SS), "RASCUNHO: conteúdo ainda não validado. Não entregar à família.",
                  font=fontes["rodape"], fill=COR_ALERTA_BORDA)


def _marca_dagua(img, fontes):
    d = ImageDraw.Draw(img)
    t1, t2 = "RASCUNHO", "Conteúdo ainda sem validação oficial"
    w1 = d.textlength(t1, font=fontes["marca_grande"])
    w2 = d.textlength(t2, font=fontes["marca_pequena"])
    tile = Image.new("RGBA", (int(max(w1, w2)) + 80 * SS, 230 * SS), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.text(((tile.width - w1) / 2, 10 * SS), t1, font=fontes["marca_grande"], fill=(200, 40, 40, 60))
    td.text(((tile.width - w2) / 2, 165 * SS), t2, font=fontes["marca_pequena"], fill=(200, 40, 40, 80))
    tile = tile.rotate(35, expand=True, resample=Image.BICUBIC)
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    camada.paste(tile, ((W - tile.width) // 2, (H - tile.height) // 2), tile)
    img.alpha_composite(camada)


def _linhas_contato(e):
    itens = []
    prof = e["profissional"].strip()
    if prof:
        extra = " · ".join(x for x in (e["registro"].strip(), e["especialidade"].strip()) if x)
        itens.append(("Profissional", f"{prof} ({extra})" if extra else prof))
    if e["local"].strip():
        itens.append(("Local", e["local"].strip()))
    if e["telefone"].strip():
        itens.append(("Telefone", e["telefone"].strip()))
    sec = " · ".join(x for x in (e["secretaria_nome"].strip(), e["secretaria_tel"].strip()) if x)
    if sec:
        itens.append(("Secretaria", sec))
    if e["email"].strip():
        itens.append(("E-mail / WhatsApp", e["email"].strip()))
    if e["horario"].strip():
        itens.append(("Horário", e["horario"].strip()))
    return itens


def _texto_prescricao(e):
    partes = []
    carac = []
    if e["idade"].strip():
        carac.append(f"Idade: {e['idade'].strip()}")
    if e["peso"].strip():
        carac.append(f"Peso: {e['peso'].strip()}")
    if e["alergias"].strip():
        carac.append(f"Alergias: {e['alergias'].strip()}")
    if carac:
        partes.append(" · ".join(carac))
    if e["prescricao"].strip():
        partes.append(e["prescricao"].strip())
    if not partes:
        return ""
    partes.append(TEXTO_FIXO_PRESCRICAO)
    return "\n\n".join(partes)


def _notas_finais(dados, e):
    nome = e["nome"]
    partes = [dados["rodape"].replace("{nome}", nome)]
    val = dados.get("validacao") or {}
    if str(val.get("status", "")).lower() == "validado":
        v = f"Conteúdo revisado por {val.get('revisado_por', '')} em {val.get('data', '')}"
        if val.get("versao"):
            v += f" (versão {val['versao']})"
        partes.append(v + ".")
    refs = referencias_publicaveis(dados)
    if refs:
        partes.append("Referências:")
        for i, r in enumerate(refs, 1):
            linha = f"{i}. {r.get('fonte', '')}"
            if r.get("entidade"):
                linha += f". {r['entidade']}"
            if r.get("ano"):
                linha += f", {r['ano']}"
            if r.get("url"):
                linha += f". {r['url']}"
            partes.append(linha)
    return "\n".join(partes)


def gerar_paginas(dados, e, rascunho):
    """Devolve a lista de páginas (PIL RGB). Quebra de página automática nos blocos."""
    fontes = get_fontes()
    nome = e["nome"]
    dm = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    sub = lambda t: t.replace("{nome}", nome)

    blocos = []
    for idx in e["secoes"]:
        s = dados["secoes"][idx]
        ilus = dados.get("tipo_ilustracao") if idx == 0 else None
        blocos.append(bloco_secao(dm, fontes, sub(s["titulo"]), sub(s["texto"]), s["cor"], s["cor2"], s["icone"], ilus))

    if e["preocupacoes"].strip():
        blocos.append(bloco_secao(dm, fontes, f"Cuidados específicos para {nome}", e["preocupacoes"],
                                  "#C2559B", "#DE86BD", "coracao"))
    texto_presc = _texto_prescricao(e)
    if texto_presc:
        blocos.append(bloco_secao(dm, fontes, f"Sobre os medicamentos de {nome}", texto_presc,
                                  "#7A5CD6", "#A28BEA", "pilula"))

    itens_alerta = [sub(dados["alerta_itens"][i]) for i in e["alertas"]]
    blocos.append(bloco_alerta(dm, fontes, sub(dados["alerta_titulo"]), itens_alerta))

    contatos = _linhas_contato(e)
    if contatos:
        blocos.append(bloco_contatos(dm, fontes, "Fale com a equipe", contatos))

    blocos.append(bloco_duvidas(fontes))
    blocos.append(bloco_notas_finais(dm, fontes, _notas_finais(dados, e)))

    paginas = []
    img, draw, y = _nova_pagina(1, dados, e, fontes)
    y_inicio = y
    paginas.append(img)
    for b in blocos:
        if y + b["altura"] > LIMITE_INFERIOR and y > y_inicio:
            img, draw, y = _nova_pagina(len(paginas) + 1, dados, e, fontes)
            y_inicio = y
            paginas.append(img)
        b["desenhar"](img, draw, y)
        y += b["altura"] + 20 * SS

    saida = []
    for i, pg in enumerate(paginas, 1):
        _rodape_pagina(pg, i, len(paginas), dados, e, rascunho, fontes)
        if rascunho:
            _marca_dagua(pg, fontes)
        rgb = pg.convert("RGB")
        if SS != 1:
            rgb = rgb.resize((W // SS, H // SS), Image.LANCZOS)
        saida.append(rgb)
    return saida


def paginas_para_bytes(paginas):
    pngs = []
    for p in paginas:
        b = io.BytesIO()
        p.save(b, format="PNG")
        pngs.append(b.getvalue())
    pdf = io.BytesIO()
    paginas[0].save(pdf, format="PDF", resolution=DPI, save_all=True, append_images=paginas[1:])
    return pngs, pdf.getvalue()


# ==============================================================================
# 3. INTERFACE STREAMLIT
# ==============================================================================

def slug(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", txt).strip("_") or "paciente"


def rotulo_diagnostico(d):
    return f"{d['cid']} · {d['nome_select']}" if d.get("cid") else d["nome_select"]


st.set_page_config(page_title="Gerador de Infográficos - Hospital", layout="centered")
st.title("🎨 Gerador de Infográficos Ilustrados (PX)")
st.caption("Ferramenta de Literacia em Saúde Infantil · uso por profissionais de saúde")
st.markdown("---")

CONTEUDOS, ERROS = carregar_conteudos(_assinatura_pasta())
for msg in ERROS:
    st.warning(msg)

if not CONTEUDOS:
    st.error("Nenhuma doença foi encontrada dentro da pasta 'conteudos'. Verifique se criou a pasta 'conteudos' e colocou os arquivos .py lá dentro.")
    st.stop()

# ---- 1. Diagnóstico ---------------------------------------------------------
st.subheader("1. Diagnóstico")
opcoes = {rotulo_diagnostico(d): k for k, d in CONTEUDOS.items() if "nome_select" in d}
opcao = st.selectbox("Diagnóstico (digite o nome ou o CID-10 para buscar):", sorted(opcoes))
chave = opcoes[opcao]
dados = CONTEUDOS[chave]

conteudo_ok, pendencias_conteudo = avaliar_conteudo(dados)
c1, c2 = st.columns(2)
c1.markdown(f"**CID-10:** {dados.get('cid') or '— não informado —'}")
c2.markdown(f"**Serviço:** {dados['hospital']}")

if conteudo_ok:
    val = dados["validacao"]
    st.success(f"Conteúdo validado por {val['revisado_por']} em {val['data']}"
               + (f" (versão {val['versao']})." if val.get("versao") else "."))
else:
    st.warning("**Conteúdo ainda não validado.** O material será gerado como RASCUNHO (com marca d'água):\n\n"
               + "\n".join(f"- {p}" for p in pendencias_conteudo))

with st.expander("Referências deste conteúdo"):
    refs = dados.get("referencias") or []
    if not refs:
        st.write("Nenhuma referência cadastrada.")
    for r in refs:
        aut = str(r.get("autorizacao", "pendente")).lower()
        selo = {"autorizada": "✅ autorizada", "nao_se_aplica": "✅ uso livre"}.get(aut, "⏳ autorização pendente")
        st.markdown(f"- {r.get('fonte', '')} · {r.get('entidade', '')} {r.get('ano', '')} · {r.get('url', '')} — *{selo}*")
    st.caption("Só referências autorizadas aparecem impressas no material.")

# ---- 2. Paciente ------------------------------------------------------------
st.subheader("2. Paciente")
nome_paciente = st.text_input("Nome da criança:", key="nome_paciente").strip()
ca, cb, cc = st.columns(3)
idade = ca.text_input("Idade (opcional):", placeholder="ex.: 5 anos", key="idade")
peso = cb.text_input("Peso (opcional):", placeholder="ex.: 18 kg", key="peso")
alergias = cc.text_input("Alergias (opcional):", placeholder="ex.: nenhuma conhecida", key="alergias")

# ---- 3. Conteúdo ------------------------------------------------------------
st.subheader("3. Conteúdo do material")
st.caption("Confira o texto de cada seção e retire o que não se aplica a este paciente.")
sel_secoes = st.multiselect(
    "Seções incluídas:", list(range(len(dados["secoes"]))),
    default=list(range(len(dados["secoes"]))),
    format_func=lambda i: dados["secoes"][i]["titulo"].replace("{nome}", nome_paciente or "paciente"),
    key=f"secoes_{chave}",
)
sel_alertas = st.multiselect(
    "Sinais de alerta incluídos:", list(range(len(dados["alerta_itens"]))),
    default=list(range(len(dados["alerta_itens"]))),
    format_func=lambda i: dados["alerta_itens"][i],
    key=f"alertas_{chave}",
)
if len(sel_alertas) < len(dados["alerta_itens"]):
    st.info("Você removeu sinais de alerta do conteúdo-base. Confirme que isso é intencional.")
with st.expander("Ler o texto completo do conteúdo-base"):
    for i, s in enumerate(dados["secoes"]):
        st.markdown(f"**{s['titulo'].replace('{nome}', nome_paciente or 'paciente')}**")
        st.text(s["texto"].replace("{nome}", nome_paciente or "paciente"))

# ---- 4. Personalização ------------------------------------------------------
st.subheader("4. Orientações específicas do paciente")
preocupacoes = st.text_area(
    "Preocupações e cuidados específicos (opcional):", max_chars=700, height=110, key="preocupacoes",
    placeholder="Escrito pelo profissional. Use '-' no início da linha para fazer lista.",
)
prescricao = st.text_area(
    "Orientações sobre a prescrição (opcional):", max_chars=700, height=110, key="prescricao",
    placeholder="Escrito pelo profissional, conforme as características do paciente.",
)
st.caption("O aplicativo **não calcula doses** nem sugere medicamentos: tudo o que aparece aqui é digitado e de responsabilidade do profissional.")

# ---- 5. Equipe e contatos ---------------------------------------------------
st.subheader("5. Equipe, contatos e local de atendimento")
cp1, cp2 = st.columns(2)
profissional = cp1.text_input("Profissional de referência:", key="profissional", placeholder="ex.: Dra. Maria Silva")
registro = cp2.text_input("Registro (CRM/COREN...):", key="registro", placeholder="ex.: CRM-PR 00000")
especialidade = st.text_input("Especialidade / cargo (opcional):", key="especialidade", placeholder="ex.: Oncologia Pediátrica")
local = st.text_input("Local de atendimento de referência:", key="local", placeholder="ex.: Ambulatório de Oncologia, 2º andar")
ct1, ct2 = st.columns(2)
telefone = ct1.text_input("Telefone da equipe:", key="telefone")
email = ct2.text_input("E-mail / WhatsApp (opcional):", key="email")
cs1, cs2 = st.columns(2)
secretaria_nome = cs1.text_input("Secretaria (nome, opcional):", key="secretaria_nome")
secretaria_tel = cs2.text_input("Secretaria (telefone):", key="secretaria_tel")
horario = st.text_input("Horário de atendimento dos contatos (opcional):", key="horario", placeholder="ex.: seg. a sex., 8h às 17h")

# ---- 6. Conferência e geração -----------------------------------------------
st.markdown("---")
st.subheader("6. Conferência e geração")

entrada = {
    "nome": nome_paciente, "idade": idade, "peso": peso, "alergias": alergias,
    "secoes": sorted(sel_secoes), "alertas": sorted(sel_alertas),
    "preocupacoes": preocupacoes, "prescricao": prescricao,
    "profissional": profissional, "registro": registro, "especialidade": especialidade,
    "local": local, "telefone": telefone, "email": email,
    "secretaria_nome": secretaria_nome, "secretaria_tel": secretaria_tel, "horario": horario,
}

bloqueios = []
if not nome_paciente:
    bloqueios.append("Informe o nome da criança.")
if not sel_secoes:
    bloqueios.append("Selecione ao menos uma seção.")
if not sel_alertas:
    bloqueios.append("Mantenha ao menos um sinal de alerta.")
if not profissional.strip():
    bloqueios.append("Informe o profissional de referência.")
if not any(x.strip() for x in (telefone, secretaria_tel, email)):
    bloqueios.append("Informe ao menos um contato (telefone, secretaria ou e-mail/WhatsApp).")

st.markdown(
    f"**Resumo:** {nome_paciente or '—'} · {rotulo_diagnostico(dados)} · "
    f"{len(sel_secoes)} seção(ões) · {len(sel_alertas)} sinal(is) de alerta · "
    f"{'com' if preocupacoes.strip() else 'sem'} cuidados específicos · "
    f"{'com' if prescricao.strip() else 'sem'} orientação de prescrição · "
    f"profissional: {profissional or '—'}"
)

confirmou = st.checkbox(
    "Revisei o diagnóstico (CID), o conteúdo selecionado e os textos digitados, e confirmo que são adequados a este paciente.",
    key="confirma_revisao",
)
if not confirmou:
    bloqueios.append("Marque a confirmação de revisão.")

ciente_rascunho = True
if not conteudo_ok:
    ciente_rascunho = st.checkbox(
        "Estou ciente de que este material sairá como RASCUNHO e não deve ser entregue à família antes da validação do conteúdo.",
        key=f"ciente_rascunho_{chave}",
    )
    if not ciente_rascunho:
        bloqueios.append("Confirme que está ciente de que o material é um rascunho.")

if bloqueios:
    st.info("Para liberar o botão:\n\n" + "\n".join(f"- {b}" for b in bloqueios))

assinatura = hashlib.md5(json.dumps({"c": chave, "e": entrada, "r": not conteudo_ok},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()

rotulo_botao = "🚀 Gerar material" + ("" if conteudo_ok else " (RASCUNHO)")
if st.button(rotulo_botao, type="primary", disabled=bool(bloqueios)):
    with st.spinner("Gerando material..."):
        paginas = gerar_paginas(dados, entrada, rascunho=not conteudo_ok)
        pngs, pdf = paginas_para_bytes(paginas)
    st.session_state["resultado"] = {
        "assinatura": assinatura, "paginas": paginas, "pngs": pngs, "pdf": pdf,
        "rascunho": not conteudo_ok, "chave": chave, "nome": nome_paciente,
    }

res = st.session_state.get("resultado")
if res:
    if res["assinatura"] != assinatura:
        st.warning("Os dados foram alterados desde a última geração. Revise e gere o material novamente.")
    else:
        if res["rascunho"]:
            st.warning("Material gerado como RASCUNHO (conteúdo não validado).")
        else:
            st.success("Material gerado com sucesso!")
        n = len(res["paginas"])
        for i, pg in enumerate(res["paginas"], 1):
            legenda = f"Guia Ilustrado - {res['nome']} (página {i} de {n})"
            try:
                st.image(pg, caption=legenda, width="stretch")
            except TypeError:  # versões antigas do Streamlit
                st.image(pg, caption=legenda, use_container_width=True)

        base = f"Guia_{res['chave']}_{slug(res['nome'])}" + ("_RASCUNHO" if res["rascunho"] else "")
        st.download_button("📥 Baixar PDF (todas as páginas)", data=res["pdf"],
                           file_name=base + ".pdf", mime="application/pdf")
        for i, png in enumerate(res["pngs"], 1):
            st.download_button(f"📥 Baixar PNG - página {i}", data=png,
                               file_name=f"{base}_p{i}.png", mime="image/png", key=f"png_{i}")
