"""Ikon garis sederhana (SVG 24x24) untuk toolbar, digambar sendiri."""
from __future__ import annotations

from functools import lru_cache

_S = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" '
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

ICONS = {
    "open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/>'
             '<path d="M21 17l-5-5-9 8"/>',
    "project": '<path d="M5 3h10l4 4v14H5z"/><path d="M15 3v4h4"/><path d="M8 12h8M8 16h6"/>',
    "save": '<path d="M4 6a2 2 0 0 1 2-2h10.2L20 7.8V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/>'
            '<path d="M8 4v4.5h7V4"/><path d="M13 5.5v1.5"/><rect x="7.5" y="12.5" width="9" height="7.5" rx="1"/>'
            '<path d="M10 15.5h4M10 18h2.5"/>',
    "save_dirty": '<path d="M4 6a2 2 0 0 1 2-2h10.2L20 7.8V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/>'
                  '<path d="M8 4v4.5h7V4"/><path d="M13 5.5v1.5"/><rect x="7.5" y="12.5" width="9" height="7.5" rx="1"/>'
                  '<circle cx="19.5" cy="4.5" r="3" fill="#ff9a62" stroke="#131722" stroke-width="1.5"/>',
    "export": '<path d="M12 15V3"/><path d="M7 8l5-5 5 5"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3'
                'M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "box": '<path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4"/><path d="M9 12h6M12 9v6"/>',
    "translate": '<path d="M3 5h9M7.5 3v2M10 5c-1 4-3.5 7-7 8.5"/><path d="M5.5 9c1 2 2.8 3.6 5 4.5"/>'
                 '<path d="M13 21l4-9 4 9M14.5 18h5"/>',
    "zap": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "zapall": '<path d="M10 2L3 12h5l-1 6 7-9H9z"/><path d="M17 8l-4 6h3l-1 4 5-7h-3z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1"/>',
    "prev": '<path d="M15 6l-6 6 6 6"/>',
    "next": '<path d="M9 6l6 6-6 6"/>',
    "split": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "fit": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
    "book": '<path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a2 2 0 0 0-2 2v14'
            'a2 2 0 0 1 2-2h6z"/>',
    "update": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "scan": '<path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4"/><path d="M8 10h8M8 14h5"/>',
    "log": '<path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/>'
           '<circle cx="4" cy="18" r="1"/>',
    "steps": '<circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="12" r="2"/>'
             '<path d="M8 6h4l4 5M8 18h4l4-5"/>',
    "bold": '<path d="M7 4h6a4 4 0 0 1 0 8H7zM7 12h7a4 4 0 0 1 0 8H7z"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "italic": '<path d="M19 4h-9M14 20H5M15 4L9 20"/>',
    "mv_left": '<path d="M14 6l-6 6 6 6"/>',
    "mv_right": '<path d="M10 6l6 6-6 6"/>',
    "mv_up": '<path d="M6 14l6-6 6 6"/>',
    "mv_down": '<path d="M6 10l6 6 6-6"/>',
    "mv_reset": '<circle cx="12" cy="12" r="2.2"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
    "eyedrop": '<path d="M14 4l6 6M17 7l-9.5 9.5L5 19l-1 1M7.5 16.5L6 18"/><path d="M12.5 6.5l5 5"/>',
    "wand": '<path d="M4 20L15 9"/><path d="M15 4v3M13.5 5.5h3M19 9v2M18 10h2M11 3v1.5M10.25 3.75h1.5"/>',
    "gradient": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 20L20 4M4 14l10-10M10 20l10-10"/>',
    "cursor": '<path d="M5 3l14 8-6 1.5L10 19z"/>',
    # pena (mata pena + celah + pegangan) — dari pen-mono.svg (512 px) diperkecil ke 24 px
    "pen": '<g stroke-width="1.5"><path d="M12 2.8L17.34 11.72 14.91 18.75H9.09L6.66 11.72Z"/>'
           '<path d="M12 2.8V10.78"/><rect x="8.44" y="18.75" width="7.13" height="2.63" rx=".47"/></g>'
           '<circle cx="12" cy="12.28" r=".7" stroke-width="1.4"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "line": '<path d="M4 19c3-1 4-6 7-8s5 1 9-6"/><circle cx="4" cy="19" r="1.6"/><circle cx="20" cy="5" r="1.6"/>',
    "hand": '<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11"/><path d="M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5"/>'
            '<path d="M14 10.5V5.5a1.5 1.5 0 0 1 3 0V12"/><path d="M17 9.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-1'
            'a7 7 0 0 1-5.5-2.7L4 15a1.5 1.5 0 0 1 2.3-1.9L8 15"/>',
    "shape": '<rect x="3" y="3" width="11" height="11" rx="1"/><circle cx="15.5" cy="15.5" r="5.5"/>',
    "heal": '<rect x="2.5" y="8.5" width="19" height="7" rx="3.5" transform="rotate(-45 12 12)"/>'
            '<path d="M10.5 10.5l3 3M13.5 10.5l-3 3"/>',
    "close": '<path d="M7 7l10 10M17 7L7 17"/>',
    "patch": '<path d="M4 9c0-3 3-5 6-5s7 1 8 4-1 5-4 6-9 1-10-1-0-2 0-4z" stroke-dasharray="2 2"/>'
             '<rect x="12" y="13" width="8" height="7" rx="1"/>',
    "al_left": '<path d="M4 6h16M4 10h10M4 14h16M4 18h10"/>',
    "al_center": '<path d="M4 6h16M7 10h10M4 14h16M7 18h10"/>',
    "al_right": '<path d="M4 6h16M10 10h10M4 14h16M10 18h10"/>',
    "folderout": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
                 '<path d="M10 13h6M13 10l3 3-3 3"/>',
}


def svg(name: str, color: str = "#d5dbea") -> str:
    return _S.format(c=color, body=ICONS[name])


DISABLED = "#3e4558"      # warna ikon saat tombol nonaktif (redup, hampir menyatu dengan latar)


def _render(name: str, color: str, size: int, dim: bool = False):
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    src = svg(name, color)
    if dim:   # semua warna (termasuk titik merah) jadi redup
        import re
        src = re.sub(r'(stroke|fill)="#[0-9A-Fa-f]{3,8}"', lambda m: f'{m.group(1)}="{DISABLED}"', src)
    r = QSvgRenderer(QByteArray(src.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    r.render(p)
    p.end()
    return pm


@lru_cache(maxsize=None)
def icon(name: str, color: str = "#d5dbea", size: int = 40):
    """QIcon dari SVG (butuh QtSvg — sudah termasuk di PySide6). Punya gambar khusus untuk keadaan
    nonaktif (redup), jadi tombol yang tidak bisa ditekan benar-benar terlihat mati."""
    from PySide6.QtGui import QIcon
    ic = QIcon()
    ic.addPixmap(_render(name, color, size), QIcon.Normal, QIcon.Off)
    ic.addPixmap(_render(name, color, size), QIcon.Normal, QIcon.On)
    dim = _render(name, color, size, dim=True)
    ic.addPixmap(dim, QIcon.Disabled, QIcon.Off)
    ic.addPixmap(dim, QIcon.Disabled, QIcon.On)
    return ic
