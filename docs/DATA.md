# Data files

The ZIP of a survey (studio: "Download all data", server: `manage.sh export-data ID FOLDER`) holds:

| File | Content |
|---|---|
| `survey.json` | the survey bundle as it stands at export |
| `description.json` | format `cardsurveys-export-1`, the name and version of the system that wrote the export, export time, survey title, languages, revision, a description of every file, and the codebook: every question with its options, every block task with items, blocks, anchor, gate question, variants and reference orders, every randomizer with arms and strata |
| `responses.csv` | one row per response: `response_uuid`, `status` (`started`, `submitted`, `withdrawn`, `declined`), `language`, `started_at`, `submitted_at`, `retest_submitted_at` (UTC, ISO 8601), `revision` (survey revision at the start of the response), `<randomizer>_arm` and `<randomizer>_stratum` for each randomizer, then one column per question and per choice module (several selected options joined by `;`) |
| `answers.csv` | `response_uuid`, `occasion`, `module_key`, `name`, `value` (JSON text) |
| `blocks.csv` | one row per block screen: `response_uuid`, `occasion`, `module_key`, `technique` (`sob` or `tap`), `variant`, `position` (screen order, from 0), `design_block` (index of the block in the design), `repeat_of` (design block repeated on this screen), `attention`, `attention_passed`, `cards` (cards in display order, joined by `|`), `result` (tap: the cards in tapped order as JSON, ending at the anchor when the anchor closes the block, so the cards of `cards` missing from `result` lie below the anchor and are tied; sob: the level, from 0 at the bottom, or `side` per card), `gate_value`, `duration_ms`, `events` (JSON list of taps `[card, ms]`, `undo`, `reset` and `auto`, the anchor placed after the last card) |
| `pairs.csv` | pair observations of block screens (attention blocks excluded): `response_uuid`, `occasion`, `module_key`, `variant`, `position`, `item_a`, `item_b`, `relation` (`a_prec_b`: item_a before item_b; `b_prec_a`; `incomparable`; `tie`: both left untapped below an anchor that closed the block) |
| `screens.csv` | `response_uuid`, `occasion`, `module_key`, `screen_key` (`module:step:occasion`), `first_shown_at`, `submitted_at`, `client_ms` (time on the page measured in the browser, summed over visits), `visits`, `question_order` (a form with `shuffle_questions`: the names of the questions in the order shown, joined by `|`), `leaves`, `away_ms` and `links` (a screen with `paradata`: the number of times the page was left, the time away from the page in milliseconds, and the links opened as a JSON list `[address, ms]`) |
| `allocations.csv` | `randomizer_key`, `stratum`, `seq_no` (position in the stratum's sequence), `arm`, `response_uuid` (empty after a withdrawal), `created_at` |
| `boards/<module>/` | for each board task: `study.json` (format, elements with codes and labels, board kind and rows, class `po` or `eq`, pair kind `prec` or `sim`, relation, confirmation, retest, random order), `responses.csv`, `placements.csv` (`placements_json` keyed by element position from 0: tier boards `{"0": 0, "1": "aside"}`, arrow board `{"arrows": [[0, 1]]}`, pile board `{"0": "p0"}`, plane board `{"0": [x, y]}`, pairwise questions `{"0,1": "a" | "b" | "apart" | "undecided"}`), `judgments.csv` (`a_prec_b`, `b_prec_a`, `apart`, `tie`, `undecided`), `confirmations.csv` (`unrelated` or `refused`) |

Times are in UTC. Preview responses are never exported. Withdrawn responses keep only their identifier and status.

## Reading tap-order blocks with an anchor

For a respondent and a task, each item meets the anchor in r blocks (for the design `v8_k4_lambda3`, r = 7). The item stands above the anchor in a block when it was tapped before the anchor card; in a task whose anchor closes the block, an item left untapped stands below the anchor. With an odd r the majority of the r comparisons never ties. Each pair of items meets in λ blocks (λ = 3 for `v8_k4_lambda3`), so every pair has λ observations per respondent in `pairs.csv`, and their agreement measures the consistency of the respondent's order. A pair recorded as `tie` stands below the anchor in that block, and the share of blocks in which item_a precedes item_b counts a tie as one half.

## Example exports

`docs/examples/` holds the exports of three demonstration surveys (`sob`: Subjective Order Blocks on the Fano plane; `tap`: tap-order blocks with an anchor card, a gate question, a repeated block and an attention block; `arrow`: the arrow board with confirmation questions), each answered by 40 simulated respondents who hold one of a few declared views and answer with some noise. `tools/example_exports.py` regenerates them in a fresh installation with a temporary database:

```sh
.venv/bin/python tools/example_exports.py --out docs/examples --respondents 40 --seed 20261117
```

The identifiers and times differ between runs; the answers follow the seed.
