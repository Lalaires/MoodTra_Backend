# MindPal Backend – API & Local Testing Guide

This README describes the REST endpoints, what each one does, and how to run/test everything locally (Dockerized Postgres + FastAPI + Swagger).

---

## Contents

* [Overview](#overview)
* [Prerequisites](#prerequisites)
* [Quick Start (Local)](#quick-start-local)

  * [1) Start Postgres in Docker](#1-start-postgres-in-docker)
  * [2) Create/Reset the `mindpal` database](#2-createreset-the-mindpal-database)
  * [3) Load schema & seed (copy method)](#3-load-schema--seed-copy-method)
  * [4) Create and activate a virtual environment](#4-create-and-activate-a-virtual-environment)
  * [5) Run the API](#5-run-the-api)
  * [6) Open Swagger](#6-open-swagger)
* [Headers Used by the API](#headers-used-by-the-api)
* [API Reference](#api-reference)

  * [Chat](#chat)
  * [Mood (append-only)](#mood-appendonly)
  * [Health](#health)
* [Notes & Conventions](#notes--conventions)

---

## Overview

* **FastAPI** app that powers chat message storage and a mood log (calendar-like).
* **Postgres** stores:

  * `account`, `chat_session`, `chat_message`
  * `emotion_label` (master list of emotions & emojis)
  * `mood_log` (append-only entries; latest-per-day logic is done in queries)
* **Swagger UI** available at `http://127.0.0.1:8000/docs`

---

## Prerequisites

* Docker Desktop (or Docker CLI)
* Python 3.11+ (recommended)
* Git (optional, to clone the repo)

---

## Quick Start (Local)

### 1) Start Postgres in Docker

```powershell
# Windows PowerShell
docker run -d --name hkdb -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
```

> If the container already exists, just `docker start hkdb`.

### 2) Create/Reset the `mindpal` database

Choose **A** (recreate DB) or **B** (wipe schema).

**A) Drop & recreate DB**

```powershell
docker exec -it hkdb psql -U postgres -c "DROP DATABASE IF EXISTS mindpal WITH (FORCE);"
docker exec -it hkdb psql -U postgres -c "CREATE DATABASE mindpal;"
```

**B) Reset public schema**

```powershell
docker exec -it hkdb psql -U postgres -d mindpal -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### 3) Load schema & seed (copy method)

From the repo root (where `.\sql\schema.sql` and `.\sql\seed.sql` live):

```powershell
docker cp .\sql\schema.sql hkdb:/tmp/schema.sql
docker cp .\sql\seed.sql   hkdb:/tmp/seed.sql

docker exec -it hkdb psql -v ON_ERROR_STOP=1 -U postgres -d mindpal -f /tmp/schema.sql
docker exec -it hkdb psql -v ON_ERROR_STOP=1 -U postgres -d mindpal -f /tmp/seed.sql
```

**Verify tables/seed:**

```powershell
docker exec -it hkdb psql -U postgres -d mindpal -c "\dt"
docker exec -it hkdb psql -U postgres -d mindpal -c "SELECT * FROM account;"
docker exec -it hkdb psql -U postgres -d mindpal -c "SELECT * FROM emotion_label;"
docker exec -it hkdb psql -U postgres -d mindpal -c "SELECT * FROM chat_session;"
```

### 4) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

(To **deactivate** later: `deactivate`)

### 5) Run the API

```powershell
uvicorn app.main:app --reload
```

### 6) Open Swagger

Go to: `http://127.0.0.1:8000/docs`

---

## Headers Used by the API

Some endpoints require these headers (Swagger shows fields to enter them):

* `x-account-id`: UUID of the account (e.g., the seeded child: `00000000-0000-0000-0000-00000000C0DE`)
* For chat, your session is the seeded one: `11111111-1111-1111-1111-111111111111`

---

## API Reference

### Chat

#### `GET /chat/messages` — Get Messages

Returns all messages for the current chat session (ordered by timestamp).

* **Response fields:** `message_id`, `session_id`, `message_ts`, `message_role` (`child|assistant`), `message_text`.

#### `POST /chat/messages` — Post Message

Create a new chat message.

* **Body:**

  ```json
  {
    "message_text": "I feel anxious about exams",
    "message_role": "child"
  }
  ```
* **Response:** the created message record.

> Emotion recognition is used for response generation only; we do **not** store emotion/confidence on messages.

---

### Mood (append-only)

#### `GET /mood/entries` — List Entries

Returns **all** mood\_log rows for the account within an optional **inclusive** date range.

* **Query**:

  * `start` (optional, `YYYY-MM-DD`)
  * `end` (optional, `YYYY-MM-DD`)
* **Headers**: `x-account-id`
* **Notes**: sorted by `mood_date DESC, created_at DESC`.

#### `POST /mood/entries` — Create Entry

Append a new mood entry.

* **Body:**

  ```json
  {
    "mood_date": "2025-09-03",
    "mood_emoji": "🙂",
    "mood_intensity": 3,
    "note": "Feeling okay today"
  }
  ```
* **Behavior**:

  * `linked_emotion_id` is **automatically mapped** from `mood_emoji` via the `emotion_label` table.
  * `created_at` stores the exact time entry was written.
* **Response**: the full row, including the derived `linked_emotion_id`.

#### `GET /mood/entries/latest` — List Latest Per Day

Returns **one entry per day** (the most recently created that day) within an **inclusive** date range.
Great for calendar/month/week screens.

* **Query**:

  * `start` (optional, `YYYY-MM-DD`)
  * `end` (optional, `YYYY-MM-DD`)
* **Headers**: `x-account-id`

#### `GET /mood/entries/today/latest` — Latest For Today

Returns the latest mood entry for **today** (or `null` if none).

* **Headers**: `x-account-id`

#### `GET /mood/summary/weekly` — Weekly Summary

Counts mood emojis for the **week relative to an anchor date**.

* **Query**:

  * `as_of` (optional, date; defaults to **today**) — anchor date.
  * `week_start` (optional, 0=Mon…6=Sun; default **0**).
  * `full_week` (optional, default **false**)

    * `false` → **Week-to-Date (WTD)** from week start through `as_of` (inclusive).
    * `true`  → **Full calendar week** containing `as_of` (week start through week start + 7 days).
  * `latest_only` (optional, default **true**) — if true, count only the latest entry per day.
* **Headers**: `x-account-id`
* **Response**: array of `{ "emoji": "🙂", "count": 3 }`.

#### `GET /mood/summary/monthly` — Monthly Summary

Counts mood emojis for the **month relative to an anchor date**.

* **Query**:

  * `as_of` (optional, date; defaults to **today**) — anchor date.
  * `full_month` (optional, default **false**)

    * `false` → **Month-to-Date (MTD)** from the 1st through `as_of` (inclusive).
    * `true`  → **Full calendar month** containing `as_of`.
  * `latest_only` (optional, default **true**) — if true, count only the latest entry per day.
* **Headers**: `x-account-id`
* **Response**: array of `{ "emoji": "🙂", "count": 10 }`.

---

### Health

#### `GET /healthz` — Health Check

Simple liveness endpoint used by Docker/Kubernetes/cloud load balancers to verify the service is up.

* **Response**: `200 OK` with a tiny JSON payload (implementation may vary).

---

## Notes & Conventions

* **Append-only mood log:** we never overwrite mood entries. To show “the mood of the day”, use the **latest-per-day** endpoint.
* **Inclusive date ranges:** both `start` and `end` are **inclusive** on `/mood/entries` and `/mood/entries/latest`.
* **Auto mapping (emoji → emotion):** when creating a mood entry, `linked_emotion_id` is looked up from `emotion_label.emoji`. If an unknown emoji is sent, the API returns `400`.
* **Stopping & restarting locally:**

  * Stop Uvicorn: press **CTRL+C**
  * Deactivate venv: `deactivate`
  * Stop DB: `docker stop hkdb` (start again with `docker start hkdb`)

If you want this README to include **example `curl`/PowerShell** calls for each endpoint, say the word and I’ll add a compact “API Examples” section you can paste in.
