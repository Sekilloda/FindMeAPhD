# 🎓 Hypatia — Autonomous PhD Opportunity Monitor & Multi-Agent Swarm

Hypatia is an autonomous, multi-agent AI system designed to discover, track, deduplicate, evaluate, and dossier PhD positions in **Theoretical Quantum Physics & High-Energy Phenomenology** (QCD, hadronization histories, quantum computing/witness circuits, and particle physics).

It runs headlessly in the background on macOS (even when the machine is locked or unattended), harvesting academic job feeds, filtering candidates using local or cloud LLMs, generating detailed application guidance dossiers, and dispatching rich email alerts via the **Gmail API** with a persistent **Outbox Queue**.

---

## 🌟 Key Features

### 1. Multi-Portal Live Ingestion Feeds
Hypatia ingests academic postings from five primary portals:
- **InspireHEP**: REST API (`inspirehep.net/api/jobs`) filtered for open doctoral and research positions.
- **Quantiki**: Quantum information and theoretical physics portal (`quantiki.org/jobs`).
- **CERN**: Direct REST API integration via SmartRecruiters (`api.smartrecruiters.com/v1/companies/CERN/postings`), filtered for experimental/theoretical physics and research roles.
- **DESY**: Direct crawler for Deutsches Elektronen-Synchrotron vacancies (`desy.de/career/job_offers/`), extracting reference IDs, topics, and deadlines.
- **Scandinavian Universities (Varbi)**: Directly scrapes major Nordic institutions:
  - **Lund University** (Theoretical Physics & Astronomy)
  - **Stockholm University** (Quantum Physics & Condensed Matter)
  - **Uppsala University** (Quantum Verification & Materials)
  - **KTH Royal Institute of Technology** (Applied Physics & Quantum Engineering)

### 2. Cross-Source Intelligent Deduplication ([`core/deduplicator.py`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/core/deduplicator.py))
When the same vacancy is advertised across multiple portals (e.g., CERN posting on InspireHEP, or Stockholm posting on Quantiki and Varbi), the `DuplicateDetector`:
- Normalizes canonical URLs and secondary application URLs.
- Strips academic portal noise, job reference codes, and generic prefixes.
- Normalizes multilingual institution names (e.g. *Stockholms universitet* $\to$ *Stockholm University*).
- Applies compound fuzzy matching (SequenceMatcher + Jaccard token containment + deadline delta) to merge cross-portal duplicates into a unified record without duplicate alerts.
- Verified with a dedicated 9-case real-world test suite ([`tests/test_deduplicator_real.py`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/tests/test_deduplicator_real.py)).

### 3. Dual Evaluation Architecture: Local llama-server & Cloud Cascade
- **Primary (Local Apple Silicon)**: Hits `llama-server` router on `http://127.0.0.1:8080` (e.g. Qwen 2.5 / Gemma 2). Automatically unloads models from Unified Memory (VRAM) after each evaluation cycle to conserve system RAM.
- **Secondary (Cloud Cascade)**: If local models are unavailable, seamlessly cascades across Groq, Google Gemini, and OpenRouter with automatic rate-limit and error fallback.

### 4. Application Dossier Generator ([`core/dossier.py`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/core/dossier.py))
For top-match postings ($\ge 7.5/10$), Hypatia synthesizes an application package stored in `applications/<id>_<title>/`:
- **Academic Alignment**: Research synergy mapping your background to the project.
- **PI & Group Talking Points**: Key literature connections and conversational hooks.
- **Cover Letter Strategy**: Structured outline highlighting Lund string model, QCD hadronization, or quantum witness circuit synergies.
- **Red Flags & Inquiries**: Administrative, funding, or visa inquiries to raise early.

### 5. Dynamic Google Calendar Deadlines ([`core/calendar_sync.py`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/core/calendar_sync.py))
While email alerts are great, their deadline counters (e.g. *"Only 10 days left"*) remain frozen relative to when the message was composed. 
Hypatia integrates directly with **Google Calendar** to provide an **always-updated, dynamic point of reference**:
- **Automatic All-Day Events**: Places bold, red-flagged events (`🚨 [Deadline] 🎓 [Score/10] Title - Institution`) on the exact deadline date.
- **Dedicated Secondary Calendar**: Automatically creates and syncs to a dedicated `🎓 Hypatia PhD Deadlines` calendar, allowing you to toggle PhD deadlines on/off on your Mac, iPhone, or browser without cluttering personal events.
- **Multi-Stage Preparation Reminders**: Configured with pop-up alarms 14 days, 7 days, 3 days, 1 day before, and at 9:00 AM on the day of the deadline.
- **Full Dossier in Description**: Event description includes total match score, category breakdowns, direct application URLs, InspireHEP records, and application pointers.

### 6. Persistent Outbox Queue & Structured Signal
- **Zero Alert Loss**: If dispatch fails or internet is disconnected, alerts are serialized to [`outbox/*.json`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/outbox).
- **Auto-Flush**: Queued alerts are automatically dispatched at the start and end of every run.
- **Sent Archive**: Successfully dispatched alerts are archived in [`outbox/sent/`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/outbox/sent).
- **Structured Exit Signal**: Emits `HYPATIA_SIGNAL:{"status": "completed", ...}` for integration with macOS Shortcuts, launchd, or external automation wrappers.

---

## 📧 Email Integration Tutorial (Gmail API & SMTP)

Hypatia supports sending rich HTML and plain-text email alerts to `danielgarciavillacanas@protonmail.com` directly from `daniel.programa.cometa@gmail.com`.

### Why Headless API instead of AppleScript?
Previously, alerts were dispatched through Apple Mail via AppleScript (`osascript`). However, when macOS is locked or the screen is asleep, WindowServer suspends GUI AppleEvents, causing `AppleEvent timed out (-1712)`. 

The **Gmail REST API** and **Gmail SMTP** communicate directly over headless TCP/HTTPS sockets, functioning **100% reliably in the background while macOS is locked or unattended**.

---

### Method A: Gmail REST API via OAuth 2.0 (Recommended)

This method uses Google's official REST API with a minimal, send-only permission scope (`https://www.googleapis.com/auth/gmail.send`). It **cannot** read, delete, or search your inbox.

#### Step 1: Ensure Google Calendar API is Enabled
1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/dashboard).
2. Under **Enabled APIs & Services**, ensure both **Gmail API** and **Google Calendar API** are enabled. (If Calendar is not enabled, click **+ Enable APIs and Services**, search for **Google Calendar API**, and click **Enable**).
3. Ensure `credentials.json` is in the project root.

#### Step 2: Authorize (One-Time)
Run the setup utility to approve both Gmail dispatch and Google Calendar event management:
```bash
./venv/bin/python scripts/setup_google.py --oauth
```
- A browser window will open automatically.
- Sign in with `daniel.programa.cometa@gmail.com` and approve permissions.
- The script automatically updates `token.json` with permissions locked to `600` (owner-only).
- Hypatia is now fully authorized to send alerts and create calendar deadlines headlessly forever.

#### Step 3: Retroactively Sync Existing High-Fit Deadlines
To instantly populate your Google Calendar with all high-scoring positions already discovered:
```bash
./venv/bin/python core/calendar_sync.py --sync
```

---

### Method B: Gmail App Password (SMTP over TLS) — *Alternative*

If you prefer not to use the Google Cloud Console, you can generate a 16-character Google App Password:

1. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification enabled).
2. Enter an app name (e.g., `Hypatia`) and click **Create**.
3. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`).
4. Save it using the helper tool:
   ```bash
   ./venv/bin/python scripts/setup_gmail.py --app-password "abcd efgh ijkl mnop"
   ```
   *(This saves `GMAIL_APP_PASSWORD` into `.env`, which is strictly ignored by git).*

---

### Testing & Verification

1. **Check Configuration Status (Gmail + Calendar)**:
   ```bash
   ./venv/bin/python scripts/setup_google.py --status
   ```
2. **Send a Live Test Alert (Email + Calendar Event)**:
   ```bash
   ./venv/bin/python scripts/setup_google.py --test
   ```
3. **Retroactively Sync All High-Scoring Deadlines to Calendar**:
   ```bash
   ./venv/bin/python core/calendar_sync.py --sync
   ```
4. **Inspect the Outbox Queue**:
   ```bash
   ./venv/bin/python core/mailer.py --status
   ```
5. **Manually Flush Pending Alerts**:
   ```bash
   ./venv/bin/python core/mailer.py --flush
   ```

---

## 🔒 Security & Permissions Management

### macOS Permissions Audit & Clean-up

| Permission / Component | Initial Purpose | Current Status | Recommended Action |
| :--- | :--- | :--- | :--- |
| **AppleEvents Automation (`Mail.app`)** | AppleScript email sending | ❌ **Obsolete** | **Revoke**: In *System Settings $\to$ Privacy & Security $\to$ Automation*, toggle off `Mail` for Terminal/Python, or run `tccutil reset AppleEvents`. |
| **`Hypatia.app` Bundle** | Early launchd background test | ❌ **Obsolete** | **Deleted**: Removed from disk. |
| **LaunchAgent (`com.hypatia.phdmonitor`)** | 12-hour background trigger | ✅ **Active** | **Keep**: Runs `/usr/bin/shortcuts run "Hypatia PhD Monitor"`. |
| **Shortcuts App (`Hypatia PhD Monitor`)** | Headless scheduler | ✅ **Active** | **Keep**: Clean macOS background agent. |
| **Gmail OAuth Token (`token.json`)** | Headless send API | ✅ **Active** | **Protected**: Permissions locked to `600`, git-ignored. |

---

## 🚀 Autonomous Background Scheduling (Every 12 Hours)

Hypatia is configured to run automatically every 12 hours via macOS launchd and Apple Shortcuts.

### Managing the Background Schedule

Use the helper script [`scripts/setup_schedule.sh`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/scripts/setup_schedule.sh):

```bash
# Check status of the launchd agent
./scripts/setup_schedule.sh status

# Install and start the 12-hour periodic monitor
./scripts/setup_schedule.sh install

# Stop and uninstall the periodic monitor
./scripts/setup_schedule.sh uninstall
```

### Logs & Alerts Digest
- **Console Log**: [`monitor.log`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/monitor.log)
- **Error Log**: [`monitor.err`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/monitor.err)
- **Top Matches Digest**: [`phd_alerts.md`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/phd_alerts.md) (All $\ge 7.5/10$ matches appended here)
- **Application Packages**: [`applications/`](file:///Users/daniel/GitHub%20repos/FindMeAPhD/applications/)

---

## 🧪 Testing

Run the automated test suite anytime:

```bash
# Run Outbox Queue unit tests
./venv/bin/python -m unittest tests/test_outbox_queue.py

# Run Real-World Cross-Source Deduplication tests (9/9 real cases)
./venv/bin/python tests/test_deduplicator_real.py

# Run all tests
./venv/bin/python -m unittest discover tests/
```

---

## 🛠 Manual Execution

To run a manual harvest and evaluation run:

```bash
# Run monitor with default limit and threshold
./venv/bin/python monitor.py

# Fetch up to 100 listings with a 8.0/10 threshold, keeping model in RAM
./venv/bin/python monitor.py --limit 100 --threshold 8.0 --keep-loaded
```
