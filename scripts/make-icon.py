"""Iconiţa: curbe de nivel peste conturul unui cap. Ce face aplicaţia, desenat."""
import math, pathlib
H, P, I, T = '#4E6A57', '#F5EFE3', '#6B5544', '#C97F5F'

def cap(s):
    """Contur de cap, scalat spre centru cu factorul s."""
    pts = []
    for i in range(72):
        a = 2 * math.pi * i / 72
        # ovoid: mai lat sus, îngustat spre bărbie
        rx, ry = 150, 195
        k = 1.0 + 0.16 * math.cos(a - math.pi / 2)
        x = 256 + rx * k * math.cos(a) * s
        y = 250 + ry * (1.0 - 0.10 * math.cos(a - math.pi / 2)) * math.sin(a) * s
        pts.append(f'{x:.1f},{y:.1f}')
    return 'M ' + ' L '.join(pts) + ' Z'

niv = [1.0, 0.87, 0.74, 0.61, 0.48, 0.35, 0.22]
cai = []
for i, s in enumerate(niv):
    f = i / (len(niv) - 1)
    cul = P if i == 0 else f'#{int(245-30*f):02X}{int(239-40*f):02X}{int(227-55*f):02X}'
    cai.append(f'  <path d="{cap(s)}" fill="{cul}" stroke="{I}" stroke-width="7" '
               f'stroke-linejoin="round"/>')
cai.append(f'  <ellipse cx="256" cy="300" rx="26" ry="34" fill="{T}" stroke="{I}" stroke-width="7"/>')

svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">\n'
       f'  <rect width="512" height="512" rx="112" fill="{H}"/>\n' + '\n'.join(cai) + '\n</svg>\n')
pathlib.Path('web/icons/icon.svg').write_text(svg, encoding='utf-8')

mask = svg.replace('rx="112" ', '').replace('<rect width="512" height="512"',
    '<rect width="512" height="512"')
# maskable: semnul la 78%, în cercul sigur
inner = '\n'.join(cai)
mask = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">\n'
        f'  <rect width="512" height="512" fill="{H}"/>\n'
        f'  <g transform="translate(56.3,56.3) scale(0.78)">\n{inner}\n  </g>\n</svg>\n')
pathlib.Path('web/icons/icon-maskable.svg').write_text(mask, encoding='utf-8')
print('svg scrise')
