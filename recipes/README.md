# Recipe format

One file = one darktable style. Folder = group in darktable (`base` → Base, `fuji` → Fuji Recipes, `vintage` → Vintage).

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
```

## Add a recipe
1. Copy a sibling file to `recipes/<group>/<slug>.toml` and fill it in.
2. `python3 tools/build.py --show <slug>` to sanity-check the computed values.
3. `python3 tools/build.py && python3 tools/verify.py --only <slug>`. It must print `ok`.
4. Optional: look at `previews/<group>_<slug>.jpg`. CATALOG.md updates itself.
