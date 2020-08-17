from django.db import models

# Create your models here.

class Course(models.Model):
    """Model representing a course at UWaterloo"""
    
    # ~2-5 letters
    subject = models.CharField(max_length=10, help_text="Course subject, i.e. CS, MATH")
    
    # ~3-4 digits
    code = models.CharField(max_length=10, help_text="Numbers/characters after subject for the course")
    
    
    class Meta:
        # Subject and code together act as a primary key.
        unique_together = (('subject', 'code'),)
        
        # Order by subject first, then code in database
        ordering = ['subject', 'code']
        
    def __str__(self):
        """String representation of Course"""
        return self.subject + ' ' + self.code
    
class CourseOffering(models.Model):
    """Model representing an offering of a course in a given term."""
    
    # Course and term are both foreign keys.
    # Use RESTRICT to prevent courses and terms from being
    # deleted from foreign tables while this exists.
    course = models.ForeignKey('course', on_delete=models.RESTRICT)
    term = models.ForeignKey('term', on_delete=models.RESTRICT)
    
    class Meta:
        unique_together = (('course', 'term'),)
        
        # Order by course first, since users will probably
        # want to see the offerings for a specific course
        # rather than all the courses offered in a term.
        ordering = ['course', 'term']
        
    def __str__(self):
        return str(self.subject) + ' ' + str(self.term)

    
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
    