#!/usr/bin/env python3
"""
Telegram News Forwarding Automation — ScrapX Media
Main entry point for running the service.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from config.settings import Settings, get_settings
from database.db_manager import DatabaseManager
from filters.faytuks import FaytuksFilter
from filters.first_squawk import FirstSquawkFilter
from core.client import TelegramClientManager
from core.monitor import ChannelMonitor
from core.publisher import MessagePublisher


def setup_logging(log_level: str) -> None:
    """Configures structured console and file logging."""
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "scrapx.log"

    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress verbose telethon internal logs unless DEBUG
    if level > logging.DEBUG:
        logging.getLogger("telethon").setLevel(logging.WARNING)


def run_rule_tests() -> None:
    """Demonstrates and verifies filtering rules on sample messages in the terminal."""
    print("=" * 70)
    print("  ScrapX Media — Filter Rules Verification Demo")
    print("=" * 70)

    # First Squawk tests
    fs_filter = FirstSquawkFilter()
    sample_fs_messages = [
        "US STOCKS RISE AS INFLATION DATA SHOWS SIGNS OF COOLING @FirstSquaw",
        "FED'S POWELL: WE ARE COMMITTED TO BRINGING INFLATION DOWN TO 2% @FirstSquaw",
        "TESLA (TSLA) Q3 DELIVERIES BEAT ESTIMATES AT 462,890 VEHICLES @FirstSquawk",
        "OIL DROPS 2.5% TO $68.50 AS OPEC+ CONSIDERS PRODUCTION HIKE - @FirstSquaw",
        "ECB CUTS RATES BY 25 BPS; S&P 500 FUTURES UP 0.3%",
        "@FirstSquaw: BREAKING NEWS ON WALL STREET",
    ]

    print("\n--- [First Squawk Transformations] ---")
    for msg in sample_fs_messages:
        transformed = fs_filter.process_text(msg)
        print(f"\n[ORIGINAL]   : {msg}")
        print(f"[TRANSFORMED]: {transformed}")

    # Faytuks tests
    faytuks_filter = FaytuksFilter()
    sample_faytuks_messages = [
        "BREAKING: Oil prices climb. Read more: https://example.com/faytuks-network/article",
        "UKRAINE: Air defense systems active in Kyiv. More details: https://t.me/faytuks/98765",
        "White House announces new economic measures. Source: https://www.reuters.com/business/economy-update",
        "Multiple reports of explosions. Read on [Faytuks Network](https://t.me/faytuks) or check [Bloomberg](https://bloomberg.com/news).",
    ]

    print("\n--- [Faytuks Network Transformations] ---")
    for msg in sample_faytuks_messages:
        transformed = faytuks_filter.process_text(msg)
        print(f"\n[ORIGINAL]   : {msg}")
        print(f"[TRANSFORMED]: {transformed}")

    print("\n" + "=" * 70)
    print("  Rule Verification Completed Successfully!")
    print("=" * 70)


async def run_auth_only(settings: Settings) -> None:
    """Runs one-time authentication to create the Telethon session file."""
    client_mgr = TelegramClientManager(settings)
    try:
        await client_mgr.start()
        print("\n✅ Telegram session successfully authenticated and saved!")
        print(f"Session file saved at: {client_mgr.session_path}.session")
    finally:
        await client_mgr.stop()


async def main_async(args: argparse.Namespace) -> None:
    settings = get_settings()

    # Override dry_run if passed via CLI
    if args.dry_run:
        settings.dry_run = True

    setup_logging(settings.log_level)
    logger = logging.getLogger("scrapx.main")

    logger.info("Starting ScrapX Media Telegram News Forwarding Automation...")
    logger.info("Mode: %s", "DRY-RUN (Simulated Publishing)" if settings.dry_run else "LIVE PRODUCTION")

    # Validate settings before connecting
    try:
        settings.validate()
    except ValueError as e:
        logger.error("%s", e)
        print("\n❌ Configuration Error. Please review your .env file.")
        print(e)
        sys.exit(1)

    # Initialize Database
    db_mgr = DatabaseManager(settings.database_path)

    if args.stats:
        stats = db_mgr.get_statistics()
        print("\n📊 Database Statistics:")
        print(f"Breakdown: {stats['breakdown']}")
        print(f"Watermarks: {stats['watermarks']}")
        return

    # Initialize Client Manager
    client_mgr = TelegramClientManager(settings)
    client = await client_mgr.start()

    try:
        # Resolve Destination Channel (ScrapX Media)
        dest_target = settings.parsed_scrapx_media
        logger.info("Resolving destination channel: %s...", dest_target)
        dest_entity = await client_mgr.resolve_entity(dest_target)

        # Initialize Publisher
        publisher = MessagePublisher(
            client=client,
            destination_entity=dest_entity,
            dry_run=settings.dry_run,
        )

        # Initialize Monitor
        monitor = ChannelMonitor(
            client=client,
            publisher=publisher,
            db_manager=db_mgr,
            settings=settings,
        )

        # Register Source Channels
        if settings.enable_first_squawk:
            fs_target = settings.parsed_first_squawk
            logger.info("Resolving source channel: First Squawk (%s)...", fs_target)
            fs_entity = await client_mgr.resolve_entity(fs_target)
            monitor.register_channel(
                channel_entity=fs_entity,
                channel_key="first_squawk",
                display_name="First Squawk",
                filter_instance=FirstSquawkFilter(),
            )

        if settings.enable_faytuks:
            fn_target = settings.parsed_faytuks_network
            logger.info("Resolving source channel: Faytuks Network (%s)...", fn_target)
            fn_entity = await client_mgr.resolve_entity(fn_target)
            monitor.register_channel(
                channel_entity=fn_entity,
                channel_key="faytuks",
                display_name="Faytuks Network",
                filter_instance=FaytuksFilter(),
            )

        # Attach Event Listener
        monitor.start_listening()

        # Start lightweight HTTP health-check server if PORT is configured or for cloud platforms
        http_port = int(os.getenv("PORT", "8080")) if os.getenv("PORT") else None
        http_server = None
        if http_port:
            async def _http_handler(reader, writer):
                await reader.read(512)
                resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 15\r\n\r\nScrapX Media OK"
                writer.write(resp)
                await writer.drain()
                writer.close()

            http_server = await asyncio.start_server(_http_handler, "0.0.0.0", http_port)
            logger.info("Cloud Health-Check HTTP server listening on port %d", http_port)

        # Handle graceful shutdown on signals
        stop_event = asyncio.Event()

        def _handle_exit_signal():
            logger.info("Received shutdown signal. Stopping monitoring gracefully...")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_exit_signal)
            except NotImplementedError:
                # Windows does not support add_signal_handler on ProactorEventLoop
                pass

        logger.info("ScrapX Media automation service is active and running.")
        logger.info("Press Ctrl+C to terminate.")

        # Keep running until stop event or client disconnects
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                if not client.is_connected():
                    logger.warning("Telegram connection dropped. Telethon is auto-reconnecting...")

    except asyncio.CancelledError:
        logger.info("Operation cancelled.")
    except Exception as e:
        logger.critical("Fatal error encountered in main loop: %s", e, exc_info=True)
        raise
    finally:
        logger.info("Cleaning up and disconnecting Telegram client...")
        await client_mgr.stop()
        logger.info("Shutdown complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ScrapX Media — Real-Time Telegram News Forwarding Automation",
    )
    parser.add_argument(
        "--test-rules",
        action="store_true",
        help="Run formatting and filtering rules against sample messages and exit.",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Run one-time interactive login to generate the Telegram session file and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run monitoring in dry-run mode without publishing messages to destination.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display database processed message statistics and exit.",
    )

    args = parser.parse_args()

    if args.test_rules:
        run_rule_tests()
        sys.exit(0)

    if args.auth_only:
        settings = get_settings()
        setup_logging(settings.log_level)
        asyncio.run(run_auth_only(settings))
        sys.exit(0)

    try:
        asyncio.run(main_async(args))
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()

