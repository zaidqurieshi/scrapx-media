"""Filters package for message sanitization and transformation."""
from typing import Dict, Optional

from .base import BaseMessageFilter
from .faytuks import FaytuksFilter
from .first_squawk import FirstSquawkFilter

__all__ = [
    "BaseMessageFilter",
    "FirstSquawkFilter",
    "FaytuksFilter",
    "get_filter_for_channel",
]

_FILTER_REGISTRY: Dict[str, BaseMessageFilter] = {
    "first_squawk": FirstSquawkFilter(),
    "faytuks": FaytuksFilter(),
}


def get_filter_for_channel(channel_key: str) -> Optional[BaseMessageFilter]:
    """Retrieves the registered filter for a given channel key."""
    channel_key = channel_key.lower().strip()
    return _FILTER_REGISTRY.get(channel_key)

