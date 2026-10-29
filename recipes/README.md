# Recipe format

One file = one darktable style. Folder = group in darktable (`base` → Base, `fuji` → Fuji, `vintage` → Vintage,
`medieval` → Medieval, `horror` → Horror, `castle` → Castle, `portugal` → Portugal, `food` → Food, `bridge` → Bridge,
`wildlife` → Wildlife). A new folder needs an entry in `GROUPS` in tools/build.py.

```toml
name = "Classic Cuban Neg"            # shown in darktable as Sony A7 V › Fuji Recipes › Classic Cuban Neg
look = "one-line description"          # becomes the style's tooltip together with the settings summary
credit = "Osan (@osanbilgi)"           # required for third-party recipes
source = "https://…"                   # required for third-party recipes
ec = "+1/3 to +2/3"                    # optional: the recipe's typical exposure compensation (informational)

[fuji]                                 # optional: settings exactly as published
sim = "classic_negative"               # key in ../sims.toml
filter = "red"                         # acros only: none | yellow | red | green
grain = "strong-large"                 # off | weak-small | weak-large | strong-small | strong-large
cce = "strong"                         # Color Chrome Effect: off | weak | strong
ccb = "strong"                         # Color Chrome FX Blue: off | weak | strong
wb = "auto"                            # auto | daylight | shade | fluorescent3 | incandescent | Kelvin int
wb_shift = [4, -5]                     # [Red, Blue]
dr = 400                               # auto | 100 | 200 | 400
highlight = -2                         # -2 … +4
shadow = 1                             # -2 … +4
color = 4                              # -4 … +4
clarity = -4                           # -5 … +5
# sharpness, noise reduction and ISO are intentionally ignored (per-image in darktable)

[darktable.colorbalancergb]            # optional raw overrides, applied last
global_Y = 0.0025                      # field names: tools/dtstyle.py MODULES

[darktable.colorequal]                 # per-hue control: red orange yellow green cyan blue lavender magenta
sat_blue = 1.2                         # sat_* / bright_* are multipliers (1 = unchanged)
hue_green = -10.0                      # hue_* shifts in degrees
```

### colorequal: what the node names actually hit (darktable 5.6.2 math)
- Node names are loose. Measured on real colors: **orange** holds tram/lemon yellows, gold, bronze and sodium
  light; **yellow** holds grass, lettuce and foliage; browns, bread crust, rust and skin are split **red**/**orange**;
  sky blue is **blue**, but cobalt, azulejo, peacock-neck and twilight blues are mostly **lavender**.
- `sat_*` acts twice as hard as it reads: gain = 1 + 2 × (value − 1), so 1.10 is +20% and 0.50 is fully grey.
- `bright_*` scales with each pixel's saturation: strong on reds and blues, nearly nothing on yellows, greens, cyans.
- The default `threshold = 0.1` damps bright yellows, greens and cyans by 30–45% (they are low-saturation to this
  module). Use `threshold = 0.04` (or lower) when a recipe needs to move them.
- `hue_*`: + rotates red → orange → yellow → green → cyan → blue → lavender → magenta.

## Add a recipe
1. Copy a sibling file to `recipes/<group>/<slug>.toml` and fill it in.
2. `python3 tools/build.py --show <slug>` to sanity-check the computed values.
3. `python3 tools/build.py && python3 tools/verify.py --only <slug>`. It must print `ok`.
4. Optional: look at `previews/<group>_<slug>.jpg`. CATALOG.md updates itself.
5. Quit darktable, then `python3 tools/install.py`. It builds and syncs every style into darktable's library
   (adds new, updates changed, removes A7V styles whose recipe is gone; backs up data.db first). No manual import.
