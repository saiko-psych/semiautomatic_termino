# loading all the needed data from the config and env file

import os
import json
from pathlib import Path
from utils.styles import RED, BLUE, BG_RED, GREEN, BG_WHITE, CYAN, RESET, DATA_INPUT_ASCI, OPTIONAL_INPUT_ASCI 


# declaring all functions

# 1. saving functions 

def save_env_file(env_vars, filename="sensible.env"):
    with open(filename, "w",encoding="utf-8") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print(f"{filename} gespeichert.")

def save_config_json(config, filename="config.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"{filename} gespeichert.")


# 2. input functions

def collect_all_inputs():
    
    print(DATA_INPUT_ASCI)
    
    print("\nBitte geben Sie die benötigten Konfigurationsdaten ein:\n")
    
    
    # Benutzer-Eingaben sammeln
    username_termino = input(f"Geben Sie Ihren {RED}Termino Benutzernamen{RESET} ein: ")
    print(f"\nIhr Termino Benutzername ist: {RED}", username_termino, f"{RESET}\n\n")

    password_termino = input(f"Geben Sie Ihr {RED}Termino Passwort{RESET} ein: ")
    print(f"\nIhr Termino Passwort ist: {RED}", password_termino, f"{RESET}\n\n")

    booking_list = input(f"Geben Sie den Namen Ihrer {BG_RED}Buchungsliste{RESET} ein: ")
    print(f"\nIhre Buchungsliste heißt: {BG_RED}", booking_list, f"{RESET}\n\n")

    mail = input(f"Geben Sie Ihre {BLUE} YAHOO-E-Mail-Adresse{RESET} ein: ")
    print(f"\nIhre E-Mail-Adresse ist: {BLUE}", mail, f"{RESET}\n\n")

    password_mail = input("Geben Sie Ihr Passwort für diese Yahoo-Mail ein: ")
    print("\nIhr Passwort für Yahoo-Mail ist: ", password_mail, "\n\n")

    app_password_mail = input("Geben Sie Ihr APP-Passwort für diese Yahoo-Mail ein: ")
    print("\nIhr APP-Passwort für Yahoo-Mail ist: ", app_password_mail, "\n\n")


    study_name = input("Geben Sie den Namen Ihrer Studie ein: (zB: Musiktheraphie Studie) ")
    print("\nDer Name Ihrer Studie lautet: ", study_name, "\n\n")
    
    
    
    # angeben ob ich die derzeitige Buchungsliste angezeigt haben will

    actual_list_printing = 3

    while actual_list_printing == 3:
        
        actual_list_printing = input("\n\nMöchtest du die alle aktuellen buchungen sehen? (ja/nein): ").strip().lower()

        
        if actual_list_printing in ["ja", "yes", "y", "j"]:
            
            print("Du hast 'Ja' gewählt!")
            actual_list_printing = 1
            
        elif actual_list_printing in ["nein", "no", "n", "noo"]:
            
            print("Du hast 'Nein' gewählt!")
            actual_list_printing =2
            
        else:
            print("Ungültige Eingabe. Bitte 'ja' oder 'nein' eingeben.")
            actual_list_printing = 3  # Wert zurücksetzen, um Schleife fortzusetzen


    #####

    to_send_first_mail = 3

    while to_send_first_mail == 3:
        
        to_send_first_mail = input("\n\nMöchtest du die Liste für Personen sehen an welche die erste Mail gesendet wird? (ja/nein): ").strip().lower()

        
        if to_send_first_mail in ["ja", "yes", "y", "j"]:
            
            print("Du hast 'Ja' gewählt!")
            to_send_first_mail = 1
            
        elif to_send_first_mail in ["nein", "no", "n", "noo"]:
            
            print("Du hast 'Nein' gewählt!")
            to_send_first_mail = 2
            
        else:
            print("Ungültige Eingabe. Bitte 'ja' oder 'nein' eingeben.")
            to_send_first_mail = 3  # Wert zurücksetzen, um Schleife fortzusetzen


    #####

    fist_mail_recieved_printing = 3

    while fist_mail_recieved_printing == 3:
        
        fist_mail_recieved_printing = input("\n\nMöchtest du die Liste für Personen sehen welche die erste Mail schon bekommen haben? (ja/nein): ").strip().lower()

        
        if fist_mail_recieved_printing in ["ja", "yes", "y", "j"]:
            
            print("Du hast 'Ja' gewählt!")
            fist_mail_recieved_printing = 1
            
        elif fist_mail_recieved_printing in ["nein", "no", "n", "noo"]:
            
            print("Du hast 'Nein' gewählt!")
            fist_mail_recieved_printing = 2
            
        else:
            print("Ungültige Eingabe. Bitte 'ja' oder 'nein' eingeben.")
            fist_mail_recieved_printing = 3  # Wert zurücksetzen, um Schleife fortzusetzen
            
            
            
    
    print(OPTIONAL_INPUT_ASCI)
    
    print(f"\n\nDiese Funktion erfordert ein {GREEN}{BG_WHITE}'GOOGLE SPREADSHEET'{RESET} in einem Verwendbaren Format! \n\nLink zu einer geeigneten Vorlage: \n{CYAN}https://docs.google.com/spreadsheets/d/1ivn2TBMxwdFAjkvgWJMQpW-AO22HK-uAYly7lF7eTMw/edit?gid=0#gid=0 {RESET}\n\n\n")
    implement_google = 3

    while implement_google ==3:
        google_input = input(f"{RESET}Möchtest du das supercoole Feature nutzen und die Versuchsleitung am Tag davor über den nächsten Tag informieren? (ja/nein) ")
        
        if google_input in ["ja", "yes", "y", "j"]:
            
            print(f"\n{RESET}NICE BRO")
            google_spreadsheet_url = input(f"\n\nBitte den {GREEN}{BG_WHITE}URL zu deinem google spreadsheet{RESET} einfügen: ")
            print(f"\n\n {RESET}dein {GREEN}{BG_WHITE}google shreadsheet url{RESET} ist: {GREEN}{BG_WHITE}", google_spreadsheet_url, f"{RESET}\n\n")
            information = input(f"\n\n Bitte den namen der spreadsheet seite eingeben wo {BLUE}{BG_WHITE}Informationen{RESET} über die Versuchsleitung steht eingeben: ")
            print(f"\n\n {RESET}der name deiner {BLUE}{BG_WHITE}informationsseite{RESET} ist: {BLUE}{BG_WHITE}", information, f"{RESET}\n\n")
            implement_google =1
            
        elif google_input in ["nein", "no", "n", "noo"]:
            
            print("\nDIESES FEATURE VERWENDEST DU ALSO NICHT :( PRETTY WHACK")
            implement_google = 2
            google_spreadsheet_url = None
            information = None
        
        else:
            print("Ungültige Eingabe. Bitte 'ja' oder 'nein' eingeben.")
            implement_google = 3  # Wert zurücksetzen, um Schleife fortzusetzen 
    
    
    # Daten in JSON-Datei speichern
    user_data = {
        "username_termino": username_termino,
        "password_termino": password_termino,
        "booking_list": booking_list,
        "mail": mail,
        "password_mail": password_mail,
        "app_password_mail": app_password_mail,
        "study_name": study_name,
        
        "actual_list_printing": actual_list_printing,
        "fist_mail_recieved_printing": fist_mail_recieved_printing,
        "to_send_first_mail": to_send_first_mail,
        "implement_google": implement_google,
        "google_spreadsheet_url": google_spreadsheet_url,
        "information": information
    }

    print("\nAlle Eingaben wurden erfasst! \n")
    
    
    return user_data

def split_data(data):
    env_keys = [
        "username_termino", "password_termino",
        "mail", "password_mail", "app_password_mail",
        "google_spreadsheet_url"
    ]
    config_keys = [
        "booking_list", "study_name",
        "actual_list_printing", "fist_mail_recieved_printing",
        "to_send_first_mail", "implement_google",
        "information"
        
    ]

    env_data = {k: data[k] for k in env_keys}
    config_data = {k: data[k] for k in config_keys}

    return env_data, config_data




def main():
    os.chdir(Path(__file__).parent)
    print("Konfiguration wird ausgeführt... \n\n\n")
    
    user_data = collect_all_inputs()
    env_data, config_data = split_data(user_data)
    
    save_env_file(env_data)
    save_config_json(config_data)
    
    
    print("\n\nKonfiguration abgeschlossen.")
    
    
if __name__ == "__main__":
    main()

