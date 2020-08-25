from django.shortcuts import render, redirect
from django.views import generic
from catalog.models import *
from django.db import connection, transaction

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
                
                # Grab classLocations happening for this course
                classLocationList = list(ClassLocation.objects
                    .filter(classOffering__courseOffering__course__subject=subject,classOffering__courseOffering__course__code=code)
                    .prefetch_related('instructor')
                    .select_related('classOffering__courseOffering__term')
                    .order_by('classOffering__courseOffering__term'))
                
                # Use a dict of sets to store instructors
                # in each term to avoid duplication.
                termInstructorDict = {}
                for classLocation in classLocationList:
                    for instructor in list(classLocation.instructor.all()):
                        termInstructorDict.setdefault(classLocation.classOffering.courseOffering.term, set()).add(instructor)
                
                # Get class offerings
                classOfferingList = list(ClassOffering.objects
                    .filter(courseOffering__course__subject=subject,courseOffering__course__code=code)
                    .select_related('courseOffering__term')
                    .order_by('courseOffering__term'))
                
                # Returns true if a ClassOffering has any ClassLocation with isCancelled == true
                def isCancelled(classOffering):
                    for classLocation in classLocationList:
                        if classLocation.classOffering == classOffering:
                            if classLocation.isCancelled: 
                                return True
                        
                    return False
                
                
                # Create dictionaries containing the enrollment within sections of a class
                enrollmentDict = {}
                enrollmentMaxDict = {}
                
                sectionTypes = set()
                
                for classOffering in classOfferingList:
                    sectionType = classOffering.sectionName.split(' ', 1)[0]
                    sectionNum = classOffering.sectionName.split(' ', 1)[1]
                    
                    # Keep track of all the different types of sections
                    sectionTypes.add(sectionType)
                    
                    # Only count enrollment for sections
                    # that haven't been cancelled.
                    if isCancelled(classOffering) == False:
                        enrollmentDict.setdefault(classOffering.courseOffering.term, {}).setdefault(sectionType, {})[sectionNum] = classOffering.enrollmentTotal
                        
                        enrollmentMaxDict.setdefault(classOffering.courseOffering.term, {}).setdefault(sectionType, {})[sectionNum] = classOffering.enrollmentCapacity
                
                    
                for term in terms:
                    # Set default to false so template will
                    # know what to not render.
                    termList[term] = False
                             
                # Loop through each course offering, getting information
                for offering in offeringList:
                    enrollmentData = []
                    
                    # Loop through each section type, getting the 
                    # enrollment in the section.
                    for typeName in sorted(sectionTypes):
                        enrollmentTotal = 0
                        enrollmentMax = 0
                                          
                        for key, val in enrollmentDict.get(offering.term, {}).get(sectionType, {}).items():
                            enrollmentTotal += int(val) 
                            
                        for key, val in enrollmentMaxDict.get(offering.term, {}).get(sectionType, {}).items():
                            enrollmentMax += int(val)    
                        
                        enrollmentData.append(str(enrollmentTotal) + "/" + str(enrollmentMax))
                        
                    # Sort instructors
                    instructors = set()
                    if offering.term in termInstructorDict:
                        for instructor in termInstructorDict.get(offering.term):
                            instructors.add(str(instructor))
                        instructors = sorted(instructors)
                    else: 
                        instructors = None
                    
                    # Ordering of array is order the values 
                    # will be output to in the table.
                    termList[offering.term] = {
                        'status': 'offered', 
                        'instructors': instructors,
                        'enrollment': enrollmentData,
                    }

                context['term_list'] = termList
                context['section_types'] = sorted(sectionTypes)

    return render(request, 'catalog/course_detail.html', context=context)

def instructorDetail(request, name):
    """View function for one instructor"""
    
    
    context = {
        'first_name': firstName,
        'last_name': lastName,
    }
    
    return render(request, 'catalog/instructor_detail.html', context=context)

class InstructorListView(generic.ListView):
    """Generic view that will query database
        automatically. to get data on courses and
        display it."""
        
    model = Instructor



