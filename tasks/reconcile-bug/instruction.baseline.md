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


## Execution guidance

- Keep every response small: aim for at most about 350 output tokens. This run allows 1,000 output tokens per minute and reserves your whole completion budget on each request, so a single enormous response is truncated before it finishes.
- Repair the program with targeted edits. Inspect only the lines you need (`sed -n '1,40p' /app/reconcile.py`), then change just the broken logic with a short `python - <<'PY'` edit.
- If the file must be rewritten wholesale, do it in at most two parts (write, then append the remainder) rather than one very long command.
- Keep terminal output small. Do not print the whole source file.
- Verify with `python -m py_compile /app/reconcile.py` and one concise CSV test covering deduplication, status filtering, and timezone comparison.
- Set `duration` to at least 60 on every command so consecutive model responses stay a minute apart; that spacing is what keeps this run inside the per-minute budget.
- When the implementation passes the checks, return `task_complete: true` rather than continuing with extra inspection.
