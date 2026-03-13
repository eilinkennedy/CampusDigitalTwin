from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('visitor/', views.visitor, name='visitor'),
    path('dashboard-ui/', views.admin_dashboard_stitch, name='dashboard_ui'),
    path('admin-login/', views.AdminLoginView.as_view(), name='admin_login'),
    path('admin-logout/', views.admin_logout, name='admin_logout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-building-occupancy/', views.admin_occupancy, name='admin_occupancy'),
    path('admin-energy-consumption/', views.admin_energy, name='admin_energy'),
    path('admin-manage-data/', views.admin_manage_data, name='admin_manage_data'),
    path('admin-manage-data/<str:model_key>/', views.admin_model_list, name='admin_model_list'),
    path('admin-manage-data/<str:model_key>/add/', views.admin_model_create, name='admin_model_create'),
    path('admin-manage-data/<str:model_key>/<int:pk>/edit/', views.admin_model_edit, name='admin_model_edit'),
    path('admin-manage-data/<str:model_key>/<int:pk>/delete/', views.admin_model_delete, name='admin_model_delete'),
    path("navigation/", views.navigation, name="navigation"),
]