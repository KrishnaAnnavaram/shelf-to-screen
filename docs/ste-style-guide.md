# The writing standard: ASD-STE100 Simplified Technical English

Use these rules for the `README.md` of shelf-to-screen and for this file. Section 3 gives the project
vocabulary. Each term in Section 3 has one meaning in all of the documentation.

## 1. The writing rules

### Words

1. Use one word for one meaning, and one meaning for one word. Do not use synonyms for variety.
2. Use a word only as one part of speech. For example, `test` is a noun or a verb, `check` is a verb.
3. Do not use phrasal verbs (`set up`, `carry out`, `find out`, `pick up`, `look up`, `come up with`).
   Use one verb: `prepare`, `do`, `find`, `get`, `make`.
4. Do not use an `-ing` form as a noun or an adjective (`the running job`, `after indexing`).
   Exception: a technical name, a file name, a command or a status value.
5. Do not use contractions (`don't`, `it's`, `can't`). Do not use slang or idioms
   (`out of the box`, `under the hood`, `at a glance`, `gotcha`, `bells and whistles`).
6. Do not use `and/or`. Write `A, B or both`.
7. Do not use `should`, `could`, `would` or `may` for instructions. Use `must` for a rule, the
   imperative for a step and `can` for a possibility.
8. Keep the articles `a`, `an` and `the` in sentences.
9. Do not make a noun cluster of more than three words. A technical name is one word.

### Sentences

1. A procedural sentence (an instruction) has a maximum of **20 words**.
2. A descriptive sentence has a maximum of **25 words**.
3. Write one instruction in one sentence.
4. Use the imperative for an instruction: `Run the tests.` Not `The tests should be run.`
5. Use the active voice. Use the passive voice only when the agent of the action is not important.
6. Use only the simple present, the simple past and the simple future.
7. Put a condition before the instruction: `If the index is stale, build it again.`
8. Do not use semicolons in sentences. Write two sentences.

### Paragraphs, notes and warnings

1. A paragraph has one topic and a maximum of **6 sentences**. Start with the topic sentence.
2. A warning or a caution starts with a clear command. Then it gives the reason.
3. A note gives information. It does not give an instruction.
4. Use a vertical list for a sequence or a set of conditions. Each item of a numbered procedure is one step.

### Tables, headings and diagrams

1. A table cell can be a short phrase. If a cell has a sentence, the sentence obeys the rules.
2. A heading is a noun phrase (`The cost model`) or an imperative (`Run the demo`).
   Do not start a heading with an `-ing` form.
3. A diagram label is a short phrase. Use the same terms as the text.

### What STE does not change

Code, commands, file names, paths, field names, environment variables, status values, enum values,
product names and URLs stay exactly as they are. They are technical names. Put them in backticks.

## 2. General words to replace

| Do not use | Use |
|---|---|
| utilize, leverage | use |
| in order to | to |
| set up | prepare, install, configure |
| carry out, perform | do |
| make sure, ensure | make sure (allowed), or `check that` |
| a lot of, lots of | many, much |
| e.g., i.e. | for example, that is |
| should (instruction) | must (rule) / imperative (step) |
| might, may (possibility) | can |
| very, really, just, simply, easily | (delete) |
| seamless, robust, powerful, blazing | (delete or give a measured fact) |

## 3. Project vocabulary

These terms have one meaning in the shelf-to-screen documentation. The code names are in backticks.

### 3.1 Technical names (nouns)

| Term | Meaning | Do not use |
|---|---|---|
| **yearly file** | One statistics export, for example `2021LibraryDataset.csv` | dataset (alone), sheet |
| **reporting year** | The year in the name of a yearly file (`file_year`) | fiscal year (for this), period |
| **fiscal year** | The local fiscal year of a library, from `fy_start` to `fy_end` | reporting year, calendar year |
| **header map** | `HEADER_MAP`: raw header to short column name | rename dictionary |
| **branch row** | A row with a name and no statistics except service hours | sub-library, outlet |
| **summary row** | A row with no name, for example a state total | totals line, footer |
| **library ID** | `library_id`: the normalised name and city, linked by phone | key, code |
| **phone link** | Two library IDs joined because they share a phone in one city | merge, match |
| **panel** | The table with one row for each library and reporting year | merged dataset, long table |
| **balanced panel** | The libraries that report in every year | complete cases, fixed set |
| **state total** | The sum of a column over the libraries of one year | aggregate, grand total |
| **per-capita value** | A value divided by the legal service area population | rate, ratio |
| **digital share** | Digital circulation divided by physical plus digital circulation (all other ages) | e-share, digital ratio |
| **backtest** | One-step-ahead forecasts from each origin year, with errors | validation (alone), test fit |
| **fixed effects** | Library and year means removed before the regression | dummies, controls |
| **pooled OLS** | A regression with no fixed effects, for comparison | naive regression |
| **indicator** | A yearly external digital-reading series | proxy (for a valid series), driver |
| **report folder** | The folder with `report.md`, CSV tables and `regression.json` | output, results |

### 3.2 Technical verbs

| Verb | Meaning |
|---|---|
| **ingest** | Read the yearly files into typed rows with a report |
| **link** | Join two library IDs by phone and city |
| **total** | Add a column over the libraries of each year |
| **backtest** | Forecast each year from the earlier years only and measure the errors |
| **regress** | Fit the fixed-effects regression with clustered errors |
| **flag** | Mark a value or a change for a manual check, with no change to the value |
