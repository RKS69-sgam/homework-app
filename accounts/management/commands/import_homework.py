import gspread
import pandas as pd
from django.core.management.base import BaseCommand
from accounts.models import CustomUser, HomeworkQuestion, StudentAnswer
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- IMPORTANT: UPDATE THESE VALUES ---
HOMEWORK_SHEET_ID = '1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI'
ANSWERS_SHEET_ID = '1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0'
SERVICE_ACCOUNT_FILE = 'C:/Users/hp/Documents/HomeworkApp/epsbargawan-firebase-adminsdk-fbsvc-d6072fb00c.json'
# ------------------------------------

class Command(BaseCommand):
    help = 'Imports homework and answers from Google Sheets'

    def handle(self, *args, **options):
        try:
            # Authenticate and connect
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
            client = gspread.authorize(creds)

            # --- Import Homework Questions ---
            self.stdout.write("Importing homework questions...")
            sheet_homework = client.open_by_key(HOMEWORK_SHEET_ID).sheet1
            homework_data = sheet_homework.get_all_records()
            df_homework = pd.DataFrame(homework_data)

            for index, row in df_homework.iterrows():
                try:
                    teacher = CustomUser.objects.get(user_name=row['Uploaded By'], role__in=['Teacher', 'Admin', 'Principal'])
                    question_date = datetime.strptime(row['Date'], '%d-%m-%Y').date()
                    due_date = datetime.strptime(row['Due_Date'], '%d-%m-%Y').date() if row.get('Due_Date') else question_date + timedelta(days=1)

                    HomeworkQuestion.objects.get_or_create(
                        question=row['Question'],
                        date=question_date,
                        uploaded_by=teacher,
                        defaults={
                            'question_class': row['Class'],
                            'subject': row['Subject'],
                            'model_answer': row['Model_Answer'],
                            'due_date': due_date
                        }
                    )
                except CustomUser.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Skipping question, teacher not found: {row['Uploaded By']}"))
                    continue
            self.stdout.write(self.style.SUCCESS('Homework questions imported successfully.'))

            # --- Import Student Answers ---
            self.stdout.write("Importing student answers...")
            sheet_answers = client.open_by_key(ANSWERS_SHEET_ID).sheet1
            answers_data = sheet_answers.get_all_records()
            df_answers = pd.DataFrame(answers_data)

            for index, row in df_answers.iterrows():
                try:
                    # --- FIX: Changed 'gmail_id' to 'email' ---
                    student = CustomUser.objects.get(email=row['Student Gmail'], role='Student')
                    question = HomeworkQuestion.objects.get(question=row['Question'], date=datetime.strptime(row['Date'], '%d-%m-%Y').date())

                    StudentAnswer.objects.get_or_create(
                        student=student,
                        question=question,
                        defaults={
                            'date': datetime.strptime(row['Date'], '%d-%m-%Y').date(),
                            'answer': row['Answer'],
                            'marks': int(row['Marks']) if row.get('Marks') else None,
                            'remarks': row['Remarks'],
                            'attempt_status': int(row.get('Attempt_Status', 0) or 0)
                        }
                    )
                except CustomUser.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Skipping answer, student not found: {row['Student Gmail']}"))
                    continue
                except HomeworkQuestion.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Skipping answer, question not found: {row['Question']}"))
                    continue
            self.stdout.write(self.style.SUCCESS('Student answers imported successfully.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))
