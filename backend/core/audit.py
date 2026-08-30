"""Audit logging helper (POPIA-aligned)."""
from .models import AuditLogEntry


def log_action(user, action, target_description):
    """Create an AuditLogEntry. Never raises to the caller."""
    try:
        AuditLogEntry.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action=action,
            target_description=(target_description or '')[:500],
        )
    except Exception:
        pass
