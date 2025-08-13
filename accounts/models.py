from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import CustomUserManager # <-- Add this import

class CustomUser(AbstractUser):
    # Remove username since we will use email as the username
    username = None
    
    # We use email as the unique identifier for login
    email = models.EmailField(unique=True, verbose_name="Gmail ID")
    
    # Set the email field as the USERNAME_FIELD
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # Fields prompted for when creating a superuser

    # Your custom fields
    USER_ROLES = [
        ('Student', 'Student'),
        ('Teacher', 'Teacher'),
        ('Admin', 'Admin'),
        ('Principal', 'Principal'),
    ]
    
    user_name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=10, choices=USER_ROLES)
    user_class = models.CharField(max_length=10, blank=True, null=True, verbose_name="Class")

    is_confirmed = models.BooleanField(default=False, verbose_name="Confirmed (for Staff)")
    payment_confirmed = models.BooleanField(default=False, verbose_name="Payment Confirmed (for Students)")

    subscription_plan = models.CharField(max_length=100, blank=True, null=True)
    subscription_date = models.DateField(blank=True, null=True)
    subscribed_till = models.DateField(blank=True, null=True)
    parent_phonepe = models.CharField(max_length=15, blank=True, null=True)

    security_question = models.CharField(max_length=255)
    security_answer = models.CharField(max_length=255)
    instructions = models.TextField(blank=True, null=True)
    instruction_reply = models.TextField(blank=True, null=True)
    instruction_status = models.CharField(max_length=20, blank=True, null=True)
    
    parent_phonepe = models.CharField(max_length=15, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True) # <-- Add this line
    salary_points = models.IntegerField(default=0)
    
    objects = CustomUserManager() # <-- Add this line

    def __str__(self):
        return self.email


class HomeworkQuestion(models.Model):
    question_class = models.CharField(max_length=10, verbose_name="Class")
    date = models.DateField()
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE) 
    subject = models.CharField(max_length=100)
    question = models.TextField()
    model_answer = models.TextField()
    due_date = models.DateField()

    def __str__(self):
        return self.question[:50]

class StudentAnswer(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    question = models.ForeignKey(HomeworkQuestion, on_delete=models.CASCADE)
    date = models.DateField()
    answer = models.TextField()
    marks = models.IntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    
    attempt_status = models.IntegerField(default=0)
    help_request = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Answer by {self.student.user_name} for question ID {self.question.id}"
