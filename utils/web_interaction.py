
import requests
import re

import pandas as pd

import time
import random
import os

from bs4 import BeautifulSoup  
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options





def termino_antibot_key():
    
    max_try = 20
    nr_try = 0
    antibot_key = "" 

    while nr_try <= max_try and len(antibot_key) < 1:
        nr_try += 1
        print(f"Fetching antibot_key try Nr: {nr_try}\n\n")

        # Verwenden des Service-Objekts, um den Chromedriver zu starten
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)

        # Öffne die Login-Seite
        driver.get("https://www.termino.gv.at/meet/de/user")

        sleep_time = random.uniform(3, 12)  
        #print(f"Warte {sleep_time:.2f} Sekunden...")
        time.sleep(sleep_time)

        try:
            # Extrahiere den antibot_key, der möglicherweise durch JavaScript gesetzt wurde
            antibot_key = driver.find_element(By.NAME, "antibot_key").get_attribute("value")
            sleep_time = random.uniform(2, 5)  
            #print(f"Warte {sleep_time:.2f} Sekunden...")
            time.sleep(sleep_time)

        except Exception as e:
            print(f"Fehler beim Abrufen des antibot_key: {e}")
        
        # Schließe den WebDriver
        driver.quit()
        
        #print("Antibot Key:", antibot_key, "\n\n")
        
    return antibot_key






def session():
    
    # Erstelle eine Session, um Cookies zu speichern -> THIS IS ESSENTIAL -> ALL OTHERS USE THIS SESSIOn
    session_id = requests.Session()

    return session_id



    
    



def termino_login(env_data, antibot_key, session_id):
    
    # URL für den Login
    login_url = "https://www.termino.gv.at/meet/de/user"  

    # Erstelle dann das login_data mit dem richtigen antibot_key
    login_data = {
        "name": env_data['username_termino'],  
        "pass": env_data['password_termino'],           
        "form_build_id": "form-IfujXxcz1-yoPlksIZ8TE_3zcwBHhodq0AAOwe5BZzk", # es kann sein das dies noch probleme bereitet mal
        "form_id": "user_login",
        "antibot_key": antibot_key,
        "op": "Login"
    }
    
    
    # 1. Sende eine POST-Anfrage zum Login
    response = session_id.post(login_url, data=login_data)

    print(">>> Login-Request gesendet!\n\n")

    # 2. Prüfe die Antwort des Servers
    if response.status_code != 200:
        print(f"⚠️ Fehler: Server hat Statuscode {response.status_code} zurückgegeben!")
        print("Mögliche Ursachen: URL falsch, Serverproblem, zu viele Anfragen geblockt.")
        
    elif "nicht akzeptiert" in response.text or "Haben Sie Ihr Passwort vergessen?" in response.text:
        print("❌ Die angegebenen Anmeldedaten stimmen nicht!")
        print("Überprüfe deine Anmeldedaten!")
        
    elif response.url == login_url:
        print("🚨 Login fehlgeschlagen! Die URL ist immer noch die Login-Seite.\n\n")
        print("Das bedeutet, dass der Server uns nicht eingeloggt hat.\n\n")
        print("Mögliche Ursachen: Falscher Benutzername/Passwort oder fehlende zusätzliche Parameter.\n\n")

    elif "Ansicht" in response.text or "Verlauf" in response.text:
        kekse = session_id.cookies.get_dict()
        # Nach dem Login die Cookies anzeigen
        print("cookies nach login = ", kekse, "\n")
        print("✅ Login erfolgreich!\n\n")
        logged_url = response.url
        print(f"Aktuelle URL nach Login: {logged_url}")

    else:
        print("❓ Unerwartete Antwort erhalten.\n\n")
        print("Hier sind die ersten 500 Zeichen der Antwort, um zu sehen, was los ist:\n")
        print(response.text[:500])

    return logged_url, kekse


def bookinglist_url(session_id, logged_url):
    
    r = session_id.get(logged_url)

    # Angenommen, `r.text` enthält den HTML-Text
    text = r.text  

    # Regex zum Finden der Buchungslisten-URL
    match = re.search(r'<a href="(https://www\.termino\.gv\.at/meet/de/user/\d+/mybookings)"', text)

    if match:
        buchungslisten_url = match.group(1)
        print("Gefundene Buchungslisten URL:", buchungslisten_url, "\n\n")
    else:
        print("Es konnte kein URL für die Buchungslisten gefunden werden... \n\n")
        
    return buchungslisten_url
    
    

def get_buchungsliste_nummer(session_id, buchungslisten_url, config_data):

    r = session_id.get(buchungslisten_url)

    # Angenommen, `r.text` enthält den HTML-Text
    booking_text = r.text 


    # Regex-Muster zum Finden der Nummer VOR dem angegebenen Namen
    pattern = rf'<a href="/meet/de/b/[a-f0-9]+-(\d+)">{config_data['booking_list']}</a>'

    # Suche durchführen
    match = re.search(pattern, booking_text)


    if match:
        buchungsliste_nummer = match.group(1)
        print("Gefundene Nummer:", buchungsliste_nummer, "\nBuchungsliste gefunden :D\n\n")
    else:
        print(f"\n\nKeine Nummer für Buchungsliste {config_data['booking_list']} gefunden. \n\nAnscheinend existiert keine Buchungsliste mit diesen Namen!")
        
        option = 3
        # Möglichkeit, einen neuen Namen einzugeben oder das Programm zu beenden
        while option == 3: 
            answer = input("\n\nMöchtest du einen anderen Namen für die Buchungsliste eingeben? (ja/nein): ").lower()

            
            if answer in ["ja", "yes", "y", "j"]:
                
                booking_list_new = input("\nBitte gib einen neuen Namen für die Buchungsliste ein: ")
                
                # Regex-Muster zum Finden der Nummer VOR dem angegebenen Namen
                pattern_new = rf'<a href="/meet/de/b/[a-f0-9]+-(\d+)">{booking_list_new}</a>'

                # Suche mit dem neuen Namen
                match = re.search(pattern_new, booking_text)

                if match:
                    buchungsliste_nummer = match.group(1)
                    print(f"Gefundene Nummer: {buchungsliste_nummer}\nBuchungsliste gefunden :D\n\n")
                    option = 1
                    
                    
                    
                else:
                    print(f"Keine Nummer für Buchungsliste '{booking_list_new}' gefunden.\n\n")
                    option = 3
                
                
            elif answer in ["nein", "no", "n", "noo"]:
                
                print("Du hast 'Nein' gewählt! \nDas Programm wird nun beendet!\n\n")
                option =2
                
            else:
                print("Ungültige Eingabe. Bitte 'ja' oder 'nein' eingeben.\n\n")
                option = 3  # Wert zurücksetzen, um Schleife fortzusetzen
    
    
    return buchungsliste_nummer
        


def termino_csv_download(session_id, config_data, buchungsliste_nummer):
    
    # URL für den CSV-Download zusammenstellen
    download_url = f"https://www.termino.gv.at/meet/de/node/{buchungsliste_nummer}/export"

    # Der Pfad, unter dem die CSV-Datei gespeichert werden soll
    actual_booking_list_csv = os.path.join("data",f"{config_data['booking_list']}_booking_list.csv")



    # Datei herunterladen
    csv_response = session_id.get(download_url)
    if csv_response.status_code == 200:
        with open(actual_booking_list_csv, "wb") as file:
            file.write(csv_response.content)
        print(f"CSV-Datei {config_data['booking_list']} wurde erfolgreich heruntergeladen und unter {actual_booking_list_csv} gespeichert\n\n")
    else:
        print(f"Fehler beim Herunterladen der CSV-Datei. {csv_response.status_code}")
        
    
    return actual_booking_list_csv
        
        

def termino_bookings(session_id, editing_url):
    
    r = session_id.get(editing_url)
    
    
    editing_text = r.text 
    
    soup = BeautifulSoup(editing_text, "html.parser")


    time_pattern = re.compile(r"^\d{2}:\d{2}$")
    

    inputs = soup.find_all("input", {"id": lambda x: x and "edit-field-flagcollection" in x})
    

    matching_inputs = [inp for inp in inputs if time_pattern.match(inp.get("value", ""))]
    
    
    short_ids = []
    for t in matching_inputs:
        full_id = t["id"]
        parts = full_id.split("-")
        short_id = "-".join(parts[:5])  # z.B. edit-field-flagcollection-und-29
        short_ids.append(short_id)
    
    
    numbers = []
    for t in matching_inputs:
        full_id = t["id"]
        parts = full_id.split("-")
        if len(parts) >= 5:
            number = parts[4]  # Das ist die Nummer nach 'und'
            numbers.append(number)
    
    
    date_suffix = "-field-optiondate-und-0-value-datepicker-popup-0"
    

    date_ids = [short_id + date_suffix for short_id in short_ids]
    

    date_values = []
    for date_id in date_ids:
        date_input = soup.find("input", {"id": date_id})
        if date_input:
            date_values.append(date_input.get("value", None))
        else:
            date_values.append(None)
    
    
    data = []
    for i in range(len(matching_inputs)):
        data.append({
            "Short ID": short_ids[i],
            "Place": numbers[i],
            "Time": matching_inputs[i]["value"],
            "Date": date_values[i]
        })
    
    # In ein DataFrame umwandeln
    df_termino = pd.DataFrame(data)

    return df_termino
    
   


def id_to_remove(buttons_list,removed_ids):
    
    
    removed_button_id = buttons_list.pop(0)
    print(f"Zu entfernende Button-ID: {removed_button_id}")
    
    removed_index = int(removed_button_id.split('-')[4])
    print(f"Entfernter Index: {removed_index}")
    
   
    updated_buttons = []


    for i, button in enumerate(buttons_list):
        button_index = int(button.split('-')[4])  # Holen des Index der aktuellen ID

        # Ignoriere das entfernte Element
        if button_index == removed_index:
            continue  
        if button_index > removed_index:
            new_index = button_index - 1
            updated_button = button.replace(f"-{button_index}-", f"-{new_index}-")
        else:
            updated_button = button

        if removed_ids == 0:
            updated_button += "--" + str(removed_ids + 2)
        else:
            updated_button = re.sub(r'\d+$', str(removed_ids + 2), updated_button)
        
        updated_buttons.append(updated_button)
        
    removed_ids = removed_ids +1
    
    return removed_button_id, updated_buttons, removed_ids


def remove_all_buttons(driver, buttons_list):
    removed_ids = 0

    while buttons_list:
        removed_button_id, buttons_list, removed_ids = id_to_remove(buttons_list, removed_ids)

        try:
            remove_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, removed_button_id))
            )
            remove_button.click()
            print(f"Button mit ID '{removed_button_id}' wurde geklickt.")
        except Exception as e:
            print(f"Fehler beim Klicken des Buttons '{removed_button_id}': {e}")
            break

        sleep_time = random.uniform(2, 10)
        print(f"Warte {sleep_time:.2f} Sekunden...")
        time.sleep(sleep_time)

    print("Alle Buttons entfernt.")
    

def deleting_bookings(kekse, editing_url, to_remove_ids, today):
    
    # Umwandeln des Cookies in das von Selenium erwartete Format
    cookies = [{'name': key, 'value': value, 'domain': '.termino.gv.at', 'path': '/'} for key, value in kekse.items()]

    # Verwende den WebDriverManager, um den ChromeDriver zu starten
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    # URL der Seite öffnen (achte darauf, dass du dich zuerst auf der Seite befindest)
    driver.get(editing_url)

    # Warte kurz, damit die Seite geladen wird
    time.sleep(2)

    # Füge die Cookies hinzu
    for cookie in cookies:
        driver.add_cookie(cookie)

    # Lade die Seite erneut, damit die Cookies wirksam werden
    driver.refresh()

    # Warte, um sicherzustellen, dass alles geladen ist
    time.sleep(4)


    remove_all_buttons(driver, to_remove_ids)

    # Warte, um sicherzustellen, dass alles geladen ist
    time.sleep(3)


    # Warte, bis der Speichern-Button sichtbar ist und klicke darauf
    try:
        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "edit-submit"))
        )
        save_button.click()
        print("Speichern-Button wurde geklickt.")
        print("\n\nes wurden alle Termine von heute dem", today, "aus Termino gelöscht.")
    except Exception as e:
        print(f"Fehler beim Klicken auf den Speichern-Button: {e}")

    print("\n\n Alle zu löschenden Termine wurden entfernt von Termino! \n\n")
    # Optional: Warten, um sicherzustellen, dass der Speichern-Button verarbeitet wurde
    time.sleep(3)
    
    
    driver.quit()










################################################################################################################
















################################################################################################################


           


def new_appointment(datum_zu_eintragen, zeit, place, short_id, driver, more_app_index):
    
    
    if more_app_index == 1:
        button_id = "edit-field-flagcollection-und-add-more"
    else:
        button_id = f"edit-field-flagcollection-und-add-more--{more_app_index}" 
    
    try:
        more_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, button_id))
        )
        more_button.click()
        print("More Button wurde geklickt.")
    except Exception as e:
        print(f"Fehler beim Klicken auf den More-Button: {e}")
    
    time.sleep(2)
       
    try: 
        date_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"{short_id}-field-optiondate-und-0-value-datepicker-popup-0"))
        )
        date_field.click()
        print(f"{datum_zu_eintragen} wurde eingefügt")
        # Trage das Datum ein
        date_field.send_keys(datum_zu_eintragen)
        
    except Exception as e:
        print(f"Fehler beim Eintragen des Datums {datum_zu_eintragen}: {e}")
    
    
    time.sleep(2)   
    
    try:
        
        
        time_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"{short_id}-field-optiondate-und-0-value-timeEntry-popup-1"))
        )
        time_field.click()
        print(f"{zeit} wurde eingefügt")
        
        time_field.send_keys(zeit)
        
    except Exception as e:
        print(f"Fehler beim Eintragen der time {zeit}: {e}")
        
        
    time.sleep(2)   
    
    try:

        
        
        place_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"{short_id}-weight"))
        )
        place_field.click()
        print(f"der Termin wurde an {place - 1}. Stelle eingefügt")
        
        insert_place = int(place - 1)
        
        if insert_place == 1:
            insert_place = 11
        elif insert_place == 11:
            insert_place = 1111
        
        print(insert_place)
            
        place_field.send_keys(insert_place)
        
        time.sleep(2)  
        
    except Exception as e:
        print(f"Fehler beim Eintragen des places: {e}")
    
    more_app_index += 1
    
    print(f"neuer Termin: ({datum_zu_eintragen} {zeit}) wurde erstellt und als {place-1}. Termin bei Termino eingefügt\n\n")
    
    return more_app_index

def insert_new_app_in_termino(kekse, editing_url, df_kombiniert):
    
    cookies = [{'name': key, 'value': value, 'domain': '.termino.gv.at', 'path': '/'} for key, value in kekse.items()]


    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)


    driver.get(editing_url)


    time.sleep(2)


    for cookie in cookies:
        driver.add_cookie(cookie)


    driver.refresh()


    try:
        numbers_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[title="Zeilen mittels numerischer Gewichtung ordnen statt mit Drag-and-Drop"]'))
        )
        numbers_button.click()
        print("numbers_button wurde geklickt.")
    except Exception as e:
        print(f"Fehler beim Klicken auf den numbers_button: {e}")

    time.sleep(2) 

    more_app_index = 1
    
    for _, row in df_kombiniert[df_kombiniert['Neuer_Termin'] == True].iterrows():
        datum_zu_eintragen = row['Date']
        zeit = row['Time']
        place = row['Place']
        short_id = row['Short ID']

        new_appointment(datum_zu_eintragen, zeit, place, short_id, driver, more_app_index)



    # Warte, um sicherzustellen, dass alles geladen ist
    time.sleep(5)


    # Warte, bis der Speichern-Button sichtbar ist und klicke darauf
    try:
        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "edit-submit"))
        )
        save_button.click()
        print("Speichern-Button wurde geklickt.")
        print("\n\n es wurden alle Termine in Termino ergänzt!")
    except Exception as e:
        print(f"Fehler beim Klicken auf den Speichern-Button: {e}")

    # Optional: Warten, um sicherzustellen, dass der Speichern-Button verarbeitet wurde
    time.sleep(5)

    driver.quit()




