"""Authenticated M4 authorization trust registry using pinned Ed25519 public keys."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from voxneuro.config import PROJECT_ROOT

PINNED_TRUST_ANCHORS_PATH = PROJECT_ROOT / "configs" / "m4_trust_anchors.yaml"
DEFAULT_AUTHORITY_KEY_ID = "voxneuro-m4-authority-ed25519-v1"

# Pinned authority verification public keys (compressed 32-byte Ed25519 points, hex).
# Corresponding private signing keys must NEVER be committed to source control or bundles.
_PINNED_ED25519_PUBLIC_KEYS: dict[str, str] = {
    "voxneuro-m4-authority-ed25519-v1": (
        "f0161e1dcd64c2b464d5c1344de1554886780a1fbd3c6efeecff2046aaed44db"
    )
}

VALID_REVIEWER_ATTESTATION_ROLES = frozenset(
    {
        "lead_validation_auditor",
        "cohort_independence_reviewer",
        "governance_approver",
    }
)
FORBIDDEN_EMBEDDED_KEY_FIELDS = frozenset(
    {
        "public_key",
        "public_key_hex",
        "verification_key",
        "trust_anchor",
        "pinned_public_keys",
        "trusted_keys",
    }
)

# ---------------------------------------------------------------------------
# Pure-Python RFC 8032 Ed25519 Digital Signature Implementation
# ---------------------------------------------------------------------------

_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, -1, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)

_GY = (4 * pow(5, -1, _Q)) % _Q
_GX = None


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, -1, _Q)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_GX = _xrecover(_GY)
_G = (_GX, _GY, 1, (_GX * _GY) % _Q)
_IDENTITY = (0, 1, 1, 0)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _point_add(
    p1: tuple[int, int, int, int], p2: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % _Q
    b = ((y1 + x1) * (y2 + x2)) % _Q
    c = (2 * _D * t1 * t2) % _Q
    d = (2 * z1 * z2) % _Q
    e = (b - a) % _Q
    f = (d - c) % _Q
    g = (d + c) % _Q
    h = (b + a) % _Q
    return (
        (e * f) % _Q,
        (g * h) % _Q,
        (f * g) % _Q,
        (e * h) % _Q,
    )


def _scalar_mult(s: int, p: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    acc = _IDENTITY
    addend = p
    k = s
    while k > 0:
        if k & 1:
            acc = _point_add(acc, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return acc


def _encode_point(p: tuple[int, int, int, int]) -> bytes:
    x, y, z, _ = p
    zi = pow(z, -1, _Q)
    xp = (x * zi) % _Q
    yp = (y * zi) % _Q
    out = bytearray(yp.to_bytes(32, "little"))
    if xp & 1:
        out[31] |= 0x80
    return bytes(out)


def _decode_point(raw: bytes) -> tuple[int, int, int, int]:
    if len(raw) != 32:
        raise ValueError("Ed25519 encoded point must be 32 bytes.")
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    if y >= _Q:
        raise ValueError("Non-canonical Ed25519 y-coordinate.")
    sign = (raw[31] >> 7) & 1

    yy = (y * y) % _Q
    u = (yy - 1) % _Q
    v = (_D * yy + 1) % _Q
    v3 = (v * v * v) % _Q
    v7 = (v3 * v3 * v) % _Q
    x = (u * v3 * pow((u * v7) % _Q, (_Q - 5) // 8, _Q)) % _Q

    vx2 = (v * x * x) % _Q
    if vx2 == u:
        pass
    elif vx2 == (-u) % _Q:
        x = (x * _I) % _Q
    else:
        raise ValueError("Decoded Ed25519 point does not lie on Edwards25519.")

    if x == 0 and sign == 1:
        raise ValueError("Invalid negative zero x-coordinate in Ed25519 point.")
    if (x & 1) != sign:
        x = _Q - x
    return (x, y, 1, (x * y) % _Q)


def _secret_expand(seed: bytes) -> tuple[int, bytes]:
    if len(seed) != 32:
        raise ValueError("Ed25519 private seed must be exactly 32 bytes.")
    digest = _sha512(seed)
    a_bytes = bytearray(digest[:32])
    a_bytes[0] &= 248
    a_bytes[31] &= 127
    a_bytes[31] |= 64
    a = int.from_bytes(a_bytes, "little")
    prefix = digest[32:]
    return a, prefix


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh random (32-byte seed, 32-byte compressed public key)."""
    seed = secrets.token_bytes(32)
    return seed, ed25519_public_key_from_seed(seed)


def ed25519_public_key_from_seed(seed: bytes) -> bytes:
    """Derive 32-byte Ed25519 compressed public key from a 32-byte private seed."""
    a, _ = _secret_expand(seed)
    return _encode_point(_scalar_mult(a, _G))


def ed25519_sign(seed: bytes, message: bytes) -> bytes:
    """Sign message bytes with a 32-byte Ed25519 private seed per RFC 8032."""
    a, prefix = _secret_expand(seed)
    pk = _encode_point(_scalar_mult(a, _G))
    r = int.from_bytes(_sha512(prefix + message), "little") % _L
    r_point = _encode_point(_scalar_mult(r, _G))
    h = int.from_bytes(_sha512(r_point + pk + message), "little") % _L
    s = (r + h * a) % _L
    return r_point + s.to_bytes(32, "little")


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a 64-byte RFC 8032 Ed25519 signature against a 32-byte public key."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        a_point = _decode_point(public_key)
        r_bytes = signature[:32]
        r_point = _decode_point(r_bytes)
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = int.from_bytes(_sha512(r_bytes + public_key + message), "little") % _L
    lhs = _scalar_mult(s, _G)
    rhs = _point_add(r_point, _scalar_mult(h, a_point))
    return _encode_point(lhs) == _encode_point(rhs)


# ---------------------------------------------------------------------------
# Trust Root Pinning & Authorization Schema
# ---------------------------------------------------------------------------


class AuthorizationTrustRootError(PermissionError):
    """Raised when the M4 trust root or signed authorization registry cannot be verified."""


def _is_valid_sha256_hex(value: Any) -> bool:
    s = str(value or "")
    return len(s) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in s)


def _parse_utc_timestamp(
    value: Any, *, field_name: str, date_only_end_of_day: bool = False
) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"Missing required timestamp field: {field_name}")
    # Date-only YYYY-MM-DD expiry dates remain valid through 23:59:59 UTC of that date.
    if date_only_end_of_day and len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        dt = datetime.fromisoformat(f"{raw}T23:59:59+00:00")
        return dt.astimezone(UTC)
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_pinned_trust_anchors() -> dict[str, str]:
    """Return pinned Ed25519 public verification keys cross-checked against config."""
    if not PINNED_TRUST_ANCHORS_PATH.is_file():
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: pinned trust anchor config missing."
        )
    try:
        cfg = yaml.safe_load(PINNED_TRUST_ANCHORS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: failed parsing trust anchor config: {exc}"
        ) from exc

    if not isinstance(cfg, dict) or cfg.get("schema_version") != "voxneuro.m4_trust_anchors.v1":
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: invalid trust anchor schema_version."
        )
    if cfg.get("signature_algorithm") != "Ed25519":
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: trust anchor algorithm must be Ed25519."
        )
    cfg_keys = cfg.get("pinned_public_keys")
    if not isinstance(cfg_keys, dict) or not cfg_keys:
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: pinned_public_keys empty or invalid."
        )
    if cfg_keys != _PINNED_ED25519_PUBLIC_KEYS:
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: trust anchor config disagrees with "
            "compiled pinned public key."
        )
    return dict(_PINNED_ED25519_PUBLIC_KEYS)


def get_pinned_public_key(key_id: str) -> bytes:
    """Look up a pinned Ed25519 verification key by key_id; never accept caller overrides."""
    clean_id = str(key_id or "").strip()
    if not clean_id:
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry key_id is required."
        )
    anchors = get_pinned_trust_anchors()
    pub_hex = anchors.get(clean_id)
    if not pub_hex:
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: key_id {clean_id!r} "
            "is not a pinned trust anchor."
        )
    try:
        pub_bytes = bytes.fromhex(str(pub_hex).strip())
        _decode_point(pub_bytes)
    except Exception as exc:
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: pinned key {clean_id!r} invalid: {exc}"
        ) from exc
    return pub_bytes


@dataclass(frozen=True)
class AuthorizedSourceRecord:
    """Authoritative dataset roster source record inside the signed M4 trust registry."""

    dataset_id: str
    dataset_version: str
    source_id: str
    role: str
    artifact_sha256: str
    retrieval_reference: str
    authorization_ref: str
    authorization_state: str
    permitted_tasks: tuple[str, ...]
    permitted_operations: tuple[str, ...]
    expiry_utc: str
    issuing_authority: str
    registry_version: str
    dua_document_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "permitted_tasks", tuple(str(x) for x in self.permitted_tasks))
        object.__setattr__(
            self, "permitted_operations", tuple(str(x) for x in self.permitted_operations)
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["permitted_tasks"] = list(self.permitted_tasks)
        d["permitted_operations"] = list(self.permitted_operations)
        return d


@dataclass(frozen=True)
class AuthorizedReviewerRecord:
    """Authoritative reviewer record inside the signed M4 trust registry."""

    reviewer_id: str
    role: str
    approval_status: str
    permitted_evaluation_tasks: tuple[str, ...]
    permitted_operations: tuple[str, ...]
    expiry_utc: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "permitted_evaluation_tasks",
            tuple(str(x) for x in self.permitted_evaluation_tasks),
        )
        object.__setattr__(
            self, "permitted_operations", tuple(str(x) for x in self.permitted_operations)
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["permitted_evaluation_tasks"] = list(self.permitted_evaluation_tasks)
        d["permitted_operations"] = list(self.permitted_operations)
        return d


@dataclass(frozen=True)
class AuthorizationTrustRegistry:
    """Payload of the signed M4 authorization trust registry."""

    registry_id: str
    registry_version: str
    issuing_authority: str
    created_utc: str
    expires_utc: str
    review_date_utc: str
    key_id: str
    authorized_sources: tuple[AuthorizedSourceRecord, ...]
    authorized_reviewers: tuple[AuthorizedReviewerRecord, ...]
    signature_algorithm: str = "Ed25519"
    registry_fingerprint: str = ""

    def __post_init__(self) -> None:
        sources = tuple(
            s if isinstance(s, AuthorizedSourceRecord) else AuthorizedSourceRecord(**s)
            for s in self.authorized_sources
        )
        reviewers = tuple(
            r if isinstance(r, AuthorizedReviewerRecord) else AuthorizedReviewerRecord(**r)
            for r in self.authorized_reviewers
        )
        object.__setattr__(self, "authorized_sources", sources)
        object.__setattr__(self, "authorized_reviewers", reviewers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "issuing_authority": self.issuing_authority,
            "created_utc": self.created_utc,
            "expires_utc": self.expires_utc,
            "review_date_utc": self.review_date_utc,
            "key_id": self.key_id,
            "signature_algorithm": self.signature_algorithm,
            "authorized_sources": [s.to_dict() for s in self.authorized_sources],
            "authorized_reviewers": [r.to_dict() for r in self.authorized_reviewers],
            "registry_fingerprint": self.registry_fingerprint,
        }

    def canonical_unsigned_bytes(self) -> bytes:
        d = self.to_dict()
        d["registry_fingerprint"] = ""
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return canonical.encode("utf-8")

    def compute_fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_unsigned_bytes()).hexdigest()

    def signing_message(self) -> bytes:
        fp = self.compute_fingerprint()
        return f"VOXNEURO-M4-AUTHORIZATION-REGISTRY-V1\x00{fp}".encode("ascii")


@dataclass(frozen=True)
class SignedAuthorizationRegistry:
    """Asymmetrically signed M4 authorization registry envelope."""

    registry: AuthorizationTrustRegistry
    signature_hex: str
    key_id: str
    signature_algorithm: str = "Ed25519"

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry": self.registry.to_dict(),
            "signature_hex": self.signature_hex,
            "key_id": self.key_id,
            "signature_algorithm": self.signature_algorithm,
        }


def sign_authorization_registry(
    registry: AuthorizationTrustRegistry,
    private_seed: bytes,
) -> SignedAuthorizationRegistry:
    """Create an offline Ed25519 signature over the canonical registry fingerprint."""
    fp = registry.compute_fingerprint()
    finalized = AuthorizationTrustRegistry(**{**registry.to_dict(), "registry_fingerprint": fp})
    sig = ed25519_sign(private_seed, finalized.signing_message())
    return SignedAuthorizationRegistry(
        registry=finalized,
        signature_hex=sig.hex(),
        key_id=finalized.key_id,
        signature_algorithm="Ed25519",
    )


def _check_for_embedded_keys(raw_obj: Any, location: str) -> str | None:
    if isinstance(raw_obj, dict):
        overlap = FORBIDDEN_EMBEDDED_KEY_FIELDS.intersection(raw_obj.keys())
        if overlap:
            return (
                f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: untrusted {location} contains "
                f"self-declared verification key field(s) {sorted(overlap)}."
            )
    return None


def load_signed_authorization_registry(
    registry_path: Path | str,
    signature_path: Path | str,
) -> SignedAuthorizationRegistry:
    """Load an authorization registry JSON and detached signature file."""
    reg_p = Path(registry_path)
    sig_p = Path(signature_path)
    if not reg_p.is_file():
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry file not found: {reg_p}"
        )
    if not sig_p.is_file():
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry signature file not found: {sig_p}"
        )

    try:
        raw_reg = json.loads(reg_p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: invalid registry JSON: {exc}"
        ) from exc

    if not isinstance(raw_reg, dict):
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry payload must be a JSON object."
        )
    embedded_err = _check_for_embedded_keys(raw_reg, "registry")
    if embedded_err:
        raise AuthorizationTrustRootError(embedded_err)

    raw_sig_bytes = sig_p.read_bytes()
    sig_hex = ""
    sig_alg = "Ed25519"
    sig_key_id = str(raw_reg.get("key_id", "")).strip()

    try:
        sig_text = raw_sig_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        sig_text = ""

    if sig_text.startswith("{"):
        try:
            sig_obj = json.loads(sig_text)
        except Exception as exc:
            raise AuthorizationTrustRootError(
                f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: invalid signature JSON: {exc}"
            ) from exc
        if not isinstance(sig_obj, dict):
            raise AuthorizationTrustRootError(
                "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: signature JSON must be an object."
            )
        sig_embedded_err = _check_for_embedded_keys(sig_obj, "signature")
        if sig_embedded_err:
            raise AuthorizationTrustRootError(sig_embedded_err)
        sig_hex = str(sig_obj.get("signature_hex", "")).strip()
        sig_alg = str(sig_obj.get("signature_algorithm", "Ed25519")).strip()
        if sig_obj.get("key_id"):
            if sig_key_id and str(sig_obj["key_id"]).strip() != sig_key_id:
                raise AuthorizationTrustRootError(
                    "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: signature key_id disagrees "
                    "with registry key_id."
                )
            sig_key_id = str(sig_obj["key_id"]).strip()
        if sig_obj.get("registry_fingerprint"):
            reg_fp = str(raw_reg.get("registry_fingerprint", "")).strip()
            if reg_fp and str(sig_obj["registry_fingerprint"]).strip() != reg_fp:
                raise AuthorizationTrustRootError(
                    "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: "
                    "signature registry_fingerprint mismatch."
                )
    elif len(raw_sig_bytes) == 64:
        sig_hex = raw_sig_bytes.hex()
    elif len(sig_text) == 128 and all(c in "0123456789abcdefABCDEF" for c in sig_text):
        sig_hex = sig_text
    else:
        raise AuthorizationTrustRootError(
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: malformed signature file encoding."
        )

    try:
        reg_obj = AuthorizationTrustRegistry(**raw_reg)
    except TypeError as exc:
        raise AuthorizationTrustRootError(
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: malformed registry schema: {exc}"
        ) from exc

    return SignedAuthorizationRegistry(
        registry=reg_obj,
        signature_hex=sig_hex,
        key_id=sig_key_id,
        signature_algorithm=sig_alg,
    )


def verify_signed_authorization_registry(
    signed_registry: SignedAuthorizationRegistry | dict[str, Any] | None,
    *,
    now_utc: datetime | None = None,
) -> tuple[bool, str, AuthorizationTrustRegistry | None]:
    """Verify the Ed25519 signature and validity of the M4 authorization registry.

    Verification ALWAYS uses the pinned trust anchor key looked up by ``key_id``;
    no dynamic caller-supplied public keys are permitted.
    """
    if signed_registry is None:
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: signed authorization registry is required.",
            None,
        )

    try:
        if isinstance(signed_registry, SignedAuthorizationRegistry):
            env = signed_registry
        elif isinstance(signed_registry, dict):
            embedded_err = _check_for_embedded_keys(signed_registry, "registry envelope")
            if embedded_err:
                return False, embedded_err, None
            reg_raw = signed_registry.get("registry")
            if not isinstance(reg_raw, dict):
                return (
                    False,
                    "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: missing registry payload object.",
                    None,
                )
            embedded_reg_err = _check_for_embedded_keys(reg_raw, "registry")
            if embedded_reg_err:
                return False, embedded_reg_err, None
            reg_obj = AuthorizationTrustRegistry(**reg_raw)
            env = SignedAuthorizationRegistry(
                registry=reg_obj,
                signature_hex=str(signed_registry.get("signature_hex", "")).strip(),
                key_id=str(signed_registry.get("key_id") or reg_obj.key_id).strip(),
                signature_algorithm=str(signed_registry.get("signature_algorithm", "")).strip(),
            )
        else:
            return (
                False,
                "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: unsupported registry object type.",
                None,
            )
    except Exception as exc:
        return False, f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: malformed registry ({exc}).", None

    reg = env.registry
    for req_field, val in (
        ("registry_id", reg.registry_id),
        ("registry_version", reg.registry_version),
        ("issuing_authority", reg.issuing_authority),
        ("key_id", reg.key_id),
    ):
        if not str(val or "").strip():
            return (
                False,
                f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: missing required field {req_field!r}.",
                None,
            )

    if env.signature_algorithm != "Ed25519" or reg.signature_algorithm != "Ed25519":
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: signature_algorithm must be 'Ed25519'.",
            None,
        )

    if env.key_id and env.key_id != reg.key_id:
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: envelope key_id mismatches registry key_id.",
            None,
        )

    if not env.signature_hex:
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry signature is missing (unsigned).",
            None,
        )

    try:
        sig_bytes = bytes.fromhex(env.signature_hex)
    except ValueError:
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry signature is not valid hex.",
            None,
        )
    if len(sig_bytes) != 64:
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: Ed25519 signature must be 64 bytes.",
            None,
        )

    computed_fp = reg.compute_fingerprint()
    if (
        not _is_valid_sha256_hex(reg.registry_fingerprint)
        or reg.registry_fingerprint != computed_fp
    ):
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry_fingerprint mismatch.",
            None,
        )

    try:
        pinned_pub = get_pinned_public_key(reg.key_id)
    except AuthorizationTrustRootError as exc:
        return False, str(exc), None

    if not ed25519_verify(pinned_pub, reg.signing_message(), sig_bytes):
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: Ed25519 cryptographic signature invalid.",
            None,
        )

    now = now_utc or datetime.now(UTC)
    try:
        created_dt = _parse_utc_timestamp(reg.created_utc, field_name="created_utc")
        expires_dt = _parse_utc_timestamp(
            reg.expires_utc, field_name="expires_utc", date_only_end_of_day=True
        )
        _parse_utc_timestamp(
            reg.review_date_utc, field_name="review_date_utc", date_only_end_of_day=True
        )
    except ValueError as exc:
        return (
            False,
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: invalid registry timestamp ({exc}).",
            None,
        )

    if created_dt > expires_dt:
        return (
            False,
            "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry created_utc exceeds expires_utc.",
            None,
        )
    if expires_dt <= now:
        return (
            False,
            f"AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: registry expired at {reg.expires_utc}.",
            None,
        )

    return True, "Signed M4 authorization trust registry verified.", reg


def load_and_verify_authorization_registry(
    registry_path: Path | str,
    signature_path: Path | str,
    *,
    now_utc: datetime | None = None,
) -> tuple[AuthorizationTrustRegistry, SignedAuthorizationRegistry]:
    """Load and verify a signed authorization registry, failing closed on error."""
    signed_env = load_signed_authorization_registry(registry_path, signature_path)
    ok, reason, reg = verify_signed_authorization_registry(signed_env, now_utc=now_utc)
    if not ok or reg is None:
        raise AuthorizationTrustRootError(reason)
    return reg, signed_env


def authorize_reviewer_from_registry(
    registry: AuthorizationTrustRegistry,
    reviewer_id: str,
    *,
    requested_task: str,
    requested_operation: str,
    allowed_roles: frozenset[str] = VALID_REVIEWER_ATTESTATION_ROLES,
    now_utc: datetime | None = None,
) -> tuple[bool, str, AuthorizedReviewerRecord | None]:
    """Verify reviewer identity, role, status, scope, and expiry against signed registry."""
    clean_id = str(reviewer_id or "").strip()
    if not clean_id:
        return False, "INDEPENDENCE_NOT_VERIFIED: reviewer_id is missing.", None

    matches = [r for r in registry.authorized_reviewers if r.reviewer_id == clean_id]
    if not matches:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} not in signed trust registry.",
            None,
        )
    if len(matches) > 1:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: duplicate reviewer entries for {clean_id!r}.",
            None,
        )
    rec = matches[0]
    if rec.approval_status != "APPROVED":
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} approval_status is "
            f"{rec.approval_status!r} (must be 'APPROVED').",
            None,
        )
    if rec.role not in allowed_roles:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} role {rec.role!r} is "
            f"insufficient (requires one of {sorted(allowed_roles)}).",
            None,
        )
    if requested_task not in rec.permitted_evaluation_tasks:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} not permitted for task "
            f"{requested_task!r}.",
            None,
        )
    if requested_operation not in rec.permitted_operations:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} not permitted for operation "
            f"{requested_operation!r}.",
            None,
        )

    now = now_utc or datetime.now(UTC)
    try:
        exp_dt = _parse_utc_timestamp(
            rec.expiry_utc, field_name="reviewer.expiry_utc", date_only_end_of_day=True
        )
    except ValueError as exc:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} has invalid expiry_utc ({exc}).",
            None,
        )
    if exp_dt <= now:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: reviewer {clean_id!r} authorization expired on "
            f"{rec.expiry_utc}.",
            None,
        )

    return True, "Reviewer authorization verified.", rec


def authorize_source_from_registry(
    registry: AuthorizationTrustRegistry,
    *,
    role: str,
    dataset_id: str,
    dataset_version: str,
    source_id: str,
    authorization_ref: str,
    actual_artifact_sha256: str,
    requested_task: str,
    requested_operation: str,
    now_utc: datetime | None = None,
) -> tuple[bool, str, AuthorizedSourceRecord | None]:
    """Verify source authorization record and bind it to exact dataset version & artifact hash."""
    clean_src = str(source_id or "").strip()
    clean_ref = str(authorization_ref or "").strip()
    if not clean_src or clean_src.casefold() in {"unknown", "pending", "none", "tbd"}:
        return False, f"INDEPENDENCE_NOT_VERIFIED: missing or invalid {role}_roster_source.", None
    if not clean_ref or clean_ref.casefold() in {"unknown", "pending", "none", "tbd"}:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: missing or invalid {role}_authorization_ref.",
            None,
        )
    if not _is_valid_sha256_hex(actual_artifact_sha256):
        return False, f"INDEPENDENCE_NOT_VERIFIED: invalid {role} roster file SHA-256.", None

    matches = [
        s
        for s in registry.authorized_sources
        if s.role == role
        and s.source_id == clean_src
        and s.dataset_id == dataset_id
        and s.dataset_version == dataset_version
    ]
    if not matches:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source {clean_src!r} for "
            f"{dataset_id!r} version {dataset_version!r} not in signed trust registry.",
            None,
        )
    if len(matches) > 1:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: ambiguous source entries for {clean_src!r}.",
            None,
        )
    rec = matches[0]
    if rec.issuing_authority != registry.issuing_authority:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source issuing_authority mismatch with registry.",
            None,
        )
    if rec.registry_version != registry.registry_version:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source registry_version mismatch with registry.",
            None,
        )
    if rec.authorization_state not in {"APPROVED", "ACTIVE"}:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source authorization_state is "
            f"{rec.authorization_state!r} (not authorized).",
            None,
        )
    if rec.authorization_ref != clean_ref:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} authorization_ref {clean_ref!r} does not "
            f"match signed registry record {rec.authorization_ref!r}.",
            None,
        )
    if requested_task not in rec.permitted_tasks:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source does not permit task {requested_task!r}.",
            None,
        )
    if requested_operation not in rec.permitted_operations:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source does not permit operation "
            f"{requested_operation!r}.",
            None,
        )
    if not _is_valid_sha256_hex(rec.artifact_sha256):
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source record missing valid artifact_sha256.",
            None,
        )
    if rec.artifact_sha256.casefold() != actual_artifact_sha256.casefold():
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} roster file SHA-256 mismatches signed "
            f"registry artifact_sha256 ({actual_artifact_sha256} != {rec.artifact_sha256}).",
            None,
        )
    if not str(rec.retrieval_reference or "").strip():
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source record missing retrieval_reference.",
            None,
        )

    now = now_utc or datetime.now(UTC)
    try:
        exp_dt = _parse_utc_timestamp(
            rec.expiry_utc, field_name="source.expiry_utc", date_only_end_of_day=True
        )
    except ValueError as exc:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source has invalid expiry_utc ({exc}).",
            None,
        )
    if exp_dt <= now:
        return (
            False,
            f"INDEPENDENCE_NOT_VERIFIED: {role} source authorization expired on {rec.expiry_utc}.",
            None,
        )

    return True, "Source authorization verified.", rec
