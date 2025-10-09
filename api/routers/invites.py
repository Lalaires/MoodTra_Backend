import os, hashlib, base64, secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..deps import get_db
from ..models import GuardianInvite, GuardianChildLink, Account
from ..schemas import InviteCreateIn, InviteOut, InviteAcceptIn, InviteListItem

router = APIRouter(prefix="/invites", tags=["invite"])
from ..deps import get_account_id

# --- helpers ---------------------------------------------------------------

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _generate_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

def _expire_if_needed(invite: GuardianInvite):
    if invite.status == "invited" and invite.expires_at < datetime.now(timezone.utc):
        invite.status = "expired"

# --- create invite ---------------------------------------------------------
@router.post("", response_model=InviteOut)
def create_invite(
    payload: InviteCreateIn,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    guardian = db.get(Account, account_id)
    if guardian.account_type != "guardian":
        raise HTTPException(status_code=403, detail="Only guardians can create invites")

    target_email = payload.invitee_email.lower()

    # 1. Load all invites for this guardian + email (small set)
    stmt_existing = select(GuardianInvite).where(
        GuardianInvite.guardian_id == account_id,
        GuardianInvite.invitee_email == target_email,
    )
    existing_invites = list(db.scalars(stmt_existing).all())
    for inv in existing_invites:
        _expire_if_needed(inv)

    pending = next((i for i in existing_invites if i.status == "invited"), None)
    accepted = next((i for i in existing_invites if i.status == "accepted"), None)

    # 2. If there is still a pending invite -> reject new one
    if pending:
        raise HTTPException(status_code=409, detail="Invite already pending for this email")

    # 3. If an invite was accepted and link is still active -> block (already linked)
    if accepted:
        # Check active link
        link_stmt = select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == account_id,
            GuardianChildLink.link_status == "active"
        )
        # Need to know the child account of that accepted invite (accepted_account_id)
        if accepted.accepted_account_id:
            link_stmt = link_stmt.where(GuardianChildLink.child_id == accepted.accepted_account_id)
            active_link = db.scalars(link_stmt).first()
            if active_link:
                raise HTTPException(status_code=409, detail="Child already linked; revoke link first to re-invite")

    # (If accepted invite exists but link revoked, we allow new invite)

    raw_token = _generate_token()
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    inv = GuardianInvite(
        guardian_id=account_id,
        invitee_email=target_email,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(inv)
    db.flush()

    share_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    share_url = f"{share_base}/accept-invite?t={raw_token}"

    return InviteOut(
        invite_id=inv.invite_id,
        invitee_email=inv.invitee_email,
        status=inv.status,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
        accepted_at=inv.accepted_at,
        accepted_account_id=inv.accepted_account_id,
        share_url=share_url,
    )

# --- list invites (unchanged except for side-effect expiry) ----------------
@router.get("", response_model=List[InviteListItem])
def list_invites(
    status: Optional[str] = Query(None, pattern="^(invited|accepted|revoked|expired)$"),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    stmt = select(GuardianInvite).where(GuardianInvite.guardian_id == account_id)
    invites = list(db.scalars(stmt).all())
    for i in invites:
        _expire_if_needed(i)
    if status:
        invites = [i for i in invites if i.status == status]
    return [
        InviteListItem(
            invite_id=i.invite_id,
            invitee_email=i.invitee_email,
            status=i.status,
            expires_at=i.expires_at,
            accepted_at=i.accepted_at,
        )
        for i in invites
    ]

# --- accept invite (reactivate link if revoked) ----------------------------
@router.post("/accept", response_model=InviteOut)
def accept_invite(
    payload: InviteAcceptIn,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    raw = (payload.token or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Token required")
    token_hash = _hash_token(raw)
    invite = db.scalar(select(GuardianInvite).where(GuardianInvite.token_hash == token_hash))
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    _expire_if_needed(invite)
    if invite.status != "invited":
        raise HTTPException(status_code=409, detail=f"Invite status={invite.status}")

    child = db.get(Account, account_id)
    if child.account_type != "child":
        child.account_type = "child"
    if invite.invitee_email.lower() != (child.email or "").lower():
        raise HTTPException(status_code=403, detail="Invite email mismatch")

    # Existing link (active or revoked)
    link = db.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == invite.guardian_id,
            GuardianChildLink.child_id == account_id,
        )
    )
    if link:
        if link.link_status == "revoked":
            # Reactivate
            link.link_status = "active"
            link.linked_at = datetime.now(timezone.utc)
            db.add(link)
        # If already active we keep it (idempotent)
    else:
        # Fresh link
        link = GuardianChildLink(
            guardian_id=invite.guardian_id,
            child_id=account_id,
        )
        db.add(link)

    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)
    invite.accepted_account_id = account_id

    db.flush()
    return InviteOut(
        invite_id=invite.invite_id,
        invitee_email=invite.invitee_email,
        status=invite.status,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        accepted_at=invite.accepted_at,
        accepted_account_id=invite.accepted_account_id,
        share_url=None,
    )

# --- revoke invite (unchanged) ---------------------------------------------
@router.post("/{invite_id}/revoke", response_model=InviteOut)
def revoke_invite(
    invite_id: str,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    inv = db.get(GuardianInvite, invite_id)
    if not inv or inv.guardian_id != account_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv.status not in ("accepted", "revoked", "expired"):
        inv.status = "revoked"
    db.flush()
    return InviteOut(
        invite_id=inv.invite_id,
        invitee_email=inv.invitee_email,
        status=inv.status,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
        accepted_at=inv.accepted_at,
        accepted_account_id=inv.accepted_account_id,
    )