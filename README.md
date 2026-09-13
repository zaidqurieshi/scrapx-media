# Telegram News Forwarding Automation — ScrapX Media

Production-ready Telegram automation system built with Python and Telethon. It monitors **First Squawk** and **Faytuks Network** in real-time, sanitizes text and links according to channel-specific formatting rules, and publishes clean messages, single media, and media groups directly to **ScrapX Media** without forward headers.

---

## Architecture & Design Overview

```
                      ┌──────────────────────────────────────┐
                      │            Source Channels           │
                      │  First Squawk   &   Faytuks Network  │
                      └──────────────────┬───────────────────┘
                                         │ Real-Time MTProto Events
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    Telethon Client (User Account)    │
                      └──────────────────┬───────────────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 [Single Message]              [Media Group / Album]
                         │                               │
                         │                   Debounce Buffer (1.5s)
                         │                   Gather sibling items by
                         │                   grouped_id, sort by ID
                         │                               │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │         Deduplication Check          │
                      │   (Persistent SQLite scrapx_media.db)│
                      └──────────────────┬───────────────────┘
                                         │ If not already processed
                                         ▼
                      ┌──────────────────────────────────────┐
                      │        Rules & Filters Engine        │
                      │                                      │
                      │  • First Squawk:                     │
                      │    - Predominant uppercase detection │
                      │    - Sentence capitalization         │
                      │    - Ticker & proper noun protection │
                      │    - Strips @FirstSquaw mention      │
                      │                                      │
                      │  • Faytuks Network:                  │
                      │    - Faytuks URL & anchor removal    │
                      │    - Preserves external news links   │
                      │    - Punctuation & prompt cleanup    │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │        Content Copy Publisher        │
                      │     (Publishes to ScrapX Media       │
                      │      without Forwarded-from tag)     │
                      └──────────────────┬───────────────────┘
                                         │ On Successful Send
                                         ▼
                      ┌──────────────────────────────────────┐
                      │   Transactional State Persistence    │
                      │ (Record message ID & channel mark)   │
                      └──────────────────────────────────────┘
```

### Why a Telegram User Account (Telethon) Instead of a Bot?

* **Telegram Bot API Limitation:** Telegram bots **cannot** read or monitor messages from public or private channels unless the bot is added as an administrator by the owner of that channel. Because *First Squawk* and *Faytuks Network* are third-party news channels, a bot cannot monitor them.
* **Telethon MTProto User Client:** A Telegram user account that is joined or subscribed to both channels receives all updates in real-time via Telegram's native MTProto protocol.
* **Clean Publishing (No Forward Headers):** Rather than calling `forward_messages` (which Telegram tags with "Forwarded from First Squawk"), this system extracts the media and text, applies the transformation rules, and publishes a fresh post via `send_message` or `send_file`.

---

## Project Structure

```
ScrapX Project/
├── config/
│   ├── __init__.py
│   └── settings.py          # Environment settings loader and channel target parser
├── core/
│   ├── __init__.py
│   ├── client.py            # Telethon client wrapper & FloodWait handler
│   ├── monitor.py           # Real-time NewMessage listener & album debouncer
│   └── publisher.py         # Content copier (text, single media, albums)
├── database/
│   ├── __init__.py
│   └── db_manager.py        # SQLite persistence, WAL mode, deduplication
├── filters/
│   ├── __init__.py          # Filter registry & factory
│   ├── base.py              # BaseMessageFilter abstract class
│   ├── first_squawk.py      # Sentence casing, ticker preservation, mention removal
│   └── faytuks.py           # Faytuks link stripping & external URL preservation
├── logs/                    # Rotating application logs (scrapx.log)
├── data/                    # Persistent database and session storage
├── tests/
│   ├── __init__.py
│   └── test_rules.py        # Unit tests covering all rules and edge cases
├── .env.example             # Template environment variables
├── .env                     # User environment configuration (do not commit)
├── main.py                  # CLI entry point with --test-rules, --dry-run, --auth-only
├── requirements.txt         # Project dependencies
└── README.md                # Full documentation and operating manual
```

---

## Quick Start Guide

### Step 1: Obtain Telegram API Credentials

1. Open a browser and log in to [https://my.telegram.org](https://my.telegram.org) with your Telegram phone number.
2. Click on **API development tools**.
3. Create a new application (e.g. App title: `ScrapX Automation`, Short name: `scrapx`).
4. Copy your **`api_id`** (numeric, e.g. `12345678`) and **`api_hash`** (32-character hex string).

---

### Step 2: Configure ScrapX Media Destination Channel

1. Open Telegram and navigate to your destination channel: **ScrapX Media**.
2. Open Channel Settings > **Administrators** > **Add Administrator**.
3. Add your Telegram account (the one you are authenticating with Telethon).
4. Ensure the administrator permissions include:
   - ✅ **Post Messages**
   - ✅ **Edit Messages**

---

### Step 3: Setup on Windows (PowerShell / CMD)

#### 1. Open PowerShell or Command Prompt
Open PowerShell as a normal user and navigate to the project folder:
```powershell
cd "C:\path\to\ScrapX Project"
```

#### 2. Verify Python 3.9+ Installation
```powershell
python --version
```
*(If python is not installed, install Python 3.10+ from [python.org](https://www.python.org/downloads/) and ensure "Add python.exe to PATH" is checked).*

#### 3. Create and Activate Virtual Environment
```powershell
python -m venv venv

# If using PowerShell:
.\venv\Scripts\Activate.ps1

# If PowerShell blocks script execution, run:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# .\venv\Scripts\Activate.ps1

# If using Command Prompt (cmd.exe):
# .\venv\Scripts\activate.bat
```

#### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 5. Configure `.env`
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Edit `.env` using Notepad or your editor:
```ini
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_32_char_api_hash_here
TELEGRAM_SESSION_NAME=scrapx_session

FIRST_SQUAWK_CHANNEL=@FirstSquawk
FAYTUKS_NETWORK_CHANNEL=@faytuks
SCRAPX_MEDIA_CHANNEL=@ScrapXMedia

ENABLE_FIRST_SQUAWK=true
ENABLE_FAYTUKS=true
DRY_RUN=false
```

---

### Step 4: Setup on macOS / Linux

```bash
cd "ScrapX Project"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # or open in VS Code / text editor
```

---

## Verification & Testing

### 1. Run Formatting Rules Verification
Test the text transformation and link stripping logic against sample messages without connecting to Telegram:
```bash
python main.py --test-rules
```
Sample Output:
```
--- [First Squawk Transformations] ---
[ORIGINAL]   : US STOCKS RISE AS INFLATION DATA SHOWS SIGNS OF COOLING @FirstSquaw
[TRANSFORMED]: US stocks rise as inflation data shows signs of cooling

[ORIGINAL]   : FED'S POWELL: WE ARE COMMITTED TO BRINGING INFLATION DOWN TO 2% @FirstSquaw
[TRANSFORMED]: Fed's Powell: We are committed to bringing inflation down to 2%

--- [Faytuks Network Transformations] ---
[ORIGINAL]   : BREAKING: Oil prices climb. Read more: https://example.com/faytuks-network/article
[TRANSFORMED]: BREAKING: Oil prices climb.

[ORIGINAL]   : White House announces new economic measures. Source: https://www.reuters.com/business/economy-update
[TRANSFORMED]: White House announces new economic measures. Source: https://www.reuters.com/business/economy-update
```

### 2. Run Automated Unit Tests
Run the comprehensive test suite verifying filters and database persistence:
```bash
pytest tests/test_rules.py -v
```

### 3. One-Time Telegram Authentication
Authenticate your Telegram account in the terminal:
```bash
python main.py --auth-only
```
- Telethon will prompt you to enter your **phone number** (with international code, e.g. `+1...` or `+44...`).
- Telegram will send an authentication code to your Telegram app. Enter the code.
- If 2-Factor Authentication (2FA) is enabled, enter your password.
- A session file will be created in `data/scrapx_session.session`. You will not need to enter your phone number again.

### 4. Test in Dry-Run Mode with Real Telegram Messages
Start the live listener in **dry-run** mode. The system will connect to Telegram, listen to *First Squawk* and *Faytuks Network*, transform any incoming messages, and log the exact transformed text without posting to ScrapX Media:
```bash
python main.py --dry-run
```

---

## Production Deployment

Once tested in dry-run mode, start the live production monitor:
```bash
python main.py
```

### Running Continuously on Windows

#### Option A: Windows Task Scheduler (Built-in)
1. Open **Task Scheduler** from the Start Menu.
2. Click **Create Task...** on the right.
3. On the **General** tab:
   - Name: `ScrapX Media Automation`
   - Select: *Run whether user is logged on or not*.
4. On the **Triggers** tab:
   - New Trigger > Begin the task: *At startup*.
5. On the **Actions** tab:
   - Action: *Start a program*.
   - Program/script: `C:\path\to\ScrapX Project\venv\Scripts\python.exe`
   - Add arguments: `main.py`
   - Start in: `C:\path\to\ScrapX Project`
6. Click **OK** and save.

#### Option B: NSSM (Non-Sucking Service Manager — Recommended for Windows)
Download `nssm` from [nssm.cc](https://nssm.cc/) and install as a background Windows Service:
```powershell
nssm install ScrapXMedia "C:\path\to\ScrapX Project\venv\Scripts\python.exe" "main.py"
nssm set ScrapXMedia AppDirectory "C:\path\to\ScrapX Project"
nssm start ScrapXMedia
```

---

### Running Continuously on Linux / macOS

#### Using systemd (Ubuntu / Debian / CentOS):
Create `/etc/systemd/system/scrapx.service`:
```ini
[Unit]
Description=ScrapX Media Telegram Automation
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/ScrapX Project
ExecStart=/path/to/ScrapX Project/venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scrapx
sudo systemctl start scrapx
sudo systemctl status scrapx
```

---

## Monitoring & Database Inspection

To view the current statistics of tracked and published messages:
```bash
python main.py --stats
```

Example output:
```
📊 Database Statistics:
Breakdown: {'first_squawk': {'published': 48}, 'faytuks': {'published': 32}}
Watermarks: {'first_squawk': 18452, 'faytuks': 9231}
```

View application logs in real-time:
- Windows PowerShell:
  ```powershell
  Get-Content -Path logs\scrapx.log -Wait -Tail 30
  ```
- Linux / macOS:
  ```bash
  tail -f logs/scrapx.log
  ```

---

## Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `Cannot find channel @...` | Channel handle is incorrect or account hasn't joined | Ensure your Telegram account is subscribed to `@FirstSquawk` and `@faytuks`. You can also use channel numeric IDs (`-100...`). |
| `ChatAdminRequiredError` | Account lacks admin rights in ScrapX Media | Make sure your Telegram account is added as an Administrator in ScrapX Media with **Post Messages** permission. |
| `FloodWaitError: A wait of X seconds is required` | Telegram rate limit hit | Telethon automatically handles this by sleeping `X + 1` seconds before retrying. Do not repeatedly restart the script. |
| `sqlite3.OperationalError: database is locked` | Concurrent database access | SQLite is configured with WAL mode (`PRAGMA journal_mode=WAL;`) and a 5-second busy timeout to prevent locking. |
| `SessionPasswordNeededError` | Two-Factor Authentication (2FA) is enabled | Run `python main.py --auth-only` and enter your 2FA password when prompted. |
| Fragmented Media Albums | Messages arriving as separate posts | The built-in album debouncer gathers all messages sharing `grouped_id` over 1.5 seconds and publishes them as a unified album. Adjust `MEDIA_GROUP_DEBOUNCE_SECONDS` in `.env` if your network has high latency. |

---

## Extending with More Channels

To add a new channel (e.g. `Bloomberg Wire`):
1. Create a new filter in `filters/bloomberg.py` inheriting from `BaseMessageFilter`.
2. Register it in `filters/__init__.py`.
3. Add the channel configuration to `.env` and `config/settings.py`.
4. Register the channel in `main.py` using `monitor.register_channel(...)`.

