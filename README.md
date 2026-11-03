# anki-card-generate

A Claude Code skill that turns a source — pasted text, a file, a URL, a PDF, a
Jira ticket or a Confluence page — into Anki cards you can import in one step.

One agent writes the cards and separate agents check them against the general
Anki rules and your own rules. Cards that fail get rewritten, for up to 3
rounds. Cards that still fail after the last round are left out, so everything
in the file you import has passed every check.

## Install

In Claude Code:

```
/plugin marketplace add jap963852741/anki-card-generate
/plugin install anki-card-generate@anki-card-generate
```

Update later with `/plugin update`.

Without the plugin system, copy `skills/anki-card-generate/` to
`~/.claude/skills/anki-card-generate/` and restart Claude Code.

You also need `python3` (standard library only) and the
[Anki](https://apps.ankiweb.net/) desktop app to import the result.

## Usage

Ask in plain words. Give it a source and a card count:

```
Make 10 anki cards from https://en.wikipedia.org/wiki/Photosynthesis
```

```
幫我把 ~/notes/tcp.md 做成 15 張 anki 卡，deck 叫 Network::TCP
```

```
Generate 20 anki cards from pages 30-45 of ~/books/ddia.pdf.
Rules: write in Traditional Chinese; at least 5 cloze cards; every card tagged "ddia-ch3".
```

```
Turn PROJ-123 into 8 anki cards
```

If you leave out the card count, Claude asks for it. If the source is very long
(over about 20k words) and you didn't say which part to use, Claude asks which
section.

### Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
| source | yes | — | Text, file path, URL, PDF (with pages), Jira key, Confluence URL |
| number | yes | — | Exact number of cards to aim for |
| custom rules | no | none | Anything you want enforced: language, card type mix, tags, wording style. Each sentence becomes one rule (`R1`, `R2`, …) |
| deck | no | Anki's current deck | Use `::` for sub-decks, e.g. `Biology::Cells` |
| max rounds | no | 3 | How many times failing cards are rewritten |
| output path | no | `~/Downloads/anki/<slug>-<YYYYMMDD>.tsv` | |

Custom rules override the general Anki rules where they conflict. For example,
"answer with the full definition" is allowed even though the general rules
prefer short answers.

## What you get

1. A `.tsv` file at the output path.
2. A table of the cards in the chat.
3. A short report: how many rounds it took, and — if any cards were left out —
   which ones and why. The deck can have fewer cards than you asked for; Claude
   does not add extra cards to make up the number.

### Importing into Anki

Anki → **File → Import** → pick the `.tsv`. The header lines in the file
already set the separator, the note type (Basic or Cloze) and the tags, so
there is nothing to map by hand.

If Anki says the note type was not found, your Anki uses different names for
the note types (for example in another UI language). Look them up in
**Tools → Manage Note Types**, then ask Claude to re-export with those names,
or run the export yourself (`<skill folder>` is where the plugin or your copy
installed this skill; `find -L ~/.claude -path '*anki-card-generate/SKILL.md'`
shows it):

```bash
python3 <skill folder>/scripts/cards.py export \
  <work folder>/cards-N.jsonl out.tsv --basic-name "<your Basic name>" --cloze-name "<your Cloze name>"
```

## How it works

```
 source  ─┐
 number  ─┼─▶ generator ─▶ structural check ─▶ anki validator  ┐ ─ pass ─▶ .tsv
 rules   ─┘       ▲                            custom validator ┘
                  │                                  │ fail
                  └──────── handoff-N.md ◀───────────┘
```

Paths below are under `skills/anki-card-generate/`.

| Step | Who | Defined in |
|---|---|---|
| Write cards | generator agent | `prompts/generator.md` |
| Structural check: count, fields, cloze syntax, no edits to cards that already passed | `cards.py check` | `scripts/cards.py` |
| Check against general Anki rules (one fact per card, no yes/no, no lists, …) | anki validator agent | `prompts/anki-validator.md`, `anki-rules.md` |
| Check against your rules (only if you gave any) | custom-rules validator agent | `prompts/custom-rules-validator.md` |
| Merge failures into a fix list for the next round | `cards.py handoff` | `handoff-spec.md` |
| Write the Anki file, leaving out cards that still fail | `cards.py export` | `scripts/cards.py` |

A few rules keep the loop honest:

- **The checkers are separate agents from the writer.** They see only the
  source, the cards and the rules — never the writer's explanation — and a
  fresh pair runs every round.
- **The fix list is built by a script, not written by hand**, so no failure
  gets dropped or reworded on the way back.
- **Cards that passed are locked.** In the next round the writer may change
  only the cards on the fix list; the script rejects any other edit.
- **Every card quotes the source sentence it is based on.** Facts that are not
  in the source fail the check.

## Working files

Each run writes its drafts to the session scratchpad, under
`.anki-card-generate/<slug>-<timestamp>/`. Look there if a result surprises
you:

| File | What it is |
|---|---|
| `source.md` | The text the cards were made from |
| `request.md` | Card count, deck, language, your rules as `R1`, `R2`, … |
| `cards-N.jsonl` | Cards after round N |
| `review-N-anki.json`, `review-N-custom.json` | What each checker found in round N |
| `handoff-N.md` | The fix list sent to round N+1 |

## Changing the rules

- **For one run:** put the rule in your request ("Rules: …").
- **For every run:** edit `skills/anki-card-generate/anki-rules.md`. Give a new rule the next id (`A11`,
  `D5`) and a "Fails when" line; the checker cites rules by id.

## Limits

- One run is meant for one chapter or article, not a whole book.
- Cards are plain text. No images, audio or formatting.
- The checkers are AI agents, so they are not perfectly consistent: a card
  that passed in one round can be flagged in the next. The 3-round limit and
  leaving out failing cards stop this from looping forever, but it can cost a
  card or two.
