from xml.sax.saxutils import XMLGenerator
from contextlib import contextmanager
from . import base
from math import sin, cos, radians
from collections import Iterable
from urllib.parse import urlunparse, ParseResult
import operator
from math import copysign

class Renderer(base.Renderer):
    def __init__(self, size, units, unitmult=1, *, margin=0,
    down=+1,  # -1 if y axis points upwards
    line=None, textsize=None, textbottom=False, colour=None):
        width = size[0] + 2 * margin
        height = size[1] + 2 * margin
        if down < 0:
            top = -size[1]
            self.flip = (+1, -1)
        else:
            top = 0
            self.flip = (+1, +1)
        viewbox = "{},{} {},{}".format(-margin, top - margin, width, height)
        
        self.xml = XMLGenerator(encoding="UTF-8", short_empty_elements=True)
        attrs = {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "width": "{}{}".format(width * unitmult, units),
            "height": "{}{}".format(height * unitmult, units),
            "viewBox": viewbox,
        }
        if line is None:
            self.linewidth = 1
        else:
            attrs["stroke-width"] = format(line)
            self.linewidth = line
        attrs.update(self._colour(colour))
        self.xml.startElement("svg", attrs)
        
        text = list()
        if textsize is not None:
            text.append("font-size: {}px".format(textsize))
        if textbottom:
            text.append("dominant-baseline: text-after-edge")
        text.append("fill: currentColor")
        
        self.rulesets = [
            (".outline, path, line, polyline",
                ("stroke: currentColor", "fill: none")),
            (".solid", ("fill: currentColor", "stroke: none")),
            ("text", text),
        ]
    
    def addfont(self, id, size, family, italic=None, bold=None):
        props = [
            "font-size: {}px".format(size),
            "font-family: {}".format(family),
        ]
        if italic:
            props.append("font-style: italic")
        if bold:
            props.append("font-weight: bold")
        self.rulesets.append(("." + id, props))
    
    def start(self):
        css = list()
        for (selector, rules) in self.rulesets:
            rules = "".join(map("  {};\n".format, rules))
            css.append("{} {{\n{}}}\n".format(selector, rules))
        self.tree(("style", dict(type="text/css"), css))
    
    def finish(self):
        self.xml.endElement("svg")
    
    def line(self, a, b=None, *pos, **kw):
        attrs = dict()
        if b:
            points = (a, b)
        else:
            points = (a,)
        for (n, p) in enumerate(points, 1 + 2 - len(points)):
            (x, y) = p
            attrs["x{}".format(n)] = format(x)
            attrs["y{}".format(n)] = format(y * self.flip[1])
        self._line(attrs, *pos, **kw)
    
    def hline(self, a, b=None, *pos,
    startarrow=None, endarrow=None, width=None, **kw):
        if b is None:
            b = a
            a = None
            reala = 0
        else:
            reala = a
        # Now a is always the start point and b is always the end point
        
        attrs = dict()
        
        dir = b - reala
        if startarrow:
            url = _buildurl(fragment=startarrow["name"])
            attrs["marker-start"] = "url({})".format(url)
            if startarrow["point"]:
                a = reala + copysign(startarrow["point"], dir)
            width = startarrow.get("width")
        if endarrow:
            url = _buildurl(fragment=endarrow["name"])
            attrs["marker-end"] = "url({})".format(url)
            b -= copysign(endarrow["point"], dir)
            width = endarrow.get("width")
        
        if a is not None:
            attrs["x1"] = format(a)
        attrs["x2"] = format(b)
        self._line(attrs, *pos, width=width, **kw)
    
    def vline(self, a, b=None, *pos, **kw):
        a = format(a * self.flip[1])
        if b is None:
            attrs = {"y2": a}
        else:
            attrs = {"y1": a, "y2": format(b * self.flip[1])}
        self._line(attrs, *pos, **kw)
    
    def _line(self, attrs, *, offset=None, width=None, colour=None):
        self._width(attrs, width)
        attrs.update(self._colour(colour))
        transform = self._offset(offset)
        self.emptyelement("line", attrs, transform=transform)
    
    def polyline(self, points, *, colour=None, **kw):
        s = list()
        for (x, y) in points:
            s.append("{},{}".format(x, y * self.flip[1]))
        attrs = {"points": " ".join(s)}
        self._width(attrs, **kw)
        attrs.update(self._colour(colour))
        self.emptyelement("polyline", attrs)
    
    def cubicbezier(self, a, b, c, d, *,
    offset=None, colour=None, width=None):
        attrs = dict(self._colour(colour))
        s = list()
        for p in (a, b, c, d):
            s.append("{},{}".format(*map(operator.mul, p, self.flip)))
        attrs["d"] = "M{} C {} {} {}".format(*s)
        self._width(attrs, width)
        self.emptyelement("path", attrs, transform=self._offset(offset))
    
    def circle(self, r, offset=None, *, outline=None, fill=None, width=None):
        attrs = {"r": format(r)}
        style = list()
        self._closed(attrs, style, outline, fill, width)
        if offset:
            (x, y) = offset
            attrs["cx"] = format(x)
            attrs["cy"] = format(y * self.flip[1])
        self.emptyelement("circle", attrs, style=style)
    
    def polygon(self, points, *,
    offset=None, rotate=None, outline=None, fill=None, width=None):
        s = list()
        for (x, y) in points:
            s.append("{},{}".format(x, y * self.flip[1]))
        attrs = {"points": " ".join(s)}
        style = list()
        transform = self._offset(offset)
        if rotate is not None:
            transform.append("rotate({})".format(rotate))
        self._closed(attrs, style, outline, fill, width)
        self.emptyelement("polygon", attrs, style=style, transform=transform)
    
    def rectangle(self, a, b=None, *, offset=None,
    outline=None, fill=None, width=None, _attrs=()):
        """
        rectangle(a) -> <rect width=a />
        rectangle(a, b) -> <rect x=a width=(b - a) />
        
        Offset implemented independently using transform="translate(offset)"
        """
        
        attrs = dict(_attrs)
        style = list()
        transform = list()
        if b:
            (x, y) = a
            attrs["x"] = format(x)
            attrs["y"] = format(y * self.flip[1])
            (bx, by) = b
            w = bx - x
            h = by - y
        else:
            (w, h) = a
        h *= self.flip[1]
        
        # Compensate for SVG not allowing negative dimensions
        translate = dict()
        if w < 0:
            translate["x"] = w
            w = -w
        if h < 0:
            translate["y"] = h
            h = -h
        if translate:
            if b:
                # x and y attributes already used for a, so use a transform
                x = translate.get("x", 0)
                y = translate.get("y", 0)
                transform.append("translate({}, {})".format(x, y))
            else:
                attrs.update(translate)
        attrs["width"] = format(w)
        attrs["height"] = format(h)
        
        transform.extend(self._offset(offset))
        self._closed(attrs, style, outline, fill, width)
        self.emptyelement("rect", attrs, style=style, transform=transform)
    
    def roundrect(self, r, *pos, **kw):
        (x, y) = r
        attrs = {"rx": format(x), "ry": format(y)}
        return self.rectangle(*pos, _attrs=attrs, **kw)
    
    def _closed(self, attrs, style, outline=None, fill=None, width=None):
        if fill:
            attrs["class"] = "solid"
            if isinstance(fill, Iterable):
                style.extend(self._colour(fill, "fill"))
        else:
            attrs["class"] = "outline"
        if isinstance(outline, Iterable):
            style.extend(self._colour(outline, "stroke"))
        self._width(attrs, width)
    
    def _width(self, attrs, width=None):
        if width is not None:
            attrs["stroke-width"] = format(width)
    
    def arc(self, r, start, end, offset=None, *, colour=None):
        if abs(end - start) >= 360:
            return self.circle(r, offset, outline=colour)
            attrs = {"r": format(*r), "class": "outline"}
            if offset:
                (x, y) = offset
                attrs["cx"] = format(x)
                attrs["cy"] = format(y * self.flip[1])
            attrs.update(self._colour(colour))
            renderer.emptyelement("circle", attrs)
        
        a = list()
        d = list()
        for x in range(2):
            sincos = (cos, sin)[x]
            da = sincos(radians(start))
            db = sincos(radians(end))
            a.append(format(da * r[x] * self.flip[x]))
            d.append(format((db - da) * r[x] * self.flip[x]))
        large = (end - start) % 360 > 180
        at = dict(self._colour(colour))
        at["d"] = "M{a} a{r} 0 {large:d},0 {d}".format(
            a=",".join(a),
            r=",".join(map(format, r)),
            large=large,
            d=",".join(d),
        )
        self.emptyelement("path", at, transform=self._offset(offset))
    
    def text(self, text, offset=None, horiz=None, vert=None, *,
    angle=None, font=None, colour=None):
        attrs = dict()
        style = list()
        transform = list()
        if vert is not None:
            baselines = {
                self.CENTRE: "middle",
                self.TOP: "text-before-edge",
                self.BOTTOM: "text-after-edge",
            }
            style.append(("dominant-baseline", baselines[vert]))
        if horiz is not None:
            anchors = {
                self.CENTRE: "middle",
                self.LEFT: "start",
                self.RIGHT: "end",
            }
            style.append(("text-anchor", anchors[horiz]))
        
        if angle is not None:
            transform.extend(self._offset(offset))
            transform.append("rotate({})".format(angle))
        elif offset:
            (x, y) = offset
            attrs["x"] = format(x)
            attrs["y"] = format(y * self.flip[1])
        
        if font is not None:
            attrs["class"] = font
        attrs.update(self._colour(colour))
        with self.element("text", attrs, style=style, transform=transform):
            if isinstance(text, str):
                self.xml.characters(text)
            else:
                for seg in text:
                    attrs = dict()
                    if seg.get("overline"):
                        attrs["text-decoration"] = "overline"
                    self.tree(("tspan", attrs, (seg["text"],)))
    
    def addobjects(self, objects=(), arrows=()):
        with self.element("defs"):
            for a in arrows:
                with self.element("marker", {
                    "overflow": "visible",
                    "markerUnits": "userSpaceOnUse",
                    "id": a["name"],
                }):
                    width = a.get("width", self.linewidth)
                    radius = a["radius"]
                    base = a["base"]
                    shoulder = a.get("shoulder", base)
                    
                    # Distance from shaft junction to point
                    point = base + (shoulder - base) * width / 2 / radius
                    a["point"] = point
                    
                    self.polygon((
                        (0, +width / 2),
                        (shoulder - point, +radius),
                        (-point, 0),
                        (shoulder - point, -radius),
                        (0, -width / 2),
                    ), fill=True)
            
            for d in objects:  # After arrows in case an object uses an arrow
                with self.element("g", dict(id=d.__name__)):
                    d(self)
    
    def draw(self, object, offset=None, *, rotate=None, colour=None):
        attrs = {"xlink:href": _buildurl(fragment=object.__name__)}
        transform = None
        if rotate is not None:
            transform = self._offset(offset)
            transform.append("rotate({})".format(rotate * 90 * self.flip[1]))
        elif offset:
            (x, y) = offset
            attrs["x"] = format(x)
            attrs["y"] = format(y * self.flip[1])
        attrs.update(self._colour(colour))
        self.emptyelement("use", attrs, transform=transform)
    
    @contextmanager
    def view(self, *, offset=None, rotate=None, colour=None):
        transform = self._offset(offset)
        if rotate is not None:
            transform.append("rotate({})".format(rotate * self.flip[1] * 90))
        attrs = dict(self._colour(colour))
        with self.element("g", attrs, transform=transform):
            yield self
    
    def _offset(self, offset=None):
        if offset:
            (x, y) = offset
            y *= self.flip[1]
            return [("translate({}, {})".format(x, y))]
        else:
            return []
    
    def _colour(self, colour=None, attr="color"):
        if colour:
            colour = (min(int(x * 0x100), 0xFF) for x in colour)
            return ((attr, "#" + "".join(map("{:02X}".format, colour))),)
        else:
            return ()
    
    @contextmanager
    def element(self, name, attrs=(), style=None, transform=None):
        attrs = dict(attrs)
        if style:
            attrs["style"] = "; ".join("{}: {}".format(*s) for s in style)
        if transform:
            attrs["transform"] = " ".join(transform)
        self.xml.startElement(name, attrs)
        yield
        self.xml.endElement(name)
    
    def emptyelement(self, *pos, **kw):
        with self.element(*pos, **kw):
            pass
    
    def tree(self, *elements):
        for e in elements:
            if isinstance(e, str):
                self.xml.characters(e)
            else:
                (name, attrs, children) = e
                with self.element(name, attrs):
                    self.tree(*children)

def _buildurl(
scheme="", netloc="", path="", params="", query="", fragment=""):
    struct = ParseResult(scheme, netloc, path, params, query, fragment)
    return urlunparse(struct)
