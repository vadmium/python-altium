from tkinter import Tk
import tkinter
from . import base
from tkinter.font import Font
from math import sin, cos, radians
import tkinter.font
import operator

class _RawRenderer(base.Renderer):
    """Implements basic TK renderer except for default offsets, colour, etc
    """
    
    def __init__(self, size, units, unitmult=1, *,
    down, line=1, textbottom=False):
        root = Tk()
        scaling = root.call("tk", "scaling") * 72  # pixels/in
        scaling *= unitmult / {"mm": 25.4, "in": 1}[units]
        self.flip = down
        if self.flip < 0:
            self.scaling = (+scaling, -scaling)
        else:
            self.scaling = (+scaling, +scaling)
        self.linewidth = line * scaling
        self.canvas = tkinter.Canvas(root,
            relief=tkinter.SUNKEN, borderwidth=1,
            background="white",
            height=size[1] * scaling, width=size[0] * scaling,
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        self.fonts = dict()
    
    def line(self, a, b=None, *, offset=(0, 0), **kw):
        (ox, oy) = offset
        if b is None:
            b = a
            a = (ox, oy)
        else:
            (ax, ay) = a
            a = (ox + ax, oy + ay)
        (bx, by) = b
        self.polyline((a, (ox + bx, oy + by)), **kw)
    
    def polyline(self, points, *,
    colour, width=None, startarrow=None, endarrow=None):
        tkpoints = list()
        for (x, y) in points:
            tkpoints.extend((x * self.scaling[0], y * self.scaling[1]))
        width = width or self.linewidth
        colour = self._colour(colour)
        
        kw = dict()
        if startarrow:
            kw["arrow"] = tkinter.FIRST
            kw["arrowshape"] = (
                startarrow["base"] * self.scaling[0],
                startarrow["shoulder"] * self.scaling[0],
                (startarrow["radius"] - width / 2) * self.scaling[0],
            )
        if endarrow:
            kw["arrow"] = tkinter.LAST
            kw["arrowshape"] = (
                endarrow["base"] * self.scaling[0],
                endarrow["shoulder"] * self.scaling[0],
                (endarrow["radius"] - width / 2) * self.scaling[0],
            )
        if startarrow and endarrow:
            kw["arrow"] = tkinter.BOTH
        
        self.canvas.create_line(*tkpoints, fill=colour, width=width, **kw)
    
    def cubicbezier(self, a, b, c, d, *,
    offset=(0, 0), colour, width=None):
        (ox, oy) = offset
        points = list()
        for (x, y) in (a, b, c, d):
            points.append((ox + x) * self.scaling[0])
            points.append((oy + y) * self.scaling[1])
        width = width or self.linewidth
        colour = self._colour(colour)
        self.canvas.create_line(*points, smooth="bezier",
            fill=colour, width=width)
    
    def arc(self, r, start, end, offset=(0, 0), *, colour):
        (rx, ry) = r
        extent = end - start
        if abs(extent) >= 360:
            assert rx == ry
            return self.circle(rx, offset, outline=colour)
        extent %= 360
        
        (ox, oy) = offset
        self.canvas.create_arc(
            (ox - rx) * self.scaling[0], (oy - ry) * self.scaling[1],
            (ox + rx) * self.scaling[0], (oy + ry) * self.scaling[1],
            style=tkinter.ARC,
            start=start, extent=extent,
            outline=self._colour(colour),
        )
    
    def circle(self, r, offset=(0, 0), *,
    outline=None, fill=None, width=None):
        (ox, oy) = offset
        points = (
            (ox - r) * self.scaling[0], (oy - r) * self.scaling[1],
            (ox + r) * self.scaling[0], (oy + r) * self.scaling[1],
        )
        kw = self._closed(outline, fill, width)
        self.canvas.create_oval(*points, **kw)
    
    def polygon(self, points, *,
    offset=None, rotate=None, outline=None, fill=None, width=None):
        if offset:
            (ox, oy) = offset
        if rotate:
            (costh, sinth) = self._rotation(rotate)
        tkpoints = list()
        for (x, y) in points:
            if rotate:
                (x, y) = (x * costh - y * sinth, x * sinth + y * costh)
            if offset:
                x += ox
                y += oy
            tkpoints.extend((x * self.scaling[0], y * self.scaling[1]))
        kw = self._closed(outline, fill, width)
        self.canvas.create_polygon(tkpoints, **kw)
    
    def rectangle(self, a, b=None, *, offset=(0, 0),
    outline=None, fill=None, width=None):
        if not b:
            b = a
            a = (0, 0)
        
        (ox, oy) = offset
        (ax, ay) = a
        (bx, by) = b
        points = (
            (ox + ax) * self.scaling[0], (oy + ay) * self.scaling[1],
            (ox + bx) * self.scaling[0], (oy + by) * self.scaling[1],
        )
        kw = self._closed(outline, fill, width)
        self.canvas.create_rectangle(*points, **kw)
    
    def _closed(self, outline=None, fill=None, width=None):
        kw = dict()
        if fill:
            kw.update(fill=self._colour(fill))
            if outline:
                kw.update(width=width or self.linewidth)
            else:
                kw.update(width=0)
        if outline:
            kw.update(outline=self._colour(outline))
        return kw
    
    def text(self, text, offset=(0, 0),
    horiz=base.Renderer.LEFT, vert=base.Renderer.BOTTOM, *,
    angle=None, font=None, colour, width=None):
        anchors = {
            (self.TOP, self.LEFT): tkinter.NW,
            (self.TOP, self.CENTRE): tkinter.N,
            (self.TOP, self.RIGHT): tkinter.NE,
            (self.CENTRE, self.LEFT): tkinter.W,
            (self.CENTRE, self.CENTRE): tkinter.CENTER,
            (self.CENTRE, self.RIGHT): tkinter.E,
            (self.BOTTOM, self.LEFT): tkinter.SW,
            (self.BOTTOM, self.CENTRE): tkinter.S,
            (self.BOTTOM, self.RIGHT): tkinter.SE,
        }
        
        kw = dict()
        if angle is not None:
            kw.update(angle=angle)
        if font is None:
            font = self.defaultfont
        else:
            font = self.fonts[font]
        kw.update(font=font)
        colour = self._colour(colour)
        kw.update(fill=colour)
        
        (ox, oy) = offset
        ox *= self.scaling[0]
        oy *= self.scaling[1]
        
        if isinstance(text, str):
            kw.update(anchor=anchors[(vert, horiz)])
            if width is not None:
                kw.update(width=width * self.scaling[0])
            self.canvas.create_text(ox, oy, text=text, **kw)
            return
        
        length = sum(font.measure(seg["text"]) for seg in text)
        anchor = anchors[(vert, self.LEFT)]
        anchors = {self.LEFT: 0, self.CENTRE: 0.5, self.RIGHT: 1}
        pos = -length * anchors[horiz]
        (cos, sin) = self._rotation(angle or 0)
        for seg in text:
            x = ox + pos * cos
            y = oy + pos * sin
            text = seg["text"]
            self.canvas.create_text(x, y, text=text, anchor=anchor, **kw)
            newpos = pos + font.measure(text)
            
            if seg.get("overline"):
                linespace = font.metrics("linespace")
                anchors = {self.TOP: 0, self.CENTRE: 0.5, self.RIGHT: 1}
                linespace *= anchors[vert]
                dx = +linespace * sin
                dy = -linespace * cos
                nx = ox + dx + newpos * cos
                ny = oy + dy + newpos * sin
                self.canvas.create_line(x + dx, y + dy, nx, ny, fill=colour)
            
            pos = newpos
    
    def _colour(self, colour):
        colour = (min(int(x * 0x1000), 0xFFF) for x in colour)
        return "#" + "".join(map("{:03X}".format, colour))
    
    def _rotation(self, rotate):
        th = radians(rotate * self.flip)
        return (cos(th), sin(th))

class Renderer(base.Renderer, base.Subview):
    def __init__(self, size, *pos,
    down=+1,  # -1 if y axis points upwards
    margin=0, **kw):
        (xsize, ysize) = size
        size = (xsize + 2 * margin, ysize + 2 * margin)
        raw = _RawRenderer(size, *pos, down=down, **kw)
        if down < 0:
            offset = (margin, -margin - ysize)
        else:
            offset = (margin, margin)
        base.Subview.__init__(self, raw, offset=offset, colour=(0, 0, 0))
    
    def addfont(self, id, size, family, *, italic=False, bold=False):
        kw = dict()
        if italic:
            kw.update(slant="italic")
        if bold:
            kw.update(weight="bold")
        size = -round(size * self._parent.scaling[0])
        self._parent.fonts[id] = Font(family=family, size=size, **kw)
    
    def setdefaultfont(self, id):
        self._parent.defaultfont = self._parent.fonts[id]
    
    def finish(self):
        tkinter.mainloop()
