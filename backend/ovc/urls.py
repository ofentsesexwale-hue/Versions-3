"""URL routing - everything lives under /api/ (Kubernetes ingress requirement)."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core import views
from core import print_views

router = DefaultRouter()
router.register(r'households', views.HouseholdViewSet, basename='household')
router.register(r'caregivers', views.CaregiverViewSet, basename='caregiver')
router.register(r'members', views.HouseholdMemberViewSet, basename='member')
router.register(r'documents', views.SupportingDocumentViewSet, basename='document')
router.register(r'checklist', views.ChecklistViewSet, basename='checklist')
router.register(r'process-notes', views.ProcessNoteViewSet, basename='processnote')
router.register(r'assessments', views.AssessmentViewSet, basename='assessment')
router.register(r'audit', views.AuditLogViewSet, basename='audit')

api_patterns = [
    path('auth/login/', views.LoginView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('auth/me/', views.MeView.as_view()),
    path('dashboard/', views.DashboardView.as_view()),
    path('choices/', views.ChoicesView.as_view()),
    path('users/', views.UsersListView.as_view()),
    path('print/<str:form>/', print_views.print_form),
    path('', include(router.urls)),
]

urlpatterns = [
    path('api/admin/', admin.site.urls),
    path('api/', include(api_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
