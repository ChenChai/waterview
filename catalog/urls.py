from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('courses/', views.CourseListView.as_view(), name='courses'),
    path('instructors/', views.InstructorListView.as_view(), name='instructors'),
]
