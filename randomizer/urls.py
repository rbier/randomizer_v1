from django.contrib.auth import views as auth_views
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from datastore import views as datastore_views
from permissions import views as permissions_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True)
         , name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='logout.html'), name='logout'),

    path('signup/', permissions_views.SignupView.as_view(), name='signup'),
    path('signup-thanks/', TemplateView.as_view(template_name='signup-thanks.html'), name='signup_thanks'),
    path('study-access/', login_required(permissions_views.StudyAccessView.as_view()), name='study_access'),
    path('study-access-thanks/', login_required(TemplateView.as_view(template_name='study-access-thanks.html')),
         name='study_access_thanks'),
    path('approve/', staff_member_required(permissions_views.AccessApproval.as_view()), name='access_approval'),

    path('', login_required(datastore_views.MyTablesView.as_view()), name='table_list'),
    path('import/', staff_member_required(datastore_views.UploadTableView.as_view()), name='table_import'),

    path('<int:pk>-<slug:table_slug>/',
         login_required(datastore_views.TableDetailView.as_view()),
         name=datastore_views.TableDetailView.view_name()),
    path('<int:pk>-<slug:table_slug>/columns/',
         staff_member_required(datastore_views.TableColumnsView.as_view()),
         name=datastore_views.TableColumnsView.view_name()),
    path('<int:pk>-<slug:table_slug>/add-site/',
         staff_member_required(datastore_views.TableAppendView.as_view()),
         name=datastore_views.TableAppendView.view_name()),
]
