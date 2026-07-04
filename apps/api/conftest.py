"""Top-level pytest config for apps/api.

The real, hermetic test suite lives under ``tests/``. A few ``test_*.py``
scripts sit at the package root as manual smoke checks against LIVE external
services (OpenAI, Anthropic, Stripe, MinIO, Semantic Scholar). They are meant
to be run by hand (each has an ``if __name__ == "__main__"`` entrypoint),
assert nothing (their ``test_*`` functions just print and return a bool while
swallowing every exception), and call ``load_dotenv()`` at import time — which
pushes apps/api/.env into ``os.environ`` and pollutes settings-default tests.

Excluding them from collection keeps ``pytest apps/api`` hermetic: no live
network calls, no real Stripe customer creation, and no .env bleed-through.
Run them deliberately, e.g. ``python test_external_services.py``.
"""

collect_ignore = [
    "test_real_api.py",
    "test_external_services.py",
    "test_openai_direct.py",
]
