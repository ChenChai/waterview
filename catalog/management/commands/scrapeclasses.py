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
        
        # Set up existing instructor and ClassOffering dictionaries.
        
        print("Building existing instructors dict")
        existingInstructors = list(Instructor.objects.all())
        existingInstructorsDict = {}
        for existing in existingInstructors:
            existingInstructorsDict[existing.firstName + existing.lastName] = True
        print("Done!")

        print("Building existing classes dict")
        existingClasses = list(ClassOffering.objects.all().select_related('courseOffering','courseOffering__course','courseOffering__course__subject','courseOffering__term'))
        existingClassesDict = {}
        for existing in existingClasses:
            existingClassesDict.setdefault(
                str(existing.courseOffering.course.subject)
                + existing.courseOffering.course.code 
                + str(existing.courseOffering.term), {})[str(existing.classNum)] = True
        print("Done!")

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
        
            subjectCode = classOffering['subject']
            courseCatalogNum = classOffering['catalog_number']
            classNum = classOffering['class_number']
            
            try:
                # Find existing models
                termModel = Term.objects.get(code=termCode)
                subjectModel = Subject.objects.get(code=subjectCode)
                courseModel = Course.objects.get(subject=subjectModel, code=courseCatalogNum)
                courseOfferingModel = CourseOffering.objects.get(
                    term=termModel, course=courseModel)
                
                if existingClassesDict.get(subjectCode+courseCatalogNum+termCode, {}).get(str(classNum), False) == True:
                    # Already exists; skip insert.
                    classRecord = ClassOffering.objects.get(classNum=classNum, courseOffering=courseOfferingModel)
                    print("    Class exists; updating reserves/locations for: " + str(classRecord))

                else: 
                    # Insert new class.
                    classRecord = ClassOffering(
                        classNum=classNum,
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
                    
                    existingClassesDict.setdefault(subjectCode+courseCatalogNum+termCode, {})[classNum] = True
                                    
                # Delete existing Reserve and ClassLocation objects associated with this class.
                # We'll re-insert the data even if the class already exists.
                ClassLocation.objects.filter(classOffering=classRecord).delete()
                ClassReserve.objects.filter(classOffering=classRecord).delete()
                
                for reserve in classOffering['reserves']:
                    try:
                        print("        Adding reserve for " + str(reserve['reserve_group']))

                        reserveRecord = ClassReserve(
                            classOffering=classRecord,
                            reserveGroup=reserve['reserve_group'],
                            enrollmentCapacity=reserve['enrollment_capacity'],
                            enrollmentTotal=reserve['enrollment_total'],
                        )
                        
                        reserveRecord.save()
                        
                    except Exception as e:
                        print("        Error inserting reserve: " + str(e))


                for classLocation in classOffering['classes']:
                    
                    instructors = []
                    
                    
                    
                    for instructor in classLocation['instructors']:
                        fullName = instructor.split(',', 1)
                        firstName = fullName[0]
                        lastName = fullName[1]
                        
                        if existingInstructorsDict.get(firstName + lastName, False) == True:
                            # instructor already exists.
                            instructors.append(Instructor.objects.get(firstName=firstName, lastName=lastName))
                        else:
                            try:
                                instructorRecord = Instructor(
                                    firstName=firstName,
                                    lastName=lastName,
                                )
                                print("        Adding Instructor: " + str(fullName))

                                instructorRecord.save()
                                existingInstructorsDict[firstName+lastName] = True
                                
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
                            locationRecord.instructor.add(instructorRecord)
                        
                    except Exception as e:
                            print("        Error inserting ClassLocation: " + str(e))

            except IntegrityError as e:
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
            
        print("Done!")
