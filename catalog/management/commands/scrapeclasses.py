from django.core.management.base import BaseCommand, CommandError
from catalog.models import *
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
                    enrollmentTotal=classOffering['enrollment_total'],
                )
                
                print("    Adding class: " + str(classRecord))
                classRecord.save()
                
                # If a duplicate is inserted, will error out here...
                
                # Delete existing Reserve and ClassLocation objects associated with this class.
                ClassLocation.objects.filter(classOffering=classRecord).delete()
                ClassReserve.objects.filter(classOffering=classRecord).delete()
                
                for reserve in classOffering['reserves']:
                    try:
                        reserveRecord = ClassReserve(
                            classOffering=classRecord,
                            reserveGroup=reserve['reserve_group'],
                            enrollmentCapacity=reserve['enrollment_capacity'],
                            enrollmentTotal=reserve['enrollment_total'],
                        )
                        
                        print("        Adding reserve: " + str(reserveRecord) + " for " + str(reserveRecord.reserveGroup))
                        reserveRecord.save()
                        
                    except Exception as e:
                        print("        Error inserting reserve: " + str(e))

                
                for classLocation in classOffering['classes']:
                    
                    instructors = []
                    
                    for instructor in classLocation['instructors']:
                        try:
                            fullName = instructor.split(',', 1)
                            instructorRecord = Instructor(
                                firstName=fullName[0],
                                lastName=fullName[1],
                            )
                            print("        Adding Instructor: " + str(fullName))

                            instructorRecord.save()
                            
                            instructors.append(instructorRecord)
                        except Exception as e:
                            print("        Error inserting instructor: " + str(e))
                    
                    try:
                        locationRecord = ClassLocation(
                            classOffering=classRecord,
                            startDate=classLocation['date']['start_date'],
                            endDate=classLocation['date']['end_date'],
                            startTime=classLocation['date']['start_time'],
                            endTime=classLocation['date']['end_time'],
                            weekdays=classLocation['date']['weekdays'],
                            building=classLocation['location']['building'],
                            room=classLocation['location']['room'],
                            isCancelled=classLocation['date']['is_cancelled'],
                            isClosed=classLocation['date']['is_closed'],
                            isTBA=classLocation['date']['is_tba'],
                        )
                        
                        print("        Adding ClassLocation: " + str(locationRecord))
                        locationRecord.save()
                        
                        for instructorRecord in instructors:
                            locationRecord.instructors.add(instructorRecord)
                        
                    except Exception as e:
                            print("        Error inserting ClassLocation: " + str(e))

            except Exception as e:
                    print("    Error adding class: " + str(e))

        
        for row in result:
            termCode = row[0]
            subjectCode = row[1]
            print("Searching Term/Subject" + str(row))
            
            # API call to get classes for this term.
            response = requests.get(
                f"https://api.uwaterloo.ca/v2/terms/{termCode}/{subjectCode}/schedule.json?key={key}")
            
            classes = response.json()['data']
            
            # Loop through classes, adding each one
            for classOffering in classes:
                addClass(classOffering, termCode)
            
        print(str(len(result)) + " term/subject combinations")
            
            
            
