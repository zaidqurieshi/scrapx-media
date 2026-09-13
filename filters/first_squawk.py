"""Text formatting and filtering rules for First Squawk."""
from __future__ import annotations

import re
from typing import Optional, Set

from .base import BaseMessageFilter

# Preserved Acronyms / Tickers / Indicators that should remain UPPERCASE
UPPERCASE_PRESERVED: Set[str] = {
    # Geopolitical & International Organizations
    "US", "USA", "UK", "EU", "UAE", "PRC", "ROC", "UN", "NATO", "G7", "G20",
    "OPEC", "OPEC+", "WHO", "WTO", "IMF", "WB", "APEC", "BRICS",
    # Financial Regulatory & Central Banks (Fed is handled in PROPER_NOUNS as "Fed")
    "FOMC", "ECB", "BOE", "BOJ", "PBOC", "SNB", "RBA", "BOC", "RBI",
    "SEC", "CFTC", "FTC", "DOJ", "FDIC", "FINRA", "OCC", "CFPB",
    # Economic Indicators & Financial Terms
    "CPI", "PPI", "GDP", "GNP", "PCE", "PMI", "NFP", "ATH", "EPS",
    "PE", "P/E", "EBITDA", "IPO", "M&A", "ETF", "ETFS", "NAV", "AUM", "ROI",
    "ROIC", "ROE", "YOY", "MOM", "QOQ", "FX", "LIBOR", "SOFR", "WTI", "BRENT",
    # Currencies & Cryptocurrencies
    "USD", "EUR", "GBP", "JPY", "CNY", "CHF", "CAD", "AUD", "NZD", "INR",
    "HKD", "SGD", "SEK", "NOK", "KRW", "MXN", "BRL", "ZAR", "TRY",
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "USDT", "USDC",
    # Stock Indices & Benchmarks
    "S&P", "NASDAQ", "DJIA", "DOW", "VIX", "FTSE", "DAX", "CAC", "NIKKEI",
    "KOSPI", "NIFTY", "SENSEX", "STOXX", "RUSSELL",
    # Prominent Tickers
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "INTC", "TSMC", "ASML", "AVGO", "ARM", "NFLX", "BABA", "DIS", "JPM",
    "BAC", "GS", "MS", "C", "WFC", "XOM", "CVX", "LLY", "JNJ", "WMT", "COST",
    "PLTR", "COIN", "MSTR", "UBER", "ABNB", "SNOW", "CRM", "ORCL", "IBM",
    # Quarters & Days/Time markers
    "Q1", "Q2", "Q3", "Q4", "H1", "H2", "YTD", "EST", "EDT", "PST", "PDT", "GMT", "UTC",
}

# Multi-word proper nouns replaced directly before word-level tokenization
MULTI_WORD_PROPER_NOUNS = [
    (r"\bWALL\s+STREET\b", "Wall Street"),
    (r"\bWHITE\s+HOUSE\b", "White House"),
    (r"\bUNITED\s+STATES\b", "United States"),
    (r"\bUNITED\s+KINGDOM\b", "United Kingdom"),
    (r"\bEUROPEAN\s+UNION\b", "European Union"),
    (r"\bSAUDI\s+ARABIA\b", "Saudi Arabia"),
    (r"\bSOUTH\s+KOREA\b", "South Korea"),
    (r"\bNORTH\s+KOREA\b", "North Korea"),
    (r"\bNEW\s+YORK\b", "New York"),
    (r"\bHONG\s+KONG\b", "Hong Kong"),
    (r"\bMIDDLE\s+EAST\b", "Middle East"),
    (r"\bSUPREME\s+COURT\b", "Supreme Court"),
    (r"\bS&P\s+500\b", "S&P 500"),
]

# Proper nouns and terms mapped to specific case
CASE_MAPPINGS = {
    # Central Bank
    "FED": "Fed",
    # Basis points convention in financial news
    "BPS": "bps",
    # Prominent Figures
    "POWELL": "Powell",
    "YELLEN": "Yellen",
    "LAGARDE": "Lagarde",
    "BIDEN": "Biden",
    "TRUMP": "Trump",
    "HARRIS": "Harris",
    "MUSK": "Musk",
    "BUFFETT": "Buffett",
    "DIMON": "Dimon",
    "COOK": "Cook",
    "HUANG": "Huang",
    "ALTMAN": "Altman",
    "NETANYAHU": "Netanyahu",
    "PUTIN": "Putin",
    "ZELENSKYY": "Zelenskyy",
    "ZELENSKY": "Zelensky",
    "XI": "Xi",
    "JINPING": "Jinping",
    "MACRON": "Macron",
    "SCHOLZ": "Scholz",
    "SUNAK": "Sunak",
    "STARMER": "Starmer",
    # Countries & Major Cities
    "AMERICA": "America",
    "AMERICAN": "American",
    "CHINA": "China",
    "CHINESE": "Chinese",
    "RUSSIA": "Russia",
    "RUSSIAN": "Russian",
    "UKRAINE": "Ukraine",
    "UKRAINIAN": "Ukrainian",
    "GERMANY": "Germany",
    "GERMAN": "German",
    "FRANCE": "France",
    "FRENCH": "French",
    "JAPAN": "Japan",
    "JAPANESE": "Japanese",
    "TAIWAN": "Taiwan",
    "TAIWANESE": "Taiwanese",
    "ISRAEL": "Israel",
    "ISRAELI": "Israeli",
    "IRAN": "Iran",
    "IRANIAN": "Iranian",
    "SAUDI": "Saudi",
    "ARABIA": "Arabia",
    "INDIA": "India",
    "INDIAN": "Indian",
    "CANADA": "Canada",
    "CANADIAN": "Canadian",
    "AUSTRALIA": "Australia",
    "AUSTRALIAN": "Australian",
    "MEXICO": "Mexico",
    "MEXICAN": "Mexican",
    "BRAZIL": "Brazil",
    "TURKEY": "Turkey",
    "TURKISH": "Turkish",
    "WASHINGTON": "Washington",
    "BEIJING": "Beijing",
    "MOSCOW": "Moscow",
    "LONDON": "London",
    "TOKYO": "Tokyo",
    "KYIV": "Kyiv",
    "TEHRAN": "Tehran",
    "JERUSALEM": "Jerusalem",
    "BRUSSELS": "Brussels",
    "TREASURY": "Treasury",
    "CONGRESS": "Congress",
    "SENATE": "Senate",
    "PENTAGON": "Pentagon",
    # Months
    "JANUARY": "January", "FEBRUARY": "February", "MARCH": "March",
    "APRIL": "April", "MAY": "May", "JUNE": "June", "JULY": "July",
    "AUGUST": "August", "SEPTEMBER": "September", "OCTOBER": "October",
    "NOVEMBER": "November", "DECEMBER": "December",
    "JAN": "Jan", "FEB": "Feb", "MAR": "Mar", "APR": "Apr",
    "JUN": "Jun", "JUL": "Jul", "AUG": "Aug", "SEP": "Sep",
    "OCT": "Oct", "NOV": "Nov", "DEC": "Dec",
    # Days
    "MONDAY": "Monday", "TUESDAY": "Tuesday", "WEDNESDAY": "Wednesday",
    "THURSDAY": "Thursday", "FRIDAY": "Friday", "SATURDAY": "Saturday", "SUNDAY": "Sunday",
    "MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu", "FRI": "Fri", "SAT": "Sat", "SUN": "Sun",
}


class FirstSquawkFilter(BaseMessageFilter):
    """
    Applies First Squawk specific transformations:
      - Detects all-caps / predominantly uppercase text.
      - Converts to natural sentence capitalization.
      - Preserves proper nouns, tickers, currencies, and acronyms.
      - Strips @FirstSquaw / @FirstSquawk mentions and dangling punctuation.
    """

    # Boundary: newline, or period/exclamation/question followed by space, or colon/semicolon followed by space
    CLAUSE_SPLIT_PATTERN = re.compile(r"(\n+|(?<=[.!?])\s+|(?<=[:;])\s+)")

    # Regex for words (handling words with apostrophes, dollar signs, slashes, numbers, etc.)
    TOKEN_PATTERN = re.compile(r"(\$[A-Za-z0-9.]+|\b[A-Za-z0-9&/+'’\-]+|\s+|[^\w\s])")

    @property
    def channel_identifier(self) -> str:
        return "first_squawk"

    def is_predominantly_uppercase(self, text: str, threshold: float = 0.65) -> bool:
        """Determines whether the text is largely written in UPPERCASE."""
        alphas = [c for c in text if c.isalpha()]
        if len(alphas) < 6:
            return False
        uppers = [c for c in alphas if c.isupper()]
        return (len(uppers) / len(alphas)) >= threshold

    def remove_mentions(self, text: str) -> str:
        """Removes @FirstSquaw and @FirstSquawk mentions and cleans leftover punctuation."""
        # 1. Clean mentions enclosed in parentheses or brackets: "(@FirstSquaw)", "[@FirstSquaw]"
        cleaned = re.sub(r"\([@＠]FirstSquaw(?:k)?\b\)", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[[@＠]FirstSquaw(?:k)?\b\]", "", cleaned, flags=re.IGNORECASE)

        # 2. Clean if at start of string: "@FirstSquaw: BREAKING..." -> "BREAKING..."
        cleaned = re.sub(r"^\s*[@＠]FirstSquaw(?:k)?\b\s*[-–—|•:]*\s*", "", cleaned, flags=re.IGNORECASE)

        # 3. Clean if at end of string: "... US GDP @FirstSquaw" -> "... US GDP"
        cleaned = re.sub(r"\s*[-–—|•:]*\s*[@＠]FirstSquaw(?:k)?\b\s*$", "", cleaned, flags=re.IGNORECASE)

        # 4. Clean if anywhere in between:
        cleaned = re.sub(r"\s*[-–—|•:]*\s*[@＠]FirstSquaw(?:k)?\b\s*", " ", cleaned, flags=re.IGNORECASE)

        # 5. Clean empty parentheses or brackets left behind
        cleaned = re.sub(r"\(\s*\)", "", cleaned)
        cleaned = re.sub(r"\[\s*\]", "", cleaned)

        # 6. Strip leftover dangling punctuation from start or end
        cleaned = cleaned.strip()
        cleaned = re.sub(r"^[\s\-–—:,|•]+", "", cleaned).strip()
        cleaned = re.sub(r"[\s\-–—:,|•]+$", "", cleaned).strip()
        return cleaned

    def _format_token(self, token: str, is_sentence_start: bool) -> str:
        """Formats an individual word token respecting financial rules."""
        raw_upper = token.upper()

        # If token is already mixed-case (e.g. iPhone, Wall, Street from multi-word replacement), preserve
        has_upper = any(c.isupper() for c in token)
        has_lower = any(c.islower() for c in token)
        if has_upper and has_lower:
            return token

        # 1. Preserved exact uppercase terms (e.g. US, FOMC, CPI, TSLA, S&P)
        if raw_upper in UPPERCASE_PRESERVED:
            return raw_upper

        # 2. Dollar prefixed tickers or prices ($AAPL, $68.50)
        if token.startswith("$"):
            val = token[1:]
            if val.isalpha():
                return f"${val.upper()}"
            return token

        # 3. Known Proper Noun or casing mapping (e.g. FED -> Fed, BPS -> bps, POWELL -> Powell)
        if raw_upper in CASE_MAPPINGS:
            val = CASE_MAPPINGS[raw_upper]
            if is_sentence_start:
                return val.capitalize()
            return val

        # 4. Possessive proper nouns: FED'S -> Fed's, POWELL'S -> Powell's, US'S -> US's
        if "'" in token or "’" in token:
            quote_char = "'" if "'" in token else "’"
            parts = token.split(quote_char, 1)
            base = parts[0].upper()
            suffix = parts[1].lower()
            if base in UPPERCASE_PRESERVED:
                return f"{base}{quote_char}{suffix}"
            if base in CASE_MAPPINGS:
                return f"{CASE_MAPPINGS[base]}{quote_char}{suffix}"
            if is_sentence_start:
                return f"{base.capitalize()}{quote_char}{suffix}"
            return f"{base.lower()}{quote_char}{suffix}"

        # 5. Check if it's an alphanumeric shorthand like 10Y, 2Y, Q3
        if re.match(r"^\d+[A-Z]+$", raw_upper) or re.match(r"^[A-Z]+\d+$", raw_upper):
            return raw_upper

        # 6. Standard word casing
        lower = token.lower()
        if is_sentence_start:
            return lower.capitalize()
        return lower

    def _convert_clause_to_sentence_case(self, clause: str) -> str:
        """Converts a single clause or sentence to natural sentence case."""
        tokens = self.TOKEN_PATTERN.findall(clause)
        result = []
        is_first_word = True

        for tok in tokens:
            if not tok:
                continue

            # If token is whitespace or punctuation
            if not any(c.isalnum() for c in tok):
                result.append(tok)
                continue

            # Format the word token
            formatted = self._format_token(tok, is_sentence_start=is_first_word)
            result.append(formatted)
            is_first_word = False

        return "".join(result)

    def convert_to_sentence_case(self, text: str) -> str:
        """Splits text into clauses / sentences and applies natural sentence case."""
        # Replace known multi-word proper nouns first
        for pattern, replacement in MULTI_WORD_PROPER_NOUNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Split text into chunks preserving delimiters
        segments = self.CLAUSE_SPLIT_PATTERN.split(text)
        processed_segments = []

        for seg in segments:
            # If segment is delimiter, keep as is
            if not seg.strip() or self.CLAUSE_SPLIT_PATTERN.fullmatch(seg):
                processed_segments.append(seg)
                continue

            processed_segments.append(self._convert_clause_to_sentence_case(seg))

        return "".join(processed_segments)

    def process_text(self, text: Optional[str]) -> Optional[str]:
        """Executes full First Squawk transformation pipeline."""
        if not text:
            return None

        # Step 1: Remove @FirstSquaw mention and clean punctuation
        cleaned = self.remove_mentions(text)
        if not cleaned:
            return None

        # Step 2: Check if predominantly uppercase
        if self.is_predominantly_uppercase(cleaned):
            cleaned = self.convert_to_sentence_case(cleaned)

        # Step 3: Final whitespace cleanup
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

