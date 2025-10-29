Here’s the frontend implementation outline for authentication + invite flows.

---

## 1. Key Concepts

- Cognito Hosted UI (Authorization Code + PKCE) returns a short‑lived authorization code (?code=...).
- Frontend must exchange that code for tokens at: https://<cognito-domain>/oauth2/token.
- Use the id_token (JWT) to establish an app session: POST /auth/session with HTTP Authorization: Bearer <id_token>.
- Backend’s /auth/session uses HTTPBearer (expects ONLY the raw JWT in the header after Bearer).
- After /auth/session returns, you MUST include x-account-id on all subsequent API calls (and x-session-id for chat messages).
- Invitations: Frontend passes the raw invite token (t query param) in POST /invites/accept; backend compares its hash.

---

## 2. Guardian Login Flow (Initial)

1. Generate code_verifier (random 43–128 URL‑safe chars) and store (sessionStorage).
2. Derive code_challenge = BASE64URL(SHA256(code_verifier)).
3. Generate state (random) and store.
4. Redirect user to:
   https://<domain>/login?
     client_id=<APP_CLIENT_ID>
     &response_type=code
     &scope=openid+email+profile
     &redirect_uri=<URL_ENCODED_CALLBACK>
     &state=<STATE>
     &code_challenge=<CODE_CHALLENGE>
     &code_challenge_method=S256
5. Callback page: verify state matches stored.
6. Extract ?code=… from URL.
7. Exchange code → POST https://<domain>/oauth2/token (Content-Type: application/x-www-form-urlencoded):
   grant_type=authorization_code
   client_id=<APP_CLIENT_ID>
   code=<CODE>
   redirect_uri=<SAME_CALLBACK>
   code_verifier=<ORIGINAL_VERIFIER>
8. Parse JSON → grab id_token (NOT access_token).
9. (Optional) Decode middle JWT segment (base64url) to read exp and email.
10. Call backend:
    POST /auth/session
    Authorization: Bearer <id_token>
11. Store:
    - account_id (response)
    - id_token
    - exp (from decoded JWT) for expiry checks
12. All future API calls:
    - Header x-account-id: <account_id>
    - Authorization header NOT required again unless you choose to (only /auth/session needs it).

Token expiry strategy: If (exp *1000 - Date.now()) < 2–5 min, re-run login flow.

---

## 3. Returning User (Already Logged In Earlier)

- Check id_token in storage and its exp.
- If still valid → skip Hosted UI, just use stored account_id.
- If expired → repeat full Guardian Login Flow.

---

## 4. Invite Creation (Guardian UI)

1. Ensure guardian is authenticated (have account_id).
2. User enters child email.
3. POST /invites { invitee_email } with headers:
   - x-account-id
4. Response returns share_url (e.g. https://app.example/accept-invite?t=<RAW_TOKEN>).
5. Show link / copy button.

Prevent duplicate UI spam: handle 409 (pending invite exists) gracefully.

---

## 5. Child Accept Flow

Entry point: user clicks invite link → /accept-invite?t=<RAW_TOKEN>

1. Extract t (invite token).
2. If no id_token (not logged in):
   - sessionStorage.setItem('inviteToken', t)
   - Start login flow (Section 2 steps 1–4) but for child Google account.
3. After code exchange + /auth/session:
   - Retrieve token = sessionStorage.getItem('inviteToken') (fallback to URL param).
   - Optional: confirmation modal (“Accept invite?”).
4. POST /invites/accept
   Headers: x-account-id: <child_account_id>
   Body: { "token": "<RAW_TOKEN>" }
5. If 200 → link established → navigate to child dashboard.
6. Handle errors:
   - 403 email mismatch (child logged in as different email)
   - 404 bad/unknown token
   - 409 status accepted/revoked/expired (show message; guardian may need a new invite)

Re-link case (previous link revoked): New invite → accept → backend reactivates link.

---

## 6. Child / Guardian Unlink

- Guardian: DELETE /me/links/{child_id}
- (If implemented) Child: DELETE /me/links/guardian/{guardian_id}
Headers: x-account-id.

UI should reflect removal immediately; re-link requires a fresh invite.

---

## 7. HTTPBearer Clarification (Important)

- /auth/session expects Authorization: Bearer <id_token>.
- In Swagger you pasted ONLY the raw JWT when using “Authorize”.
- In your frontend fetch/axios code you must set:
  headers: { Authorization: `Bearer ${idToken}` }
- Do NOT send the whole token JSON payload—only the JWT string.
- Other endpoints DO NOT require Authorization; they rely on x-account-id (your simplified project model). Keep the id_token around only to renew session later or for future secured endpoints.

---

## 8. Storage & Security (Lightweight Guidance)

Store (for dev/school):
- id_token in memory (and optionally sessionStorage)
- account_id in localStorage or memory
- code_verifier & state only until the code exchange finishes (sessionStorage)

On logout:
- Clear id_token, account_id, and any inviteToken remnants.

No refresh_token handling needed unless you want silent renew; just re-run login when near expiry.

---

## 9. Error Handling Cheat Sheet

During login exchange:
- invalid_grant → reused or expired code or redirect_uri mismatch.
During /auth/session:
- 401 → signature / issuer / audience mismatch; re-login or config error.
Invite accept:
- 403 → email mismatch
- 404 → token typo
- 409 → already accepted / expired / revoked

---

## 10. Minimal Sequence Diagrams (Text)

Guardian login:
Browser → Cognito (/login) → Browser ← redirect ?code → Browser → Cognito /oauth2/token → Browser ← {id_token} → Browser → Backend /auth/session (Bearer id_token) → Backend ← {account_id}

Child accept:
Browser (/accept-invite?t=TOKEN) → (if needed login sequence) → /auth/session → POST /invites/accept { token } → success

---

## 11. Optional Enhancements (Later)

- Add GET /invites/lookup?t= to show guardian name before accept.
- Implement decline endpoint.
- Add refresh token handling for silent renewal (not required now).
- Switch API endpoints to require Authorization on every call (replace x-account-id) when moving beyond school project.

---

Keep this outline as your FE implementation checklist. Ask if you want sample React hook or vanilla JS utility for the code+PKCE flow.