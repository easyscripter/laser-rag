"""Authentication: argon2 passwords, JWT tokens, user lookup, and login service.

Pure logic — no FastAPI imports here. The HTTP layer (``app/api/auth.py`` and the
dependency guards in ``app/api/deps.py``) builds on these primitives.
"""
