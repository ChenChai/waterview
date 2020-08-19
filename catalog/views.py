from django.shortcuts import render, redirect
from catalog.models import *
from django.views import generic

def homepage(request):
    """View function for homepage."""

    # Generate some counts to display
    
    numTerms = Term.objects.all().count()
    numCourses = Course.objects.all().count()
    numCourseOfferings = CourseOffering.objects.all().count()
    
    context = {
        'numTerms': numTerms,
        'numCourses': numCourses,
        'numCourseOfferings': numCourseOfferings,
    }
    
    return render(request, 'homepage.html', context=context)

def courses(request):
    """View function for course list"""
    
    # select_related reduces number of queries to just one,
    # doing a join on subject field.
    courseList = list(Course.objects.all().select_related("subject"))
    
    context = {
       'course_list': courseList,
    }
    
    return render(request, 'catalog/course_list.html', context=context)

def subjectDetail(request, subject):
    """View function for a subject (i.e. CS)"""
    
    # Redirect to all uppercase subject
    if subject.upper() != subject:
        pathArray = request.path.split('/')
        
        # Replace last slug in path with uppercase version of slug
        newPath = ''
        for i in range(0, len(pathArray) - 2):
            newPath += pathArray[i] + '/'
        
        newPath += subject.upper() + '/'
        return redirect(newPath)
    
    
    if Subject.objects.filter(code=subject).exists():
    
        model = Subject.objects.get(code=subject)
        
        courseList = list(Course.objects.filter(subject=model).select_related('subject'))
        
        context = {
            'subject_code': subject,
            'subject_name': model.name,
            'course_list': courseList,
        }
        
    else:
        context = {
            'subject_code': subject,
        }
    
    
    return render(request, 'catalog/subject_detail.html', context=context)

def courseDetail(request, subject, code):
    """View function for a specific course (i.e. CS 241E)"""
    
    return courses(request)

class InstructorListView(generic.ListView):
    """Generic view that will query database
        automatically. to get data on courses and
        display it."""
        
    model = Instructor