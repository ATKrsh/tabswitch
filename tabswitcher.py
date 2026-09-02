# tabswitcher.py
# Always-on-top, translucent Assistive Tab Switcher desktop widget.
# Mode 1 (outer donut): Ctrl+Tab — cycle to next tab in the active window.
# Mode 2 (inner circle): Ctrl+Shift+Tab — cycle to previous / recent tab.
# Built with Python, PyQt5, and native Windows APIs.

import sys
import os
import time
import math
import base64

# if sys.stdout is None:
#     sys.stdout = open(os.devnull, "w")
# if sys.stderr is None:
#     sys.stderr = open(os.devnull, "w")

from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import (
    Qt, QPoint, QTimer, QPropertyAnimation, QVariantAnimation, QPointF
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QColor, QPainter, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPainterPath, QFont, QCursor
)

import ctypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win32 constants
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_TAB = 0x09
KEYEVENTF_KEYUP = 0x0002
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SW_RESTORE = 9

# Win32 API handles
# Win32 API handles with explicit argtypes and restypes for 64-bit compatibility
IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [ctypes.c_void_p]
IsWindowVisible.restype = ctypes.c_bool

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
GetWindowTextLengthW.restype = ctypes.c_int

GetParent = user32.GetParent
GetParent.argtypes = [ctypes.c_void_p]
GetParent.restype = ctypes.c_void_p

SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = [ctypes.c_void_p]
SetForegroundWindow.restype = ctypes.c_bool

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
ShowWindow.restype = ctypes.c_bool

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.argtypes = []
GetForegroundWindow.restype = ctypes.c_void_p

IsWindow = user32.IsWindow
IsWindow.argtypes = [ctypes.c_void_p]
IsWindow.restype = ctypes.c_bool

IsIconic = user32.IsIconic
IsIconic.argtypes = [ctypes.c_void_p]
IsIconic.restype = ctypes.c_bool

user32.keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_void_p]
user32.keybd_event.restype = None

if hasattr(user32, "GetWindowLongPtrW"):
    GetWindowLongW = user32.GetWindowLongPtrW
    GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    GetWindowLongW.restype = ctypes.c_ssize_t
    
    SetWindowLongW = user32.SetWindowLongPtrW
    SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    SetWindowLongW.restype = ctypes.c_ssize_t
else:
    GetWindowLongW = user32.GetWindowLongW
    GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    GetWindowLongW.restype = ctypes.c_long
    
    SetWindowLongW = user32.SetWindowLongW
    SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    SetWindowLongW.restype = ctypes.c_long


def get_window_title(hwnd):
    length = GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def is_user_application(hwnd):
    if not IsWindow(hwnd):
        return False
    if not IsWindowVisible(hwnd):
        return False
    title = get_window_title(hwnd)
    if not title:
        return False
    if GetParent(hwnd):
        return False
        
    # Exclude tool windows
    ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW:
        return False
        
    # Exclude specific system/background UI processes
    ignored_titles = [
        "Program Manager", "Start", "Settings", "Cortana", 
        "Windows Shell Experience Host", "Microsoft Text Input Application",
        "Assistive Tab Switcher"
    ]
    if title in ignored_titles:
        return False
        
    return True


def press_key(vk):
    user32.keybd_event(vk, 0, 0, 0)


def release_key(vk):
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def send_ctrl_tab():
    """Send Ctrl+Tab to the OS: cycle to next tab."""
    press_key(VK_CONTROL)
    time.sleep(0.02)
    press_key(VK_TAB)
    time.sleep(0.02)
    release_key(VK_TAB)
    time.sleep(0.02)
    release_key(VK_CONTROL)


def send_ctrl_shift_tab():
    """Send Ctrl+Shift+Tab to the OS: cycle to previous/recent tab."""
    press_key(VK_CONTROL)
    time.sleep(0.02)
    press_key(VK_SHIFT)
    time.sleep(0.02)
    press_key(VK_TAB)
    time.sleep(0.02)
    release_key(VK_TAB)
    time.sleep(0.02)
    release_key(VK_SHIFT)
    time.sleep(0.02)
    release_key(VK_CONTROL)


# ---------------------------------------------------------------------------
# Custom painter widget — the concentric-circle floating button
# ---------------------------------------------------------------------------
class TabSwitcherButton(QWidget):
    """
    A circular widget with two interactive hit zones:
      • Inner circle  (radius < INNER_R)  → Mode 2: Ctrl+Shift+Tab
      • Outer donut   (INNER_R ≤ radius ≤ OUTER_R) → Mode 1: Ctrl+Tab
    Draggable when the user holds and moves the mouse > 5 px.
    """
    OUTER_R = 44          # outer radius of the widget hit circle
    INNER_R = 18          # inner solid circle radius
    WIDGET_SIZE = 96      # widget pixel size (square bounding box)

    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.setFixedSize(self.WIDGET_SIZE, self.WIDGET_SIZE)

        self._drag_pos = QPoint()
        self._is_dragging = False
        self._press_pos = QPoint()

        # Hover & press state
        self._hover_inner = False
        self._hover_outer = False
        self._press_inner = False
        self._press_outer = False

        # Animation for the glow pulse
        self._pulse_t = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(30)

        self.setMouseTracking(True)

    # ---- Animation ---------------------------------------------------------
    def _tick_pulse(self):
        self._pulse_t = (self._pulse_t + 0.06) % (2 * math.pi)
        self.update()

    # ---- Hit testing -------------------------------------------------------
    def _zone(self, pos: QPoint):
        """Return 'inner', 'outer', or None based on click position."""
        cx = self.WIDGET_SIZE / 2
        cy = self.WIDGET_SIZE / 2
        dx = pos.x() - cx
        dy = pos.y() - cy
        r = math.sqrt(dx * dx + dy * dy)
        if r <= self.INNER_R:
            return "inner"
        elif r <= self.OUTER_R:
            return "outer"
        return None

    # ---- Painting ----------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cx = self.WIDGET_SIZE / 2
        cy = self.WIDGET_SIZE / 2
        pulse = 0.5 + 0.5 * math.sin(self._pulse_t)

        # ── Outer Glow (ambient shadow) ──────────────────────────────────────
        glow_alpha = int(40 + 20 * pulse)
        glow_r = self.OUTER_R + 8 + 4 * pulse
        glow = QRadialGradient(cx, cy, glow_r)
        glow.setColorAt(0.0, QColor(0, 200, 255, glow_alpha))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(
            QPointF(cx, cy),
            glow_r, glow_r
        )

        # ── Outer Donut Background ───────────────────────────────────────────
        outer_bg = QRadialGradient(cx, cy - 10, self.OUTER_R)
        if self._press_outer:
            outer_bg.setColorAt(0.0, QColor(0, 140, 200, 230))
            outer_bg.setColorAt(1.0, QColor(20, 25, 40, 240))
        elif self._hover_outer:
            outer_bg.setColorAt(0.0, QColor(30, 50, 80, 230))
            outer_bg.setColorAt(1.0, QColor(18, 22, 35, 240))
        else:
            outer_bg.setColorAt(0.0, QColor(22, 28, 44, 210))
            outer_bg.setColorAt(1.0, QColor(14, 18, 30, 220))

        p.setBrush(QBrush(outer_bg))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), self.OUTER_R, self.OUTER_R)

        # ── Outer Ring Border ────────────────────────────────────────────────
        ring_alpha = int(180 + 60 * pulse)
        if self._hover_outer or self._press_outer:
            ring_color = QColor(0, 220, 255, ring_alpha)
        else:
            ring_color = QColor(0, 180, 220, int(120 + 40 * pulse))

        pen = QPen(ring_color)
        pen.setWidthF(2.5)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), self.OUTER_R - 1.25, self.OUTER_R - 1.25)

        # ── Inner "Cutout" separator ring (gives the donut feel) ─────────────
        sep_color = QColor(8, 12, 22, 255)
        pen2 = QPen(sep_color)
        pen2.setWidthF(4)
        p.setPen(pen2)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), self.INNER_R + 5, self.INNER_R + 5)

        # ── Inner Circle Background ──────────────────────────────────────────
        inner_bg = QRadialGradient(cx, cy - 6, self.INNER_R)
        if self._press_inner:
            inner_bg.setColorAt(0.0, QColor(0, 200, 255, 255))
            inner_bg.setColorAt(1.0, QColor(0, 100, 180, 255))
        elif self._hover_inner:
            inner_bg.setColorAt(0.0, QColor(0, 180, 240, 255))
            inner_bg.setColorAt(1.0, QColor(0, 80, 150, 255))
        else:
            inner_bg.setColorAt(0.0, QColor(0, 160, 220, int(200 + 40 * pulse)))
            inner_bg.setColorAt(1.0, QColor(0, 60, 120, int(220 + 20 * pulse)))

        p.setBrush(QBrush(inner_bg))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), self.INNER_R, self.INNER_R)

        # ── Inner Circle border ───────────────────────────────────────────────
        inner_border_alpha = int(180 + 60 * pulse)
        inner_border = QColor(100, 230, 255, inner_border_alpha)
        pen3 = QPen(inner_border)
        pen3.setWidthF(1.5)
        p.setPen(pen3)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), self.INNER_R - 0.75, self.INNER_R - 0.75)

        # ── Tab icon arrows in the donut zone ─────────────────────────────────
        # Draw a small "→ tab" icon (right-pointing chevrons) in the donut area
        arrow_pen = QPen(QColor(160, 220, 255, 200))
        arrow_pen.setWidthF(2.0)
        arrow_pen.setCapStyle(Qt.RoundCap)
        arrow_pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(arrow_pen)

        # Two small arrows at top and bottom of the donut suggesting cycling
        # Top arrow → (next tab hint)
        mid_r = (self.INNER_R + 5 + self.OUTER_R) / 2   # mid donut radius ~34
        for angle_deg, flip in [(-90, False), (90, True)]:
            angle = math.radians(angle_deg)
            ax = cx + mid_r * math.cos(angle)
            ay = cy + mid_r * math.sin(angle)
            aw = 7
            ah = 5
            path = QPainterPath()
            if not flip:
                path.moveTo(ax - aw, ay - ah)
                path.lineTo(ax + aw, ay)
                path.lineTo(ax - aw, ay + ah)
            else:
                path.moveTo(ax + aw, ay - ah)
                path.lineTo(ax - aw, ay)
                path.lineTo(ax + aw, ay + ah)
            p.drawPath(path)

        p.end()

    # ---- Mouse Events -------------------------------------------------------
    def mouseMoveEvent(self, event):
        zone = self._zone(event.pos())
        self._hover_inner = (zone == "inner")
        self._hover_outer = (zone == "outer")

        if event.buttons() & Qt.LeftButton and not self._parent.is_locked:
            diff = event.globalPos() - (self._parent.frameGeometry().topLeft() + self._drag_pos)
            if diff.manhattanLength() > 5:
                self._is_dragging = True
            if self._is_dragging:
                self._parent.move(event.globalPos() - self._drag_pos)

        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.AltModifier:
                print("[Action] Alt+Click → Quitting.")
                QApplication.quit()
                return
            if modifiers & Qt.ShiftModifier:
                self._parent.toggle_lock()
                event.accept()
                return

            self._press_pos = event.globalPos()
            self._drag_pos = event.globalPos() - self._parent.frameGeometry().topLeft()
            self._is_dragging = False

            zone = self._zone(event.pos())
            self._press_inner = (zone == "inner")
            self._press_outer = (zone == "outer")
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_inner = False
            self._press_outer = False
            self.update()

            if not self._is_dragging:
                zone = self._zone(event.pos())
                if zone == "outer":
                    print("[Mode 1] Outer donut → Ctrl+Tab (next tab)")
                    self._parent.do_mode1()
                elif zone == "inner":
                    print("[Mode 2] Inner circle → Ctrl+Shift+Tab (recent tab)")
                    self._parent.do_mode2()
            self._is_dragging = False
        event.accept()

    def leaveEvent(self, event):
        self._hover_inner = False
        self._hover_outer = False
        self.update()

    def enterEvent(self, event):
        self.update()


# ---------------------------------------------------------------------------
# Main floating widget
# ---------------------------------------------------------------------------
class TabSwitcherWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Frameless, transparent, always-on-top. WindowDoesNotAcceptFocus is
        # critical — it keeps the previously focused app active so that the
        # Ctrl+Tab shortcut hits the right window.
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.SubWindow |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Embed icon (base64 encoded icon.ico generated by generate_icon.py)
        icon_b64 = (
    "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"
)
        # Use a default Qt icon if the embedded one can't be decoded
        try:
            raw = base64.b64decode(icon_b64)
            pix = QPixmap()
            ok = pix.loadFromData(raw)
            if not ok:
                pix = QPixmap(64, 64)
                pix.fill(Qt.transparent)
            self.app_icon = QIcon(pix)
        except Exception:
            self.app_icon = QIcon()

        self.setWindowTitle("Assistive Tab Switcher")
        self.setWindowIcon(self.app_icon)

        # Widget size matches the inner button
        SIZE = TabSwitcherButton.WIDGET_SIZE
        self.setFixedSize(SIZE, SIZE)

        # Opacity management
        self._idle_opacity = 0.55
        self._hover_opacity = 0.92
        self.setWindowOpacity(self._idle_opacity)

        # State
        self.is_locked = False

        # Build button
        self._btn = TabSwitcherButton(self)
        self._btn.move(0, 0)

        # Opacity fade animation
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(150)

        # Drag / position tracking vars
        self.drag_position = QPoint()
        self.is_dragging = False

        # Tray
        self._setup_tray()

        # Hover opacity (track mouse entering/leaving the whole widget)
        self.setMouseTracking(True)

        # Apply native Windows WS_EX_NOACTIVATE style to prevent stealing focus when clicked
        hwnd = int(self.winId())
        style = GetWindowLongW(hwnd, GWL_EXSTYLE)
        SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

        # Track active window to restore focus before sending keyboard events
        self.last_active_hwnd = None
        self.active_hwnd_timer = QTimer(self)
        self.active_hwnd_timer.timeout.connect(self.poll_active_window)
        self.active_hwnd_timer.start(100)  # poll every 100ms

    # ---- Active Window Polling ---------------------------------------------
    def poll_active_window(self):
        hwnd = GetForegroundWindow()
        if hwnd and hwnd != int(self.winId()):
            if is_user_application(hwnd):
                if hwnd != self.last_active_hwnd:
                    title = get_window_title(hwnd)
                    print(f"[Focus Tracking] Active window changed to: '{title}' (HWND: {hwnd})", flush=True)
                self.last_active_hwnd = hwnd

    # ---- Opacity helpers ---------------------------------------------------
    def _fade_to(self, target):
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(target)
        self._fade.start()

    def enterEvent(self, event):
        self._fade_to(self._hover_opacity)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._fade_to(self._idle_opacity)
        super().leaveEvent(event)

    # ---- Switching actions -------------------------------------------------
    def do_mode1(self):
        """Mode 1: outer donut → Ctrl+Tab (next tab)."""
        self._animate_flash()
        if self.last_active_hwnd and IsWindow(self.last_active_hwnd):
            if IsIconic(self.last_active_hwnd):
                ShowWindow(self.last_active_hwnd, SW_RESTORE)
            SetForegroundWindow(self.last_active_hwnd)
            time.sleep(0.02)
        send_ctrl_tab()

    def do_mode2(self):
        """Mode 2: inner circle → Ctrl+Shift+Tab (recent/previous tab)."""
        self._animate_flash()
        if self.last_active_hwnd and IsWindow(self.last_active_hwnd):
            if IsIconic(self.last_active_hwnd):
                ShowWindow(self.last_active_hwnd, SW_RESTORE)
            SetForegroundWindow(self.last_active_hwnd)
            time.sleep(0.02)
        send_ctrl_shift_tab()

    def _animate_flash(self):
        """Quick opacity pulse feedback."""
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.setDuration(60)
        self._fade.finished.connect(self._after_flash)
        self._fade.start()

    def _after_flash(self):
        try:
            self._fade.finished.disconnect(self._after_flash)
        except TypeError:
            pass
        self._fade_to(self._hover_opacity)
        self._fade.setDuration(150)

    # ---- Lock ---------------------------------------------------------------
    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            print("[Lock] Position locked.")
            self.tray_icon.showMessage(
                "Tab Switcher", "Position locked.", QSystemTrayIcon.Information, 1500
            )
        else:
            print("[Lock] Position unlocked.")
            self.tray_icon.showMessage(
                "Tab Switcher", "Position unlocked.", QSystemTrayIcon.Information, 1500
            )

    # ---- Tray ---------------------------------------------------------------
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("Assistive Tab Switcher")

        menu = QMenu()

        mode1_info = QAction("Mode 1 (Outer): Ctrl+Tab → Next Tab", self)
        mode1_info.setEnabled(False)
        menu.addAction(mode1_info)

        mode2_info = QAction("Mode 2 (Inner): Ctrl+Shift+Tab → Prev/Recent Tab", self)
        mode2_info.setEnabled(False)
        menu.addAction(mode2_info)

        menu.addSeparator()

        toggle_action = QAction("Hide / Show Widget", self)
        toggle_action.triggered.connect(self._toggle_visibility)
        menu.addAction(toggle_action)

        lock_action = QAction("Toggle Lock Position", self)
        lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(lock_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_visibility()

    # ---- Window-level drag fallback ----------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.is_dragging = False
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and not self.is_locked:
            diff = event.globalPos() - (self.frameGeometry().topLeft() + self.drag_position)
            if diff.manhattanLength() > 5:
                self.is_dragging = True
            if self.is_dragging:
                self.move(event.globalPos() - self.drag_position)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
        event.accept()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app.setQuitOnLastWindowClosed(False)   # keep alive via tray

    widget = TabSwitcherWidget()

    # Place in bottom-right area
    screen_rect = QApplication.primaryScreen().geometry()
    init_x = screen_rect.width() - 130
    init_y = screen_rect.height() - 200
    widget.move(init_x, init_y)
    widget.show()

    sys.exit(app.exec_())
