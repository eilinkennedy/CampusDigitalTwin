from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),                 # Landing page
    path('visitor/', views.visitor, name='visitor'),   # Visitor navigation page
    path('dashboard-ui/', views.admin_dashboard_stitch, name='dashboard_ui'),  # Admin-only dashboard
]