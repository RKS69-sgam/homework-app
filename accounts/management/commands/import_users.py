import gspread
import pandas as pd
from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from google.oauth2.service_account import Credentials
import hashlib

# --- IMPORTANT: UPDATE THIS VALUE ---
SERVICE_ACCOUNT_FILE = 'C:/Users/hp/Documents/HomeworkApp/epsbargawan-firebase-adminsdk-fbsvc-d6072fb00c.json'
# ------------------------------------

class Command(BaseCommand):
    help = 'Imports users from the specified Google Sheet into the CustomUser model'

    def handle(self, *args, **options):
        try:
            # Authenticate with Google Sheets
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
            client = gspread.authorize(creds)
            
            # Open the sheet and read the data
            sheet = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
            data = sheet.get_all_records()
            df = pd.DataFrame(data)

            self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(df)} rows from Google Sheet.'))

            for index, row in df.iterrows():
                email = row.get('Gmail ID', '').lower().strip()
                if not email:
                    continue

                # --- FIX: Changed 'gmail_id' to 'email' ---
                user, created = CustomUser.objects.get_or_create(
                    email=email,
                    defaults={
                        'user_name': row.get('User Name'),
                        'father_name': row.get('Father Name'),
                        'mobile_number': row.get('Mobile Number'),
                        'password': row.get('Password'), # Assumes this is a hash
                        'role': row.get('Role'),
                        'user_class': row.get('Class'),
                        'is_confirmed': True if row.get('Confirmed') == 'Yes' else False,
                        'payment_confirmed': True if row.get('Payment Confirmed') == 'Yes' else False,
                        'subscription_plan': row.get('Subscription Plan'),
                        'security_question': row.get('Security Question'),
                        'security_answer': row.get('Security Answer'),
                        'salary_points': int(row.get('Salary Points', 0) or 0)
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f'Successfully created user: {email}'))
                else:
                    self.stdout.write(self.style.WARNING(f'User already exists, skipping: {email}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))
