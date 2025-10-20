# src/gen.py
import sqlite3
import uuid
import random
from datetime import datetime, timedelta, date
from pathlib import Path

# --- small vocabularies (no external deps) ---
COUNTRIES = ["PL", "DE", "CZ", "SK", "LT", "LV", "EE", "GB", "US", "TR", "FR", "ES"]
CURRENCIES = ["PLN", "EUR", "USD"]
PRODUCTS = ["CHECKING", "SAVINGS", "CREDIT_CARD", "PREPAID"]
RISKS = ["LOW", "MEDIUM", "HIGH"]
MCC_SAMPLES = ["5411", "5732", "5812", "5912", "5947", "4111", "4789"]  # grocery, electronics, restaurant, etc.
MERCHANTS = ["Biedronka", "MediaMarkt", "Café Aurora", "Zabka", "Lotos", "Empik", "IKEA"]

def _uuid() -> str:
    return str(uuid.uuid4())

def _pick_weighted(r: random.Random, items, weights):
    return r.choices(items, weights=weights, k=1)[0]

def _rand_country(r: random.Random) -> str:
    # bias to PL
    return r.choices(COUNTRIES, weights=[7] + [1]*(len(COUNTRIES)-1), k=1)[0]

def _rand_currency(r: random.Random) -> str:
    return r.choices(CURRENCIES, weights=[7, 2, 1], k=1)[0]

def _rand_amount_minor(r: random.Random, channel: str) -> int:
    # amounts in major units via triangular, then convert to minor (cents/grosze)
    if channel == "CARD":
        amt = r.triangular(5, 400, 40)        # purchases
    elif channel == "ATM":
        amt = r.triangular(50, 1500, 400)     # withdrawals
    else:  # CASH desk deposit/withdrawal
        amt = r.triangular(50, 5000, 600)
    cents = max(1, int(round(amt * 100)))
    return cents

def _rand_ts(r: random.Random, days_back: int = 90) -> str:
    now = datetime.utcnow()
    start = now - timedelta(days=days_back)
    delta = r.random() * (now - start).total_seconds()
    return (start + timedelta(seconds=delta)).isoformat(timespec="seconds") + "Z"

def _rand_open_date(r: random.Random, years_back: int = 2) -> str:
    today = date.today()
    start = date(today.year - years_back, today.month, 1)
    delta_days = (today - start).days
    return (start + timedelta(days=r.randint(0, max(1, delta_days)))).isoformat()

def _risk(r: random.Random) -> str:
    return _pick_weighted(r, RISKS, [6, 3, 1])

def _bool(r: random.Random, p_true: float) -> int:
    return 1 if r.random() < p_true else 0

# -------------------------
# Generators + inserters
# -------------------------
def generate_customers(r: random.Random, n_internal: int, n_external: int):
    rows = []

    # internal customers
    for _ in range(n_internal):
        cid = _uuid()
        rows.append((
            cid,
            1,                                  # is_internal
            "PERSON" if r.random() < 0.8 else "ORG",
            f"Cust {cid[:8]}",
            _rand_country(r),
            _risk(r),
            _bool(r, 0.02),                     # pep_flag
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "ACTIVE",
        ))

    # external counterparties (merchants/ATM operators/other banks’ clients)
    for _ in range(n_external):
        cid = _uuid()
        rows.append((
            cid,
            0,
            "ORG" if r.random() < 0.7 else "PERSON",
            f"Ext {cid[:8]}",
            _rand_country(r),
            _risk(r),
            0,
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "ACTIVE",
        ))
    return rows

def insert_customers(conn: sqlite3.Connection, rows):
    conn.executemany("""
        INSERT INTO customers
        (customer_id, is_internal, customer_type, full_name, country_iso2, risk_rating, pep_flag, created_at_utc, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

def generate_accounts(r: random.Random, internal_customer_ids, n_accounts: int):
    rows = []
    for _ in range(n_accounts):
        owner = r.choice(internal_customer_ids)
        product = _pick_weighted(r, PRODUCTS, [6, 4, 3, 1])
        currency = _rand_currency(r)
        acc_id = _uuid()
        rows.append((
            acc_id, owner, product, f"***{acc_id[:6]}", currency,
            _rand_open_date(r), None, "OPEN"
        ))
    return rows

def insert_accounts(conn: sqlite3.Connection, rows):
    conn.executemany("""
        INSERT INTO accounts
        (account_id, customer_id, product_type, iban_or_masked, currency_iso3, open_date, close_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

def generate_transactions(
    r: random.Random,
    accounts,                                  # list of (account_id, customer_id, currency_iso3)
    internal_by_account,                        # dict account_id -> (customer_id, currency)
    external_customer_ids,                      # candidates for counterparties
    n_tx: int
):
    rows = []
    # channel mix
    channels = ["CARD", "ATM", "CASH"]
    ch_w = [0.60, 0.25, 0.15]

    for _ in range(n_tx):
        acc_id = r.choice(accounts)
        cust_id, acc_curr = internal_by_account[acc_id]

        channel = _pick_weighted(r, channels, ch_w)
        # direction defaults
        if channel == "CARD":
            direction = "OUT" if r.random() < 0.95 else "IN"
        elif channel == "ATM":
            direction = "OUT" if r.random() < 0.98 else "IN"
        else:
            direction = "IN" if r.random() < 0.55 else "OUT"

        amount_minor = _rand_amount_minor(r, channel)
        country = _rand_country(r)
        counterparty = r.choice(external_customer_ids) if external_customer_ids else None

        mcc = merchant = terminal = branch = None
        if channel == "CARD":
            mcc = r.choice(MCC_SAMPLES)
            merchant = r.choice(MERCHANTS)
        elif channel == "ATM":
            terminal = f"ATM{r.randint(1000,9999)}"
        else:  # CASH desk
            branch = f"BR{r.randint(100,999)}"

        rows.append((
            _uuid(),
            _rand_ts(r),
            acc_id,
            cust_id,
            counterparty,
            channel,
            direction,
            amount_minor,
            acc_curr,            # use account currency for v0.1
            country,
            mcc,
            merchant,
            terminal,
            branch,
            f"{channel} {direction} {_uuid()[:6]}",  # description
        ))
    return rows

def insert_transactions(conn: sqlite3.Connection, rows):
    conn.executemany("""
        INSERT INTO cash_transactions
        (tx_id, ts_utc, account_id, customer_id, counterparty_customer_id, channel, direction,
         amount_minor, currency_iso3, country_iso2, mcc_code, merchant_name, terminal_id, branch_id, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

def generate_simple_alerts(r: random.Random, tx_rows, top_percent: float = 0.01):
    # pick top X% by amount as alerts
    n = max(1, int(len(tx_rows) * top_percent))
    # sort by amount_minor descending
    chosen = sorted(tx_rows, key=lambda t: t[7], reverse=True)[:n]
    out = []
    for row in chosen:
        tx_id = row[0]
        score = min(100.0, row[7] / 1000.0)  # simple scaling
        out.append((
            _uuid(),
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "TRANSACTION",
            tx_id,
            "R_HIGH_AMOUNT",
            round(score, 2),
            1,                     # label: positive in synthetic
            "STRUCTURING",
            "OPEN",
            None
        ))
    return out

def insert_alerts(conn: sqlite3.Connection, rows):
    conn.executemany("""
        INSERT INTO alerts
        (alert_id, created_ts_utc, entity_type, entity_id, rule_id, score, label, typology, outcome, closed_ts_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

def load_ids(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT customer_id, is_internal FROM customers")
    internals = []
    externals = []
    for cid, is_int in cur.fetchall():
        (internals if is_int else externals).append(cid)
    cur.execute("SELECT account_id, customer_id, currency_iso3 FROM accounts")
    acct_rows = cur.fetchall()
    internal_by_account = {acc: (cust, curr) for acc, cust, curr in acct_rows}
    account_ids = [acc for acc, _, _ in acct_rows]
    return internals, externals, account_ids, internal_by_account

def seed_everything(db_path: str, n_customers: int, n_externals: int, n_accounts: int, n_tx: int, seed: int):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    r = random.Random(seed)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        # customers
        cust_rows = generate_customers(r, n_customers, n_externals)
        insert_customers(conn, cust_rows)

        # accounts
        internals, externals, _, _ = load_ids(conn)
        acct_rows = generate_accounts(r, internals, n_accounts)
        insert_accounts(conn, acct_rows)

        # tx
        internals, externals, account_ids, internal_by_account = load_ids(conn)
        tx_rows = generate_transactions(r, account_ids, internal_by_account, externals, n_tx)
        insert_transactions(conn, tx_rows)

        # alerts (simple)
        alert_rows = generate_simple_alerts(r, tx_rows, top_percent=0.01)
        insert_alerts(conn, alert_rows)

        conn.commit()
        return {
            "customers": len(cust_rows),
            "accounts": len(acct_rows),
            "transactions": len(tx_rows),
            "alerts": len(alert_rows),
        }
    finally:
        conn.close()