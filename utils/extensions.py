import requests
import re
import pandas as pd
import datetime
from pathlib import Path


def download_g_s(env_data, config_data):
    """
    Provider-dispatching wrapper around the old Google-Sheets downloader.

    Reads config_data["sheet_provider"] (if present) and delegates to either
    GoogleSheetProvider or UniCloudSheetProvider, which both write the two
    CSV files into ./data/. Downstream functions (google_dp, data_prep)
    read those CSVs and don't need to know where they came from.

    If "sheet_provider" is missing from config, we fall back to Google for
    backward compatibility - the original behaviour.
    """
    from utils.sheet_providers import make_sheet_provider

    provider = make_sheet_provider(config_data)
    provider.fetch(env_data, config_data, Path("data"))
    return  # downstream functions read from ./data/ as before
    # ------- legacy body kept below for reference; not reached -------
    
    # Extract the spreadsheet ID from the URL
    spreadsheet_id = env_data['google_spreadsheet_url'].split('/d/')[1].split('/')[0]

    # URL to retrieve the HTML page
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    # Retrieve the HTML content of the page
    response = requests.get(url)

    # Save the full HTML content as text
    html_content = response.text

    # Find the first occurrence of "resizeApp"
    resize_app_index = html_content.find("resizeApp")

    if resize_app_index != -1:
        # Extract the part after the first occurrence of "resizeApp"
        content_after_resize_app = html_content[resize_app_index:]
        cleaned_content = re.sub(r'[^\w\s,]', '', content_after_resize_app)

    # Remove all numbers with less than 6 digits
    cleaned_content = re.sub(r'\b\d{1,8}\b', '', cleaned_content)

    # Remove all "words" longer than 20 characters (excluding spaces and commas)
    cleaned_content = re.sub(r'\b\w{21,}\b', '', cleaned_content)

    # Regular expression to find the number before the keyword from config
    _info_keyword = config_data['information']
    pattern = rf'(\d+)\s*,*\s*{re.escape(_info_keyword)}'

    # Search for the number before the keyword
    match = re.search(pattern, cleaned_content)

    if match:
        print(f"The number before {config_data['information']} is: {match.group(1)}")
    else:
        print(f"No gid found for {config_data['information']}. Please enter the correct name for the sheet in the input.")

    # URL to download the entire spreadsheet as CSV
    download_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"

    # Request the CSV content
    response = requests.get(download_url)

    # Check if the download was successful
    if response.status_code == 200:
        with open("data/google_spreadsheet.csv", "wb") as file:
            file.write(response.content)
            print("File successfully downloaded and saved as 'google_spreadsheet.csv'")
    else:
        print(f"Download error: {response.status_code}")

    # URL to download the specific sheet using the found gid
    download_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&id={spreadsheet_id}&gid={match.group(1)}"

    # Request the CSV content for the specific sheet
    response = requests.get(download_url)

    # Check if the download was successful
    if response.status_code == 200:
        with open("data/google_spreadsheet_information.csv", "wb") as file:
            file.write(response.content)
        print("File successfully downloaded and saved as 'google_spreadsheet_information.csv'")
    else:
        print(f"Download error: {response.status_code}")



def _is_valid_uhrzeit(value) -> bool:
    """True iff value parses as a HH:MM time string.

    Drops anything that openpyxl-CSV may have left as garbage:
      - NaN / None / empty string
      - the famous '01.01.1900' (Excel time-of-day epoch glitch)
      - any string that doesn't match HH:MM after trimming
    """
    if pd.isna(value):
        return False
    s = str(value).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return False
    if "1900" in s or "1899" in s:
        return False
    # Accept HH:MM and HH:MM:SS (we'll truncate seconds later).
    try:
        datetime.datetime.strptime(s[:5], "%H:%M")
        return True
    except ValueError:
        return False


def _normalize_uhrzeit(value):
    """Return 'HH:MM' string, or pd.NA if value is not a valid time."""
    if not _is_valid_uhrzeit(value):
        return pd.NA
    return str(value).strip()[:5]


def google_dp(tomorrow):
    """
    Processes the Google Spreadsheet data for tomorrow's date and extracts the corresponding
    supervisor details (name, email, date, time) for each appointment.

    Phantom-row handling
    --------------------
    Rows where the Uhrzeit column is empty/invalid (e.g. user typed a VL in
    a row that doesn't have a time, or openpyxl wrote out '01.01.1900' from
    an Excel time-only cell) are SKIPPED with a console warning instead of
    crashing the run. The script keeps going with valid rows.

    Returns:
        tuple of four lists: (name_vl, email_vl, date_vl, time_vl)
    """
    df = pd.read_csv("data/google_spreadsheet.csv", parse_dates=["Datum"], dayfirst=True)
    # errors='coerce' so a single bad date doesn't crash here.
    df["Datum"] = pd.to_datetime(df["Datum"], errors='coerce').ffill()
    # If after ffill the first rows still have NaT (column was empty up top)
    # those rows can't match tomorrow anyway. Drop NaT-rows defensively.
    if df["Datum"].isna().any():
        bad = int(df["Datum"].isna().sum())
        print(f"  !  google_dp: {bad} Zeile(n) mit ungueltigem Datum uebersprungen")
        df = df[df["Datum"].notna()].copy()

    t_iso = datetime.datetime.strptime(tomorrow, "%d.%m.%Y").strftime("%Y-%m-%d")
    morgen_daten = df[df["Datum"] == t_iso].copy()

    df_info = pd.read_csv("data/google_spreadsheet_information.csv")

    name_vl, email_vl, date_vl, time_vl = [], [], [], []
    vl_spalten = ["VL1", "VL2", "VL3", "VL4"]

    skipped_rows = 0
    for idx, row in morgen_daten.iterrows():
        uhrzeit_raw = row["Uhrzeit"]
        if not _is_valid_uhrzeit(uhrzeit_raw):
            # Phantom row: VL maybe set, but no usable time. Skip it.
            vls_in_row = [str(row[c]) for c in vl_spalten
                          if pd.notna(row[c]) and str(row[c]).strip()]
            if vls_in_row:
                print(
                    f"  !  google_dp: Spreadsheet-Zeile {idx + 2} ignoriert "
                    f"(Uhrzeit ungueltig: {uhrzeit_raw!r}, VLs: {vls_in_row}). "
                    f"Bitte in der xlsx korrigieren."
                )
                skipped_rows += 1
            continue

        uhrzeit = _normalize_uhrzeit(uhrzeit_raw)
        datum = row["Datum"].strftime("%Y-%m-%d")

        for spalte in vl_spalten:
            vl_kuerzel = row[spalte]
            if pd.notna(vl_kuerzel) and str(vl_kuerzel).strip() != "":
                kuerzel_stripped = str(vl_kuerzel).strip()
                vl_info = df_info[df_info["VL"] == kuerzel_stripped]
                if vl_info.empty:
                    # VL-Kuerzel ist in der Zeittabelle, fehlt aber im
                    # information-Sheet. Lautes Warnen statt still zu droppen.
                    print(
                        f"  !  google_dp: VL-Kuerzel {kuerzel_stripped!r} "
                        f"(Zeile {idx + 2}, Spalte {spalte}) fehlt im "
                        f"information-Sheet - VL wird nicht benachrichtigt!"
                    )
                    continue
                email = vl_info.iloc[0]["email"]
                name = vl_info.iloc[0]["name"]
                if pd.isna(email) or not str(email).strip():
                    print(
                        f"  !  google_dp: VL {kuerzel_stripped!r} hat keine "
                        f"Mail-Adresse im information-Sheet - kein Versand!"
                    )
                    continue
                name_vl.append(name)
                email_vl.append(email)
                date_vl.append(datum)
                time_vl.append(uhrzeit)

    if skipped_rows:
        print(f"  !  google_dp: {skipped_rows} Spreadsheet-Zeile(n) "
              f"wegen ungueltiger Uhrzeit uebersprungen.")

    return name_vl, email_vl, date_vl, time_vl



def data_prep(tomorrow, df_termino):
    """
    Prepares and filters the event data for upcoming events after the specified date (tomorrow) and compares it 
    with the data from another source (df_termino).

    This function:
    - Reads data from two CSV files (the main schedule and supervisor information).
    - Filters the events based on valid supervisor (VL) information and events that occur after tomorrow's date.
    - Converts date and time information into a combined datetime format for comparison.
    - Returns two datasets:

        - differenz_termino: Events from df_termino that do not match the upcoming events.
        - zukuenftige_ereignisse: Events that are upcoming (after tomorrow).

    Args:
        tomorrow (str): The date to use as the threshold for filtering (in "DD.MM.YYYY" format).
        df_termino (pd.DataFrame): DataFrame containing the event details from an external source.

    Returns:
        tuple: A tuple containing two DataFrames:
            - differenz_termino: Events from df_termino that do not match the upcoming events.
            - zukuenftige_ereignisse: Events that are scheduled after tomorrow's date.
    """
    
    df = pd.read_csv("data/google_spreadsheet.csv", parse_dates=["Datum"], dayfirst=True)

    # errors='coerce' so a single bad date doesn't crash data_prep.
    df["Datum"] = pd.to_datetime(df["Datum"], errors='coerce').ffill()
    if df["Datum"].isna().any():
        bad = int(df["Datum"].isna().sum())
        print(f"  !  data_prep: {bad} Zeile(n) mit ungueltigem Datum uebersprungen")
        df = df[df["Datum"].notna()].copy()

    # Drop phantom rows up front: rows where Uhrzeit is empty, NaN, or one of
    # the openpyxl garbage values ('01.01.1900'). This stops a single bad
    # spreadsheet cell from crashing the entire daily run.
    #
    # Pandas quirk: df[empty_object_series] returns a frame with NO columns,
    # so we must (a) coerce the mask to bool, and (b) skip the whole block
    # when df is already empty.
    if "Uhrzeit" in df.columns and not df.empty:
        before = len(df)
        valid_mask = df["Uhrzeit"].apply(_is_valid_uhrzeit).astype(bool)
        bad = df[~valid_mask]
        for idx, row in bad.iterrows():
            any_vl = any(
                pd.notna(row.get(c)) and str(row.get(c)).strip()
                for c in ("VL1", "VL2", "VL3", "VL4")
            )
            if any_vl:
                print(
                    f"  !  data_prep: Zeile {idx + 2} ignoriert "
                    f"(Uhrzeit ungueltig: {row['Uhrzeit']!r}). "
                    f"Bitte in der xlsx korrigieren."
                )
        df = df[valid_mask].copy()
        # Normalise Uhrzeit to 'HH:MM' so downstream pd.to_datetime never
        # sees '10:00:00' / '10:00 '/etc.
        if not df.empty:
            df["Uhrzeit"] = df["Uhrzeit"].apply(_normalize_uhrzeit)
        if len(df) < before:
            print(f"  !  data_prep: {before - len(df)} ungueltige Zeile(n) "
                  f"uebersprungen.")

    df_info = pd.read_csv("data/google_spreadsheet_information.csv")

    gueltige_vl = df_info['VL'].tolist()

    # Create filters for rows where at least one VL column contains a valid value
    filter_vl1 = df['VL1'].isin(gueltige_vl)
    filter_vl2 = df['VL2'].isin(gueltige_vl)
    filter_vl3 = df['VL3'].isin(gueltige_vl)
    filter_vl4 = df['VL4'].isin(gueltige_vl)

    # Combined filter with OR condition for valid VL abbreviations
    filter_gueltige_vl = filter_vl1 | filter_vl2 | filter_vl3 | filter_vl4

    # Filter for future events (after tomorrow)
    t_iso = datetime.datetime.strptime(tomorrow, "%d.%m.%Y").strftime("%Y-%m-%d")
    
    # >= statt >: morgen selbst soll auch synchronisiert werden, sonst wird ein
    # xlsx-Eintrag fuer morgen nie als "in Termino fehlend" erkannt. Bug found
    # 2026-05-28 im Live-Test: 29.05.-Slot landete im Kalender + VL-Mail aber
    # nicht in Termino, weil filter_zukuenftig den Slot raus warf.
    filter_zukuenftig = df["Datum"] >= t_iso


    #filter only for valid datetimes in googlespreadsheet
    all_ereignisse = df[filter_gueltige_vl].copy()

    # Combine both filters (AND condition)
    kombinierter_filter = filter_gueltige_vl & filter_zukuenftig

    # Retrieve filtered data
    zukuenftige_ereignisse = df[kombinierter_filter].copy()
    
    # errors='coerce' across the board: one bad Termino row or one bad
    # spreadsheet row must not crash the whole daily run. Affected rows
    # become NaT and get filtered out before the diff.
    df_termino["datetime"] = pd.to_datetime(
        df_termino["Date"].dt.strftime("%d.%m.%Y") + " " + df_termino["Time"].astype(str),
        format="%d.%m.%Y %H:%M",
        errors="coerce",
    )
    if df_termino["datetime"].isna().any():
        bad = int(df_termino["datetime"].isna().sum())
        print(f"  !  data_prep: {bad} Termino-Booking(s) mit ungueltigem Date/Time uebersprungen")
        df_termino = df_termino[df_termino["datetime"].notna()].copy()

    zukuenftige_ereignisse["Datum"] = pd.to_datetime(
        zukuenftige_ereignisse["Datum"], errors="coerce"
    )
    zukuenftige_ereignisse["datetime"] = pd.to_datetime(
        zukuenftige_ereignisse["Datum"].dt.strftime("%Y-%m-%d") + " "
        + zukuenftige_ereignisse["Uhrzeit"].astype(str),
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )
    zukuenftige_ereignisse = zukuenftige_ereignisse[
        zukuenftige_ereignisse["datetime"].notna()
    ].copy()

    all_ereignisse["Datum"] = pd.to_datetime(
        all_ereignisse["Datum"], errors="coerce"
    )
    all_ereignisse["datetime"] = pd.to_datetime(
        all_ereignisse["Datum"].dt.strftime("%Y-%m-%d") + " "
        + all_ereignisse["Uhrzeit"].astype(str),
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )
    all_ereignisse = all_ereignisse[all_ereignisse["datetime"].notna()].copy()

    

    # Compare using the datetime column
    differenz_termino = df_termino[~df_termino["datetime"].isin(all_ereignisse["datetime"])]
    
    return differenz_termino, zukuenftige_ereignisse


def data_prep_2(zukuenftige_ereignisse, df_termino):
    """
    Prepares the data by comparing the upcoming events with the existing events in Termino and merging the data.

    This function:
    - Identifies events in `zukuenftige_ereignisse` that are not yet present in `df_termino`.
    - Generates a new dataframe (`differenz_neu`) with these events that need to be added to Termino.
    - Merges this new data with the existing Termino data, assigns unique IDs and place values, and sorts the data.
    - Returns the combined dataframe with the new events to be added to Termino.

    Args:
        zukuenftige_ereignisse (pd.DataFrame): DataFrame containing the upcoming events.
        df_termino (pd.DataFrame): DataFrame containing the existing events from Termino.

    Returns:
        pd.DataFrame: A combined DataFrame with both existing and new events, sorted and with updated IDs and place values.
    """
    # Find events in the spreadsheet that aren't yet in Termino
    differenz_shreadsheet = zukuenftige_ereignisse[
        ~zukuenftige_ereignisse["datetime"].isin(df_termino["datetime"])
    ]

    if not differenz_shreadsheet.empty:
        print("For these events, there are no matching entries in Termino: \n\n",
              differenz_shreadsheet[['Datum', 'Uhrzeit']])

    # Step 1: Reshape differenz_shreadsheet to create differenz_neu
    differenz_neu = pd.DataFrame()

    differenz_neu['datetime'] = differenz_shreadsheet['datetime']
    # NaT-Guard: errors='coerce' so a bad Datum doesn't kill the whole task.
    differenz_neu['Date'] = pd.to_datetime(
        differenz_shreadsheet['Datum'], errors='coerce'
    ).dt.strftime('%d.%m.%Y')
    differenz_neu['Time'] = differenz_shreadsheet['Uhrzeit']
    differenz_neu['Place'] = None
    differenz_neu['Short ID'] = None
    differenz_neu['Neuer_Termin'] = True

    df_termino['Neuer_Termin'] = False

    if not differenz_neu.empty:
        df_kombiniert = pd.concat([df_termino, differenz_neu], ignore_index=True)
    else:
        df_kombiniert = df_termino.copy()

    # Step 3: Sort by datetime
    df_kombiniert = df_kombiniert.sort_values('datetime').reset_index(drop=True)

    # Step 4: Determine the starting value for the Short ID counter
    existing_ids = df_termino['Short ID'].dropna().tolist()
    if existing_ids:
        existing_nums = [
            int(s.split('-')[-1])
            for s in existing_ids
            if isinstance(s, str) and s.split('-')[-1].isdigit()
        ]
        short_id_counter = max(existing_nums) + 1 if existing_nums else 0
    else:
        short_id_counter = 0


    # Step 5: Reset Place to row index, fill in missing Short IDs.
    #
    # Vectorised + column-replace because pandas 2.2+ with the new
    # future-string-dtype option treats ``df[col] = ...`` as an in-place
    # update of an existing column. If the column was previously
    # str-dtype (which happens when df_termino was parsed from the
    # Termino CSV where Place is a numeric string), an int assignment
    # raises TypeError. Dropping the column first guarantees the new
    # one gets a fresh dtype.
    df_kombiniert = df_kombiniert.drop(columns=['Place'])
    df_kombiniert['Place'] = list(range(len(df_kombiniert)))

    # Same trick for Short ID: build a clean object-dtype column with
    # existing IDs preserved and new ones generated for the NaN slots.
    existing_short_ids = df_kombiniert['Short ID'].tolist()
    df_kombiniert = df_kombiniert.drop(columns=['Short ID'])
    new_short_ids = []
    counter = short_id_counter
    for sid in existing_short_ids:
        if pd.isna(sid):
            new_short_ids.append(f'edit-field-flagcollection-und-{counter}')
            counter += 1
        else:
            new_short_ids.append(sid)
    df_kombiniert['Short ID'] = new_short_ids

    # Step 6: Reorder the columns
    df_kombiniert = df_kombiniert[['Short ID', 'Place', 'Time', 'Date', 'datetime', 'Neuer_Termin']]

    return df_kombiniert
