import time
import sys
import smtplib
import random
from string import Template
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText



def loading_animation(duration):
    # Diese Animation läuft für die angegebene Dauer
    end_time = time.time() + duration
    while time.time() < end_time:
        for char in ["|", "/", "-", "\\"]:
            sys.stdout.write(f"\rLade{char}... ")  # Zeigt das Ladezeichen
            sys.stdout.flush()
            time.sleep(0.2)  # Kurze Pause zwischen den Frames
    sys.stdout.write("\rFertig! \n")  # Am Ende die Animation stoppen



def send_email(msg, s):
    try:
        s.send_message(msg)
    except smtplib.SMTPDataError as e:
        print(f"Fehler beim Senden der E-Mail: {e}")
    except Exception as e:
        print(f"Allgemeiner Fehler: {e}")



# Funktion zum Einlesen einer Vorlage
def readTemplate(filename): 
    with open(filename, 'r', encoding='utf-8') as templateFile:
        templateFileNachricht = templateFile.read()
    return Template(templateFileNachricht)  # Rückgabe eines Template-Objekts 



def first_message(env_data, config_data, to_send_name, to_send_mail, to_send_date):
    
    first_message_Template = readTemplate('templates/first_email.txt')

    # Verbindung zum Yahoo SMTP-Server herstellen
    s = smtplib.SMTP_SSL('smtp.mail.yahoo.com', 465)

    s.login(env_data['mail'], env_data['app_password_mail'])

    
    for name1, mail1, termin1 in zip(to_send_name, to_send_mail, to_send_date):

        date1, time1 = termin1.split(" - ")
        
        msg = MIMEMultipart() 
        message = first_message_Template.substitute(NAME=name1.title(), DATE=date1.title(), TIME = time1.title() )
        
        
        msg['From']=env_data['mail']
        msg['To']=mail1
        msg['Subject']=f"Teilnahmebestätigung {config_data['study_name']} am {date1} um {time1} Uhr für {name1}"

        msg.attach(MIMEText(message, 'plain'))
        
        # Sende die E-Mail mit Fehlerbehandlung
        send_email(msg, s)
        del msg

        print(f"\n\nBestätigunsemail an {name1} für Termin am {date1} um {time1} Uhr wird versendet.\n\n")
        
        # Zufällige Wartezeit zwischen den E-Mails
        sleep_time = random.uniform(2, 10)  
        print(f"Warte {sleep_time:.2f} Sekunden...")
        time.sleep(sleep_time)

        # Ladeanimation während der Wartezeit
        loading_animation(sleep_time)
    
    print("\n\n\nAlle Personen haben nun die erste Bestätigungsmail bekommen. \n\nNeu verschickte Mails: ", len(to_send_mail), "\n\n\n")
    
    s.quit()
    

def reminder(env_data, config_data, tomorrow_name, tomorrow_email, tomorrow_date):
    
    reminder_Template = readTemplate('templates/reminder.txt')
    
    # Verbindung zum Yahoo SMTP-Server herstellen
    s = smtplib.SMTP_SSL('smtp.mail.yahoo.com', 465)

    s.login(env_data['mail'], env_data['app_password_mail'])

    
    for name1, mail1, termin1 in zip(tomorrow_name, tomorrow_email, tomorrow_date):

        date1, time1 = termin1.split(" - ")
        
        msg = MIMEMultipart() 
        message = reminder_Template.substitute(NAME=name1.title(), DATE=date1.title(), TIME = time1.title(), STUDYNAME = config_data['study_name'].title(), MAIL = env_data['mail'].title() )

        print(f"Erinnerungsmail wird an {name1} für morgen um {time1} Uhr gesendet!")

        msg['From']=env_data['mail']
        msg['To']=mail1
        msg['Subject'] = f"Terminerinnerung {config_data['study_name']} für Morgen {date1} um {time1} Uhr"

        msg.attach(MIMEText(message, 'plain'))
        
        s.send_message(msg)
        del msg

        # Zufällige Wartezeit zwischen den E-Mails, z.B. zwischen 10 und 15 Sekunden
        sleep_time = random.uniform(8, 15)  
        print(f"Warte {sleep_time:.2f} Sekunden...")
        # Ladeanimation während der Wartezeit
        loading_animation(sleep_time)
        time.sleep(sleep_time)

    print("\n\n Alle Erinnerungsmails für morgen wurden an die Proband:innen verschickt! \nMorgen kommen insgesamt", len(tomorrow_email), "Personen zur Studie.\n")
       
    s.quit()   



def vl_mail(env_data, config_data, name_vl, email_vl, time_vl, tomorrow_time, tomorrow_name, tomorrow_email, tomorrow):
    
    try:
        # Verbindung zum Yahoo SMTP-Server
        s = smtplib.SMTP_SSL('smtp.mail.yahoo.com', 465)
        s.login(env_data['mail'], env_data['app_password_mail'])
    except Exception as e:
        print(f" Fehler beim Login zum Mailserver: {e}")
        return

    
    for name1, mail1, time1 in zip(name_vl, email_vl, time_vl):

        # Zähle, wie viele Versuchspersonen an diesem Datum und dieser Uhrzeit kommen
        anzahl_personen = sum(
        1 for t1 in tomorrow_time if t1 == time1
        )       

        personen_info = [
           (n1, e1) for n1, e1, t1 in zip(tomorrow_name, tomorrow_email, tomorrow_time)
           if t1 == time1
        ]

        # Erstellen des Info-Strings mit den Personeninformationen
        personen_details = "\n".join([f"    - {name} - {email}" for name, email in personen_info])
    
        
        msg = MIMEMultipart() 
        message = (
            f"Hallo {name1},\n\n"
            f"du bist für morgen ({tomorrow}) um {time1} für eine Testung eingetragen!\n\n"
            f"Es sind für diesen Termin {anzahl_personen} Personen angemeldet.\n\n"
            f"Infos zu den Personen:\n{personen_details}\n"
        )
        
        print("\n\n", message)

        msg['From']=env_data['mail']
        msg['To']=mail1
        msg['Subject']="Studientestung morgen "+" "+ tomorrow + " um " + time1 +" Uhr"

        
        msg.attach(MIMEText(message, 'plain'))
        
        s.send_message(msg)
        del msg

        # Zufällige Wartezeit zwischen den E-Mails, z.B. zwischen 10 und 15 Sekunden
        sleep_time = random.uniform(5, 10)  
        print(f"Warte {sleep_time:.2f} Sekunden...")
        # Ladeanimation während der Wartezeit
        loading_animation(sleep_time)
        
        time.sleep(sleep_time)



    print("\n\n Die Versuchsleitung wurde kontaktiert!")    
    s.quit()
    
    

def termin_missing(env_data, config_data, differenz_termino):
    
    try:
        # Verbindung zum Yahoo SMTP-Server
        s = smtplib.SMTP_SSL('smtp.mail.yahoo.com', 465)
        s.login(env_data['mail'], env_data['app_password_mail'])
    except Exception as e:
        print(f" Fehler beim Login zum Mailserver: {e}")
        return




    msg = MIMEMultipart() 
    message = (
            f"Hallo Studienleitung,\n\n"
            f"es wurden Termine in Termino gefunden für welche sich im google spreadsheet ( {env_data['google_spreadsheet_url']} ) noch keine Versuchsleitung eingetragen hat\n\n"
            f"Bitte so schnell es geht dieses Problem beheben! \n\n"
            f"Bei diesen Terminen gibt es noch keine Versuchsleitung:\n{differenz_termino["datetime"]}\n"
        )
        
    print(message)

    msg['From']=env_data['mail']
    msg['To']=env_data['mail']
    msg['Subject']="ACHTUNG BEI TERMINO GIBT ES TERMINE OHNE VERSUCHSLEITUNG"
    
    msg.attach(MIMEText(message, 'plain'))
        
    s.send_message(msg)
    del msg

    print("Mail an sich selber wurde gesendet um das Problem von zu vielen Terminen auf Termino anzugehen!")    
    s.quit()
    
