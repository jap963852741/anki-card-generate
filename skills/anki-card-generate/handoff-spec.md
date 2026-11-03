# Handoff spec

The handoff is the only thing that carries a failed round back to the
generator. This file defines its inputs (the review files), its layout, and
what the generator must do with it.

```
review-N-anki.json ─┐
review-N-custom.json ┼─▶ cards.py handoff ─▶ handoff-N.md ─▶ generator (round N+1)
cards-N.jsonl ───────┘   (+ structural check)
```

## Who writes it

`cards.py handoff` only. The main thread never writes or edits a handoff by
hand: merging by hand drops items, softens them, or adds its own opinion, and
then the generator fixes something nobody reported.

```bash
python3 <CARDS_PY> handoff cards-N.jsonl --count <number> --round N \
  --out handoff-N.md [--review review-N-anki.json] [--review review-N-custom.json] \
  [--prev cards-<N-1>.jsonl]   # round 2+
```

**Locked cards (round 2+).** With `--prev`, a card identical to last round's
is locked: it passed then and is not judged again. Validators are told to
review only the new or changed cards (`cards.py changed`), and the script
drops any finding that still lands on a locked card — a per-card finding on
it, or a Deck-level finding whose ids are all locked. Dropped findings are
listed under "Ignored" and never send a card back. Without this, each fresh
validator found a new nit in a card that had already passed (D1 picked c09 in
round 2 and c08 in round 3 of the same run) and the loop never settled.

| Exit | Meaning | Next |
|---|---|---|
| 0 | `PASS`: no structural problem, no finding. No file written | Deliver |
| 1 | `FAIL`: `handoff-N.md` written | Generator round N+1 |
| 2 | A review file is broken (bad JSON, missing key, unknown card id) | Re-dispatch that validator with the error |

Run it with no `--review` when the structural check failed: the handoff then
holds only `[structure]` items and no validator runs that round.

## Review files

Each validator writes one JSON file, `review-<N>-<validator>.json`:

```json
{
  "validator": "anki",
  "round": 2,
  "cards": [
    {"id": "c03", "rule": "A4", "problem": "Back lists 4 items: \"solid, liquid, gas, plasma\"", "fix": "Make it a cloze: The four states of matter are {{c1::solid}}, {{c2::liquid}}, {{c3::gas}} and {{c4::plasma}}."}
  ],
  "deck": [
    {"rule": "D1", "problem": "Section 'Phase transitions' (a main point) has no card; c09 tests a footnote", "fix": "Replace c09 with a card on what a phase transition is"}
  ]
}
```

| Key | Rule |
|---|---|
| `validator` | `anki` or `custom` |
| `round` | The round being checked |
| `cards` | Per-card findings. `[]` when none. One entry per (card, rule) pair |
| `deck` | Deck-level findings (no single card owns them). `[]` when none |
| `id` | A card id that exists in `cards-N.jsonl` |
| `rule` | `A1`–`A10` / `D1`–`D4` for `anki`; `R1`, `R2`, … for `custom` |
| `problem` | What is wrong, quoting the card's words. Not "too long" but "back is 3 sentences: \"…\"" |
| `fix` | Concrete enough to apply without guessing: the rewritten front / back, or the exact action ("drop c09", "split into two cards: …"). Never "improve" or "make clearer" |

PASS for a validator = both lists empty. There is no `verdict` key: the
script decides from the lists, so a validator cannot say PASS while listing
findings.

## Layout of `handoff-N.md`

Fixed sections, in this order, always present (an empty section says
`none`):

```markdown
# Round 2 handoff — FAIL

Inputs: cards-2.jsonl, review-2-anki.json, review-2-custom.json

## Cards to fix (2)

### c03
- [anki A4] Back lists 4 items: "solid, liquid, gas, plasma" → Make it a cloze: …
- [custom R2] Front does not start with "Ch.3:"; R2 requires it → Ch.3: The four states of matter are …

### c07
- [anki A6] Front says "it" without naming the subject → Q: In what year was the Magna Carta signed?

## Deck-level (1)
- [anki D1] Section 'Phase transitions' has no card; c09 tests a footnote → Replace c09 with a card on what a phase transition is

## Keep unchanged (8)
c01, c02, c04, c05, c06, c08, c09, c10

## Ignored: findings on locked cards (0)
none
```

- Item line: `- [<validator> <rule>] <problem> → <fix>`. Structural
  problems are `- [structure] <message from cards.py check>`.
- Items are grouped by card id, in id order. Exact duplicates are dropped.
- Ignored = findings on locked cards, kept for the record only. The
  generator does not act on them.
- Keep unchanged = every card id with no per-card item. A card named only in
  a Deck-level item (c09 above) is still listed here; the deck item decides
  whether it changes.

## Generator obligations

1. Start from `cards-N.jsonl`, not from scratch.
2. **Keep unchanged**: copy those cards byte for byte — same id, same text,
   same tags. Unless a Deck-level item names the card, do not touch it.
   Enforced: `cards.py check --prev cards-N.jsonl --handoff handoff-N.md`
   fails on any such card changed or dropped.
3. **Cards to fix**: handle every item. Apply its `fix`, or a better fix that
   still satisfies the rule. If you skip an item, say which and why in your
   return; never silently ignore one.
4. **Deck-level**: may add, drop, or replace cards — only the ones the item
   names or implies. The card count must still equal the requested number.
5. New cards take the next unused id; a dropped id is never reused, so a
   reviewer can tell a replaced card from an edited one.

## Stop

After `max rounds` (default 3) the main thread stops even if the last handoff
is FAIL. It exports the last `cards-N.jsonl` with `--handoff handoff-N.md`,
which leaves out every card under "Cards to fix" — still-failing cards are not
delivered. Deck-level items have no card to leave out; they are shown to the
user as open. The deck may end up smaller than asked; it is not topped up. No
rule is dropped or loosened to reach PASS.
