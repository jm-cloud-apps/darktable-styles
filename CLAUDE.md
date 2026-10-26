# darktable-styles: Sony A7 V + FE 24-70mm f/2.8 GM II

Film-recipe styles for darktable 5.6.2, generated from small TOML recipes. Python 3.11+ stdlib only.

## Map (read top-down, stop when you have enough)
- `CATALOG.md`: generated index of every style. Read this instead of listing/opening recipes.
- `recipes/<base|fuji|vintage>/<slug>.toml`: **source of truth**, one style per file. Schema and add-a-recipe steps: `recipes/README.md`.
- `sims.toml`: Fuji film-simulation base looks shared by recipes.
- `tools/build.py`: Fuji settings → darktable translation (tuning constants at top), writes outputs.
- `tools/dtstyle.py`: binary param layouts pinned to darktable 5.6.2, plus a `show` decoder.
- `tools/verify.py`: renders every style through real darktable-cli in a throwaway config.
- `styles/*.dtstyle`, `CATALOG.md`: **generated**. Never hand-edit. Don't read `styles/` (hex blobs); use `--show`.
- `previews/`: verify output (gitignored). The JPEGs are viewable when judging a look.

## Commands
```sh
python3 tools/build.py                      # regenerate styles/ + CATALOG.md (instant)
python3 tools/build.py --show <slug>        # computed darktable params for one recipe
python3 tools/build.py --check              # exit 1 if outputs are stale
python3 tools/verify.py --only <substr>     # ~6 s/style; all 21 ≈ 2 min. --image <raw> for real previews
python3 tools/dtstyle.py show <file>        # decode any .dtstyle (user exports, downloaded packs)
```

## Rules
- Styles are workflow-agnostic. Never add a tone mapper (AgX/sigmoid/filmic), exposure, white balance,
  lens correction, denoise or sharpening. Those are per-image, and the user's darktable runs scene-referred **AgX**.
  Fuji WB settings become a `primaries` tint relative to as-shot WB.
- To tweak one look, edit its recipe (`[fuji]` settings or `[darktable.<op>]` field overrides).
  Edit `sims.toml` only when every recipe on that sim should change; edit the build.py constants only for global retuning.
- Style names are flat: `A7V · <Group> · <name>` (`ROOT`/`GROUPS` in build.py; the group comes from the recipe folder).
  Never use `|`. It creates darktable folders, and dragging through folders in the darkroom styles menu crashes darktable 5.6.x.
- New module: add its struct to `MODULES` in tools/dtstyle.py, copying the version and field order from darktable
  `src/iop/<op>.c` (`DT_MODULE_INTROSPECTION`, `*_params_t`). Add it to `PIPE_ORDER` in build.py, then verify.
- After changes, run build, then verify on just the affected styles (`--only`). Report verify failures verbatim.
- Recipe credits and sources are mandatory for third-party recipes (`credit`, `source` keys).
