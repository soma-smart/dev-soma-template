"""Domain layer.

Contains the core business model: entities, value objects, domain exceptions.
This layer has zero dependencies on third parties and zero non-deterministic
side effects (no datetime.now(), no uuid.uuid4(), no random). Anything
non-deterministic comes through abstractions (Clock, IdGenerator, RandomSource)
defined in the application layer.
"""
