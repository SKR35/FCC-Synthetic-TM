from pathlib import Path
import sqlite3

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT PRIMARY KEY,
  is_internal INTEGER NOT NULL CHECK (is_internal IN (0,1)),
  customer_type TEXT NOT NULL CHECK (customer_type IN ('PERSON','ORG')),
  full_name TEXT,
  country_iso2 TEXT CHECK (length(country_iso2)=2),
  risk_rating TEXT CHECK (risk_rating IN ('LOW','MEDIUM','HIGH')),
  pep_flag INTEGER NOT NULL DEFAULT 0 CHECK (pep_flag IN (0,1)),
  created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  product_type TEXT NOT NULL CHECK (product_type IN ('CHECKING','SAVINGS','CREDIT_CARD','PREPAID')),
  iban_or_masked TEXT,
  currency_iso3 TEXT NOT NULL CHECK (length(currency_iso3)=3),
  open_date TEXT NOT NULL,      -- YYYY-MM-DD
  close_date TEXT,
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','FROZEN')),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cash_transactions (
  tx_id TEXT PRIMARY KEY,
  ts_utc TEXT NOT NULL,         -- ISO timestamp
  account_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,    -- owner of account (denormalized)
  counterparty_customer_id TEXT,
  channel TEXT NOT NULL CHECK (channel IN ('CASH','ATM','CARD')),
  direction TEXT NOT NULL CHECK (direction IN ('IN','OUT')),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  currency_iso3 TEXT NOT NULL CHECK (length(currency_iso3)=3),
  country_iso2 TEXT CHECK (length(country_iso2)=2),
  mcc_code TEXT,                -- for CARD
  merchant_name TEXT,           -- for CARD
  terminal_id TEXT,             -- ATM/POS
  branch_id TEXT,               -- cash desk
  auth_code TEXT,               -- card auth (synthetic)
  description TEXT,
  FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  FOREIGN KEY (counterparty_customer_id) REFERENCES customers(customer_id),
  CHECK (channel <> 'CARD' OR (mcc_code IS NOT NULL OR merchant_name IS NOT NULL)),
  CHECK (channel <> 'ATM' OR terminal_id IS NOT NULL),
  CHECK (channel <> 'CASH' OR branch_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS alerts (
  alert_id TEXT PRIMARY KEY,
  created_ts_utc TEXT NOT NULL DEFAULT (datetime('now')),
  entity_type TEXT NOT NULL CHECK (entity_type IN ('TRANSACTION','ACCOUNT','CUSTOMER')),
  entity_id TEXT NOT NULL,      -- tx_id OR account_id OR customer_id
  rule_id TEXT NOT NULL,        -- e.g., R_STRUCTURING_01
  score REAL NOT NULL CHECK (score >= 0),
  label INTEGER CHECK (label IN (0,1)),
  typology TEXT,
  outcome TEXT CHECK (outcome IN ('OPEN','CLOSED','ESCALATED','DISMISSED')),
  closed_ts_utc TEXT
);

CREATE INDEX IF NOT EXISTS ix_accounts_customer    ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS ix_tx_account_time      ON cash_transactions(account_id, ts_utc);
CREATE INDEX IF NOT EXISTS ix_tx_customer_time     ON cash_transactions(customer_id, ts_utc);
CREATE INDEX IF NOT EXISTS ix_tx_counterparty      ON cash_transactions(counterparty_customer_id);
CREATE INDEX IF NOT EXISTS ix_alerts_entity        ON alerts(entity_type, entity_id);
"""

def create_db(db_path: str = "data/fcc_tm.sqlite") -> None:
    """Create SQLite DB and schema."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()