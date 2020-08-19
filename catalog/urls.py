from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('courses/', views.courses, name='courses'),
    path('courses/<slug:subject>/', views.subjectDetail, name='subjectDetail'),
    path('courses/<slug:subject>/<slug:code>/', views.courseDetail, name='courseDetail'),
    path('instructors/', views.InstructorListView.as_view(), name='instructors'),
]
