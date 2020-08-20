from django.shortcuts import render, redirect
from django.views import generic
from catalog.models import *
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
    
    context = {
        'subject_code': subject,
    }
    
    if Subject.objects.filter(code=subject.upper()).exists():
        model = Subject.objects.get(code=subject.upper())

        # Redirect to all uppercase URL
        if subject.upper() != subject:
            return redirect(model.getAbsoluteUrl())

        courseList = list(Course.objects.filter(subject=model).select_related('subject'))
        
        context = {
            'subject_code': subject,
            'subject_name': model.name,
            'course_list': courseList,
            'exists': True,
        }
    
    return render(request, 'catalog/subject_detail.html', context=context)

def courseDetail(request, subject, code):
    """View function for a specific course (i.e. CS 241E)"""
    
    context = {
        'subject_code': subject,
        'catalog_code': code,
    }
    
    # Check if the subject exists.
    if Subject.objects.filter(code=subject.upper()).exists():
        subjectModel = Subject.objects.get(code=subject.upper())
        
        # Check if the course exists.
        if Course.objects.filter(subject=subjectModel, code=code.upper()).exists():
            courseModel = Course.objects.get(subject=subjectModel, code=code.upper())

            # Redirect to all uppercase
            if subject.upper() != subject or code.upper() != code:
                return redirect(courseModel.getAbsoluteUrl())
                 
            context = {
                'subject_code': subject,
                'catalog_code': code,
                'course': courseModel,
                'exists': True,
            }
            
            offeringQS = CourseOffering.objects.filter(course=courseModel).select_related('term')
            
            if offeringQS.exists():
                
                terms = Term.objects.all().order_by('-code')
                
                termList = {}
                
                offeringList = list(offeringQS)
                
                for term in terms:
                    # Set default to false so template will
                    # know what to not render.
                    termList[term] = False

                for offering in offeringList:
                    # Ordering of array is order the values 
                    # will be output to in the table.
                    termList[offering.term] = [offering.term.name, 'offered']
                    
                
                context['term_list'] = termList
                
                print("term_list: " + str(termList))
    
    return render(request, 'catalog/course_detail.html', context=context)

class InstructorListView(generic.ListView):
    """Generic view that will query database
        automatically. to get data on courses and
        display it."""
        
    model = Instructor


