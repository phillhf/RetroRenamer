"""Erzeugt installer/app.ico (Spielmodul mit Lupe) ohne externe Bibliotheken.

Ausfuehren:  python installer/make_icon.py
Die Formen werden als Abstandsfunktionen beschrieben und mit 4x4-Supersampling gerastert,
dadurch sind die Kanten in jeder Groesse glatt.
"""
import math
import os
import struct
import zlib

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def rrect(cx, cy, hw, hh, r):
    def d(x, y):
        qx, qy = abs(x - cx) - hw + r, abs(y - cy) - hh + r
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    return d


def ring(cx, cy, radius, width):
    return lambda x, y: abs(math.hypot(x - cx, y - cy) - radius) - width / 2


def disc(cx, cy, radius):
    return lambda x, y: math.hypot(x - cx, y - cy) - radius


def segment(ax, ay, bx, by, width):
    def d(x, y):
        px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay
        t = max(0.0, min(1.0, (px * vx + py * vy) / (vx * vx + vy * vy)))
        return math.hypot(px - vx * t, py - vy * t) - width / 2
    return d


def grow(f, amount):
    return lambda x, y: f(x, y) - amount


OUTLINE = hexcol("#1e2433")
# Ebenen von hinten nach vorne: (Form, Farbe)
body = rrect(0.43, 0.50, 0.31, 0.42, 0.06)
label = rrect(0.43, 0.52, 0.22, 0.20, 0.035)
lens = (0.69, 0.70)
LAYERS = [
    (grow(body, 0.025), OUTLINE),
    (body, hexcol("#9aa3b2")),
    (rrect(0.43, 0.12, 0.31, 0.04, 0.02), hexcol("#b9c0cc")),                     # obere Kante hell
    *[(rrect(0.25 + i * 0.09, 0.19, 0.025, 0.035, 0.01), hexcol("#6b7486")) for i in range(5)],  # Rillen
    (grow(label, 0.018), OUTLINE),
    (label, hexcol("#2f6fe4")),
    (rrect(0.43, 0.42, 0.15, 0.03, 0.015), hexcol("#ffffff", 0.95)),              # "Titelzeilen"
    (rrect(0.38, 0.51, 0.10, 0.025, 0.012), hexcol("#ffffff", 0.75)),
    (segment(0.80, 0.81, 0.93, 0.94, 0.11), OUTLINE),                              # Lupengriff
    (segment(0.81, 0.82, 0.92, 0.93, 0.065), hexcol("#4b5563")),
    (disc(*lens, 0.20), OUTLINE),
    (disc(*lens, 0.16), hexcol("#dbeafe", 0.55)),                                 # Glas
    (ring(*lens, 0.165, 0.055), hexcol("#f59e0b")),                               # Lupenring
    (ring(*lens, 0.165, 0.015), hexcol("#fbbf24")),
]


def render(size):
    ss = 4
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) / size
                    y = (py + (sy + 0.5) / ss) / size
                    r = g = b = a = 0.0
                    for shape, (cr, cg, cb, ca) in LAYERS:
                        if shape(x, y) <= 0:
                            # "source over" mit vormultipliziertem Alpha
                            r, g, b, a = cr * ca + r * (1 - ca), cg * ca + g * (1 - ca), cb * ca + b * (1 - ca), ca + a * (1 - ca)
                    acc[0] += r; acc[1] += g; acc[2] += b; acc[3] += a
            n = ss * ss
            a = acc[3] / n
            if a > 0:
                row += bytes((round(acc[0] / n / a * 255), round(acc[1] / n / a * 255),
                              round(acc[2] / n / a * 255), round(a * 255)))
            else:
                row += b"\0\0\0\0"
        rows.append(bytes(row))
    return rows


def png(size, rows):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + r for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    images = [(s, png(s, render(s))) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for s, img in images:
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(img), offset + len(data))
        data += img
    with open(OUT, "wb") as f:
        f.write(header + entries + data)
    # Vorschau fuer die Doku
    with open(os.path.join(os.path.dirname(OUT), "app_256.png"), "wb") as f:
        f.write(images[-1][1])
    print(f"{OUT} geschrieben ({len(images)} Groessen)")


if __name__ == "__main__":
    main()
