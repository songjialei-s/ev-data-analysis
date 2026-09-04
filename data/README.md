# Data policy

The CSV files in this directory are synthetic demonstration data retained for the legacy analysis pipeline. They do not represent company operations.

Real source workbooks must be stored locally under `data/raw/`. This directory is ignored by Git because the source contains user, vehicle and internal transaction identifiers. Row-level cleaned extracts must be written to `data/private_processed/`, which is also ignored.

The repository publishes only reproducible cleaning code, aggregate quality summaries and a fully synthetic sample. Never commit raw Excel files, user numbers, card numbers, license plates, VINs, internal business numbers or unreviewed intermediate files.
