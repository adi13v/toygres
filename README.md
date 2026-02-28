# Toygres

A fast, lightweight CLI for PostgreSQL built around disposable databases. Stop writing teardown scripts. Stop waiting on setup. Just get a clean database and get back to work.

---

## The Problem

Testing and debugging against a database is painful. You reset state manually, re-run migrations, re-seed lookup data, and repeat. Toygres eliminates that friction entirely.

---

## Core Features

### 1. Instant Disposable Databases

Spin up a new PostgreSQL database instantly through a simple interactive CLI — no prompts for usernames, passwords, or hostnames. Create it, use it, and drop it just as fast when you are done.

**Example:** Your integration test suite fails halfway through and leaves the database in a dirty state. Instead of writing a teardown script, hit reset from the CLI and start clean in under a second.

---

### 2. Baseline Databases

Save a pre-configured database state as a named baseline and restore to it any time with a single selection. Think of it as a constructor for your database — you get a fresh instance but with your required seed data already in place.

**Example:** Your app requires an admin user, a set of country codes, and default app config rows before it can run. Configure this once, save it as a baseline, and every future reset restores all of it automatically.

---

### 3. Observer Agent

Describe what you want to watch in plain English. The agent monitors your database in real time and alerts you the moment a matching change occurs — no polling scripts, no SQL triggers required.

**Example:** You are debugging an async background worker. Instead of manually querying the database every few seconds, set up an Observer Agent with a prompt like "Alert me when order 12345 changes status from pending to completed" and get notified the moment it happens.

---

### 4. Natural Language Queries

Ask questions about your data in plain English directly from the CLI. The AI layer has read-only access at the database level, so there is no risk of accidental writes or data manipulation.

**Example:** You need a quick count of rows matching a complex condition but do not want to context-switch into a SQL editor. Just describe what you want and get the answer inline in your terminal.

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