# Toygres

Toygres is a lightweight CLI tool for frictionless PostgreSQL database management and intelligent monitoring, tailored for rapid testing.

## Core Features

### The Disposable Database
Built for quick testing environments.
- **One-Keystroke Setup:** Spin up a completely new database instantly.
- **Instant Teardown:** Delete or reset to a clean slate with a single key press.

**Example Use Case:**
You are running integration tests and your test suite fails halfway through, leaving your database in a dirty state. Instead of writing a teardown script, you press `Ctrl+R` to instantly drop and recreate the test database.

### AI-Powered Observer Agent
A continuous monitor for your data, powered by AI.
- **Real-time Monitoring:** Track specific row changes without writing polling scripts.
- **Natural Language Prompts:** Tell the agent what to monitor in plain English; no SQL required.

**Example Use Case:**
You are testing an asynchronous background worker that processes orders. You deploy an Observer Agent with the prompt: _"Watch the 'orders' table for order ID 12345. Alert me the moment its status changes from 'pending' to 'completed'."_ The agent runs in the background and prints the result as soon as the worker finishes the job.

### Baseline Resets
Save time by starting from a pre-configured state.
- **Save State:** Configure essential data (e.g., super-admin, app configs) and save it as a "baseline".
- **One-Click Recreate:** Delete and recreate your database from the baseline instantly.

**Example Use Case:**
Your application requires a default "admin" user and several lookup tables (like countries and currencies) to be populated before it can start. You set this up once, run the "Create Baseline" command, and name it `app_defaults`. Now, whenever you reset your database, you can choose to reset from `app_defaults`, and your admin user and lookup tables are instantly restored.

## Installation

Ensure you have Python 3.11+ installed. Clone the repository and install dependencies using `uv`:

```bash
git clone <repository_url>
cd toygres
uv sync
```

## Usage

Start Toygres using the provided `Makefile` command:

```bash
make start
```
