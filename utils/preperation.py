import datetime
import json
import pandas as pd
from dotenv import load_dotenv, dotenv_values
from utils.styles import RED, BLUE, GREEN, YELLOW, BG_WHITE, RESET

def date_creation():

    #today
    t = datetime.datetime.now()
    today = t.strftime("%d.%m.%Y")

    #print(today)

    #tomorrow
    t = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = t.strftime("%d.%m.%Y")

    #print(tomorrow)
    
    today_as_datetime = pd.to_datetime(today, dayfirst=True)
    tomorrow_as_datetime = pd.to_datetime(tomorrow, dayfirst=True)
    
    return today, tomorrow, today_as_datetime, tomorrow_as_datetime



def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)
    

def load_env_data() -> dict:
    load_dotenv("sensible.env",encoding="utf-8")  # Laden ins os.environ
    return dotenv_values("sensible.env",encoding="utf-8")  # Dictionary zurückgeben
    


 


def config_text(config_data,env_data):
    
    print("Sensible Daten: \n\n")
    print(f"{RED}Termino Benutzernamen{RESET}: {env_data['username_termino']} \n")
    print(f"{RED}Termino Passwort{RESET}: {env_data['password_termino']} \n")
    print(f"{BLUE}YAHOO-E-Mail-Adresse{RESET}: {env_data['mail']} \n")
    print(f"{BLUE}E-Mail Passwort{RESET}: {env_data['password_mail']} \n")
    print(f"{RED}Termino Benutzernamen{RESET}: {env_data['app_password_mail']} \n")
    
    
    print("\n\nWeitere Konfigurationen: \n\n")
    print(f"{YELLOW}Buchungsliste{RESET}: {config_data['booking_list']} \n")
    print(f"{YELLOW}Studienname{RESET}: {config_data['study_name']} \n")
    
    
    if config_data['actual_list_printing'] == 1:
        print("\nAktuelle Buchungsliste soll ausgegeben werden!")
    else:
        print("\nAktuelle Buchungsliste soll nicht ausgegeben werden!")
        
    if config_data['fist_mail_recieved_printing'] == 1:
        print("\nListe mit Personen welche die erste Mail erhalten haben soll ausgegeben werden!")
    else:
        print("\nListe mit Personen die erste Mail erhalten haben soll nicht ausgegeben werden!")
        
    if config_data['to_send_first_mail'] ==1:
        print("\n")
    else:
        print("\n")

    if config_data['implement_google'] ==1:
        print(f"\nSuper Cooles Feature zur Benachrichtigung der Versuchsleitung wird verwendet!"
              f"\nlets gooo!!!!! SIIIICKE SACHE"
              f"\n\n{GREEN}{BG_WHITE}google_spreadsheet url{RESET}: {GREEN}{BG_WHITE}{env_data['google_spreadsheet_url']}{RESET}"
              f"\n\nName des {YELLOW}Tabellenblattes{RESET} für die VL-Information: {YELLOW}{config_data['information']}{RESET}\n\n"
              )
    else:
        print("\n du verwendest das tolle feature nicht :( \n\n"
              )




def booking_list_preperation(actual_booking_list_csv, config_data):
    
    first_mail_file = "data/first_mail_sended_booking_list.csv"

    df = pd.read_csv(actual_booking_list_csv, sep=";",decimal=",") #Termino Buchungsliste
    
    
    date_prob = df['Date'].tolist()
    name_prob = df['Name'].tolist()
    email_prob = df['E-Mail'].tolist()

    def print_actual_bookings(x=2):
        if x==1:
            print("\n\n\n\n\nAktuelle Buchungen: \n\n",)
            for name, datum, email in zip(name_prob, date_prob, email_prob):
                print(f"   Name: {name} \n   Datum: {datum} \n   E-Mail: {email}\n\n")
        else:
           print("\n\nAktuelle Buchungsliste wird nicht ausgegeben.") 




    first_mail_sended = pd.read_csv(first_mail_file, sep=",",decimal=";") #Termino


    date_first_mail_sended=first_mail_sended['Date'].tolist()
    name_first_mail_sended=first_mail_sended['Name'].tolist()
    email_first_mail_sended=first_mail_sended['E-Mail'].tolist()


    def print_first_mail_sended(x=2):
        if x ==1:
            print("\n\n\n\n\nPersonen die erste Mail schon erhalten haben: \n\n",)
            for name, datum, email in zip(name_first_mail_sended, date_first_mail_sended, email_first_mail_sended):
                print(f"   Name: {name} \n   Datum: {datum} \n   E-Mail: {email}\n\n")
        else:
            print("\n\nListe mit Personen die erste Mail schon erhalten haben wird nicht ausgegeben.")
    
    print_actual_bookings(config_data['actual_list_printing'])
    print_first_mail_sended(config_data['fist_mail_recieved_printing'])
    
    
    to_send_name=[]
    to_send_mail=[]
    to_send_date=[] 

    for eintrag in range(0,len(email_prob)):
        drauen = 2
        for no in range(0,len(date_first_mail_sended)):
            if email_first_mail_sended[no] == email_prob[eintrag] and name_first_mail_sended[no] == name_prob[eintrag]:
                drauen-=1   
                
        if drauen >1:
            to_send_name.append(name_prob[eintrag])
            to_send_date.append(date_prob[eintrag])
            to_send_mail.append(email_prob[eintrag])  #zur Mailliste hinzufügen
            
            if email_prob[eintrag] not in email_first_mail_sended:
                date_first_mail_sended.append(date_prob[eintrag])
                name_first_mail_sended.append(name_prob[eintrag])
                email_first_mail_sended.append(email_prob[eintrag])  # zur first_email_sended Liste hinzufügen





    def print_to_send_first_mail(x=1):
        if x ==1:
            print("\n\n\n\n\nPersonen an welche die erste Mail gesendet wird: \n\n",)
            for name, datum, email in zip(to_send_name, to_send_date, to_send_mail):
                print(f"   Name: {name} \n   Datum: {datum} \n   E-Mail: {email}\n\n")
        else:
            print("\n\nListe mit Personen welche die erste Mail nun gesendet bekommen wird nicht ausgegeben.")


    print_to_send_first_mail(config_data['to_send_first_mail'])




    # first email sended liste ergänzen um die neuen namen

    first_mail_sended = {'Name': name_first_mail_sended, 'Date': date_first_mail_sended, 'E-Mail': email_first_mail_sended}
    first_mail_sended = pd.DataFrame(first_mail_sended)
    first_mail_sended.to_csv(first_mail_file)
    
    
    
    
    return date_prob, name_prob, email_prob, date_first_mail_sended, name_first_mail_sended, email_first_mail_sended, to_send_name, to_send_mail, to_send_date



def tomorrow_today_data(date_prob, name_prob, email_prob, tomorrow, today):
    
    tomorrow_name=[]
    tomorrow_email=[]
    tomorrow_date=[] 

    for eintrag in range (0,len(date_prob)):
        if date_prob[eintrag].split( ) [0]==tomorrow: # eintrag morgen ist
            tomorrow_name.append(name_prob[eintrag])
            tomorrow_email.append(email_prob[eintrag])
            tomorrow_date.append(date_prob[eintrag])
        else: continue
    
    tomorrow_time = []

    for termin1 in tomorrow_date:
        date1, time1 = termin1.split(" - ")
        tomorrow_time.append(time1)

    
    today_name=[]
    today_email=[]
    today_date=[] 

    for eintrag in range (0,len(date_prob)):
        if date_prob[eintrag].split( ) [0]==today: # eintrag heute ist
            today_name.append(name_prob[eintrag])
            today_email.append(email_prob[eintrag])
            today_date.append(date_prob[eintrag])
        else: continue
    
    return tomorrow_name, tomorrow_email, tomorrow_date, tomorrow_time, today_name, today_email, today_date



def get_ids_to_remove(df_termino, today_as_datetime, tomorrow_as_datetime, tomorrow_time):
    
    df_termino_used = df_termino

    df_termino_used['Date'] = pd.to_datetime(df_termino_used['Date'], format="%d.%m.%Y", errors='coerce')

    # Jetzt filtern
    df_till_today = df_termino_used[df_termino_used['Date'] <= today_as_datetime]
    df_tomorrow = df_termino_used[df_termino_used['Date'] == tomorrow_as_datetime]
    
    
    # Filtere df_tomorrow nach Time-Werten, die NICHT in tomorrow_time vorkommen
    df_tomorrow_filtered = df_tomorrow[~df_tomorrow['Time'].isin(tomorrow_time)]


    # Füge die gefilterten Einträge zu df_till_today hinzu
    df_till_today = pd.concat([df_till_today, df_tomorrow_filtered], ignore_index=True)

    # Optional: sortieren
    df_to_remove = df_till_today.sort_values(by=['Date', 'Time']).reset_index(drop=True)

    to_remove_ids = [sid + "-remove-button" for sid in df_to_remove['Short ID']]
    
    return to_remove_ids

