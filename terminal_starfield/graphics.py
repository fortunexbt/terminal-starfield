"""Authored worlds and small 3-D silhouettes, drawn without terminal I/O.

The canvas is intentionally duck typed. Art stays independent of simulation and
the renderer, and the same geometry has a plain ASCII rasterization.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

RGB = Tuple[int, int, int]
Point = Tuple[float, float]
Vertex = Tuple[float, float, float]
Face = Tuple[Tuple[int, ...], float]


def tint(color: RGB, light: float) -> RGB:
    return tuple(min(255, max(0, round(channel * light))) for channel in color)  # type: ignore[return-value]


class VectorInk:
    """Accumulate continuous lines in 2 x 4 braille subcells before compositing."""

    BITS = ((1, 8), (2, 16), (4, 32), (64, 128))

    def __init__(self, canvas, color: RGB, priority: int = 5, top: int = 0, bottom: int = 100000):
        self.canvas, self.color, self.priority = canvas, color, priority
        self.top, self.bottom = max(0, top), min(canvas.height - 1, bottom)
        self.dots: Dict[Tuple[int, int], int] = {}

    def line(self, a: Point, b: Point) -> None:
        if not self.canvas.unicode:
            dx, dy = b[0] - a[0], b[1] - a[1]
            glyph = "-" if abs(dx) > abs(dy) * 2.5 else "|" if abs(dy) > abs(dx) else "\\" if dx * dy > 0 else "/"
            steps = max(1, math.ceil(max(abs(dx), abs(dy))))
            for i in range(steps + 1):
                x, y = round(a[0] + dx * i / steps), round(a[1] + dy * i / steps)
                if self.top <= y <= self.bottom:
                    self.canvas.put(x, y, glyph, self.color, "", self.priority)
            return
        x0, y0, x1, y1 = a[0] * 2, a[1] * 4, b[0] * 2, b[1] * 4
        # Geometry is bounded by the viewport by callers. Capping samples also
        # keeps a near-plane or resize edge case from making a frame expensive.
        steps = min(2000, max(1, math.ceil(max(abs(x1 - x0), abs(y1 - y0)))))
        for i in range(steps + 1):
            px, py = round(x0 + (x1 - x0) * i / steps), round(y0 + (y1 - y0) * i / steps)
            x, y = px // 2, py // 4
            if 0 <= x < self.canvas.width and self.top <= y <= self.bottom:
                key = (x, y)
                self.dots[key] = self.dots.get(key, 0) | self.BITS[py % 4][px % 2]

    def path(self, points: Iterable[Point], closed: bool = False) -> None:
        vertices = list(points)
        if closed and vertices:
            vertices.append(vertices[0])
        for a, b in zip(vertices, vertices[1:]):
            self.line(a, b)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, tilt: float = 0.0,
                start: float = 0.0, end: float = math.tau) -> None:
        points = []
        steps = max(12, min(160, math.ceil(abs(end - start) * rx * 1.2)))
        for i in range(steps + 1):
            angle = start + (end - start) * i / steps
            dx, dy = math.cos(angle) * rx, math.sin(angle) * ry
            points.append((cx + dx, cy + dy + dx * tilt))
        self.path(points)

    def flush(self) -> None:
        for (x, y), bits in self.dots.items():
            self.canvas.put(x, y, chr(0x2800 + bits), self.color, "", self.priority)


def planet(canvas, cx: float, cy: float, radius: float, palette: RGB,
           world: str, top: int, bottom: int, phase: float = 0.0) -> None:
    """A lit globe with an actual terminator, atmosphere and orbital rings."""
    ry = radius * .48
    ring = VectorInk(canvas, tint(palette, .48), 4, top, bottom)
    if world == "rings":
        for scale in (1.43, 1.53, 1.82):
            ring.ellipse(cx, cy, radius * scale, ry * scale * .27, -.15, math.pi, math.tau)
        ring.flush()
    atmosphere = VectorInk(canvas, tint(palette, .62), 5, top, bottom)
    atmosphere.ellipse(cx, cy, radius + .8, ry + .35, 0, math.pi * .70, math.pi * 1.80)
    atmosphere.flush()
    shades = " .,:;ox%#@" if world == "sun" else " .,:;oO#"
    for y in range(max(top, math.floor(cy - ry)), min(bottom, math.ceil(cy + ry)) + 1):
        ny = (y - cy) / max(1.0, ry)
        for x in range(max(0, math.floor(cx - radius)), min(canvas.width - 1, math.ceil(cx + radius)) + 1):
            nx = (x - cx) / max(1.0, radius)
            sphere = 1 - nx * nx - ny * ny
            if sphere <= 0:
                continue
            nz = math.sqrt(sphere)
            light = max(0.0, -.67 * nx - .36 * ny + .57 * nz)
            # Coherent latitude and continent fields, without random screen noise.
            land = math.sin(nx * 9 + math.sin(ny * 8) * 1.7 + phase) * math.cos(ny * 11 - nx * 3)
            if world == "sun":
                light = .52 + .32 * nz + .12 * land
            elif world == "rings":
                light *= .75 + .22 * math.sin(ny * 28 + nx * 2)
            else:
                light *= .72 if land > .18 else 1.04
            index = min(len(shades) - 1, int(light * (len(shades) - 1)))
            # The unlit hemisphere masks background stars instead of glowing.
            char = shades[index] if light > .09 else " "
            color = tint(palette, .18 + light * .70)
            canvas.put(x, y, char, color, "", 6)
    if world == "rings":
        ring = VectorInk(canvas, tint(palette, .72), 8, top, bottom)
        for scale in (1.43, 1.53, 1.82):
            ring.ellipse(cx, cy, radius * scale, ry * scale * .27, -.15, 0, math.pi)
        ring.flush()
    if world == "sun":
        corona = VectorInk(canvas, tint(palette, .42), 5, top, bottom)
        for start, end in ((.2, 1.2), (2.2, 3.8), (4.3, 5.8)):
            corona.ellipse(cx, cy, radius * 1.12, ry * 1.12, start=start, end=end)
        corona.flush()


def ruins(canvas, cx: float, cy: float, radius: float, palette: RGB, top: int, bottom: int) -> None:
    """A fractured orbital gate: two depth planes, sparse broken ribs."""
    ink = VectorInk(canvas, tint(palette, .55), 7, top, bottom)
    ry = radius * .63
    for start, end in ((-.2, 1.1), (1.35, 2.9), (3.15, 4.45), (4.9, 5.8)):
        ink.ellipse(cx, cy, radius, ry, .08, start, end)
        ink.ellipse(cx + 2.5, cy - 1.3, radius * .92, ry * .92, .08, start, end)
    for i in range(14):
        angle = i * math.tau / 14
        if i in (3, 7, 11):
            continue
        a = (cx + math.cos(angle) * radius, cy + math.sin(angle) * ry + math.cos(angle) * radius * .08)
        b = (cx + 2.5 + math.cos(angle) * radius * .92,
             cy - 1.3 + math.sin(angle) * ry * .92 + math.cos(angle) * radius * .074)
        ink.line(a, b)
    ink.path(((cx - radius * .8, cy + ry * .7), (cx - radius * 1.1, cy + ry * 1.1),
              (cx - radius * .55, cy + ry * .85)))
    ink.flush()
    canvas.text(round(cx - radius), round(cy + ry + 1), "GATE // OFFLINE", tint(palette, .5), "dim", 7)


def draw_world(canvas, state, route, top: int, bottom: int) -> None:
    if canvas.width < 40 or bottom - top < 7:
        return
    radius = min(canvas.width * .17, (bottom - top) * .80)
    cx = canvas.width * .16 - state.heading_x * 11 - state.velocity_x * 7
    cy = top + (bottom - top) * .33 - state.heading_y * 5
    if route.world == "ruins":
        ruins(canvas, cx, cy, radius * .78, route.palette, top, bottom)
    else:
        planet(canvas, cx, cy, radius, route.palette, route.world, top, bottom, state.elapsed * .015)
    # Tiny navigational callout anchors scale while leaving the gun corridor open.
    if canvas.width >= 80 and bottom - top >= 17:
        canvas.text(2, bottom - 5, route.name, tint(route.palette, .60), "", 9)
        canvas.text(2, bottom - 4, "LOCAL ORBIT  /  {:02d}".format(state.sector), tint(route.palette, .36), "dim", 9)


def _mesh(kind: str, shape: str) -> Tuple[List[Vertex], List[Tuple[int, int]], List[Face]]:
    if kind == "boss" and shape == "seraph":
        vertices = [(0,-.25,-.6),(0,.8,.2),(-.22,.1,.4),(.22,.1,.4),
                    (-1,-.5,.3),(-.62,.14,-.3),(-.9,.7,.7),(-.3,.44,.4),
                    (1,-.5,.3),(.62,.14,-.3),(.9,.7,.7),(.3,.44,.4)]
        edges = [(0,2),(2,1),(1,3),(3,0),(0,4),(4,5),(5,2),(2,6),(6,7),(7,1),
                 (0,8),(8,9),(9,3),(3,10),(10,11),(11,1),(4,6),(8,10)]
        faces = [((0,4,5,2), .60), ((4,6,2,5), .29), ((2,6,7,1), .37),
                 ((0,8,9,3), .44), ((8,10,3,9), .24), ((3,10,11,1), .31),
                 ((0,2,1), .66), ((0,1,3), .46)]
    elif kind == "boss" and shape == "citadel":
        vertices = [(-1,.3,.3),(-1,-.35,.3),(-.67,-.35,.3),(-.67,-.7,.1),
                    (-.38,-.7,.1),(-.38,-.25,-.3),(0,-.9,-.4),(.38,-.25,-.3),
                    (.38,-.7,.1),(.67,-.7,.1),(.67,-.35,.3),(1,-.35,.3),(1,.3,.3),
                    (.5,.55,.6),(0,.38,-.6),(-.5,.55,.6),(0,-.15,-.7)]
        edges = [(i,i+1) for i in range(15)] + [(15,0),(0,14),(12,14),(6,16),(16,14),(5,16),(7,16),(3,15),(9,13)]
        faces = [((0,1,2,15), .42), ((2,3,4,5,15), .58), ((5,16,14,15), .31),
                 ((7,8,9,10,13), .44), ((10,11,12,13), .30), ((7,13,14,16), .26),
                 ((5,6,16), .70), ((6,7,16), .51), ((0,14,15), .25), ((12,13,14), .22)]
    elif kind == "boss":
        vertices = [(-.25,0,-.9),(0,-.55,-.4),(.25,0,-.9),(0,.6,-.4),
                    (-.85,-.7,.3),(-.65,-.7,.3),(-.65,.7,.5),(-.85,.7,.5),
                    (.85,-.7,.3),(.65,-.7,.3),(.65,.7,.5),(.85,.7,.5),
                    (-.48,0,.3),(.48,0,.3),(0,0,.7)]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(8,9),(9,10),(10,11),(11,8),
                 (0,12),(12,5),(12,6),(2,13),(13,9),(13,10),(1,14),(3,14)]
        faces = [((4,5,6,7), .56), ((8,9,10,11), .38), ((0,12,5,1), .35),
                 ((0,3,6,12), .25), ((2,1,9,13), .29), ((2,13,10,3), .22),
                 ((0,1,14), .66), ((1,2,14), .45), ((2,3,14), .31), ((3,0,14), .50)]
    elif kind == "frigate":
        vertices = [(-.85,-.45,.2),(.85,-.45,.2),(1,.4,.5),(-1,.4,.5),
                    (-.35,-.3,-.7),(.35,-.3,-.7),(.4,.5,-.4),(-.4,.5,-.4)]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        faces = [((0,1,5,4), .64), ((0,4,7,3), .44), ((1,2,6,5), .28),
                 ((2,3,7,6), .23), ((4,5,6,7), .51)]
    elif kind == "hunter":
        vertices = [(0,-.5,-.8),(-1,.15,.5),(-.4,.6,.2),(0,.25,-.3),(.4,.6,.2),(1,.15,.5)]
        edges = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,0),(0,3)]
        faces = [((0,1,2,3), .50), ((0,3,4,5), .31)]
    else:
        vertices = [(0,-.55,-.7),(-.85,.5,.4),(0,.25,.1),(.85,.5,.4),(0,.65,.6)]
        edges = [(0,1),(1,2),(2,3),(3,0),(0,2),(1,4),(3,4)]
        faces = [((0,1,2), .52), ((0,2,3), .33), ((1,4,3,2), .23)]
    return vertices, edges, faces


def _fill_face(canvas, polygon: List[Point], color: RGB, light: float, top: int, bottom: int) -> None:
    """Opaque, uniformly hatched hull planes; no animated grain or screen noise.

    Half-cell scanlines support the concave wing and citadel panels. The vector
    outline, reticle and committed impact marks all composite above this ink.
    """
    level = 2 if light >= .5 else 1 if light >= .3 else 0
    glyph = ("·", "░", "▒")[level] if canvas.unicode else (".", ":", "=")[level]
    shade = tint(color, light)
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    for y in range(max(top, 0, math.floor(min(p[1] for p in polygon))),
                   min(bottom, canvas.height - 1, math.ceil(max(p[1] for p in polygon))) + 1):
        scan = y + .5
        intersections = []
        for a, b in edges:
            if (a[1] <= scan < b[1]) or (b[1] <= scan < a[1]):
                intersections.append(a[0] + (scan - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        intersections.sort()
        for left, right in zip(intersections[::2], intersections[1::2]):
            for x in range(max(0, math.ceil(left - .5)), min(canvas.width - 1, math.floor(right - .5)) + 1):
                canvas.put(x, y, glyph, shade, "", 53)


def draw_ship(canvas, enemy, cx: int, cy: int, span: float, color: RGB,
              shape: str, top: int, bottom: int) -> None:
    vertices, edges, faces = _mesh(enemy.kind, shape)
    yaw = math.sin(enemy.spin * .28 + enemy.phase) * .13
    bank = math.sin(enemy.spin * .4) * (.04 if enemy.kind == "boss" else .12)
    points: List[Point] = []
    depth: List[float] = []
    for x, y, z in vertices:
        rx = x * math.cos(yaw) + z * math.sin(yaw)
        rz = z * math.cos(yaw) - x * math.sin(yaw)
        perspective = 1 / (1 + rz * .18)
        points.append((cx + rx * span * .5 * perspective,
                       cy + (y + rx * bank) * span * .23 * perspective))
        depth.append(rz)
    # Deliberate face values establish a consistent upper-left key light.
    # Paint distant panels first so the projected hull remains opaque in turns.
    for indices, light in sorted(faces, key=lambda face: sum(depth[i] for i in face[0]) / len(face[0]), reverse=True):
        _fill_face(canvas, [points[i] for i in indices], color, light, top, bottom)
    ink = VectorInk(canvas, color, 55, top, bottom)
    for a, b in edges:
        ink.line(points[a], points[b])
    ink.flush()
    canvas.put(cx, cy, "◇" if canvas.unicode else "*", color, "bold", 58)


def jump_rings(canvas, progress: float, palette: RGB, top: int, bottom: int) -> None:
    cx, cy = (canvas.width - 1) * .5, (top + bottom) * .5
    ink = VectorInk(canvas, tint(palette, .8), 5, top, bottom)
    for i in range(5):
        fraction = ((i / 5 + progress * .8) % 1.0) ** 2
        rx = 3 + fraction * canvas.width * .70
        ink.ellipse(cx, cy, rx, rx * .32)
    ink.flush()
