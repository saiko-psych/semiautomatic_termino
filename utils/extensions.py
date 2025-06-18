import requests
import re
import pandas as pd
import datetime


def download_g_s(env_data, config_data):
    """
    Downloads a Google Spreadsheet and a specific worksheet from it as CSV files.

    This function:
    - Extracts the spreadsheet ID from the Google Sheets URL.
    - Retrieves the full HTML content of the spreadsheet to locate a specific sheet ("gid")
      by identifying a keyword provided in the configuration (e.g., "AUFNAHME LISTE").
    - Cleans the HTML content using regex to isolate relevant identifiers.
    - Constructs the download URLs for:
        1. The entire spreadsheet.
        2. The specific sheet matching the keyword.
    - Downloads and saves the CSV files to the 'data/' directory.

    Args:
        env_data (dict): Contains environment variables, including the Google Sheets URL.
        config_data (dict): Contains configuration, especially the target sheet name (`information`) for parsing.

    Returns:
        None
    """
    
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
    pattern = rf'(\d+)\s*,*\s*{re.escape(config_data['information'])}'

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



def google_dp(tomorrow):
    """
    Processes the Google Spreadsheet data for tomorrow's date and extracts the corresponding 
    supervisor details (name, email, date, time) for each appointment.

    This function:
    - Reads and processes the CSV files containing the main schedule and supervisor information.
    - Filters the data for the appointments scheduled for tomorrow.
    - Extracts relevant supervisor details (name, email, date, and time) for each appointment.
    - Returns lists of supervisor names, emails, appointment dates, and times.

    Args:
        tomorrow (str): The date for which the appointments should be retrieved (in "DD.MM.YYYY" format).

    Returns:
        tuple: A tuple containing four lists:
            - name_vl: List of supervisor names.
            - email_vl: List of supervisor email addresses.
            - date_vl: List of appointment dates.
            - time_vl: List of appointment times.
    """
    
    ## now the fun starts and we can work with the files 

    # Read the CSV file
    df = pd.read_csv("data/google_spreadsheet.csv", parse_dates=["Datum"], dayfirst=True)

    df["Datum"] = df["Datum"].ffill()


    t_iso = datetime.datetime.strptime(tomorrow, "%d.%m.%Y").strftime("%Y-%m-%d")  # will be "2025-04-06"

    # Filter values for tomorrow's date
    morgen_daten = df[df["Datum"] == t_iso]

    # Read additional spreadsheet info
    df_info = pd.read_csv("data/google_spreadsheet_information.csv")

    # Prepare empty lists
    name_vl = []
    email_vl = []
    date_vl = []
    time_vl = []

    # Columns with supervisor data
    vl_spalten = ["VL1", "VL2", "VL3", "VL4"]

    # Iterate over each row
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

    df["Datum"] = df["Datum"].ffill()

    #print(df)

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
    
    filter_zukuenftig = df["Datum"] > t_iso


    #filter only for valid datetimes in googlespreadsheet
    all_ereignisse = df[filter_gueltige_vl].copy()

    # Combine both filters (AND condition)
    kombinierter_filter = filter_gueltige_vl & filter_zukuenftig

    # Retrieve filtered data
    zukuenftige_ereignisse = df[kombinierter_filter].copy()
    
    df_termino["datetime"] = pd.to_datetime(
        df_termino["Date"].dt.strftime("%d.%m.%Y") + " " + df_termino["Time"],
        format="%d.%m.%Y %H:%M"
    )

    # If 'Datum' is not datetime yet:
    zukuenftige_ereignisse["Datum"] = pd.to_datetime(zukuenftige_ereignisse["Datum"])

    # Add time and combine into datetime
    zukuenftige_ereignisse["datetime"] = pd.to_datetime(
        zukuenftige_ereignisse["Datum"].dt.strftime("%Y-%m-%d") + " " + zukuenftige_ereignisse["Uhrzeit"],
        format="%Y-%m-%d %H:%M"
    )
    
    # If 'Datum' is not datetime yet:
    all_ereignisse["Datum"] = pd.to_datetime(all_ereignisse["Datum"])

    # Add time and combine into datetime
    all_ereignisse["datetime"] = pd.to_datetime(
        all_ereignisse["Datum"].dt.strftime("%Y-%m-%d") + " " + all_ereignisse["Uhrzeit"],
        format="%Y-%m-%d %H:%M"
    )   
    

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
    differenz_shreadsheet = []
    differenz_shreadsheet = zukuenftige_ereignisse[~zukuenftige_ereignisse["datetime"].isin(df_termino["datetime"])]

    if not differenz_shreadsheet.empty:
        print("For these events, there are no matching entries in Termino: \n\n", differenz_shreadsheet[['Datum','Uhrzeit']])
    
    # Would also be nice if the VLs are notified that they have registered for these new events
    # and receive calendar events with the new bookings, so they do not have to manually add them to their calendars or receive reminders
    # alternatively, a weekly reminder email could be nice where all VLs are informed of the appointments they have that week

    # Step 1: Reshape differenz_shreadsheet to create differenz_neu
    differenz_neu = pd.DataFrame()

    differenz_neu['datetime'] = differenz_shreadsheet['datetime']
    differenz_neu['Date'] = pd.to_datetime(differenz_shreadsheet['Datum']).dt.strftime('%d.%m.%Y')
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
    existing_ids = df_kombiniert['Short ID'].dropna().tolist()
    short_id_nums = [int(re.search(r'(\d+)$', sid).group(1)) for sid in existing_ids if re.search(r'(\d+)$', sid)]
    short_id_counter = max(short_id_nums, default=-1) + 1  # Start at 0 if none are found

    # Step 5: Assign new Short IDs and Place values
    for i in range(len(df_kombiniert)):
        df_kombiniert.loc[i, 'Place'] = i
        if pd.isna(df_kombiniert.loc[i, 'Short ID']):
            df_kombiniert.loc[i, 'Short ID'] = f'edit-field-flagcollection-und-{short_id_counter}'
            short_id_counter += 1

    # Step 6: Reorder the columns
    df_kombiniert = df_kombiniert[['Short ID', 'Place', 'Time', 'Date', 'datetime', 'Neuer_Termin']]
    
    return df_kombiniert


