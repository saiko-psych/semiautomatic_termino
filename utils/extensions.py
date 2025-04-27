import requests
import re
import pandas as pd
import datetime


def download_g_s(env_data, config_data):
    # Extrahieren der Spreadsheet-ID aus der URL
    spreadsheet_id = env_data['google_spreadsheet_url'].split('/d/')[1].split('/')[0]



    # URL zum Abrufen der HTML-Seite
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"



    # HTML-Inhalt der Seite abrufen
    response = requests.get(url)

    # Den gesamten HTML-Inhalt als Text speichern
    html_content = response.text

    # Finden des ersten Vorkommens von "resizeApp"
    resize_app_index = html_content.find("resizeApp")

    if resize_app_index != -1:
        # Extrahieren des Teils nach dem ersten Vorkommen von "resizeApp"
        content_after_resize_app = html_content[resize_app_index:]
        cleaned_content = re.sub(r'[^\w\s,]', '', content_after_resize_app)


    # Entferne alle Zahlen mit weniger als 6 Stellen
    cleaned_content = re.sub(r'\b\d{1,8}\b', '', cleaned_content)

    # Entferne alle "Wörter" mit mehr als 20 Buchstaben/Zahlen (ohne Leerzeichen oder Kommas)
    cleaned_content = re.sub(r'\b\w{21,}\b', '', cleaned_content)



    # Regulärer Ausdruck, um die Zahl vor "AUFNAHME LISTE" zu finden
    pattern = rf'(\d+)\s*,*\s*{re.escape(config_data['information'])}'

    # Suche nach der Zahl vor "AUFNAHME LISTE"
    match = re.search(pattern, cleaned_content)

    if match:
        print(f"Die Zahl vor {config_data['information']} ist: {match.group(1)}")
    else:
        print(f"Keine gid für {config_data['information']} gefunden. Bitte richtigen namen für die seite eingeben beim daten input")
    

    # URL zum dowload der HTML-Seite

    download_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"

    # HTML-Inhalt der Seite abrufen
    response = requests.get(download_url)

    # Check, ob der Download erfolgreich war
    if response.status_code == 200:
        with open("data/google_spreadsheet.csv", "wb") as file:
            file.write(response.content)
            print("Datei erfolgreich heruntergeladen und gespeichert als 'google_spreadsheet.csv'")
    else:
        print(f"Fehler beim Download: {response.status_code}")



    download_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&id={spreadsheet_id}&gid={match.group(1)}"

    # HTML-Inhalt der Seite abrufen
    response = requests.get(download_url)

    # Check, ob der Download erfolgreich war
    if response.status_code == 200:
        with open("data/google_spreadsheet_information.csv", "wb") as file:
            file.write(response.content)
        print("Datei erfolgreich heruntergeladen und gespeichert als 'google_spreadsheet_information.csv'")
    else:
        print(f"Fehler beim Download: {response.status_code}")




def google_dp(tomorrow):
    ## now the fun starts and we can work with the files 

    # CSV einlesen
    df = pd.read_csv("data/google_spreadsheet.csv", parse_dates=["Datum"], dayfirst=True)

    df["Datum"] = df["Datum"].ffill()


    t_iso = datetime.datetime.strptime(tomorrow, "%d.%m.%Y").strftime("%Y-%m-%d")  # wird "2025-04-06"

    # Werte für das heutige Datum herausfiltern
    morgen_daten = df[df["Datum"] == t_iso]

    #print(morgen_daten)

    df_info = pd.read_csv("data/google_spreadsheet_information.csv")

    # print(df_info)


    # Leere Listen vorbereiten
    name_vl = []
    email_vl = []
    date_vl = []
    time_vl = []

    # Spalten mit den VLs
    vl_spalten = ["VL1", "VL2", "VL3", "VL4"]

    # Zeilenweise durchgehen
    for idx, row in morgen_daten.iterrows():
        uhrzeit = row["Uhrzeit"]
        datum = row["Datum"].strftime("%Y-%m-%d")

        for spalte in vl_spalten:
            vl_kürzel = row[spalte]

            if pd.notna(vl_kürzel) and str(vl_kürzel).strip() != "":
                vl_info = df_info[df_info["VL"] == vl_kürzel]

                if not vl_info.empty:
                    email = vl_info.iloc[0]["email"]
                    name = vl_info.iloc[0]["name"]

                    if pd.notna(email) and str(email).strip() != "":
                        name_vl.append(name)
                        email_vl.append(email)
                        date_vl.append(datum)
                        time_vl.append(uhrzeit)


    #print("name_vl: ", name_vl)
    #print("email_vl:", email_vl)
    #print("date_vl: ", date_vl)
    #print("time_vl: ", time_vl)


    
    return name_vl, email_vl, date_vl, time_vl


def data_prep(tomorrow, df_termino):
    
    df = pd.read_csv("data/google_spreadsheet.csv", parse_dates=["Datum"], dayfirst=True)

    df["Datum"] = df["Datum"].ffill()

    #print(df)

    df_info = pd.read_csv("data/google_spreadsheet_information.csv")
    
    gueltige_vl = df_info['VL'].tolist()

    # Filter erstellen für Zeilen, bei denen mindestens eine VL-Spalte einen gültigen Wert enthält
    filter_vl1 = df['VL1'].isin(gueltige_vl)
    filter_vl2 = df['VL2'].isin(gueltige_vl)
    filter_vl3 = df['VL3'].isin(gueltige_vl)
    filter_vl4 = df['VL4'].isin(gueltige_vl)

    # Kombinierter Filter mit ODER-Verknüpfung für gültige VL-Kürzel
    filter_gueltige_vl = filter_vl1 | filter_vl2 | filter_vl3 | filter_vl4

    # Filter für zukünftige Ereignisse (ab morgen)
    t_iso = datetime.datetime.strptime(tomorrow, "%d.%m.%Y").strftime("%Y-%m-%d")
    
    filter_zukuenftig = df["Datum"] > t_iso

    # Beide Filter kombinieren (UND-Verknüpfung)
    kombinierter_filter = filter_gueltige_vl & filter_zukuenftig

    # Gefilterte Daten abrufen
    zukuenftige_ereignisse = df[kombinierter_filter].copy()
    
    df_termino["datetime"] = pd.to_datetime(
        df_termino["Date"].dt.strftime("%d.%m.%Y") + " " + df_termino["Time"],
        format="%d.%m.%Y %H:%M"
    )



    # Falls 'Datum' noch nicht datetime ist:
    zukuenftige_ereignisse["Datum"] = pd.to_datetime(zukuenftige_ereignisse["Datum"])

    # Zeit hinzufügen und zu datetime kombinieren
    zukuenftige_ereignisse["datetime"] = pd.to_datetime(
        zukuenftige_ereignisse["Datum"].dt.strftime("%Y-%m-%d") + " " + zukuenftige_ereignisse["Uhrzeit"],
        format="%Y-%m-%d %H:%M"
    )




    # Vergleich über datetime-Spalte
    differenz_termino = df_termino[~df_termino["datetime"].isin(zukuenftige_ereignisse["datetime"])]
    
    return differenz_termino, zukuenftige_ereignisse


def data_prep_2(zukuenftige_ereignisse, df_termino):
    
    differenz_shreadsheet = zukuenftige_ereignisse[~zukuenftige_ereignisse["datetime"].isin(df_termino["datetime"])]

    print("für diese Termine gibt es noch keine Termine in Termino: \n\n", differenz_shreadsheet[['Datum','Uhrzeit']])


    # wäre auch cool wenn die vl informiert wird das sie sich für diese Termine neu eingetragen hat 
    #und dann werden ihr kalender events gesendet mit den neuen buchungen und somit müsste man sich selbst nicht mehr alle Termine in seinem kalender eintragen bzw bekommt man erinnerungen
        # alternativ wäre auch eine weekly reminder mail ganz nice wo alle VL informiert werden welche Termine Sie diese woche haben

    # Schritt 1: df_differenz_spreadsheet umformen
    differenz_neu = pd.DataFrame()

    differenz_neu['datetime'] = differenz_shreadsheet['datetime']
    differenz_neu['Date'] = pd.to_datetime(differenz_shreadsheet['Datum']).dt.strftime('%d.%m.%Y')
    differenz_neu['Time'] = differenz_shreadsheet['Uhrzeit']
    differenz_neu['Place'] = None
    differenz_neu['Short ID'] = None
    differenz_neu['Neuer_Termin'] = True

    df_termino['Neuer_Termin'] = False

    # Schritt 2: Zusammenführen
    df_kombiniert = pd.concat([df_termino, differenz_neu], ignore_index=True)

    # Schritt 3: Nach datetime sortieren
    df_kombiniert = df_kombiniert.sort_values('datetime').reset_index(drop=True)

    # Schritt 4: Startwert für Short ID Zähler ermitteln
    existing_ids = df_kombiniert['Short ID'].dropna().tolist()
    short_id_nums = [int(re.search(r'(\d+)$', sid).group(1)) for sid in existing_ids if re.search(r'(\d+)$', sid)]
    short_id_counter = max(short_id_nums, default=-1) + 1  # Falls keine vorhanden, beginnt bei 0

    # Schritt 5: Neue Short IDs und Place setzen
    for i in range(len(df_kombiniert)):
        df_kombiniert.loc[i, 'Place'] = i
        if pd.isna(df_kombiniert.loc[i, 'Short ID']):
            df_kombiniert.loc[i, 'Short ID'] = f'edit-field-flagcollection-und-{short_id_counter}'
            short_id_counter += 1

    # Schritt 6: Spaltenreihenfolge
    df_kombiniert = df_kombiniert[['Short ID', 'Place', 'Time', 'Date', 'datetime', 'Neuer_Termin']]
    
    return df_kombiniert


