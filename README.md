# Toygres

A blazing fast, lightweight CLI for PostgreSQL built around disposable databases and manual testing. Stop writing teardown scripts. Stop juggling on usernames and passwords when you just want a clean DB for instant testing. Toygres makes this effortless. AND MUCH MORE!

---

## The Problem

Manual DB testing is painful—your server crashed mid-login test and left partial data? Now retesting means the same loop: drop the DB, rerun migrations, reseed, repeat… sometimes hundreds of times while chasing a single bug.

Debugging data issues is no better — you write throwaway queries and re-run them manually, waiting to catch a change that may have already happened.

Toygres eliminates both. All in natural language.

---

## Core Features

### 1. Instant Disposable Databases

Spin up a new PostgreSQL database instantly through a simple interactive CLI — no prompts for usernames, passwords, or hostnames. Create it, use it, and drop it just as fast when you are done.

**Example:** Your integration test suite fails halfway through and leaves the database in a dirty state. Instead of writing a teardown script, hit reset from the CLI and start clean in under a second.
https://github.com/user-attachments/assets/1e5c64cd-a86f-48a4-ab46-ba2c03c257b0

---

### 2. Baseline Databases

Save a pre-configured database state as a named baseline and restore to it any time with a single selection. Think of it as a constructor for your database — you get a fresh instance but with your required seed data already in place.

**Example:** Your app requires an admin user, a set of country codes, and default app config rows before it can run. Configure this once, save it as a baseline, and every future reset restores all of it automatically.

---

### 3. Observer Agent

Describe what you want to watch in plain English. The agent monitors your database in real time and alerts you the moment a matching change occurs — no polling scripts, no SQL triggers required.

**Example:** You are debugging an async background worker. Instead of manually querying the database every few seconds, set up an Observer Agent with a prompt like "Alert me when order 12345 changes status from pending to completed" and get notified the moment it happens.

https://github.com/user-attachments/assets/d542035c-5206-4b21-87a3-6e17ea47b830

---

### 4. Natural Language Queries

Ask questions about your data in plain English directly from the CLI. The AI layer has read-only access at the database level, so there is no risk of accidental writes or data manipulation.

**Example:** You need a quick count of rows matching a complex condition but do not want to context-switch into a SQL editor. Just describe what you want and get the answer inline in your terminal.


https://github.com/user-attachments/assets/c09ea0b4-a8f7-44c2-9cf5-3ad2533dbc00

---

## Additional Features

**Autocomplete from history.** The CLI remembers your past inputs and surfaces them as you type, so repeated commands and queries require minimal keystrokes.

**Smart schema injection.** When your natural language query references a table or column, Toygres fuzzy-matches it against your schema and injects only the relevant context into the prompt. No full schema dumps on every call — just what the model actually needs.

**Cost and token summary.** At the end of each session, Toygres prints a breakdown of tokens consumed and estimated cost, so you always know what you are spending.

---

## Installation

Requires Python 3.11+ and Docker.

```bash
git clone <repository_url>
cd toygres
cp .env.example .env        # Configure your environment variables
docker compose up -d        # Start the required services
uv sync                     # Install Python dependencies
```

## Usage

```bash
make start
```
