-- ACCOUNT
CREATE TABLE account (
  account_id    UUID PRIMARY KEY,
  email         TEXT UNIQUE,
  display_name  TEXT NOT NULL,
  account_type  TEXT NOT NULL CHECK (account_type IN ('child','parent','guardian','admin')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  status        TEXT NOT NULL DEFAULT 'active'
);

-- Map to Cognito and track login recency
ALTER TABLE account
  ADD COLUMN IF NOT EXISTS cognito_sub     TEXT UNIQUE,        
  ADD COLUMN IF NOT EXISTS last_login_at   TIMESTAMPTZ;

-- Helpful for first-time linking by email
CREATE UNIQUE INDEX IF NOT EXISTS account_email_uidx ON account (lower(email));

-- GUARDIAN_CHILD_LINK
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

-- GUARDIAN_INVITE
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
	strategy_requirements JSONB NULL,
	strategy_instruction text NULL,
	strategy_source JSONB NULL,
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
  crisis_id            SMALLINT NOT NULL
                          REFERENCES crisis(crisis_id) ON DELETE RESTRICT,      
  crisis_alert_ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
  crisis_alert_severity TEXT NOT NULL
                          CHECK (crisis_alert_severity IN ('low', 'medium','high','extremely_high')),
  crisis_alert_status  TEXT NOT NULL DEFAULT 'pending'
                          CHECK (crisis_alert_status IN ('pending','acknowledged')),
  crisis_alert_note    TEXT
);

-- Index to fetch alerts for a parent dashboard efficiently
CREATE INDEX IF NOT EXISTS idx_crisis_alert_account_ts
  ON crisis_alert(account_id, crisis_alert_ts DESC);

-- ...existing code...

-- ACTIVITY
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
  mood_log_id       UUID NULL REFERENCES mood_log(mood_id) ON DELETE SET NULL,
  message_id        UUID NULL REFERENCES chat_message(message_id) ON DELETE SET NULL,
  CONSTRAINT activity_one_source_chk CHECK (
    (mood_log_id IS NOT NULL AND message_id IS NULL)
    OR (mood_log_id IS NULL AND message_id IS NOT NULL)
  )
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_activity_account_ts ON activity (account_id, activity_ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_strategy ON activity (strategy_id);
CREATE INDEX IF NOT EXISTS idx_activity_mood_log ON activity (mood_log_id);
CREATE INDEX IF NOT EXISTS idx_activity_message ON activity (message_id);


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




-- ...existing code...

-- ACTIVITY: drop mood_log link and XOR constraint (message_id remains optional)
ALTER TABLE public.activity
  DROP CONSTRAINT IF EXISTS activity_one_source_chk,
  DROP COLUMN IF EXISTS mood_log_id;

-- Optional: helpful index for listing by account + time
CREATE INDEX IF NOT EXISTS idx_activity_account_ts
  ON public.activity (account_id, activity_ts DESC);

-- ...existing code...


-- CHAT_SESSION: add account_id and other fields if not present
-- Note: existing sessions will have NULL account_id until updated
--       (which is fine, as long as new sessions always set it)
ALTER TABLE chat_session
  ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES account(account_id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS name TEXT NULL,
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','archived','closed'));

CREATE INDEX IF NOT EXISTS idx_chat_session_account_last_active
  ON chat_session (account_id, last_active_at DESC);

-- Messages index (in case not present)
CREATE INDEX IF NOT EXISTS idx_chat_message_session_ts
  ON chat_message (session_id, message_ts DESC);

ALTER TABLE chat_session
  ADD COLUMN IF NOT EXISTS name TEXT NULL,
  ADD CONSTRAINT status_category_valid_values CHECK (status IN ('active','archived','closed'));



-- Trigger to update chat_session.last_active_at on new chat_message
DROP FUNCTION IF EXISTS trg_chat_message_touch_session();
CREATE OR REPLACE FUNCTION trg_chat_message_touch_session()
RETURNS trigger AS $$
BEGIN
  UPDATE chat_session
    SET last_active_at = now()
    WHERE session_id = NEW.session_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chat_message_touch_session ON chat_message;

CREATE TRIGGER chat_message_touch_session
AFTER INSERT ON chat_message
FOR EACH ROW EXECUTE FUNCTION trg_chat_message_touch_session();



-- ==========================
-- Table: crisis_strategy
-- ==========================

CREATE TABLE crisis_strategy (
    crisis_id INT NOT NULL,
    crisis_severity VARCHAR(20) NOT NULL CHECK (crisis_severity IN ('low', 'medium', 'high', 'extremely_high')),
    crisis_strategy_text JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT pk_crisis_strategy PRIMARY KEY (crisis_id, crisis_severity),
    CONSTRAINT fk_crisis_strategy_crisis FOREIGN KEY (crisis_id)
        REFERENCES crisis (crisis_id)
        ON DELETE CASCADE
);
