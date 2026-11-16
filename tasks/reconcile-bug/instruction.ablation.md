# Payment transaction reconciliation

Repair the Python command-line program at `/app/reconcile.py`.

## Input

The program receives one positional argument: the path to a UTF-8 CSV file. The CSV has these columns:

- `tx_id`: transaction identifier
- `timestamp`: ISO-8601 timestamp containing a timezone (`Z` or an explicit UTC offset)
- `amount`: decimal transaction amount
- `status`: transaction state

The program must write one JSON object to standard output. It must not require an output-file argument.

## Business rules

1. Reconcile duplicate records by `tx_id`. Keep the record with the latest instant in time, comparing timestamps after conversion to UTC. When two records for the same ID represent the same instant, the later row in the CSV wins.
2. Normalize status values by trimming surrounding whitespace and comparing case-insensitively.
3. After deduplication, include only `VALID` records in `total_valid_amount` and `valid_count`.
4. After deduplication, count `FAILED` records in `failed_count`. `PENDING` records contribute to neither count nor amount.
5. Parse monetary values as decimal amounts and round the final valid total to two decimal places using conventional half-up rounding.
6. Ignore individual malformed records (for example, missing identifiers, invalid timestamps, timestamps without a timezone, invalid amounts, or unknown statuses). If the input file cannot be read or the required CSV headers are missing, exit with a non-zero status and write a useful error to standard error.

## Output

Write a JSON object with exactly these keys:

- `total_valid_amount`: number rounded to two decimal places
- `valid_count`: integer number of winning `VALID` transactions
- `failed_count`: integer number of winning `FAILED` transactions

The output must be deterministic for the same input. Do not print diagnostics to standard output.

## Additional example (the only ablation change)

For example, running `python /app/reconcile.py /app/sample_transactions.csv` should print a JSON object to the terminal, not write to a second output path. This example clarifies the intended command-line interaction; the sample path is illustrative and is not guaranteed to exist in the container.


## Execution guidance

- You have four responses in total, so plan them: (1) read the program once with `sed -n '1,120p' /app/reconcile.py`; (2) write the corrected program in one command; (3) verify it; (4) use any remaining response to repair a failure.
- Keep every response small: at most about 450 output tokens. This run allows 1,000 output tokens per minute and reserves your whole completion budget on each request, so a single enormous response is truncated before it finishes. If a write is cut off, use your next response to append the remainder.
- Keep the payload compact. Every command you issue is re-sent with the next request, so write only what is needed and never repeat source you have already sent.
- Verify with one command that compiles the program and runs a single concise CSV test covering deduplication, status filtering and timezone comparison.
- The verifier scores the file as it stands when your last response ends; return `task_complete: true` as soon as the checks pass rather than inspecting further.
