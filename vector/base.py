import operator

class Renderer:
    def addobjects(self, objects):
        pass
    
    def draw(self, object, offset=None):
        object.draw(OffsetRenderer(self, offset))

class OffsetRenderer:
    def __init__(self, renderer, offset):
        self.renderer = renderer
        self.offset = offset
    
    def line(self, *points):
        if self.offset:
            points = (map(operator.add, point, self.offset) for
                point in points)
        self.renderer.line(*points)
    
    def circle(self, r, centre=None):
        if centre or self.offset:
            centre = centre or (0, 0)
            centre = map(operator.add, centre, self.offset or (0, 0))
            self.renderer.circle(r, centre)
        else:
            self.renderer.circle(r)
    
    def polygon(self, points):
        if self.offset:
            points = (map(operator.add, point, self.offset) for
                point in points)
        self.renderer.polygon(points)
    
    def rectangle(self, dim, start=None):
        if start or self.offset:
            start = map(operator.add, start or (0, 0), self.offset or (0, 0))
            self.renderer.rectangle(dim, start)
        else:
            self.renderer.rectangle(dim)
