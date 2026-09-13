"""Link and content filtering rules for Faytuks Network."""
from __future__ import annotations

import re
from typing import Optional

from .base import BaseMessageFilter


class FaytuksFilter(BaseMessageFilter):
    """
    Applies Faytuks Network specific transformations:
      - Removes URLs and hyperlinks that reference Faytuks Network.
      - Removes promotional boilerplate preceding removed links (e.g. 'Read more:', 'Read on').
      - Strictly preserves unrelated external links (e.g. Reuters, Bloomberg, AP).
      - Cleans up leftover punctuation, dangling colons/dashes, and extra whitespace.
    """

    # Matches Markdown links: [Anchor](URL)
    MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")

    # General URL regex
    URL_PATTERN = re.compile(r"(https?://[^\s\)]+)")

    # Keywords indicating a link references Faytuks Network
    FAYTUKS_KEYWORDS = ("faytuks", "faytuksnetwork", "faytuks-network")

    # Boilerplate prompts preceding links to be cleaned if the attached link was removed
    PROMPTS_PATTERN = re.compile(
        r"(?:(?:read\s+more(?:\s+here)?|read\s+on|read\s+at|see\s+on|source|via|link|more\s+details|full\s+story|follow(?:\s+us)?|see\s+more)\s*[:\-–—]?\s*)$",
        re.IGNORECASE,
    )

    @property
    def channel_identifier(self) -> str:
        return "faytuks_network"

    def is_faytuks_reference(self, text_or_url: str) -> bool:
        """Checks if a URL or anchor text references Faytuks."""
        lowered = text_or_url.lower()
        return any(kw in lowered for kw in self.FAYTUKS_KEYWORDS)

    def _remove_faytuks_markdown_links(self, text: str) -> str:
        """Removes Markdown links [text](url) where anchor or url references Faytuks."""
        # Also clean preceding prompt like "Read on [Faytuks](...)" or "on [Faytuks](...)"
        def replacer(match: re.Match) -> str:
            anchor = match.group(1)
            url = match.group(2)
            if self.is_faytuks_reference(anchor) or self.is_faytuks_reference(url):
                return ""
            return match.group(0)

        # Match markdown links with optional preceding prompt like "Read on [Faytuks](...)"
        cleaned = re.sub(
            r"(?:read\s+on|read\s+at|see\s+on|follow\s+on)?\s*\[([^\]]+)\]\((https?://[^\s\)]+)\)",
            lambda m: "" if (self.is_faytuks_reference(m.group(1)) or self.is_faytuks_reference(m.group(2))) else m.group(0),
            text,
            flags=re.IGNORECASE,
        )
        return cleaned

    def _remove_faytuks_raw_urls(self, text: str) -> str:
        """Removes standalone raw URLs that reference Faytuks."""
        def replacer(match: re.Match) -> str:
            url = match.group(1)
            if self.is_faytuks_reference(url):
                return ""
            return match.group(0)

        return self.URL_PATTERN.sub(replacer, text)

    def _remove_faytuks_mentions(self, text: str) -> str:
        """Removes @Faytuks / @Faytuks_Network mentions."""
        return re.sub(r"[@＠]Faytuks(?:_?Network)?\b", "", text, flags=re.IGNORECASE)

    def _clean_dangling_prompts_and_punctuation(self, text: str) -> str:
        """
        Cleans up leftover boilerplate and punctuation when a link has been stripped.
        e.g., 'BREAKING: Oil prices climb. Read more: ' -> 'BREAKING: Oil prices climb.'
        """
        # Clean dangling conjunctions left after link removal like " or check" or " and see"
        text = re.sub(r"\s+(?:or|and)\s+(?:check|see)\b", "", text, flags=re.IGNORECASE)

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            trimmed = line.strip()
            # If the entire line was a prompt or Faytuks reference, discard it
            if not trimmed or self.is_faytuks_reference(trimmed):
                continue

            # Strip dangling prompt at the end of the line
            trimmed = self.PROMPTS_PATTERN.sub("", trimmed).strip()

            # Clean trailing punctuation like ' -', ' :', ' |', ' •'
            trimmed = re.sub(r"[\s\-–—:,|•]+$", "", trimmed).strip()

            if trimmed:
                cleaned_lines.append(trimmed)

        return "\n".join(cleaned_lines)

    def process_text(self, text: Optional[str]) -> Optional[str]:
        """Executes full Faytuks Network transformation pipeline."""
        if not text:
            return None

        # Step 1: Remove Markdown links referencing Faytuks
        cleaned = self._remove_faytuks_markdown_links(text)

        # Step 2: Remove raw URLs referencing Faytuks
        cleaned = self._remove_faytuks_raw_urls(cleaned)

        # Step 3: Remove Faytuks @ mentions
        cleaned = self._remove_faytuks_mentions(cleaned)

        # Step 4: Clean dangling prompts, punctuation, and empty lines
        cleaned = self._clean_dangling_prompts_and_punctuation(cleaned)

        # Step 5: Normalize multiple whitespace
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = cleaned.strip()

        return cleaned if cleaned else None

