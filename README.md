## FCC-Synthetic-TM

**SQLite schema + Python toolkit** for generating realistic **synthetic Transaction Monitoring** data.  
Tables: `customers` (internal/external), `accounts`, `cash_transactions` (cash/ATM/card), `alerts`.

> **Purpose:** Safe, PII-free sandbox to prototype TM rules, analytics and QC (KS/PSI) - with reproducible seeds.

---

## Features
- **Lean schema** focused on TM essentials (4 tables).
- **Reproducible generators** (seeded) for customers, accounts, transactions and simple alerts.
- **Channel-aware** transaction fields (CARD/ATM/CASH with MCC, terminal/branch, etc.).
- **No external dependencies** (stdlib only).
- **CI smoke test** to build DB and verify basic integrity.

---

## Data Model (v0.1)

customers (customer_id PK, is_internal)
└── accounts (account_id PK, customer_id FK -> customers)
└── cash_transactions (tx_id PK, account_id FK -> accounts,
customer_id FK -> customers [owner],
counterparty_customer_id FK -> customers [external])
alerts (alert_id PK) → references {transaction | account | customer} by (entity_type, entity_id)

### Tables & key columns
- **customers**
  - `customer_id (PK)`, `is_internal (0/1)`, `customer_type ('PERSON'|'ORG')`,
    `country_iso2`, `risk_rating ('LOW'|'MEDIUM'|'HIGH')`, `pep_flag (0/1)`, `status`.
- **accounts**
  - `account_id (PK)`, `customer_id (FK)`, `product_type ('CHECKING'|'SAVINGS'|'CREDIT_CARD'|'PREPAID')`,
    `currency_iso3`, `open_date`, `status`.
- **cash_transactions**
  - `tx_id (PK)`, `ts_utc`, `account_id (FK)`, `customer_id (FK)`, `counterparty_customer_id (FK)`,
    `channel ('CASH'|'ATM'|'CARD')`, `direction ('IN'|'OUT')`,
    `amount_minor` (integer, cents/grosze), `currency_iso3`, `country_iso2`,
    channel-specific: `mcc_code`, `merchant_name`, `terminal_id`, `branch_id`, `auth_code`.
- **alerts**
  - `alert_id (PK)`, `created_ts_utc`, `entity_type ('TRANSACTION'|'ACCOUNT'|'CUSTOMER')`, `entity_id`,
    `rule_id`, `score`, `label (0/1)`, `typology`, `outcome`, `closed_ts_utc`.

> v0.1 rule of thumb: `accounts` belong to **internal** customers + counterparties are typically **external**.

---

## Quickstart

### 1) Create environment
~~~bash
conda create -n fcc_tm python=3.11 -y

conda activate fcc_tm
~~~

### 2) Initialize the SQLite schema

python -m src init-db --db data/fcc_tm.sqlite

### 3) Generate synthetic data
python -m src generate --db data/fcc_tm.sqlite --n-customers 1500 --n-externals 1000 --n-accounts 1300 --n-transactions 200000 --seed 42

## Ethics 

100% synthetic data + not guidance for evasion. No affiliation with any FI or vendor.

### Directory Layout

```text
FCC-Synthetic-TM/
├─ src/
│  ├─ __main__.py         # entry: python -m src
│  ├─ cli.py              # CLI commands
│  ├─ db.py               # SQLite schema (create_db)
│  └─ gen.py              # data generators & inserters
├─ .github/
│  └─ workflows/
│     └─ ci.yml           # CI smoke test (init + generate + checks)
├─ data/                  # runtime artifacts
│  └─ fcc_tm.sqlite       # created by init-db/generate
├─ README.md
├─ pyproject.toml
├─ LICENSE