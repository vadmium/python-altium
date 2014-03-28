import operator
from contextlib import contextmanager

class Renderer:
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
    
    def addobjects(self, objects):
        pass
    
    def draw(self, object, offset=None):
        with self.offset(offset) as offset:
            object.draw(offset)
    
    @contextmanager
    def offset(self, offset):
        yield OffsetRenderer(self, offset)
    
    CENTRE = 0
    LEFT = -1
    RIGHT = +1
    TOP = -1
    BOTTOM = +1

class OffsetRenderer:
    def __init__(self, renderer, offset):
        self._renderer = renderer
        self._offset = offset
    
    def line(self, *pos, offset=None, **kw):
        self._renderer.line(*pos, offset=self._map(offset), **kw)
    def hline(self, *pos, offset=None, **kw):
        self._renderer.hline(*pos, offset=self._map(offset), **kw)
    def vline(self, *pos, offset=None, **kw):
        self._renderer.vline(*pos, offset=self._map(offset), **kw)
    def polygon(self, points, *pos, **kw):
        self._renderer.polygon(map(self._map, points), *pos, **kw)
    def polyline(self, points, *pos, **kw):
        self._renderer.polyline(map(self._map, points), *pos, **kw)
    def circle(self, r, offset=None, *pos, **kw):
        self._renderer.circle(r, self._map(offset), *pos, **kw)
    def rectangle(self, *pos, offset=None, **kw):
        self._renderer.rectangle(*pos, offset=self._map(offset), **kw)
    
    def _map(self, point):
        if not self._offset:
            return point
        if not point:
            return self._offset
        return map(operator.add, point, self._offset)
