#!/usr/bin/env python3
"""
Génère les rendus pour la présentation mairie du projet Duo Papillon.

1. Plan de masse (SVG -> PNG haute résolution) : la maison sur son terrain,
   avec 3,5 m de bordure façade sur les 4 côtés, cotes, nord, échelle.
2. Vue 3D conceptuelle réaliste : rendu isométrique de la maison finie
   (murs imprimés J1 bleu-gris / J2 ocre, toiture papillon, vitrages,
   menuiseries, terrasse bois, dalle béton, terrain engazonné).
3. Page A3 paysage (PNG 300 dpi + PDF) : plan en haut, vue 3D en bas,
   cartouche mairie.

Données géométriques extraites de "Duo Papillon.html" (DATA.ext, DATA.glass,
DATA.doors). Système de coordonnées : x = est-ouest (m), y = nord-sud (m),
la scène Three.js mappe (x, y_plan) -> (x, -y, z_hauteur).
"""

import json
import math
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
REPO = "/workspace/github__quentinderooC3D__Duo-papillon"
HTML = open(f"{REPO}/Duo Papillon.html", encoding="utf-8").read()

m = re.search(r'const DATA = (\{.*?\});\s*\n', HTML, re.S)
# extraction robuste du JSON DATA
i = HTML.find("const DATA = ")
start = i + len("const DATA = ")
depth = 0
j = start
in_str = False
esc = False
while j < len(HTML):
    c = HTML[j]
    if in_str:
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            in_str = False
    else:
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
    j += 1
DATA = json.loads(HTML[start : j + 1])
M = DATA["metrics"]
EXT = DATA["ext"]
GLASS = DATA["glass"]
DOORS = DATA["doors"]

# ---------------------------------------------------------------------------
# Constantes de présentation
# ---------------------------------------------------------------------------
BORDURE = 3.5          # m de bordure façade demandée (3 à 4 m)
TERRAIN_MARGIN = 6.0   # marge supplémentaire autour de la parcelle affichée
DPI = 300
PX_PER_M = 60          # résolution du plan de masse (px/m)

# Couleurs (alignées sur le rendu 3D du .html)
C = {
    "paper":      (249, 250, 248),
    "ink":        (26, 29, 32),
    "muted":      (89, 97, 106),
    "faint":      (138, 146, 154),
    "line":       (210, 214, 211),
    "slate":      (127, 155, 187),   # J1 logement A
    "slate_dk":   (90, 115, 145),
    "gold":       (210, 178, 90),    # J2 logement B
    "gold_dk":    (160, 130, 55),
    "mas":        (140, 143, 146),   # maçonnerie / refend
    "post":       (28, 31, 35),      # poteaux BA
    "insul":      (230, 210, 154),   # isolation
    "slab":       (217, 214, 207),   # dalle béton
    "roof":       (241, 239, 234),   # toiture
    "glass":      (156, 195, 230),
    "glass_dk":   (80, 120, 160),
    "frame":      (59, 63, 68),      # menuiseries alu
    "door":       (123, 90, 60),     # portes bois
    "deck":       (181, 143, 98),    # terrasse bois
    "furn":       (236, 230, 218),
    "grass":      (163, 191, 138),   # terrain engazonné
    "grass_dk":   (140, 170, 115),
    "gravel":     (200, 198, 190),   # allée
    "white":      (255, 255, 255),
    "black":      (0, 0, 0),
    "parcel_line": (60, 70, 60),
}

# Polices
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def font(size, bold=False, mono=False):
    path = FONT_PATHS[1] if bold else (FONT_PATHS[2] if mono else FONT_PATHS[0])
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Utilitaires géométrie 2D
# ---------------------------------------------------------------------------
def poly_bbox(polys):
    xs, ys = [], []
    for poly in polys:
        for pt in poly["o"]:
            xs.append(pt[0])
            ys.append(pt[1])
    return min(xs), max(xs), min(ys), max(ys)


def get_ext(group):
    out = []
    for e in EXT:
        if e["g"] == group:
            out.append(e)
    return out


def flatten(e):
    """Retourne la liste des polygones {o: [...], h: [...]} d'un élément ext."""
    return e["p"] if isinstance(e["p"], list) else [e["p"]]


def point_in_poly(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_holes(x, y, holes):
    return any(point_in_poly(x, y, h) for h in holes)


# ---------------------------------------------------------------------------
# 1. PLAN DE MASSE
# ---------------------------------------------------------------------------
def make_plan_masse(path_png):
    # Emprise maison (toiture = plus grande emprise)
    roof = get_ext("roof")
    x0, x1, y0, y1 = poly_bbox([p for e in roof for p in flatten(e)])
    # Terrasse au nord (y négatif dans le plan = nord d'après la flèche N)
    deck = get_ext("deck")
    dx0, dx1, dy0, dy1 = poly_bbox([p for e in deck for p in flatten(e)])
    x0 = min(x0, dx0); x1 = max(x1, dx1)
    y0 = min(y0, dy0); y1 = max(y1, dy1)

    # Terrain: maison + bordure de 3,5 m de chaque côté
    tx0 = x0 - BORDURE
    tx1 = x1 + BORDURE
    ty0 = y0 - BORDURE
    ty1 = y1 + BORDURE
    # parcelle un peu plus grande que la zone affichée
    px0, px1 = tx0 - 4.0, tx1 + 4.0
    py0, py1 = ty0 - 4.0, ty1 + 4.0

    w_m = px1 - px0
    h_m = py1 - py0
    W = int(w_m * PX_PER_M)
    H = int(h_m * PX_PER_M)

    img = Image.new("RGB", (W, H), C["paper"])
    dr = ImageDraw.Draw(img)

    def X(x):
        return (x - px0) * PX_PER_M

    def Y(y):
        # y plan croissant vers le nord; en image on inverse pour avoir le nord en haut
        return H - (y - py0) * PX_PER_M

    def draw_poly(pts, fill=None, outline=None, width=1):
        p = [(X(px), Y(py)) for px, py in pts]
        if fill is not None:
            dr.polygon(p, fill=fill)
        if outline is not None:
            dr.line(p + [p[0]], fill=outline, width=width, joint="curve")

    # --- Terrain engazonné (parcelle) ---
    dr.rectangle([X(px0), Y(py1), X(px1), Y(py0)], fill=C["grass"])
    # texture herbe: points aléatoires
    rng = np.random.default_rng(42)
    for _ in range(int(w_m * h_m * 120)):
        gx = rng.uniform(px0, px1)
        gy = rng.uniform(py0, py1)
        r = rng.uniform(0.5, 1.6)
        col = C["grass_dk"] if rng.random() < 0.5 else C["grass"]
        dr.ellipse([X(gx) - r, Y(gy) - r, X(gx) + r, Y(gy) + r], fill=col)

    # --- Limite de parcelle (trait mixte) ---
    pw = max(2, int(0.06 * PX_PER_M))
    dash = int(0.35 * PX_PER_M)
    gap = int(0.18 * PX_PER_M)
    # pointillés sur les 4 côtés
    def dashed_line(xa, ya, xb, yb, col, w):
        L = math.hypot(X(xb) - X(xa), Y(yb) - Y(ya))
        n = int(L // (dash + gap))
        for k in range(n + 1):
            t0 = k * (dash + gap) / L
            t1 = min(1, (k * (dash + gap) + dash) / L)
            dr.line([X(xa) + (X(xb) - X(xa)) * t0, Y(ya) + (Y(yb) - Y(ya)) * t0,
                     X(xa) + (X(xb) - X(xa)) * t1, Y(ya) + (Y(yb) - Y(ya)) * t1],
                    fill=col, width=w)
    dashed_line(px0, py0, px1, py0, C["parcel_line"], pw)
    dashed_line(px1, py0, px1, py1, C["parcel_line"], pw)
    dashed_line(px1, py1, px0, py1, C["parcel_line"], pw)
    dashed_line(px0, py1, px0, py0, C["parcel_line"], pw)

    # --- Allée d'accès (sud, au milieu) ---
    allee_w = 3.0
    allee_x0, allee_x1 = -allee_w / 2, allee_w / 2
    dr.rectangle([X(allee_x0), Y(ty1 + 0.2), X(allee_x1), Y(py0)], fill=C["gravel"])
    # texture gravier
    for _ in range(3000):
        gx = rng.uniform(allee_x0, allee_x1)
        gy = rng.uniform(py0, ty1 + 0.2)
        r = rng.uniform(0.4, 1.2)
        col = tuple(max(0, min(255, c + rng.integers(-15, 15))) for c in C["gravel"])
        dr.ellipse([X(gx) - r, Y(gy) - r, X(gx) + r, Y(gy) + r], fill=col)

    # --- Dalle béton (slab) ---
    for e in get_ext("slab"):
        for poly in flatten(e):
            draw_poly(poly["o"], fill=C["slab"], outline=C["faint"], width=1)

    # --- Terrasse bois (deck) au nord ---
    for e in get_ext("deck"):
        for poly in flatten(e):
            draw_poly(poly["o"], fill=C["deck"], outline=(160, 125, 80), width=1)
            # lames de bois
            xs = [p[0] for p in poly["o"]]
            ys = [p[1] for p in poly["o"]]
            for yy in np.arange(min(ys), max(ys), 0.12):
                dr.line([X(min(xs)), Y(yy), X(max(xs)), Y(yy)], fill=(160, 125, 80), width=1)

    # --- Murs imprimés J1 (A, ouest) et J2 (B, est) ---
    for e in get_ext("print_A"):
        for poly in flatten(e):
            if poly["o"]:
                draw_poly(poly["o"], fill=C["slate"], outline=C["slate_dk"], width=1)
    for e in get_ext("print_B"):
        for poly in flatten(e):
            if poly["o"]:
                draw_poly(poly["o"], fill=C["gold"], outline=C["gold_dk"], width=1)

    # --- Refend / cloison centrale (maçonnerie) ---
    for e in get_ext("party"):
        for poly in flatten(e):
            draw_poly(poly["o"], fill=C["mas"], outline=(100, 103, 106), width=1)
    for e in get_ext("part"):
        for poly in flatten(e):
            draw_poly(poly["o"], fill=(228, 226, 220), outline=C["faint"], width=1)

    # --- Poteaux BA (petits carrés noirs) ---
    for e in get_ext("post"):
        for poly in flatten(e):
            draw_poly(poly["o"], fill=C["post"], outline=None)

    # --- Toiture (contour + faitage papillon) ---
    for e in get_ext("roof"):
        for poly in flatten(e):
            draw_poly(poly["o"], fill=None, outline=C["faint"], width=1)
    # ligne de faitage (vallée centrale x=0)
    dr.line([X(0), Y(y0), X(0), Y(y1)], fill=C["faint"], width=1)

    # --- Pièces (remplissage blanc + noms) ---
    rooms = [
        ("Séjour · cuisine · entrée", 27.9, (-1.9, 4.05), "A"),
        ("Séjour · cuisine · entrée", 27.9, (1.9, 4.05), "B"),
        ("Chambre", 15.8, (-2.75, -4.2), "A"),
        ("Chambre", 15.8, (2.75, -4.2), "B"),
        ("Salle d'eau", 5.1, (-1.3, -0.55), "A"),
        ("Salle d'eau", 5.1, (1.3, -0.55), "B"),
    ]
    # remplissage des pièces en blanc cassé (sous les murs)
    # on remplit les contours de rooms depuis le SVG original
    room_polys = []
    for m2 in re.finditer(r'<path class="room room-(\w+)" data-unit="(\w)"[^>]*d="([^"]+)"', HTML):
        d = m2.group(3)
        pts = [tuple(map(float, t)) for t in re.findall(r'(-?[\d.]+) (-?[\d.]+)', d)]
        room_polys.append((m2.group(1), m2.group(2), pts))
    for key, unit, pts in room_polys:
        draw_poly(pts, fill=C["white"], outline=C["line"], width=1)

    # --- Porches (hachures) ---
    for m2 in re.finditer(r'<path class="porch"[^>]*d="([^"]+)"', HTML):
        d = m2.group(1)
        pts = [tuple(map(float, t)) for t in re.findall(r'(-?[\d.]+) (-?[\d.]+)', d)]
        draw_poly(pts, fill=(233, 226, 208), outline=(203, 190, 156), width=1)

    # --- Menuiseries (vitrages en bleu, portes en bois) ---
    for g in GLASS:
        a, b = g["a"], g["b"]
        dr.line([X(a[0]), Y(a[1]), X(b[0]), Y(b[1])], fill=C["glass_dk"], width=max(2, int(0.08 * PX_PER_M)))
    for g in DOORS:
        a, b = g["a"], g["b"]
        dr.line([X(a[0]), Y(a[1]), X(b[0]), Y(b[1])], fill=C["door"], width=max(3, int(0.12 * PX_PER_M)))

    # --- Noms des pièces ---
    f_room = font(int(0.30 * PX_PER_M), bold=True)
    f_area = font(int(0.26 * PX_PER_M), mono=True)
    for name, area, (rx, ry), unit in rooms:
        dr.text((X(rx), Y(ry)), name, font=f_room, fill=C["ink"], anchor="mm")
        dr.text((X(rx), Y(ry) + int(0.34 * PX_PER_M)), f"{area:.1f} m²".replace(".", ","),
                font=f_area, fill=C["muted"], anchor="mm")

    # --- Cotes ---
    f_dim = font(int(0.24 * PX_PER_M), mono=True)
    # cote largeur (haut)
    cy = Y(ty1) - int(0.5 * PX_PER_M)
    dr.line([X(x0), cy, X(x1), cy], fill=C["muted"], width=2)
    dr.line([X(x0), cy - 6, X(x0), cy + 6], fill=C["muted"], width=2)
    dr.line([X(x1), cy - 6, X(x1), cy + 6], fill=C["muted"], width=2)
    dr.text(((X(x0) + X(x1)) / 2, cy - int(0.12 * PX_PER_M)), f"{x1-x0:.2f} m".replace(".", ","),
            font=f_dim, fill=C["muted"], anchor="mm")
    # cote profondeur (droite)
    cx = X(tx1) + int(0.6 * PX_PER_M)
    dr.line([cx, Y(y0), cx, Y(y1)], fill=C["muted"], width=2)
    dr.line([cx - 6, Y(y0), cx + 6, Y(y0)], fill=C["muted"], width=2)
    dr.line([cx - 6, Y(y1), cx + 6, Y(y1)], fill=C["muted"], width=2)
    # texte vertical
    txt = Image.new("RGBA", (int(1.2 * PX_PER_M), int(0.4 * PX_PER_M)), (0, 0, 0, 0))
    td = ImageDraw.Draw(txt)
    td.text((txt.width // 2, txt.height // 2), f"{y1-y0:.2f} m".replace(".", ","),
            font=f_dim, fill=C["muted"], anchor="mm")
    txt = txt.rotate(90, expand=True)
    img.paste(txt, (int(cx + 0.15 * PX_PER_M), int((Y(y0) + Y(y1)) / 2 - txt.height / 2)), txt)

    # --- Bordures 3,5 m (cotes de retrait) ---
    f_bord = font(int(0.20 * PX_PER_M), mono=True)
    # côté ouest
    dr.line([X(tx0), Y(y0), X(x0), Y(y0)], fill=(46, 139, 87), width=2)
    dr.text(((X(tx0) + X(x0)) / 2, Y(y0) - int(0.15 * PX_PER_M)), "3,50",
            font=f_bord, fill=(46, 139, 87), anchor="mm")
    # côté nord
    dr.line([X(x1), Y(ty0), X(x1), Y(y0)], fill=(46, 139, 87), width=2)
    dr.text((X(x1) + int(0.2 * PX_PER_M), (Y(ty0) + Y(y0)) / 2), "3,50",
            font=f_bord, fill=(46, 139, 87), anchor="mm")

    # --- Flèche nord ---
    nx, ny = X(px1) - int(0.8 * PX_PER_M), Y(py1) + int(1.4 * PX_PER_M)
    dr.polygon([(nx, ny - 30), (nx - 10, ny), (nx, ny - 8), (nx + 10, ny)], fill=C["ink"])
    dr.text((nx, ny + 22), "N", font=font(int(0.3 * PX_PER_M), bold=True), fill=C["ink"], anchor="mm")

    # --- Échelle graphique ---
    sx, sy = X(px0) + int(0.5 * PX_PER_M), Y(py0) - int(1.2 * PX_PER_M)
    seg = int(1 * PX_PER_M)
    for k in range(5):
        col = C["ink"] if k % 2 == 0 else C["white"]
        dr.rectangle([sx + k * seg, sy, sx + (k + 1) * seg, sy + int(0.12 * PX_PER_M)],
                     fill=col, outline=C["ink"])
    for k in range(6):
        dr.text((sx + k * seg, sy + int(0.28 * PX_PER_M)), str(k), font=f_bord,
                fill=C["muted"], anchor="mm")
    dr.text((sx + 5 * seg + int(0.25 * PX_PER_M), sy + int(0.06 * PX_PER_M)), "m",
            font=f_bord, fill=C["muted"], anchor="lm")

    # --- Labels logements ---
    f_unit = font(int(0.28 * PX_PER_M), bold=True)
    dr.text((X(-3.9), Y(ty1) + int(0.35 * PX_PER_M)), "LOGEMENT A", font=f_unit,
            fill=C["slate_dk"], anchor="mm")
    dr.text((X(3.9), Y(ty1) + int(0.35 * PX_PER_M)), "LOGEMENT B", font=f_unit,
            fill=C["gold_dk"], anchor="mm")

    # --- Titre ---
    f_title = font(int(0.5 * PX_PER_M), bold=True)
    dr.text((W / 2, int(1.0 * PX_PER_M)), "PLAN DE MASSE", font=f_title,
            fill=C["ink"], anchor="mm")
    f_sub = font(int(0.3 * PX_PER_M))
    dr.text((W / 2, int(1.0 * PX_PER_M) + int(0.55 * PX_PER_M)),
            "Duo Papillon · 2 logements · emprise 11,83 m × 10,71 m · retrait façade 3,50 m",
            font=f_sub, fill=C["muted"], anchor="mm")

    img.save(path_png, dpi=(DPI, DPI))
    return img, (px0, px1, py0, py1)


# ---------------------------------------------------------------------------
# 2. VUE 3D CONCEPTUELLE RÉALISTE (rendu logiciel isométrique)
# ---------------------------------------------------------------------------
# Projection isométrique simple: screen = (x - y*cos30, z + (x+y*sin30)*...)
# On fait un vrai rendu 3D "peintre" avec faces triées par profondeur.

class Face:
    __slots__ = ("pts3", "color", "outline", "order")

    def __init__(self, pts3, color, outline=None):
        self.pts3 = pts3
        self.color = color
        self.outline = outline
        self.order = sum(p[2] for p in pts3) / len(pts3)  # profondeur moyenne


def project(p, cam):
    """p = (x, y, z) monde (y = hauteur). Retourne (sx, sy, depth)."""
    x, y, z = p
    # caméra en position élevée, direction sud-ouest -> nord-est
    # On projette en orthographique isométrique avec élévation
    sx = (x - z) * cam["cos30"]
    sy = (x + z) * cam["sin30"] * 0.5 - y
    depth = x + z + y * 0.001
    return sx, sy, depth


def build_faces():
    """Construit la liste des faces 3D de la maison finie."""
    faces = []

    def add_prism(polys, z0, z1, top_col, side_col, side_col_dk=None, roof_slope=False):
        """Extrude des polygones 2D (x, y_plan) entre z0 et z1.
        y_plan -> -z monde. On travaille en (x, y_plan, z_haut)."""
        for poly in polys:
            o = poly["o"]
            holes = poly.get("h", [])
            # face dessus (toiture si pente papillon)
            top_pts = []
            for (px, py) in o:
                h = z1
                if roof_slope:
                    h = z1 + M["roof_k"] * abs(px)
                top_pts.append((px, -py, h))
            faces.append(Face(top_pts, top_col))
            # face dessous (rarement visible)
            bot_pts = [(px, -py, z0) for (px, py) in o]
            faces.append(Face(bot_pts, shade(top_col, 0.7)))
            # faces latérales (murs)
            n = len(o)
            for i in range(n):
                ax, ay = o[i]
                bx, by = o[(i + 1) % n]
                # normale horizontale
                nx, ny = -(by - ay), (bx - ax)
                nl = math.hypot(nx, ny) or 1
                nx, ny = nx / nl, ny / nl
                # éclairage: faces orientées vers la lumière (sud-ouest, vecteur (-1,-1))
                light = -(nx + ny) / math.sqrt(2)
                col = blend(side_col, (255, 250, 235), max(0, light) * 0.35)
                quad = [(ax, -ay, z0), (bx, -by, z0), (bx, -by, z1), (ax, -ay, z1)]
                faces.append(Face(quad, col, side_col_dk))

    def shade(col, k):
        return tuple(min(255, int(c * k)) for c in col)

    def blend(c1, c2, t):
        return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))

    # --- Dalle béton ---
    for e in get_ext("slab"):
        add_prism(flatten(e), e["z0"], e["z1"], C["slab"], shade(C["slab"], 0.85))

    # --- Terrasse bois ---
    for e in get_ext("deck"):
        add_prism(flatten(e), e["z0"], e["z1"], C["deck"], shade(C["deck"], 0.8))

    # --- Murs imprimés J1 (A) et J2 (B) ---
    for e in get_ext("print_A"):
        add_prism(flatten(e), e["z0"], e["z1"], C["slate"], C["slate"], C["slate_dk"])
    for e in get_ext("print_B"):
        add_prism(flatten(e), e["z0"], e["z1"], C["gold"], C["gold"], C["gold_dk"])

    # --- Isolation (extérieur, jaune pâle) ---
    for e in get_ext("insul"):
        add_prism(flatten(e), e["z0"], e["z1"], C["insul"], C["insul"], (200, 180, 120))

    # --- Refend central + cloisons ---
    for e in get_ext("party"):
        add_prism(flatten(e), e["z0"], e["z1"], C["mas"], C["mas"], (100, 103, 106))
    for e in get_ext("part"):
        add_prism(flatten(e), e["z0"], e["z1"], (228, 226, 220), (228, 226, 220), C["faint"])

    # --- Poteaux BA ---
    for e in get_ext("post"):
        add_prism(flatten(e), e["z0"], e["z1"], C["post"], C["post"])

    # --- Appuis de fenêtre (sill) ---
    for e in get_ext("sill"):
        add_prism(flatten(e), e["z0"], e["z1"], (207, 203, 194), (207, 203, 194))

    # --- Toiture papillon (pente selon |x|) ---
    for e in get_ext("roof"):
        add_prism(flatten(e), e["z0"], e["z1"], C["roof"], C["roof"], C["faint"], roof_slope=True)

    # --- Menuiseries : vitrages + châssis + portes ---
    def add_panel(a, b, z0, z1, col, frame_col, thickness=0.06):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        # normale dans le plan (perpendiculaire)
        nx, ny = -uy, ux
        # épaisseur horizontale
        ox, oy = nx * thickness / 2, ny * thickness / 2
        p1 = (ax + ox, -(ay + oy), z0)
        p2 = (bx + ox, -(by + oy), z0)
        p3 = (bx + ox, -(by + oy), z1)
        p4 = (ax + ox, -(ay + oy), z1)
        p5 = (ax - ox, -(ay - oy), z0)
        p6 = (bx - ox, -(by - oy), z0)
        p7 = (bx - ox, -(by - oy), z1)
        p8 = (ax - ox, -(ay - oy), z1)
        light = -(nx + ny) / math.sqrt(2)
        faces.append(Face([p1, p2, p3, p4], blend(col, (255, 255, 255), max(0, light) * 0.3)))
        faces.append(Face([p5, p6, p7, p8], blend(col, (255, 255, 255), max(0, -light) * 0.2)))
        # châssis (frame) : 4 barres
        fw = 0.05
        for (qa, qb) in [(a, b)]:
            # haut et bas
            for zz in (z0, z1 - fw):
                c1 = (qa[0], -qa[1], zz)
                c2 = (qb[0], -qb[1], zz)
                c3 = (qb[0], -qb[1], zz + fw)
                c4 = (qa[0], -qa[1], zz + fw)
                faces.append(Face([c1, c2, c3, c4], frame_col))

    for g in GLASS:
        add_panel(g["a"], g["b"], g["z0"], g["z1"], C["glass"], C["frame"], 0.08)
    for g in DOORS:
        add_panel(g["a"], g["b"], g["z0"], g["z1"], C["door"], C["frame"], 0.12)

    return faces


def make_view3d(path_png, width=2400, height=1500):
    faces = build_faces()

    cam = {"cos30": math.cos(math.radians(30)), "sin30": math.sin(math.radians(30))}

    # Calcul des coordonnées projetées pour le cadrage
    all_pts = []
    for f in faces:
        for p in f.pts3:
            sx, sy, d = project(p, cam)
            all_pts.append((sx, sy))
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    # Marge + décalage pour centrer
    margin = 0.08
    span_x = maxx - minx
    span_y = maxy - miny
    scale = min(width / (span_x * (1 + 2 * margin)), height / (span_y * (1 + 2 * margin)))
    offx = width / 2 - (minx + maxx) / 2 * scale
    offy = height / 2 - (miny + maxy) / 2 * scale

    def to_screen(p):
        sx, sy, d = project(p, cam)
        return (sx * scale + offx, sy * scale + offy, d)

    # Fond dégradé ciel
    img = Image.new("RGB", (width, height), (227, 231, 228))
    dr = ImageDraw.Draw(img)
    for yy in range(height):
        t = yy / height
        col = blend3((227, 231, 228), (200, 210, 205), t * 0.5)
        dr.line([(0, yy), (width, yy)], fill=col)

    # Sol (terrain) : grand polygone sous la maison
    sol_pts = [(-14, 14, -0.30), (14, 14, -0.30), (14, -14, -0.30), (-14, -14, -0.30)]
    sp = [to_screen(p)[:2] for p in sol_pts]
    dr.polygon(sp, fill=C["grass"])
    # ombre portée de la maison (ellipse décalée sud-est)
    shadow = [to_screen(p)[:2] for p in [(-8, 8, -0.26), (8, 8, -0.26), (10, -6, -0.26), (-6, -10, -0.26)]]
    dr.polygon(shadow, fill=(120, 140, 100))

    # Trier les faces du plus loin au plus proche (depth = x+z, caméra au sud-ouest)
    # Caméra regarde depuis (-x, -z) vers (+x, +z) et du haut.
    # Profondeur: plus (x + z) est grand, plus c'est proche... ajustons:
    # Avec notre projection, la caméra est en haut à gauche (x négatif, z négatif).
    # On veut dessiner d'abord les faces les plus éloignées.
    def depth_key(f):
        return -sum(p[0] + p[2] for p in f.pts3) / len(f.pts3)

    faces.sort(key=depth_key)

    for f in faces:
        pts = [to_screen(p)[:2] for p in f.pts3]
        dr.polygon(pts, fill=f.color, outline=f.outline or f.color)
        if f.outline:
            dr.line(pts + [pts[0]], fill=f.outline, width=1, joint="curve")

    # Légère ombre sur les faces mal orientées déjà gérée via éclairage

    # Titre
    f_title = font(int(height * 0.035), bold=True)
    dr.text((width / 2, int(height * 0.04)), "VUE 3D CONCEPTUELLE · MAISON FINIE",
            font=f_title, fill=C["ink"], anchor="mm")
    f_sub = font(int(height * 0.022))
    dr.text((width / 2, int(height * 0.04) + int(height * 0.045)),
            "Duo Papillon · logements A (J1, bleu-gris) & B (J2, ocre) · toiture papillon · terrasse nord",
            font=f_sub, fill=C["muted"], anchor="mm")

    img.save(path_png, dpi=(DPI, DPI))
    return img


def blend3(c1, c2, t):
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


# ---------------------------------------------------------------------------
# 3. PAGE A3 PAYSAGE
# ---------------------------------------------------------------------------
def make_a3(plan_img, view_img, path_png, path_pdf=None):
    # A3 paysage = 420 x 297 mm -> à 300 dpi: 4961 x 3508 px
    W, H = 4961, 3508
    page = Image.new("RGB", (W, H), C["white"])
    dr = ImageDraw.Draw(page)

    # Marges
    m = 120
    header_h = 260
    footer_h = 180

    # --- Cartouche titre ---
    f_title = font(110, bold=True)
    f_sub = font(56)
    dr.text((m, 90), "PROJET DUO PAPILLON", font=f_title, fill=C["ink"], anchor="lm")
    dr.text((m, 175), "Présentation mairie · Implantation sur parcelle · Maisons jumelées en impression 3D béton",
            font=f_sub, fill=C["muted"], anchor="lm")
    # ligne de séparation
    dr.line([(m, header_h - 30), (W - m, header_h - 30)], fill=C["line"], width=3)

    # --- Zone de contenu ---
    content_top = header_h
    content_bot = H - footer_h
    content_h = content_bot - content_top
    # Deux colonnes: plan à gauche (55%), vue 3D à droite (45%)
    gap = 60
    plan_w = int((W - 2 * m - gap) * 0.52)
    view_w = W - 2 * m - gap - plan_w

    # Redimensionner le plan (conserver ratio)
    pr = plan_img.width / plan_img.height
    ph = content_h - 40
    pw = int(ph * pr)
    if pw > plan_w:
        pw = plan_w
        ph = int(pw / pr)
    plan_r = plan_img.resize((pw, ph), Image.LANCZOS)
    page.paste(plan_r, (m, content_top + (content_h - ph) // 2))
    # cadre plan
    dr.rectangle([m - 8, content_top + (content_h - ph) // 2 - 8,
                  m + pw + 8, content_top + (content_h - ph) // 2 + ph + 8],
                 outline=C["line"], width=3)

    # Redimensionner la vue 3D
    vr = view_img.width / view_img.height
    vh = content_h - 40
    vw = int(vh * vr)
    if vw > view_w:
        vw = view_w
        vh = int(vw / vr)
    view_r = view_img.resize((vw, vh), Image.LANCZOS)
    vx = m + plan_w + gap
    page.paste(view_r, (vx, content_top + (content_h - vh) // 2))
    dr.rectangle([vx - 8, content_top + (content_h - vh) // 2 - 8,
                  vx + vw + 8, content_top + (content_h - vh) // 2 + vh + 8],
                 outline=C["line"], width=3)

    # --- Pied de page / cartouche ---
    dr.line([(m, content_bot), (W - m, content_bot)], fill=C["line"], width=3)
    f_foot = font(44)
    f_foot_b = font(44, bold=True)
    yf = content_bot + 40
    dr.text((m, yf), "Duo Papillon", font=f_foot_b, fill=C["ink"], anchor="lm")
    dr.text((m, yf + 60), "2 logements · SHAB 2 × 48,8 m² · Emprise 11,83 m × 10,71 m · Retrait façade 3,50 m",
            font=f_foot, fill=C["muted"], anchor="lm")
    dr.text((m, yf + 115), "Impression 3D béton · Toiture papillon · Terrasse bois · Vitrages aluminium",
            font=f_foot, fill=C["muted"], anchor="lm")
    # échelle / date à droite
    dr.text((W - m, yf + 60), "Échelle plan : graphique", font=f_foot, fill=C["muted"], anchor="rm")
    dr.text((W - m, yf + 115), "Format A3 paysage · 300 dpi", font=f_foot, fill=C["muted"], anchor="rm")

    page.save(path_png, dpi=(DPI, DPI))

    if path_pdf:
        page.save(path_pdf, "PDF", resolution=DPI, save_all=False)
    return page


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    outdir = f"{REPO}/rendu-mairie"
    print("Génération du plan de masse...")
    plan_img, terrain = make_plan_masse(f"{outdir}/plan-de-masse.png")
    print(f"  -> {outdir}/plan-de-masse.png  ({plan_img.width}x{plan_img.height})")

    print("Génération de la vue 3D conceptuelle...")
    view_img = make_view3d(f"{outdir}/vue-3d-conceptuelle.png")
    print(f"  -> {outdir}/vue-3d-conceptuelle.png  ({view_img.width}x{view_img.height})")

    print("Composition de la page A3...")
    a3 = make_a3(plan_img, view_img,
                 f"{outdir}/page-A3-mairie.png",
                 f"{outdir}/page-A3-mairie.pdf")
    print(f"  -> {outdir}/page-A3-mairie.png / .pdf  ({a3.width}x{a3.height})")
    print("Terminé.")
