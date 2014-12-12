import operator
from contextlib import contextmanager
from collections import Iterable

class View:
    def draw(self, object, offset=None, **kw):
        with self.view(offset=offset, **kw) as view:
            object(view)
    
    @contextmanager
    def view(self, **kw):
        """A context manager that returns a new view object
        
        The context manager should be exited
        before making any more rendering calls on the parent view."""
        
        yield Subview(self, **kw)
    
    # Values such that:
    # * Text aligned at point (align_x, align_y) is
    #     inside a double unit square, aligned to adjacent edges,
    #     and is centred between pairs of distant edges
    # * Negating an alignment value
    #     mirrors between left and right, and top and bottom
    # * An alignment is considered false precisely if it is centred
    CENTRE = 0
    LEFT = -1
    RIGHT = +1
    TOP = -1
    BOTTOM = +1
    
    START = 1 << 0
    END = 1 << 1

class Renderer(View):
    """
    Arrow shapes are defined by:
    * point: Where the line would end without the arrow
    * shoulder: Part laterally furthest away from the shaft
    * base: Where the lines from the shoulders intersect
    
    shoulder __
            \  ---___
    --------+\       --
            | >base    >point
    --------+/    ___--
            /__---
    
    Attributes of arrows:
    * width: Of shaft; default used if omitted
    * base: Distance from point to base
    * shoulder: Longitudinal distance from point to shoulder
    * radius: Lateral distance from axis to shoulder
    
    Types of shapes:
    * Dart, chevron, barbed, concave arrowhead; shoulder > base:  ===>>
    * Triangular arrowhead; shoulder = base:  ===|>
    * Diamond, convex; 0 < shoulder < base:  ===<>
    * Triangular tail; shoulder = 0:  ===<|
    
    Text is rendered by the text() method. The "text" argument may be:
    * A simple plain text string
    * A sequence of dict() objects, each specifying a formatted text segment.
        Not supported in combination with text wrapping.
    The default alignment is left- and bottom-aligned.
    """
    
    def start(self):
        pass
    
    def hline(self, a, b=None, **kw):
        if b is not None:
            kw.update(b=(b, 0))
        self.line((a, 0), **kw)
    
    def vline(self, a, b=None, **kw):
        if b is not None:
            kw.update(b=(0, b))
        self.line((0, a), **kw)
    
    def roundrect(self, r, a, b=None, *, offset=None,
    fill=None, outline=None, **kw):
        if not all(r):
            return self.rectangle(a, b,
                offset=offset, fill=fill, outline=outline, **kw)
        
        if b:
            (ax, ay) = a
            (bx, by) = b
        else:
            (ax, ay) = (0, 0)
            (bx, by) = a
        fill = fill and tuple(fill)
        outline = outline and tuple(outline)
        
        # Only positive dimensions are considered
        (rx, ry) = r
        assert rx == ry
        r = rx
        cax = ax + rx
        cay = ay + ry
        cbx = bx - rx
        cby = by - ry
        
        with self.view(offset=offset):
            # TODO: circles not good enough if fill=None; need arcs
            c0 = (cax, cay)
            self.circle(r, c0, fill=fill, outline=outline, **kw)
            c = (cbx, cay)
            if c != c0:
                self.circle(r, c, fill=fill, outline=outline, **kw)
            c = (cax, cby)
            if c != c0:
                self.circle(r, c, fill=fill, outline=outline, **kw)
            c = (cbx, cby)
            if c != c0:
                self.circle(r, c, fill=fill, outline=outline, **kw)
            
            if cby != cay:
                if fill:
                    self.rectangle((ax, cay), (bx, cby), fill=fill)
                if outline or not fill:
                    self.vline(cay, cby, offset=(ax, 0), colour=outline)
                    self.vline(cay, cby, offset=(bx, 0), colour=outline)
            if cbx != cax:
                if fill:
                    self.rectangle((cax, ay), (cbx, by), fill=fill)
                if outline or not fill:
                    self.hline(cax, cbx, offset=(0, ay), colour=outline)
                    self.hline(cax, cbx, offset=(0, by), colour=outline)
    
    def addobjects(self, objects=(), arrows=()):
        pass

class Subview(View):
    def __init__(self, parent, *, offset=None, rotate=None, colour=None):
        self._parent = parent
        self._rotatearg = rotate
        
        # Copy parameters in case they are generators or mutable
        if offset:
            self._offset = tuple(offset)
        else:
            self._offset = None
        if colour:
            self._colour = tuple(colour)
        else:
            self._colour = None
        
        self._rotation = self._rotatearg or 0
    
    def line(self, *pos, colour=None, **kw):
        pos = map(self._rotate, pos)
        self._map_offset(kw)
        colour = colour or self._colour
        return self._parent.line(*pos, colour=colour, **kw)
    
    def hline(self, *pos, colour=None, **kw):
        self._map_offset(kw)
        colour = colour or self._colour
        if self._rotation & 2:
            pos = map(operator.neg, pos)  # Rotate by 180 degrees
        if self._rotation & 1:
            method = self._parent.vline  # Rotate by 90 degrees
        else:
            method = self._parent.hline
        return method(*pos, colour=colour, **kw)
    
    def vline(self, *pos, colour=None, **kw):
        self._map_offset(kw)
        colour = colour or self._colour
        if self._rotation + 1 & 2:
            pos = map(operator.neg, pos)  # Rotate by 180 degrees
        if self._rotation + 1 & 1:
            method = self._parent.vline
        else:
            method = self._parent.hline  # Rotate by -90 degrees
        return method(*pos, colour=colour, **kw)
    
    def polygon(self, *pos, rotate=None, **kw):
        self._closed(kw)
        if rotate is None:
            rotate = self._rotatearg
        else:
            rotate += self._rotation
        return self._parent.polygon(*pos, rotate=rotate, **kw)
    
    def polyline(self, points, *pos, colour=None, **kw):
        points = map(self._map, points)
        colour = colour or self._colour
        return self._parent.polyline(points, *pos, colour=colour, **kw)
    def cubicbezier(self, *points, colour=None, **kw):
        self._map_offset(kw)
        return self._parent.cubicbezier(*map(self._rotate, points),
            colour=colour or self._colour,
        **kw)
    def arc(self, r, start, end, offset=None, *, colour=None):
        kw = dict(offset=offset)
        r = self._rotate(r)
        self._map_offset(kw)
        start += self._rotation * 90
        end += self._rotation * 90
        colour = colour or self._colour
        return self._parent.arc(r, start, end, colour=colour, **kw)
    def circle(self, r, offset=None, **kw):
        kw.update(offset=offset)
        self._closed(kw)
        return self._parent.circle(r, **kw)
    def rectangle(self, *pos, **kw):
        pos = map(self._rotate, pos)
        self._closed(kw)
        return self._parent.rectangle(*pos, **kw)
    def roundrect(self, r, *pos, **kw):
        pos = map(self._rotate, pos)
        self._closed(kw)
        return self._parent.roundrect(r, *pos, **kw)
    
    def text(self, text, *pos, angle=None, colour=None, **kw):
        if pos:  # First argument is offset
            pos = (self._map(pos[0]),) + pos[1:]
        else:
            self._map_offset(kw)
        if self._rotatearg is not None:
            if angle is None:
                angle = 0
            angle += self._rotation * 90
        colour = colour or self._colour
        return self._parent.text(text, *pos,
            angle=angle, colour=colour, **kw)
    
    def _map_offset(self, kw):
        offset = kw.get("offset")
        if offset:
            kw.update(offset=self._map(offset))
        else:
            if self._offset:
                kw.update(offset=self._offset)
    
    def _map(self, point):
        point = self._rotate(point)
        if not self._offset:
            return point
        return map(operator.add, point, self._offset)
    
    def _rotate(self, point):
        if self._rotation & 2:
            point = map(operator.neg, point)  # Rotate by 180 degrees
        if self._rotation & 1:
            (x, y) = point
            point = (-y, +x)  # Rotate by 90 degrees
        return point
    
    def _closed(self, kw):
        if self._colour:
            for param in ("fill", "outline"):
                if kw.get(param) and not isinstance(kw[param], Iterable):
                    kw[param] = self._colour
        self._map_offset(kw)
