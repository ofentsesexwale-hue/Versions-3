"""Server-side role enforcement (Django Groups)."""
from django.conf import settings
from django.db.models import Q
from rest_framework import permissions

ROLE_DATA_CAPTURER = settings.ROLE_DATA_CAPTURER
ROLE_CASE_WORKER = settings.ROLE_CASE_WORKER
ROLE_CYCW = settings.ROLE_CYCW
ROLE_AUXILIARY = settings.ROLE_AUXILIARY
ROLE_CAREGIVER = settings.ROLE_CAREGIVER
ROLE_CAREGIVER_EPWP = settings.ROLE_CAREGIVER_EPWP
ROLE_EPWP_COORDINATOR = settings.ROLE_EPWP_COORDINATOR
ROLE_POVERTY_ALLEVATOR_COORDINATOR = settings.ROLE_POVERTY_ALLEVATOR_COORDINATOR
ROLE_SUPERVISOR = settings.ROLE_SUPERVISOR
ROLE_ADMIN = settings.ROLE_ADMIN

FIELD_WORKER_ROLES = frozenset({
    ROLE_CASE_WORKER, ROLE_CYCW, ROLE_AUXILIARY, ROLE_CAREGIVER_EPWP,
    ROLE_EPWP_COORDINATOR, ROLE_POVERTY_ALLEVATOR_COORDINATOR,
})

ROLE_PRIORITY = (
    ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_EPWP_COORDINATOR,
    ROLE_POVERTY_ALLEVATOR_COORDINATOR, ROLE_CYCW, ROLE_CASE_WORKER,
    ROLE_AUXILIARY, ROLE_CAREGIVER_EPWP, ROLE_DATA_CAPTURER, ROLE_CAREGIVER,
)

ROLE_PERMISSION_TEXT = {
    ROLE_ADMIN: 'Full live office: all files, staff logins, organisation, and audit.',
    ROLE_SUPERVISOR: 'All files, quality sign-off, and caseload reassignment. Cannot add staff.',
    ROLE_EPWP_COORDINATOR: 'All files for E.P.W.P coordination. Capture and assign caseload. No staff logins or sign-off.',
    ROLE_POVERTY_ALLEVATOR_COORDINATOR: 'All files for poverty-alleviation coordination. Capture and assign caseload. No staff logins or sign-off.',
    ROLE_CYCW: 'Own caseload: open files, capture caregivers and children, visits, and services.',
    ROLE_CASE_WORKER: 'Own caseload (training title). Same field permissions as a CYCW.',
    ROLE_AUXILIARY: 'Own caseload: support visits, services, and file capture. No sign-off or staff.',
    ROLE_CAREGIVER_EPWP: 'Own caseload as an E.P.W.P caregiver: visits, services, and file capture. No sign-off or staff.',
    ROLE_DATA_CAPTURER: 'All files for capturing. No sign-off, reassignment, or staff.',
    ROLE_CAREGIVER: 'View the household file linked to this login. Cannot change office records.',
}


def is_training_user(user):
    """Demo / training logins used for staff practice, not the live office file."""
    return bool(user and getattr(user, 'username', None) in settings.TRAINING_USERNAMES)


def system_builder_username():
    return getattr(settings, 'SYSTEM_BUILDER_USERNAME', 'OrphanCoordinator')


def is_system_builder(user):
    """Orphan Coordinator — live office administrator (cannot be demoted)."""
    name = getattr(user, 'username', None) if user else None
    return bool(name) and name.lower() == system_builder_username().lower()


def training_households_filter():
    prefix = getattr(settings, 'TRAINING_HOUSEHOLD_PREFIX', 'TEST')
    return Q(org_household_number__istartswith=prefix)


def user_role(user):
    """Return the highest-priority role for a user, or None."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    groups = set(user.groups.values_list('name', flat=True))
    for role in ROLE_PRIORITY:
        if role in groups:
            return role
    return None


def is_field_worker(user):
    return user_role(user) in FIELD_WORKER_ROLES


def can_view_all_households(user):
    return user_role(user) in (
        ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_DATA_CAPTURER,
        ROLE_EPWP_COORDINATOR, ROLE_POVERTY_ALLEVATOR_COORDINATOR,
    )


def can_edit_records(user):
    """Who may create/edit Household/Caregiver/Member/Documents."""
    return user_role(user) in (
        ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_CASE_WORKER, ROLE_CYCW,
        ROLE_AUXILIARY, ROLE_DATA_CAPTURER, ROLE_CAREGIVER_EPWP,
        ROLE_EPWP_COORDINATOR, ROLE_POVERTY_ALLEVATOR_COORDINATOR,
    )


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
