# Survey bundle format (`cardsurveys-bundle`, version 1)

A bundle is one JSON object with four keys:

```json
{
  "format": "cardsurveys-bundle",
  "version": 1,
  "survey": { ... },
  "modules": [ ... ]
}
```

Every text a respondent sees is a translation object, a map from language code to text: `{"pl": "Dalej", "en": "Next"}`. Longer texts accept light markup: a blank line starts a paragraph, lines starting with `- ` form a list, `**bold**`, `*italic*`, and web addresses become links. Everything else is shown as plain text.

## `survey`

| Key | Meaning |
|---|---|
| `title`, `description` | translation objects; the description appears above the consent text |
| `languages` | language codes of the survey, for example `["pl", "en"]` |
| `default_language` | one of `languages` |
| `detect_browser_language` | choose the respondent's language from the browser (default true) |
| `allow_language_switch` | show the language switch (default true) |
| `retest` | the survey has a second session (modules marked `"retest": true` are repeated) |
| `slug` | link code (only in exported bundles; import gives a new code unless asked to keep it) |

## Common keys of every module

`key` (unique code, letters, digits and `_`), `type`, `title` (translation object, optional), `condition` (optional, see below), `retest` (optional).

## Module types

**consent**: `text`; optional `agree_label`, `decline_label`. Declining ends the survey and stores nothing.

**info**: `text`.

**form**: `intro` (optional) and `questions`, each with `name` (unique in the survey), `type` (`text`, `textarea`, `number`, `select`, `radio`, `checkbox`, `yesno`), `label`, optional `help`, `required`, `options` (`[{"value": "...", "label": {...}}]` for `select`, `radio`, `checkbox`), `min` and `max` for numbers, and `condition`.

**board**: `relation` (a full clause, for example "one must be settled before the other"), `kind` (`tier`, `tier_aside`, `arrow`, `pile`, `plane`, `pairs`), `rows` (tier boards), `elements` (2 to 8 cards `{"code", "label"}`), `confirm_critical` (arrow board: ask whether blank pairs are unrelated), `randomize_order`, optional `instructions`.

**sob_blocks** (Subjective Order Blocks): `relation`, `items`, and either `design` (a key such as `v8_k4_lambda3`) or `blocks` (lists of item codes); optional `instructions`, `side_label`, `shuffle_blocks`, `shuffle_cards`.

**tap_blocks** (tap-order blocks): `criterion` (the sentence shown above every block), `items` with `design` or `blocks`, and optionally `instructions` (shown above the first block of the task) and:

| Key | Meaning |
|---|---|
| `anchor` | a card `{"code", "label"}` added to every block and shown last |
| `anchor_closes` | `true`: tapping the anchor ends the block; the cards left untapped lie below the anchor, tied with one another, and the anchor is placed after the last card when every other card is tapped (default `false`: every card is tapped) |
| `anchor_note` | a sentence shown under the criterion on every block, for the meaning of the anchor card in the task |
| `gate` | a question after every block: `{"question": {...}, "options": [{"value", "label"}]}` |
| `duplicates` | number of design blocks shown a second time, later in the sequence |
| `attention` | number of attention blocks: a design block with an extra card (`attention_label`) to be tapped last |
| `attention_position` | `last` (default) or `first`: where the extra card of an attention block has to be tapped; beside an anchor that closes the block, the anchor is left out of the count |
| `practice` | the task is a practice task |
| `reference_order` | the correct order as tiers of item codes, first tier best |
| `variants_by`, `variants` | an earlier answer that chooses the item set: `{"value": {"items", "design" or "blocks", "reference_order", "criterion"}}`; the variant `"*"` serves every other value |
| `shuffle_blocks`, `shuffle_cards` | random block order and card order (default true); the anchor is always last |

Designs available: every verified design of the library (for example `v7_k3_lambda1`, the Fano plane; `v8_k4_lambda3`; `v9_k3_lambda1`; `v10_k4_lambda2`; `v13_k4_lambda1`). The studio lists them with v, k, λ, r and b.

**randomizer**: `arms` (`[{"code": "L", "weight": 1}, ...]`), `strata_by` (names of earlier closed questions), `block_multiplier` (permuted blocks hold every arm weight × multiplier times). No screen; the arm is stored with the response.

**stimulus**: `contents` by arm and stratum: `{"L": {"*": {...}}, "G": {"hum": {...}, "*": {...}}}`; `arm_of` (the randomizer), optional `stratum_by` (an earlier answer) and `prompt`. Arms without content skip the module.

**choice**: `prompt`, `options` (`{"value", "label", "preview"}`), `contents` by option and stratum (as in stimulus), optional `stratum_by`. The respondent chooses an option and then sees its content; the choice is stored as an answer named after the module key.

**debrief**: `text`; optional `stratum_by` with `texts` by stratum; `offer_withdrawal` (default true).

**thanks**: `text`; `show_retest_link` when the survey has a second session.

## Conditions

A condition shows a module or a question only when it holds:

```json
{"answer": "level", "op": "eq", "value": "phd"}
{"arm": "assignment", "op": "in", "value": ["L", "G"]}
{"all": [ ... ]}   {"any": [ ... ]}   {"not": { ... }}
```

Operators: `eq`, `ne`, `in`, `not_in`, `answered`, `empty`. A condition may name only answers and randomizers of earlier modules (or earlier questions of the same form).

## Checks

Import and saving refuse a bundle with errors: unknown or repeated codes, conditions naming unknown answers, blocks that name unknown items, designs that do not fit the number of items, a reference order that does not list every item once. Publishing also requires every text in every survey language. Warnings (shown in the studio) cover even λ (majority readings can tie), block sizes outside the usual range, strata on open questions, and a consent module that is not first.
