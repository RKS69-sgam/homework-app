from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CustomUser, HomeworkQuestion, StudentAnswer
import hashlib
import json
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Avg, Count
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# --- Password Hashing Functions ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

# --- Auto-Grading Utility Functions ---
def get_text_similarity(text1, text2):
    try:
        if not text1 or not text2:
            return 0.0
        vectorizer = TfidfVectorizer().fit_transform([text1, text2])
        return cosine_similarity(vectorizer)[0, 1] * 100
    except:
        return 0.0

def get_grade_from_similarity(percentage):
    if percentage >= 95: return 5  # Outstanding
    elif percentage >= 80: return 4  # Very Good
    elif percentage >= 60: return 3  # Good
    elif percentage >= 40: return 2  # Average
    else: return 1  # Needs Improvement

# --- Login View ---
def login_view(request):
    if request.method == 'POST':
        gmail = request.POST.get('gmail').lower().strip()
        password = request.POST.get('password')
        try:
            user = CustomUser.objects.get(email=gmail)
            if check_hashes(password, user.password):
                is_active = False
                if user.role == 'Student' and user.payment_confirmed:
                    is_active = True
                elif user.role != 'Student' and user.is_confirmed:
                    is_active = True
                if is_active:
                    login(request, user)
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Your account is not active. Please wait for confirmation.')
            else:
                messages.error(request, 'Incorrect Gmail ID or Password.')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Incorrect Gmail ID or Password.')
    return render(request, 'accounts/login.html')

# --- Dashboard View (Complete for all roles) ---
@login_required(login_url='/login/')
def dashboard_view(request):
    user = request.user
    role = user.role.lower()
    template_name = f'accounts/{role}_dashboard.html'
    context = {'user_name': user.user_name}

    if role == 'admin':
        # --- Admin Data ---
        context['unconfirmed_students'] = CustomUser.objects.filter(role='Student', payment_confirmed=False)
        context['unconfirmed_teachers'] = CustomUser.objects.filter(role='Teacher', is_confirmed=False)
    

    elif role == 'student':
        # --- Student Data ---
        all_homework = HomeworkQuestion.objects.filter(question_class=user.user_class)
        all_student_answers = StudentAnswer.objects.filter(student=user)
        
        # Performance Overview Data
        graded_answers = all_student_answers.filter(marks__isnull=False)
        total_assigned = all_homework.count()
        total_completed = graded_answers.count()
        context['total_assigned'] = total_assigned
        context['total_completed'] = total_completed
        context['total_pending'] = total_assigned - total_completed
        context['average_score'] = graded_answers.aggregate(Avg('marks'))['marks__avg'] or 0.0

        # Pending Homework Logic (Corrected)
        answered_q_ids = graded_answers.values_list('question_id', flat=True)
        pending_homework_qs = all_homework.exclude(id__in=answered_q_ids)
        
        pending_homework_with_details = []
        for hw in pending_homework_qs:
            answer_with_remark = all_student_answers.filter(question=hw, marks__isnull=True).first()
            if answer_with_remark:
                hw.previous_answer = answer_with_remark.answer
                hw.remarks = answer_with_remark.remarks
            pending_homework_with_details.append(hw)
        context['pending_homework'] = pending_homework_with_details
        
        # Revision Zone (Good, Very Good & Outstanding)
        context['revision_answers'] = graded_answers.filter(marks__gte=3).order_by('-date')
        
        # Chart Data
        context['chart_data'] = graded_answers.values('question__subject').annotate(average_marks=Avg('marks')).order_by('question__subject')
        context['growth_chart_data'] = list(graded_answers.order_by('date').values('date', 'marks'))
        
        # Leaderboard Data
        class_students = CustomUser.objects.filter(user_class=user.user_class, role='Student')
        leaderboard_data = (
            StudentAnswer.objects.filter(student__in=class_students, marks__isnull=False)
            .values('student__user_name')
            .annotate(average_marks=Avg('marks'))
            .order_by('-average_marks')
        )
        ranked_leaderboard = [{'rank': i + 1, **entry} for i, entry in enumerate(leaderboard_data)]
        context['top_3_students'] = ranked_leaderboard[:3]
        context['my_rank_info'] = next((item for item in ranked_leaderboard if item['student__user_name'] == user.user_name), None)

    elif role == 'teacher':
        # --- Teacher Data Calculation ---
        
        view_class = request.GET.get('view_class')
        view_subject = request.GET.get('view_subject')

        if view_class and view_subject:
            # --- Detail View: Sirf chune gaye sawaal dikhayein ---
            context['is_detail_view'] = True
            selected_questions = HomeworkQuestion.objects.filter(
                uploaded_by=user,
                date=date.today(),
                question_class=view_class,
                subject=view_subject
            )
            context['selected_questions'] = selected_questions
            context['detail_info'] = {'class': view_class, 'subject': view_subject}
        else:
            # --- Normal View: Sabhi reports aur summary dikhayein ---
            context['is_detail_view'] = False
            
            # 1. Top Metrics
            all_teachers = CustomUser.objects.filter(role='Teacher').order_by('-salary_points')
            my_rank = "N/A"
            for i, teacher in enumerate(all_teachers):
                if teacher.id == user.id:
                    my_rank = i + 1
                    break
            
            context['teacher_stats'] = {
                'salary_points': user.salary_points,
                'total_questions': HomeworkQuestion.objects.filter(uploaded_by=user).count(),
                'rank': my_rank
            }
            context['all_teachers_ranked'] = all_teachers

            # 2. Today's Homework Summary
            todays_homework = HomeworkQuestion.objects.filter(uploaded_by=user, date=date.today())
            context['todays_homework'] = todays_homework
            
            # 3. Report Metrics
            all_graded_answers = StudentAnswer.objects.filter(marks__isnull=False)
            all_students = CustomUser.objects.filter(role='Student')
            
            context['total_students'] = all_students.count()
            context['total_answers_submitted'] = StudentAnswer.objects.count()
            
            # Overall Top 3 Students
            overall_performance = all_graded_answers.values('student__user_name', 'student__user_class').annotate(average_marks=Avg('marks')).order_by('-average_marks')
            context['overall_top_3'] = list(overall_performance[:3])

            # Class-wise Top 3 Students
            classwise_performance = all_graded_answers.values('student__user_name', 'student__user_class').annotate(average_marks=Avg('marks')).order_by('student__user_class', '-average_marks')
            
            top_by_class = {}
            for record in classwise_performance:
                class_name = record['student__user_class']
                if class_name not in top_by_class:
                    top_by_class[class_name] = []
                if len(top_by_class[class_name]) < 3:
                    top_by_class[class_name].append(record)
            context['classwise_top_3'] = top_by_class
            
    elif role == 'principal':
        # --- Principal Data Calculation ---
    
        # 1. Top Metrics
        all_users = CustomUser.objects.all()
        all_teachers = all_users.filter(role='Teacher')
        all_students = all_users.filter(role='Student')
    
        context['total_students'] = all_students.count()
        context['total_teachers'] = all_teachers.count()
        context['total_questions_created'] = HomeworkQuestion.objects.count()

        # 2. Today's Teacher Activity Report
        today = date.today()
        todays_homework = HomeworkQuestion.objects.filter(date=today)
        questions_created_today = (
            todays_homework.values('uploaded_by__user_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        context['questions_created_today'] = questions_created_today

        # --- NEW: Live School Analytics ---
        all_graded_answers = StudentAnswer.objects.filter(marks__isnull=False)

        # Subject-wise Performance
        subject_performance = (
            all_graded_answers.values('question__subject')
            .annotate(average_marks=Avg('marks'))
            .order_by('-average_marks')
        )
        context['subject_performance'] = subject_performance
    
        # Class-wise Comparison
        class_performance = (
            all_graded_answers.values('student__user_class')
            .annotate(average_marks=Avg('marks'))
            .order_by('-average_marks')
        )
        context['class_performance'] = class_performance
        # --- END NEW ---


    elif role == 'admin':
        # --- Admin Data ---
        context['unconfirmed_students'] = CustomUser.objects.filter(role='Student', payment_confirmed=False)
        context['unconfirmed_teachers'] = CustomUser.objects.filter(role='Teacher', is_confirmed=False)

    return render(request, template_name, context)

# --- Answer View ---
@login_required(login_url='/login/')
def answer_view(request, question_id):
    try:
        question = HomeworkQuestion.objects.get(id=question_id)
    except HomeworkQuestion.DoesNotExist:
        messages.error(request, "This question does not exist.")
        return redirect('dashboard')

    # Find the previous attempt if it exists
    previous_answer_obj = StudentAnswer.objects.filter(
        student=request.user, 
        question=question, 
        marks__isnull=True
    ).first()
    previous_answer_text = previous_answer_obj.answer if previous_answer_obj else ""

    # This part handles the form submission
    if request.method == 'POST':
        answer_text = request.POST.get('student_answer')
        
        if not answer_text:
            messages.error(request, "Answer cannot be empty.")
            return redirect('dashboard')

        # Auto-grade the answer by comparing with the model answer
        similarity = get_text_similarity(answer_text, question.model_answer)
        grade_score = get_grade_from_similarity(similarity)

        # If this was a resubmission, delete the old attempt to replace it
        if previous_answer_obj:
            previous_answer_obj.delete()

        # Save the new attempt based on the grade
        if grade_score >= 3: # Good, Very Good, or Outstanding
            remark = "Good! Try for better performance next time." if grade_score == 3 else f"Auto-Graded: Excellent! ({similarity:.2f}%)"
            StudentAnswer.objects.create(
                student=request.user, question=question, date=timezone.now().date(),
                answer=answer_text, marks=grade_score, remarks=remark
            )
            messages.success(request, f"Good work! Your answer was {similarity:.2f}% correct and has been saved.")
        else: # Needs Improvement or Average (auto-return)
            remark = f"Auto-Remark: Your answer was {similarity:.2f}% correct. Please review and improve it."
            StudentAnswer.objects.create(
                student=request.user, question=question, date=timezone.now().date(),
                answer=answer_text, marks=None, remarks=remark
            )
            messages.warning(
                request,
                f"Your answer was {similarity:.2f}% correct. Please review the auto-remark and resubmit.",
                extra_tags=f"question_{question.id}"
            )
        
        return redirect('dashboard')
    
    # This part handles showing the page initially
    page_data_for_js = json.dumps({
        'questionText': question.question,
        'modelAnswerText': question.model_answer,
        'subject': question.subject
    })
    
    word_count = len(question.model_answer.split())
    timer_duration = max(10, word_count) # 1 second per word, min 10 seconds
    
    context = {
        'question': question,
        'timer_duration': timer_duration,
        'previous_answer': previous_answer_text,
        'page_data_json': page_data_for_js
    }
    return render(request, 'accounts/answer_page.html', context)

# --- FINAL CREATE HOMEWORK VIEW ---
@login_required(login_url='/login/')
def create_homework_view(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        question_class = request.POST.get('question_class')
        
        # --- YEH CHECK ZAROORI HAI ---
        if subject == "---Select Subject---" or question_class == "---Select Class---":
            messages.error(request, "Please select a valid subject and class.")
            # Form ko dobara data ke saath render karen
            context = {
                'classes': ["---Select Class---"] + [f"{i}th" for i in range(5, 13)],
                'subjects': ["---Select Subject---", "Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Physics", "Chemistry", "Biology", "Advance Classes"]
            }
            return render(request, 'accounts/create_homework.html', context)
        # --------------------------------

        question_text = request.POST.get('question')
        model_answer_text = request.POST.get('model_answer')
        
        HomeworkQuestion.objects.create(
            question_class=question_class,
            date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=1),
            uploaded_by=request.user,
            subject=subject,
            question=question_text,
            model_answer=model_answer_text
        )
        messages.success(request, 'New homework assignment has been created successfully!')
        return redirect('dashboard')
    
    # Dropdowns ke liye data
    context = {
        'classes': ["---Select Class---"] + [f"{i}th" for i in range(5, 13)],
        'subjects': ["---Select Subject---", "Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Physics", "Chemistry", "Biology", "Advance Classes"]
    }
    return render(request, 'accounts/create_homework.html', context)

def registration_view(request):
    if request.method == 'POST':
        # --- Step 1: Get all data from the form ---
        user_name = request.POST.get('user_name')
        email = request.POST.get('email').lower().strip()
        mobile_number = request.POST.get('mobile_number')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        security_question = request.POST.get('security_question')
        security_answer = request.POST.get('security_answer').lower().strip()
        role = request.POST.get('role')
        
        # --- Step 2: Validate the data ---
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif CustomUser.objects.filter(email=email).exists():
            messages.error(request, "A user with this email already exists.")
        else:
            # --- Step 3: Create the new user object ---
            user = CustomUser(
                user_name=user_name,
                email=email,
                password=make_hashes(password),
                mobile_number=mobile_number,
                security_question=security_question,
                security_answer=security_answer,
                role=role
            )
            
            # Add student-specific or teacher-specific details
            if role == 'Student':
                user.father_name = request.POST.get('father_name')
                user.user_class = request.POST.get('user_class')
                user.subscription_plan = request.POST.get('subscription_plan')
                user.parent_phonepe = request.POST.get('parent_phonepe')
            else: # Teacher or Principal
                user.is_confirmed = False # Must be confirmed by Admin

            user.save() # Save the user to the database

            # --- Step 4: Redirect based on role ---
            if role == 'Student':
                return redirect('payment', user_id=user.id)
            else:
                messages.success(request, f"{role} registered successfully! Please wait for admin approval.")
                return redirect('login')
    
    # This shows the blank form on the first visit
    return render(request, 'accounts/registration.html')
# --- NAYA PAYMENT VIEW ---
def payment_view(request, user_id):
    try:
        user_to_confirm = CustomUser.objects.get(id=user_id, role='Student')
    except CustomUser.DoesNotExist:
        messages.error(request, "Invalid user for payment.")
        return redirect('register')

    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        if transaction_id:
            user_to_confirm.transaction_id = transaction_id
            user_to_confirm.save()
            messages.success(request, "Your payment confirmation has been sent to the admin. Your account will be activated within 24 hours.")
            return redirect('login')
        else:
            messages.error(request, "Please enter the Transaction ID or your Parent's PhonePe number.")

    context = {
        'user_to_confirm': user_to_confirm,
        'upi_id': '9685840429@pnb' # Aapka UPI ID
    }
    return render(request, 'accounts/payment.html', context)

def forgot_password_view(request):
    if request.method == 'POST':
        # This part handles the form submission
        gmail = request.POST.get('gmail', '').lower().strip()
        security_answer = request.POST.get('security_answer', '').lower().strip()
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        try:
            user = CustomUser.objects.get(email=gmail)

            if security_answer != user.security_answer:
                messages.error(request, "Incorrect security answer.")
            elif new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
            else:
                # Success: Hash and save the new password
                user.password = make_hashes(new_password)
                user.save()
                messages.success(request, "Your password has been reset successfully. Please log in.")
                return redirect('login')

        except CustomUser.DoesNotExist:
            messages.error(request, "This email is not registered.")

    # This part just shows the page
    return render(request, 'accounts/forgot_password.html')

@login_required(login_url='/login/')
def confirm_student_view(request, user_id):
    if request.user.role != 'Admin':
        return redirect('dashboard')
    
    try:
        student = CustomUser.objects.get(id=user_id, role='Student')
        
        # --- FIX: Add a safety check for the subscription plan ---
        duration = 30 # Default to 30 days if plan is missing
        if student.subscription_plan: # Check if the plan is not empty
            if "6 months" in student.subscription_plan:
                duration = 182
            elif "1 year" in student.subscription_plan:
                duration = 365
        # ----------------------------------------------------
            
        student.payment_confirmed = True
        student.subscription_date = date.today()
        student.subscribed_till = date.today() + timedelta(days=duration)
        student.save()
        messages.success(request, f"{student.user_name}'s account has been activated.")
    
    except CustomUser.DoesNotExist:
        messages.error(request, "Student not found.")
    
    return redirect('dashboard')

# --- NEW VIEW TO CONFIRM TEACHERS ---
@login_required(login_url='/login/')
def confirm_teacher_view(request, user_id):
    if request.user.role != 'Admin':
        return redirect('dashboard')
        
    try:
        teacher = CustomUser.objects.get(id=user_id, role__in=['Teacher', 'Principal'])
        teacher.is_confirmed = True
        teacher.save()
        messages.success(request, f"{teacher.user_name}'s account has been activated.")
    except CustomUser.DoesNotExist:
        messages.error(request, "Teacher or Principal not found.")

    return redirect('dashboard')

# --- Logout View ---
def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')
