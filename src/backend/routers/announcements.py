"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _require_teacher(username: Optional[str]) -> Dict[str, Any]:
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return teacher


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return active announcements (now within optional start and required expiration)."""
    now = datetime.now(timezone.utc)
    query = {
        "$and": [
            {"$or": [
                {"starts_at": {"$exists": False}},
                {"starts_at": {"$lte": now}}
            ]},
            {"expires_at": {"$gt": now}}
        ]
    }
    items: List[Dict[str, Any]] = []
    for a in announcements_collection.find(query).sort("created_at", 1):
        item = {
            "id": a.get("_id"),
            "message": a.get("message"),
            "starts_at": a.get("starts_at"),
            "expires_at": a.get("expires_at"),
            "created_at": a.get("created_at"),
            "updated_at": a.get("updated_at"),
        }
        items.append(item)
    return items


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    _require_teacher(teacher_username)
    items: List[Dict[str, Any]] = []
    for a in announcements_collection.find({}).sort("created_at", -1):
        items.append({
            "id": a.get("_id"),
            "message": a.get("message"),
            "starts_at": a.get("starts_at"),
            "expires_at": a.get("expires_at"),
            "created_at": a.get("created_at"),
            "updated_at": a.get("updated_at"),
        })
    return items


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    body: Dict[str, Any],
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    _require_teacher(teacher_username)

    message = (body or {}).get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    expires_at_raw = (body or {}).get("expires_at")
    starts_at_raw = (body or {}).get("starts_at")

    def parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            # Prefer ISO strings; if naive, assume UTC
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid datetime format")

    expires_at = parse_dt(expires_at_raw)
    if not expires_at:
        raise HTTPException(status_code=400, detail="Expiration is required")

    starts_at = parse_dt(starts_at_raw)

    now = datetime.now(timezone.utc)
    doc = {
        "_id": f"ann-{int(now.timestamp()*1000)}",
        "message": message,
        "starts_at": starts_at,
        "expires_at": expires_at,
        "created_at": now,
        "updated_at": now,
    }

    announcements_collection.insert_one(doc)
    return {
        "id": doc["_id"],
        "message": doc["message"],
        "starts_at": doc["starts_at"],
        "expires_at": doc["expires_at"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    body: Dict[str, Any],
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    _require_teacher(teacher_username)

    doc = announcements_collection.find_one({"_id": announcement_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updates: Dict[str, Any] = {}

    if "message" in body:
        message = (body.get("message") or "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        updates["message"] = message

    def parse_dt_optional(value: Any) -> Any:
        if value is None:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid datetime format")

    if "starts_at" in body:
        updates["starts_at"] = parse_dt_optional(body.get("starts_at"))

    if "expires_at" in body:
        parsed = parse_dt_optional(body.get("expires_at"))
        if not parsed:
            raise HTTPException(status_code=400, detail="Expiration is required")
        updates["expires_at"] = parsed

    updates["updated_at"] = datetime.now(timezone.utc)

    announcements_collection.update_one({"_id": announcement_id}, {"$set": updates})

    new_doc = announcements_collection.find_one({"_id": announcement_id})
    return {
        "id": new_doc.get("_id"),
        "message": new_doc.get("message"),
        "starts_at": new_doc.get("starts_at"),
        "expires_at": new_doc.get("expires_at"),
        "created_at": new_doc.get("created_at"),
        "updated_at": new_doc.get("updated_at"),
    }


@router.delete("/{announcement_id}", response_model=Dict[str, Any])
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    _require_teacher(teacher_username)

    res = announcements_collection.delete_one({"_id": announcement_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted"}
