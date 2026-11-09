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

    # ------------------------------------------------------------ konten
    def set_page(self, image_path: str | None, blocks, fit=True):
        self.scene().clear()
        self.boxes = []
        self.pix_item = None
        if not image_path:
            return
        pm = QPixmap.fromImage(QImage(image_path))
        self.pix_item = self.scene().addPixmap(pm)
        self.pix_item.setZValue(0)
        self.scene().setSceneRect(QRectF(pm.rect()))
        self.set_blocks(blocks)
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
        return max(0.05, min((vp.width() - 16) / r.width(), (vp.height() - 16) / r.height()))

    def fit(self):
        if self.pix_item:
            self.set_zoom(self.fit_scale())
            self.centerOn(self.pix_item)
            self.zoom_changed.emit(self.zoom())

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
    def set_draw_mode(self, on: bool):
        self.draw_mode = on and self.editable and not self.ghost
        self.viewport().setCursor(Qt.CrossCursor if self.draw_mode else Qt.ArrowCursor)

    def _item_at(self, pos):
        for it in self.items(pos):
            if isinstance(it, BoxItem) and it.isVisible():
                return it
            if isinstance(it, QGraphicsSimpleTextItem) and isinstance(it.parentItem(), BoxItem):
                return it.parentItem()
        return None

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
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
        if self._item_at(pos) is None and not self.draw_mode:
            self.viewport().setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._draw_rect is not None:
            r = self._draw_rect.rect().intersected(self.scene().sceneRect())
            self.scene().removeItem(self._draw_rect)
            self._draw_rect = None
            if r.width() > 8 and r.height() > 8:
                self.box_drawn.emit(r)
            return
        if self._pan is not None:
            clicked_empty = not self._pan["moved"] and e.button() == Qt.LeftButton
            self._pan = None
            if clicked_empty and self.selected is not None:   # klik area kosong = batal pilih
                self.select_block(None)
                self.block_selected.emit(None)
            return
        super().mouseReleaseEvent(e)
