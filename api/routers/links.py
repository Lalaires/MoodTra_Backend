from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from uuid import UUID as UUIDT
from ..deps import get_db, get_account_id
from ..models import GuardianChildLink, Account
from ..schemas import LinkedChild, LinkedGuardian

router = APIRouter(prefix="/me", tags=["link"])

# Guardians can see their children
@router.get("/children", response_model=list[LinkedChild])
def list_children(
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    guardian = db.get(Account, account_id)
    if guardian.account_type != "guardian":
        raise HTTPException(status_code=403, detail="Not a guardian")
    stmt = (
        select(Account)
        .join(GuardianChildLink, GuardianChildLink.child_id == Account.account_id)
        .where(
            GuardianChildLink.guardian_id == account_id,
            GuardianChildLink.link_status == "active",
        )
        .order_by(Account.display_name.asc())
    )
    return [
        LinkedChild(account_id=a.account_id, display_name=a.display_name, email=a.email)
        for a in db.scalars(stmt)
    ]

# Children can see their guardians
@router.get("/guardians", response_model=list[LinkedGuardian])
def list_guardians(
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    child = db.get(Account, account_id)
    if child.account_type != "child":
        raise HTTPException(status_code=403, detail="Not a child")
    stmt = (
        select(Account)
        .join(GuardianChildLink, GuardianChildLink.guardian_id == Account.account_id)
        .where(
            GuardianChildLink.child_id == account_id,
            GuardianChildLink.link_status == "active",
        )
        .order_by(Account.display_name.asc())
    )
    return [
        LinkedGuardian(account_id=a.account_id, display_name=a.display_name, email=a.email)
        for a in db.scalars(stmt)
    ]

# Guardian revokes a link to a child
@router.delete("/links/{child_id}")
def revoke_link(
    child_id: UUIDT,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    # Guardian revokes
    stmt = select(GuardianChildLink).where(
        GuardianChildLink.guardian_id == account_id,
        GuardianChildLink.child_id == child_id,
        GuardianChildLink.link_status == "active",
    )
    link = db.scalars(stmt).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    link.link_status = "revoked"
    db.add(link)
    return {"status": "revoked", "child_id": str(child_id)}

# Child revokes a link to a guardian
@router.delete("/links/guardian/{guardian_id}")
def child_unlink_guardian(
    guardian_id: UUIDT,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    Child-initiated unlink. Child revokes relationship with given guardian.
    """
    child_acct = db.get(Account, account_id)
    if child_acct.account_type != "child":
        raise HTTPException(status_code=403, detail="Not a child")
    link = db.scalar(
        select(GuardianChildLink).where(
            GuardianChildLink.guardian_id == guardian_id,
            GuardianChildLink.child_id == account_id,
            GuardianChildLink.link_status == "active",
        )
    )
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    link.link_status = "revoked"
    db.add(link)
    return {"status": "revoked", "guardian_id": str(guardian_id)}