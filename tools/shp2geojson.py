"""Reads a polygon shapefile (+ .dbf) with the standard library only and writes one GeoJSON per
record, plus an index. Usage: shp2geojson.py <path/without/extension> <out-dir> [--summary]"""
import json
import os
import struct
import sys


def read_dbf(path):
    with open(path, "rb") as f:
        data = f.read()
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0")[0].decode("ascii")
        ftype = chr(data[pos + 11])
        length = data[pos + 16]
        fields.append((name, ftype, length))
        pos += 32
    records = []
    for i in range(count):
        rec = data[header_len + i * record_len: header_len + (i + 1) * record_len]
        if rec[0:1] == b"*":
            records.append(None)
            continue
        offset = 1
        row = {}
        for name, ftype, length in fields:
            raw = rec[offset:offset + length].decode("utf-8", "replace").strip()
            offset += length
            if ftype in "NF" and raw:
                row[name] = float(raw) if "." in raw else int(raw)
            else:
                row[name] = raw
        records.append(row)
    return records


def signed_area(ring):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:])) / 2


def point_in_ring(pt, ring):
    x, y = pt
    inside = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def read_shapes(path):
    with open(path, "rb") as f:
        data = f.read()
    pos = 100
    shapes = []
    while pos < len(data):
        _, length = struct.unpack(">II", data[pos:pos + 8])
        content = data[pos + 8: pos + 8 + length * 2]
        pos += 8 + length * 2
        shape_type = struct.unpack("<i", content[0:4])[0]
        if shape_type == 0:
            shapes.append(None)
            continue
        if shape_type not in (5, 15, 25):
            raise ValueError(f"unsupported shape type {shape_type}")
        num_parts, num_points = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{num_parts}i", content[44:44 + 4 * num_parts]))
        pts_off = 44 + 4 * num_parts
        coords = struct.unpack(f"<{2 * num_points}d", content[pts_off:pts_off + 16 * num_points])
        points = [(coords[2 * i], coords[2 * i + 1]) for i in range(num_points)]
        rings = [points[s:e] for s, e in zip(parts, parts[1:] + [num_points])]
        shapes.append(rings)
    return shapes


def to_geometry(rings, digits):
    # Shapefile: outer rings clockwise, holes counter-clockwise. GeoJSON (RFC 7946): the reverse.
    rnd = lambda ring: [[round(x, digits), round(y, digits)] for x, y in ring]
    outers, holes = [], []
    for ring in rings:
        (outers if signed_area(ring) < 0 else holes).append(ring)
    polygons = [[rnd(list(reversed(o)))] for o in outers]
    for hole in holes:
        for poly, outer in zip(polygons, outers):
            if point_in_ring(hole[0], outer):
                poly.append(rnd(hole))
                break
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def bbox(geometry):
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    xs = [x for p in polys for r in p for x, _ in r]
    ys = [y for p in polys for r in p for _, y in r]
    if max(xs) - min(xs) > 180:
        # Across the antimeridian (Alaska's Aleutians): west > east, as the collections API expects.
        shifted = [x + 360 if x < 0 else x for x in xs]
        return [min(shifted), min(ys), round(max(shifted) - 360, 5), max(ys)]
    return [min(xs), min(ys), max(xs), max(ys)]


def main():
    base, out = sys.argv[1], sys.argv[2]
    summary = "--summary" in sys.argv
    records = read_dbf(base + ".dbf")
    shapes = read_shapes(base + ".shp")
    assert len(records) == len(shapes), (len(records), len(shapes))
    if summary:
        print(len(records), "records; fields:", list(records[0].keys()))
        for r in records[:5]:
            print(r)
        states = {}
        for r in records:
            states[r["id"][:2]] = states.get(r["id"][:2], 0) + 1
        print(len(states), "states/areas:", dict(sorted(states.items())))
        return
    os.makedirs(out, exist_ok=True)
    index = []
    for r, rings in zip(records, shapes):
        geometry = to_geometry(rings, 5)
        feature = {"type": "Feature", "properties": r, "bbox": bbox(geometry), "geometry": geometry}
        name = f"{r['id']}.geojson"
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": [feature]}, f, separators=(",", ":"))
        index.append({**r, "file": name, "bbox": feature["bbox"]})
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)
    print(len(index), "files written to", out)


main()
