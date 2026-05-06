"""Marker base for value objects."""


class ValueObject:
    """Marker class for value objects.

    Concrete subclasses MUST be declared with
    ``@dataclass(frozen=True, slots=True)`` for value-based equality and
    immutability. Inheriting from this class with ``__slots__ = ()`` keeps
    the slotted layout intact.
    """

    __slots__ = ()
