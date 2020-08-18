from django.core.management.base import BaseCommand, CommandError
from catalog.models import Course, CourseOffering, Term, Subject, ClassOffering
from django.db.utils import DataError, IntegrityError
from django.db import connection, transaction

import requests
import environ
import json

# Environment should already be read in settings.py
env = environ.Env()

class Command(BaseCommand):
    help = "updates class list in database from API"
    
    def handle(self, *args, **kwargs):
        newCourses = 0
        key = env("OPENDATA_V2_KEY")
        cursor = connection.cursor()
        
        # Get the combinations of which subjects were offered
        # in each term. 
        cursor.execute("""
            SELECT DISTINCT term_id, subject_id
            FROM catalog_courseoffering
            JOIN catalog_course ON 
                catalog_course.id = catalog_courseoffering.course_id
            """)
        
        result = cursor.fetchall()
        
        
        def addClass(classOffering, termCode):
            try:
                # Find existing models
                termModel = Term.objects.get(code=termCode)
                subjectModel = Subject.objects.get(code=classOffering['subject'])
                courseModel = Course.objects.get(subject=subjectModel, code=classOffering['catalog_number'])
                courseOfferingModel = CourseOffering.objects.get(
                    term=termModel, course=courseModel)

                # Insert new class.
                classRecord = ClassOffering(
                    classNum=classOffering['class_number'],
                    courseOffering=courseOfferingModel,
                    sectionName=classOffering['section'],
                    topic=classOffering['topic'],
                    campus=classOffering['campus'],
                    associatedClass=str(classOffering['associated_class']),
                    relComp1=str(classOffering['related_component_1']),
                    relComp2=str(classOffering['related_component_2']),
                    enrollmentCapacity=classOffering['enrollment_capacity'],
                    enrollmentTotal=classOffering['enrollment_total']
                )
                print("Adding class: " + str(classRecord))
                classRecord.save()
                
                
                # If a duplicate is inserted, will error out here...
                
                # Delete existing Reserve and ClassLocation objects associated with this class.
                ClassLocation.objects.filter(classOffering=classRecord).delete()
                
                ClassReserve.objects.filter(classOffering=classRecord).delete()
                
                
                
                
                
                
                
            
            except Exception as e:
                    print("Error inserting class offering: " + str(e))

        
        for row in result:
            termCode = row[0]
            subjectCode = row[1]
            print(str(row))
            
            # API call to get classes for this term.
            response = requests.get(
                f"https://api.uwaterloo.ca/v2/terms/{termCode}/{subjectCode}/schedule.json?key={key}")
            print("Got response: " + str(response))
            
            classes = response.json()['data']
            
            # Loop through classes, adding each one
            for classOffering in classes:
                addClass(classOffering, termCode)
            
        print(str(len(result)) + " term/subject combinations")
            
            
            
