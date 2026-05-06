"""Background jobs (workers, relays, schedulers).

Each module here is a ``__main__``-runnable async script meant to live in a
separate container or process from the API. Pick a runner per project
(plain Python loop, ARQ, dramatiq, Celery) and document the choice; the
template ships only the polling-loop scaffold for the outbox relay.
"""
