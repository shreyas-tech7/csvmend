# Demo transcript

A real terminal session from 2026-11-21, run in an empty folder after `./init.sh` and `source .venv/bin/activate`. Nothing below was edited by hand. The first command cleans the small built-in demo table. The rest walk one generated orders file through every step.

```text
$ csvmend demo
BEFORE (messy input, first 6 rows)
customer_id | Name | email | Phone Area | phone_line | signup_date | city | Segment | lifetime_value
C00001 | 	Ben Clark |   ben.clark36@mail.test | 	306 | 555-8589 | 2023-09-13 | Dallas | Onnline | $7,381.48
C00002 | Elena  Ã‡elik | elena.elik90@mail.test  | 670 | 555-7410 | 13 Jan 2025 | Chicago  | Wholeasle  | 5589.81
C09011 | 	elena Çelik | 	elena.elik90@mail.test | 670 | 555-7410 | 01/13/2025 | Chicago | Wholesale | 5589.81
C00003 | Grace Patel | grace.patel62@mail.test   | 680 | 555-8404  | 01/22/2024 | Seattle | ONLINE | $4,832.83
C00004 | Omar DuprÃ© |   omar.dupr84@mail.test | 755 | 555-4673 | 2024-04-05 | Denver | Online | 5109.84
C00005 | BjÃ¶rn Jones  | bjrn.jones89@mail.test | 769 | 555-8377 | Oct 02, 2023 | N/A | Online | $1,416.03

PLAN
1. rename: header names to snake_case
2. trim: stray whitespace or bad bytes
3. fill_missing: null words
4. merge_columns: rebuild phone
5. split_column: split name
6. parse_dates: mixed date formats
7. map_values: typos and case
8. normalize_currency: money formats
9. fuzzy_dedupe: near duplicate rows

RUN
step 1 rename: changed 3, failed 0, dropped 0
step 2 trim: changed 27, failed 0, dropped 0
step 3 fill_missing: changed 1, failed 0, dropped 0
step 4 merge_columns: changed 11, failed 0, dropped 0
step 5 split_column: changed 22, failed 0, dropped 0
step 6 parse_dates: changed 5, failed 0, dropped 0
step 7 map_values: changed 5, failed 0, dropped 0
step 8 normalize_currency: changed 4, failed 0, dropped 0
step 9 fuzzy_dedupe: changed 0, failed 0, dropped 1

AFTER (clean output, first 6 rows)
customer_id | first_name | last_name | email | phone | signup_date | city | segment | lifetime_value
C00001 | Ben | Clark | ben.clark36@mail.test | 306-555-8589 | 2023-09-13 | Dallas | Online | 7381.48
C00002 | Elena | Çelik | elena.elik90@mail.test | 670-555-7410 | 2025-01-13 | Chicago | Wholesale | 5589.81
C00003 | Grace | Patel | grace.patel62@mail.test | 680-555-8404 | 2024-01-22 | Seattle | Online | 4832.83
C00004 | Omar | Dupré | omar.dupr84@mail.test | 755-555-4673 | 2024-04-05 | Denver | Online | 5109.84
C00005 | Björn | Jones | bjrn.jones89@mail.test | 769-555-8377 | 2023-10-02 |  | Online | 1416.03
C00006 | Liam | Tanaka | liam.tanaka96@mail.test | 319-555-7710 | 2024-05-08 | Seattle | Enterprise | 3667.07

11 rows in, 10 out, 75 cell changes logged in changes.csv

$ csvmend generate --kind orders --seed 3 --out data --name orders
wrote data/orders.csv with its .truth.json and .schema.json

$ csvmend plan data/orders.csv --schema orders -o plan.json
$ cat plan.json | head -30
{
  "version": 1,
  "steps": [
    {
      "op": "rename",
      "mapping": {
        " quantity ": "quantity",
        "UNIT_PRICE": "unit_price",
        " weight_kg ": "weight_kg"
      },
      "why": "header names to snake_case"
    },
    {
      "op": "trim",
      "columns": "*",
      "unicode": false,
      "why": "stray whitespace or bad bytes"
    },
    {
      "op": "drop_rows",
      "where": {
        "ragged": true
      },
      "why": "rows with the wrong field count"
    },
    {
      "op": "fill_missing",
      "columns": "*",
      "tokens": [
        "-",

$ csvmend run data/orders.csv --plan plan.json --out out
step  1 rename             changed    3  failed   0  dropped   0
step  2 trim               changed   92  failed   0  dropped   0
step  3 drop_rows          changed    0  failed   0  dropped   4
step  4 fill_missing       changed   19  failed   0  dropped   0
step  5 split_column       changed  172  failed   0  dropped   0
step  6 parse_dates        changed   37  failed   0  dropped   0
step  7 map_values         changed   29  failed   0  dropped   0
step  8 normalize_currency changed   50  failed   0  dropped   0
step  9 convert_units      changed   41  failed   0  dropped   0
step 10 fuzzy_dedupe       changed    0  failed   0  dropped  11
90 rows in, 75 rows out, 466 log entries
wrote out/clean.csv, plan.json, changes.csv, run.json

$ csvmend verify out/clean.csv --schema orders --rows-in 90
16/16 checks pass
(exit 0)

$ head -6 out/changes.csv
step,op,kind,row,column,old,new
0,load,encoding,,*,cp1252,utf-8
0,load,ragged,4,*,"[""O00005"", ""C00055"", """", ""04/16/2024"", ""Furniture"", ""18"", ""$719.04"", ""42.25"", ""Miami, FL""]","[""O00005"", ""C00055"", """", ""04/16/2024"", ""Furniture"", ""18"", ""$719.04"", ""42.25""]"
0,load,ragged,8,*,"[""O00009"", ""-"", ""2024-09-17"", ""office supplies"", ""5"", ""902.91"", ""13.59 kg"", """", ""Austin, TX""]","[""O00009"", ""-"", ""2024-09-17"", ""office supplies"", ""5"", ""902.91"", ""13.59 kg"", """"]"
0,load,ragged,63,*,"[""O00057"", ""C00265"", """", ""Mar 05, 2023"", ""Clothing"", ""17"", ""572.66"", ""9.47"", ""Chicago, IL  ""]","[""O00057"", ""C00265"", """", ""Mar 05, 2023"", ""Clothing"", ""17"", ""572.66"", ""9.47""]"
0,load,ragged,64,*,"[""O00058"", ""C00322"", ""2024-09-09"", ""null"", ""5"", ""800.62"", """", ""46.55 kg"", ""\tMiami, FL""]","[""O00058"", ""C00322"", ""2024-09-09"", ""null"", ""5"", ""800.62"", """", ""46.55 kg""]"

$ csvmend replay data/orders.csv --log out/changes.csv | diff - out/clean.csv && echo replay matches
replay matches
```

The same demo table, with changed cells in yellow and dropped rows in red, is in [index.html](index.html). Open it from disk.
