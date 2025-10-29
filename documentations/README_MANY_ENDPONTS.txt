
General notes
- Base URL: http://localhost:8000
- Headers:
  - x-account-id: UUID of the signed-in account. If omitted, the backend uses MOCK_ACCOUNT_ID from environment (dev only).
- All timestamps are UTC.
- Emojis in URLs must be URL-encoded (e.g., 😰 -> %F0%9F%98%B0).

Strategy API
Base path: /strategy

1) GET /strategy
- Purpose: List all strategies for client-side mapping (e.g., enrich activity cards).
- Query params: none
- Response: Array of StrategyOut
  - strategy_id: string
  - strategy_name: string
  - strategy_desc: string | null
  - strategy_duration: number | null (minutes)
  - strategy_requirements: object | null (JSONB; e.g., { "location": "indoor" })
  - strategy_instruction: string | null
  - strategy_source: object | null (JSONB; e.g., { "source_name": "...", "source_link": "..." })

Example:
````bash
curl http://localhost:8000/strategy
````

2) GET /strategy/emojis/{emoji}
- Purpose: Recommend strategies by an emoji (joined via emotion_label -> strategy_emotion -> strategy).
- Path params:
  - emoji: string (URL-encoded)
- Response: Array of StrategyOut (same shape as above)

Example:
````bash
curl "http://localhost:8000/strategy/emojis/%F0%9F%98%B0"   # 😰 anxious
````

Activity API
Base path: /activity

Model semantics
- Records a teen’s selected strategy, sourced either from:
  - a mood_log entry (mood_log_id), or
  - a chat message that confirms selection (message_id).
- Exactly one source must be provided (enforced by DB constraint).
- activity_status: "pending" | "completed" | "abandoned"
- emotion_before: emoji before doing the activity
- emotion_after: emoji after completing/abandoning (optional)

1) POST /activity
- Purpose: Create a new activity.
- Headers: x-account-id required.
- Body (ActivityCreate):
  - strategy_id: string (required)
  - emotion_before: string (emoji, required)
  - mood_log_id: UUID | null
  - message_id: UUID | null
  - Rule: exactly one of mood_log_id or message_id must be present.
- Response: ActivityOut
  - activity_id, account_id, strategy_id, activity_ts, activity_status, emotion_before, emotion_after, mood_log_id, message_id

Example:
````bash
curl -X POST http://localhost:8000/activity \
  -H "Content-Type: application/json" \
  -H "x-account-id: 00000000-0000-0000-0000-00000000C0DE" \
  -d '{
    "strategy_id": "s1",
    "emotion_before": "😰",
    "mood_log_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
  }'
````

2) PATCH /activity/{activity_id}
- Purpose: Update status and/or record emotion_after.
- Headers: x-account-id required.
- Path params:
  - activity_id: UUID
- Body (ActivityUpdate):
  - activity_status: "pending" | "completed" | "abandoned" (optional)
  - emotion_after: string (emoji, optional)
- Response: ActivityOut

Example:
````bash
curl -X PATCH http://localhost:8000/activity/BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB \
  -H "Content-Type: application/json" \
  -H "x-account-id: 00000000-0000-0000-0000-00000000C0DE" \
  -d '{ "activity_status": "completed", "emotion_after": "😊" }'
````

3) GET /activity
- Purpose: List activities within a date range (default: current month).
- Headers: x-account-id required.
- Query params:
  - start_date: YYYY-MM-DD (optional; default = first day of current month)
  - end_date: YYYY-MM-DD (optional; default = last day of current month)
  - limit: integer (1–200, default 50). Results sorted by activity_ts desc.
- Response: Array of ActivityOut

Examples:
````bash
# Defaults to current month
curl -H "x-account-id: 00000000-0000-0000-0000-00000000C0DE" http://localhost:8000/activity

# Custom range
curl -H "x-account-id: 00000000-0000-0000-0000-00000000C0DE" \
  "http://localhost:8000/activity?start_date=2025-09-01&end_date=2025-09-21&limit=100"
````

Notes:
- The backend uses a half-open timestamp range [start_date 00:00:00, end_date+1 00:00:00) in UTC to include all records on end_date.
- Frontend can join Activity.strategy_id to GET /strategy results to display names/descriptions.

Mood API
Base path: /mood

Behavior
- One mood entry per account per calendar day (enforced; 409 on duplicate).
- mood_emoji is mapped to emotion_label.emotion_id automatically; 400 if emoji missing in emotion_label.

Models
- MoodCreate: mood_date (date), mood_emoji (emoji), mood_intensity (1–3), note (optional)
- MoodUpdate: mood_emoji, mood_intensity (1–3), note (optional)
- MoodOut: mood_id, account_id, mood_date, mood_emoji, mood_intensity, note
- Summary item: { emoji: string, emotion_id: number, count: number }

Endpoints

1) POST /mood/entries
- Purpose: Create a mood entry for a date.
- Headers: x-account-id required.
- Body: MoodCreate
- Responses:
  - 201 with MoodOut
  - 409 if an entry already exists for that date
  - 400 if emoji not found in emotion_label

Example:
````bash
curl -X POST http://localhost:8000/mood/entries \
  -H "Content-Type: application/json" \
  -H "x-account-id: 00000000-0000-0000-0000-00000000C0DE" \
  -d '{ "mood_date": "2025-09-21", "mood_emoji": "😰", "mood_intensity": 2, "note": "Nervous before exam" }'
````

2) PUT /mood/entries/{mood_date}
- Purpose: Update the mood entry for a specific date.
- Headers: x-account-id required.
- Path params: mood_date (YYYY-MM-DD)
- Body: MoodUpdate
- Response: MoodOut or 404 if not found

3) DELETE /mood/entries/{mood_date}
- Purpose: Delete a mood entry (idempotent).
- Headers: x-account-id required.
- Path params: mood_date (YYYY-MM-DD)
- Response: 204 No Content

4) GET /mood/entries/{mood_date}
- Purpose: Get the mood entry for a date.
- Headers: x-account-id required.
- Path params: mood_date (YYYY-MM-DD)
- Response: MoodOut or 404

5) GET /mood/entries?start=YYYY-MM-DD&end=YYYY-MM-DD
- Purpose: List entries in an inclusive date range (newest first).
- Headers: x-account-id required.
- Query params: start, end (both required)
- Response: Array of MoodOut

6) GET /mood/summary/weekly?as_of=YYYY-MM-DD&week_start=0..6
- Purpose: Week-to-date summary for the week containing as_of.
- Headers: x-account-id required.
- Query params:
  - as_of: date (defaults to today on server)
  - week_start: 0=Mon .. 6=Sun (default 0)
- Response: Array of { emoji, emotion_id, count }

7) GET /mood/summary/monthly?as_of=YYYY-MM-DD
- Purpose: Month-to-date summary for the month containing as_of.
- Headers: x-account-id required.
- Query params:
  - as_of: date (defaults to today on server)
- Response: Array of { emoji, emotion_id, count }

Error codes (common)
- 400 Bad Request: invalid parameters (e.g., start_date > end_date, emoji not found).
- 401/403: missing or invalid x-account-id (depending on deployment settings).
- 404 Not Found: resource not found (e.g., activity not owned by account, mood entry missing).
- 409 Conflict: duplicate mood entry for a date.

Tip for frontend
- Fetch strategies once via GET /strategy and cache client-side. When listing activities, map each activity.strategy_id to enrich cards with strategy_name/description/instructions.