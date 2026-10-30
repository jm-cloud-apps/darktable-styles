#!/usr/bin/env python3
"""Turn darktable exports into Instagram posts: the whole photo with a thin white border, centered on a
zoomed-in, slightly dimmed copy of itself, on a 3:4 canvas (the shape Instagram's feed and profile grid
both show uncut). darktable styles can't do this: framing fills the canvas with one solid color, and the
overlay module is tied to one specific image.

  python3 tools/instagram.py                     every photo in today's export folder -> NAME_ig.jpg beside it
  python3 tools/instagram.py 1234                just DSC01234 from today's folder (file number or name)
  python3 tools/instagram.py --day oct-29 1234   the same from another day's folder
  python3 tools/instagram.py FOLDER_OR_FILE ...  any other folders or files
  options: --out DIR  --size 1080x1440  --border PX  --margin 0.07  --dim 0.2  --blur 0

Today's folder comes from EXPORTS below, the same pattern as the darktable export path
/Volumes/T7/$(YEAR)/exports/$(MONTH.SHORT,,)-$(DAY)/$(FILE_NAME). Export JPEG or PNG (sRGB, look applied,
no Frame style). Photos ending in _ig are skipped, so re-running rebuilds the posts instead of making
_ig_ig copies. Needs Pillow, the repo's only non-stdlib dependency: python3 -m pip install Pillow
"""
import argparse
import datetime
import pathlib
import re
import sys

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
except ImportError:
    sys.exit("tools/instagram.py needs Pillow: python3 -m pip install Pillow")

EXPORTS = "/Volumes/T7/{year}/exports/{day}"  # {day} like oct-30
SUFFIX = "_ig"
PHOTO_TYPES = {".jpg", ".jpeg", ".png"}
LANCZOS = Image.Resampling.LANCZOS


def compose(photo, size, border, margin, dim, blur):
    """photo (RGB) -> canvas of `size`: zoomed background + bordered photo, centered."""
    w, h = size
    bg = ImageOps.fit(photo, size, LANCZOS)  # fill the canvas, cropping the overflow evenly
    if blur:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
    bg = ImageEnhance.Brightness(bg).enhance(1 - dim)
    m = round(margin * w)  # background left showing around the bordered photo
    room_w, room_h = w - 2 * (m + border), h - 2 * (m + border)
    scale = min(room_w / photo.width, room_h / photo.height)
    inset = photo.resize((round(photo.width * scale), round(photo.height * scale)), LANCZOS)
    framed = ImageOps.expand(inset, border=border, fill="white")
    bg.paste(framed, ((w - framed.width) // 2, (h - framed.height) // 2))
    return bg


def day_folder(day=None):
    """Export folder for a day like 'oct-29' (its latest past date, so dec-31 works in January); default today."""
    today = d = datetime.date.today()
    if day:
        d = datetime.datetime.strptime(f"{day}-{today.year}", "%b-%d-%Y").date()
        if d > today:
            d = d.replace(year=today.year - 1)
    return pathlib.Path(EXPORTS.format(year=d.year, day=d.strftime("%b-%d").lower()))


def photos_in(folder):
    """Exported photos in a folder, minus finished posts and the "._" metadata files macOS puts on external drives."""
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES
                  and not p.name.startswith(".") and not p.stem.endswith(SUFFIX))


def file_number(stem):
    m = re.search(r"\d+", stem)  # DSC01234_01 -> 1234
    return int(m.group()) if m else None


def find(folder, wanted):
    """'1234', 'D1234' or 'DSC01234' -> the photos in folder with that file number or name."""
    digits = re.sub(r"\D", "", wanted)
    return [p for p in photos_in(folder)
            if p.stem.lower() == wanted.lower() or (digits and file_number(p.stem) == int(digits))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", nargs="*", help="file numbers or names from the day's folder (1234, DSC01234), "
                                              "or folders/files; none = the whole day's folder")
    ap.add_argument("--day", help="export folder date like oct-29 (default: today)")
    ap.add_argument("--out", type=pathlib.Path, help="output folder (default: next to each photo)")
    ap.add_argument("--size", default="1080x1440", help="canvas WxH (default 1080x1440, Instagram 3:4)")
    ap.add_argument("--border", type=int, help="white border in px (default 1.3%% of the width: 14 px at 1080)")
    ap.add_argument("--margin", type=float, default=0.07,
                    help="background showing around the photo, as a fraction of the width (default 0.07)")
    ap.add_argument("--dim", type=float, default=0.2, help="background darkening, 0-1 (default 0.2)")
    ap.add_argument("--blur", type=float, default=0.0, help="background blur radius in px (default 0: sharp)")
    args = ap.parse_args()

    try:
        size = tuple(int(v) for v in args.size.lower().split("x"))
        assert len(size) == 2 and min(size) > 0
    except (ValueError, AssertionError):
        ap.error(f"--size must look like 1080x1440, not {args.size!r}")
    if not 0 <= args.dim <= 1 or not 0 <= args.margin < 0.4:
        ap.error("--dim must be 0-1 and --margin 0-0.4")
    try:
        folder = day_folder(args.day)
    except ValueError:
        ap.error(f"--day must look like oct-29, not {args.day!r}")
    border = args.border if args.border is not None else round(0.013 * size[0])

    def day_photos():
        if not folder.is_dir():
            sys.exit(f"no export folder {folder} (drive not connected, or nothing exported that day?)")
        return photos_in(folder)

    photos = [] if args.photos else day_photos()
    for item in args.photos:
        path = pathlib.Path(item)
        if path.is_dir():
            photos += photos_in(path)
        elif path.is_file():
            photos.append(path)
        else:
            hits = find(folder, item) if day_photos() else []
            if not hits:
                names = ", ".join(p.stem for p in photos_in(folder)) or "none"
                sys.exit(f"no photo {item!r} in {folder} (photos there: {names})")
            photos += hits
    if not photos:
        sys.exit("no photos found")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    for path in photos:
        if path.stem.endswith(SUFFIX):
            print(f"skip {path.name} (already a post)")
            continue
        try:
            with Image.open(path) as im:
                icc = im.info.get("icc_profile")  # keep darktable's sRGB tag so colors don't shift
                photo = ImageOps.exif_transpose(im).convert("RGB")
        except (OSError, UnidentifiedImageError) as e:
            print(f"skip {path.name} ({e})")
            continue
        out = (args.out or path.parent) / f"{path.stem}{SUFFIX}.jpg"
        post = compose(photo, size, border, args.margin, args.dim, args.blur)
        post.save(out, quality=95, subsampling=0, icc_profile=icc)  # 4:4:4 keeps the thin border crisp
        print(f"{path.name} -> {out}")


if __name__ == "__main__":
    main()
