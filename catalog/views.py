from django.shortcuts import render, redirect
from django.views import generic
from catalog.models import *
from django.db import connection, transaction
import json

def homepage(request):
    """View function for homepage."""

    # Generate some counts to display
    
    numSubjects = Subject.objects.all().count()
    numCourses = Course.objects.all().count()
    numInstructors = Instructor.objects.all().count()

    context = {
        'num_subjects': numSubjects,
        'num_courses': numCourses,
        'num_instructors': numInstructors,
    }
    
    return render(request, 'homepage.html', context=context)

def aboutpage(request):
    """View function for about page."""
    context = {}
    return render(request, 'aboutpage.html', context=context)

def courses(request):
    """View function for course list"""
    
    # select_related reduces number of queries to just one,
    # doing a join on subject field.
    courseList = list(Course.objects.all().select_related("subject"))
    
    context = {
       'course_list': courseList,
    }
    
    return render(request, 'catalog/course_list.html', context=context)

def courseRandom(request):
    """Redirects to a random course's page. 
       TODO make an error page if there are no courses.
    """
    
    count = Course.objects.count()

    if count == 0:
        # No courses, just redirect to home.
        return redirect('homepage')
    else:
        from random import randint
        model = Course.objects.all()[randint(0,count)] 
        return redirect(model.getAbsoluteUrl())

def subjects(request):
    """View function for subject list"""
    
    subjectList = list(Subject.objects.all())
    context = {
        'subject_list': subjectList
    }
    return render(request, 'catalog/subject_list.html', context=context)

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
        'course_exists': False,
    }
    
    # Check if the subject exists.
    if Subject.objects.filter(code=subject.upper()).exists() == False:
        # If not, return this
        return render(request, 'catalog/course_detail.html', context=context)
    
    subjectModel = Subject.objects.get(code=subject.upper())
        
    # Check if the course exists.
    if Course.objects.filter(subject=subjectModel, code=code.upper()).exists() == False:
        return render(request, 'catalog/course_detail.html', context=context)
    
    courseModel = Course.objects.get(subject=subjectModel, code=code.upper())

    # Redirect to all uppercase
    if subject.upper() != subject or code.upper() != code:
        return redirect(courseModel.getAbsoluteUrl())
    
    context['course'] = courseModel
    context['course_exists'] = True
    
    # Get course offerings for this term.
    offeringQS = CourseOffering.objects.filter(course=courseModel).select_related('term')
    
    if offeringQS.exists() == False:
        # No offerings of this course are in db
        context['offering_exists'] = False
    else:
        context['offering_exists'] = True

        terms = Term.objects.all().order_by('-code')
        offerings = list(offeringQS)
        
        data = {}

        # Construct data structure:
        # dictionary of dictionaries; one entry
        # for each term.
        """
            {
                'term': Term object
                'hasData': True/False depending on whether has data
                'isCancelled': whether all classes were cancelled or not.

                'enrollment': { # Dict of dicts indexed by sectionType
                    'LEC': {
                        // Individual sections
                        'sections': [ { 'num': section number,'total': total enrollment, 'max': max enrollment, 'instructors': [array of inst obj], 'isCancelled': true/false } ....]
                        'sectionCount': number of sections,
                        'averageSize': avg section size.
                                'totalEnrollment': 0,
                                'maxEnrollment': 0,
                    },
                    'TUT': {
                        //...
                    },
                }
                'instructors': [array of instructor objects]
            }
        """
        
        for term in terms:
            data[term] = {
                # Default to not having data, will change to true if we find data.
                'hasData': False, 
                # Similarly, default to class being cancelled.
                'isCancelled': True,
                'enrollment': {},
                'instructors': set(),
            }
        
        # Find the first/last term the course 
        # was offered
        firstTermOffered = offerings[0].term
        lastTermOffered = offerings[0].term
        
        # Find which terms have course offering data
        for offering in offerings:
            data[offering.term]['hasData'] = True
            
            if offering.term < firstTermOffered:
                firstTermOffered = offering.term
            if offering.term > lastTermOffered:
                lastTermOffered = offering.term
            

        # Grab classLocations happening for this course
        classLocations = list(ClassLocation.objects
            .filter(classOffering__courseOffering__course__subject=subject,classOffering__courseOffering__course__code=code)
            .prefetch_related('instructor')
            .select_related('classOffering__courseOffering__term')
            .order_by('classOffering__courseOffering__term'))
            

        # Get all the instructors
        for classLocation in classLocations:
            for instructor in list(classLocation.instructor.all()):
                data[classLocation.classOffering.courseOffering.term]['instructors'].add(instructor)

        
        # Get class offerings
        classOfferingList = list(ClassOffering.objects
            .filter(courseOffering__course__subject=subject,courseOffering__course__code=code)
            .select_related('courseOffering__term')
            .order_by('courseOffering__term'))
        

        # Find the possible section types
        # i.e. LEC, TUT, TST
        sectionTypes = set()
        

        for classOffering in classOfferingList:
            # i.e. LEC 001 -> LEC 
            sectionType = classOffering.sectionName.split(' ', 1)[0]
            sectionTypes.add(sectionType)
        
        # Set default values in data structure
        for term in terms:
            if data[term]['hasData'] == True:
                for sectionType in sectionTypes:
                    data[term]['enrollment'][sectionType] = {
                        'sections': [],
                        'sectionCount': 0,
                        'averageSize': 0,
                        'totalEnrollment': 0,
                        'maxEnrollment': 0,
                    }
        
        # Returns true if a ClassOffering has any ClassLocation with isCancelled == true
        def isCancelled(classOffering):
            return False
            for classLocation in classLocations:
                if classLocation.classOffering == classOffering:
                    if classLocation.isCancelled: 
                        return True
                
            return False
        
        # returns instructors associated with 
        # class offering from class location
        def getInstructors(classOffering):
            instructors = set()
            for classLocation in classLocations:
                for instructor in list(classLocation.instructor.all()):
                    instructors.add(instructor)
            return instructors
          
        for classOffering in classOfferingList:
            sectionType = classOffering.sectionName.split(' ', 1)[0]
            sectionNum = classOffering.sectionName.split(' ', 1)[1]
            term = classOffering.courseOffering.term
            
            if isCancelled(classOffering):
                data[term]['enrollment'][sectionType]['sections'].append({
                    'num': sectionNum,
                    'total': 0,
                    'max': 0,
                    'isCancelled': True,
                    #'instructors': getInstructors(classOffering)
                })
            else:
                # Both offering and class not cancelled
                # Update default value
                data[term]['isCancelled'] = False
                
                data[term]['enrollment'][sectionType]['totalEnrollment'] += classOffering.enrollmentTotal
                

                data[term]['enrollment'][sectionType]['maxEnrollment'] += classOffering.enrollmentCapacity
                
                data[term]['enrollment'][sectionType]['sectionCount'] += 1
                
                data[term]['enrollment'][sectionType]['sections'].append({
                    'num': sectionNum,
                    'total': classOffering.enrollmentTotal,
                    'max': classOffering.enrollmentCapacity,
                    'isCancelled': False,
                    #'instructors': getInstructors(classOffering)
                })


        # Final data cleanup
        for term in terms:
            # Calculate average section size for each section type in each term
            for sectionName, sectionDict in data[term]['enrollment'].items():
                sectionDict['averageSize'] = int(sectionDict['totalEnrollment'] / sectionDict['sectionCount']) if sectionDict['sectionCount'] > 0 else 'n/a'
                
                # Also sort sections
                sectionDict['sections'] = sorted(sectionDict['sections'], key=lambda d: d['num'])
            
            # Sort enrollment dictionaries
            data[term]['enrollment_items'] = sorted(data[term]['enrollment'].items())
            
            # Sort instructors by name
            data[term]['instructors'] = sorted(data[term]['instructors'])
            numInstructors = len(data[term]['instructors'])
            
            # Split instructors into first four
            # and last few to be rendered more
            # prettily
            if numInstructors > 4:
                data[term]['firstInstructors'] =  data[term]['instructors'][:4]
                data[term]['nextInstructors'] =  data[term]['instructors'][-(numInstructors - 4):]
            else: 
                data[term]['firstInstructors'] =  data[term]['instructors']
        
        
        # Create chart data
        termDataItems = sorted(data.items(), reverse=True)
        
        chartData = {
            'labels': [],
            'datasets': [],
        }
        
        
        def getSectionTypeColour(sectionType, alpha=1):
            d = {
                'LEC': '102, 102, 255',
                'TUT': '152, 205, 170',
                
            }
            
            return 'rgba(' + d.get(sectionType, "203, 230, 212") + "," + str(alpha) + ')'
        
        
        # One dataset for each section type
        sectionTypes = sorted(sectionTypes)
        for sectionType in sectionTypes: 
            chartData['datasets'].append({
                'label': sectionType,
                'data': [],
				'backgroundColor': getSectionTypeColour(sectionType, 0.2),
				'borderColor':getSectionTypeColour(sectionType, 1),
				'borderWidth': 1,
                'pointRadius': 3,
                'spanGaps': False, # Useful for null data.
            })
        
        # Reverse to loop through terms from least to most recent
        for term, info in reversed(termDataItems):
            if (term > firstTermOffered and term < lastTermOffered) or term == firstTermOffered or term == lastTermOffered:
                chartData['labels'].append(term.reverseName())
                
                # sectionTypes will be looped through in same order.
                for i in range(0, len(sectionTypes)):
                    sectionType = sectionTypes[i]
                    
                    if info['hasData'] == True:
                        chartData['datasets'][i]['data'].append(info['enrollment'][sectionType]['totalEnrollment'])
                    else:
                        chartData['datasets'][i]['data'].append(0)

                
        
            
            
        
        
        context['term_data_items'] = termDataItems
        context['section_types'] = sorted(sectionTypes)
        context['chart_data'] = json.dumps(chartData)

    return render(request, 'catalog/course_detail.html', context=context)

def instructorDetail(request, instructorId):
    """View function for one instructor"""
    
    context = {}
    if Instructor.objects.filter(id=instructorId).exists():
        instructor = Instructor.objects.get(id=instructorId)
        
        # Get the class offerings that have been taught by this instructor
        classLocationList = list(ClassLocation.objects.filter(instructor__id=instructor.id)
            .select_related('classOffering__courseOffering__term','classOffering__courseOffering__course','classOffering__courseOffering__course__subject'))
        
        # Keys are CourseOfferings, values are a set
        # of when they were offered.
        courseOfferingDict = {}
        
        # Use the classLocations to organize the dictionary.
        for classLocation in classLocationList:
            courseOfferingDict.setdefault(classLocation.classOffering.courseOffering.course, set()).add(classLocation.classOffering.courseOffering.term)        
        
        for course, terms in courseOfferingDict.items():
            courseOfferingDict[course] = sorted(terms, reverse=True)
        
        context = {
            'first_name': instructor.firstName,
            'last_name': instructor.lastName,
            'exists': True,
            # Sort here instead of in template to use sorted()
            'course_offerings_items': sorted(courseOfferingDict.items()),
        }
    
    return render(request, 'catalog/instructor_detail.html', context=context)

def instructorRandom(request):
    """Redirects to a random instructor's page. 
       TODO make an error page if there are no instructors.
    """
    
    count = Instructor.objects.count()

    if count == 0:
        # No instructors, just redirect to home.
        return redirect('homepage')
    else:
        from random import randint
        model = Instructor.objects.all()[randint(0,count)] 
        return redirect(model.getAbsoluteUrl())

class InstructorListView(generic.ListView):
    """Generic view that will query database
        automatically. to get data on courses and
        display it."""
        
    model = Instructor



