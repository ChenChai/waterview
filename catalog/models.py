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
        return self.subject + self.code
    
    
    
    
    
    
    