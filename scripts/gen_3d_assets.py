"""Generate the animated 3D SVGs used by README.md.

GitHub strips <script> from rendered markdown, so nothing here is scripted:
the geometry is projected in Python at N keyframes and baked into SMIL
<animate> values. Browsers interpolate between the frames, which is real 3D
rotation rather than a 2D fake. Every animated element also carries a static
attribute, so a renderer without SMIL still shows a sensible still frame.

Six pieces, deliberately six different techniques, so the page doesn't read as
one effect repeated:

    ring-3d    perspective rotation of a torus of nodes and edges
    mesh-3d    a wave crossing a wireframe surface (animated polyline points)
    sphere-3d  a rotating tag sphere -- <text>, sized and faded by depth
    stack-3d   a fixed isometric architecture, with packets falling through it
    fleet-3d   vehicles driving routes on a ground plane in perspective
    voxel-3d   a field of isometric cubes bobbing on a wave (group transforms)

Usage:  python scripts/gen_3d_assets.py
Output: assets/{ring,mesh,sphere,stack,fleet,voxel}-3d-{light,dark}.svg

Every builder asserts that its geometry lands inside the viewBox, so a tweak
to a camera can't silently clip the artwork.
"""

from __future__ import annotations

import math
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# One palette per GitHub colour mode. Backgrounds stay transparent so the SVG
# sits on whatever GitHub paints behind it.
THEMES = {
    "light": {
        "edge": "#94a3b8",
        "node": "#4f46e5",
        "node_alt": "#0ea5e9",
        "alert": "#e11d48",
        "mesh_near": "#4f46e5",
        "mesh_far": "#a5b4fc",
        "text": "#334155",
        "muted": "#94a3b8",
        "slab_top": "#e0e7ff",
        "slab_left": "#a5b4fc",
        "slab_right": "#c7d2fe",
        "slab_line": "#6366f1",
        "cube_top": "#818cf8",
        "cube_left": "#4338ca",
        "cube_right": "#6366f1",
        "ground": "#cbd5e1",
        "route": "#0ea5e9",
    },
    "dark": {
        "edge": "#4c5a72",
        "node": "#a78bfa",
        "node_alt": "#22d3ee",
        "alert": "#fb7185",
        "mesh_near": "#a78bfa",
        "mesh_far": "#3b3168",
        "text": "#cbd5e1",
        "muted": "#64748b",
        "slab_top": "#312e81",
        "slab_left": "#1e1b4b",
        "slab_right": "#272160",
        "slab_line": "#818cf8",
        "cube_top": "#a78bfa",
        "cube_left": "#4c1d95",
        "cube_right": "#6d28d9",
        "ground": "#334155",
        "route": "#22d3ee",
    },
}


def r(value: float) -> str:
    """Round for file size; SMIL interpolates fine at one decimal."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


def rotate_y(point, angle):
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)


def rotate_x(point, angle):
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


class Camera:
    """Perspective camera that also reports how deep each point sits."""

    def __init__(self, width, height, distance, depth_span):
        self.width = width
        self.height = height
        self.distance = distance
        self.depth_span = depth_span
        self.seen = []  # every projected point, for the bounds check

    def project(self, point):
        x, y, z = point
        factor = self.distance / (self.distance - z)
        depth = max(0.0, min(1.0, (z + self.depth_span) / (2 * self.depth_span)))
        screen = (self.width / 2 + x * factor, self.height / 2 + y * factor)
        self.seen.append(screen)
        return (screen[0], screen[1], depth)

    def note(self, x, y):
        """Register a point for the bounds check without projecting it."""
        self.seen.append((x, y))

    def check(self, name, margin=2.0):
        """Fail loudly rather than ship art that is clipped by the viewBox."""
        xs = [x for x, _ in self.seen]
        ys = [y for _, y in self.seen]
        box = (min(xs), max(xs), min(ys), max(ys))
        if (box[0] < margin or box[1] > self.width - margin
                or box[2] < margin or box[3] > self.height - margin):
            raise SystemExit(
                f"{name}: geometry leaves the {self.width}x{self.height} "
                f"viewBox (x {box[0]:.0f}..{box[1]:.0f}, "
                f"y {box[2]:.0f}..{box[3]:.0f})"
            )
        return box


def animate(attribute, values, duration):
    return (f'<animate attributeName="{attribute}" values="{values}" '
            f'dur="{duration}s" repeatCount="indefinite"/>')


def series(values):
    return ";".join(r(v) for v in values)


def opacities(values):
    return ";".join(str(v) for v in values)


def isometric(point, width, height, lift=0.0):
    """True isometric projection: no perspective, 30 degrees each way."""
    x, y, z = point
    return (width / 2 + (x - z) * math.cos(math.radians(30)),
            height / 2 + (x + z) * math.sin(math.radians(30)) - y - lift)


def fibonacci_sphere(count: int, radius: float):
    """Evenly spread points on a sphere -- no clumping at the poles."""
    points = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(count):
        y = 1 - (i / (count - 1)) * 2
        ring = math.sqrt(max(0.0, 1 - y * y))
        theta = golden * i
        points.append((math.cos(theta) * ring * radius,
                       y * radius,
                       math.sin(theta) * ring * radius))
    return points


# ----------------------------- the rotating ring -----------------------------

def torus_points(count: int, major: float, minor: float):
    """Nodes spread over a torus: a ring of accounts with real thickness."""
    golden = math.pi * (3.0 - math.sqrt(5.0))
    points = []
    for i in range(count):
        phi = 2 * math.pi * i / count          # around the ring
        theta = golden * i * 2.0               # around the tube
        radius = major + minor * math.cos(theta)
        points.append((radius * math.cos(phi),
                       minor * math.sin(theta),
                       radius * math.sin(phi)))
    return points


def nearest_edges(points, per_node: int = 2):
    """Connect each node to its closest neighbours, deduplicated."""
    edges = set()
    for i, a in enumerate(points):
        closest = sorted(
            (math.dist(a, b), j) for j, b in enumerate(points) if j != i
        )
        for _, j in closest[:per_node]:
            edges.add((min(i, j), max(i, j)))
    return sorted(edges)


def ring_svg(theme: str, nodes: int = 44, frames: int = 30,
             width: int = 880, height: int = 280, duration: int = 26) -> str:
    """A money-movement ring, rotating in perspective.

    Wide and shallow on purpose: it reads as a banner rather than a blob, and
    a ring is the shape fraud actually makes in a transaction graph.
    """
    colours = THEMES[theme]
    major, minor = 290.0, 40.0
    tilt = math.radians(12)
    camera = Camera(width, height, distance=1800.0, depth_span=major + minor)
    points = torus_points(nodes, major, minor)
    edges = nearest_edges(points)
    alerts = {5, 16, 27, 38}  # a few nodes read as flagged accounts

    # frames + 1 so the last frame equals the first and the loop is seamless.
    projected = [
        [camera.project(rotate_x(rotate_y(p, 2 * math.pi * f / frames), tilt))
         for p in points]
        for f in range(frames + 1)
    ]
    camera.check(f"ring-3d-{theme}")

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="A ring of accounts and transfers rotating in 3D">',
        "<defs>",
        f'<radialGradient id="glow-{theme}">'
        f'<stop offset="0%" stop-color="{colours["alert"]}" stop-opacity=".5"/>'
        f'<stop offset="100%" stop-color="{colours["alert"]}" stop-opacity="0"/>'
        "</radialGradient>",
        "</defs>",
        # Edges first so the nodes sit on top of them.
        f'<g stroke="{colours["edge"]}" stroke-width="1" fill="none">',
    ]

    for i, j in edges:
        xs1 = [frame[i][0] for frame in projected]
        ys1 = [frame[i][1] for frame in projected]
        xs2 = [frame[j][0] for frame in projected]
        ys2 = [frame[j][1] for frame in projected]
        # Fade the edges that swing round the back.
        ops = [round(0.1 + 0.4 * (frame[i][2] + frame[j][2]) / 2, 2)
               for frame in projected]
        out.append(
            f'<line x1="{r(xs1[0])}" y1="{r(ys1[0])}" x2="{r(xs2[0])}" '
            f'y2="{r(ys2[0])}" opacity="{ops[0]}">'
            + animate("x1", series(xs1), duration)
            + animate("y1", series(ys1), duration)
            + animate("x2", series(xs2), duration)
            + animate("y2", series(ys2), duration)
            + animate("opacity", opacities(ops), duration)
            + "</line>"
        )
    out.append("</g>")

    for index in range(nodes):
        xs = [frame[index][0] for frame in projected]
        ys = [frame[index][1] for frame in projected]
        # Radius and opacity carry the depth cue: near nodes bigger, brighter.
        radii = [1.7 + 3.3 * frame[index][2] for frame in projected]
        ops = [round(0.32 + 0.68 * frame[index][2], 2) for frame in projected]
        fill = colours["alert"] if index in alerts else (
            colours["node"] if index % 3 else colours["node_alt"])

        if index in alerts:
            halo = [value * 4.0 for value in radii]
            out.append(
                f'<circle cx="{r(xs[0])}" cy="{r(ys[0])}" r="{r(halo[0])}" '
                f'fill="url(#glow-{theme})">'
                + animate("cx", series(xs), duration)
                + animate("cy", series(ys), duration)
                + animate("r", series(halo), duration)
                + animate("opacity", "1;.2;1", 2.4)
                + "</circle>"
            )

        out.append(
            f'<circle cx="{r(xs[0])}" cy="{r(ys[0])}" r="{r(radii[0])}" '
            f'fill="{fill}" opacity="{ops[0]}">'
            + animate("cx", series(xs), duration)
            + animate("cy", series(ys), duration)
            + animate("r", series(radii), duration)
            + animate("opacity", opacities(ops), duration)
            + "</circle>"
        )

    out.append("</svg>")
    return "".join(out)


# ---------------------------- the travelling surface -------------------------

def mesh_svg(theme: str, columns: int = 17, rows: int = 9, frames: int = 24,
             width: int = 880, height: int = 220, duration: int = 14) -> str:
    """A wireframe surface with a wave travelling across it, in real 3D."""
    colours = THEMES[theme]
    span_x, span_z, amplitude = 340.0, 130.0, 30.0
    yaw, pitch = math.radians(0), math.radians(31)
    camera = Camera(width, height, distance=1600.0,
                    depth_span=span_z + amplitude)

    def surface(u: int, v: int, phase: float):
        x = (u / (columns - 1) - 0.5) * 2 * span_x
        z = (v / (rows - 1) - 0.5) * 2 * span_z
        y = (amplitude * math.sin(3.1 * x / span_x + phase)
             * math.cos(1.6 * z / span_z + phase * 0.6))
        return rotate_x(rotate_y((x, -y, z), yaw), pitch)

    grid = [
        [[camera.project(surface(u, v, 2 * math.pi * f / frames))
          for u in range(columns)]
         for v in range(rows)]
        for f in range(frames + 1)
    ]
    camera.check(f"mesh-3d-{theme}")

    def polyline(sequences):
        """One polyline whose vertices are animated through every frame."""
        values = ";".join(
            " ".join(f"{r(x)},{r(y)}" for x, y, _ in seq) for seq in sequences
        )
        first = " ".join(f"{r(x)},{r(y)}" for x, y, _ in sequences[0])
        return (f'<polyline points="{first}">'
                + animate("points", values, duration)
                + "</polyline>")

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Animated 3D wireframe surface">',
        "<defs>",
        f'<linearGradient id="mesh-{theme}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{colours["mesh_far"]}"/>'
        f'<stop offset="100%" stop-color="{colours["mesh_near"]}"/>'
        "</linearGradient>",
        "</defs>",
        f'<g fill="none" stroke="url(#mesh-{theme})" stroke-width="1.1" '
        'stroke-linecap="round" opacity=".9">',
    ]
    for v in range(rows):
        out.append(polyline([grid[f][v] for f in range(frames + 1)]))
    for u in range(columns):
        out.append(polyline([[grid[f][v][u] for v in range(rows)]
                             for f in range(frames + 1)]))
    out.append("</g></svg>")
    return "".join(out)


# ------------------------------ the tag sphere -------------------------------

SKILLS = [
    "Python", "C++", "TypeScript", "FastAPI", "Postgres", "Redis", "React",
    "Docker", "PostGIS", "pgvector", "BullMQ", "WebSockets", "OR-Tools",
    "openCypher", "RAG", "Whisper", "Fastify", "Nginx", "Linux", "PyTorch",
]


def sphere_svg(theme: str, frames: int = 30, width: int = 880,
               height: int = 320, duration: int = 30) -> str:
    """The stack as a rotating sphere of words.

    Same rotation maths as the ring, but the marks are <text>: the depth cue
    is font-size and opacity rather than radius, which reads very differently.
    """
    colours = THEMES[theme]
    radius = 118.0
    camera = Camera(width, height, distance=radius * 4.0, depth_span=radius)
    points = fibonacci_sphere(len(SKILLS), radius)

    projected = [
        [camera.project(rotate_x(rotate_y(p, 2 * math.pi * f / frames),
                                 math.radians(-10)))
         for p in points]
        for f in range(frames + 1)
    ]
    # Words are wider than their centre point, so measure the extremes too.
    for frame in projected:
        for (x, y, depth), word in zip(frame, SKILLS):
            half = 0.32 * len(word) * (10 + 9 * depth)
            camera.note(x - half, y)
            camera.note(x + half, y)
    camera.check(f"sphere-3d-{theme}")

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="The stack I work with, on a sphere rotating in 3D">',
        '<g font-family="Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-weight="600" text-anchor="middle" fill="{colours["text"]}">',
    ]
    for index, word in enumerate(SKILLS):
        xs = [frame[index][0] for frame in projected]
        ys = [frame[index][1] for frame in projected]
        sizes = [10 + 9 * frame[index][2] for frame in projected]
        ops = [round(0.28 + 0.72 * frame[index][2], 2) for frame in projected]
        out.append(
            f'<text x="{r(xs[0])}" y="{r(ys[0])}" font-size="{r(sizes[0])}" '
            f'opacity="{ops[0]}">{word}'
            + animate("x", series(xs), duration)
            + animate("y", series(ys), duration)
            + animate("font-size", series(sizes), duration)
            + animate("opacity", opacities(ops), duration)
            + "</text>"
        )
    out.append("</g></svg>")
    return "".join(out)


# --------------------------- the isometric architecture ----------------------

def stack_svg(theme: str, frames: int = 24, width: int = 880,
              height: int = 432, duration: int = 6) -> str:
    """The architecture as isometric slabs, with requests falling through it.

    The camera never moves here -- the 3D comes from the projection and the
    motion from packets travelling between layers. A fixed isometric scene
    also means the draw order is correct once and stays correct.
    """
    colours = THEMES[theme]
    half_x, half_z, thickness = 145.0, 66.0, 13.0
    # Bottom of the stack first. Lifts are centred on the viewBox further
    # down, and drawing in this order puts the top slab nearest the camera.
    layers = [
        ("graph store", 0.0),
        ("detectors", 62.0),
        ("FastAPI", 124.0),
        ("React UI", 186.0),
    ]
    centre = layers[-1][1] / 2
    camera = Camera(width, height, distance=1.0, depth_span=1.0)

    def face(points, lift, fill, opacity=1.0):
        flat = [isometric(p, width, height, lift) for p in points]
        for x, y in flat:
            camera.note(x, y)
        pts = " ".join(f"{r(x)},{r(y)}" for x, y in flat)
        return f'<polygon points="{pts}" fill="{fill}" opacity="{opacity}"/>'

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="An isometric stack of services with requests falling '
        'through it">',
    ]

    top_face = [(-half_x, 0.0, -half_z), (half_x, 0.0, -half_z),
                (half_x, 0.0, half_z), (-half_x, 0.0, half_z)]
    left_face = [(-half_x, 0.0, half_z), (half_x, 0.0, half_z),
                 (half_x, -thickness, half_z), (-half_x, -thickness, half_z)]
    right_face = [(half_x, 0.0, -half_z), (half_x, 0.0, half_z),
                  (half_x, -thickness, half_z), (half_x, -thickness, -half_z)]

    # Lowest layer first: in isometric, later shapes sit visually in front.
    for label, raw_lift in layers:
        lift = raw_lift - centre
        out.append(face(left_face, lift, colours["slab_left"]))
        out.append(face(right_face, lift, colours["slab_right"]))
        out.append(face(top_face, lift, colours["slab_top"], 0.96))
        # Edge the top face so the layers separate on a busy background.
        edge = [isometric(p, width, height, lift) for p in top_face]
        pts = " ".join(f"{r(x)},{r(y)}" for x, y in edge)
        out.append(f'<polygon points="{pts}" fill="none" '
                   f'stroke="{colours["slab_line"]}" stroke-width="1" '
                   'opacity=".55"/>')
        # Slabs this wide overlap by more than their spacing, so a label
        # placed level with its slab reads as belonging to the one above.
        # A leader line to the slab's own left corner removes the ambiguity.
        corner = isometric((-half_x, 0.0, half_z), width, height, lift)
        label_x = corner[0] - 66
        camera.note(label_x - 84, corner[1] + 6)
        out.append(
            f'<line x1="{r(label_x + 8)}" y1="{r(corner[1])}" '
            f'x2="{r(corner[0] - 2)}" y2="{r(corner[1])}" '
            f'stroke="{colours["muted"]}" stroke-width="1" opacity=".6"/>'
            f'<text x="{r(label_x)}" y="{r(corner[1] + 4)}" '
            'font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="13" '
            f'font-weight="600" text-anchor="end" fill="{colours["text"]}" '
            f'opacity=".85">{label}</text>'
        )

    # Packets fall from the top slab to the bottom one, on three lanes.
    lanes = [(-92.0, -32.0), (0.0, 16.0), (88.0, -6.0)]
    top_lift, bottom_lift = layers[-1][1] - centre, layers[0][1] - centre
    for lane, (x, z) in enumerate(lanes):
        xs, ys, ops = [], [], []
        for f in range(frames + 1):
            # Each lane starts a third of a cycle apart.
            phase = (f / frames + lane / len(lanes)) % 1.0
            lift = top_lift + (bottom_lift - top_lift) * phase
            px, py = isometric((x, 0.0, z), width, height, lift)
            camera.note(px, py - 12)
            xs.append(px)
            ys.append(py - 9)
            # Fade at both ends so the loop point is invisible.
            ops.append(round(min(1.0, 3.4 * min(phase, 1 - phase)), 2))
        out.append(
            f'<circle cx="{r(xs[0])}" cy="{r(ys[0])}" r="4.5" '
            f'fill="{colours["route"]}" opacity="{ops[0]}">'
            + animate("cx", series(xs), duration)
            + animate("cy", series(ys), duration)
            + animate("opacity", opacities(ops), duration)
            + "</circle>"
        )

    camera.check(f"stack-3d-{theme}")
    out.append("</svg>")
    return "".join(out)


# ------------------------------ the fleet on a plane -------------------------

ROUTES = [
    [(-320, 118), (-170, 40), (-40, 94), (110, 18), (300, 72)],
    [(-310, -70), (-140, -102), (30, -46), (200, -94), (320, -30)],
    [(-250, 8), (-60, -30), (90, 60), (250, -10)],
]


def resample(path, count):
    """Walk a polyline at constant speed and return `count` points."""
    spans = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    total = sum(spans)
    points = []
    for step in range(count):
        travelled = total * step / count
        for index, span in enumerate(spans):
            if travelled <= span or index == len(spans) - 1:
                ratio = travelled / span if span else 0.0
                ax, az = path[index]
                bx, bz = path[index + 1]
                points.append((ax + (bx - ax) * ratio, az + (bz - az) * ratio))
                break
            travelled -= span
    return points


def fleet_svg(theme: str, frames: int = 36, width: int = 880,
              height: int = 320, duration: int = 16) -> str:
    """A fleet driving routes across a ground plane, seen in perspective.

    The plane recedes, so a van halfway up the picture is genuinely further
    away: it is smaller and dimmer because the projection says so.
    """
    colours = THEMES[theme]
    # Close camera, moderate tilt: the far edge of the plane has to be
    # visibly narrower than the near edge or none of this reads as ground.
    camera = Camera(width, height, distance=500.0, depth_span=150.0)
    pitch = math.radians(60)

    def ground(x, z):
        return camera.project(rotate_x((x, 0.0, z), pitch))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Delivery vehicles driving optimised routes across a 3D '
        'ground plane">',
        f'<g stroke="{colours["ground"]}" stroke-width=".8" opacity=".55" '
        'fill="none">',
    ]
    for x in range(-330, 331, 66):
        a, b = ground(x, -140), ground(x, 140)
        out.append(f'<line x1="{r(a[0])}" y1="{r(a[1])}" x2="{r(b[0])}" '
                   f'y2="{r(b[1])}"/>')
    for z in range(-140, 141, 56):
        a, b = ground(-330, z), ground(330, z)
        out.append(f'<line x1="{r(a[0])}" y1="{r(a[1])}" x2="{r(b[0])}" '
                   f'y2="{r(b[1])}"/>')
    out.append("</g>")

    for index, route in enumerate(ROUTES):
        flat = [ground(x, z) for x, z in route]
        pts = " ".join(f"{r(x)},{r(y)}" for x, y, _ in flat)
        out.append(f'<polyline points="{pts}" fill="none" '
                   f'stroke="{colours["route"]}" stroke-width="2" '
                   'stroke-linecap="round" stroke-linejoin="round" '
                   f'opacity="{round(0.8 - index * 0.14, 2)}"/>')
        for x, y, depth in flat:
            out.append(f'<circle cx="{r(x)}" cy="{r(y)}" '
                       f'r="{r(2 + 1.6 * depth)}" fill="{colours["route"]}" '
                       f'opacity="{round(0.5 + 0.4 * depth, 2)}"/>')

        # One vehicle per route, at constant speed, looping the circuit out
        # and back so it never teleports at the seam.
        circuit = route + route[::-1][1:]
        walk = resample(circuit, frames) + [circuit[0]]
        seats = [ground(x, z) for x, z in walk]
        xs = [seat[0] for seat in seats]
        ys = [seat[1] for seat in seats]
        sizes = [3.2 + 3.4 * seat[2] for seat in seats]
        out.append(
            f'<circle cx="{r(xs[0])}" cy="{r(ys[0])}" r="{r(sizes[0])}" '
            f'fill="{colours["node"]}">'
            + animate("cx", series(xs), duration + index * 3)
            + animate("cy", series(ys), duration + index * 3)
            + animate("r", series(sizes), duration + index * 3)
            + "</circle>"
        )

    # The depot: everything leaves from here, so it gets a pulse.
    depot = ground(-320, 118)
    camera.note(depot[0] - 21, depot[1] - 21)
    camera.note(depot[0] + 21, depot[1] + 21)
    out.append(
        f'<circle cx="{r(depot[0])}" cy="{r(depot[1])}" r="5.5" '
        f'fill="{colours["alert"]}" opacity=".9"/>'
        f'<circle cx="{r(depot[0])}" cy="{r(depot[1])}" r="6" fill="none" '
        f'stroke="{colours["alert"]}" stroke-width="1.5">'
        + animate("r", "6;20", 2.6) + animate("opacity", ".8;0", 2.6)
        + "</circle>"
    )
    camera.check(f"fleet-3d-{theme}")
    out.append("</svg>")
    return "".join(out)


# ------------------------------ the bobbing voxels ---------------------------

def voxel_svg(theme: str, columns: int = 13, rows: int = 6, frames: int = 24,
              width: int = 880, height: int = 400, duration: int = 9) -> str:
    """A field of isometric cubes riding a wave.

    Cheap by construction: each cube is three static polygons in a group, and
    the only animation is one translate per group. That keeps the file small
    enough to sit next to five other animations.
    """
    colours = THEMES[theme]
    size, gap = 24.0, 29.0
    camera = Camera(width, height, distance=1.0, depth_span=1.0)

    def cube(cx, cz):
        """Three faces of a cube standing on the ground plane at (cx, cz)."""
        half = size / 2
        top = [(cx - half, size, cz - half), (cx + half, size, cz - half),
               (cx + half, size, cz + half), (cx - half, size, cz + half)]
        left = [(cx - half, size, cz + half), (cx + half, size, cz + half),
                (cx + half, 0.0, cz + half), (cx - half, 0.0, cz + half)]
        right = [(cx + half, size, cz - half), (cx + half, size, cz + half),
                 (cx + half, 0.0, cz + half), (cx + half, 0.0, cz - half)]
        return top, left, right

    def polygon(points, fill):
        flat = [isometric(p, width, height) for p in points]
        for x, y in flat:
            camera.note(x, y)
        pts = " ".join(f"{r(x)},{r(y)}" for x, y in flat)
        return f'<polygon points="{pts}" fill="{fill}"/>'

    cells = [(column, row) for row in range(rows) for column in range(columns)]
    # Back to front, so the overlaps are right in every frame.
    cells.sort(key=lambda cell: cell[0] + cell[1])

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="A field of isometric cubes bobbing on a wave">',
    ]
    for column, row in cells:
        cx = (column - (columns - 1) / 2) * gap
        cz = (row - (rows - 1) / 2) * gap
        wave = 2.4 * (column / columns) + 1.9 * (row / rows)
        heights = [
            26.0 + 22.0 * math.sin(2 * math.pi * f / frames - wave)
            for f in range(frames + 1)
        ]
        shadow = isometric((cx, 0.0, cz), width, height)
        camera.note(shadow[0], shadow[1] - max(heights) - size)
        out.append(
            f'<ellipse cx="{r(shadow[0])}" cy="{r(shadow[1])}" '
            f'rx="{r(size * 0.78)}" ry="{r(size * 0.4)}" '
            f'fill="{colours["muted"]}" opacity=".14"/>'
        )
        top, left, right = cube(cx, cz)
        out.append(f'<g transform="translate(0,{r(-heights[0])})">')
        out.append(polygon(left, colours["cube_left"]))
        out.append(polygon(right, colours["cube_right"]))
        out.append(polygon(top, colours["cube_top"]))
        out.append(
            '<animateTransform attributeName="transform" type="translate" '
            f'values="{";".join("0," + r(-h) for h in heights)}" '
            f'dur="{duration}s" repeatCount="indefinite"/>'
        )
        out.append("</g>")

    camera.check(f"voxel-3d-{theme}")
    out.append("</svg>")
    return "".join(out)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    builders = (("ring-3d", ring_svg), ("mesh-3d", mesh_svg),
                ("sphere-3d", sphere_svg), ("stack-3d", stack_svg),
                ("fleet-3d", fleet_svg), ("voxel-3d", voxel_svg))
    total = 0
    for theme in THEMES:
        for name, build in builders:
            svg = build(theme)
            path = ASSETS / f"{name}-{theme}.svg"
            path.write_text(svg, encoding="utf-8")
            total += len(svg)
            print(f"{path.name}: {len(svg) / 1024:.1f} KB")
    print(f"total: {total / 1024:.0f} KB")


if __name__ == "__main__":
    main()
