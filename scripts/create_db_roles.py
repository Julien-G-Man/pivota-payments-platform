"""
Run app/db/roles.sql against target database.
Idempotent — safe to run multiple times.

Usage:
  python scripts/create_db_roles.py --env development
  python scripts/create_db_roles.py --env staging
"""

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--env", required=True, choices=["development", "staging", "production"])
args = parser.parse_args()

# TODO: implement role creation via psycopg2 / asyncpg
print(f"Creating DB roles for {args.env}... (not yet implemented)")
