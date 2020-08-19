from django.db import models
from django.urls import reverse

class Subject(models.Model):
    """Model representing an academic subject at UWaterloo"""
    # subject code
    code = models.CharField(primary_key=True, max_length=10)
    
    # Full name
    name = models.CharField(max_length=100)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return str(self.code)

class Term(models.Model):
    """Model representing an academic term at UWaterloo"""
    # 4-digit term code
    code = models.CharField(primary_key=True, max_length=10)
    
    # i.e. Winter 2020
    name = models.CharField(max_length=100, help_text="i.e. 'Winter 2020'")
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return str(self.code)

class Instructor(models.Model):
    """Model representing an instructor. At the moment, 
    instructors are unique by name, since we don't have access
    to IDs. We'll still keep a separate primary key ID, 
    automatically made by django."""
    
    firstName = models.CharField(max_length=100)
    lastName = models.CharField(max_length=100)
    
    class Meta:
        unique_together = ['firstName', 'lastName']
        ordering = ['firstName', 'lastName']
    
    def __str__(self):
        return firstName + ' ' + lastName

class Course(models.Model):
    """Model representing a course at UWaterloo"""
    
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    
    # ~3-4 digits normally
    code = models.CharField(max_length=10, help_text="Numbers/characters after subject for the course")
    
    
    class Meta:
        # Subject and code together act as a primary key.
        unique_together = (('subject', 'code'),)
        
        # Order by subject first, then code in database
        ordering = ['subject', 'code']
        
    def __str__(self):
        """String representation of Course"""
        return str(self.subject) + ' ' + str(self.code)
    
    def getAbsoluteUrl(self):
        return reverse(views.courses) + str(self.subject.code) + '/' + self.code + '/'

class CourseOffering(models.Model):
    """Model representing an offering of a course in a given term."""
    
    # Course and term are both foreign keys.
    # Use CASCADE to delete referencing rows on delete.
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    
    # i.e. Algebra for Honours Mathematics
    name = models.CharField(max_length=100)
    
    class Meta:
        unique_together = (('course', 'term'),)
        
        # Order by course first, since users will probably
        # want to see the offerings for a specific course
        # rather than all the courses offered in a term.
        ordering = ['course', 'term']
        
    def __str__(self):
        return str(self.course) + ' ' + str(self.term)

class ClassOffering(models.Model):
    """Model representing one class of a course offering."""
    
    # UWaterloo class number. Hopefully unique within
    # a CourseOffering in a term. Not unique in general
    classNum = models.CharField(max_length=10)
    
    # Course offering instance this class is offered under
    courseOffering = models.ForeignKey('CourseOffering', on_delete=models.CASCADE)
    
    # i.e. 'LEC 010'
    sectionName = models.CharField(max_length=10)
    
    # For special topics in the course.
    topic = models.CharField(max_length=100, null=True)
    
    # i.e. MC
    campus = models.CharField(max_length=100)
    
    # Administrative values for enrollment
    associatedClass = models.CharField(max_length=10)
    relComp1 = models.CharField(max_length=10, null=True)
    relComp2 = models.CharField(max_length=10, null=True)
    
    # Maximum number of students that can 
    # enroll in the class
    enrollmentCapacity = models.IntegerField()
    
    # Actual number of students enrolled; 
    # may be higher than enrollmentCapacity.
    enrollmentTotal = models.IntegerField()
    
    class Meta:
        unique_together = (('classNum', 'courseOffering'))
        
        # Order by sectionName for ease of reading, 
        # can see which are lectures and which tutorials.
        ordering = ['sectionName']
    
    def __str__(self):
        return str(self.courseOffering) + ' ' + str(self.classNum)

class ClassLocation(models.Model):
    """Model representing one class location as presented
        in the API query data. This information is stored
        here with some duplication to mirror the structure
        of the authoritative data source as closely as possible
        in case the duplication is relevant in some instances."""
    
    classOffering = models.ForeignKey('ClassOffering', on_delete=models.CASCADE)
    
    # If startDate == endDate, this is probably a 'fake'
    # section we sometimes see in the data. Not sure
    # why these show up.
    startDate = models.CharField(max_length=10, null=True)
    endDate = models.CharField(max_length=10, null=True)

    # When the course runs.
    startTime = models.CharField(max_length=10, null=True)
    endTime = models.CharField(max_length=10, null=True)
    weekdays = models.CharField(max_length=10, null=True)
    
    # Where the course runs.
    building = models.CharField(max_length=100, null=True)
    room = models.CharField(max_length=100, null=True)
    
    # potential for multiple instructors?
    instructor = models.ManyToManyField(Instructor)
    
    isCancelled = models.BooleanField()
    isClosed = models.BooleanField()
    isTBA = models.BooleanField()
    
    class Meta:
        # Order by startDate since most 'real' class times are null
        ordering = ['startDate']

    def __str__(self):
        return str(self.classOffering)

class ClassReserve(models.Model):
    """Model representing a reserve section in a class"""
    
    classOffering = models.ForeignKey('ClassOffering', on_delete=models.CASCADE)
    
    # People the reserve is for
    reserveGroup = models.CharField(max_length=100)
    
    enrollmentCapacity = models.IntegerField(null=True)
    enrollmentTotal = models.IntegerField(null=True)
    
    def __str__(self):
        return str(self.classOffering) + ' ' + str(reserveGroup)
    
    
    
# import after functions: https://stackoverflow.com/questions/11698530/two-python-modules-require-each-others-contents-can-that-work
from catalog import views
