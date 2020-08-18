from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('courses/', views.courses, name='courses'),
    path('instructors/', views.InstructorListView.as_view(), name='instructors'),
]
