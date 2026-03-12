"""
Inspect and replay DLQ entries from Redis Stream dlq:events.

Usage:
  python scripts/replay_dlq.py --list
  python scripts/replay_dlq.py --replay {id}
  python scripts/replay_dlq.py --clear {id}
"""

import argparse

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--list", action="store_true")
group.add_argument("--replay", metavar="ID")
group.add_argument("--clear", metavar="ID")
args = parser.parse_args()

# TODO: implement DLQ inspection/replay
print("DLQ operations... (not yet implemented)")
