# setup.py
import os
import subprocess
import sys
import json
from pathlib import Path



def install_requirements():
    """Install the required libraries via pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])





def create_data_folder():
    """Creates the 'data' folder if it doesn't already exist."""
    data_folder = Path("data")
    if not data_folder.exists():
        data_folder.mkdir()
        print("The 'data' folder has been created.")
    else:
        print("The 'data' folder already exists.")
    return data_folder

def create_templates_folder():
    """Creates the 'templates' folder if it doesn't already exist."""
    templates_folder = Path("templates")
    if not templates_folder.exists():
        templates_folder.mkdir()
        print("The 'templates' folder has been created.")
    else:
        print("The 'templates' folder already exists.")
    return templates_folder





def create_env_file():
    """Creates a .env file if it doesn't already exist."""
    env_file = "sensible.env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("# .env file for sensitive data \n")
            f.write("SECRET_KEY=your_secret_key_here\n")
            f.write("DATABASE_URL=your_database_url_here\n")
            print(f"The {env_file} file has been created.")
    else:
        print(f"{env_file} already exists.")




def create_config_json():
    """Creates an empty config.json file if it doesn't already exist."""
    config_file = "config.json"
    if not os.path.exists(config_file):
        user_data = {
            "username_termino": "",
            "password_termino": "",
            "booking_list": "",
            "mail": "",
            "password_mail": "",
            "app_password_mail": "",
            "study_name": "",
            "template_first_mail": "",
            "template_reminder_mail": ""
        }
        with open(config_file, "w") as f:
            json.dump(user_data, f, indent=4)
        print(f"The {config_file} file has been created.")
    else:
        print(f"{config_file} already exists.")





def create_first_email_template():
    """Creates the 'first_email.txt' template if it doesn't already exist."""
    templates_folder = Path("templates")
    templates_folder.mkdir(exist_ok=True)

    file_path = templates_folder / "first_email.txt"
    if not file_path.exists():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "Subject: Welcome to the Study!\n\n"
                "Hello $NAME,\n\n"
                "We are pleased that you are participating in our study $STUDYNAME!\n"
                "This is to confirm your booking for the appointment on $DATE at $TIME.\n\n"
                "If you have any questions, please contact $MAIL \n\n"
                "Best regards,\n"
                "Your Study Team\n"
            )
        print("The 'first_email.txt' file has been created.")
    else:
        print("The 'first_email.txt' file already exists.")





def create_reminder_template():
    """Creates the 'reminder.txt' template if it doesn't already exist."""
    templates_folder = Path("templates")
    templates_folder.mkdir(exist_ok=True)

    file_path = templates_folder / "reminder.txt"
    if not file_path.exists():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "Subject: Reminder of Your Appointment Tomorrow, $DATE at $TIME\n\n"
                "Hello $NAME,\n\n"
                "This is a friendly reminder of your appointment for the study $STUDYNAME "
                "on $DATE at $TIME.\n\n"
                "Please be on time. If you have any questions, feel free to contact us.\n\n"
                "If you have any questions, please contact $MAIL \n\n"
                "Best regards,\n"
                "Your Study Team\n"
            )
        print("The 'reminder.txt' file has been created.")
    else:
        print("The 'reminder.txt' file already exists.")



def create_csv_file(data_folder):
    """Creates a CSV file in the 'data' folder if it doesn't already exist."""
    csv_file = data_folder / "first_mail_sended_booking_list.csv"
    if not csv_file.exists():
        with open(csv_file, "w") as f:
            f.write(",Name,Date,Email\n")
        print(f"The {csv_file} file has been created.")
    else:
        print(f"{csv_file} already exists.")

        
        

def main():
    """
    This function runs the setup script for the study system.
    It performs the following tasks:
    1. Installs the required Python dependencies.
    2. Creates necessary configuration and environment files.
    3. Sets up data and template folders.
    4. Creates CSV files for tracking email sends and study bookings.
    5. Initializes email templates for the study communication.

    The function is meant to be run once during the initial setup of the system.

    Steps:
    - Install requirements from the 'requirements.txt' file.
    - Create the environment file ('sensible.env').
    - Create the config JSON file ('config.json').
    - Set up the 'data' and 'templates' directories.
    - Create necessary CSV files and email templates.

    After execution, the system will be ready for further use.
    """
    os.chdir(Path(__file__).parent)
    print("Running setup script...")
    install_requirements()
    create_env_file()
    create_config_json()
    data_folder = create_data_folder()
    templates_folder = create_templates_folder()
    create_csv_file(data_folder)
    create_first_email_template()
    create_reminder_template()
    print("Setup complete.")

if __name__ == "__main__":
    main()

