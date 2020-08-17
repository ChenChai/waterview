from django.core.management.base import BaseCommand, CommandError
from catalog.models import Course
from django.db.utils import DataError, IntegrityError
import requests
import environ
import json

# Environment should already be read in settings.py
env = environ.Env()

class Command(BaseCommand):
    help = "updates course list in database from API"
    
    def handle(self, *args, **kwargs):
        
        term = 1201
        key = env("OPENDATA_V2_KEY")
        
        # API call to get courses for this term.
        response = requests.get(
            f"https://api.uwaterloo.ca/v2/terms/{term}/courses.json?key={key}")
        
        
        courses = response.json()['data']
        
        # Get existing courses as an in-memory dictionary 
        # for fast comparisons
        existingCourses = list(Course.objects.all())
        existingDict = {}
        
        # https://stackoverflow.com/questions/8550912/dictionary-of-dictionaries-in-python
        for existing in existingCourses:
            existingDict.setdefault(existing.subject, {})[existing.code] = True
        
        
        #print(existingDict)
        
        for course in courses:
            s = course['subject']
            c = str(course['catalog_number'])
            print("Course found: " + course['subject'] + course['catalog_number'])
            
            # Check if a course already exists in database;
            # if not, insert it into the database.
            if existingDict.get(s, {}).get(c, False) == True:
                print("Course already exists; skipping insert.")
            else:
                print("Course does not yet exist; inserting.")
                try:
                    record = Course(subject=s, code=c)
                    record.save()


                except IntegrityError as e:
                    # Can happen with duplicate entries
                    print("Error inserting course: " + str(e))
                
                except DataError as e:
                    # error inserting into database
                    print("Error inserting course: " + str(e))

        print("Done!")
    