"""Server-side role enforcement (Django Groups)."""
from django.conf import settings
from rest_framework import permissions

ROLE_DATA_CAPTURER = settings.ROLE_DATA_CAPTURER
ROLE_CASE_WORKER = settings.ROLE_CASE_WORKER
ROLE_SUPERVISOR = settings.ROLE_SUPERVISOR
ROLE_ADMIN = settings.ROLE_ADMIN


def user_role(user):
    """Return the highest-priority role for a user, or None."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    groups = set(user.groups.values_list('name', flat=True))
    for role in (ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_CASE_WORKER, ROLE_DATA_CAPTURER):
        if role in groups:
            return role
    return None


def can_view_all_households(user):
    return user_role(user) in (ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_DATA_CAPTURER)


def can_edit_records(user):
    """Who may create/edit Household/Caregiver/Member/Documents."""
    return user_role(user) in (ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_CASE_WORKER, ROLE_DATA_CAPTURER)


def can_signoff_checklist(user):
    return user_role(user) in (ROLE_ADMIN, ROLE_SUPERVISOR)


def can_view_audit(user):
    return user_role(user) == ROLE_ADMIN


class IsStaffRole(permissions.BasePermission):
    """Any authenticated user with a recognised role."""
    message = 'You do not have a role assigned. Contact an administrator.'

    def has_permission(self, request, view):
        return user_role(request.user) is not None


class IsAdminRole(permissions.BasePermission):
    message = 'Only administrators may perform this action.'

    def has_permission(self, request, view):
        return user_role(request.user) == ROLE_ADMIN
