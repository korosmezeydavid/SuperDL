from pathlib import Path
import json
import re
from urllib.parse import urlsplit
import requests
from superdl import store

DATA = store.CONFIG_DIR / 'linkek.json'

def normalize_url(url):
    url = url.strip()
    if not url:
        raise ValueError('Add meg a linket.')
    if '://' not in url:
        url = 'https://' + url
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Adj meg egy érvényes http vagy https címet, felhasználónév nélkül.')
    return url

def shorten(url, alias='', statistics=True):
    url = normalize_url(url)
    alias = alias.strip()
    if alias and not re.fullmatch(r'[A-Za-z0-9_]{5,30}', alias):
        raise ValueError('A link vége 5–30 ékezet nélküli betű, szám vagy aláhúzás lehet.')
    params = {'format': 'json', 'url': url}
    if alias: params['shorturl'] = alias
    if statistics: params['logstats'] = '1'
    try:
        response = requests.post('https://is.gd/create.php', data=params, timeout=(10, 25), allow_redirects=False)
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError('A szolgáltatótól nem érkezett egyértelmű válasz. Lehet, hogy a link létrejött; ellenőrizd, mielőtt újra próbálod.') from exc
    if not isinstance(result, dict):
        raise RuntimeError('A szolgáltató válasza nem értelmezhető; a létrehozás eredménye bizonytalan.')
    if 'errorcode' in result:
        raise ValueError('Az is.gd nem hozta létre a linket: ' + str(result.get('errormessage', 'ismeretlen hiba')))
    short = result.get('shorturl', '')
    parsed = urlsplit(short)
    if response.status_code != 200 or parsed.scheme != 'https' or parsed.hostname != 'is.gd' or not re.fullmatch(r'/[A-Za-z0-9_]{5,30}', parsed.path) or parsed.query or parsed.fragment:
        raise RuntimeError('A szolgáltató nem igazolta a link létrehozását; az eredmény bizonytalan.')
    return {'url': url, 'short': short, 'caption': '', 'statistics': bool(statistics)}

def load():
    data = store.load_json(DATA, [])
    if not isinstance(data, list):
        raise ValueError('A mentett linkek listája nem olvasható.')
    return data

def save(items):
    store.save_json(DATA, items)

def make_qr(url, caption, destination):
    import sys
    vendor = str(Path(__file__).parent / 'vendor')
    if vendor not in sys.path: sys.path.insert(0, vendor)
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    url = normalize_url(url)
    image = qrcode.make(url).convert('RGB')
    if caption.strip():
        fontpath = Path('C:/Windows/Fonts/arial.ttf')
        font = ImageFont.truetype(str(fontpath), 20) if fontpath.exists() else ImageFont.load_default()
        draw = ImageDraw.Draw(image)
        words, lines, line = caption.split(), [], ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if line and draw.textbbox((0, 0), candidate, font=font)[2] > image.width - 24:
                lines.append(line); line = word
            else: line = candidate
        if line: lines.append(line)
        height = max(25, draw.textbbox((0, 0), 'Árvíz', font=font)[3] + 8)
        out = Image.new('RGB', (max(image.width, 300), image.height + len(lines) * height + 20), 'white')
        out.paste(image, ((out.width-image.width)//2, 0))
        draw = ImageDraw.Draw(out)
        for i, line in enumerate(lines):
            draw.text((12, image.height + 8 + i*height), line, fill='black', font=font)
        image = out
    image.save(destination, format='PNG')
