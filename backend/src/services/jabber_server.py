"""T068 / T069 — Minimal XMPP C2S and S2S server using asyncio raw TCP."""
import asyncio
import base64
import logging
import re
import uuid
from datetime import datetime

import bcrypt

from src.config import XMPP_DOMAIN, XMPP_S2S_PEERS
from src.models.base import SessionLocal
from src.models.room import Room
from src.models.user import User

logger = logging.getLogger(__name__)

# ── Module-level session trackers ─────────────────────────────────────────────

# jid → {user_id, jid, connected_at, messages_in, messages_out}
_c2s_sessions: dict[str, dict] = {}

# remote_domain → {domain, connected_at, messages_in, messages_out}
_s2s_links: dict[str, dict] = {}

# ── XML helpers ───────────────────────────────────────────────────────────────


def _try_extract_stanza(text: str) -> "str | None":
    """Try to extract one complete XML element from the beginning of text.
    Returns the element string or None if incomplete."""
    text = text.lstrip()
    if not text or not text.startswith("<"):
        return None

    # Find tag name
    m = re.match(r"<([a-zA-Z:][^\s/>]*)", text)
    if not m:
        return None

    # Self-closing: <tag ... />
    if re.match(r"<[^>]*/\s*>", text, re.DOTALL):
        end = text.index("/>") + 2
        return text[:end]

    # Look for matching close tag using depth counter
    tag_local = m.group(1).split(":")[-1]
    depth = 0
    i = 0
    while i < len(text):
        if text[i] == "<":
            if i + 1 < len(text) and text[i + 1] == "/":
                # closing tag
                depth -= 1
                if depth == 0:
                    end = text.index(">", i) + 1
                    return text[:end]
            elif i + 1 < len(text) and text[i + 1] == "?":
                pass  # processing instruction
            else:
                # check if self-closing
                end_bracket = text.find(">", i)
                if end_bracket == -1:
                    return None
                snippet = text[i : end_bracket + 1]
                if snippet.endswith("/>"):
                    i = end_bracket + 1
                    continue
                depth += 1
        i += 1
    return None


async def _read_stanza(reader: asyncio.StreamReader, buf_holder: list) -> str:
    """Extract one complete XML element from the buffer. Returns the xml string."""
    while True:
        text = buf_holder[0].decode("utf-8", errors="ignore")
        stanza = _try_extract_stanza(text)
        if stanza is not None:
            buf_holder[0] = buf_holder[0][len(stanza.encode("utf-8")) :]
            return stanza
        chunk = await reader.read(4096)
        if not chunk:
            raise ConnectionResetError("Client disconnected")
        buf_holder[0] += chunk


async def _read_until_stream_open(reader: asyncio.StreamReader, buf_holder: list) -> str:
    """Read until we see the end of an opening <stream:stream ...> tag."""
    while True:
        text = buf_holder[0].decode("utf-8", errors="ignore")
        # The stream open tag ends at the first '>'
        idx = text.find(">")
        if idx != -1:
            header = text[: idx + 1]
            buf_holder[0] = buf_holder[0][len(header.encode("utf-8")) :]
            return header
        chunk = await reader.read(4096)
        if not chunk:
            raise ConnectionResetError("Client disconnected during stream open")
        buf_holder[0] += chunk


# ── XMPP namespace helpers ────────────────────────────────────────────────────

_NS_STREAM = "http://etherx.jabber.org/streams"
_NS_CLIENT = "jabber:client"
_NS_SASL = "urn:ietf:params:xml:ns:xmpp-sasl"
_NS_BIND = "urn:ietf:params:xml:ns:xmpp-bind"
_NS_SESSION = "urn:ietf:params:xml:ns:xmpp-session"


def _stream_open(domain: str, stream_id: str) -> str:
    return (
        f'<?xml version="1.0"?>'
        f'<stream:stream xmlns="jabber:client" '
        f'xmlns:stream="http://etherx.jabber.org/streams" '
        f'id="{stream_id}" '
        f'from="{domain}" '
        f'version="1.0">'
    )


def _features_sasl() -> str:
    return (
        "<stream:features>"
        '<mechanisms xmlns="urn:ietf:params:xml:ns:xmpp-sasl">'
        "<mechanism>PLAIN</mechanism>"
        "</mechanisms>"
        "</stream:features>"
    )


def _features_bind() -> str:
    return (
        "<stream:features>"
        f'<bind xmlns="{_NS_BIND}"/>'
        f'<session xmlns="{_NS_SESSION}"/>'
        "</stream:features>"
    )


# ── Database helpers ──────────────────────────────────────────────────────────


def _get_user_by_username(username: str) -> "User | None":
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


def _get_user_by_id(user_id: int) -> "User | None":
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _get_room_by_name(name: str) -> "Room | None":
    db = SessionLocal()
    try:
        return db.query(Room).filter(Room.name == name).first()
    finally:
        db.close()


# ── Stanza parsing ────────────────────────────────────────────────────────────


def _parse_tag_name(xml_str: str) -> str:
    """Extract the local element name (without namespace prefix) from an XML string."""
    m = re.match(r"<([a-zA-Z:][^\s/>]*)", xml_str.lstrip())
    if not m:
        return ""
    return m.group(1).split(":")[-1]


def _get_attr(xml_str: str, attr: str) -> "str | None":
    """Extract attribute value from an XML tag string."""
    pattern = rf'{attr}=["\']([^"\']*)["\']'
    m = re.search(pattern, xml_str)
    return m.group(1) if m else None


def _get_text_content(xml_str: str, tag: str) -> "str | None":
    """Extract text content of a child element."""
    pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
    m = re.search(pattern, xml_str, re.DOTALL)
    return m.group(1).strip() if m else None


# ── Message routing ───────────────────────────────────────────────────────────


async def _route_message(sender_user: User, to_jid: str, body: str) -> None:
    """Route an XMPP message to the appropriate handler."""
    if not to_jid or not body:
        return

    from src.services.messaging import send_dm, send_room_message

    # Parse JID: user@domain or room@conference.domain
    parts = to_jid.split("@")
    if len(parts) != 2:
        return

    local, domain_part = parts[0], parts[1]

    # Check if it's a conference (MUC) address
    if domain_part.startswith("conference.") or domain_part.startswith("conf."):
        # Room message
        room = _get_room_by_name(local)
        if room:
            db = SessionLocal()
            try:
                await send_room_message(
                    db=db,
                    room_id=room.id,
                    sender_id=sender_user.id,
                    sender_username=sender_user.username,
                    content=body,
                )
            except Exception as e:
                logger.warning("Failed to send room message via XMPP: %s", e)
            finally:
                db.close()
        return

    # Check if message targets a foreign domain (S2S)
    if domain_part != XMPP_DOMAIN and not domain_part.endswith(".local"):
        await _relay_s2s(to_jid, sender_user, body)
        return

    # Local DM
    recipient = _get_user_by_username(local)
    if recipient:
        db = SessionLocal()
        try:
            await send_dm(
                db=db,
                sender_id=sender_user.id,
                sender_username=sender_user.username,
                recipient_id=recipient.id,
                content=body,
            )
        except PermissionError as e:
            logger.debug("XMPP DM permission error: %s", e)
        except Exception as e:
            logger.warning("Failed to send DM via XMPP: %s", e)
        finally:
            db.close()


# ── S2S outbound relay ────────────────────────────────────────────────────────


async def _relay_s2s(to_jid: str, sender_user: User, body: str) -> None:
    """Relay a message to a foreign domain via S2S."""
    parts = to_jid.split("@")
    if len(parts) != 2:
        return
    remote_domain = parts[1].split("/")[0]

    # Find the peer address from config
    peer_addr = None
    for peer in XMPP_S2S_PEERS.split(","):
        peer = peer.strip()
        if not peer:
            continue
        host_part = peer.split(":")[0]
        port_part = int(peer.split(":")[1]) if ":" in peer else 5269
        if host_part == remote_domain:
            peer_addr = (host_part, port_part)
            break

    if not peer_addr:
        logger.warning("No S2S peer configured for domain: %s", remote_domain)
        return

    try:
        reader, writer = await asyncio.open_connection(peer_addr[0], peer_addr[1])
        stream_id = str(uuid.uuid4())
        # Send stream open
        writer.write(
            f'<?xml version="1.0"?>'
            f'<stream:stream xmlns:stream="http://etherx.jabber.org/streams" '
            f'xmlns="jabber:server" '
            f'from="{XMPP_DOMAIN}" '
            f'to="{remote_domain}" '
            f'version="1.0">'.encode()
        )
        # Send message stanza
        msg_xml = (
            f'<message xmlns="jabber:server" '
            f'from="{sender_user.username}@{XMPP_DOMAIN}" '
            f'to="{to_jid}">'
            f"<body>{body}</body>"
            f"</message>"
        )
        writer.write(msg_xml.encode())
        writer.write(b"</stream:stream>")
        await writer.drain()
        writer.close()

        # Track link
        if remote_domain not in _s2s_links:
            _s2s_links[remote_domain] = {
                "domain": remote_domain,
                "connected_at": datetime.utcnow().isoformat(),
                "messages_in": 0,
                "messages_out": 0,
                "errors": 0,
            }
        _s2s_links[remote_domain]["messages_out"] += 1
        logger.info("S2S relayed message to %s", remote_domain)
    except Exception as e:
        logger.error("S2S relay failed for domain %s: %s", remote_domain, e)
        if remote_domain in _s2s_links:
            _s2s_links[remote_domain]["errors"] += 1


# ── C2S handler ───────────────────────────────────────────────────────────────


async def _handle_c2s(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle a single C2S (Client-to-Server) connection."""
    peer = writer.get_extra_info("peername")
    logger.info("C2S connection from %s", peer)
    buf_holder = [b""]
    authenticated_user: "User | None" = None
    jid: "str | None" = None

    async def send(data: str) -> None:
        writer.write(data.encode("utf-8"))
        await writer.drain()

    try:
        # ── Step 1: Read initial <stream:stream> open ─────────────────────────
        stream_id = str(uuid.uuid4())[:8]
        await _read_until_stream_open(reader, buf_holder)

        # ── Step 2: Send stream open + SASL features ──────────────────────────
        await send(_stream_open(XMPP_DOMAIN, stream_id))
        await send(_features_sasl())

        # ── Step 3: Read SASL auth ────────────────────────────────────────────
        auth_xml = await _read_stanza(reader, buf_holder)
        tag_name = _parse_tag_name(auth_xml)

        if tag_name != "auth":
            logger.warning("Expected <auth>, got <%s>", tag_name)
            writer.close()
            return

        mechanism = _get_attr(auth_xml, "mechanism")
        if mechanism != "PLAIN":
            await send('<failure xmlns="urn:ietf:params:xml:ns:xmpp-sasl"><invalid-mechanism/></failure>')
            writer.close()
            return

        # Extract base64-encoded credentials: \0username\0password
        b64_content = _get_text_content(auth_xml, "auth") or ""
        # The content may be directly in the auth tag
        m = re.search(r"<auth[^>]*>(.*?)</auth>", auth_xml, re.DOTALL)
        b64_content = m.group(1).strip() if m else ""

        try:
            decoded = base64.b64decode(b64_content).decode("utf-8")
            parts = decoded.split("\x00")
            # Format: [authzid, username, password] or [\x00, username, password]
            if len(parts) == 3:
                _, username, password = parts
            elif len(parts) == 2:
                username, password = parts
            else:
                raise ValueError("Invalid PLAIN format")
        except Exception:
            await send('<failure xmlns="urn:ietf:params:xml:ns:xmpp-sasl"><incorrect-encoding/></failure>')
            writer.close()
            return

        # Verify credentials
        user = _get_user_by_username(username)
        auth_ok = False
        if user:
            try:
                auth_ok = bcrypt.checkpw(password.encode(), user.password_hash.encode())
            except Exception:
                auth_ok = False

        if not auth_ok:
            await send('<failure xmlns="urn:ietf:params:xml:ns:xmpp-sasl"><not-authorized/></failure>')
            writer.close()
            return

        authenticated_user = user
        await send('<success xmlns="urn:ietf:params:xml:ns:xmpp-sasl"/>')

        # ── Step 4: Client reopens stream ─────────────────────────────────────
        stream_id2 = str(uuid.uuid4())[:8]
        await _read_until_stream_open(reader, buf_holder)
        await send(_stream_open(XMPP_DOMAIN, stream_id2))
        await send(_features_bind())

        # ── Step 5: Resource binding ──────────────────────────────────────────
        bind_xml = await _read_stanza(reader, buf_holder)
        tag_name = _parse_tag_name(bind_xml)

        resource = "default"
        iq_id = _get_attr(bind_xml, "id") or "bind1"

        if tag_name == "iq":
            resource_val = _get_text_content(bind_xml, "resource")
            if resource_val:
                resource = resource_val

        jid = f"{authenticated_user.username}@{XMPP_DOMAIN}/{resource}"
        await send(
            f'<iq type="result" id="{iq_id}">'
            f'<bind xmlns="{_NS_BIND}">'
            f"<jid>{jid}</jid>"
            f"</bind>"
            f"</iq>"
        )

        # Register session
        _c2s_sessions[jid] = {
            "user_id": authenticated_user.id,
            "jid": jid,
            "connected_at": datetime.utcnow().isoformat(),
            "messages_in": 0,
            "messages_out": 0,
            "errors": 0,
        }

        logger.info("C2S session established: %s", jid)

        # ── Step 6: Stanza loop ───────────────────────────────────────────────
        while True:
            stanza_xml = await _read_stanza(reader, buf_holder)
            tag_name = _parse_tag_name(stanza_xml)
            _c2s_sessions[jid]["messages_in"] += 1

            if tag_name == "iq":
                iq_id = _get_attr(stanza_xml, "id") or "1"
                iq_type = _get_attr(stanza_xml, "type") or ""
                # Session IQ or ping
                await send(f'<iq type="result" id="{iq_id}"/>')

            elif tag_name == "message":
                to_jid = _get_attr(stanza_xml, "to") or ""
                body = _get_text_content(stanza_xml, "body") or ""
                if body and to_jid and authenticated_user:
                    asyncio.create_task(_route_message(authenticated_user, to_jid, body))
                _c2s_sessions[jid]["messages_out"] += 1

            elif tag_name == "presence":
                # Acknowledge presence
                from_jid = jid
                await send(f'<presence from="{from_jid}"/>')

            # stream close
            elif "stream:stream" in stanza_xml and "/" in stanza_xml[:15]:
                break

    except ConnectionResetError:
        logger.info("C2S client disconnected: %s", peer)
    except asyncio.IncompleteReadError:
        logger.info("C2S stream ended: %s", peer)
    except Exception as e:
        logger.error("C2S handler error for %s: %s", peer, e)
        if jid and jid in _c2s_sessions:
            _c2s_sessions[jid]["errors"] += 1
    finally:
        if jid and jid in _c2s_sessions:
            del _c2s_sessions[jid]
            logger.info("C2S session removed: %s", jid)
        try:
            writer.close()
        except Exception:
            pass


# ── S2S handler ───────────────────────────────────────────────────────────────


async def _handle_s2s(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle an incoming S2S (Server-to-Server) connection."""
    peer = writer.get_extra_info("peername")
    logger.info("S2S connection from %s", peer)
    buf_holder = [b""]
    remote_domain: "str | None" = None

    async def send(data: str) -> None:
        writer.write(data.encode("utf-8"))
        await writer.drain()

    try:
        # Read stream open
        stream_header = await _read_until_stream_open(reader, buf_holder)
        from_domain = _get_attr(stream_header, "from") or str(peer)
        remote_domain = from_domain

        # Register S2S link
        if remote_domain not in _s2s_links:
            _s2s_links[remote_domain] = {
                "domain": remote_domain,
                "connected_at": datetime.utcnow().isoformat(),
                "messages_in": 0,
                "messages_out": 0,
                "errors": 0,
            }

        stream_id = str(uuid.uuid4())[:8]
        await send(
            f'<?xml version="1.0"?>'
            f'<stream:stream xmlns:stream="http://etherx.jabber.org/streams" '
            f'xmlns="jabber:server" '
            f'id="{stream_id}" '
            f'from="{XMPP_DOMAIN}" '
            f'to="{remote_domain}" '
            f'version="1.0">'
        )
        await send("<stream:features/>")

        # Stanza loop
        while True:
            stanza_xml = await _read_stanza(reader, buf_holder)
            tag_name = _parse_tag_name(stanza_xml)
            _s2s_links[remote_domain]["messages_in"] += 1

            if tag_name == "message":
                to_jid = _get_attr(stanza_xml, "to") or ""
                from_jid = _get_attr(stanza_xml, "from") or ""
                body = _get_text_content(stanza_xml, "body") or ""

                if to_jid and body:
                    local_part = to_jid.split("@")[0] if "@" in to_jid else to_jid
                    from_user = _get_user_by_username(from_jid.split("@")[0] if "@" in from_jid else from_jid)
                    recipient = _get_user_by_username(local_part)

                    if recipient and from_user:
                        from src.services.messaging import send_dm
                        db = SessionLocal()
                        try:
                            await send_dm(
                                db=db,
                                sender_id=from_user.id,
                                sender_username=from_user.username,
                                recipient_id=recipient.id,
                                content=body,
                            )
                        except Exception as e:
                            logger.warning("S2S DM routing error: %s", e)
                        finally:
                            db.close()

    except ConnectionResetError:
        logger.info("S2S client disconnected: %s", peer)
    except asyncio.IncompleteReadError:
        logger.info("S2S stream ended: %s", peer)
    except Exception as e:
        logger.error("S2S handler error for %s: %s", peer, e)
        if remote_domain and remote_domain in _s2s_links:
            _s2s_links[remote_domain]["errors"] += 1
    finally:
        if remote_domain and remote_domain in _s2s_links:
            del _s2s_links[remote_domain]
        try:
            writer.close()
        except Exception:
            pass


# ── Public API ────────────────────────────────────────────────────────────────


async def start_jabber_server() -> None:
    """Start the XMPP C2S server on port 5222 and S2S server on port 5269."""
    try:
        c2s_server = await asyncio.start_server(_handle_c2s, "0.0.0.0", 5222)
        addrs_c2s = ", ".join(str(s.getsockname()) for s in c2s_server.sockets)
        logger.info("XMPP C2S server listening on %s", addrs_c2s)
        asyncio.create_task(c2s_server.serve_forever())
    except OSError as e:
        logger.warning("XMPP C2S server could not bind (port 5222): %s", e)

    try:
        s2s_server = await asyncio.start_server(_handle_s2s, "0.0.0.0", 5269)
        addrs_s2s = ", ".join(str(s.getsockname()) for s in s2s_server.sockets)
        logger.info("XMPP S2S server listening on %s", addrs_s2s)
        asyncio.create_task(s2s_server.serve_forever())
    except OSError as e:
        logger.warning("XMPP S2S server could not bind (port 5269): %s", e)


def get_c2s_sessions() -> list[dict]:
    """Return a snapshot of active C2S sessions."""
    return list(_c2s_sessions.values())


def get_s2s_links() -> list[dict]:
    """Return a snapshot of active S2S federation links."""
    return list(_s2s_links.values())
