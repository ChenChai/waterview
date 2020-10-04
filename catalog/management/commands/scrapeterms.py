from django.core.management.base import BaseCommand, CommandError
from catalog.models import Term
from django.db.utils import DataError, IntegrityError
import requests
import environ
import json

# Environment should already be read in settings.py
env = environ.Env()

class Command(BaseCommand):
    help = "updates term in database from API"
    
    def handle(self, *args, **kwargs):
        newTerms = 0
    
        # Create existing courses as an in-memory dictionary 
        # for fast comparisons
        existingTerms = list(Term.objects.all())
        existingDict = {}

        # https://stackoverflow.com/questions/8550912/dictionary-of-dictionaries-in-python
        for existing in existingTerms:
            existingDict[existing.code] = True
        
        # First, get the list of all the academic terms.
        # V3 API contains this list.
        response = requests.get(f"https://openapi.data.uwaterloo.ca/v3/Terms",
            headers={
                'Accept':'application/json',
                'x-api-key': env("OPENDATA_V3_KEY")})
        
        terms = response.json()
        
        # Loop through each term looking for courses that don't exist yet.
        for term in terms:
            termCode = term['termCode']
            termName = term['name']
            
            if not existingDict.get(termCode, False) == True:

                print("Term found: " + str(termCode))
                try:
                    record = Term(code=termCode, name=termName)
                    record.save()
                    
                    # Also update dictionary with new term.
                    existingDict[termCode] = True
                    
                    newTerms += 1

                except IntegrityError as e:
                    print("Error inserting course: " + str(e))
                
                except DataError as e:
                    print("Error inserting course: " + str(e))
        
        print("Done! Found " + str(newTerms) + " new terms")
    