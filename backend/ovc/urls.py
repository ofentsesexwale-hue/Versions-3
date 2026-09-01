"""URL routing - everything lives under /api/ (Kubernetes ingress requirement)."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core import views
from core import print_views
from core import form_views
from core import scan_views

router = DefaultRouter()
router.register(r'households', views.HouseholdViewSet, basename='household')
router.register(r'caregivers', views.CaregiverViewSet, basename='caregiver')
router.register(r'members', views.HouseholdMemberViewSet, basename='member')
router.register(r'documents', views.SupportingDocumentViewSet, basename='document')
router.register(r'checklist', views.ChecklistViewSet, basename='checklist')
router.register(r'process-notes', views.ProcessNoteViewSet, basename='processnote')
router.register(r'assessments', views.AssessmentViewSet, basename='assessment')
router.register(r'services', views.ServiceDeliveryViewSet, basename='service')
router.register(r'audit', views.AuditLogViewSet, basename='audit')
router.register(r'consents', views.ConsentRecordViewSet, basename='consent')
router.register(r'care-plans', views.FamilyCarePlanViewSet, basename='careplan')
router.register(r'protection-incidents', views.ProtectionIncidentViewSet, basename='protection')
router.register(r'cow1', views.Cow1PlanViewSet, basename='cow1')
router.register(r'evaluations', views.EvaluationViewSet, basename='evaluation')
router.register(r'group-sessions', views.GroupWorkSessionViewSet, basename='groupsession')
router.register(r'referrals', views.ReferralViewSet, basename='referral')
router.register(r'visits', views.PlannedVisitViewSet, basename='visit')
router.register(r'partners', views.PartnerAgencyViewSet, basename='partner')
router.register(r'staff', views.StaffViewSet, basename='staff')
router.register(r'scan-intake', scan_views.ScanIntakeViewSet, basename='scan-intake')

api_patterns = [
    path('auth/login/', views.LoginView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('auth/me/', views.MeView.as_view()),
    path('auth/change-password/', views.ChangePasswordView.as_view()),
    path('dashboard/', views.DashboardView.as_view()),
    path('choices/', views.ChoicesView.as_view()),
    path('users/', views.UsersListView.as_view()),
    path('organisation/', views.OrganisationView.as_view()),
    path('site-config/', views.SiteConfigView.as_view()),
    path('id-check/', views.IdCheckView.as_view()),
    path('work-diary/', views.WorkDiaryView.as_view()),
    path('backups/', views.BackupListView.as_view()),
    path('backups/create/', views.BackupCreateView.as_view()),
    path('backups/restore/', views.BackupRestoreView.as_view()),
    path('backups/<str:name>/download/', views.BackupDownloadView.as_view()),
    path('service-targets/', views.ServiceTargetView.as_view()),
    path('branding/', views.BrandingView.as_view()),
    path('official-forms/', form_views.OfficialFormListView.as_view()),
    path('official-forms/<str:code>/', form_views.OfficialFormDetailView.as_view()),
    path('official-forms/<str:code>/values/', form_views.OfficialFormValuesView.as_view()),
    path('official-forms/<str:code>/blank/<int:page>/', form_views.official_blank),
    path('print/official/<str:form>/', form_views.print_official),
    path('scan-intake/<int:job_id>/pages/<int:page_id>/image/', scan_views.scan_page_image),
    path('print/timeline/', print_views.print_timeline),
    path('print/service-report/', print_views.print_service_report),
    path('print/<str:form>/', print_views.print_form),
    path('', include(router.urls)),
]

urlpatterns = [
    path('api/admin/', admin.site.urls),
    path('api/', include(api_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
