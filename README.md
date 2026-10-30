# darktable styles for the Sony A7 V + FE 24-70mm f/2.8 GM II

21 film-look styles for **darktable 5.6.2**: the popular Fuji X Weekly recipes, the Classic Cuban Neg family,
vintage looks, and everyday base looks. Each one is built from a short, readable recipe and tested
by rendering it with darktable itself. The full list is in **[CATALOG.md](CATALOG.md)**.

| Group | Styles |
|---|---|
| **Fuji Recipes** | Classic Cuban Neg · Cuban Street Neg · CubanAce · Reggie's Portra · Kodachrome 64 · Kodak Gold 200 · Kodak Portra 400 v2 · Kodak Tri-X 400 · CineStill 800T · Pacific Blues · Fujifilm Negative · Reggie's Superia · California Summer |
| **Vintage** | Vintage Kodachrome · 1976 Kodak · Faded Print |
| **Base** | Natural · Vivid · Portrait · Cinematic · Mono |

## Install into darktable
1. Open darktable, go to **lighttable**, and expand the **styles** module (right panel).
2. Click **import…**, open this repo's `styles/` folder, select all `.dtstyle` files, and confirm.
3. The styles show up as one flat list: **A7V · Base · …**, **A7V · Fuji · …**, **A7V · Vintage · …**.
   If darktable asks about an existing name, choose *overwrite*.

### Faster ways to pick a style
- **Filter box (lighttable styles module):** type part of a name *or* description (`cuban`, `portra`, `warm`, `B&W`,
  `Classic Chrome`), then double-click the match. Ctrl/⌘-click several styles and press **apply** to stack them.
  Hovering over a style shows a live preview of it on the selected image.
- **Keyboard shortcuts:** *preferences → shortcuts*, search for a style's name, and assign a key (e.g. ⌥1–⌥9 for your
  favorites). It then applies in lighttable or darkroom with one keypress.
- **Darkroom quick access:** assign a key to *quick access to styles*, then use ↑/↓ and Enter in the menu.

> **Known darktable 5.6.x crash:** in the darkroom quick-access styles menu, dragging through a *folder* with the mouse
> button held down crashes darktable (null event in `_darkroom_ui_apply_style_activate_callback`; this menu was rewritten
> on darktable master). These styles use flat names, so they never create folders. darktable's own *darktable › camera styles*
> folder still can trigger it, so click instead of dragging when you pass over it.

## Instagram posts
- **White border:** in the export module (*global options*), set **style** to **A7V · Frame · Instagram White Border 3:4**
  with mode *append*, and the size to **1080 × 1440**. 3:4 is the tallest post shape and the profile grid's tile shape,
  so the border shows uncut in the feed and the grid on every phone. Your darkroom edit stays border-free.
- **One export folder per day:** an export path like `/Volumes/T7/$(YEAR)/exports/$(MONTH.SHORT,,)-$(DAY)/$(FILE_NAME)`
  makes darktable write into today's folder (`2026/exports/oct-30`), creating it if needed. `EXPORTS` at the top of
  `tools/instagram.py` holds the same pattern; change both together.
- **Photo as its own background:** export JPEGs without a frame, then run `python3 tools/instagram.py 1234` for just
  DSC01234 from today's folder, or with no arguments for every photo in it (`--day oct-29` for another day; folders
  and files work too). Each photo gets a `NAME_ig.jpg` beside it: the photo with a thin white border on a zoomed-in,
  slightly dimmed copy of itself, at 1080 × 1440. Tune with `--dim`, `--margin`, `--border`, or `--blur 30` for a
  blurred background. Needs Pillow (`python3 -m pip install Pillow`).

## What the styles assume
- **Scene-referred workflow (AgX or sigmoid).** The styles never touch the tone mapper, exposure, white balance,
  lens correction, denoise or sharpening, so they stack on top of your normal per-image edit.
  They only use color balance rgb, rgb primaries, local contrast, grain and vignette
  (plus a second color calibration instance named *B&W film* for the monochrome styles).
- **Exposure is yours.** Fuji recipes are shot with exposure compensation, and each style's tooltip lists the
  recipe's typical value (often +1/3 to +1 EV). Add that in the exposure module if the image looks dense.
- **Fuji white balance is relative.** "Auto, R+4 B-5" becomes a warm tint on top of your as-shot white balance.
  Kelvin-based recipes such as CineStill 800T (Fluorescent 3) are tinted relative to daylight, so they look strongest in daylight.

### One-time setup for the A7 V + 24-70 GM II
darktable 5.6.2 reads A7 V (ILCE-7M5) raws and ships noise profiles and Lensfun data for both the body and the lens.
- **Lens correction**: choose *embedded metadata* (uses the correction data Sony writes into every ARW) or *Lensfun database*,
  then save it as a preset with *auto-apply* for this lens. Keep it out of styles, because it depends on focal length.
- **Denoise (profiled)**: the A7 V profile is built in. Apply it per image at high ISO.
- **Sharpening**: the GM II is very sharp. The styles add no sharpening, and Fuji "Sharpness" values are ignored on purpose.

### Removing older "Sony A7 V › …" styles
- **01 Natural … 06 Black & White:** these switch on **sigmoid**. Your darktable already applies **AgX** to every raw,
  so using them tone-maps twice (flat, washed-out results). The **A7V · Base** styles replace them.
- **Sony A7 V › Base / Fuji Recipes / Vintage:** the first, folder-based import of this repo, replaced by the flat `A7V · …` names.

In the styles module, type `Sony A7 V` in the filter box and expand the folders. Click the first style, shift-click
the last, and click **remove**. Folder rows themselves are ignored, so only the styles inside them get removed.

## How recipes map to darktable
Recipes keep the published Fuji settings verbatim. `tools/build.py` translates them:

| Fuji setting | darktable |
|---|---|
| Film simulation | base look from `sims.toml` (color balance rgb + rgb primaries) |
| Highlight / Shadow | color balance rgb highlight gain and shadow lift luminance, re-anchored so mid-grey stays put |
| Color | color balance rgb global chroma |
| Color Chrome Effect | color balance rgb saturation (adds density to saturated colors) |
| Color Chrome FX Blue | rgb primaries blue purity |
| White balance + shift | rgb primaries achromatic tint |
| Dynamic range | extra highlight compression (DR200/DR400) |
| Grain (weak/strong, small/large) | grain strength / coarseness |
| Clarity | local contrast detail |
| Acros +Y/+R/+G | color calibration gray tab (B&W film instance) |

These are approximations of the in-camera JPEG looks, tuned by eye. Every number lives in one place and is easy to retune.

## Working on the repo
```sh
python3 tools/build.py                        # recipes → styles/ + CATALOG.md
python3 tools/verify.py                       # render every style with darktable-cli → previews/index.html
python3 tools/verify.py --image ~/path/DSC00502.ARW   # previews on one of your own raws
```
Python 3.11+ with no dependencies (only `tools/instagram.py` needs Pillow). Add a recipe by following
[recipes/README.md](recipes/README.md).
AI agents should start at [CLAUDE.md](CLAUDE.md).

## Credits
Recipes are by their authors, linked in each recipe file's `source` field:
[Fuji X Weekly](https://fujixweekly.com) (Ritchie Roesch; Reggie Ballesteros for Reggie's Portra and Reggie's Superia), and
Osan ([@osanbilgi](https://www.instagram.com/osanbilgi/)) for Classic Cuban Neg, Cuban Street Neg and CubanAce
([FujiRumors](https://www.fujirumors.com/?p=128669)). This repo only translates their published settings for darktable.
