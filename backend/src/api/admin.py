"""T070 — Admin endpoints for XMPP connection monitoring."""
from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.models.user import User
from src.services.jabber_server import get_c2s_sessions, get_s2s_links

router = APIRouter()


@router.get("/admin/jabber/connections")
def jabber_connections(current_user: User = Depends(get_current_user)) -> list[dict]:
    """List active C2S sessions: [{jid, user_id, connected_at, messages_in, messages_out}]"""
    return get_c2s_sessions()


@router.get("/admin/jabber/federation")
def jabber_federation(current_user: User = Depends(get_current_user)) -> list[dict]:
    """List active S2S federation links: [{domain, connected_at, messages_in, messages_out}]"""
    return get_s2s_links()
