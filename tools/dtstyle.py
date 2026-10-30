#!/usr/bin/env python3
"""Encode/decode darktable .dtstyle files.

Module parameter layouts are pinned to darktable 5.6.2 (src/iop/*.c,
DT_MODULE_INTROSPECTION). Fields are 4 bytes (float, int, enum or gboolean)
or fixed char arrays, little-endian, no padding. If darktable bumps a module
version, update its entry here and run tools/verify.py.

CLI:  python3 tools/dtstyle.py show <file.dtstyle>   # readable dump of any style
"""
import base64
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from xml.sax.saxutils import escape

DARKTABLE_VERSION = "5.6.2"
GRAIN_SCALE_FACTOR = 213.2  # src/iop/grain.c

# op -> (module version, [(field, count, type, default)]); type: f=float, i=int/enum/gboolean,
# s=char[count] string
MODULES = {
    "colorbalancergb": (5, [
        ("shadows_Y", 1, "f", 0.0), ("shadows_C", 1, "f", 0.0), ("shadows_H", 1, "f", 0.0),
        ("midtones_Y", 1, "f", 0.0), ("midtones_C", 1, "f", 0.0), ("midtones_H", 1, "f", 0.0),
        ("highlights_Y", 1, "f", 0.0), ("highlights_C", 1, "f", 0.0), ("highlights_H", 1, "f", 0.0),
        ("global_Y", 1, "f", 0.0), ("global_C", 1, "f", 0.0), ("global_H", 1, "f", 0.0),
        ("shadows_weight", 1, "f", 1.0), ("white_fulcrum", 1, "f", 0.0),
        ("highlights_weight", 1, "f", 1.0),
        ("chroma_shadows", 1, "f", 0.0), ("chroma_highlights", 1, "f", 0.0),
        ("chroma_global", 1, "f", 0.0), ("chroma_midtones", 1, "f", 0.0),
        ("saturation_global", 1, "f", 0.0), ("saturation_highlights", 1, "f", 0.0),
        ("saturation_midtones", 1, "f", 0.0), ("saturation_shadows", 1, "f", 0.0),
        ("hue_angle", 1, "f", 0.0),
        ("brilliance_global", 1, "f", 0.0), ("brilliance_highlights", 1, "f", 0.0),
        ("brilliance_midtones", 1, "f", 0.0), ("brilliance_shadows", 1, "f", 0.0),
        ("mask_grey_fulcrum", 1, "f", 0.1845),
        ("vibrance", 1, "f", 0.0), ("grey_fulcrum", 1, "f", 0.1845), ("contrast", 1, "f", 0.0),
        ("saturation_formula", 1, "i", 1),  # 0=JzAzBz, 1=darktable UCS
    ]),
    "primaries": (1, [  # hues in radians, rotation relative to each working-space primary
        ("achromatic_tint_hue", 1, "f", 0.0), ("achromatic_tint_purity", 1, "f", 0.0),
        ("red_hue", 1, "f", 0.0), ("red_purity", 1, "f", 1.0),
        ("green_hue", 1, "f", 0.0), ("green_purity", 1, "f", 1.0),
        ("blue_hue", 1, "f", 0.0), ("blue_purity", 1, "f", 1.0),
    ]),
    "channelmixerrgb": (3, [  # color calibration
        ("red", 4, "f", [1.0, 0.0, 0.0, 0.0]), ("green", 4, "f", [0.0, 1.0, 0.0, 0.0]),
        ("blue", 4, "f", [0.0, 0.0, 1.0, 0.0]), ("saturation", 4, "f", [0.0] * 4),
        ("lightness", 4, "f", [0.0] * 4), ("grey", 4, "f", [0.0] * 4),
        ("normalize_R", 1, "i", 0), ("normalize_G", 1, "i", 0), ("normalize_B", 1, "i", 0),
        ("normalize_sat", 1, "i", 0), ("normalize_light", 1, "i", 0), ("normalize_grey", 1, "i", 1),
        ("illuminant", 1, "i", 2), ("illum_fluo", 1, "i", 2), ("illum_led", 1, "i", 4),
        ("adaptation", 1, "i", 1),  # 1=CAT16, 3=XYZ (bypass with illuminant 0), 4=none
        ("x", 1, "f", 0.333), ("y", 1, "f", 0.333), ("temperature", 1, "f", 5003.0),
        ("gamut", 1, "f", 1.0), ("clip", 1, "i", 1), ("version", 1, "i", 2),
    ]),
    "bilat": (3, [  # local contrast
        ("mode", 1, "i", 1),  # 1=local laplacian
        ("sigma_r", 1, "f", 0.5), ("sigma_s", 1, "f", 0.5),  # highlights, shadows
        ("detail", 1, "f", 0.25), ("midtone", 1, "f", 0.5),
    ]),
    "grain": (2, [
        ("channel", 1, "i", 2),  # 2=lightness
        ("scale", 1, "f", 1600.0 / GRAIN_SCALE_FACTOR),  # GUI coarseness / 213.2
        ("strength", 1, "f", 25.0), ("midtones_bias", 1, "f", 100.0),
    ]),
    "vignette": (4, [
        ("scale", 1, "f", 80.0), ("falloff_scale", 1, "f", 50.0),
        ("brightness", 1, "f", -0.5), ("saturation", 1, "f", -0.5),
        ("center_x", 1, "f", 0.0), ("center_y", 1, "f", 0.0),
        ("autoratio", 1, "i", 0), ("whratio", 1, "f", 1.0), ("shape", 1, "f", 1.0),
        ("dithering", 1, "i", 0), ("unbound", 1, "i", 1),
    ]),
    "soften": (1, [
        ("size", 1, "f", 50.0), ("saturation", 1, "f", 100.0),
        ("brightness", 1, "f", 0.33), ("amount", 1, "f", 50.0),
    ]),
    "bloom": (1, [("size", 1, "f", 20.0), ("threshold", 1, "f", 90.0), ("strength", 1, "f", 25.0)]),
    "colorequal": (4, [  # color equalizer; per-hue sat/bright are multipliers, hue shifts in degrees
        ("threshold", 1, "f", 0.1), ("smoothing_hue", 1, "f", 1.0), ("contrast", 1, "f", 0.0),
        ("white_level", 1, "f", 1.0), ("chroma_size", 1, "f", 1.5), ("param_size", 1, "f", 1.0),
        ("use_filter", 1, "i", 1),
    ] + [(f"{kind}_{hue}", 1, "f", 0.0 if kind == "hue" else 1.0)
         for kind in ("sat", "hue", "bright")
         for hue in ("red", "orange", "yellow", "green", "cyan", "blue", "lavender", "magenta")]
      + [("hue_shift", 1, "f", 0.0)]),
    "borders": (4, [  # framing; the *_text fields are unused by darktable
        ("color", 3, "f", [1.0, 1.0, 1.0]),
        ("aspect", 1, "f", -1.0),  # outer frame w/h >= 1; -1 = constant border, 0 = image aspect
        ("aspect_text", 20, "s", "constant border"),
        ("aspect_orient", 1, "i", 0),  # 0=auto (follow the photo), 1=portrait, 2=landscape
        ("size", 1, "f", 0.1),  # border width relative to the basis side
        ("pos_h", 1, "f", 0.5), ("pos_h_text", 20, "s", "1/2"),
        ("pos_v", 1, "f", 0.5), ("pos_v_text", 20, "s", "1/2"),
        ("frame_size", 1, "f", 0.0), ("frame_offset", 1, "f", 0.5),  # line inside the border
        ("frame_color", 3, "f", [0.0, 0.0, 0.0]),
        ("max_border_size", 1, "i", 1),
        ("basis", 1, "i", 0),  # side the size is measured on: 0=auto (constant: longer, canvas: width), 4=longer
    ]),
}


def _fmt(op):
    return "<" + "".join(f"{n}{t}" for _, n, t, _ in MODULES[op][1])


def params_size(op):
    return struct.calcsize(_fmt(op))


def defaults(op):
    return {f: (list(d) if n > 1 and t != "s" else d) for f, n, t, d in MODULES[op][1]}


def encode(op, values):
    """Pack a {field: value} dict (missing fields use defaults) into hex op_params."""
    fields = MODULES[op][1]
    unknown = set(values) - {f for f, *_ in fields}
    if unknown:
        raise KeyError(f"{op}: unknown field(s) {sorted(unknown)}")
    flat = []
    for f, n, t, d in fields:
        v = values.get(f, d)
        if t == "s":
            b = str(v).encode()
            if len(b) >= n:  # keep the C string NUL-terminated
                raise ValueError(f"{op}.{f}: longer than {n - 1} bytes")
            flat.append(b)
            continue
        vs = list(v) if n > 1 else [v]
        if len(vs) != n:
            raise ValueError(f"{op}.{f}: expected {n} values")
        flat += [int(x) if t == "i" else float(x) for x in vs]
    return struct.pack(_fmt(op), *flat).hex()


def decode_blob(text):
    """Inverse of darktable's dt_exif_xmp_encode: plain hex, or 'gzNN' + base64(zlib)."""
    text = (text or "").strip()
    if text.startswith("gz"):
        return zlib.decompress(base64.b64decode(text[4:]))
    return bytes.fromhex(text)


def decode(op, blob):
    vals = struct.unpack(_fmt(op), blob)
    out, i = {}, 0
    for f, n, t, _ in MODULES[op][1]:
        if t == "s":  # one struct item per char array
            out[f] = vals[i].split(b"\0", 1)[0].decode(errors="replace")
            i += 1
            continue
        out[f] = list(vals[i:i + n]) if n > 1 else vals[i]
        i += n
    return out


def write(path, name, description, items):
    """items: [{op, params(dict), enabled, multi_priority, multi_name}] in pipeline-agnostic order."""
    plugins = []
    for num, it in enumerate(items):
        op = it["op"]
        multi_name = it.get("multi_name", "")
        plugins.append(
            "<plugin>"
            f"<num>{num}</num><module>{MODULES[op][0]}</module>"
            f"<operation>{op}</operation><op_params>{encode(op, it['params'])}</op_params>"
            f"<enabled>{int(it.get('enabled', 1))}</enabled>"
            # empty blend params -> darktable uses the module's default blending
            "<blendop_params></blendop_params><blendop_version>14</blendop_version>"
            f"<multi_priority>{it.get('multi_priority', 0)}</multi_priority>"
            f"<multi_name>{escape(multi_name)}</multi_name>"
            f"<multi_name_hand_edited>{int(bool(multi_name))}</multi_name_hand_edited>"
            "</plugin>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<darktable_style version="1.0">\n'
           f"<info><name>{escape(name)}</name><description>{escape(description)}</description></info>\n"
           "<style>\n" + "\n".join(plugins) + "\n</style>\n</darktable_style>\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(xml)


def read(path):
    """Parse a .dtstyle into (name, description, [item dicts with raw bytes])."""
    root = ET.parse(path).getroot()
    items = []
    for p in root.iter("plugin"):
        g = lambda k: (p.findtext(k) or "")
        items.append({
            "num": int(g("num") or 0), "op": g("operation"), "version": int(g("module") or 0),
            "enabled": int(g("enabled") or 0), "blob": decode_blob(g("op_params")),
            "blendop": decode_blob(g("blendop_params")), "blendop_version": int(g("blendop_version") or 0),
            "multi_priority": int(g("multi_priority") or 0), "multi_name": g("multi_name"),
            "multi_name_hand_edited": int(g("multi_name_hand_edited") or 0),
        })
    return root.findtext("info/name"), root.findtext("info/description") or "", items


def db_insert_items(db, styleid, items):
    """Same style_items rows darktable's styles import writes (src/common/styles.c)."""
    for it in items:
        db.execute("INSERT INTO style_items (styleid, num, module, operation, op_params, enabled,"
                   " blendop_params, blendop_version, multi_priority, multi_name, multi_name_hand_edited)"
                   " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (styleid, it["num"], it["version"], it["op"], it["blob"], it["enabled"], it["blendop"],
                    it["blendop_version"], it["multi_priority"], it["multi_name"],
                    it["multi_name_hand_edited"]))


def show(path):
    name, desc, items = read(path)
    print(f"# {name}\n# {desc}")
    for it in items:
        op, label = it["op"], it["op"] + (f" [{it['multi_name']}]" if it["multi_name"] else "")
        known = op in MODULES and MODULES[op][0] == it["version"] and len(it["blob"]) == params_size(op)
        print(f"\n{label} v{it['version']} {'on' if it['enabled'] else 'off'}")
        if not known:
            print(f"  (layout not in tools/dtstyle.py: {len(it['blob'])} bytes)")
            continue
        base = defaults(op)
        for k, v in decode(op, it["blob"]).items():
            if isinstance(v, float):
                v = round(v, 4)
            elif isinstance(v, list):
                v = [round(x, 4) for x in v]
            mark = "" if v == base[k] or (isinstance(v, float) and abs(v - base[k]) < 1e-4) else "  *"
            print(f"  {k} = {v}{mark}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "show":
        show(sys.argv[2])
    else:
        sys.exit(__doc__)
