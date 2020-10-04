from django.core.management.base import BaseCommand, CommandError
from catalog.models import *
from django.db.utils import DataError, IntegrityError
from django.db import connection, transaction
from bs4 import BeautifulSoup, NavigableString

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
        #existingInstructors = list(Instructor.objects.all())
        existingInstructorsDict = {}
        #for existing in existingInstructors:
        #    existingInstructorsDict.setdefault(existing.firstName, {})[existing.lastName] = True
        #print("Done!")

        print("Building existing classes dict")
        #existingClasses = list(ClassOffering.objects.all().select_related('courseOffering','courseOffering__course','courseOffering__course__subject','courseOffering__term'))
        existingClassesDict = {}
        #for existing in existingClasses:
        #    existingClassesDict.setdefault(
        #        str(existing.courseOffering.course.subject)
        #        + existing.courseOffering.course.code 
        #        + str(existing.courseOffering.term), {})[str(existing.classNum)] = True
        #print("Done!")

         Get the combinations of which subjects were offered
         in each term. 
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
                    lastName = fullName[0]

                    if len(fullName) >= 2:
                        firstName = fullName[1]
                    else:
                        firstName = ""
                    
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

        def scrapeScheduleOfClasses(termCode, subject, academicLevel):
            assert(academicLevel == "undergraduate" or academicLevel == "graduate")
            print("Scraping term " + str(termCode) + " subject " + subject)
            level = "grad" if academicLevel == "graduate" else "under" 
            response = requests.get(
                f"https://classes.uwaterloo.ca/cgi-bin/cgiwrap/infocour/salook.pl?level=under&sess={termCode}&subject={subject}")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Object to return.
            classes = []
            
            # Get last updated time
            
            # No results for query, as no table (i.e. term out of range)
            if (soup.table == None):
                print("No classes returned for query " + str(termCode) + subject)
                return classes
            
            # Get trs in first table we see (should be outer-level table)
            rows = list(filter(lambda x: type(x) != NavigableString and x.name == 'tr', soup.table.contents))
            i = 0 
            # Loop through results table
            while i < len(rows): 
                tr = rows[i]
                # Each Course has a rows associated with it with
                # labels for subject, catalog, units and title.            
                # Look for this label row.
                tds = tr.find_all(['td', 'th'])
                if (len(tds) == 4 
                    and tds[0].string == "Subject" 
                    and tds[1].string == "Catalog #" 
                    and tds[2].string == "Units" 
                    and tds[3].string == "Title"):
                    
                    print("-----------------------Found Course")
                    # Retrieve the labelled values in the next row.
                    i = i + 1
                    tr = rows[i]
                    tds = tr.find_all(['td', 'th'])
                    
                    
                    # Convert strings to unicode strings so they don't carry
                    # references to soup object, saving memory
                    assert(subject == tds[0].string.strip())
                    catalogNumber = str(tds[1].string.strip())
                    units         = str(tds[2].string.strip())
                    title         = str(tds[3].string.strip())
                    
                    print("Found values: subject=" + subject + " catalogNumber=" + catalogNumber + " units=" + units + " title=" + title)
                    
                    i = i + 1
                    tr = rows[i]
                    
                    # Check for a note associated with the course.
                    note = None
                    if tr.b != None and tr.b.string == "Notes:":
                        note = str(tr.td.contents[1].strip)
                        print("Note found: " + str(note))
                        
                        i = i + 1
                        tr = rows[i]
                    
                    # This row should be the table of classes.
                    classTable = tr.table
                    
                    classRows = list(filter(lambda x: type(x) != NavigableString and x.name == 'tr', classTable))
                    
                    j = 0
                    while j < len(classRows):
                        classTr = classRows[j]
                        
                        classTds = classTr.find_all(['th', 'td'])
                        print("Parsing [" + str(j) + "]: " + str(classTds))
                        # make sure that everything lines up with what we expect.
                        if j == 0:
                            assert(len(classTds) == 13
                                and classTds[0].string == "Class" 
                                and classTds[1].string == "Comp Sec" 
                                and classTds[2].string == "Camp Loc" 
                                and classTds[3].string == "Assoc Class" 
                                and classTds[4].string == "Rel 1" 
                                and classTds[5].string == "Rel 2" 
                                and classTds[6].string == "Enrl Cap" 
                                and classTds[7].string == "Enrl Tot" 
                                and classTds[8].string == "Wait Cap" 
                                and classTds[9].string == "Wait Tot"
                                and classTds[10].string == "Time Days/Date" 
                                and classTds[11].string == "Bldg Room" 
                                and classTds[12].string == "Instructor" 
                            )
                        elif classTds[0].i != None and classTds[0].i.string.startswith("Reserve:"):
                            # Check if this is a reserve.
                            # If it is, add the reserve to the last class we saw.
                            
                            # Grab reserve group from stuff after colon.
                            reserveGroup            = str(classTds[0].string.split(':', 2)[1].strip())
                            enrollmentCapacity      = str(classTds[1].string.strip())  if classTds[1].string != None else None
                            enrollmentTotal         = str(classTds[2].string.strip())  if classTds[2].string != None else None
                            
                            print("--------------------Reserve found! " + reserveGroup + " " + enrollmentTotal + "/" + enrollmentCapacity)
                            classes[-1]["reserves"].append({
                                "reserve_group": reserveGroup,
                                "enrollment_capacity": enrollmentCapacity,
                                "enrollment_total": enrollmentTotal,
                            })
                            
                            
                            # Assert there's no information we're missing for some reason:
                            
                            
                            
                            # check if there's another instructor listed.
                            # If there is, it will be in index 8.
                            if len(classTds) >= 9 and classTds[8].string != None and len(classTds[8].string) > 0:
                                instructor = str(classTds[8].strip())
                                classes[-1]["classes"][0]["instructors"].append(instructor)
                                
                        elif classTds[0].i != None and classTds[0].i.string.startswith("Held With:"):
                            # Check if the previous section was "Held With" another class.
                            
                            # Grab held_with group from stuff after colon.
                            heldWith = str(classTds[0].string.split(':', 2)[1].strip())
                            
                            print("--------------------Held With Found! " + heldWith)
                            classes[-1]["held_with"].append(heldWith)
                            
                            # check if there's another instructor listed.
                            # If there is, it will be in index 3.
                            if len(classTds) >= 4 and classTds[3].string != None and len(classTds[3].string) > 0:
                                instructor = str(classTds[3].string.strip())
                                classes[-1]["classes"][0]["instructors"].append(instructor)                        
                                
                        elif classTds[0].i != None and classTds[0].i.string.startswith("Topic:"):
                            # Check if the previous section has a topic.
                            
                            assert(len(classTds) == 3)
                            
                            # Grab held_with group from stuff after colon.
                            topic = str(classTds[0].string.split(':', 2)[1].strip())
                            
                            print("--------------------Topic Found! " + heldWith)
                            classes[-1]["topic"] = topic
                            
                            # check if there's another instructor listed.
                            # If there is, it will be in index 3.
                            #if len(classTds) >= 4 and classTds[3].string != None and len(classTds[3].string) > 0:
                            #    instructor = str(classTds[3].string.strip())
                            #    classes[-1]["classes"][0]["instructors"].append(instructor)
                                
                        elif len(classTds) == 11 and classTds[10].string == "Cancelled Section":                        
                            # Check if the previous section was cancelled.
                            classes[-1]["classes"][0]["date"]["is_cancelled"] = True
                            
                        else:
                            assert(len(classTds) == 12 or len(classTds) == 13)
                            # Regular class entry.
                            classNumber             = str(classTds[0].string.strip())  if classTds[0].string != None else None
                            section                 = str(classTds[1].string.strip())  if classTds[1].string != None else None
                            campus                  = str(classTds[2].string.strip())  if classTds[2].string != None else None
                            associatedClass         = str(classTds[3].string.strip())  if classTds[3].string != None else None
                            relatedComponent1       = str(classTds[4].string.strip())  if classTds[4].string != None else None
                            relatedComponent2       = str(classTds[5].string.strip())  if classTds[5].string != None else None
                            enrollmentCapacity      = str(classTds[6].string.strip())  if classTds[6].string != None else None
                            enrollmentTotal         = str(classTds[7].string.strip())  if classTds[7].string != None else None
                            waitingCapacity         = str(classTds[8].string.strip())  if classTds[8].string != None else None
                            waitingTotal            = str(classTds[9].string.strip())  if classTds[9].string != None else None
                            time                    = str(classTds[10].string.strip()) if classTds[10].string != None else None
                            
                            buildingRoom            = str(classTds[11].string.strip()) if classTds[11].string != None else None
                            building                = buildingRoom.split(' ', 2)[0] if buildingRoom != None and len(buildingRoom) > 0 else None
                            room                    = buildingRoom.split(' ', 2)[1] if buildingRoom != None and len(buildingRoom) > 0 else None
                            
                            instructor              = str(classTds[12].string.strip() if len(classTds) > 12 and classTds[12].string != None else None)
                            
                            # TBA is held in the time section
                            isTBA = False
                            if time == "TBA":
                                time = None
                                isTBA = True
                            
                            
                            classes.append({
                                "subject": subject,
                                "catalog_number": catalogNumber,
                                "units": units,
                                "title": title,
                                "note": note,
                                "class_number": classNumber,
                                "section": section,
                                "campus": campus,
                                "associated_class": associatedClass,
                                "related_component_1": relatedComponent1,
                                "related_component_2": relatedComponent2,
                                "enrollment_capacity": enrollmentCapacity,
                                "enrollment_total": enrollmentTotal,
                                "waiting_capacity": waitingCapacity,
                                "waiting_total": waitingTotal,
                                "topic": None,
                                "reserves": [
                                    # Will be filled out in next rows.
                                ],
                                "classes": [
                                    {
                                        "date": {
                                            "start_time": None,
                                            "end_time": None,
                                            "weekdays": time,
                                            "start_date": None,
                                            "end_date": None,
                                            "is_tba": isTBA,
                                            "is_cancelled": False,
                                            "is_closed": False
                                        },
                                        "location": {
                                            "building": building,
                                            "room": room
                                        },
                                        "instructors": [
                                            instructor
                                        ]
                                    }
                                ],
                                "held_with": [
                                    # Will be filled out in next rows.
                                ],
                                "term": termCode,
                                "academic_level": academicLevel,
                                "last_updated": "2020-10-04T15:03:16-04:00"
                            })

                        
                        
                        j = j + 1
                        
                    i = i + 1
                    tr = rows[i]
                    print(tr)
                    assert(len(tr.td.contents) == 0)
                i = i + 1
            
            #print(soup.table.contents)
            return classes

        #termCode = 1209
        #subject = "MATH"

        #scrapeScheduleOfClasses(termCode, subject, "graduate")

        for row in result:
            termCode = row[0]
            subjectCode = row[1]
            print("Searching Term/Subject" + str(row))
            
            # API call to get classes for this term.
            # response = requests.get(
            #     f"https://api.uwaterloo.ca/v2/terms/{termCode}/{subjectCode}/schedule.json?key={key}")
            # 
            # classes = response.json()['data']
            
            classes = scrapeScheduleOfClasses(termCode, subjectCode, "undergraduate").append(scrapeScheduleOfClasses(termCode, subjectCode, "graduate"))
            
            # Loop through classes, adding each one
            for classOffering in classes:
                addClass(classOffering, termCode)
            
        print("Done!")
