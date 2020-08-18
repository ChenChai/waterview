from django.core.management.base import BaseCommand, CommandError
from catalog.models import Course, CourseOffering, Term, Subject
from django.db.utils import DataError, IntegrityError
import requests
import environ
import json

# Environment should already be read in settings.py
env = environ.Env()

class Command(BaseCommand):
    help = "updates course list in database from API"
    
    def handle(self, *args, **kwargs):
        newCourses = 0
        newCourseOfferings = 0
        key = env("OPENDATA_V2_KEY")
        
        print("Setting up....")
        
        # Create existing courses as an in-memory dictionary 
        # for fast comparisons
        existingCourses = list(Course.objects.all().select_related('subject'))
        existingCourseDict = {}
        existingOfferings = list(CourseOffering.objects.all().select_related('course').select_related('course__subject').select_related('term'))
        existingOfferingsDict = {}
        
        # https://stackoverflow.com/questions/8550912/dictionary-of-dictionaries-in-python
        for existing in existingCourses:
            existingCourseDict.setdefault(existing.subject, {})[existing.code] = True
        
        for existing in existingOfferings:
            existingOfferingsDict.setdefault(str(existing.course), {})[existing.term.code] = True
        
        # First, get the list of all the academic terms and subjects.
        terms = list(Term.objects.all())
        subjects = list(Subject.objects.all())
        
        print("Beginning Scraping!")
        
        # Attempts to insert a course if it doesn't exist yet.
        def insertCourse(course):
            s = Subject.objects.get(code=course['subject'])
            c = str(course['catalog_number'])

            # Check if a course already exists in database;
            # if not, insert it into the database.
            if existingCourseDict.get(s, {}).get(c, False) == True:
                ""
                #print("COURSE already exists; skipping insert.")
            else:
                print("COURSE found: " + str(s) + " " + c)
                try:
                    courseModel = Course(subject=s, code=c)
                    courseModel.save()
                    
                    # Also update existing courses dictionary with new course.
                    existingCourseDict.setdefault(s, {})[c] = True
                    
                    newCourses += 1
                
                except IntegrityError as e:
                    print("Error inserting course: " + str(e))
                
                except DataError as e:
                    print("Error inserting course: " + str(e))
            
        
        def insertCourseOffering(course, termCode):
            s = Subject.objects.get(code=course['subject'])
            c = str(course['catalog_number'])
            courseName = str(course['title'])
            courseModel = Course.objects.get(subject=s, code=c)

            # Try to insert a course offering as well.
            if existingOfferingsDict.get(str(courseModel), {}).get(str(termCode), False) == True:
                ""
                print("Course Offering already exists; skipping insert:"  + str(courseModel) + " " + str(termCode) + "(" + courseName + ")")
            else:
                print("Course Offering found: " + str(courseModel) + " " + str(termCode) + "(" + courseName + ")")
                try:
                    termModel = Term.objects.get(code=termCode)
                    
                    record = CourseOffering(course=courseModel, term=termModel, name=courseName)
                    record.save()
                    
                    # Also update existing courses dictionary with new offering.
                    existingOfferingsDict.setdefault(str(courseModel), {})[termCode] = True
                    
                    newCourseOfferings += 1

                except Exception as e:
                    print("Error inserting course offering: " + str(e))

        # Loop through each term looking for courses that don't exist yet.
        for term in terms:
            termCode = term.code
            print("Term: " + termCode)

            # API call to get courses for this term.
            response = requests.get(
                f"https://api.uwaterloo.ca/v2/terms/{termCode}/courses.json?key={key}")
            
            courses = response.json()['data']
            
            for course in courses:
                insertCourse(course)
                insertCourseOffering(course, termCode)


        # Also look through courses returned by API itself.
        # API call to get courses for this term.
        for subject in subjects:
            subjectCode = subject.code
            print("Subject: " + subjectCode)

            # API call to get courses for this term.
            response = requests.get(
                f"https://api.uwaterloo.ca/v2/courses/{subjectCode}.json?key={key}")
            
            courses = response.json()['data']
            
            for course in courses:
                insertCourse(course)

        print("Done! Found " + str(newCourses) + " new courses and " + str(newCourseOfferings) + " new course offerings.")