# generator prompt

Fill the {placeholders}, then dispatch as one `general-purpose` subagent. A
fresh agent every round. Drop the `{if round >= 2:}` block in round 1.

---

You write Anki cards. Everything you need is in files; read them, do not
expect their contents in this prompt.

Work folder: `{work_dir}`

| File | What it is |
|---|---|
| `source.md` | The only ground truth. No fact that is not in it |
| `request.md` | Card count, custom rules `R1`, `R2`, …, deck, card language |
| `{anki_rules}` | General rules `A1`–`A10`, `D1`–`D4`. A custom rule wins where they conflict |
{if round >= 2:}
| `cards-{prev}.jsonl` | Last round's cards |
| `handoff-{prev}.md` | What failed last round. Format and your obligations: `{handoff_spec}` |
{end if}

## Round 1

1. List the `{number}` most important, testable points of `source.md` —
   importance first, not the first `{number}` sentences.
2. Write one card per point, following every rule above.

{if round >= 2:}
## Round {round}

Follow "Generator obligations" in `{handoff_spec}` exactly. In short: start
from `cards-{prev}.jsonl`, copy every card under "Keep unchanged" byte for
byte, fix every item under "Cards to fix" and "Deck-level". Do not touch
anything the handoff does not name.
{end if}

## Output: `{work_dir}/cards-{round}.jsonl`

One JSON object per line:

```json
{"id": "c01", "type": "basic", "front": "...", "back": "...", "tags": ["..."], "source": "<the source.md sentence this card is based on>"}
```

- `type` is `basic` or `cloze`.
- Cloze: `front` holds the text with `{{c1::answer}}` deletions; `back` is
  optional extra info and may be `""`.
- Plain text only, no HTML. `\n` for a line break. No tab characters.
- `source` is a verbatim quote from `source.md`. If you cannot quote one, the
  card is not supported — drop it.
- Ids are `c01`, `c02`, …. New cards take the next unused number; never reuse
  a dropped card's id.

## Self-check

```bash
python3 {cards_py} check {work_dir}/cards-{round}.jsonl --count {number}
{if round >= 2:}
  --prev {work_dir}/cards-{prev}.jsonl --handoff {work_dir}/handoff-{prev}.md
{end if}
```

Fix and re-run until it prints `OK`. In round 2+ it also fails when you
changed or dropped a "Keep unchanged" card that no Deck-level item names.

## Return

Keep it short; the main thread re-checks everything itself.

```
path: {work_dir}/cards-{round}.jsonl
count: <n> (<b> basic, <c> cloze)
changes:
- c03: <what changed>            # round 2+: one line per handoff item
- skipped c07 [anki A3]: <why>   # only if you did not apply an item
```
