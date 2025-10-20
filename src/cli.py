# src/cli.py
import argparse
from .db import create_db
from .gen import seed_everything

def main():
    parser = argparse.ArgumentParser(prog="fcc-synthetic-tm", description="FCC/TM synthetic data toolkit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init db
    p_init = sub.add_parser("init-db", help="Create SQLite DB schema")
    p_init.add_argument("--db", default="data/fcc_tm.sqlite", help="Path to SQLite file")

    # generate data
    p_gen = sub.add_parser("generate", help="Insert synthetic data (customers, accounts, transactions, alerts)")
    p_gen.add_argument("--db", default="data/fcc_tm.sqlite", help="Path to SQLite file")
    p_gen.add_argument("--n-customers", type=int, default=1000, help="Number of INTERNAL customers")
    p_gen.add_argument("--n-externals", type=int, default=600, help="Number of EXTERNAL counterparties")
    p_gen.add_argument("--n-accounts", type=int, default=1500, help="Total accounts (assigned to internal customers)")
    p_gen.add_argument("--n-transactions", type=int, default=20000, help="Total transactions")
    p_gen.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    if args.cmd == "init-db":
        create_db(args.db)
        print(f"Initialized schema at {args.db}")

    elif args.cmd == "generate":
        stats = seed_everything(
            db_path=args.db,
            n_customers=args.n_customers,
            n_externals=args.n_externals,
            n_accounts=args.n_accounts,
            n_tx=args.n_transactions,
            seed=args.seed,
        )
        print("Generated: {customers} customers | {accounts} accounts | "
        "{transactions} transactions | {alerts} alerts -> {db}".format(
        customers=stats['customers'],
        accounts=stats['accounts'],
        transactions=stats['transactions'],
        alerts=stats['alerts'],
        db=args.db))