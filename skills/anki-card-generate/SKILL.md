---
name: anki-card-generate
description: Use when the user gives a source (pasted text, a file, a URL, a PDF, a Jira / Confluence page) and asks to turn it into Anki cards / flashcards ("generate anki cards", "make flashcards from this"). Inputs are source, number of cards, and optional custom rules. Loops a generator agent → validator agents (Anki-rules validator always, custom-rules validator only when custom rules are given, in parallel); on any fail `cards.py handoff` builds handoff-N.md from the validators' JSON reviews and the generator re-generates only what it names. Max 3 rounds by default; cards still failing after the last round are left out of the output. Delivers an Anki-importable TSV. Optional args: deck, max rounds (default 3), output path.
---

# anki-card-generate

```
            ┌──────────────┐
 source  ─┐ │              │      ┌─────────────────────────────────────┐
 number  ─┼─┤  generator   ├─────▶│ anki-validator │ custom-validator   │──success──▶ export .tsv
 rules   ─┘ │              │      │  (always)      │ (only if rules)    │
            └──────▲───────┘      └───────────────────┬─────────────────┘
                   │ re-generate                      │ fail
                   └───────────── handoff-N.md ◀──────┘
                                  (cards.py handoff)
```

The main thread is only the orchestrator: it prepares inputs, dispatches
agents, runs `cards.py`, and decides the next step from exit codes. It does not
write cards, judge cards, or write handoffs.

| Box | File |
|---|---|
| generator | `prompts/generator.md` |
| anki-rules validator | `prompts/anki-validator.md` + `anki-rules.md` |
| custom-rules validator | `prompts/custom-rules-validator.md` |
| handoff.md | `handoff-spec.md` (format, who writes it, generator obligations) |
| structural check, handoff, export | `scripts/cards.py` (stdlib only) |

Generator and validators are separate agents on purpose: validators read only
the source, the cards and the rules — never the generator's change log or the
previous handoff — so they are not anchored on the generator's story. Every
round gets fresh agents.

## 0. Setup

Work folder `WORK_DIR` = `<scratchpad>/.anki-card-generate/<slug>-<YYYYMMDD-HHMMSS>/`
(session scratchpad; `/tmp` only if there is none). Not the current repo —
drafts are throwaway.

Resolve once; every placeholder below is an absolute path:

| Placeholder | Value |
|---|---|
| `{skill_dir}` | The "Base directory for this skill" shown when this skill loaded. Not shown → `dirname` of the first hit of `find -L ~/.claude -path '*anki-card-generate/SKILL.md' 2>/dev/null`. Never assume a fixed path: plugin and manual installs live in different places |
| `{cards_py}` | `{skill_dir}/scripts/cards.py`, run with `python3` |
| `{anki_rules}` | `{skill_dir}/anki-rules.md` |
| `{handoff_spec}` | `{skill_dir}/handoff-spec.md` |
| `{work_dir}` | `WORK_DIR` |

## 1. Inputs

| Input | Required | Notes |
|---|---|---|
| source | yes | Fetch per table below; write extracted text to `source.md` |
| number | yes | Exact card count. Missing → ask once; do not guess |
| custom-rules | no | Verbatim from the user |
| deck | no | Anki deck name for the `#deck:` header |
| max rounds | no | Default 3 |
| output path | no | Default `~/Downloads/anki/<slug>-<YYYYMMDD>.tsv` |

| Source | Fetch |
|---|---|
| Pasted text / file | as is |
| URL | WebFetch; keep the article body, drop nav / ads |
| PDF | Read with `pages`; only the pages the user named if it is long |
| Jira key / Confluence URL | `getJiraIssue` / `getConfluencePage`, only the part the user named |

Source over ~20k words and no section named → ask which part. One deck
should not try to cover a book.

Write `request.md`:

```markdown
# Request
- number: 10
- deck: Biology::Cells        # or "none"
- language: zh-TW             # = source language unless a custom rule says otherwise

## Custom rules
- R1: <user's rule, verbatim>
- R2: <user's rule, verbatim>
```

One user sentence = one rule id. No custom rules → the section says `none`.
Validators and the handoff cite these ids, so do not renumber them later.

## 2. Loop (round N = 1 … max rounds)

### 2a. Generate

Dispatch `prompts/generator.md` with `{round}` = N, `{prev}` = N−1,
`{number}`, and the paths from Setup.

### 2b. Structural check

Re-run it yourself — do not trust the generator's "OK":

```bash
python3 {cards_py} check {work_dir}/cards-N.jsonl --count {number} \
  [--prev {work_dir}/cards-<N-1>.jsonl --handoff {work_dir}/handoff-<N-1>.md]   # round 2+
```

Round 2+ also fails if a card under "Keep unchanged" was changed or dropped
without a Deck-level item naming it.

Exit 1 → skip 2c, run 2d with no `--review`. A wrong count or broken cloze is
cheaper to fix than to review.

### 2c. Validate (parallel)

Send both Agent calls in one message:

- `prompts/anki-validator.md` — always.
- `prompts/custom-rules-validator.md` — only if `request.md` has custom rules.

Round 2+: a card identical to last round's passed then and is locked — it is
not judged again, so a fresh validator cannot flip a card that already passed.
Fill `{review_ids}` with the cards that are new or changed:

```bash
python3 {cards_py} changed {work_dir}/cards-N.jsonl --prev {work_dir}/cards-<N-1>.jsonl
```

### 2d. Handoff

```bash
python3 {cards_py} handoff {work_dir}/cards-N.jsonl --count {number} --round N \
  --out {work_dir}/handoff-N.md \
  --review {work_dir}/review-N-anki.json [--review {work_dir}/review-N-custom.json] \
  [--prev {work_dir}/cards-<N-1>.jsonl]   # round 2+
```

With `--prev`, findings on locked cards are dropped and listed under
"Ignored" in the handoff, so they never send a card back.

| Exit | Next |
|---|---|
| 0 PASS | Go to 3 |
| 1 FAIL | N < max rounds → 2a with N+1. N = max rounds → go to 3; failing cards are left out |
| 2 broken review | Re-dispatch that validator once with the error message; still broken → stop and show the user |

Never edit `handoff-N.md` by hand, and never drop or loosen a rule to pass.

## 3. Deliver

```bash
python3 {cards_py} export {work_dir}/cards-N.jsonl <output path> [--deck "<deck>"] \
  [--handoff {work_dir}/handoff-N.md]   # only if the last round was FAIL
```

`--handoff` leaves out every card under its "Cards to fix": a card that still
breaks a rule after the last round is not worth importing. The deck then has
fewer cards than asked; say so, do not top it up.

If the last round failed the structural check, export round N−1 with
`handoff-<N-1>.md` instead (round 1 → nothing to export; tell the user).

Show the user:

1. The output path and how to import: Anki → File → Import → pick the file.
   The header lines set separator, note type and tags; nothing to map by hand.
2. All exported cards as a table (`id | type | front | back`) if ≤ 20, else
   the first 10 plus the count.
3. Rounds used. If stopped at max rounds: `<exported> of <number>` cards, each
   left-out card with its handoff items, the Deck-level items still open, and
   any items the generator skipped with its reason.
4. Three sections: what was made, what was verified (structural check +
   which validators passed in which round), what was not done.

## Common mistakes

| Mistake | Fix |
|---|---|
| Main thread writes or tidies the handoff | Only `cards.py handoff` writes it; see `handoff-spec.md` |
| Generator rewrites cards that already passed | `check --prev --handoff` fails it; "Keep unchanged" is byte for byte |
| Still-failing cards end up in the TSV | Export with `--handoff handoff-N.md` when the last round was FAIL |
| Validator given the change log or last handoff | Validators get only cards, source, rules — they judge cards fresh |
| A fresh validator flags a card that passed last round | Round 2+: pass `{review_ids}` from `cards.py changed`, and `--prev` to `handoff` so findings on locked cards are ignored |
| Anki validator flags what a custom rule asked for | It reads `request.md`; custom rules win on conflict |
| Custom-rules validator spawned with no custom rules | Only when `request.md` has custom rules |
| Trusting the generator's "check passed" | Main thread re-runs `cards.py check` |
| Cards built from outside knowledge | Every card carries a verbatim `source` quote |
| Import says note type not found | Note types are localized; pass `--basic-name` / `--cloze-name` with the names in Tools → Manage Note Types |
