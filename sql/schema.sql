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

-- Nice-to-have checks
ALTER TABLE emotion_label
  ADD CONSTRAINT uq_emotion_label_emoji UNIQUE (emoji),
  ADD CONSTRAINT emotion_category_chk CHECK (category IN ('positive','negative','neutral','ambiguous'));

ALTER TABLE mood_log
  ADD CONSTRAINT mood_log_intensity_chk CHECK (mood_intensity BETWEEN 1 AND 3),
  ADD CONSTRAINT uq_mood_log_account_date UNIQUE (account_id, mood_date);
