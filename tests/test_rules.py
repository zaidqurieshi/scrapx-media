"""Unit tests for ScrapX Media message filters and database persistence."""
import os
import tempfile
import unittest

from database.db_manager import DatabaseManager
from filters.faytuks import FaytuksFilter
from filters.first_squawk import FirstSquawkFilter


class TestFirstSquawkFilter(unittest.TestCase):
    def setUp(self):
        self.filter = FirstSquawkFilter()

    def test_example_from_prompt(self):
        original = "US STOCKS RISE AS INFLATION DATA SHOWS SIGNS OF COOLING @FirstSquaw"
        expected = "US stocks rise as inflation data shows signs of cooling"
        result = self.filter.process_text(original)
        self.assertEqual(result, expected)

    def test_mention_removal_variants(self):
        cases = [
            ("US GDP GROWS 3.0% @FirstSquawk", "US GDP grows 3.0%"),
            ("US GDP GROWS 3.0% - @FirstSquaw", "US GDP grows 3.0%"),
            ("@FirstSquaw: BREAKING NEWS ON WALL STREET", "Breaking news on Wall Street"),
            ("@FirstSquaw", None),
            ("   @FirstSquawk   ", None),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(self.filter.process_text(original), expected)

    def test_tickers_and_indicators(self):
        original = "FED'S POWELL: WE ARE COMMITTED TO BRINGING INFLATION DOWN TO 2% @FirstSquaw"
        expected = "Fed's Powell: We are committed to bringing inflation down to 2%"
        self.assertEqual(self.filter.process_text(original), expected)

        original_tickers = "TESLA (TSLA) Q3 DELIVERIES BEAT ESTIMATES AT 462,890 VEHICLES"
        expected_tickers = "Tesla (TSLA) Q3 deliveries beat estimates at 462,890 vehicles"
        self.assertEqual(self.filter.process_text(original_tickers), expected_tickers)

        original_opec = "OIL DROPS 2.5% TO $68.50 AS OPEC+ CONSIDERS PRODUCTION HIKE"
        expected_opec = "Oil drops 2.5% to $68.50 as OPEC+ considers production hike"
        self.assertEqual(self.filter.process_text(original_opec), expected_opec)

        original_ecb = "ECB CUTS RATES BY 25 BPS; S&P 500 FUTURES UP 0.3%"
        expected_ecb = "ECB cuts rates by 25 bps; S&P 500 futures up 0.3%"
        self.assertEqual(self.filter.process_text(original_ecb), expected_ecb)

        original_btc = "BITCOIN RISES ABOVE $65,000 AS $NVDA REACHES NEW ATH"
        expected_btc = "Bitcoin rises above $65,000 as $NVDA reaches new ATH"
        self.assertEqual(self.filter.process_text(original_btc), expected_btc)

    def test_already_mixed_case_not_ruined(self):
        original = "Apple announced the new iPhone 16 with AI capabilities @FirstSquaw"
        expected = "Apple announced the new iPhone 16 with AI capabilities"
        self.assertEqual(self.filter.process_text(original), expected)


class TestFaytuksFilter(unittest.TestCase):
    def setUp(self):
        self.filter = FaytuksFilter()

    def test_example_from_prompt(self):
        original = "BREAKING: Oil prices climb. Read more: https://example.com/faytuks-network/article"
        expected = "BREAKING: Oil prices climb."
        result = self.filter.process_text(original)
        self.assertEqual(result, expected)

    def test_faytuks_telegram_and_twitter_links(self):
        original = "UKRAINE UPDATE: Air alert declared across southern regions.\n\nRead more: https://t.me/faytuks/12345"
        expected = "UKRAINE UPDATE: Air alert declared across southern regions."
        self.assertEqual(self.filter.process_text(original), expected)

    def test_preserves_external_links(self):
        original = "White House issues statement on Gaza ceasefire negotiations. Full report: https://www.reuters.com/world/middle-east/gaza-talks"
        expected = "White House issues statement on Gaza ceasefire negotiations. Full report: https://www.reuters.com/world/middle-east/gaza-talks"
        self.assertEqual(self.filter.process_text(original), expected)

    def test_markdown_links_handling(self):
        original = "Major developments unfolding. Read on [Faytuks Network](https://t.me/faytuks) or see [Bloomberg](https://bloomberg.com/news/123)."
        result = self.filter.process_text(original)
        self.assertIn("https://bloomberg.com/news/123", result)
        self.assertNotIn("faytuks", result.lower())

    def test_only_faytuks_link_returns_none(self):
        original = "https://t.me/faytuks"
        self.assertIsNone(self.filter.process_text(original))


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_scrapx.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deduplication_flow(self):
        channel = "first_squawk"
        msg_id = 1001

        # Initially not processed
        self.assertFalse(self.db.is_message_processed(channel, msg_id))

        # Mark as published
        self.db.mark_published(channel, msg_id, dest_channel="scrapx_media", dest_msg_id=5001)

        # Now processed
        self.assertTrue(self.db.is_message_processed(channel, msg_id))

        # Check watermark
        self.assertEqual(self.db.get_last_processed_id(channel), msg_id)

    def test_dry_run_tracking(self):
        channel = "first_squawk"
        msg_id = 1002

        self.db.mark_dry_run(channel, msg_id)
        self.assertTrue(self.db.is_message_processed(channel, msg_id))

    def test_failure_tracking(self):
        channel = "faytuks"
        msg_id = 2002

        self.db.mark_failed(channel, msg_id, error_message="Network timeout")
        # A failed message should NOT be considered successfully processed (allowing safe retry)
        self.assertFalse(self.db.is_message_processed(channel, msg_id))


if __name__ == "__main__":
    unittest.main()

