from django.shortcuts import render
from catalog.models import Term, Course, CourseOffering, Instructor
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
    
class CourseListView(generic.ListView):
    """Generic view that will query database
        automatically. to get data on courses and
        display it."""
        
    model = Course
    
class InstructorListView(generic.ListView):
    """Generic view that will query database
        automatically. to get data on courses and
        display it."""
        
    model = Instructor