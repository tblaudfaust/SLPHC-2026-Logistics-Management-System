from app.models.user import User


def effective_permission_codes(user: User) -> set[str]:
    """Role-derived permissions with that user's individual GRANT/REVOKE
    overrides applied on top. The single source of truth for "what can this
    user actually do" — used by the require_permission dependency, JWT claim
    generation at login, /auth/me, and notification recipient resolution, so
    an override behaves consistently everywhere rather than only in the spot
    it was first added for."""
    codes = {p.code for role in user.roles for p in role.permissions}
    for override in user.permission_overrides:
        if override.effect == "GRANT":
            codes.add(override.permission.code)
        elif override.effect == "REVOKE":
            codes.discard(override.permission.code)
    return codes
