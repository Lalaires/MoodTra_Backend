````markdown
Authentication / Linking Additions
(Use together with previously documented Strategy / Mood / Chat APIs.)

Auth API
Base path: /auth

1) POST /auth/session
- Purpose: Register / update the currently signed-in Cognito user and obtain account_id for subsequent calls.
- Auth: Authorization: Bearer <id_token> (Cognito ID token; Authorization Code + PKCE flow on frontend).
- Headers: (only Authorization)
- Response: { account_id, email, display_name, account_type, status }
- Notes:
  - Only this endpoint requires the Bearer ID token (HTTPBearer). Other endpoints use x-account-id.
  - id_token must be the raw JWT string (three dot segments), not the whole token JSON.

Example:
````bash
curl -X POST http://localhost:8000/auth/session \
  -H "Authorization: Bearer <ID_TOKEN>"
````

Invite API
Base path: /invites
Used by guardians to invite a child (by email) and by the child to accept.

Statuses: invited | accepted | revoked | expired  
Invite token: raw token appears once in share_url (query param t=). Backend stores only SHA-256 hash.

1) POST /invites
- Purpose: Create a new invite (guardian → child email).
- Headers: x-account-id (guardian)
- Body: { invitee_email }
- Response: Invite object with share_url (contains raw token once).
- Constraints:
  - Only guardians.
  - One pending (status=invited) invite per guardian+email (409 if another still pending).
  - If child already linked (active), returns 409 (must unlink first).

Example:
````bash
curl -X POST http://localhost:8000/invites \
  -H "x-account-id: <GUARDIAN_ID>" \
  -H "Content-Type: application/json" \
  -d '{"invitee_email":"child@example.com"}'
````

2) GET /invites
- Purpose: List guardian’s invites (auto-expire any past expiry).
- Headers: x-account-id (guardian)
- Query (optional):
  - status=invited|accepted|revoked|expired
- Response: Array (no share_url).

Example:
````bash
curl -H "x-account-id: <GUARDIAN_ID>" \
  "http://localhost:8000/invites?status=invited"
````

3) POST /invites/accept
- Purpose: Child accepts an invite using the raw token from link (?t=...).
- Headers: x-account-id (child)
- Body: { token }
- Response: Accepted invite (no share_url).
- Behavior:
  - Verifies token, not expired, status=invited.
  - Email must match logged-in child’s email.
  - Creates link or reactivates if previously revoked.
  - Reuse → 409.

Example:
````bash
curl -X POST http://localhost:8000/invites/accept \
  -H "x-account-id: <CHILD_ID>" \
  -H "Content-Type: application/json" \
  -d '{"token":"<RAW_TOKEN>"}'
````

4) POST /invites/{invite_id}/revoke
- Purpose: Guardian revokes an unused (or even already accepted) invite (idempotent).
- Headers: x-account-id (guardian)
- Response: Invite (status updated if applicable).

Example:
````bash
curl -X POST http://localhost:8000/invites/<INVITE_ID>/revoke \
  -H "x-account-id: <GUARDIAN_ID>"
````

Link / Relationship API
Base path: /me
Represents guardian ↔ child links (guardian_child_link). Active links only returned.

1) GET /me/children (guardian)
- Purpose: List active linked children for guardian.
- Headers: x-account-id (guardian)
- Response: Array of { account_id, display_name, email }

Example:
````bash
curl -H "x-account-id: <GUARDIAN_ID>" http://localhost:8000/me/children
````

2) GET /me/guardians (child)
- Purpose: List active linked guardians for child.
- Headers: x-account-id (child)
- Response: Array of { account_id, display_name, email }

Example:
````bash
curl -H "x-account-id: <CHILD_ID>" http://localhost:8000/me/guardians
````

3) DELETE /me/links/{child_id} (guardian)
- Purpose: Guardian revokes link to specific child.
- Headers: x-account-id (guardian)
- Response: { status:"revoked", child_id }

Example:
````bash
curl -X DELETE http://localhost:8000/me/links/<CHILD_ID> \
  -H "x-account-id: <GUARDIAN_ID>"
````

4) DELETE /me/links/guardian/{guardian_id} (child)  (Optional if implemented)
- Purpose: Child severs link to guardian.
- Headers: x-account-id (child)
- Response: { status:"revoked", guardian_id }

Example:
````bash
curl -X DELETE http://localhost:8000/me/links/guardian/<GUARDIAN_ID> \
  -H "x-account-id: <CHILD_ID>"
````

Invite / Link Flow Summary
1. Guardian login → POST /auth/session → obtain account_id.
2. Guardian creates invite → receives share_url.
3. Child clicks link → logs in → POST /auth/session.
4. Child POST /invites/accept with token.
5. Guardian GET /me/children (child appears).
6. Optional unlink (guardian or child) via DELETE endpoint → re-invite if needed.

Error Codes (common)
- 400: Missing token (accept) / malformed email.
- 401: Bad / expired Cognito ID token (only /auth/session).
- 403: Role or email mismatch.
- 404: Invite token not found.
- 409: Duplicate pending invite, invite already used/expired, or already linked.
````