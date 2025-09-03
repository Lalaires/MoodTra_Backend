-- ACCOUNT
INSERT INTO account (account_id, display_name, account_type)
VALUES ('00000000-0000-0000-0000-00000000C0DE', 'Liam', 'child');

-- EMOTION_LABEL
INSERT INTO emotion_label (emotion_id, emoji, name, category) VALUES
 (1,'😡','anger','negative'),
 (2,'🤢','disgust','negative'),
 (3,'😨','fear','negative'),
 (4,'😃','joy','positive'),
 (5,'😐','neutral','neutral'),
 (6,'😭','sadness','negative'),
 (7,'😲','surprise','ambiguous');

-- CHAT_SESSION
INSERT INTO chat_session (session_id, account_id)
VALUES ('11111111-1111-1111-1111-111111111111', '00000000-0000-0000-0000-00000000C0DE');
