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
        key = env("OPENDATA_V2_KEY")
    
        # Create existing courses as an in-memory dictionary 
        # for fast comparisons
        existingCourses = list(Course.objects.all())
        existingDict = {}

        # https://stackoverflow.com/questions/8550912/dictionary-of-dictionaries-in-python
        for existing in existingCourses:
            existingDict.setdefault(existing.subject, {})[existing.code] = True
        
        
        # First, get the list of all the academic terms and subjects.
        terms = list(Term.objects.all())
        subjects = list(Subject.objects.all())

        
        # Attempts to insert a course if it doesn't exist yet.
        def insertCourse(course):
            s = Subject.objects.get(code=course['subject'])
            c = str(course['catalog_number'])

            # Check if a course already exists in database;
            # if not, insert it into the database.
            if existingDict.get(s, {}).get(c, False) == True:
                ""
                # print("Course already exists; skipping insert.")
            else:
                print("Course found: " + str(s) + " " + c)
                try:
                    record = Course(subject=s, code=c)
                    record.save()
                    
                    # Also update existing courses dictionary with new course.
                    existingDict.setdefault(s, {})[c] = True
                    
                    #newCourses += 1
                
                except IntegrityError as e:
                    print("Error inserting course: " + str(e))
                
                except DataError as e:
                    print("Error inserting course: " + str(e))
        

        
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

        
        print("Done! Found " + str(newCourses) + " new courses (searched " + str(len(terms)) + " terms)")
    