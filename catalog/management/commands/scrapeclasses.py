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
            existingInstructorsDict.setdefault(existing.firstName, {})[existing.lastName] = True
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
                    sectionName=classOffering.get('section'),
                    topic=classOffering.get('topic'),
                    campus=classOffering.get('campus'),
                    associatedClass=str(classOffering.get('associated_class')),
                    relComp1=str(classOffering.get('related_component_1')),
                    relComp2=str(classOffering.get('related_component_2')),
                    enrollmentCapacity=classOffering.get('enrollment_capacity'),
                    enrollmentTotal=classOffering.get('enrollment_total'),
                )
                
                print("    Adding class: " + str(classRecord))
                classRecord.save()
                
                existingClassesDict.setdefault(subjectCode+courseCatalogNum+termCode, {})[classNum] = True
                                
            # Delete existing Reserve and ClassLocation objects associated with this class.
            # We'll re-insert the data even if the class already exists.
            ClassLocation.objects.filter(classOffering=classRecord).delete()
            ClassReserve.objects.filter(classOffering=classRecord).delete()
            
            for reserve in classOffering['reserves']:
                print("        Adding reserve for " + str(reserve.get('reserve_group')))

                reserveRecord = ClassReserve(
                    classOffering=classRecord,
                    reserveGroup=reserve.get('reserve_group'),
                    enrollmentCapacity=reserve.get('enrollment_capacity'),
                    enrollmentTotal=reserve.get('enrollment_total'),
                )
                
                reserveRecord.save()

            for classLocation in classOffering['classes']:
                
                instructors = []

                for instructor in classLocation['instructors']:
                    fullName = instructor.split(',', 1)
                    firstName = fullName[0]

                    if len(fullName) >= 2:
                        lastName = fullName[1]
                    else:
                        lastName = ""
                    
                    if existingInstructorsDict.get(firstName, {}).get(lastName, False) == True:
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
                            existingInstructorsDict.setdefault(firstName, {})[lastName] = True
                            
                            instructors.append(instructorRecord)
                        except IntegrityError as e:
                            print("        Error: " + str(e))
                        
                locationRecord = ClassLocation(
                    classOffering =classRecord,
                    startDate     = classLocation.get('date', {}).get('start_date'),
                    endDate       = classLocation.get('date', {}).get('end_date'  ),
                    startTime     = classLocation.get('date', {}).get('start_time'),
                    endTime       = classLocation.get('date', {}).get('end_time'  ),
                    weekdays      = classLocation.get('date', {}).get('weekdays'  ),
                    building      = classLocation.get('location', {}).get('building'),
                    room          = classLocation.get('location', {}).get('room'),
                    isCancelled   = classLocation.get('date', {}).get('is_cancelled'),
                    isClosed      = classLocation.get('date', {}).get('is_closed'),
                    isTBA         = classLocation.get('date', {}).get('is_tba'),
                )
                
                print("        Adding ClassLocation: " + str(locationRecord))
                locationRecord.save()
                
                for instructorRecord in instructors:
                    locationRecord.instructor.add(instructorRecord)

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
