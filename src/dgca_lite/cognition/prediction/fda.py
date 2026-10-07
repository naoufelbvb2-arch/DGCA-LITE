"""FDA has no public fields or methods and cannot be copied or serialized."""

from ..authority import _OpaqueHandle


class ForecastDelegatedAuthority(_OpaqueHandle):
    __slots__ = ()
