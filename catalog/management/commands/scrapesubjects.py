from django.core.management.base import BaseCommand, CommandError
from catalog.models import Subject
from django.db.utils import DataError, IntegrityError
import requests
import environ
import json

# Environment should already be read in settings.py
env = environ.Env()

class Command(BaseCommand):
    help = "updates subjects in database from API"
    
    def handle(self, *args, **kwargs):
        newCount = 0
    
        # Create existing courses as an in-memory dictionary 
        # for fast comparisons
        existingSubjects = list(Subject.objects.all())
        existingDict = {}

        # https://stackoverflow.com/questions/8550912/dictionary-of-dictionaries-in-python
        for existing in existingSubjects:
            existingDict[existing.code] = True
        
        # First, get the list of all the academic terms.
        # V3 API contains this list.
        response = requests.get(f"https://openapi.data.uwaterloo.ca/v3/Subjects",
            headers={
                'Accept':'application/json',
                'x-api-key': env("OPENDATA_V3_KEY")})
        
        subjects = response.json()
        
        # Loop through each term looking for courses that don't exist yet.
        for subject in subjects:
            code = subject['code']
            # Description gives "full name"
            name = subject['description']
            
            if not existingDict.get(code, False) == True:

                print("Subject found: " + str(code))
                try:
                    record = Subject(code=code, name=name)
                    record.save()
                    
                    # Also update dictionary with new term.
                    existingDict[code] = True
                    
                    newCount += 1

                except IntegrityError as e:
                    print("Error inserting course: " + str(e))
                
                except DataError as e:
                    print("Error inserting course: " + str(e))
        
        print("Done! Found " + str(newCount) + " new subjects")
    