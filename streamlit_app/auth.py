"""Authentication and per-module permissions (checklist T2).

Decision D3: named users with hashed passwords, no external identity provider,
so it behaves the same locally and deployed. Named users matter because every
write records `changed_by`; a shared password would make the audit trail and
the accountability the brief asks for both meaningless.

Decision D2: two roles. `marketing` writes, `viewer` reads. Permissions live in
a per-module table rather than in `if role == ...` scattered through the pages,
so adding the branch or agency seat later is a row here, not a refactor.

Deviation from D3, recorded here rather than buried: the checklist said
streamlit-authenticator. This is hand-rolled on stdlib PBKDF2-HMAC-SHA256
instead, because the valuable half of D3 was named users plus a permission
table, and adding a dependency is the most common way a Streamlit Cloud build
breaks. Passwords are salted and hashed, never stored in the clear. Production
target is still GSB SSO, phase 2 in SYSTEM_SPEC.md.
"""
import hashlib
import hmac
import os
import secrets
from pathlib import Path

import streamlit as st
import yaml

_ITER = 240_000          # PBKDF2-HMAC-SHA256 rounds


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _ITER)
    return f"pbkdf2${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        scheme, iters, salt_hex, dk_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex),
                                 int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False

USERS_FILE = Path(__file__).resolve().parent / "users.yaml"

# module -> roles that may READ it / roles that may WRITE in it.
# Every page asks this table; no page decides for itself.
PERMISSIONS = {
    "overview":        {"read": {"marketing", "viewer"}, "write": set()},
    "engagement":      {"read": {"marketing", "viewer"}, "write": set()},
    "lead_quality":    {"read": {"marketing", "viewer"}, "write": set()},
    "loan_funnel":     {"read": {"marketing", "viewer"}, "write": set()},
    "business":        {"read": {"marketing", "viewer"}, "write": set()},
    "customers":       {"read": {"marketing", "viewer"}, "write": set()},
    "customer_detail": {"read": {"marketing", "viewer"}, "write": {"marketing"}},
    "dictionary":      {"read": {"marketing", "viewer"}, "write": set()},
    "worklist":        {"read": {"marketing"},           "write": {"marketing"}},
    "data_health":     {"read": {"marketing"},           "write": {"marketing"}},
    "campaign_setup":  {"read": {"marketing"},           "write": {"marketing"}},
    "leads_import":    {"read": {"marketing"},           "write": {"marketing"}},
}

ROLE_LABEL = {"marketing": "Marketing", "viewer": "Campaign owner"}
ROLE_HELP = {
    "marketing": "Reads everything unmasked, and holds the only human write path.",
    "viewer": "Reads every KPI page. Writes nothing, ever. Contact fields masked.",
}


def _default_users():
    """Seed file. Passwords are the demo ones printed on the login screen."""
    return {
        "users": {
            "marketing.gsb": {"name": "Marketing (GSB)", "role": "marketing",
                              "password": hash_password("dco-marketing")},
            "owner.gsb": {"name": "Campaign owner (GSB)", "role": "viewer",
                          "password": hash_password("dco-owner")},
        }
    }


def load_users() -> dict:
    if not USERS_FILE.exists():
        USERS_FILE.write_text(yaml.safe_dump(_default_users(), allow_unicode=True))
    return yaml.safe_load(USERS_FILE.read_text())["users"]


def save_users(users: dict) -> None:
    USERS_FILE.write_text(yaml.safe_dump({"users": users}, allow_unicode=True))


# ---------------- session ----------------
def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def role() -> str:
    u = current_user()
    return u["role"] if u else "viewer"


def username() -> str:
    u = current_user()
    return u["username"] if u else "anonymous"


def is_authenticated() -> bool:
    return current_user() is not None


def sign_in(user: str, password: str) -> tuple[bool, str]:
    users = load_users()
    rec = users.get(user)
    # Hash even when the user does not exist, so a missing username and a wrong
    # password take the same time and the form cannot be used to enumerate.
    stored = rec.get("password") if rec else hash_password(secrets.token_hex(8))
    if not rec or not verify_password(password, stored):
        # One message for both cases, so the form cannot be used to discover
        # which usernames exist.
        return False, "Username or password is incorrect."
    st.session_state.auth_user = {"username": user, "name": rec["name"],
                                  "role": rec["role"]}
    return True, ""


def sign_out() -> None:
    st.session_state.pop("auth_user", None)
    st.session_state.pop("_last_role", None)


# ---------------- permissions ----------------
def can_read(module: str) -> bool:
    return role() in PERMISSIONS.get(module, {}).get("read", set())


def can_write(module: str | None = None) -> bool:
    if module is None:
        return role() == "marketing"
    return role() in PERMISSIONS.get(module, {}).get("write", set())


def visible_modules() -> set:
    return {m for m in PERMISSIONS if can_read(m)}


def guard(module: str) -> None:
    """Stop a page the current role may not read. Absence in the nav is the
    first line; this is the second, for anyone typing the URL directly."""
    if not can_read(module):
        st.error(f":material/lock: **{ROLE_LABEL.get(role(), role())}** has no access to "
                 f"this page. Your seat reads every KPI page, but does not write.")
        st.stop()


def add_user(user: str, name: str, pw: str, user_role: str) -> tuple[bool, str]:
    """Used by the admin page. Marketing can onboard a campaign owner without
    a developer, which is use case A7."""
    users = load_users()
    if user in users:
        return False, f"User {user} already exists."
    if user_role not in ROLE_LABEL:
        return False, f"Unknown role {user_role}."
    if len(pw) < 8:
        return False, "Password must be at least 8 characters."
    users[user] = {"name": name, "role": user_role, "password": hash_password(pw)}
    save_users(users)
    return True, f"Added {user} as {ROLE_LABEL[user_role]}."
