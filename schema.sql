-- SQL Schema for MoodTra Application
-- Table of Contents:
-- 1. ACCOUNT
-- 2. GUARDIAN_CHILD_LINK
-- 3. GUARDIAN_INVITE
-- 4. CHAT_SESSION
-- 5. EMOTION_LABEL
-- 6. CHAT_MESSAGE
-- 7. MOOD_LOG
-- 8. STRATEGY
-- 9. STRATEGY_EMOTION
-- 10. ACTIVITY
-- 11. CRISIS
-- 12. CRISIS_ALERT
-- 13. CRISIS_STRATEGY
-- 14. WELLBEING_CONV_TIP


-- 1. ACCOUNT
-- Stores user accounts: child, parent, guardian, admin
CREATE TABLE account (
  account_id    UUID PRIMARY KEY,
  email         TEXT UNIQUE,
  display_name  TEXT NOT NULL,
  account_type  TEXT NULL CHECK (account_type IN ('child','parent','guardian','admin')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  status        TEXT NOT NULL DEFAULT 'active'
);

-- Map to Cognito and track login recency
ALTER TABLE account
  ADD COLUMN IF NOT EXISTS cognito_sub     TEXT UNIQUE,        
  ADD COLUMN IF NOT EXISTS last_login_at   TIMESTAMPTZ;

-- Helpful for first-time linking by email
CREATE UNIQUE INDEX IF NOT EXISTS account_email_uidx ON account (lower(email));

-- 2. GUARDIAN_CHILD_LINK
-- Links a guardian account to a child account.
CREATE TABLE IF NOT EXISTS guardian_child_link (
  link_id     UUID PRIMARY KEY,
  guardian_id   UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  child_id    UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  link_status TEXT   NOT NULL DEFAULT 'active',  -- 'active' | 'revoked'
  linked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (guardian_id, child_id)
);

-- Common lookups:
CREATE INDEX IF NOT EXISTS gcl_guardian_idx ON guardian_child_link (guardian_id) ;
CREATE INDEX IF NOT EXISTS gcl_child_idx  ON guardian_child_link (child_id)  ;

-- 3. GUARDIAN_INVITE
-- Lightweight enum for invite status
DO $$ BEGIN
  CREATE TYPE invite_status AS ENUM ('invited','accepted','revoked','expired');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Store only a HASH of the token (never the raw token) for security
CREATE TABLE IF NOT EXISTS guardian_invite (
  invite_id            UUID PRIMARY KEY,
  guardian_id          UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  invitee_email        TEXT   NOT NULL,
  token_hash           TEXT   NOT NULL UNIQUE,        -- sha256/bcrypt of the random token
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at           TIMESTAMPTZ NOT NULL,
  status               invite_status NOT NULL DEFAULT 'invited',
  accepted_at          TIMESTAMPTZ,
  accepted_account_id  UUID REFERENCES account(account_id)  -- child account_id once accepted
);

-- Lookups by guardian and pending state
CREATE INDEX IF NOT EXISTS gi_guardian_idx  ON guardian_invite (guardian_id, status);
CREATE INDEX IF NOT EXISTS gi_email_idx   ON guardian_invite (lower(invitee_email));

-- 4. CHAT_SESSION
-- A chat session is tied to a child account. It can be active, archived, or closed.
CREATE TABLE chat_session (
  session_id    	UUID PRIMARY KEY,
  account_id    	UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  created_at    	TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at 	TIMESTAMPTZ NOT NULL DEFAULT now(),
  status        	TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','archived','closed')),
  name          	TEXT NULL
);

CREATE INDEX idx_chat_session_account ON chat_session(account_id);
CREATE INDEX IF NOT EXISTS idx_chat_session_account_last_active
  ON chat_session (account_id, last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_message_session_ts
  ON chat_message (session_id, message_ts DESC);

-- 5. EMOTION_LABEL
-- Master list of emotions with emoji, name, and category
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

-- 6. CHAT_MESSAGE
-- Messages in a chat session, from child or assistant
CREATE TABLE chat_message (
  message_id    		UUID PRIMARY KEY,
  session_id    		UUID REFERENCES chat_session(session_id) ON DELETE SET NULL,
  message_ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
  message_role          VARCHAR(50) NOT NULL CHECK (message_role IN ('child','assistant')),
  message_text          TEXT NOT NULL
);
CREATE INDEX idx_chat_message_acc_ts ON chat_message(session_id, message_ts);

-- 7. MOOD_LOG
-- Daily mood log tied to a child account
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

-- 8. STRATEGY
-- Master list of coping strategies
CREATE TABLE public.strategy (
	strategy_id text NOT NULL,
	strategy_name text NULL,
	strategy_desc text NULL,
	strategy_duration int4 NULL,
	strategy_requirements JSONB NULL,
	strategy_instruction text NULL,
	strategy_source JSONB NULL,
	CONSTRAINT strategies_pk PRIMARY KEY (strategy_id)
);

ALTER TABLE strategy
  ADD COLUMN strategy_category TEXT NULL,
  ADD COLUMN parent_conv_tip JSONB;

-- 9. STRATEGY_EMOTION
-- Link table for many-to-many relationship between strategies and emotions
CREATE TABLE public.strategy_emotion (
	strategy_id text NOT NULL,
	emotion_id int2 NOT NULL,
	CONSTRAINT emo_strategy_pk PRIMARY KEY (strategy_id, emotion_id)
);

ALTER TABLE public.strategy_emotion ADD CONSTRAINT emo_strategy_emotion_label_fk FOREIGN KEY (emotion_id) REFERENCES public.emotion_label(emotion_id);
ALTER TABLE public.strategy_emotion ADD CONSTRAINT emo_strategy_strategies_fk FOREIGN KEY (strategy_id) REFERENCES public.strategy(strategy_id);

-- 10. ACTIVITY
-- Records a chosen strategy. Source is either a mood_log (mood_log_id) OR a chat message (message_id).
-- emotion_before/after store emojis.
CREATE TABLE IF NOT EXISTS activity (
  activity_id       UUID PRIMARY KEY,
  account_id        UUID NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
  strategy_id       TEXT NOT NULL REFERENCES strategy(strategy_id) ON DELETE RESTRICT,
  activity_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
  activity_status   TEXT NOT NULL DEFAULT 'pending'
                    CHECK (activity_status IN ('pending','completed','abandoned')),
  emotion_before    TEXT NOT NULL,
  emotion_after     TEXT NULL,
  message_id        UUID NULL REFERENCES chat_message(message_id) ON DELETE SET NULL,
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_activity_account_ts ON activity (account_id, activity_ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_strategy ON activity (strategy_id);
CREATE INDEX IF NOT EXISTS idx_activity_message ON activity (message_id);

-- 11. CRISIS
-- Master list of crisis categories
CREATE TABLE IF NOT EXISTS crisis (
  crisis_id    SMALLINT PRIMARY KEY,
  crisis_name  TEXT NOT NULL UNIQUE
);

-- 12. CRISIS_ALERT
-- Escalation record tied to the user account (not session)

CREATE TABLE crisis_alert (
  crisis_alert_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id           UUID NOT NULL
                          REFERENCES account(account_id) ON DELETE CASCADE,
  crisis_id            SMALLINT NOT NULL
                          REFERENCES crisis(crisis_id) ON DELETE RESTRICT,      
  crisis_alert_ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
  crisis_alert_severity TEXT NOT NULL
                          CHECK (crisis_alert_severity IN ('low', 'medium','high','extremely_high')),
  crisis_alert_status  TEXT NOT NULL DEFAULT 'pending'
                          CHECK (crisis_alert_status IN ('pending','acknowledged')),
  crisis_alert_note    TEXT,
  last_msg_ts           TIMESTAMPTZ,
);

-- Index to fetch alerts for a parent dashboard efficiently
CREATE INDEX IF NOT EXISTS idx_crisis_alert_account_ts
  ON crisis_alert(account_id, crisis_alert_ts DESC);

-- 13. CRISIS_STRATEGY
-- Predefined strategies for different crisis types and severities
CREATE TABLE crisis_strategy (
    crisis_id INT NOT NULL,
    crisis_severity VARCHAR(20) NOT NULL CHECK (crisis_severity IN ('low', 'medium', 'high', 'extremely_high')),
    crisis_strategy_text JSONB NOT NULL,
    
    CONSTRAINT pk_crisis_strategy PRIMARY KEY (crisis_id, crisis_severity),
    CONSTRAINT fk_crisis_strategy_crisis FOREIGN KEY (crisis_id)
        REFERENCES crisis (crisis_id)
        ON DELETE CASCADE
);

-- 14. wellbeing_conv_tip
-- Predefined conversation tips based on wellbeing score (1-5)
CREATE TABLE wellbeing_conv_tip (
  wellbeing_score SMALLINT NOT NULL
    CHECK (wellbeing_score BETWEEN 1 AND 5),
  wellbeing_conv_text JSONB NOT NULL,        -- { "1": "...", "2": "...", ... }
  CONSTRAINT pk_wellbeing_conv_tip PRIMARY KEY (wellbeing_score)
);




