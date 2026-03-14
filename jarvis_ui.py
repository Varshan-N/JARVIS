"""
JARVIS AI — Voice Interface v5.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Real-time audio → arc reactor waveform visualisation
Like OpenAI voice mode — reactor breathes with your voice
"""

import sys, math, time
from datetime import datetime
from collections import deque

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QLineEdit,
    QGraphicsOpacityEffect, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QRect, QPoint
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush,
    QRadialGradient, QPainterPath, QPalette
)

try:
    import sounddevice as sd
    import numpy as np
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False

from main import LLMassistant

C = {
    "bg0":     "#050508",
    "bg1":     "#08080e",
    "bg2":     "#0c0c15",
    "bg3":     "#10101c",
    "border":  "#161628",
    "border2": "#1e1e38",
    "accent":  "#7b61ff",
    "accent2": "#00d4ff",
    "accent3": "#ff6b9d",
    "glow1":   "#5b3eff",
    "text0":   "#f0f2ff",
    "text1":   "#8a8db0",
    "text2":   "#404265",
    "mic_on":  "#ff3366",
    "success": "#00ffa3",
    "warn":    "#ffb020",
    "user_bg": "#0f1133",
    "user_br": "#2a2880",
    "ai_bg":   "#0a0a16",
    "ai_br":   "#1a1a30",
}


class AudioMonitor(QThread):
    """
    Captures live audio from mic (or output device for TTS) in a background
    thread and emits normalised RMS amplitude [0.0 – 1.0] ~60× per second.
    Falls back to a smooth sine simulation if sounddevice is not installed.
    """
    amplitude = pyqtSignal(float)

    SAMPLE_RATE  = 16000
    BLOCK_SIZE   = 512
    CHANNELS     = 1
    NORM_PEAK    = 0.25     
    SMOOTH       = 0.25     

    def __init__(self, device=None, parent=None):
        super().__init__(parent)
        self._device  = device   
        self._running = False
        self._smooth  = 0.0

    def run(self):
        self._running = True

        if AUDIO_OK:
            def _cb(indata, frames, t, status):
                if not self._running:
                    return
                rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
                raw = min(1.0, rms / self.NORM_PEAK)
                self._smooth += self.SMOOTH * (raw - self._smooth)
                self.amplitude.emit(round(self._smooth, 4))

            try:
                with sd.InputStream(
                    device=self._device,
                    samplerate=self.SAMPLE_RATE,
                    channels=self.CHANNELS,
                    blocksize=self.BLOCK_SIZE,
                    dtype="int16",
                    callback=_cb,
                ):
                    while self._running:
                        self.msleep(10)
            except Exception:
                self._simulate()
        else:
            self._simulate()

    def _simulate(self):
        """Sine-wave fake amplitude — used when sounddevice is absent."""
        t = 0.0
        while self._running:
            v = (math.sin(t * 3.1) + 1) / 2 * 0.6 + 0.05
            self.amplitude.emit(round(v, 4))
            t += 0.08
            self.msleep(14)

    def stop_monitor(self):
        self._running = False
        self.wait(1000)

WAVE_BARS = 64

class ArcReactor(QWidget):
    def __init__(self, parent=None, d=340):
        super().__init__(parent)
        self.d = d
        self.setFixedSize(d, d)

        self._a1 = 0.0
        self._a2 = 0.0
        self._a3 = 0.0
        self._p  = 0.0     

        self._speaking   = False   
        self._tts        = False   
        self._amplitude  = 0.0    
        self._amp_smooth = 0.0   

        self._wave_hist = deque([0.0] * WAVE_BARS, maxlen=WAVE_BARS)
        self._hist_buf  = deque([0.0] * 8, maxlen=8)   
        
        self._tts_anim_time = 0.0

        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(14)       

    def set_speaking(self, v: bool):   
        self._speaking = v
        if v:
            self._tts = False  
            
    def set_tts(self, v: bool):        
        self._tts = v
        if v:
            self._speaking = False  
        if v:
            self._tts_anim_time = 0.0
            
    def feed_amplitude(self, v: float):
        """Called by AudioMonitor on every audio chunk."""
        self._amplitude = v
        self._hist_buf.append(v)

    def _tick(self):
        amp = self._amplitude
        active = self._speaking or self._tts
        speed  = 1.0 + amp * 3.0 if active else 1.0    

        self._a1 = (self._a1 + 0.55 * speed) % 360
        self._a2 = (self._a2 - 0.85 * speed) % 360
        self._a3 = (self._a3 + 0.32 * speed) % 360
        self._p  = (self._p  + 0.016) % (2 * math.pi)
        
        self._tts_anim_time += 0.1

        if self._tts:
            t = self._tts_anim_time
            animated_amp = 0.5 + 0.4 * math.sin(t * 0.8) + 0.2 * math.sin(t * 2.5)
            target = min(1.0, animated_amp)
        elif self._speaking:
            target = amp
        else:
            target = 0.1  
            
        self._amp_smooth += 0.18 * (target - self._amp_smooth)

        bar_val = self._amp_smooth + 0.03   
        self._wave_hist.appendleft(min(1.0, bar_val))

        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = self.d / 2, self.d / 2
        R      = self.d / 2 - 8
        pulse  = (math.sin(self._p) + 1) / 2
        amp    = self._amp_smooth
        active = self._speaking or self._tts

        if self._speaking:   
            ac = QColor(255, 51, 102)   
            outer_accent = QColor(255, 80, 120)
            glow_intensity = 1.0
        elif self._tts:      
            ac = QColor(0, 212, 255)    
            outer_accent = QColor(0, 180, 255)
            glow_intensity = 1.2 
        else:                
            ac = QColor(123, 97, 255)   
            outer_accent = QColor(100, 80, 200)
            glow_intensity = 0.5

        painter.setPen(Qt.NoPen)
        bg = QRadialGradient(cx, cy, R)
        if active:
            bg_intensity = int(60 + 80 * amp * glow_intensity)
            bg.setColorAt(0.0,  QColor(80, 50, 180, bg_intensity))
            bg.setColorAt(0.55, QColor(20, 20, 80,  int(30 + 40 * amp * glow_intensity)))
        else:
            bg.setColorAt(0.0,  QColor(50, 30, 130, int(40 + 60 * amp)))
            bg.setColorAt(0.55, QColor(10, 10, 60,  int(20 + 30 * amp)))
        bg.setColorAt(1.0,  QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(bg))
        painter.drawEllipse(int(cx-R), int(cy-R), int(R*2), int(R*2))

        aura_extra = amp * 25  
        for i in range(7, 0, -1):
            base_alpha = (35 + 25 * pulse) / i  
            if active:
                base_alpha = base_alpha * (1 + amp * 3.0 * glow_intensity)  
            alpha = int(min(255, base_alpha))
            pen_w = i * 4.0 + amp * 5  
            painter.setPen(QPen(QColor(outer_accent.red(), outer_accent.green(), outer_accent.blue(), alpha), pen_w))
            painter.setBrush(Qt.NoBrush)
            er = R + i * 3.0 + aura_extra * (i / 7)  
            painter.drawEllipse(int(cx-er), int(cy-er), int(er*2), int(er*2))

        for rf, base_alpha in [(0.96, 45), (0.82, 32), (0.66, 22), (0.50, 18), (0.36, 14)]:
            rr = int(R * rf)
            alpha = base_alpha + int(40 * amp * glow_intensity)  
            painter.setPen(QPen(QColor(100, 80, 255, alpha), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(int(cx-rr), int(cy-rr), rr*2, rr*2)

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._a1)
        arc_r = int(R * 0.88)
        rc = QRect(-arc_r, -arc_r, arc_r*2, arc_r*2)
        dash_alpha = int(180 + 100 * amp * glow_intensity) if active else int(180 + 75 * amp)
        pen = QPen(QColor(123, 97, 255, dash_alpha), 2.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush)
        for _ in range(8):
            painter.rotate(45)
            painter.drawArc(rc, 2*16, 36*16)
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._a2)
        mid_r = int(R * 0.70)
        rc2 = QRect(-mid_r, -mid_r, mid_r*2, mid_r*2)
        mid_alpha = int(150 + 100 * amp * glow_intensity) if active else int(150 + 80 * amp)
        pen2 = QPen(QColor(0, 212, 255, mid_alpha), 2)
        pen2.setCapStyle(Qt.RoundCap)
        painter.setPen(pen2)
        for _ in range(6):
            painter.rotate(60)
            painter.drawArc(rc2, 5*16, 54*16)
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._a3)
        e_r = int(R * 0.56)
        rc3 = QRect(-e_r, -e_r, e_r*2, e_r*2)
        cshift = int(80 + 100 * pulse)  
        energy_alpha = int(120 + 100 * amp * glow_intensity) if active else int(120 + 80 * amp)
        pen3 = QPen(QColor(cshift, 80, 255-cshift, energy_alpha), 1.8)
        pen3.setCapStyle(Qt.RoundCap)
        painter.setPen(pen3)
        for _ in range(4):
            painter.rotate(90)
            painter.drawArc(rc3, 8*16, 74*16)
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        wave_list = list(self._wave_hist)
        base_wave_r = R * 0.95        
        max_bar_h   = R * 0.25       
        min_bar_h   = R * 0.02        

        for i in range(WAVE_BARS):
            angle_rad  = 2 * math.pi * i / WAVE_BARS
            bar_amp    = wave_list[i % len(wave_list)]
            wobble     = 0.1 * math.sin(self._p * 2 + i * 0.4)  
            bar_h      = min_bar_h + (max_bar_h - min_bar_h) * min(1.0, bar_amp + wobble)

            x1 = math.cos(angle_rad) * base_wave_r
            y1 = math.sin(angle_rad) * base_wave_r
            x2 = math.cos(angle_rad) * (base_wave_r + bar_h)
            y2 = math.sin(angle_rad) * (base_wave_r + bar_h)

            bar_frac = bar_h / max_bar_h
            if self._speaking:
                bar_col = QColor(255, int(40 + 70 * bar_frac), int(80 + 90 * bar_frac))
                bar_alpha = int(100 + 155 * bar_frac)  
            elif self._tts:
                bar_col = QColor(int(60 + 70 * bar_frac), int(180 + 75 * bar_frac), 255)
                bar_alpha = int(100 + 155 * bar_frac)  
            else:
                bar_col = QColor(int(100 + 80 * bar_frac), int(80 + 60 * bar_frac), 255)
                bar_alpha = int(60 + 140 * bar_frac)  

            pen_bar   = QPen(QColor(bar_col.red(), bar_col.green(), bar_col.blue(), bar_alpha),
                             2.2)  
            pen_bar.setCapStyle(Qt.RoundCap)
            painter.setPen(pen_bar)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        hex_r      = int(R * (0.24 + 0.08 * amp * glow_intensity))   
        core_alpha = int(200 + 80 * pulse)  
        cg = QRadialGradient(0, 0, hex_r)
        cg.setColorAt(0.0,  QColor(220, 210, 255, core_alpha))
        cg.setColorAt(0.35, QColor(ac.red(), ac.green(), ac.blue(), core_alpha))
        cg.setColorAt(0.75, QColor(0, 180, 255, int(core_alpha * 0.7)))
        cg.setColorAt(1.0,  QColor(0, 50, 180, 0))
        painter.setBrush(QBrush(cg))
        painter.setPen(QPen(QColor(180, 160, 255, 220), 1.5))

        def hexpath(rr, rot=0):
            path = QPainterPath()
            for i in range(6):
                a = math.radians(i*60 - 90 + rot)
                p = (rr*math.cos(a), rr*math.sin(a))
                if i == 0: path.moveTo(*p)
                else:      path.lineTo(*p)
            path.closeSubpath()
            return path

        painter.drawPath(hexpath(hex_r))
        painter.setBrush(Qt.NoBrush)
        inner_hex_alpha = 180 if active else 160
        painter.setPen(QPen(QColor(0, 220, 255, inner_hex_alpha), 1))
        painter.drawPath(hexpath(int(hex_r * 0.60), 30))

        star_r = int(R * (0.055 + 0.04 * amp * glow_intensity))
        sg = QRadialGradient(0, 0, star_r)
        sg.setColorAt(0,   QColor(255, 255, 255, 255))
        sg.setColorAt(0.3, QColor(180, 160, 255, 250))
        sg.setColorAt(1,   QColor(100, 80, 255, 0))
        painter.setBrush(QBrush(sg))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(-star_r, -star_r, star_r*2, star_r*2)
        painter.restore()

class ScanlineOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(parent.rect())
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Overlay)
        pen = QPen(QColor(255, 255, 255, 4)); pen.setWidth(1)
        p.setPen(pen)
        for y in range(0, self.height(), 4):
            p.drawLine(0, y, self.width(), y)


class PulseLabel(QLabel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        eff  = QGraphicsOpacityEffect(self)
        eff.setOpacity(1.0)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(2400); anim.setStartValue(0.35); anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.SineCurve); anim.setLoopCount(-1)
        anim.start()


class Bubble(QWidget):
    def __init__(self, text, is_user, timestamp="", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 3, 12, 3); outer.setSpacing(0)
        row = QHBoxLayout(); row.setSpacing(8)

        def avatar(letter, grad):
            av = QLabel(letter)
            av.setFixedSize(26, 26)
            av.setAlignment(Qt.AlignCenter)
            av.setFont(QFont("Segoe UI", 8, QFont.Bold))
            av.setStyleSheet(f"background:{grad}; color:white; border-radius:13px;")
            return av

        if not is_user:
            row.addWidget(avatar("J",
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4a30cc,stop:1 #7b61ff)"),
                0, Qt.AlignTop)

        card = QFrame()
        card.setMaximumWidth(340)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        br = f"border-radius:{'16px 4px 16px 16px' if is_user else '4px 16px 16px 16px'};"
        card.setStyleSheet(
            f"QFrame{{background:{C['user_bg'] if is_user else C['ai_bg']};"
            f"border:1px solid {C['user_br'] if is_user else C['ai_br']};{br}padding:0px;}}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8); cl.setSpacing(3)
        txt = QLabel(text)
        txt.setWordWrap(True); txt.setFont(QFont("Segoe UI", 9))
        txt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        txt.setStyleSheet(f"color:{C['text0']}; background:transparent; border:none;")
        cl.addWidget(txt)
        if timestamp:
            ts = QLabel(timestamp)
            ts.setFont(QFont("Segoe UI", 7)); ts.setAlignment(Qt.AlignRight)
            ts.setStyleSheet(f"color:{C['text2']}; background:transparent; border:none;")
            cl.addWidget(ts)

        if is_user:
            row.addStretch()
            row.addWidget(card, 0, Qt.AlignTop)
            row.addWidget(avatar("T",
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #002266,stop:1 #0044bb)"),
                0, Qt.AlignTop)
        else:
            row.addWidget(card, 0, Qt.AlignTop); row.addStretch()

        outer.addLayout(row)


class ChatCanvas(QWidget):
    CANVAS_W       = 420
    send_requested = pyqtSignal(str)   

    def __init__(self, parent):
        super().__init__(parent)
        self._visible = False
        self.setFixedWidth(self.CANVAS_W)
        self.setStyleSheet(f"QWidget{{background:{C['bg1']};border-left:1px solid {C['border2']};}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet(f"background:{C['bg2']}; border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 12, 0)
        title = QLabel("CONVERSATION CANVAS")
        title.setFont(QFont("Consolas", 8, QFont.Bold))
        title.setStyleSheet(f"color:{C['text2']}; letter-spacing:2px; background:transparent; border:none;")
        cb = QPushButton("✕"); cb.setFixedSize(28, 28)
        cb.setFont(QFont("Segoe UI", 10)); cb.setCursor(Qt.PointingHandCursor)
        cb.setStyleSheet(f"QPushButton{{background:transparent;color:{C['text2']};border:none;border-radius:6px;}}"
                         f"QPushButton:hover{{background:{C['border2']};color:{C['accent3']};}}")
        cb.clicked.connect(self.hide_canvas)
        hl.addWidget(title); hl.addStretch(); hl.addWidget(cb)
        lay.addWidget(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{C['bg1']};border:none;}}"
            f"QScrollBar:vertical{{background:{C['bg0']};width:5px;border:none;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:{C['border2']};border-radius:3px;min-height:24px;}}"
            f"QScrollBar::handle:vertical:hover{{background:{C['accent']};}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")
        self._msg_w = QWidget()
        self._msg_w.setStyleSheet(f"background:{C['bg1']};")
        self._chat_lay = QVBoxLayout(self._msg_w)
        self._chat_lay.setContentsMargins(8, 12, 8, 12); self._chat_lay.setSpacing(5)
        self._chat_lay.addStretch()
        self._scroll.setWidget(self._msg_w)
        lay.addWidget(self._scroll, 1)

        bot = QWidget(); bot.setFixedHeight(58)
        bot.setStyleSheet(f"background:{C['bg2']}; border-top:1px solid {C['border']};")
        bl = QHBoxLayout(bot); bl.setContentsMargins(12, 8, 12, 8); bl.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message…")
        self._input.setFixedHeight(36); self._input.setFont(QFont("Segoe UI", 9))
        self._input.setStyleSheet(
            f"QLineEdit{{background:{C['bg3']};color:{C['text0']};border:1px solid {C['border2']};"
            f"border-radius:10px;padding:0 12px;}}"
            f"QLineEdit:focus{{border-color:{C['accent']};}}")
        self._input.returnPressed.connect(self._send)
        sb = QPushButton("⏎"); sb.setFixedSize(36, 36)
        sb.setFont(QFont("Segoe UI", 12)); sb.setCursor(Qt.PointingHandCursor)
        sb.clicked.connect(self._send)
        sb.setStyleSheet(f"QPushButton{{background:{C['glow1']};color:white;border-radius:10px;border:none;}}"
                         f"QPushButton:hover{{background:{C['accent']};}}")
        bl.addWidget(self._input, 1); bl.addWidget(sb)
        lay.addWidget(bot)
        self.move(9999, 9999)

    def _init_geometry(self):
        """Call once after window shown so canvas has real dimensions."""
        ph = self.parent().height()
        top = 58
        self.setFixedHeight(ph - top)
        self.move(self.parent().width(), top)        

    def show_canvas(self):
        if self._visible: return
        self._visible = True
        ph = self.parent().height(); top = 58
        self.setFixedHeight(ph - top)
        self.show(); self.raise_()
        QTimer.singleShot(80, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(280)
        anim.setStartValue(QPoint(self.parent().width(), top))
        anim.setEndValue(QPoint(self.parent().width() - self.CANVAS_W, top))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(); self._anim = anim

    def hide_canvas(self):
        if not self._visible: return
        self._visible = False
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(240)
        anim.setStartValue(self.pos())
        anim.setEndValue(QPoint(self.parent().width(), self.y()))
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self.hide)
        anim.start(); self._anim = anim

    def toggle(self):
        if self._visible: 
            self.hide_canvas()
        else:             
            self.show_canvas()

    def is_open(self):   
        return self._visible

    def add_message(self, text, is_user, timestamp=""):
        b = Bubble(text, is_user, timestamp)
        self._chat_lay.insertWidget(self._chat_lay.count() - 1, b)
        QTimer.singleShot(40, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self.send_requested.emit(txt)

    def reposition(self, pw, ph, top=58):
        if self._visible:
            self.setFixedHeight(ph - top)
            self.move(pw - self.CANVAS_W, top)


class JarvisUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS  ·  Voice AI")
        self.resize(1100, 740)
        self.setMinimumSize(800, 580)
        self._mic_on    = False
        self._tts_on    = False
        self._monitor   = None

        self._apply_palette()
        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)

        main_lay = QVBoxLayout(root)
        main_lay.setContentsMargins(0, 0, 0, 0); main_lay.setSpacing(0)
        main_lay.addWidget(self._topbar())
        main_lay.addWidget(self._hero(), 1)
        main_lay.addWidget(self._bottom_bar())

        self._root_ref = root
        self._scan     = ScanlineOverlay(root)
        self._canvas   = ChatCanvas(root)
        self._scan.raise_()

        t = QTimer(self)
        t.timeout.connect(self._tick_clock)
        t.start(500)
        self._tick_clock()

        self._assistant = LLMassistant()
        sig             = self._assistant.sig

        sig.speech_detected.connect(self._on_speech_detected)
        sig.user_text_ready.connect(self._on_user_text)
        sig.ai_reply_ready.connect(self._on_ai_reply)
        sig.tts_started.connect(self._on_tts_started)
        sig.tts_finished.connect(self._on_tts_finished)
        sig.energy.connect(self._reactor.feed_amplitude)

        self._canvas.send_requested.connect(self._assistant.process_text)

        self._assistant.start()
        self._mic_on = True
        self._refresh_mic()
        self._reactor.set_speaking(True)
        self._set_mode("LISTENING", C['mic_on'])
        self._sub_lbl.setText("Listening…  speak now")
        self._start_monitor()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_root_ref"):
            if hasattr(self, "_scan"):
                self._scan.setGeometry(self._root_ref.rect())
            if hasattr(self, "_canvas"):
                self._canvas.reposition(self._root_ref.width(), self._root_ref.height())

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._canvas._init_geometry)

    def _apply_palette(self):
        self.setStyleSheet(f"""
            * {{ font-family:'Segoe UI'; color:{C['text0']}; }}
            QMainWindow, #root {{ background:{C['bg0']}; }}
            QToolTip {{ background:{C['bg3']}; color:{C['text0']};
                        border:1px solid {C['border2']}; border-radius:6px; padding:4px 8px; }}
        """)
        pal = QPalette()
        for role, col in [
            (QPalette.Window,          QColor(5, 5, 8)),
            (QPalette.WindowText,      QColor(240, 242, 255)),
            (QPalette.Base,            QColor(8, 8, 14)),
            (QPalette.Text,            QColor(240, 242, 255)),
            (QPalette.Button,          QColor(12, 12, 21)),
            (QPalette.ButtonText,      QColor(240, 242, 255)),
            (QPalette.Highlight,       QColor(123, 97, 255)),
            (QPalette.HighlightedText, QColor(255, 255, 255)),
        ]:
            pal.setColor(role, col)
        self.setPalette(pal)

    def _topbar(self):
        bar = QWidget(); bar.setFixedHeight(58)
        bar.setStyleSheet(f"background:{C['bg1']}; border-bottom:1px solid {C['border']};")
        lay = QHBoxLayout(bar); lay.setContentsMargins(24, 0, 20, 0)

        badge = QLabel("JARVIS  ✦  VOICE MODE")
        badge.setFont(QFont("Consolas", 8))
        badge.setStyleSheet(f"color:{C['accent']}; background:#0e0e22; "
                            f"border:1px solid {C['border2']}; border-radius:8px; padding:4px 12px;")
        lay.addWidget(badge); lay.addStretch()

        clk = QVBoxLayout(); clk.setSpacing(0); clk.setAlignment(Qt.AlignCenter)
        self._clock_lbl = QLabel("12:00 AM")
        self._clock_lbl.setFont(QFont("Segoe UI Light", 26, QFont.Light))
        self._clock_lbl.setAlignment(Qt.AlignCenter)
        self._clock_lbl.setStyleSheet(f"color:{C['text0']}; letter-spacing:3px; background:transparent; border:none;")
        self._date_lbl = QLabel("—")
        self._date_lbl.setFont(QFont("Segoe UI", 8)); self._date_lbl.setAlignment(Qt.AlignCenter)
        self._date_lbl.setStyleSheet(f"color:{C['text2']}; background:transparent; border:none;")
        clk.addWidget(self._clock_lbl); clk.addWidget(self._date_lbl)
        lay.addLayout(clk); lay.addStretch()

        for ic, tip in [("⚙", "Settings"), ("✕", "Close")]:
            b = QPushButton(ic); b.setFixedSize(32, 32)
            b.setFont(QFont("Segoe UI", 10)); b.setToolTip(tip); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:transparent;color:{C['text1']};border-radius:8px;}}"
                            f"QPushButton:hover{{background:{C['border2']};color:{C['text0']};}}")
            lay.addWidget(b); lay.addSpacing(4)
        return bar

    def _hero(self):
        w = QWidget(); w.setStyleSheet(f"background:{C['bg0']};")
        lay = QVBoxLayout(w); lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(0); lay.setContentsMargins(0, 30, 0, 20)

        self._reactor = ArcReactor(d=340)
        lay.addWidget(self._reactor, 0, Qt.AlignCenter)
        lay.addSpacing(32)

        self._mode_lbl = PulseLabel("READY")
        self._mode_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        self._mode_lbl.setAlignment(Qt.AlignCenter)
        self._mode_lbl.setStyleSheet(f"color:{C['accent']}; letter-spacing:6px; background:transparent; border:none;")
        lay.addWidget(self._mode_lbl)
        lay.addSpacing(6)

        self._sub_lbl = QLabel("Say something to begin  ·  or press the mic button below")
        self._sub_lbl.setFont(QFont("Segoe UI", 9))
        self._sub_lbl.setAlignment(Qt.AlignCenter)
        self._sub_lbl.setStyleSheet(f"color:{C['text2']}; background:transparent; border:none;")
        lay.addWidget(self._sub_lbl)
        lay.addSpacing(28)
        lay.addWidget(self._stats_row())
        return w

    def _stats_row(self):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w); lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(0); lay.setContentsMargins(0, 0, 0, 0)
        stats = [
            ("POWER",   "94.7%",    C['success']),
            ("MODEL",   "GPT-4o",   C['accent2']),
            ("LATENCY", "38 ms",    C['warn']),
            ("UPTIME",  "4h 12m",   C['text1']),
            ("VOICE",   "Enabled",  C['accent']),
        ]
        for i, (lbl, val, col) in enumerate(stats):
            if i > 0:
                div = QFrame(); div.setFrameShape(QFrame.VLine)
                div.setFixedHeight(28)
                div.setStyleSheet(f"color:{C['border2']}; background:{C['border2']};")
                lay.addWidget(div)
            cell = QWidget(); cell.setStyleSheet("background:transparent;")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(22, 0, 22, 0); cl.setSpacing(2); cl.setAlignment(Qt.AlignCenter)
            l = QLabel(lbl); l.setFont(QFont("Consolas", 7)); l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(f"color:{C['text2']}; background:transparent; border:none;")
            v = QLabel(val); v.setFont(QFont("Consolas", 9, QFont.Bold)); v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet(f"color:{col}; background:transparent; border:none;")
            cl.addWidget(l); cl.addWidget(v); lay.addWidget(cell)
        return w

    def _bottom_bar(self):
        bar = QWidget(); bar.setFixedHeight(90)
        bar.setStyleSheet(f"background:{C['bg1']}; border-top:1px solid {C['border']};")
        lay = QHBoxLayout(bar); lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(22)

        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(62, 62)
        self._mic_btn.setFont(QFont("Segoe UI", 22))
        self._mic_btn.setToolTip("Click to speak")
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.clicked.connect(self._toggle_mic)
        self._refresh_mic()
        lay.addWidget(self._mic_btn)

        self._canvas_btn = QPushButton("💬")
        self._canvas_btn.setFixedSize(46, 46)
        self._canvas_btn.setFont(QFont("Segoe UI", 16))
        self._canvas_btn.setToolTip("Open Conversation Canvas")
        self._canvas_btn.setCursor(Qt.PointingHandCursor)
        self._canvas_btn.clicked.connect(self._toggle_canvas)
        self._canvas_btn.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};color:{C['text1']};"
            f"border:1px solid {C['border2']};border-radius:13px;}}"
            f"QPushButton:hover{{background:{C['border2']};color:{C['text0']};}}")
        lay.addWidget(self._canvas_btn)
        return bar

    def _on_speech_detected(self):
        if not self._mic_on:
            return
        self._set_mode("LISTENING", C['mic_on'])
        self._sub_lbl.setText("Listening…")
        self._reactor.set_speaking(True)
        self._reactor.set_tts(False)

    def _on_user_text(self, text):
        ts = datetime.now().strftime("%I:%M %p")
        self._canvas.add_message(text, True, ts)
        self._set_mode("PROCESSING", C['warn'])
        self._sub_lbl.setText("Processing…")
        self._reactor.set_speaking(False)
        self._reactor.set_tts(False)

    def _on_ai_reply(self, reply):
        ts = datetime.now().strftime("%I:%M %p")
        self._canvas.add_message(reply, False, ts)

    def _on_tts_started(self):
        self._reactor.set_tts(True)
        self._reactor.set_speaking(False)
        self._set_mode("SPEAKING", C['accent2'])
        self._sub_lbl.setText("JARVIS is speaking…")

    def _on_tts_finished(self):
        self._reactor.set_tts(False)
        self._reactor.set_speaking(False)
        self._set_mode("LISTENING", C['mic_on'])
        self._sub_lbl.setText("Listening…  speak now")

    def _toggle_mic(self):
        self._mic_on = not self._mic_on
        self._refresh_mic()
        self._reactor.set_speaking(self._mic_on)
        if self._mic_on:
            self._assistant.is_listening = True
            self._assistant.audio_thread.reset()   # clear Chrome output, restart fresh
            self._set_mode("LISTENING", C['mic_on'])
            self._sub_lbl.setText("Listening…  speak now")
            self._start_monitor()
        else:
            self._assistant.is_listening = False
            self._set_mode("READY", C['accent'])
            self._sub_lbl.setText("Microphone muted  ·  press to listen again")
            self._stop_monitor()
            self._reactor.feed_amplitude(0.0)

    def _start_monitor(self):
        if self._monitor and self._monitor.isRunning():
            return
        self._monitor = AudioMonitor()
        self._monitor.amplitude.connect(self._on_amplitude)
        self._monitor.start()

    def _stop_monitor(self):
        if self._monitor:
            self._monitor.stop_monitor()
            self._monitor = None

    def _on_amplitude(self, v: float):
        self._reactor.feed_amplitude(v)

    def _toggle_canvas(self):
        self._canvas.toggle()
        if self._canvas.is_open():
            self._canvas_btn.setStyleSheet(
                f"QPushButton{{background:{C['accent']};color:white;"
                f"border:1px solid {C['accent']};border-radius:13px;}}"
                f"QPushButton:hover{{background:{C['glow1']};}}")
        else:
            self._canvas_btn.setStyleSheet(
                f"QPushButton{{background:{C['bg3']};color:{C['text1']};"
                f"border:1px solid {C['border2']};border-radius:13px;}}"
                f"QPushButton:hover{{background:{C['border2']};color:{C['text0']};}}")

    def _refresh_mic(self):
        if self._mic_on:
            self._mic_btn.setStyleSheet(
                f"QPushButton{{background:{C['mic_on']};color:white;"
                f"border-radius:31px;font-size:22px;border:none;}}"
                f"QPushButton:hover{{background:#dd2255;}}")
        else:
            self._mic_btn.setStyleSheet(
                f"QPushButton{{background:{C['bg3']};color:{C['text1']};"
                f"border:1px solid {C['border2']};border-radius:31px;font-size:22px;}}"
                f"QPushButton:hover{{background:{C['border2']};color:{C['text0']};}}")

    def _set_mode(self, label, color):
        self._mode_lbl.setText(label)
        self._mode_lbl.setStyleSheet(
            f"color:{color};letter-spacing:6px;font-family:Consolas;"
            f"font-size:11pt;font-weight:bold;background:transparent;border:none;")

    def _tick_clock(self):
        now = datetime.now()
        self._clock_lbl.setText(now.strftime("%I:%M %p"))
        self._date_lbl.setText(now.strftime("%A,  %B %d,  %Y"))

    def closeEvent(self, e):
        self._stop_monitor()
        self._assistant.stop()
        QApplication.quit()
        e.accept()



def main():
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    for role, c in [
        (QPalette.Window,          QColor(5, 5, 8)),
        (QPalette.WindowText,      QColor(240, 242, 255)),
        (QPalette.Base,            QColor(8, 8, 14)),
        (QPalette.AlternateBase,   QColor(12, 12, 21)),
        (QPalette.ToolTipBase,     QColor(5, 5, 8)),
        (QPalette.ToolTipText,     QColor(240, 242, 255)),
        (QPalette.Text,            QColor(240, 242, 255)),
        (QPalette.Button,          QColor(12, 12, 21)),
        (QPalette.ButtonText,      QColor(240, 242, 255)),
        (QPalette.Highlight,       QColor(123, 97, 255)),
        (QPalette.HighlightedText, QColor(255, 255, 255)),
    ]:
        pal.setColor(role, c)
    app.setPalette(pal)

    w = JarvisUI()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()