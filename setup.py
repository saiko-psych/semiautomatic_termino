# setup.py
import os
import subprocess
import sys
import json
from pathlib import Path



# zuerst mal die nötigen requirements insallieren

def install_requirements():
    """Installiere die erforderlichen Bibliotheken über pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


# danach die richtige ordnerstruktur anlegen

def create_data_folder():
    """Erstellt den Ordner 'data', falls er noch nicht existiert."""
    data_folder = Path("data")
    if not data_folder.exists():
        data_folder.mkdir()
        print("Der 'data'-Ordner wurde erstellt.")
    else:
        print("Der 'data'-Ordner existiert bereits.")
    return data_folder

def create_templates_folder():
    """Erstellt den Ordner 'templates', falls er noch nicht existiert."""
    templates_folder = Path("templates")
    if not templates_folder.exists():
        templates_folder.mkdir()
        print("Der 'templates'-Ordner wurde erstellt.")
    else:
        print("Der 'templates'-Ordner existiert bereits.")
    return templates_folder



# die files erstellen für config

def create_env_file():
    """Erstellt eine .env-Datei, falls sie noch nicht existiert."""
    env_file = "sensible.env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("# .env Datei für sensible Daten \n")
            f.write("SECRET_KEY=your_secret_key_here\n")
            f.write("DATABASE_URL=your_database_url_here\n")
            print(f"Die {env_file}-Datei wurde erstellt.")
    else:
        print(f"{env_file} existiert bereits.")

def create_config_json():
    """Erstellt eine leere config.json-Datei, falls sie noch nicht existiert."""
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
        print(f"Die {config_file}-Datei wurde erstellt.")
    else:
        print(f"{config_file} existiert bereits.")


# die template files erstellen

def create_first_email_template():
    """Erstellt das Template 'first_email.txt', falls es noch nicht existiert."""
    templates_folder = Path("templates")
    templates_folder.mkdir(exist_ok=True)

    file_path = templates_folder / "first_email.txt"
    if not file_path.exists():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "Betreff: Willkommen zur Studie!\n\n"
                "Hallo $NAME,,\n\n"
                "wir freuen uns, dass Sie an unserer Studie $STUDYNAME teilnehmen!\n"
                "Hiermit bestätigen wir Ihre Buchung für den Termin am $DATE um $TIME.\n\n"
                "Bei Fragen Melde dich bitte bei $MAIL \n\n"
                "Viele Grüße,\n"
                "Ihr Studienteam\n"
            )
        print("Die Datei 'first_email.txt' wurde erstellt.")
    else:
        print("Die Datei 'first_email.txt' existiert bereits.")


def create_reminder_template():
    """Erstellt das Template 'reminder.txt', falls es noch nicht existiert."""
    templates_folder = Path("templates")
    templates_folder.mkdir(exist_ok=True)

    file_path = templates_folder / "reminder.txt"
    if not file_path.exists():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "Betreff: Erinnerung an Ihren Termin morgen den $DATE um $TIME Uhr\n\n"
                "Hallo $NAME,\n\n"
                "dies ist eine freundliche Erinnerung an Ihren Termin für die Studie $STUDYNAME "
                "am $DATE um $TIME Uhr.\n\n"
                "Bitte seien Sie pünktlich. Bei Fragen können Sie uns jederzeit kontaktieren.\n\n"
                "Bei Fragen Melde dich bitte bei $MAIL \n\n"
                "Beste Grüße,\n"
                "Ihr Studienteam\n"
            )
        print("Die Datei 'reminder.txt' wurde erstellt.")
    else:
        print("Die Datei 'reminder.txt' existiert bereits.")


# die files erstellen für das main skript

def create_csv_file(data_folder):
    """Erstellt eine CSV-Datei im 'data'-Ordner, falls sie noch nicht existiert."""
    csv_file = data_folder / "first_mail_sended_booking_list.csv"
    if not csv_file.exists():
        with open(csv_file, "w") as f:
            f.write(",Name,Date,E-Mail\n")
        print(f"Die {csv_file}-Datei wurde erstellt.")
    else:
        print(f"{csv_file} existiert bereits.")
        
        

def main():
    os.chdir(Path(__file__).parent)
    print("Setup-Skript wird ausgeführt...")
    install_requirements()
    create_env_file()
    create_config_json()
    data_folder = create_data_folder()
    templates_folder = create_templates_folder()
    create_csv_file(data_folder)
    create_first_email_template()
    create_reminder_template()
    print("Setup abgeschlossen.")

if __name__ == "__main__":
    main()
