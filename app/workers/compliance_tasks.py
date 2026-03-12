"""compliance_tasks — Celery task definitions.

All tasks must have max_retries=3, retry_backoff=True, retry_backoff_max=3600.
See CLAUDE.md Rule 6.
"""

from app.config.celery import celery_app

# TODO: implement tasks for compliance_tasks
