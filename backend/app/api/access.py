from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AccessRequestEvent, ActionProposal, User
from app.schemas.access import AccessArguments, Decision
from app.services import access
from app.services.auth import current_user
from app.services.onboarding import overview

router = APIRouter(tags=["Corporate actions"])


@router.get("/access-requests")
def list_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return access.requests(db, user)


@router.get("/access-requests/{request_id}")
def detail(request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = access.get_request(db, user, request_id)
    events = db.scalars(
        select(AccessRequestEvent)
        .where(AccessRequestEvent.request_id == item.id)
        .order_by(AccessRequestEvent.id)
    ).all()
    return access.serialize(item) | {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "comment": e.comment,
                "created_at": e.created_at,
            }
            for e in events
        ]
    }


@router.post("/assistant/actions/prepare")
def prepare(
    body: AccessArguments, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = access.prepare(db, user, body)
    db.commit()
    return proposal_data(item)


def proposal_data(item):
    return {
        "id": item.id,
        "parameters": item.parameters,
        "state": item.state,
        "expires_at": item.expires_at,
        "conversation_id": item.conversation_id,
    }


@router.get("/assistant/actions")
def proposals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        proposal_data(p)
        for p in db.scalars(
            select(ActionProposal)
            .where(ActionProposal.user_id == user.id)
            .order_by(ActionProposal.created_at.desc())
            .limit(100)
        ).all()
    ]


@router.post("/assistant/actions/{proposal_id}/confirm")
def confirm(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = access.serialize(access.confirm(db, user, proposal_id))
    db.commit()
    return result


@router.post("/assistant/actions/{proposal_id}/cancel")
def cancel(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = access.cancel(db, user, proposal_id)
    db.commit()
    return result


@router.post("/access-requests/{request_id}/approve")
def approve(
    request_id: int,
    body: Decision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    result = access.serialize(access.decide(db, user, request_id, "approved", body.comment))
    db.commit()
    return result


@router.post("/access-requests/{request_id}/reject")
def reject(
    request_id: int,
    body: Decision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    result = access.serialize(access.decide(db, user, request_id, "rejected", body.comment))
    db.commit()
    return result


@router.get("/mentor/overview")
def mentor_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    from app.models import Team

    if user.role not in ("mentor", "manager"):
        raise HTTPException(403, "Раздел доступен наставнику и руководителю")
    query = select(User).where(User.team_id == user.team_id, User.role == "intern")
    if user.role == "mentor":
        query = query.where(User.mentor_id == user.id)
    elif db.get(Team, user.team_id).leader_id != user.id:
        raise HTTPException(403, "Вы не руководитель команды")
    interns = [
        {"id": p.id, "full_name": p.full_name, "onboarding": overview(db, p.id)}
        for p in db.scalars(query).all()
    ]
    items = access.requests(db, user)
    return {
        "interns": interns,
        "requests": len(items),
        "pending": sum(x["status"] == "pending" for x in items),
        "approved": sum(x["status"] == "approved" for x in items),
        "rejected": sum(x["status"] == "rejected" for x in items),
    }
