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

def print_centimeters(value):
    """Egy cédulaoldal centiméterben. A vesszős magyar számot is elfogadja."""
    text = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'\d+(?:\.\d+)?', text):
        raise ValueError('A méret pozitív szám legyen, például 3 vagy 3,5.')
    number = float(text)
    if number < 2 or number > 20:
        raise ValueError('A cédula oldala 2 és 20 centiméter között legyen.')
    return number

def size_sentence(width_cm, height_cm):
    return (f'Nyomtatáskor {_cm_text(width_cm)} centiméter széles és '
            f'{_cm_text(height_cm)} centiméter magas.')

def _cm_text(number):
    return f'{number:.2f}'.rstrip('0').rstrip('.').replace('.', ',')

def label_origin_mm(page_w_mm, page_h_mm, width_cm, height_cm, margin_mm=10):
    """A cédula bal felső sarka a lapon, milliméterben. Ha nem fér el, nem nyomtatunk."""
    width, height = width_cm * 10, height_cm * 10
    usable_w = page_w_mm - 2 * margin_mm
    usable_h = page_h_mm - 2 * margin_mm
    if width > usable_w or height > usable_h:
        raise ValueError('A cédula nem fér el a lapon. Kisebb méretet adj meg, vagy nagyobb papírt válassz.')
    return margin_mm + (usable_w - width) / 2, margin_mm + (usable_h - height) / 2

def make_qr(url, caption, destination, width_cm=3, height_cm=3):
    image = render_qr(url, caption, width_cm, height_cm)
    save_png(image, destination, width_cm, height_cm)
    return image

def make_label(text, destination, width_cm=3, height_cm=3):
    image = render_label(text, width_cm, height_cm)
    save_png(image, destination, width_cm, height_cm)
    return image

def render_qr(url, caption, width_cm=3, height_cm=3):
    return _render_slip(normalize_url(url), caption, width_cm, height_cm)

def render_label(text, width_cm=3, height_cm=3):
    text = text.strip()
    if not text:
        raise ValueError('Add meg a tárgy nevét vagy a címke szövegét.')
    return _render_slip(text, text, width_cm, height_cm)

def save_png(image, destination, width_cm, height_cm):
    """A PNG pHYs adata a kért nyomtatási méret. A képpontok nem nyúlnak el."""
    width_cm = print_centimeters(width_cm)
    height_cm = print_centimeters(height_cm)
    dpi = (image.width * 2.54 / width_cm, image.height * 2.54 / height_cm)
    image.save(destination, format='PNG', dpi=dpi)

def _render_slip(payload, caption, width_cm, height_cm):
    import sys
    vendor = str(Path(__file__).parent / 'vendor')
    if vendor not in sys.path: sys.path.insert(0, vendor)
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    width_cm = print_centimeters(width_cm)
    height_cm = print_centimeters(height_cm)
    px_per_cm = 120
    canvas_w = max(1, round(width_cm * px_per_cm))
    canvas_h = max(1, round(height_cm * px_per_cm))
    pad = max(8, round(min(canvas_w, canvas_h) * 0.04))
    caption = caption.strip()
    font = _label_font(max(14, min(canvas_w, canvas_h) // 16))
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = _wrap(probe, caption, font, canvas_w - 2 * pad) if caption else []
    line_h = 0 if not lines else max(1, probe.textbbox((0, 0), 'Árvíz', font=font)[3] + 6)
    text_h = line_h * len(lines) + (pad if lines else 0)
    room = min(canvas_w - 2 * pad, canvas_h - 2 * pad - text_h)
    min_qr = round(1.8 * px_per_cm)
    if room < min_qr:
        raise ValueError('Ekkora cédulára a QR-kód és a felirat együtt nem fér ki olvashatóan. Nagyobb méretet adj meg.')
    image = _qr_square(qrcode, payload, room)
    out = Image.new('RGB', (canvas_w, canvas_h), 'white')
    out.paste(image, ((canvas_w - image.width) // 2, pad))
    if lines:
        draw = ImageDraw.Draw(out)
        top = pad + image.height + pad // 2
        for index, line in enumerate(lines):
            draw.text((pad, top + index * line_h), line, fill='black', font=font)
    return out

def _label_font(size):
    from PIL import ImageFont
    fontpath = Path('C:/Windows/Fonts/arial.ttf')
    if fontpath.exists():
        return ImageFont.truetype(str(fontpath), size)
    return ImageFont.load_default()

def _wrap(draw, caption, font, limit):
    words, lines, line = caption.split(), [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if line and draw.textbbox((0, 0), candidate, font=font)[2] > limit:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines

def _qr_square(qrcode, payload, side):
    from PIL import Image
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2, box_size=1)
    code.add_data(payload)
    code.make(fit=True)
    image = code.make_image(fill_color='black', back_color='white').convert('RGB')
    scale = max(1, side // image.width)
    target = image.width * scale
    return image.resize((target, target), Image.Resampling.NEAREST)


LABELS_DATA = store.CONFIG_DIR / 'targycimkek.json'

def load_labels():
    try:
        with LABELS_DATA.open(encoding='utf-8') as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return []
    if not isinstance(data, list) or not all(isinstance(x, str) and x.strip() for x in data):
        raise ValueError('A tárgycímkék listája sérült vagy nem olvasható.')
    return data

def save_labels(labels):
    if not isinstance(labels, list) or not all(isinstance(x, str) and x.strip() for x in labels):
        raise ValueError('Érvénytelen címkelista.')
    store.save_json(LABELS_DATA, labels)
