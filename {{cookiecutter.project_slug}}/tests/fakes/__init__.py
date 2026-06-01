"""In-memory implementations of application abstractions used in tests.

The whole package is the contract: production code never imports from
``tests/fakes`` and tests never use ``unittest.mock`` for these collaborators.
"""
