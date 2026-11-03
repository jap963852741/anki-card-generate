#!/usr/bin/env python3
"""Structural check and Anki TSV export for anki-card-generate.

  cards.py check  cards.jsonl --count N [--prev prev.jsonl --handoff prev-handoff.md]
  cards.py export cards.jsonl out.tsv [--handoff last-handoff.md] [--deck D] [--basic-name Basic] [--cloze-name Cloze]
  cards.py handoff cards.jsonl --count N --round R --out handoff.md [--prev prev.jsonl] [--review review.json ...]
  cards.py changed cards.jsonl --prev prev.jsonl

handoff exits 0 (PASS, no file), 1 (FAIL, file written) or 2 (broken review file).
Layout and rules: ../handoff-spec.md
"""
import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

CLOZE = re.compile(r"\{\{c\d+::.+?\}\}", re.S)
TYPES = ("basic", "cloze")
CARD_ID = re.compile(r"\bc\d+\b")


def load(path):
    cards, problems = [], []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cards.append(json.loads(line))
        except json.JSONDecodeError as e:
            problems.append(f"line {n}: invalid JSON ({e.msg})")
    return cards, problems


def check(cards, count):
    problems = []
    seen_ids, seen_fronts = set(), {}
    for i, c in enumerate(cards, 1):
        cid = c.get("id") or f"#{i}"
        for key in ("id", "type", "front", "back"):
            if key not in c:
                problems.append(f"{cid}: missing '{key}'")
        if cid in seen_ids:
            problems.append(f"{cid}: duplicate id")
        seen_ids.add(cid)

        kind, front, back = c.get("type"), str(c.get("front", "")), str(c.get("back", ""))
        if kind not in TYPES:
            problems.append(f"{cid}: type must be one of {TYPES}, got {kind!r}")
        if not front.strip():
            problems.append(f"{cid}: empty front")
        if kind == "basic" and not back.strip():
            problems.append(f"{cid}: basic card with empty back")
        if kind == "basic" and "{{c" in front:
            problems.append(f"{cid}: basic card contains cloze markup")
        if kind == "cloze" and not CLOZE.search(front):
            problems.append(f"{cid}: cloze card has no {{{{c1::...}}}} deletion")
        tags = c.get("tags", [])
        if not isinstance(tags, list):
            problems.append(f"{cid}: tags must be a list")
            tags = []
        if any("\t" in str(v) for v in (front, back, *tags)):
            problems.append(f"{cid}: tab character in a field")

        key = " ".join(front.lower().split())
        if key in seen_fronts:
            problems.append(f"{cid}: same front as {seen_fronts[key]}")
        seen_fronts.setdefault(key, cid)

    if count is not None and len(cards) != count:
        problems.append(f"count: {len(cards)} cards, expected {count}")
    return problems


def load_review(path, card_ids):
    try:
        r = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON ({e.msg})")
    if not isinstance(r, dict) or r.get("validator") not in ("anki", "custom"):
        raise ValueError(f"{path}: validator must be 'anki' or 'custom'")
    for section, keys in (("cards", ("id", "rule", "problem", "fix")), ("deck", ("rule", "problem", "fix"))):
        if not isinstance(r.get(section), list):
            raise ValueError(f"{path}: '{section}' must be a list")
        for n, f in enumerate(r[section], 1):
            missing = [k for k in keys if not str(f.get(k, "")).strip()]
            if missing:
                raise ValueError(f"{path}: {section}[{n}] missing {missing}")
            if section == "cards" and f["id"] not in card_ids:
                raise ValueError(f"{path}: cards[{n}] names unknown card id {f['id']!r}")
    return r


def locked_ids(cards, prev_path):
    """Ids whose card is identical to last round's: it passed then, so it is not judged again."""
    prev = {c.get("id"): c for c in load(prev_path)[0]}
    return {c.get("id") for c in cards if c.get("id") in prev and prev[c.get("id")] == c}


def handoff(cards, problems, reviews, round_no, inputs, locked):
    by_card, deck, ignored = {}, [f"[structure] {p}" for p in problems], []
    for r in reviews:
        for f in r["cards"]:
            item = f"[{r['validator']} {f['rule']}] {f['id']}: {f['problem']} → {f['fix']}"
            if f["id"] in locked:
                ignored.append(item)
            else:
                by_card.setdefault(f["id"], []).append(item.replace(f"{f['id']}: ", "", 1))
        for f in r["deck"]:
            item = f"[{r['validator']} {f['rule']}] {f['problem']} → {f['fix']}"
            named = set(CARD_ID.findall(f"{f['problem']} {f['fix']}"))
            (ignored if named and named <= locked else deck).append(item)
    ignored = list(dict.fromkeys(ignored))
    if not by_card and not deck:
        return None, ignored

    ids = [c.get("id") for c in cards if c.get("id")]
    keep = [i for i in ids if i not in by_card]
    lines = [f"# Round {round_no} handoff — FAIL", "", f"Inputs: {', '.join(inputs)}", ""]
    lines += [f"## Cards to fix ({len(by_card)})", ""]
    for cid in sorted(by_card):
        lines += [f"### {cid}", *(f"- {x}" for x in dict.fromkeys(by_card[cid])), ""]
    if not by_card:
        lines += ["none", ""]
    deck = list(dict.fromkeys(deck))
    lines += [f"## Deck-level ({len(deck)})", *([f"- {x}" for x in deck] or ["none"]), ""]
    lines += [f"## Keep unchanged ({len(keep)})", ", ".join(keep) or "none", ""]
    lines += [f"## Ignored: findings on locked cards ({len(ignored)})", *([f"- {x}" for x in ignored] or ["none"]), ""]
    return "\n".join(lines), ignored


def read_handoff(path):
    """Return (ids under Cards to fix, Deck-level lines, ids under Keep unchanged)."""
    fix, deck, keep, section = [], [], [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].split(" (")[0]
        elif section == "Cards to fix" and line.startswith("### "):
            fix.append(line[4:].strip())
        elif section == "Deck-level" and line.startswith("- "):
            deck.append(line[2:])
        elif section == "Keep unchanged" and line.strip() not in ("", "none"):
            keep += [x.strip() for x in line.split(",")]
    return fix, deck, keep


def check_keep(cards, prev_path, handoff_path):
    prev = {c.get("id"): c for c in load(prev_path)[0]}
    _, deck, keep = read_handoff(handoff_path)
    named = set(CARD_ID.findall(" ".join(deck)))
    now = {c.get("id"): c for c in cards}
    problems = []
    for cid in keep:
        if cid in named:
            continue
        if cid not in now:
            problems.append(f"{cid}: in Keep unchanged but dropped")
        elif now[cid] != prev.get(cid):
            problems.append(f"{cid}: in Keep unchanged but changed")
    return problems


def to_field(text):
    return html.escape(str(text), quote=False).replace("\n", "<br>")


def export(cards, out, deck, basic_name, cloze_name):
    out = Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        f.write("#separator:tab\n#html:true\n#notetype column:1\n#tags column:4\n")
        if deck:
            f.write(f"#deck:{deck}\n")
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        for c in cards:
            notetype = cloze_name if c["type"] == "cloze" else basic_name
            tags = " ".join(str(t).replace(" ", "_") for t in c.get("tags", []))
            writer.writerow([notetype, to_field(c["front"]), to_field(c.get("back", "")), tags])
    return out


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("check")
    pc.add_argument("cards")
    pc.add_argument("--count", type=int)
    pc.add_argument("--prev")
    pc.add_argument("--handoff")
    pe = sub.add_parser("export")
    pe.add_argument("cards")
    pe.add_argument("out")
    pe.add_argument("--handoff")
    pe.add_argument("--deck")
    pe.add_argument("--basic-name", default="Basic")
    pe.add_argument("--cloze-name", default="Cloze")
    ph = sub.add_parser("handoff")
    ph.add_argument("cards")
    ph.add_argument("--count", type=int, required=True)
    ph.add_argument("--round", type=int, required=True)
    ph.add_argument("--out", required=True)
    ph.add_argument("--review", action="append", default=[])
    ph.add_argument("--prev")
    pd = sub.add_parser("changed")
    pd.add_argument("cards")
    pd.add_argument("--prev", required=True)
    args = p.parse_args()

    cards, problems = load(args.cards)
    dropped = []
    if args.cmd == "export" and args.handoff:
        dropped = read_handoff(args.handoff)[0]
        cards = [c for c in cards if c.get("id") not in dropped]
    problems += check(cards, getattr(args, "count", None))
    if args.cmd == "check" and bool(args.prev) != bool(args.handoff):
        p.error("--prev and --handoff go together")
    if args.cmd == "check" and args.prev:
        problems += check_keep(cards, args.prev, args.handoff)

    if args.cmd == "changed":
        locked = locked_ids(cards, args.prev)
        print(", ".join(c.get("id") for c in cards if c.get("id") not in locked) or "none")
        return

    if args.cmd == "handoff":
        card_ids = {c.get("id") for c in cards}
        try:
            reviews = [load_review(r, card_ids) for r in args.review]
        except ValueError as e:
            print(f"BROKEN REVIEW: {e}")
            sys.exit(2)
        inputs = [Path(x).name for x in (args.cards, *args.review)]
        locked = locked_ids(cards, args.prev) if args.prev else set()
        text, ignored = handoff(cards, problems, reviews, args.round, inputs, locked)
        if ignored:
            print(f"ignored {len(ignored)} finding(s) on locked cards")
        if text is None:
            print("PASS: nothing to hand off")
            return
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"FAIL -> {args.out}")
        sys.exit(1)

    if problems:
        print("FAIL")
        print("\n".join(f"- {x}" for x in problems))
        sys.exit(1)

    if args.cmd == "check":
        kinds = {t: sum(c["type"] == t for c in cards) for t in TYPES}
        print(f"OK: {len(cards)} cards ({kinds['basic']} basic, {kinds['cloze']} cloze)")
    else:
        out = export(cards, args.out, args.deck, args.basic_name, args.cloze_name)
        note = f" (dropped still failing: {', '.join(dropped)})" if dropped else ""
        print(f"exported {len(cards)} cards{note} -> {out}")


if __name__ == "__main__":
    main()
