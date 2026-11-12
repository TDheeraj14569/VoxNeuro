"""Backend authentication, session lifecycle, password reset, and server-side RBAC."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from voxneuro.study.audit import log_audit_event
from voxneuro.study.database import transaction
from voxneuro.study.schema import utc_now_iso

VALID_ROLES: tuple[str, ...] = ("participant", "researcher", "ml_admin", "admin")
PBKDF2_ITERATIONS = 200_000
DEFAULT_SESSION_TTL_HOURS = 12
DEFAULT_RESET_TTL_MINUTES = 30


class AuthorizationError(PermissionError):
    """Raised when an unauthenticated or unauthorized user attempts a restricted action."""


@dataclass(frozen=True)
class UserAccount:
    """Authenticated platform account excluding password material."""

    user_id: str
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool
    participant_id: str | None
    study_id: str | None
    prediction_retention_opt_in: bool
    created_at: str
    updated_at: str
    last_login_at: str | None


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Hash a secret password using per-user salt and PBKDF2-HMAC-SHA256."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a PBKDF2-HMAC-SHA256 hash using constant-time comparison."""
    try:
        scheme, iter_text, salt_hex, digest_hex = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iter_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _row_to_user(row: sqlite3.Row) -> UserAccount:
    return UserAccount(
        user_id=row["user_id"],
        username=row["username"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        participant_id=row["participant_id"],
        study_id=row["study_id"],
        prediction_retention_opt_in=bool(row["prediction_retention_opt_in"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_login_at=row["last_login_at"],
    )


def _normalize_username(username: str) -> str:
    cleaned = username.strip().lower()
    if len(cleaned) < 3 or any(ch.isspace() for ch in cleaned):
        raise ValueError("Username must be at least 3 non-whitespace characters.")
    return cleaned


def _normalize_email(email: str) -> str:
    cleaned = email.strip().lower()
    if "@" not in cleaned or "." not in cleaned.split("@", 1)[-1]:
        raise ValueError("A valid email address is required.")
    return cleaned


def register_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    email: str,
    password: str,
    display_name: str = "",
    role: str = "participant",
    participant_id: str | None = None,
    study_id: str | None = None,
    prediction_retention_opt_in: bool = False,
    actor: UserAccount | None = None,
    actor_session_token: str | None = None,
) -> UserAccount:
    """Create a user account; elevated roles require an authenticated admin actor or bootstrap."""
    if role not in VALID_ROLES:
        raise ValueError(f"Unsupported role {role!r}. Expected one of {VALID_ROLES}.")
    if role != "participant":
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin' AND is_active = 1;")
        admin_count = int(cursor.fetchone()["cnt"])
        if admin_count > 0:
            if actor_session_token:
                actor = require_role(conn, actor_session_token, {"admin"})
            elif actor is not None:
                row = conn.execute(
                    "SELECT is_active, role FROM users WHERE user_id = ?;",
                    (actor.user_id,),
                ).fetchone()
                if not row or not bool(row["is_active"]) or row["role"] != "admin":
                    raise AuthorizationError(
                        "Supplied actor is not an active verified administrator in this system."
                    )
            else:
                raise AuthorizationError(
                    "Creating researcher, ml_admin, or admin accounts "
                    "requires an active admin session."
                )
    norm_username = _normalize_username(username)
    norm_email = _normalize_email(email)
    pw_hash = hash_password(password)
    user_id = f"usr-{uuid.uuid4().hex[:12]}"
    now_iso = utc_now_iso()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO users (
                user_id, username, email, display_name, password_hash, role,
                is_active, participant_id, study_id, prediction_retention_opt_in,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                norm_username,
                norm_email,
                display_name.strip() or norm_username,
                pw_hash,
                role,
                participant_id,
                study_id,
                1 if prediction_retention_opt_in else 0,
                now_iso,
                now_iso,
            ),
        )
        log_audit_event(
            conn,
            operation_type="USER_ACCOUNT_CREATED",
            entity_type="user",
            entity_id=user_id,
            actor_role=actor.role if actor else "self_registration",
            details={"role": role, "has_participant_link": bool(participant_id)},
        )
    return get_user_by_id(conn, user_id)


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> UserAccount:
    """Fetch a user account by user_id."""
    row = conn.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,)).fetchone()
    if not row:
        raise KeyError(f"User not found: {user_id!r}")
    return _row_to_user(row)


def authenticate_user(
    conn: sqlite3.Connection,
    *,
    identifier: str,
    password: str,
    ttl_hours: int = DEFAULT_SESSION_TTL_HOURS,
) -> tuple[UserAccount, str]:
    """Authenticate username/email + password and issue an opaque bearer session token."""
    norm = identifier.strip().lower()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?;",
        (norm, norm),
    ).fetchone()
    if not row or not bool(row["is_active"]) or not verify_password(password, row["password_hash"]):
        raise AuthorizationError("Invalid credentials or inactive account.")
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    now_dt = datetime.now(UTC)
    now_iso = now_dt.isoformat()
    expires_iso = (now_dt + timedelta(hours=max(1, ttl_hours))).isoformat()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO user_sessions (session_token_hash, user_id, role, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (token_hash, row["user_id"], row["role"], now_iso, expires_iso),
        )
        conn.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE user_id = ?;",
            (now_iso, now_iso, row["user_id"]),
        )
        log_audit_event(
            conn,
            operation_type="USER_SIGN_IN",
            entity_type="user",
            entity_id=row["user_id"],
            actor_role=row["role"],
            details={"session_ttl_hours": ttl_hours},
        )
    return get_user_by_id(conn, row["user_id"]), raw_token


def resolve_session_user(conn: sqlite3.Connection, session_token: str | None) -> UserAccount | None:
    """Resolve an active non-expired bearer session token to its UserAccount."""
    if not session_token or not isinstance(session_token, str):
        return None
    token_hash = _hash_token(session_token.strip())
    row = conn.execute(
        """
        SELECT s.expires_at, s.revoked_at, u.*
        FROM user_sessions s
        JOIN users u ON u.user_id = s.user_id
        WHERE s.session_token_hash = ?;
        """,
        (token_hash,),
    ).fetchone()
    if not row or row["revoked_at"] is not None or not bool(row["is_active"]):
        return None
    if datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
        return None
    return _row_to_user(row)


def revoke_session(conn: sqlite3.Connection, session_token: str) -> bool:
    """Revoke an active session token on sign-out."""
    token_hash = _hash_token(session_token.strip())
    now_iso = utc_now_iso()
    with transaction(conn):
        cur = conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = ?
            WHERE session_token_hash = ? AND revoked_at IS NULL;
            """,
            (now_iso, token_hash),
        )
        return cur.rowcount > 0


def require_authenticated_user(conn: sqlite3.Connection, session_token: str | None) -> UserAccount:
    """Enforce valid server-side authentication or raise AuthorizationError."""
    user = resolve_session_user(conn, session_token)
    if user is None:
        raise AuthorizationError("Authentication required for this action.")
    return user


def require_role(
    conn: sqlite3.Connection,
    session_token: str | None,
    allowed_roles: tuple[str, ...] | set[str],
) -> UserAccount:
    """Enforce server-side RBAC for a restricted backend or UI action."""
    user = require_authenticated_user(conn, session_token)
    if user.role not in allowed_roles:
        raise AuthorizationError(
            f"Role {user.role!r} is not authorized; requires one of {sorted(allowed_roles)}."
        )
    return user


def update_user_profile_preferences(
    conn: sqlite3.Connection,
    session_token: str | None,
    *,
    display_name: str | None = None,
    prediction_retention_opt_in: bool | None = None,
) -> UserAccount:
    """Update the authenticated user's own display preferences and retention opt-in."""
    user = require_authenticated_user(conn, session_token)
    now_iso = utc_now_iso()
    next_name = (
        display_name.strip()
        if display_name is not None and display_name.strip()
        else user.display_name
    )
    next_opt_in = (
        1
        if prediction_retention_opt_in
        else 0
        if prediction_retention_opt_in is not None
        else (1 if user.prediction_retention_opt_in else 0)
    )
    with transaction(conn):
        conn.execute(
            """
            UPDATE users
            SET display_name = ?, prediction_retention_opt_in = ?, updated_at = ?
            WHERE user_id = ?;
            """,
            (next_name, next_opt_in, now_iso, user.user_id),
        )
        log_audit_event(
            conn,
            operation_type="USER_PROFILE_UPDATED",
            entity_type="user",
            entity_id=user.user_id,
            actor_role=user.role,
            details={"prediction_retention_opt_in": bool(next_opt_in)},
        )
    return get_user_by_id(conn, user.user_id)


def update_user_role_or_status(
    conn: sqlite3.Connection,
    admin_session_token: str | None,
    *,
    target_user_id: str,
    new_role: str | None = None,
    is_active: bool | None = None,
) -> UserAccount:
    """Admin-only RBAC management to adjust user roles or active status."""
    admin = require_role(conn, admin_session_token, {"admin"})
    target = get_user_by_id(conn, target_user_id)
    role_val = target.role if new_role is None else new_role
    if role_val not in VALID_ROLES:
        raise ValueError(f"Unsupported role {role_val!r}.")
    active_val = target.is_active if is_active is None else bool(is_active)
    if target.role == "admin" and (role_val != "admin" or not active_val):
        other_admins = conn.execute(
            "SELECT COUNT(*) AS cnt FROM users "
            "WHERE role = 'admin' AND is_active = 1 AND user_id != ?;",
            (target_user_id,),
        ).fetchone()
        if int(other_admins["cnt"]) == 0:
            raise AuthorizationError(
                "Cannot deactivate or demote the last remaining active administrator."
            )
    now_iso = utc_now_iso()
    with transaction(conn):
        conn.execute(
            "UPDATE users SET role = ?, is_active = ?, updated_at = ? WHERE user_id = ?;",
            (role_val, 1 if active_val else 0, now_iso, target_user_id),
        )
        if not active_val:
            conn.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL;",
                (now_iso, target_user_id),
            )
        log_audit_event(
            conn,
            operation_type="ADMIN_USER_RBAC_UPDATED",
            entity_type="user",
            entity_id=target_user_id,
            actor_role=admin.role,
            details={"new_role": role_val, "is_active": active_val},
        )
    return get_user_by_id(conn, target_user_id)


def issue_password_reset_token(
    conn: sqlite3.Connection,
    *,
    email: str,
    ttl_minutes: int = DEFAULT_RESET_TTL_MINUTES,
) -> str | None:
    """Create a short-lived single-use password reset token if account exists and is active."""
    row = conn.execute(
        "SELECT user_id, is_active FROM users WHERE email = ?;",
        (_normalize_email(email),),
    ).fetchone()
    if not row or not bool(row["is_active"]):
        return None
    raw_token = secrets.token_urlsafe(24)
    now_dt = datetime.now(UTC)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO password_reset_tokens (
                reset_id, token_hash, user_id, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?);
            """,
            (
                f"rst-{uuid.uuid4().hex[:12]}",
                _hash_token(raw_token),
                row["user_id"],
                (now_dt + timedelta(minutes=max(1, ttl_minutes))).isoformat(),
                now_dt.isoformat(),
            ),
        )
    return raw_token


def complete_password_reset(
    conn: sqlite3.Connection,
    *,
    reset_token: str,
    new_password: str,
) -> UserAccount:
    """Verify single-use reset token, update password hash, and revoke prior sessions."""
    if not reset_token or not isinstance(reset_token, str):
        raise AuthorizationError("Valid reset token required.")
    token_hash = _hash_token(reset_token.strip())
    pw_hash = hash_password(new_password)
    now_iso = utc_now_iso()
    with transaction(conn):
        cur = conn.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?;
            """,
            (now_iso, token_hash, now_iso),
        )
        if cur.rowcount != 1:
            raise AuthorizationError("Invalid, expired, or already used password reset token.")
        row = conn.execute(
            "SELECT user_id, reset_id FROM password_reset_tokens WHERE token_hash = ?;",
            (token_hash,),
        ).fetchone()
        if not row:
            raise AuthorizationError("Password reset record not found.")
        user_id = row["user_id"]
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?;",
            (pw_hash, now_iso, user_id),
        )
        conn.execute(
            "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL;",
            (now_iso, user_id),
        )
        log_audit_event(
            conn,
            operation_type="USER_PASSWORD_RESET",
            entity_type="user",
            entity_id=user_id,
            actor_role="self_service",
            details={"reset_id": row["reset_id"]},
        )
    return get_user_by_id(conn, user_id)


def list_users_admin(
    conn: sqlite3.Connection, admin_session_token: str | None
) -> list[UserAccount]:
    """List registered user accounts (admin only)."""
    require_role(conn, admin_session_token, {"admin"})
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC;").fetchall()
    return [_row_to_user(row) for row in rows]
