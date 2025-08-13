from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('answer/<int:question_id>/', views.answer_view, name='answer'),
    path('create_homework/', views.create_homework_view, name='create_homework'), # <-- Add this line
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.registration_view, name='register'),
    path('payment/<int:user_id>/', views.payment_view, name='payment'),
    path('forgot_password/', views.forgot_password_view, name='forgot_password'),
    path('confirm_student/<int:user_id>/', views.confirm_student_view, name='confirm_student'), # <-- Add this
    path('confirm_teacher/<int:user_id>/', views.confirm_teacher_view, name='confirm_teacher'), # <-- Add this
]
