"""Kanvas halaman.

- Kursor panah biasa; di atas kotak teks berubah jadi ikon geser (panah empat), di tepi/sudut
  jadi ikon ubah ukuran.
- Geser tampilan: seret area kosong (atau tombol tengah mouse) — kursor tetap panah.
- Roda mouse = zoom.
- Kotak teks bisa dipindah dan diubah ukurannya dari ke-4 sisi dan ke-4 sudut.
- Kanvas "Hasil" memakai kotak tak terlihat (hanya tampak saat disorot/terpilih), jadi gambar
  hasil tetap bersih tapi balonnya tetap bisa diklik & digeser.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView)

HANDLE_PX = 9          # ukuran pegangan di layar (piksel), tidak ikut zoom
MIN_SIZE = 10

CURSORS = {
    "move": Qt.SizeAllCursor,
    "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor, "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor, "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
}


class BoxItem(QGraphicsRectItem):
    def __init__(self, block, index, canvas, ghost=False):
        super().__init__(0, 0, block.w, block.h)
        self.block = block
        self.canvas = canvas
        self.ghost = ghost
        self.selected = False
        self.hover = False
        self.setPos(block.x, block.y)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self._mode = None
        self._press_scene = None
        self._press_rect = None
        self.label = None
        if not ghost:
            self.label = QGraphicsSimpleTextItem(str(index), self)
            f = QFont()
            f.setBold(True)
            f.setPointSize(10)
            self.label.setFont(f)
            self.label.setBrush(QBrush(QColor("white")))
            self.label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            self.label.setPos(2, 0)
        self.refresh_style()

    # ------------------------------------------------------------ tampilan
    def color(self):
        if self.selected:
            return QColor("#ffbe0b")
        if self.block.kind == "title":
            return QColor("#c77dff")
        return QColor("#ff4d6d") if self.block.kind == "bubble" else QColor("#3a86ff")

    def refresh_style(self):
        col = self.color()
        if self.ghost and not (self.selected or self.hover):
            self.setPen(QPen(Qt.NoPen))
            self.setBrush(QBrush(Qt.transparent))   # tetap bisa diklik walau tak terlihat
        else:
            pen = QPen(col, 2.5 if self.selected else 1.6)
            pen.setCosmetic(True)
            if self.ghost and not self.selected:
                pen.setStyle(Qt.DashLine)
            self.setPen(pen)
            fill = QColor(col)
            fill.setAlpha(0 if self.ghost else (45 if self.selected else 25))
            self.setBrush(QBrush(fill))
        if self.label:
            self.label.setVisible(True)
        self.update()

    def handle_size(self):
        z = self.canvas.zoom() or 1
        return HANDLE_PX / z

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.label and not self.ghost:
            z = self.canvas.zoom() or 1
            painter.fillRect(QRectF(0, 0, 20 / z, 17 / z), self.color())
        if self.selected:  # 8 pegangan
            s = self.handle_size()
            painter.setPen(QPen(QColor("#1b1c21"), 0))
            painter.setBrush(QBrush(QColor("white")))
            for x, y in self._handle_points():
                painter.drawRect(QRectF(x - s / 2, y - s / 2, s, s))

    def _handle_points(self):
        r = self.rect()
        xs = (r.left(), r.center().x(), r.right())
        ys = (r.top(), r.center().y(), r.bottom())
        return [(x, y) for y in ys for x in xs if not (x == xs[1] and y == ys[1])]

    def boundingRect(self):
        s = self.handle_size()
        return super().boundingRect().adjusted(-s, -s, s, s)

    # ------------------------------------------------------------ zona kursor
    def zone(self, p: QPointF) -> str | None:
        r = self.rect()
        m = self.handle_size() * 0.9
        x, y = p.x(), p.y()
        if x < r.left() - m or x > r.right() + m or y < r.top() - m or y > r.bottom() + m:
            return None
        left, right = abs(x - r.left()) <= m, abs(x - r.right()) <= m
        top, bottom = abs(y - r.top()) <= m, abs(y - r.bottom()) <= m
        v = "t" if top else "b" if bottom else ""
        h = "l" if left else "r" if right else ""
        if v or h:
            return v + h
        return "move" if r.contains(p) else None

    def shape(self):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        s = self.handle_size() * 0.9
        path.addRect(self.rect().adjusted(-s, -s, s, s))
        return path

    def hoverEnterEvent(self, e):
        self.hover = True
        self.refresh_style()

    def hoverLeaveEvent(self, e):
        self.hover = False
        self.unsetCursor()
        self.refresh_style()

    def hoverMoveEvent(self, e):
        if self.canvas.draw_mode:
            self.setCursor(Qt.CrossCursor)
            return
        z = self.zone(e.pos())
        self.setCursor(CURSORS.get(z, Qt.ArrowCursor))

    # ------------------------------------------------------------ geser & ubah ukuran
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton or self.canvas.draw_mode:
            e.ignore()
            return
        self._mode = self.zone(e.pos()) or "move"
        self._press_scene = e.scenePos()
        self._press_rect = QRectF(self.pos(), self.rect().size())
        self.canvas.edit_started.emit(self.block)
        self.canvas.request_select(self.block)
        e.accept()

    def mouseMoveEvent(self, e):
        if not self._mode:
            return
        d = e.scenePos() - self._press_scene
        r = QRectF(self._press_rect)
        m = self._mode
        if m == "move":
            r.translate(d)
        else:
            if "l" in m:
                r.setLeft(min(r.right() - MIN_SIZE, r.left() + d.x()))
            if "r" in m:
                r.setRight(max(r.left() + MIN_SIZE, r.right() + d.x()))
            if "t" in m:
                r.setTop(min(r.bottom() - MIN_SIZE, r.top() + d.y()))
            if "b" in m:
                r.setBottom(max(r.top() + MIN_SIZE, r.bottom() + d.y()))
        self.prepareGeometryChange()
        self.setPos(r.topLeft())
        self.setRect(0, 0, r.width(), r.height())
        self.sync()
        self.canvas.block_moving.emit(self.block)

    def mouseReleaseEvent(self, e):
        if not self._mode:
            return
        moved = QRectF(self.pos(), self.rect().size()) != self._press_rect
        self._mode = None
        self.sync()
        if moved:
            self.canvas.block_geometry_changed.emit(self.block)
        e.accept()

    def mouseDoubleClickEvent(self, e):
        self.canvas.block_double_clicked.emit(self.block)

    def sync(self):
        """Tulis posisi/ukuran kotak ke data blok."""
        b = self.block
        nx, ny = int(round(self.pos().x())), int(round(self.pos().y()))
        nw, nh = int(round(self.rect().width())), int(round(self.rect().height()))
        if (nx, ny, nw, nh) != (b.x, b.y, b.w, b.h):
            if (nw, nh) == (b.w, b.h):         # digeser saja: kontur & area teks ikut digeser
                dx, dy = nx - b.x, ny - b.y
                if b.mask_poly:
                    b.mask_poly = [[px + dx, py + dy] for px, py in b.mask_poly]
                if b.text_rect:
                    b.text_rect = [b.text_rect[0] + dx, b.text_rect[1] + dy, b.text_rect[2], b.text_rect[3]]
            else:                              # diubah ukuran: kontur & area teks lama tidak berlaku
                b.mask_poly = []
                b.text_rect = []
            b.x, b.y, b.w, b.h = nx, ny, nw, nh

    def reload(self):
        """Ambil ulang posisi dari data blok (mis. setelah diubah di kanvas lain / undo)."""
        b = self.block
        self.prepareGeometryChange()
        self.setPos(b.x, b.y)
        self.setRect(0, 0, b.w, b.h)
        self.refresh_style()


class PageCanvas(QGraphicsView):
    block_selected = Signal(object)          # TextBlock atau None
    edit_started = Signal(object)            # sebelum kotak digeser/diubah (untuk undo)
    block_moving = Signal(object)            # selama digeser
    block_geometry_changed = Signal(object)  # setelah dilepas
    block_double_clicked = Signal(object)
    box_drawn = Signal(QRectF)
    zoom_changed = Signal(float)
    heal_stroke = Signal(list, int)          # healing brush: titik-titik goresan, jari-jari kuas
    region_done = Signal(list, object)       # pen / bentuk: titik poligon, posisi layar (QPoint) untuk menu
    patch_done = Signal(list)                # patch tool: titik poligon area yang ditambal
    line_stroke = Signal(list, int)          # (lama) garis langsung jadi
    draft_changed = Signal(bool)             # alat garis: ada / tidak ada pratinjau garis yang bisa diedit
    draft_menu = Signal(object)              # klik kanan di pratinjau garis -> posisi layar (QPoint)
    space_held = False                       # spasi ditahan = mode tangan (geser) sementara, semua kanvas

    def __init__(self, parent=None, editable=True, ghost=False):
        super().__init__(parent)
        self.editable = editable
        self.ghost = ghost
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor("#111214")))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setMouseTracking(True)
        self.viewport().setCursor(Qt.ArrowCursor)
        self.pix_item: QGraphicsPixmapItem | None = None
        self.boxes: list[BoxItem] = []
        self.show_boxes = True
        self.draw_mode = False
        self.selected = None
        self._draw_start = None
        self._draw_rect = None
        self._pan = None
        # alat sunting: "select" | "heal" | "pen" | "shape"
        self.tool = "select"
        self.shape_kind = "rect"                 # rect | ellipse
        self.brush = 14                          # jari-jari healing brush (px gambar)
        self._stroke = None                      # titik goresan heal
        self._stroke_item = None
        self._brush_item = None
        self._pen_pts = []
        self._pen_item = None
        self._pen_rubber = None
        self._shape_start = None
        self._shape_item = None
        self.line_color = "#000000"              # alat garis
        self._line_start = None
        # pratinjau garis (putus-putus) yang bisa diedit sebelum dijadikan garis sungguhan
        self.draft = {"pts": [], "closed": False, "smooth": True}
        self._draft_items = []
        self._draft_drag = None                  # {"i": indeks titik} / {"new": start_index}
        self._draft_page = None

    # ------------------------------------------------------------ konten
    def set_page(self, image_path: str | None, blocks, fit=True):
        self.scene().clear()
        self._draft_items = []
        if image_path != self._draft_page:
            had = bool(self.draft["pts"])
            self.draft = {"pts": [], "closed": False, "smooth": True}
            self._draft_drag = None
            self._draft_page = image_path
            if had:
                self.draft_changed.emit(False)
        self._stroke_item = self._pen_item = self._pen_rubber = self._shape_item = self._brush_item = None
        self._stroke, self._pen_pts = None, []
        self.boxes = []
        self.pix_item = None
        if not image_path:
            return
        from . import imgcache
        k = (image_path, imgcache.key(image_path))
        if getattr(self, "_pm_key", None) == k and getattr(self, "_pm", None) is not None:
            pm = self._pm                      # gambar yang sama: tidak perlu dibaca / diubah ulang
        else:
            pm = QPixmap.fromImage(imgcache.get(image_path))
            self._pm, self._pm_key = pm, k
        self.pix_item = self.scene().addPixmap(pm)
        self.pix_item.setZValue(0)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.set_blocks(blocks)
        self._draw_draft()
        if fit:
            self.fit()

    def set_blocks(self, blocks):
        for b in self.boxes:
            self.scene().removeItem(b)
        self.boxes = []
        if not self.editable:
            return
        for i, blk in enumerate(blocks, 1):
            item = BoxItem(blk, i, self, ghost=self.ghost)
            item.selected = blk is self.selected
            item.refresh_style()
            item.setVisible(self.show_boxes)
            if self.tool != "select":
                item.setAcceptedMouseButtons(Qt.NoButton)
            self.scene().addItem(item)
            self.boxes.append(item)

    def reload_boxes(self):
        for b in self.boxes:
            b.reload()

    def set_boxes_visible(self, v: bool):
        self.show_boxes = v
        for b in self.boxes:
            b.setVisible(v)

    def select_block(self, block, ensure_visible=True):
        self.selected = block
        for b in self.boxes:
            b.selected = b.block is block
            b.refresh_style()
            if b.selected and ensure_visible:
                self.ensureVisible(b, 40, 40)

    def request_select(self, block):
        if block is not self.selected:
            self.select_block(block, ensure_visible=False)
            self.block_selected.emit(block)

    # ------------------------------------------------------------ zoom
    def fit_scale(self) -> float:
        if not self.pix_item:
            return 1.0
        r = self.pix_item.boundingRect()
        vp = self.viewport().rect()
        if r.width() <= 0 or r.height() <= 0:
            return 1.0
        sw, sh = (vp.width() - 16) / r.width(), (vp.height() - 16) / r.height()
        if self.is_strip():
            return max(0.05, sw)          # strip webtoon panjang: pas lebar, gulir ke bawah
        return max(0.05, min(sw, sh))

    def is_strip(self) -> bool:
        """Gambar webtoon (manhwa/manhua) yang jauh lebih tinggi dari lebarnya."""
        if not self.pix_item:
            return False
        r = self.pix_item.boundingRect()
        return r.width() > 0 and r.height() / r.width() > 2.5

    def fit(self):
        if self.pix_item:
            self.set_zoom(self.fit_scale())
            self._center_or_top()
            self.zoom_changed.emit(self.zoom())

    def _center_or_top(self):
        if self.is_strip():   # mulai dari atas strip
            r = self.pix_item.sceneBoundingRect()
            self.centerOn(r.center().x(), r.top() + self.viewport().height() / (2 * max(self.zoom(), 1e-6)))
        else:
            self.centerOn(self.pix_item)

    def zoom(self) -> float:
        return self.transform().m11()

    def set_zoom(self, s: float, emit=False):
        s = max(0.05, min(8.0, s))
        self.setTransform(QTransform.fromScale(s, s))
        for b in self.boxes:
            b.prepareGeometryChange()   # ukuran pegangan bergantung zoom
        if emit:
            self.zoom_changed.emit(s)

    def wheelEvent(self, e):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        if 0.05 < self.zoom() * f < 8:
            self.scale(f, f)
            for b in self.boxes:
                b.prepareGeometryChange()
            self.zoom_changed.emit(self.zoom())

    # ------------------------------------------------------------ mouse: gambar kotak / geser tampilan
    # ------------------------------------------------------------ alat sunting
    def set_tool(self, tool: str):
        self.cancel_tool()
        self.tool = tool if self.pix_item is not None or tool == "select" else tool
        if tool != "select":
            self.draw_mode = False
        self.viewport().setCursor(self._tool_cursor())
        for b in self.boxes:      # kotak teks tidak menghalangi saat menyunting gambar
            b.setAcceptedMouseButtons(Qt.NoButton if tool != "select" else Qt.AllButtons)
        if tool != "heal" and self._brush_item is not None:
            self.scene().removeItem(self._brush_item)
            self._brush_item = None

    def _tool_cursor(self):
        if PageCanvas.space_held:
            return Qt.ClosedHandCursor if self._pan is not None else Qt.OpenHandCursor
        if self.draw_mode:
            return Qt.CrossCursor
        return {"heal": Qt.BlankCursor, "pen": Qt.CrossCursor, "shape": Qt.CrossCursor,
                "line": Qt.CrossCursor, "patch": Qt.CrossCursor}.get(self.tool, Qt.ArrowCursor)

    def set_space(self, on: bool):
        """Spasi ditahan: tangan untuk menggeser gambar tanpa mengganti alat."""
        PageCanvas.space_held = bool(on)
        if self._brush_item is not None and self._brush_item.scene() is self.scene():
            self._brush_item.setVisible(not on)
        self.viewport().setCursor(self._tool_cursor())

    def cancel_tool(self):
        for name in ("_stroke_item", "_pen_item", "_pen_rubber", "_shape_item"):
            it = getattr(self, name)
            if it is not None and it.scene() is self.scene():
                self.scene().removeItem(it)
            setattr(self, name, None)
        self._stroke, self._pen_pts, self._shape_start, self._line_start = None, [], None, None

    def set_brush(self, r: int):
        self.brush = max(1, int(r))
        self._update_brush_cursor(None)

    def _pen(self, color, width=2, style=Qt.SolidLine, cosmetic=True):
        p = QPen(QColor(color), width, style)
        p.setCosmetic(cosmetic)
        return p

    def _update_brush_cursor(self, scene_pos):
        if self.tool != "heal":
            return
        if self._brush_item is None or self._brush_item.scene() is not self.scene():
            self._brush_item = self.scene().addEllipse(QRectF(0, 0, 1, 1), self._pen("#ffffff", 1.5))
            self._brush_item.setZValue(40)
        if scene_pos is not None:
            r = self.brush
            self._brush_item.setRect(QRectF(scene_pos.x() - r, scene_pos.y() - r, 2 * r, 2 * r))

    def _stroke_path(self):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        pts = self._stroke or []
        if pts:
            path.moveTo(*pts[0])
            for p in pts[1:]:
                path.lineTo(*p)
        return path

    def _pen_path(self, closing=False):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        if self._pen_pts:
            path.moveTo(*self._pen_pts[0])
            for p in self._pen_pts[1:]:
                path.lineTo(*p)
            if closing:
                path.closeSubpath()
        return path

    def _finish_pen(self, screen_pos=None):
        pts = [list(map(int, p)) for p in self._pen_pts]
        self.cancel_tool()
        if len(pts) >= 3:
            self.region_done.emit(pts, screen_pos)

    def _tool_press(self, e) -> bool:
        if self.tool == "select" or self.pix_item is None:
            return False
        if self.tool == "line":
            return self._line_press(e)
        sp = self.mapToScene(e.position().toPoint())
        x, y = sp.x(), sp.y()
        if e.button() == Qt.RightButton:
            if self.tool == "pen" and self._pen_pts:
                self._finish_pen(e.globalPosition().toPoint())
            else:
                self.cancel_tool()
            return True
        if e.button() != Qt.LeftButton:
            return False
        if self.tool == "patch":                 # lasso: seret melingkari area
            self._stroke = [(x, y)]
            pen = self._pen("#ffd166", 1.5, Qt.DashLine)
            self._stroke_item = self.scene().addPath(self._stroke_path(), pen, QBrush(QColor(255, 209, 102, 45)))
            self._stroke_item.setZValue(30)
            return True
        if self.tool == "heal":
            self._stroke = [(x, y)]
            pen = QPen(QColor(255, 77, 109, 120), 2 * self.brush, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self._stroke_item = self.scene().addPath(self._stroke_path(), pen)
            self._stroke_item.setZValue(30)
            return True
        if self.tool == "pen":
            if len(self._pen_pts) >= 3:
                fx, fy = self._pen_pts[0]
                tol = 8 / max(self.zoom(), 1e-6)
                if abs(fx - x) < tol and abs(fy - y) < tol:     # klik titik pertama = tutup
                    self._finish_pen(e.globalPosition().toPoint())
                    return True
            self._pen_pts.append((x, y))
            if self._pen_item is None:
                self._pen_item = self.scene().addPath(self._pen_path(), self._pen("#06d6a0", 2))
                self._pen_item.setZValue(30)
            else:
                self._pen_item.setPath(self._pen_path())
            return True
        if self.tool == "shape":
            self._shape_start = sp
            pen = self._pen("#06d6a0", 2, Qt.DashLine)
            add = self.scene().addEllipse if self.shape_kind == "ellipse" else self.scene().addRect
            self._shape_item = add(QRectF(sp, sp), pen, QBrush(QColor(6, 214, 160, 40)))
            self._shape_item.setZValue(30)
            return True
        return False

    def _tool_move(self, e) -> bool:
        if self.tool == "select" or self.pix_item is None:
            return False
        if self.tool == "line":
            return self._line_move(e)
        sp = self.mapToScene(e.position().toPoint())
        if self.tool == "patch":
            if self._stroke is not None:
                lx, ly = self._stroke[-1]
                if abs(sp.x() - lx) + abs(sp.y() - ly) >= 2.0 / max(self.zoom(), 1e-6):
                    self._stroke.append((sp.x(), sp.y()))
                    path = self._stroke_path()
                    path.closeSubpath()
                    self._stroke_item.setPath(path)
            return True
        if self.tool == "heal":
            self._update_brush_cursor(sp)
            if self._stroke is not None:
                lx, ly = self._stroke[-1]
                if abs(sp.x() - lx) + abs(sp.y() - ly) >= max(1.0, self.brush * 0.25):
                    self._stroke.append((sp.x(), sp.y()))
                    self._stroke_item.setPath(self._stroke_path())
            return True
        if self.tool == "pen" and self._pen_pts:
            from PySide6.QtCore import QLineF
            lx, ly = self._pen_pts[-1]
            if self._pen_rubber is None:
                self._pen_rubber = self.scene().addLine(QLineF(lx, ly, sp.x(), sp.y()),
                                                        self._pen("#06d6a0", 1, Qt.DashLine))
                self._pen_rubber.setZValue(30)
            else:
                self._pen_rubber.setLine(QLineF(lx, ly, sp.x(), sp.y()))
            return True
        if self.tool == "shape" and self._shape_item is not None:
            r = QRectF(self._shape_start, sp).normalized()
            if e.modifiers() & Qt.ShiftModifier:        # Shift = persegi / lingkaran
                side = max(r.width(), r.height())
                r.setWidth(side)
                r.setHeight(side)
            self._shape_item.setRect(r)
            return True
        return self.tool in ("pen", "shape", "line", "patch")

    def _tool_release(self, e) -> bool:
        if self.tool == "select" or self.pix_item is None:
            return False
        if self.tool == "line":
            return self._line_release(e)
        if self.tool == "heal" and self._stroke is not None:
            pts = [[int(round(x)), int(round(y))] for x, y in self._stroke]
            self.cancel_tool()
            self.heal_stroke.emit(pts, int(self.brush))
            return True
        if self.tool == "patch" and self._stroke is not None:
            pts = [[int(round(x)), int(round(y))] for x, y in self._stroke]
            self.cancel_tool()
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            if len(pts) >= 3 and max(xs) - min(xs) >= 4 and max(ys) - min(ys) >= 4:
                self.patch_done.emit(pts)
            return True
        if self.tool == "shape" and self._shape_item is not None:
            r = self._shape_item.rect().intersected(self.scene().sceneRect())
            kind = self.shape_kind
            self.cancel_tool()
            if r.width() < 4 or r.height() < 4:
                return True
            if kind == "ellipse":
                import math
                cx, cy, rx, ry = r.center().x(), r.center().y(), r.width() / 2, r.height() / 2
                pts = [[int(cx + rx * math.cos(t * math.pi / 36)), int(cy + ry * math.sin(t * math.pi / 36))]
                       for t in range(72)]
            else:
                pts = [[int(r.left()), int(r.top())], [int(r.right()), int(r.top())],
                       [int(r.right()), int(r.bottom())], [int(r.left()), int(r.bottom())]]
            self.region_done.emit(pts, e.globalPosition().toPoint())
            return True
        return self.tool in ("pen", "heal", "shape", "line", "patch")

    # ------------------------------------------------------------ alat garis: pratinjau yang bisa diedit
    def has_draft(self) -> bool:
        return len(self.draft["pts"]) >= 2

    def clear_draft(self):
        had = bool(self.draft["pts"])
        self.draft = {"pts": [], "closed": False, "smooth": True}
        self._draft_drag = None
        self._draw_draft()
        if had:
            self.draft_changed.emit(False)

    def take_draft(self) -> dict:
        d = {"pts": [[round(x, 1), round(y, 1)] for x, y in self.draft["pts"]],
             "closed": bool(self.draft["closed"]), "smooth": bool(self.draft["smooth"])}
        self.clear_draft()
        return d

    def set_draft_option(self, key, value):
        self.draft[key] = value
        self._draw_draft()

    def _tol(self, px=7.0):
        return px / max(self.zoom(), 1e-6)

    def _draw_draft(self):
        from PySide6.QtGui import QPainterPath
        from PySide6.QtWidgets import QGraphicsItem
        sc = self.scene()
        for it in self._draft_items:
            if it.scene() is sc:
                sc.removeItem(it)
        self._draft_items = []
        pts = self.draft["pts"]
        if not pts or self.pix_item is None:
            return
        from core.edits import spline
        curve = spline(pts, self.draft["closed"] and len(pts) >= 3, self.draft["smooth"],
                       step=max(1.0, 2.0 / max(self.zoom(), 1e-6)))
        path = QPainterPath()
        path.moveTo(float(curve[0][0]), float(curve[0][1]))
        for x, y in curve[1:]:
            path.lineTo(float(x), float(y))
        # bayangan putih tipis + garis putus-putus warna garis -> terlihat di latar gelap & terang
        under = QPen(QColor(255, 255, 255, 200), 3.5)
        under.setCosmetic(True)
        dash = QPen(QColor(self.line_color if QColor(self.line_color).lightness() < 200 else "#ff4d6d"), 1.8,
                    Qt.CustomDashLine)
        dash.setDashPattern([5, 4])
        dash.setCosmetic(True)
        for pen in (under, dash):
            it = sc.addPath(path, pen)
            it.setZValue(35)
            self._draft_items.append(it)
        for i, (x, y) in enumerate(pts):
            first = i == 0
            it = sc.addRect(QRectF(-4, -4, 8, 8), self._pen("#ff4d6d" if first else "#06d6a0", 1.5),
                            QBrush(QColor("#ffffff")))
            it.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            it.setPos(x, y)
            it.setZValue(36)
            self._draft_items.append(it)

    def _hit_point(self, sp) -> int:
        tol = self._tol(7)
        best, bi = tol, -1
        for i, (x, y) in enumerate(self.draft["pts"]):
            d = abs(x - sp.x()) + abs(y - sp.y())
            if d <= best * 1.4:
                best, bi = d, i
        return bi

    def _hit_segment(self, sp) -> int:
        """Indeks sisipan bila titik dekat ke ruas garis (-1 bila tidak)."""
        import numpy as np
        pts = self.draft["pts"]
        if len(pts) < 2:
            return -1
        P = np.array(pts, np.float32)
        segs = list(range(len(P) - 1)) + ([len(P) - 1] if self.draft["closed"] and len(P) >= 3 else [])
        q = np.array([sp.x(), sp.y()], np.float32)
        best, bi = self._tol(6), -1
        for i in segs:
            a, b = P[i], P[(i + 1) % len(P)]
            ab = b - a
            t = float(np.clip(np.dot(q - a, ab) / max(1e-6, np.dot(ab, ab)), 0, 1))
            d = float(np.linalg.norm(a + t * ab - q))
            if d < best:
                best, bi = d, i + 1
        return bi

    def _line_press(self, e) -> bool:
        sp = self.mapToScene(e.position().toPoint())
        pts = self.draft["pts"]
        if e.button() == Qt.RightButton:
            if pts:
                self.draft_menu.emit(e.globalPosition().toPoint())
            return True
        if e.button() != Qt.LeftButton:
            return False
        self._last_added = None
        i = self._hit_point(sp)
        if i >= 0:
            if e.modifiers() & Qt.AltModifier:                 # Alt + klik titik = hapus titik
                pts.pop(i)
                self._after_draft_edit()
                return True
            if i == 0 and len(pts) >= 3 and not self.draft["closed"] and not (e.modifiers() & Qt.ControlModifier):
                self.draft["closed"] = True                    # klik titik awal = tutup bentuk
                self._after_draft_edit()
                return True
            self._draft_drag = {"i": i}
            return True
        if e.modifiers() & Qt.ControlModifier or (pts and self.draft["closed"]):
            k = self._hit_segment(sp)
            if k >= 0:                                         # Ctrl + klik di garis = tambah titik
                pts.insert(k, (sp.x(), sp.y()))
                self._draft_drag = {"i": k}
                self._after_draft_edit()
                return True
            if self.draft["closed"]:
                return True
        # klik = tambah titik di ujung; seret = gambar bebas (disederhanakan jadi titik-titik)
        pts.append((sp.x(), sp.y()))
        self._last_added = (len(pts) - 1, sp.x(), sp.y())
        self._draft_drag = {"new": len(pts) - 1, "start": (sp.x(), sp.y())}
        self._after_draft_edit()
        return True

    def _line_move(self, e) -> bool:
        if not self._draft_drag:
            return True
        sp = self.mapToScene(e.position().toPoint())
        pts = self.draft["pts"]
        if "i" in self._draft_drag:
            i = self._draft_drag["i"]
            if 0 <= i < len(pts):
                pts[i] = (sp.x(), sp.y())
                self._draw_draft()
            return True
        k = self._draft_drag["new"]
        if e.modifiers() & Qt.ShiftModifier:                   # Shift = ruas lurus
            del pts[k + 1:]
            pts.append((sp.x(), sp.y()))
        else:
            lx, ly = pts[-1]
            if abs(sp.x() - lx) + abs(sp.y() - ly) >= self._tol(2):
                pts.append((sp.x(), sp.y()))
        self._draw_draft()
        return True

    def _line_release(self, e) -> bool:
        d = self._draft_drag
        self._draft_drag = None
        if d and "new" in d:
            pts = self.draft["pts"]
            k = d["new"]
            seg = pts[k:]
            if len(seg) > 2:      # goresan bebas -> sedikit titik jangkar supaya mudah diedit
                import cv2
                import numpy as np
                arr = np.array(seg, np.float32).reshape(-1, 1, 2)
                simp = cv2.approxPolyDP(arr, self._tol(2.5), False).reshape(-1, 2)
                self.draft["pts"] = pts[:k] + [(float(x), float(y)) for x, y in simp]
            self._after_draft_edit()
        return True

    def _after_draft_edit(self):
        if len(self.draft["pts"]) < 3:
            self.draft["closed"] = False
        self._draw_draft()
        self.draft_changed.emit(bool(self.draft["pts"]))

    def mouseDoubleClickEvent(self, e):
        if self.tool == "line" and self.draft["pts"]:
            sp = self.mapToScene(e.position().toPoint())
            la = getattr(self, "_last_added", None)
            pts = self.draft["pts"]
            if la and la[0] == len(pts) - 1 and abs(la[1] - sp.x()) + abs(la[2] - sp.y()) < self._tol(6):
                pts.pop()                                      # titik dari klik pertama klik-dua-kali
            self._last_added = None
            i = self._hit_point(sp)
            if i >= 0:                                         # klik dua kali titik = hapus titik
                self.draft["pts"].pop(i)
            else:
                k = self._hit_segment(sp)
                if k >= 0:                                     # klik dua kali garis = tambah titik
                    self.draft["pts"].insert(k, (sp.x(), sp.y()))
            self._after_draft_edit()
            return
        if self.tool == "pen" and len(self._pen_pts) >= 2:
            sp = self.mapToScene(e.position().toPoint())
            if len(self._pen_pts) < 3:
                self._pen_pts.append((sp.x(), sp.y()))
            self._finish_pen(e.globalPosition().toPoint())
            return
        super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        if self.tool == "line" and self.draft["pts"]:
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.draft_menu.emit("commit")
                return
            if e.key() == Qt.Key_Escape:
                self.clear_draft()
                return
            if e.key() in (Qt.Key_Backspace, Qt.Key_Delete):
                self.draft["pts"].pop()
                self._after_draft_edit()
                return
        if self.tool == "pen":
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and len(self._pen_pts) >= 3:
                self._finish_pen(None)
                return
            if e.key() == Qt.Key_Escape:
                self.cancel_tool()
                return
            if e.key() == Qt.Key_Backspace and self._pen_pts:
                self._pen_pts.pop()
                if self._pen_item is not None:
                    self._pen_item.setPath(self._pen_path())
                return
        if e.key() == Qt.Key_Escape and self.tool != "select":
            self.cancel_tool()
            return
        super().keyPressEvent(e)

    def leaveEvent(self, e):
        if self._brush_item is not None and self._brush_item.scene() is self.scene():
            self._brush_item.setRect(QRectF(0, 0, 0, 0))
        super().leaveEvent(e)

    def set_draw_mode(self, on: bool):
        self.draw_mode = on and self.editable and not self.ghost
        self.viewport().setCursor(self._tool_cursor())

    def _item_at(self, pos):
        for it in self.items(pos):
            if isinstance(it, BoxItem) and it.isVisible():
                return it
            if isinstance(it, QGraphicsSimpleTextItem) and isinstance(it.parentItem(), BoxItem):
                return it.parentItem()
        return None

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if PageCanvas.space_held and e.button() == Qt.LeftButton:     # spasi + seret = geser gambar
            self._pan = {"start": pos, "h": self.horizontalScrollBar().value(),
                         "v": self.verticalScrollBar().value(), "moved": True, "space": True}
            self.viewport().setCursor(Qt.ClosedHandCursor)
            e.accept()
            return
        if e.button() != Qt.MiddleButton and self._tool_press(e):
            return
        if self.draw_mode and e.button() == Qt.LeftButton and self.pix_item:
            self._draw_start = self.mapToScene(pos)
            pen = QPen(QColor("#06d6a0"), 2, Qt.DashLine)
            pen.setCosmetic(True)
            self._draw_rect = self.scene().addRect(QRectF(self._draw_start, self._draw_start), pen)
            self._draw_rect.setZValue(20)
            return
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and self._item_at(pos) is None):
            self._pan = {"start": pos, "h": self.horizontalScrollBar().value(),
                         "v": self.verticalScrollBar().value(), "moved": False}
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._pan is None and self._tool_move(e):
            return
        if self._draw_rect is not None:
            self._draw_rect.setRect(QRectF(self._draw_start, self.mapToScene(pos)).normalized())
            return
        if self._pan is not None:
            d = pos - self._pan["start"]
            if abs(d.x()) + abs(d.y()) > 2:
                self._pan["moved"] = True
            self.horizontalScrollBar().setValue(self._pan["h"] - d.x())
            self.verticalScrollBar().setValue(self._pan["v"] - d.y())
            return
        super().mouseMoveEvent(e)
        if self._item_at(pos) is None and not self.draw_mode and self.tool == "select" \
                and not PageCanvas.space_held:
            self.viewport().setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._pan is None and e.button() != Qt.MiddleButton and self._tool_release(e):
            return
        if self._draw_rect is not None:
            r = self._draw_rect.rect().intersected(self.scene().sceneRect())
            self.scene().removeItem(self._draw_rect)
            self._draw_rect = None
            if r.width() > 8 and r.height() > 8:
                self.box_drawn.emit(r)
            return
        if self._pan is not None:
            clicked_empty = not self._pan["moved"] and e.button() == Qt.LeftButton
            was_space = self._pan.get("space")
            self._pan = None
            if was_space:
                self.viewport().setCursor(self._tool_cursor())
                return
            if clicked_empty and self.selected is not None:   # klik area kosong = batal pilih
                self.select_block(None)
                self.block_selected.emit(None)
            return
        super().mouseReleaseEvent(e)
