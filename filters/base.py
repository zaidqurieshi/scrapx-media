"""Base filter class for channel message processors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BaseMessageFilter(ABC):
    """Abstract base class for channel-specific message transformations."""

    @property
    @abstractmethod
    def channel_identifier(self) -> str:
        """Name or identifier of the channel this filter applies to."""
        pass

    @abstractmethod
    def process_text(self, text: Optional[str]) -> Optional[str]:
        """
        Transforms message text or caption according to the channel rules.
        Returns the sanitized text, or None if the text is empty/removed.
        """
        pass

