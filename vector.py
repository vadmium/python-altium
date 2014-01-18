from xml.sax.saxutils import XMLGenerator
from contextlib import contextmanager
from tkinter import Tk
import tkinter
import operator

class Renderer:
    def set_objects(self, objects):
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

class SvgRenderer(Renderer):
    def __init__(self, size, line=0.4, colour="black"):
        self.svg = XMLGenerator(encoding="UTF-8", short_empty_elements=True)
        self.svg.startElement("svg", {
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "xmlns": "http://www.w3.org/2000/svg",
            "width": "{}mm".format(size[0]),
            "height": "{}mm".format(size[1]),
            "viewBox": "{},{} {},{}".format(0, 0, size[0], size[1]),
        })
        
        style = """
            /*.outline, path,*/ line/*, polyline*/ {{
                stroke: {colour};
                fill: none;
                stroke-width: {line};
            }}
            
            .solid {{
                fill: {colour};
                stroke: none;
            }}
        """
        style = style.format(line=line, colour=colour)
        tree(self.svg, (("style", dict(type="text/css"), (style,)),))
    
    def set_objects(self, objects):
        with element(self.svg, "defs", dict()):
            for d in objects:
                with element(self.svg, "g", dict(id=type(d).__name__)):
                    d.draw(self)
    
    def draw(self, object, offset):
        attrs = {"xlink:href": "#{}".format(type(object).__name__)}
        if offset:
            attrs.update(zip("xy", map(format, offset)))
        emptyElement(self.svg, "use", attrs)
    
    def line(self, *points):
        attrs = dict()
        for (n, p) in enumerate(points, 1):
            for (x, s) in zip(p, "xy"):
                attrs[s + format(n)] = format(x)
        emptyElement(self.svg, "line", attrs)
    
    def circle(self, r, point=None):
        attrs = {"r": format(r), "class": "solid"}
        if point:
            attrs.update(zip(("cx", "cy"), map(format, point)))
        emptyElement(self.svg, "circle", attrs)
    
    def polygon(self, points):
        points = " ".join(",".join(map(format, point)) for point in points)
        attrs = {"class": "solid", "points": points}
        emptyElement(self.svg, "polygon", attrs)
    
    def rectangle(self, dim, start=None):
        attrs = {"class": "solid"}
        attrs.update(zip(("width", "height"), map(format, dim)))
        if start:
            attrs.update(zip("xy", map(format, start)))
        emptyElement(self.svg, "rect", attrs)
    
    def finish(self):
        self.svg.endElement("svg")

class TkRenderer(Renderer):
    def __init__(self, size, line=0.4, colour="black"):
        self.colour = colour
        
        root = Tk()
        self.scaling = root.call("tk", "scaling") * 72 / 25.4  # pixels/mm
        self.linewidth = line * self.scaling
        self.canvas = tkinter.Canvas(root,
            relief=tkinter.SUNKEN, borderwidth=1,
            background="white",
            height=size[1] * self.scaling, width=size[0] * self.scaling,
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
    
    def line(self, a=(0, 0), b=(0, 0)):
        points = (x * self.scaling for point in (a, b) for x in point)
        self.canvas.create_line(*points, fill=self.colour, width=self.linewidth)
    
    def circle(self, r, centre=(0, 0)):
        coords = tuple((o - r, o + r) for o in centre)
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_oval(*points, fill=self.colour, width=0)
    
    def polygon(self, points):
        points = tuple(x * self.scaling for point in points for x in point)
        self.canvas.create_polygon(points)
    
    def rectangle(self, dim, start=(0, 0)):
        coords = tuple((x, o + x) for (x, o) in zip(start, dim))
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_rectangle(*points, fill=self.colour, width=0)
    
    def finish(self):
        tkinter.mainloop()

@contextmanager
def element(xml, name, *pos, **kw):
    xml.startElement(name, *pos, **kw)
    yield
    xml.endElement(name)

def emptyElement(*pos, **kw):
    with element(*pos, **kw):
        pass

def tree(xml, elements):
    for e in elements:
        if isinstance(e, str):
            xml.characters(e)
        else:
            (name, attrs, children) = e
            with element(xml, name, attrs):
                tree(xml, children)
