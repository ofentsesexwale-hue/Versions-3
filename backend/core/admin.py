from django.contrib import admin

from .models import (
    AuditLogEntry,
    Caregiver,
    CaseFileChecklistItem,
    Household,
    HouseholdMember,
    SupportingDocument,
)

admin.site.register(Household)
admin.site.register(Caregiver)
admin.site.register(HouseholdMember)
admin.site.register(SupportingDocument)
admin.site.register(CaseFileChecklistItem)
admin.site.register(AuditLogEntry)
