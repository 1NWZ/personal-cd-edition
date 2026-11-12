"""Render one fixed CD edition using source pixels and deterministic compositing."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

SIZE = (1500, 2000)
BASE = (1086, 1448)


def font(size, custom=None):
    if custom:
        # A missing user font must not silently turn Chinese into empty squares.
        return ImageFont.truetype(custom, size)
    candidates = [custom] if custom else []
    candidates += [
        '/System/Library/Fonts/Supplemental/Arial Narrow.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
        'DejaVuSans.ttf',
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def label(draw, xy, text, width, size, color, custom=None):
    selected = font(size, custom)
    while draw.textbbox((0, 0), text, font=selected)[2] > width and size > 10:
        size -= 1
        selected = font(size, custom)
    if draw.textbbox((0, 0), text, font=selected)[2] > width:
        raise ValueError('Text too long for its panel. Shorten title or track name.')
    draw.text(xy, text, font=selected, fill=color)


def star(draw, center, radius, color):
    x, y = center
    s = radius * .18
    draw.polygon([(x,y-radius),(x+s,y-s),(x+radius,y),(x+s,y+s),
                  (x,y+radius),(x-s,y+s),(x-radius,y),(x-s,y-s)], fill=color)


def paper_grain(panel):
    # Texture applies to blank stock, never to photograph pixels.
    pixels = np.asarray(panel).astype(np.int16)
    noise = np.random.default_rng(7).normal(0, .9, pixels.shape[:2])[..., None]
    return Image.fromarray(np.clip(pixels + noise, 0, 255).astype('uint8'))


def wrapped(draw, xy, text, width, size, color, custom=None):
    chosen = font(size, custom)
    lines, line = [], ''
    for word in text.split():
        trial = (line + ' ' + word).strip()
        if draw.textlength(trial, font=chosen) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    if len(lines) > 4:
        raise ValueError('Caption exceeds four lines; shorten it.')
    for i, line in enumerate(lines):
        label(draw, (xy[0], xy[1]+i*(size+4)), line, width, size, color, custom)


def load_region(spec, root):
    path = Path(spec['path'])
    if not path.is_absolute():
        path = root / path
    with Image.open(path) as raw:
        source = ImageOps.exif_transpose(raw).convert('RGB')
    crop = spec.get('crop', [0, 0, 1, 1])
    if len(crop) != 4 or not (0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1):
        raise ValueError('crop must be normalized [left, top, right, bottom].')
    box = tuple(round(v * source.size[i % 2]) for i, v in enumerate(crop))
    region = source.crop(box)
    if min(region.size) < 2:
        raise ValueError('Selected crop is too small.')
    return ImageOps.grayscale(region).convert('RGB')


def photo_panel(spec, root, size):
    # Containment preserves the selected region in full, without generative extension.
    photo = ImageOps.contain(load_region(spec, root), size, Image.Resampling.LANCZOS)
    panel = Image.new('RGB', size, '#f7f7f5')
    panel.paste(photo, ((size[0] - photo.width) // 2, (size[1] - photo.height) // 2))
    return panel


def project(canvas, panel, quad, shadow=True):
    scale = SIZE[0] / BASE[0]
    target = [(x * scale, y * scale) for x, y in quad]
    if shadow:
        layer = Image.new('RGBA', SIZE)
        d = ImageDraw.Draw(layer)
        d.polygon([(x + 5, y + 15) for x, y in target], fill=(0, 0, 0, 62))
        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(12)))
    source = [(0, 0), (panel.width, 0), (panel.width, panel.height), (0, panel.height)]
    rows, values = [], []
    for (x, y), (u, v) in zip(target, source):
        rows.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
        values.extend([u, v])
    coeffs = np.linalg.solve(np.array(rows), np.array(values))
    mapped = panel.convert('RGBA').transform(SIZE, Image.Transform.PERSPECTIVE, coeffs,
                                             Image.Resampling.BICUBIC)
    canvas.alpha_composite(mapped)
    return target


def abstract_disc(accent):
    # This mode uses only procedural geometry: no source pixels or faces can enter it.
    panel = Image.new('RGB', (700, 700), '#eeeeec')
    d = ImageDraw.Draw(panel)
    for i in range(32):
        radius = 90 + i * 8
        color = accent if i % 7 == 0 else '#999999'
        d.arc((350-radius, 350-radius, 350+radius, 350+radius), 20, 310, fill=color, width=2)
    for y in range(60, 650, 12):
        for x in range(60, 650, 12):
            if math.sin(x / 90) + math.cos(y / 80) > 0.8:
                d.ellipse((x, y, x+2, y+2), fill='#666666')
    return panel


def render(config, root):
    title = config['title']
    tracks = config['tracks']
    if not isinstance(title, str) or not title.strip() or not isinstance(tracks, list) or len(tracks) != 3:
        raise ValueError('Supply a nonempty title and exactly three track names.')
    if any(not isinstance(t, str) or not t.strip() for t in tracks):
        raise ValueError('Each track name must be nonempty text.')
    captions = config.get('captions')
    if not isinstance(captions, list) or len(captions) != 3 or any(not isinstance(t, str) or not t.strip() for t in captions):
        raise ValueError('Supply three nonempty original lyric captions.')
    accent = config['accent']
    if len(accent) != 7 or accent[0] != '#':
        raise ValueError('accent must be #RRGGBB.')
    int(accent[1:], 16)
    custom_font = config.get('font')
    if custom_font and not Path(custom_font).is_absolute():
        custom_font = str(root / custom_font)
    cover = config['cover']
    left = config.get('album_left', cover)
    right = config.get('album_right', cover)
    card = config.get('card', cover)
    disc = config.get('disc', {'mode': 'abstract'})
    mode = disc.get('mode', 'abstract')
    if mode not in ('abstract', 'verified_nonhuman'):
        raise ValueError('Disc mode must be abstract or verified_nonhuman.')
    if mode == 'verified_nonhuman' and disc.get('reviewed_no_human_face') is not True:
        raise ValueError('Disc photo requires visual review of the actual crop for human faces.')
    canvas = Image.new('RGBA', SIZE, 'white')

    # Lyric card: one photo region, title, and three short original lines.
    panel = paper_grain(Image.new('RGB', (600, 600), accent))
    panel.paste(photo_panel(card, root, (500, 240)), (50, 115))
    d = ImageDraw.Draw(panel)
    label(d, (40, 30), title, 520, 40, '#171717', custom_font)
    star(d, (540,62), 14, '#222222')
    for i, track in enumerate(tracks):
        label(d, (40, 385+i*65), f'{i+1:02d}  {track}', 520, 24, '#171717', custom_font)
        label(d, (65, 415+i*65), captions[i], 490, 17, '#171717', custom_font)
    project(canvas, panel, [(30,524),(404,472),(451,834),(79,881)])

    # Jewel case: fixed square print, rendered border and thin clear spine.
    panel = photo_panel(cover, root, (800, 800))
    d = ImageDraw.Draw(panel)
    d.rectangle((30,675,770,775), fill='#f5f5f2')
    label(d, (45,690), title, 700, 66, accent, custom_font)
    d.rectangle((0,0,799,799), outline='#aaaaaa', width=9)
    d.rectangle((12,12,788,788), outline='#eeeeee', width=3)
    d.line((25,10,25,790), fill='#bbbbbb', width=9)
    for x in range(28,52,4):
        d.line((x,20,x,780), fill='#dddddd', width=1)
    for y in (16,770):
        d.rounded_rectangle((205,y,265,y+10), radius=4, outline='#cccccc', width=2)
        d.rounded_rectangle((570,y,630,y+10), radius=4, outline='#cccccc', width=2)
    project(canvas, panel, [(430,180),(960,78),(1046,601),(492,710)])

    # Open album: photographic left page; photographic right page and track column.
    panel = photo_panel(left, root, (760, 820))
    d = ImageDraw.Draw(panel)
    d.rectangle((30,720,730,795), fill='#f5f5f2')
    label(d, (45,728), title, 680, 48, accent, custom_font)
    project(canvas, panel, [(38,932),(527,815),(548,1292),(64,1415)])
    panel = paper_grain(Image.new('RGB', (820, 820), '#f5f5f2'))
    panel.paste(photo_panel(right, root, (570, 820)), (0, 0))
    d = ImageDraw.Draw(panel)
    d.rectangle((585,25,800,75), fill=accent)
    label(d, (595,35), 'TRACKLIST', 195, 24, '#161616', custom_font)
    for i, track in enumerate(tracks):
        y = 130 + i*205
        label(d, (595,y), f'{i+1:02d}', 195, 28, '#222222', custom_font)
        label(d, (595,y+42), track, 195, 26, '#222222', custom_font)
        wrapped(d, (595,y+85), captions[i], 195, 18, '#444444', custom_font)
    star(d, (705,775), 18, accent)
    # A narrow fold shadow is printed onto the page edge, not synthesized into a photo.
    for x in range(14):
        d.line((x,0,x,819), fill=(215+x*2,)*3, width=1)
    project(canvas, panel, [(527,815),(969,747),(1060,1242),(548,1292)])

    # Disc sits foremost. Hole reveals the composited scene underneath it.
    panel = abstract_disc(accent) if mode == 'abstract' else photo_panel(disc, root, (700,700))
    d = ImageDraw.Draw(panel)
    d.rectangle((200,80,500,155), fill='#f5f5f2')
    label(d, (210,90), title, 280, 40, accent, custom_font)
    d.ellipse((3,3,697,697), outline='#999999', width=5)
    d.ellipse((15,15,685,685), outline=accent, width=2)
    for radius, color, width in [(98,'#b4b4b4',7),(89,'#eeeeee',6),(62,'#aaaaaa',4)]:
        d.ellipse((350-radius,350-radius,350+radius,350+radius), outline=color, width=width)
    mask = Image.new('L', panel.size)
    md = ImageDraw.Draw(mask)
    md.ellipse((0,0,699,699), fill=255)
    md.ellipse((298,298,402,402), fill=0)
    disc_rgba = panel.convert('RGBA')
    disc_rgba.putalpha(mask)
    scale = SIZE[0] / BASE[0]
    edge = round(464 * scale)
    disc_rgba = disc_rgba.resize((edge,edge), Image.Resampling.LANCZOS)
    xy = (round(40*scale), round(45*scale))
    shadow = Image.new('RGBA', SIZE)
    shadow.paste((0,0,0,65), (xy[0]+3,xy[1]+12,xy[0]+edge+3,xy[1]+edge+12),
                 disc_rgba.getchannel('A'))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    canvas.alpha_composite(disc_rgba, xy)
    return canvas.convert('RGB')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    config = json.loads(args.manifest.read_text(encoding='utf-8'))
    result = render(config, args.manifest.parent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output, format='PNG')


if __name__ == '__main__':
    main()
