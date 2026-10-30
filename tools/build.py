#!/usr/bin/env python3
"""Build darktable styles from recipes.

  recipes/<group>/<slug>.toml + sims.toml  ->  styles/<group>_<slug>.dtstyle + CATALOG.md

Usage:
  python3 tools/build.py              build everything
  python3 tools/build.py --check      exit 1 if styles/ or CATALOG.md are stale (writes nothing)
  python3 tools/build.py --show SLUG  print the darktable params computed for one recipe
"""
import math
import pathlib
import sys
import tempfile
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import dtstyle  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOT = "A7V"  # style name prefix; flat names (no "|" folders) avoid the 5.6.x quick-menu crash
GROUPS = {"base": "Base", "fuji": "Fuji", "vintage": "Vintage", "medieval": "Medieval", "horror": "Horror",
          "castle": "Castle", "portugal": "Portugal", "food": "Food", "bridge": "Bridge", "wildlife": "Wildlife",
          "frame": "Frame"}

# --- Fuji setting -> darktable translation (tuned by eye; README "How recipes map") ---
HIGHLIGHT_STEP = 0.07   # colorbalancergb highlights_Y per Highlight step (+ = brighter/harder)
SHADOW_STEP = -0.08     # colorbalancergb shadows_Y per Shadow step (+ = deeper/harder)
COLOR_STEP = 0.045      # chroma_global per Color step
CCE = {"off": 0.0, "weak": 0.06, "strong": 0.12}    # saturation_global: density in saturated colors
CCB = {"weak": (1.05, 0.92), "strong": (1.10, 0.85)}  # colorequal blue (sat, bright): deeper, denser blues
DR = {"auto": 0.0, 100: 0.0, 200: -0.02, 400: -0.04}  # extra highlights_Y (highlight protection)
GRAIN_STRENGTH = {"weak": 10.0, "strong": 18.0}
GRAIN_SIZE = {"small": 1000.0, "large": 2000.0}     # darktable "coarseness"
CLARITY_STEP = 0.05     # local contrast detail per Clarity step
WB_STEP_PURITY = 0.007  # primaries tint purity per WB-shift step
MIRED_PER_STEP = 6.0    # Kelvin presets become steps on the blue/amber axis
WB_KELVIN = {"auto": 5500, "daylight": 5500, "shade": 7000, "fluorescent3": 4000, "incandescent": 3000}
B_AXIS = math.radians(-116)  # Fuji "B" axis (blue primary) relative to the red primary
GREY = 0.1845

PIPE_ORDER = ["channelmixerrgb", "primaries", "colorbalancergb", "colorequal", "bilat", "bloom", "grain", "soften",
              "vignette", "borders"]


def wb_tint(wb, shift):
    """Fuji WB (preset/Kelvin) + [R, B] shift -> primaries tint (hue rad, purity), relative to as-shot."""
    kelvin = WB_KELVIN[wb] if isinstance(wb, str) else float(wb)
    warm_mired = 1e6 / 5500 - 1e6 / kelvin           # > 0: camera WB set warmer than daylight
    r, b = shift[0], shift[1] - warm_mired / MIRED_PER_STEP
    x, y = r + b * math.cos(B_AXIS), b * math.sin(B_AXIS)
    return math.atan2(y, x), min(math.hypot(x, y) * WB_STEP_PURITY, 0.15)


def anchor_midtones(cb):
    """Shadow/highlight luminance also moves mid-grey; offset it with the midtones power."""
    f = 1 + 0.25 * cb.get("shadows_Y", 0.0) + 0.5 * cb.get("highlights_Y", 0.0)
    if abs(f - 1) < 1e-6:
        return
    p = math.log(GREY) / math.log(GREY * f) / (1 + cb.get("midtones_Y", 0.0))
    cb["midtones_Y"] = 1 / p - 1


def translate(recipe, sims):
    mods = {}
    cb = mods.setdefault("colorbalancergb", {})
    fuji = recipe.get("fuji")
    if fuji:
        sim = sims[fuji["sim"]]
        cb.update(sim.get("colorbalancergb", {}))
        pr = dict(sim.get("primaries", {}))
        add = lambda k, v: cb.__setitem__(k, cb.get(k, 0.0) + v)
        add("highlights_Y", HIGHLIGHT_STEP * fuji.get("highlight", 0) + DR[fuji.get("dr", "auto")])
        add("shadows_Y", SHADOW_STEP * fuji.get("shadow", 0))
        if sim.get("mono"):
            mods["channelmixerrgb"] = {
                "grey": sims["bw_filters"][fuji.get("filter", "none")] + [0.0],
                "illuminant": 0, "adaptation": 4, "x": 0.3457, "y": 0.3585, "gamut": 0.0,
            }
        else:
            add("chroma_global", COLOR_STEP * fuji.get("color", 0))
            add("saturation_global", CCE[fuji.get("cce", "off")])
            if fuji.get("ccb", "off") != "off":
                sat, bright = CCB[fuji["ccb"]]
                mods["colorequal"] = {"sat_blue": sat, "bright_blue": bright}
            hue, purity = wb_tint(fuji.get("wb", "auto"), fuji.get("wb_shift", [0, 0]))
            if purity > 1e-4:
                pr.update(achromatic_tint_hue=hue, achromatic_tint_purity=purity)
            if pr:
                mods["primaries"] = pr
        if fuji.get("grain", "off") != "off":
            strength, size = fuji["grain"].split("-")
            mods["grain"] = {"strength": GRAIN_STRENGTH[strength],
                             "scale": GRAIN_SIZE[size] / dtstyle.GRAIN_SCALE_FACTOR}
        if fuji.get("clarity", 0):
            mods["bilat"] = {"detail": CLARITY_STEP * fuji["clarity"]}
    for op, vals in recipe.get("darktable", {}).items():  # explicit overrides win
        vals = dict(vals)
        if op == "grain" and "coarseness" in vals:
            vals["scale"] = vals.pop("coarseness") / dtstyle.GRAIN_SCALE_FACTOR
        mods.setdefault(op, {}).update(vals)
    anchor_midtones(cb)
    if not cb:  # an all-default instance would reset the image's own color balance rgb (e.g. frame-only styles)
        del mods["colorbalancergb"]
    return mods


def items_for(mods):
    items = []
    for op in sorted(mods, key=PIPE_ORDER.index):
        it = {"op": op, "params": mods[op]}
        if op == "channelmixerrgb":  # extra instance: leaves the image's white balance instance alone
            it.update(multi_priority=1, multi_name="B&W film")
        items.append(it)
    return items


def fuji_summary(f):
    if not f:
        return ""
    sign = lambda v: f"{v:+g}"
    parts = [f["sim"].replace("_", " ").title()]
    if f.get("filter"):
        parts[0] += f" +{f['filter'][0].upper()}"
    for key, label in (("grain", "Grain"), ("cce", "CCE"), ("ccb", "CCB")):
        if f.get(key, "off") != "off":
            parts.append(f"{label} {f[key]}")
    wb, shift = f.get("wb", "auto"), f.get("wb_shift", [0, 0])
    if wb != "auto" or shift != [0, 0]:
        parts.append(f"WB {wb}{'K' if isinstance(wb, int) else ''} R{sign(shift[0])} B{sign(shift[1])}")
    if f.get("dr"):
        parts.append(f"DR{f['dr']}")
    parts.append(f"H{sign(f.get('highlight', 0))} S{sign(f.get('shadow', 0))}")
    for key, label in (("color", "Color"), ("clarity", "Clarity")):
        if f.get(key):
            parts.append(f"{label} {sign(f[key])}")
    return " · ".join(parts)


def load():
    sims = tomllib.loads((REPO / "sims.toml").read_text())
    recipes = []
    for path in sorted((REPO / "recipes").glob("*/*.toml")):
        r = tomllib.loads(path.read_text())
        r["slug"], r["group_dir"] = path.stem, path.parent.name
        r["file"] = f"{path.parent.name}_{path.stem}.dtstyle"
        if "|" in r["name"]:
            sys.exit(f"{path}: '|' would create a darktable folder; keep style names flat")
        r["style_name"] = f"{ROOT} · {GROUPS[path.parent.name]} · {r['name']}"
        recipes.append(r)
    return sims, recipes


def description(r):
    bits = [r.get("look", "")]
    if r.get("fuji"):
        bits.append(fuji_summary(r["fuji"]))
    if r.get("credit"):
        bits.append(f"Recipe: {r['credit']}")
    if r.get("ec"):
        bits.append(f"Typical exposure comp. {r['ec']}")
    return ". ".join(b.rstrip(".") for b in bits if b) + "."


def catalog(recipes, sims):
    lines = ["<!-- GENERATED by tools/build.py; edit recipes/*.toml instead -->",
             f"# Style catalog ({len(recipes)} styles, darktable {dtstyle.DARKTABLE_VERSION})", "",
             "| darktable style | look | base | file |", "|---|---|---|---|"]
    for r in recipes:
        f = r.get("fuji", {})
        base = f["sim"] if f else "custom"
        lines.append(f"| {r['style_name']} | {r.get('look', '')} | {base} "
                     f"| [{r['file']}](styles/{r['file']}) |")
    return "\n".join(lines) + "\n"


def build(out_dir):
    sims, recipes = load()
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in recipes:
        dtstyle.write(out_dir / r["file"], r["style_name"], description(r), items_for(translate(r, sims)))
    return sims, recipes


def main(argv):
    if argv[:1] == ["--show"] and len(argv) == 2:
        sims, recipes = load()
        r = next((r for r in recipes if r["slug"] == argv[1]), None)
        if not r:
            sys.exit(f"no recipe '{argv[1]}'")
        print(f"{r['style_name']}\n{description(r)}")
        for op, vals in translate(r, sims).items():
            print(f"[{op}] " + ", ".join(f"{k}={round(v, 4) if isinstance(v, float) else v}"
                                         for k, v in vals.items()))
        return
    if argv[:1] == ["--check"]:
        with tempfile.TemporaryDirectory() as tmp:
            sims, recipes = build(pathlib.Path(tmp))
            stale = [r["file"] for r in recipes
                     if not (REPO / "styles" / r["file"]).exists()
                     or (REPO / "styles" / r["file"]).read_bytes() != (pathlib.Path(tmp) / r["file"]).read_bytes()]
        cat = REPO / "CATALOG.md"
        if not cat.exists() or cat.read_text() != catalog(recipes, sims):
            stale.append("CATALOG.md")
        orphans = {p.name for p in (REPO / "styles").glob("*.dtstyle")} - {r["file"] for r in recipes}
        if stale or orphans:
            sys.exit(f"stale: {stale} orphans: {sorted(orphans)} -> run python3 tools/build.py")
        print(f"ok: {len(recipes)} styles up to date")
        return
    if argv:
        sys.exit(__doc__)
    out = REPO / "styles"
    sims, recipes = build(out)
    for orphan in {p.name for p in out.glob("*.dtstyle")} - {r["file"] for r in recipes}:
        (out / orphan).unlink()
    (REPO / "CATALOG.md").write_text(catalog(recipes, sims))
    print(f"built {len(recipes)} styles -> styles/, CATALOG.md")


if __name__ == "__main__":
    main(sys.argv[1:])
