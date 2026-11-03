# General Anki rules

Condensed from Wozniak's "20 rules of formulating knowledge". They apply to any subject. Validators cite the rule id.

## Per card

| Id | Rule | Fails when |
|---|---|---|
| A1 | Faithful to source | The back says something the source does not support, or contradicts it |
| A2 | One fact per card | A complete answer needs two or more independent facts |
| A3 | Short answer | The back is a paragraph. Aim for a word or a phrase; one sentence at most |
| A4 | No lists | The answer is a list of 3 or more items. Split into one card per item, or cloze each item separately |
| A5 | One right answer | Someone could answer the front correctly with something other than the back |
| A6 | Stands on its own | The front only makes sense next to the source: it says "it", "this", "the above", or leaves out which subject it is about. Name the subject on the front |
| A7 | No yes / no | The front can be answered with yes, no, true or false |
| A8 | No giveaway | The answer, or an obvious form of it, appears on the front |
| A9 | Cloze hides what matters | The deletion is a filler word that anything could replace, or so much is deleted that nothing is left to cue the answer |
| A10 | Meaning over wording | The card asks to recall a sentence word for word instead of a fact, a cause, or a relation |

## Deck level

| Id | Rule | Fails when |
|---|---|---|
| D1 | Coverage | A main point of the source has no card while a minor detail does |
| D2 | No duplicates | Two cards test the same fact |
| D3 | No mix-ups | Two cards have almost the same front but different answers, and nothing on the front tells them apart |
| D4 | Count | The number of cards is not the number asked for |

## Examples

| Bad | Rule | Better |
|---|---|---|
| Q: What are the three states of matter? A: Solid, liquid, gas | A4 | Cloze: `The three common states of matter are {{c1::solid}}, {{c2::liquid}} and {{c3::gas}}.` |
| Q: Did the French Revolution begin in 1789? A: Yes | A7 | Q: In what year did the French Revolution begin? A: 1789 |
| Q: When was it signed? A: 1215 | A6 | Q: In what year was the Magna Carta signed? A: 1215 |
| Q: What does photosynthesis produce from light? A: Products of photosynthesis: glucose and oxygen | A8, A2 | Q: Which gas do plants release during photosynthesis? A: Oxygen |
| Cloze: `Paris {{c1::is}} the capital of France.` | A9 | Cloze: `{{c1::Paris}} is the capital of France.` |
