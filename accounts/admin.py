from django.contrib import admin
from .models import CustomUser, HomeworkQuestion, StudentAnswer # Add new models

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(HomeworkQuestion) # <-- Add this line
admin.site.register(StudentAnswer)  # <-- Add this line
