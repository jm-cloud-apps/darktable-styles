#!/usr/bin/env python3
"""Render every style with the real darktable (darktable-cli) to prove it loads and applies.

Uses a throwaway darktable config, so your library and styles are never touched.
Fails on version mismatches, modules that did not apply, or no-op renders.
Writes previews/<style>.jpg and previews/index.html (contact sheet).

Usage:
  python3 tools/verify.py                      synthetic color chart
  python3 tools/verify.py --image DSC0001.ARW  your own A7 V raw (realistic previews)
  python3 tools/verify.py --only cuban         subset by filename substring
Env: DARKTABLE_CLI=/path/to/darktable-cli (default: macOS app bundle or PATH)
"""
import argparse
import html
import os
import pathlib
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import dtstyle  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
MAC_CLI = "/Applications/darktable.app/Contents/MacOS/darktable-cli"
COMMITTED = re.compile(r"committed\s+\[export\]\s+(\w+)\.\d+\s+\S+\s+enabled")
FAILURE = re.compile(r"version mismatch|can't load|dt_styles_apply_style_item|no such style", re.I)


def find_cli():
    for c in (os.environ.get("DARKTABLE_CLI"), MAC_CLI, shutil.which("darktable-cli")):
        if c and os.path.exists(c):
            return c
    sys.exit("darktable-cli not found; set DARKTABLE_CLI")


def write_chart(path):
    """Gray ramp + 18 ColorChecker-like patches (sRGB PNG), no dependencies."""
    patches = [(115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (133, 128, 177),
               (103, 189, 170), (214, 126, 44), (80, 91, 166), (193, 90, 99), (94, 60, 108),
               (157, 188, 64), (224, 163, 46), (56, 61, 150), (70, 148, 73), (175, 54, 60),
               (231, 199, 31), (187, 86, 149), (8, 133, 161)]
    w, h, rows = 600, 400, []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            v = int(255 * x / (w - 1))
            row += bytes((v, v, v) if y < 100 else patches[x // 100 + 6 * ((y - 100) // 100)])
        rows.append(bytes(row))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def import_styles(db_path, files):
    db = sqlite3.connect(db_path)
    for f in files:
        name, desc, items = dtstyle.read(f)
        sid = db.execute("INSERT INTO styles (name, description) VALUES (?, ?)", (name, desc)).lastrowid
        dtstyle.db_insert_items(db, sid, items)
    db.commit()
    db.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", type=pathlib.Path)
    ap.add_argument("--only", default="")
    ap.add_argument("--size", type=int, default=900)
    args = ap.parse_args()

    cli = find_cli()
    files = sorted(p for p in (REPO / "styles").glob("*.dtstyle") if args.only in p.name)
    if not files:
        sys.exit("no styles matched; run python3 tools/build.py")
    out_dir = REPO / "previews"
    out_dir.mkdir(exist_ok=True)
    image = args.image
    if not image:
        image = out_dir / "_chart.png"
        write_chart(image)

    with tempfile.TemporaryDirectory(prefix="dt-verify-") as cfg:
        # mirror the user's pixel workflow (AgX/sigmoid/filmic) so raw previews match their defaults
        user_rc = pathlib.Path.home() / ".config/darktable/darktablerc"
        if user_rc.exists():
            wf = [l for l in user_rc.read_text().splitlines() if l.startswith("plugins/darkroom/workflow=")]
            pathlib.Path(cfg, "darktablerc").write_text("\n".join(wf) + "\n")

        def render(out, style=None):
            cmd = ([cli, str(image), str(out), "--width", str(args.size), "--height", str(args.size)]
                   + (["--style", style] if style else [])
                   + ["--core", "--configdir", cfg, "--library", ":memory:", "-d", "params"])
            return subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout

        baseline = out_dir / "_original.jpg"
        baseline.unlink(missing_ok=True)  # darktable-cli never overwrites; a stale baseline breaks the no-op check
        render(baseline)  # also creates the throwaway data.db
        import_styles(pathlib.Path(cfg, "data.db"), files)

        failures, cards = [], []
        for f in files:
            name, _, items = dtstyle.read(f)
            out = out_dir / f"{f.stem}.jpg"
            out.unlink(missing_ok=True)
            log = render(out, name)
            problems = [l.strip() for l in log.splitlines() if FAILURE.search(l)]
            missing = {it["op"] for it in items if it["enabled"]} - set(COMMITTED.findall(log))
            if missing:
                problems.append(f"modules not applied: {sorted(missing)}")
            if not out.exists():
                problems.append("no output written")
            elif out.read_bytes() == baseline.read_bytes():
                problems.append("render identical to original (style had no effect)")
            print(f"{'FAIL' if problems else 'ok  '} {name}")
            for p in problems:
                print(f"      {p}")
            if problems:
                failures.append(name)
            cards.append((name, out.name))

    sheet = "".join(f'<figure><img src="{html.escape(src)}" loading="lazy"><figcaption>'
                    f'{html.escape(n)}</figcaption></figure>'
                    for n, src in [("Original", baseline.name)] + cards)
    (out_dir / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Style previews</title><style>"
        "body{font:14px system-ui;background:#1b1b1b;color:#ddd;margin:16px}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}"
        "img{width:100%;display:block}figure{margin:0}figcaption{padding:4px 0}</style>"
        f"<h1>Style previews · {html.escape(image.name)}</h1><main>{sheet}</main>\n")
    print(f"\n{len(files) - len(failures)}/{len(files)} passed · previews: {out_dir / 'index.html'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
