# Version observations

`versions.csv` contains 912 observations: 216 primary, 288 historical, 189 for
each new editing configuration, and 30 additional extension versions. The
primary prefix of each extension is reconstructed by task and repeat during
analysis. `step=0` denotes initial generation; positive steps are revisions.
`repeat` is zero-based.

| Fields | Definition |
|---|---|
| `cohort`, `task`, `repo`, `repeat`, `step` | Version identity and clustering |
| `hash` | SHA-256 of the resulting patch text |
| `score` | Sum of the two visible check passes, from 0 to 2 |
| `ordinary_pass`, `issue_pass` | Visible checks: start and pass markers plus zero exit status |
| `success` | Original strict independent-test result; 1 only when all required tests are observed passing |
| `complete` | Whether all required independent test results were observed |
| `status` | Later audit classification: `pass`, `observed_nonpass`, or `undetermined` |
| `required_failures` | Number of required tests marked FAILED or ERROR |
| `tokens`, `prompt_tokens`, `completion_tokens` | Provider-reported total, input, and output tokens for this call |
| `valid` | Whether the editing operation was accepted |
| `changed` | Whether patch text differs from the previous retained version; initial generation is compared with the empty patch |
| `matcher_fallback_used` | Whether the matching fallback was successfully used for this proposal |
| `grade`, `source_record` | Paths relative to the original project root, for locating material in the full archive |

Boolean fields are stored as 0/1. The original `success` and `complete` fields
are kept separately from `status`. An incomplete evaluation with a recorded
failure/error for a required test is an observed nonpass. An import/collection
problem without a decisive required-test outcome remains undetermined. This
classification identifies the recorded outcome, not whether the patch or the
environment caused the error.

Stopping and output decisions use visible score and patch identity; invalid
edit controls also use `valid`. They never use independent-test `success` or
`status`. Tokens are summed through the stopping point, including invalid edits.

`provenance.json` records the digest of this CSV and the hashes of the 6,267
source files checked during export. These are source-relative identifiers, not
download links. They support comparison with the full archive but cannot replace
access to the raw files. No prompts, repository code, generated patch text,
credentials, machine-specific absolute paths, or test logs are included in this
CSV.
