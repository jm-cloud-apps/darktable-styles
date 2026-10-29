#!/usr/bin/env python3
"""Sync the built styles straight into your darktable library (replaces styles-module imports).

  python3 tools/install.py                  build, then add/update every A7V style and delete A7V styles
                                            whose recipe is gone
  python3 tools/install.py --dry-run        only print what would change
  python3 tools/install.py --remove-legacy  also delete the old "Sony A7 V|..." folder styles
  python3 tools/install.py --db PATH        target another data.db (default ~/.config/darktable/data.db)

darktable must be closed: it caches styles in memory and keeps data.db open.
data.db is backed up next to itself before anything is written (the last 5 backups are kept).
"""
import argparse
import datetime
import os
import pathlib
import shutil
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build  # noqa: E402
import dtstyle  # noqa: E402

DEFAULT_DB = pathlib.Path.home() / ".config/darktable/data.db"
LEGACY_PREFIX = "Sony A7 V|"  # pre-flat names; "|" folders crash the 5.6.x darkroom styles menu
BACKUPS_KEPT = 5
ITEM_COLS = ("num, module, operation, op_params, enabled, blendop_params, blendop_version,"
             " multi_priority, multi_name, multi_name_hand_edited")


def darktable_running(db_path):
    """darktable writes its pid to data.db.lock while it has this library open."""
    try:
        os.kill(int(db_path.with_name(db_path.name + ".lock").read_text().strip()), 0)
    except (OSError, ValueError):
        return False
    return True


def norm(row):
    """Empty blobs and NULL compare equal (darktable's GUI import may store either)."""
    return tuple((bytes(v) or None) if isinstance(v, (bytes, memoryview)) else v for v in row)


def item_rows(items):
    return [norm((it["num"], it["version"], it["op"], it["blob"], it["enabled"], it["blendop"],
                  it["blendop_version"], it["multi_priority"], it["multi_name"], it["multi_name_hand_edited"]))
            for it in items]


def plan(db, styles, remove_legacy):
    """-> [(action, name, styleid, description, items)] with action in + ~ -"""
    existing = dict(db.execute("SELECT name, id FROM styles"))
    changes = []
    for name, (desc, items) in styles.items():
        sid = existing.get(name)
        if sid is None:
            changes.append(("+", name, None, desc, items))
            continue
        old_desc = db.execute("SELECT description FROM styles WHERE id = ?", (sid,)).fetchone()[0]
        old = [norm(row) for row in
               db.execute(f"SELECT {ITEM_COLS} FROM style_items WHERE styleid = ? ORDER BY num", (sid,))]
        if old_desc != desc or old != item_rows(items):
            changes.append(("~", name, sid, desc, items))
    prefix = f"{build.ROOT} · "
    for name, sid in sorted(existing.items()):
        if (name.startswith(prefix) and name not in styles) or (remove_legacy and name.startswith(LEGACY_PREFIX)):
            changes.append(("-", name, sid, None, None))
    return changes


def apply(db, changes):
    for action, name, sid, desc, items in changes:
        if action == "+":
            sid = db.execute("INSERT INTO styles (name, description) VALUES (?, ?)", (name, desc)).lastrowid
        elif action == "~":
            db.execute("UPDATE styles SET description = ? WHERE id = ?", (desc, sid))
        db.execute("DELETE FROM style_items WHERE styleid = ?", (sid,))
        if action == "-":
            db.execute("DELETE FROM styles WHERE id = ?", (sid,))
        else:
            dtstyle.db_insert_items(db, sid, items)
    db.commit()


def backup(db_path):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = db_path.with_name(f"{db_path.name}-styles-backup-{stamp}")
    shutil.copy2(db_path, dest)
    for old in sorted(db_path.parent.glob(f"{db_path.name}-styles-backup-*"))[:-BACKUPS_KEPT]:
        old.unlink()
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=pathlib.Path, default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--remove-legacy", action="store_true")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"{args.db} not found; start darktable once, or pass --db")
    if not args.dry_run and darktable_running(args.db):
        sys.exit("darktable is running; quit it first (it would not see the changes and could overwrite them)")

    build.main([])
    styles = {}
    for f in sorted((build.REPO / "styles").glob("*.dtstyle")):
        name, desc, items = dtstyle.read(f)
        styles[name] = (desc, items)

    db = sqlite3.connect(args.db)
    changes = plan(db, styles, args.remove_legacy)
    for action, name, *_ in changes:
        print(f"  {action} {name}")
    if not changes:
        print(f"darktable already has all {len(styles)} styles up to date")
        return
    if args.dry_run:
        print(f"dry run: {len(changes)} change(s) not written")
        return
    db.close()
    print(f"backup: {backup(args.db)}")
    db = sqlite3.connect(args.db)
    apply(db, changes)
    db.close()
    counts = {a: sum(c[0] == a for c in changes) for a in "+~-"}
    print(f"darktable library updated: {counts['+']} added, {counts['~']} updated, {counts['-']} removed")


if __name__ == "__main__":
    main()
