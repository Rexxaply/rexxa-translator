"""Kanvas halaman: zoom, geser, kotak blok yang bisa dipindah/diubah ukuran, gambar kotak baru."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QStyle)

HANDLE = 12


class BoxItem(QGraphicsRectItem):
    def __init__(self, block, index, canvas):
        super().__init__(0, 0, block.w, block.h)
        self.block = block
        self.canvas = canvas
        self.setPos(block.x, block.y)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self._resizing = False
        self.label = QGraphicsSimpleTextItem(str(index), self)
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        self.label.setFont(f)
        self.label.setBrush(QBrush(QColor("white")))
        self.label.setPos(3, 1)
        self.refresh_style()

    def refresh_style(self):
        sel = self.isSelected()
        col = QColor("#ff4d6d") if self.block.kind == "bubble" else QColor("#3a86ff")
        if sel:
            col = QColor("#ffbe0b")
        pen = QPen(col, 3 if sel else 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        fill = QColor(col)
        fill.setAlpha(45 if sel else 25)
        self.setBrush(QBrush(fill))

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected  # sembunyikan garis seleksi bawaan
        super().paint(painter, option, widget)
        # kotak nomor + pegangan resize
        painter.fillRect(QRectF(0, 0, 22, 20), self.pen().color())
        r = self.rect()
        painter.fillRect(QRectF(r.right() - HANDLE, r.bottom() - HANDLE, HANDLE, HANDLE), self.pen().color())

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.refresh_style()
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.sync()
        return super().itemChange(change, value)

    def _in_handle(self, p: QPointF):
        r = self.rect()
        return p.x() >= r.right() - HANDLE * 1.5 and p.y() >= r.bottom() - HANDLE * 1.5

    def hoverMoveEvent(self, e):
        self.setCursor(Qt.SizeFDiagCursor if self._in_handle(e.pos()) else Qt.SizeAllCursor)

    def mousePressEvent(self, e):
        self._press_geom = (self.block.x, self.block.y, self.block.w, self.block.h)
        if e.button() == Qt.LeftButton and self._in_handle(e.pos()):
            self._resizing = True
            self.setSelected(True)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._resizing:
            p = e.pos()
            self.prepareGeometryChange()
            self.setRect(0, 0, max(10, p.x()), max(10, p.y()))
            self.sync()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._resizing = False
        super().mouseReleaseEvent(e)
        self.sync()
        b = self.block
        if getattr(self, "_press_geom", None) != (b.x, b.y, b.w, b.h):
            self.canvas.block_geometry_changed.emit(self.block)

    def mouseDoubleClickEvent(self, e):
        self.canvas.block_double_clicked.emit(self.block)

    def sync(self):
        b = self.block
        # kontur balon tidak lagi valid kalau kotak diubah manual
        nx, ny = int(self.pos().x()), int(self.pos().y())
        nw, nh = int(self.rect().width()), int(self.rect().height())
        if (nx, ny, nw, nh) != (b.x, b.y, b.w, b.h):
            if b.mask_poly:
                dx, dy = nx - b.x, ny - b.y
                if (nw, nh) == (b.w, b.h):
                    b.mask_poly = [[px + dx, py + dy] for px, py in b.mask_poly]
                else:
                    b.mask_poly = []
            b.x, b.y, b.w, b.h = nx, ny, nw, nh


class PageCanvas(QGraphicsView):
    block_selected = Signal(object)          # TextBlock atau None
    block_geometry_changed = Signal(object)
    block_double_clicked = Signal(object)
    box_drawn = Signal(QRectF)
    zoom_changed = Signal(float)

    def __init__(self, parent=None, editable=True):
        super().__init__(parent)
        self.editable = editable
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#111214")))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.pix_item: QGraphicsPixmapItem | None = None
        self.boxes: list[BoxItem] = []
        self.show_boxes = True
        self.draw_mode = False
        self._draw_start = None
        self._draw_rect = None
        self.scene().selectionChanged.connect(self._on_sel)

    # ------------------------------------------------------------ konten
    def set_page(self, image_path: str | None, blocks, fit=True):
        self.scene().clear()
        self.boxes = []
        self.pix_item = None
        if not image_path:
            return
        pm = QPixmap.fromImage(QImage(image_path))
        self.pix_item = self.scene().addPixmap(pm)
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
            item = BoxItem(blk, i, self)
            item.setVisible(self.show_boxes)
            self.scene().addItem(item)
            self.boxes.append(item)

    def set_boxes_visible(self, v: bool):
        self.show_boxes = v
        for b in self.boxes:
            b.setVisible(v)

    def select_block(self, block):
        self.scene().blockSignals(True)
        for b in self.boxes:
            b.setSelected(b.block is block)
            b.refresh_style()
        self.scene().blockSignals(False)
        for b in self.boxes:
            if b.block is block:
                self.ensureVisible(b, 60, 60)

    def _on_sel(self):
        sel = [i for i in self.scene().selectedItems() if isinstance(i, BoxItem)]
        self.block_selected.emit(sel[0].block if sel else None)

    # ------------------------------------------------------------ zoom
    def fit(self):
        if self.pix_item:
            self.fitInView(self.pix_item, Qt.KeepAspectRatio)
            self.zoom_changed.emit(self.transform().m11())

    def zoom(self) -> float:
        return self.transform().m11()

    def set_zoom(self, s: float, emit=False):
        s = max(0.05, min(8.0, s))
        self.setTransform(QTransform.fromScale(s, s))
        if emit:
            self.zoom_changed.emit(s)

    def wheelEvent(self, e):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        if 0.05 < self.zoom() * f < 8:
            self.scale(f, f)
            self.zoom_changed.emit(self.zoom())

    # ------------------------------------------------------------ gambar kotak baru
    def set_draw_mode(self, on: bool):
        on = on and self.editable
        self.draw_mode = on
        self.setDragMode(QGraphicsView.NoDrag if on else QGraphicsView.ScrollHandDrag)
        self.viewport().setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if self.draw_mode and e.button() == Qt.LeftButton and self.pix_item:
            self._draw_start = self.mapToScene(e.position().toPoint())
            pen = QPen(QColor("#06d6a0"), 2, Qt.DashLine)
            pen.setCosmetic(True)
            self._draw_rect = self.scene().addRect(QRectF(self._draw_start, self._draw_start), pen)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._draw_rect is not None:
            p = self.mapToScene(e.position().toPoint())
            self._draw_rect.setRect(QRectF(self._draw_start, p).normalized())
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._draw_rect is not None:
            r = self._draw_rect.rect().intersected(self.scene().sceneRect())
            self.scene().removeItem(self._draw_rect)
            self._draw_rect = None
            if r.width() > 8 and r.height() > 8:
                self.box_drawn.emit(r)
            return
        super().mouseReleaseEvent(e)
