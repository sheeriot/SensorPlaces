from django.urls import path
from .views import dev_views

app_name = 'sensors_dev'

urlpatterns = [
    path('siteplan-test/<slug:place_slug>/', dev_views.siteplan_test_page, name='siteplan_test_page'),
]
