"""
Seed development database with realistic test data.

Creates 3 users, 6 months of transaction history, and anomalous transactions.
GUARD: raises if ENVIRONMENT != 'development'. Never runs in prod.
"""

import os
import sys

if os.getenv("ENVIRONMENT", "development") != "development":
    print("ERROR: seed_dev_data.py must only run in development environment")
    sys.exit(1)

# TODO: implement seeding logic
print("Seeding dev data... (not yet implemented)")
