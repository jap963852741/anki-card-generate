# anki-validator prompt

Fill the {placeholders}, then dispatch as a read-only `general-purpose`
subagent. Runs every round, in parallel with the custom-rules validator. A
fresh agent every round; it never sees the generator's change log or the
previous handoff, so it judges the cards, not the story about them.

---

You check Anki cards against the general Anki rules. You must not edit any
card. You write one file: your review.

Work folder: `{work_dir}`

| File | What it is |
|---|---|
| `cards-{round}.jsonl` | The cards to check |
| `source.md` | Ground truth for `A1` |
| `{anki_rules}` | The rules you check: `A1`–`A10` per card, `D1`–`D4` for the deck |
| `request.md` | Read only its custom rules: where a custom rule asks for something a general rule forbids, it is not a finding |

## What to do

1. Check every card against every `A` rule. Use each card's `source` quote and
   `source.md` for `A1`.
2. Check the deck as a whole against `D1`–`D4`. For `D1`, skim `source.md` for
   main points with no card.
3. Only real rule breaks. A card you would merely phrase differently is not a
   finding. An empty review is a good review.

## Output: `{work_dir}/review-{round}-anki.json`

Schema and the rules for writing a finding are in "Review files" of
`{handoff_spec}`. Use `"validator": "anki"`; `rule` is an `A` or `D` id.

## Return

```
PASS | FAIL (<n> card findings, <m> deck findings)
path: {work_dir}/review-{round}-anki.json
```
