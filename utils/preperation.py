import datetime
import json
import pandas as pd
from dotenv import load_dotenv, dotenv_values
from utils.styles import RED, BLUE, GREEN, YELLOW, BG_WHITE, RESET

def date_creation():
    """
    This function generates today's and tomorrow's dates both in string format and as datetime objects.

    It performs the following steps:
    1. Fetches the current date (today) and formats it as a string in the format "DD.MM.YYYY".
    2. Calculates tomorrow's date by adding one day to the current date, and formats it similarly.
    3. Converts both the string representations of today's and tomorrow's dates into pandas datetime objects for further manipulation.
    
    Returns:
    - today (str): The current date in "DD.MM.YYYY" format.
    - tomorrow (str): The date of the following day in "DD.MM.YYYY" format.
    - today_as_datetime (datetime): The current date as a pandas datetime object.
    - tomorrow_as_datetime (datetime): Tomorrow's date as a pandas datetime object.
    """
    
    # Get today's date
    t = datetime.datetime.now()
    today = t.strftime("%d.%m.%Y")

    # Get tomorrow's date
    t = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = t.strftime("%d.%m.%Y")
    
    # Convert to pandas datetime objects
    today_as_datetime = pd.to_datetime(today, dayfirst=True)
    tomorrow_as_datetime = pd.to_datetime(tomorrow, dayfirst=True)
    
    return today, tomorrow, today_as_datetime, tomorrow_as_datetime




def load_config():
    """
    Loads the configuration data from the 'config.json' file.

    This function opens the 'config.json' file, reads its content, and returns the configuration data
    as a Python dictionary.

    Returns:
    - dict: The configuration data loaded from the 'config.json' file.
    
    Raises:
    - FileNotFoundError: If the 'config.json' file does not exist.
    - json.JSONDecodeError: If there is an issue parsing the JSON data.
    """
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

    

def load_env_data() -> dict:
    """
    Loads environment variables from the '.env' file and returns them as a dictionary.

    This function loads the environment variables from the 'sensible.env' file into the
    system's environment using the `load_dotenv()` function. It then uses the `dotenv_values()`
    function to retrieve the values as a dictionary and returns them.

    Returns:
    - dict: A dictionary containing the environment variables from the 'sensible.env' file.
    
    Raises:
    - FileNotFoundError: If the 'sensible.env' file does not exist.
    - dotenv.errors.DotenvError: If there is an error loading the '.env' file.
    """
    load_dotenv("sensible.env", encoding="utf-8")  # Load into os.environ
    return dotenv_values("sensible.env", encoding="utf-8")  # Return dictionary

    


 


def config_text(config_data, env_data):
    """
    Prints the configuration data and environment variables in a formatted manner.

    This function takes two arguments: `config_data` (a dictionary containing configuration 
    settings) and `env_data` (a dictionary containing environment variables). It prints various 
    pieces of configuration information and environment variables with different colors for better 
    visibility and understanding.

    Args:
    - config_data (dict): A dictionary containing configuration settings such as booking list, study name, 
                           flags for printing booking lists, and feature toggles.
    - env_data (dict): A dictionary containing sensitive environment variables like email credentials 
                       and Termino usernames.

    Prints:
    - Various environment and configuration settings to the console, including:
        - Termino username and password
        - Yahoo email address and credentials
        - Configuration flags (e.g., whether to print current bookings)
        - Feature toggle information (e.g., use of Google spreadsheet integration)
    
    Notes:
    - The printed information uses color formatting (e.g., red, blue, green) for better readability.
    """
    print("Sensible Daten: \n\n")
    print(f"{RED}Termino Benutzernamen{RESET}: {env_data['username_termino']} \n")
    print(f"{RED}Termino Passwort{RESET}: {env_data['password_termino']} \n")
    print(f"{BLUE}YAHOO-E-Mail-Adresse{RESET}: {env_data['mail']} \n")
    print(f"{BLUE}E-Mail Passwort{RESET}: {env_data['password_mail']} \n")
    print(f"{RED}App Passwort{RESET}: {env_data['app_password_mail']} \n")
    
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
        
    if config_data['to_send_first_mail'] == 1:
        print("\n")
    else:
        print("\n")

    if config_data['implement_google'] == 1:
        print(f"\nSuper Cooles Feature zur Benachrichtigung der Versuchsleitung wird verwendet!"
              f"\nlets gooo!!!!! SIIIICKE SACHE"
              f"\n\n{GREEN}{BG_WHITE}google_spreadsheet url{RESET}: {GREEN}{BG_WHITE}{env_data['google_spreadsheet_url']}{RESET}"
              f"\n\nName des {YELLOW}Tabellenblattes{RESET} für die VL-Information: {YELLOW}{config_data['information']}{RESET}\n\n"
              )
    else:
        print("\n du verwendest das tolle feature nicht :( \n\n")




def booking_list_preperation(actual_booking_list_csv, config_data):
    """
    Prepares and processes the booking list by checking which bookings have already 
    received the first email and which need to be sent the first email. It also prints 
    relevant details about the bookings based on the configuration settings.

    Args:
    - actual_booking_list_csv (str): The path to the CSV file containing the actual booking list.
    - config_data (dict): A dictionary containing configuration data, including flags 
                          for printing the booking list and sending first emails.

    Returns:
    - date_prob (list): A list of dates from the actual booking list.
    - name_prob (list): A list of names from the actual booking list.
    - email_prob (list): A list of emails from the actual booking list.
    - date_first_mail_sended (list): A list of dates when the first emails were sent.
    - name_first_mail_sended (list): A list of names who have already received the first email.
    - email_first_mail_sended (list): A list of emails of those who have received the first email.
    - to_send_name (list): A list of names who will receive the first email.
    - to_send_mail (list): A list of emails who will receive the first email.
    - to_send_date (list): A list of dates for the bookings that will receive the first email.

    Side Effects:
    - Reads and writes to CSV files (`first_mail_sended_booking_list.csv` and the provided `actual_booking_list_csv`).
    - Optionally prints out booking lists and the people who need to be sent the first email based on configuration.
    - Updates the first email sent list to include new names.

    Notes:
    - The function uses the provided `config_data` to determine whether to print booking lists and emails.
    - If a person from the actual booking list has not received the first email yet, they will be added to the list 
      of people to receive the first email.
    """
    
    first_mail_file = "data/first_mail_sended_booking_list.csv"

    # Load the actual booking list from the provided CSV file
    df = pd.read_csv(actual_booking_list_csv, sep=";", decimal=",")  # Termino Booking List
    
    # Extract relevant columns as lists
    date_prob = df['Date'].tolist()
    name_prob = df['Name'].tolist()
    email_prob = df['E-Mail'].tolist()

    def print_actual_bookings(x=2):
        """
        Prints the current bookings based on the configuration setting.

        Args:
        - x (int): Determines whether the current bookings should be printed. If `x == 1`, 
                   the bookings will be printed. If `x != 1`, they will not be printed.
        
        Returns:
        - None: This function only prints the bookings to the console.
        """
        if x == 1:
            print("\n\n\n\n\nAktuelle Buchungen: \n\n")
            for name, datum, email in zip(name_prob, date_prob, email_prob):
                print(f"   Name: {name} \n   Datum: {datum} \n   E-Mail: {email}\n\n")
        else:
            print("\n\nAktuelle Buchungsliste wird nicht ausgegeben.") 

    # Load the list of bookings that have already received the first email
    first_mail_sended = pd.read_csv(first_mail_file, sep=",", decimal=";")  # Termino
    
    # Extract the relevant data for already sent first emails
    date_first_mail_sended = first_mail_sended['Date'].tolist()
    name_first_mail_sended = first_mail_sended['Name'].tolist()
    email_first_mail_sended = first_mail_sended['E-Mail'].tolist()

    def print_first_mail_sended(x=2):
        """
        Prints the list of people who have already received the first email.

        Args:
        - x (int): Determines whether the list of people who have received the first email should be printed.
                   If `x == 1`, the list will be printed. If `x != 1`, it will not be printed.

        Returns:
        - None: This function only prints the list to the console.
        """
        if x == 1:
            print("\n\n\n\n\nPersonen die erste Mail schon erhalten haben: \n\n")
            for name, datum, email in zip(name_first_mail_sended, date_first_mail_sended, email_first_mail_sended):
                print(f"   Name: {name} \n   Datum: {datum} \n   E-Mail: {email}\n\n")
        else:
            print("\n\nListe mit Personen die erste Mail schon erhalten haben wird nicht ausgegeben.")

    print_actual_bookings(config_data['actual_list_printing'])
    print_first_mail_sended(config_data['fist_mail_recieved_printing'])
    
    # Lists for people who need to receive the first email
    to_send_name = []
    to_send_mail = []
    to_send_date = [] 

    # Identify the people who need to receive the first email
    for eintrag in range(0, len(email_prob)):
        drauen = 2
        for no in range(0, len(date_first_mail_sended)):
            if email_first_mail_sended[no] == email_prob[eintrag] and name_first_mail_sended[no] == name_prob[eintrag]:
                drauen = 1   
                
        if drauen > 1:
            to_send_name.append(name_prob[eintrag])
            to_send_date.append(date_prob[eintrag])
            to_send_mail.append(email_prob[eintrag])  # Add to the mail list
            
            if (email_prob[eintrag] and name_prob[eintrag]) not in email_first_mail_sended:
                date_first_mail_sended.append(date_prob[eintrag])
                name_first_mail_sended.append(name_prob[eintrag])
                email_first_mail_sended.append(email_prob[eintrag])  # Add to first_email_sended list

    def print_to_send_first_mail(x=1):
        """
        Prints the list of people who will receive the first email.

        Args:
        - x (int): Determines whether the list of people to receive the first email should be printed.
                   If `x == 1`, the list will be printed. If `x != 1`, it will not be printed.

        Returns:
        - None: This function only prints the list to the console.
        """
        if x == 1:
            print("\n\n\n\n\nPersonen an welche die erste Mail gesendet wird: \n\n")
            for name, datum, email in zip(to_send_name, to_send_date, to_send_mail):
                print(f"   Name: {name} \n   Datum: {datum} \n   E-Mail: {email}\n\n")
        else:
            print("\n\nListe mit Personen welche die erste Mail nun gesendet bekommen wird nicht ausgegeben.")

    print_to_send_first_mail(config_data['to_send_first_mail'])

    # Update the first email sent list with new names
    first_mail_sended = {'Name': name_first_mail_sended, 'Date': date_first_mail_sended, 'E-Mail': email_first_mail_sended}
    first_mail_sended = pd.DataFrame(first_mail_sended)
    first_mail_sended.to_csv(first_mail_file)
    
    return (date_prob, name_prob, email_prob, 
            date_first_mail_sended, name_first_mail_sended, email_first_mail_sended, 
            to_send_name, to_send_mail, to_send_date)




def tomorrow_today_data(date_prob, name_prob, email_prob, tomorrow, today):
    """
    This function filters the provided booking data to separate out the bookings for today and tomorrow. 
    It then returns the relevant information for tomorrow's and today's bookings, including names, emails, 
    dates, and times for each.

    Args:
    - date_prob (list): A list of booking dates as strings (e.g., "dd.mm.yyyy - hh:mm").
    - name_prob (list): A list of names associated with each booking.
    - email_prob (list): A list of emails associated with each booking.
    - tomorrow (str): The date of tomorrow in the format "dd.mm.yyyy".
    - today (str): The date of today in the format "dd.mm.yyyy".

    Returns:
    - tomorrow_name (list): A list of names for the bookings scheduled for tomorrow.
    - tomorrow_email (list): A list of emails for the bookings scheduled for tomorrow.
    - tomorrow_date (list): A list of dates for the bookings scheduled for tomorrow.
    - tomorrow_time (list): A list of times for the bookings scheduled for tomorrow.
    - today_name (list): A list of names for the bookings scheduled for today.
    - today_email (list): A list of emails for the bookings scheduled for today.
    - today_date (list): A list of dates for the bookings scheduled for today.

    Example:
    If `date_prob` contains ["01.05.2025 - 10:00", "02.05.2025 - 14:00"], and `today` is "01.05.2025",
    the function will return:
    - tomorrow_name: ["John Doe"]
    - tomorrow_email: ["john.doe@example.com"]
    - tomorrow_date: ["02.05.2025 - 14:00"]
    - tomorrow_time: ["14:00"]
    - today_name: ["Jane Smith"]
    - today_email: ["jane.smith@example.com"]
    - today_date: ["01.05.2025 - 10:00"]
    """

    # Lists to store tomorrow's and today's bookings
    tomorrow_name = []
    tomorrow_email = []
    tomorrow_date = []

    # Loop through the dates to identify tomorrow's bookings
    for eintrag in range(0, len(date_prob)):
        if date_prob[eintrag].split()[0] == tomorrow:  # Match the date part with tomorrow
            tomorrow_name.append(name_prob[eintrag])
            tomorrow_email.append(email_prob[eintrag])
            tomorrow_date.append(date_prob[eintrag])

    # Extract the time from the date for tomorrow's bookings
    tomorrow_time = []
    for termin1 in tomorrow_date:
        date1, time1 = termin1.split(" - ")
        tomorrow_time.append(time1)

    # Lists to store today's bookings
    today_name = []
    today_email = []
    today_date = []

    # Loop through the dates to identify today's bookings
    for eintrag in range(0, len(date_prob)):
        if date_prob[eintrag].split()[0] == today:  # Match the date part with today
            today_name.append(name_prob[eintrag])
            today_email.append(email_prob[eintrag])
            today_date.append(date_prob[eintrag])

    # Return the relevant information
    return tomorrow_name, tomorrow_email, tomorrow_date, tomorrow_time, today_name, today_email, today_date



def get_ids_to_remove(df_termino, today_as_datetime, tomorrow_as_datetime, tomorrow_time):
    """
    This function filters the provided booking dataframe (`df_termino`) to identify records that need to be removed based on the following criteria:
    - Bookings that are already past (before or on today's date).
    - Bookings for tomorrow that do not match the expected time values (`tomorrow_time`).

    The function returns a list of IDs to remove, which are based on the 'Short ID' field of the filtered bookings.

    Args:
    - df_termino (pandas.DataFrame): DataFrame containing booking data with columns like 'Date', 'Time', and 'Short ID'.
    - today_as_datetime (datetime): The current date as a datetime object to compare against booking dates.
    - tomorrow_as_datetime (datetime): The date for tomorrow as a datetime object to filter bookings for tomorrow.
    - tomorrow_time (list): A list of expected times for tomorrow's bookings.

    Returns:
    - list: A list of IDs to remove, constructed by appending "-remove-button" to the 'Short ID' values of the filtered records.

    Example:
    If the dataframe `df_termino` contains the following:
    ```
    Date            | Time    | Short ID
    --------------------------------------
    30.04.2025      | 10:00   | 12345
    01.05.2025      | 14:00   | 23456
    02.05.2025      | 09:00   | 34567
    02.05.2025      | 15:00   | 45678
    ```
    And the inputs are:
    - `today_as_datetime`: 30.04.2025
    - `tomorrow_as_datetime`: 01.05.2025
    - `tomorrow_time`: ["10:00", "14:00"]
    
    The function will return a list of IDs to remove based on the following criteria:
    - All bookings before or on today's date (e.g., 30.04.2025).
    - Bookings for tomorrow (01.05.2025) with times that do not match any in the `tomorrow_time` list.
    
    In this case, the result might be:
    ```
    ['12345-remove-button', '23456-remove-button']
    ```
    """
    
    # Working copy of df_termino
    df_termino_used = df_termino.copy()


    # Filter bookings that are today or in the past
    df_till_today = df_termino_used[df_termino_used['Date'] <= today_as_datetime]
    
    # Filter bookings that are scheduled for tomorrow
    df_tomorrow = df_termino_used[df_termino_used['Date'] == tomorrow_as_datetime]
    
    # Filter out bookings that don't have a time in the 'tomorrow_time' list
    df_tomorrow_filtered = df_tomorrow[~df_tomorrow['Time'].isin(tomorrow_time)]

    # Combine bookings that are today or earlier with those for tomorrow that don't match expected times
    df_till_today = pd.concat([df_till_today, df_tomorrow_filtered], ignore_index=True)

    # Optional: sort by Date and Time
    df_to_remove = df_till_today.sort_values(by=['Date', 'Time']).reset_index(drop=True)

    # Generate list of IDs to remove by appending "-remove-button" to 'Short ID' column
    to_remove_ids = [sid + "-remove-button" for sid in df_to_remove['Short ID']]
    
    return to_remove_ids
