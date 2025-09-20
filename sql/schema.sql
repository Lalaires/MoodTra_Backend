-- ACCOUNT
CREATE TABLE account (
  account_id    UUID PRIMARY KEY,
  email         TEXT UNIQUE,
  display_name  TEXT NOT NULL,
  account_type  TEXT NOT NULL CHECK (account_type IN ('child','parent','guardian','admin')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  status        TEXT NOT NULL DEFAULT 'active'
);

-- CHAT_SESSION
CREATE TABLE chat_session (
  session_id    	UUID PRIMARY KEY,
  account_id    	UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  created_at    	TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at 	TIMESTAMPTZ NOT NULL DEFAULT now(),
  status        	TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX idx_chat_session_account ON chat_session(account_id);

-- EMOTION_LABEL
CREATE TABLE emotion_label (
  emotion_id   	SMALLINT PRIMARY KEY,
  emoji        	TEXT NOT NULL,
  name 			VARCHAR(50) NOT NULL UNIQUE,
  category 		VARCHAR(50) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emotion_label_emoji ON emotion_label(emoji);

ALTER TABLE emotion_label
  ADD CONSTRAINT uq_emotion_label_emoji UNIQUE (emoji),
  ADD CONSTRAINT emotion_category_chk CHECK (category IN ('positive','negative','neutral','ambiguous'));

-- CHAT_MESSAGE
CREATE TABLE chat_message (
  message_id    		UUID PRIMARY KEY,
  session_id    		UUID REFERENCES chat_session(session_id) ON DELETE SET NULL,
  message_ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
  message_role          VARCHAR(50) NOT NULL CHECK (message_role IN ('child','assistant')),
  message_text          TEXT NOT NULL
);
CREATE INDEX idx_chat_message_acc_ts ON chat_message(session_id, message_ts);

-- MOOD_LOG
CREATE TABLE mood_log (
  mood_id           UUID PRIMARY KEY,
  account_id        UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  mood_date         DATE NOT NULL,
  mood_emoji        TEXT NOT NULL,
  mood_intensity    SMALLINT NOT NULL,
  note              TEXT,
  linked_emotion_id SMALLINT REFERENCES emotion_label(emotion_id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mood_log_account_day_created ON mood_log (account_id, mood_date, created_at DESC);
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

ALTER TABLE mood_log
  ADD CONSTRAINT mood_log_intensity_chk CHECK (mood_intensity BETWEEN 1 AND 3),
  ADD CONSTRAINT uq_mood_log_account_date UNIQUE (account_id, mood_date);

-- STRATEGY and ACTIVITY

-- STRATEGY 
CREATE TABLE public.strategy (
	strategy_id text NOT NULL,
	strategy_name text NULL,
	strategy_desc text NULL,
	strategy_duration int4 NULL,
	strategy_requirements text NULL,
	strategy_instruction text NULL,
	strategy_source text NULL,
	CONSTRAINT strategies_pk PRIMARY KEY (strategy_id)
);

-- STRATEGY_EMOTION:
CREATE TABLE public.strategy_emotion (
	strategy_id text NOT NULL,
	emotion_id int2 NOT NULL,
	CONSTRAINT emo_strategy_pk PRIMARY KEY (strategy_id, emotion_id)
);

ALTER TABLE public.strategy_emotion ADD CONSTRAINT emo_strategy_emotion_label_fk FOREIGN KEY (emotion_id) REFERENCES public.emotion_label(emotion_id);
ALTER TABLE public.strategy_emotion ADD CONSTRAINT emo_strategy_strategies_fk FOREIGN KEY (strategy_id) REFERENCES public.strategy(strategy_id);


-- CRISIS DETECTION

-- 1) CRISIS: master list of crisis categories
--    (ids are small and stable so SMALLINT is fine)
CREATE TABLE IF NOT EXISTS crisis (
  crisis_id    SMALLINT PRIMARY KEY,
  crisis_name  TEXT NOT NULL UNIQUE
);


-- 2) CRISIS_FLAG: individual detections inside a chat session
--    'crisis_flag_note' is free text with the model’s analysis.
--    Severity is limited to the three allowed values.
DROP TABLE IF EXISTS crisis_flag CASCADE;

CREATE TABLE IF NOT EXISTS crisis_flag (
  crisis_flag_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  crisis_id          SMALLINT NOT NULL
                        REFERENCES crisis(crisis_id) ON DELETE RESTRICT,
  session_id         UUID NOT NULL
                        REFERENCES chat_session(session_id) ON DELETE CASCADE,
  crisis_flag_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  crisis_flag_severity TEXT NOT NULL
                        CHECK (crisis_flag_severity IN ('low', 'medium','high','extremely_high')),
  crisis_flag_note   TEXT
);

-- Helpful index to list/review flags per session quickly
CREATE INDEX IF NOT EXISTS idx_crisis_flag_session_ts
  ON crisis_flag(session_id, crisis_flag_ts DESC);

-- Optional: if you often query by severity, this helps
CREATE INDEX IF NOT EXISTS idx_crisis_flag_severity_ts
  ON crisis_flag(crisis_flag_severity, crisis_flag_ts DESC);

-- 3) CRISIS_ALERT: escalation record tied to the user account (not session)
--    crisis_alert_status captures guardian acknowledgement.
--    crisis_alert_note stores a *string* of the crisis_flag_id list used
--    to justify the alert (as you requested).

DROP TABLE IF EXISTS crisis_alert CASCADE;
CREATE TABLE crisis_alert (
  crisis_alert_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id           UUID NOT NULL
                          REFERENCES account(account_id) ON DELETE CASCADE,
  crisis_alert_ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
  crisis_alert_severity TEXT NOT NULL
                          CHECK (crisis_alert_severity IN ('attention','emergency')),
  crisis_alert_status  TEXT NOT NULL DEFAULT 'pending'
                          CHECK (crisis_alert_status IN ('pending','acknowledged')),
  crisis_alert_note    TEXT
);

-- Index to fetch alerts for a parent dashboard efficiently
CREATE INDEX IF NOT EXISTS idx_crisis_alert_account_ts
  ON crisis_alert(account_id, crisis_alert_ts DESC);



-- Convert text JSON to JSONB (safe if values are valid JSON or null/empty)
ALTER TABLE strategy
  ALTER COLUMN strategy_requirements TYPE jsonb
    USING CASE
      WHEN strategy_requirements IS NULL OR btrim(strategy_requirements) = '' THEN NULL
      ELSE btrim(strategy_requirements)::jsonb
    END,
  ALTER COLUMN strategy_source TYPE jsonb
    USING CASE
      WHEN strategy_source IS NULL OR btrim(strategy_source) = '' THEN NULL
      ELSE btrim(strategy_source)::jsonb
    END;