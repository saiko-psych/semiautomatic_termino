
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
    """
    This function attempts to retrieve the antibot key required for login on the Termino website.

    The function simulates multiple tries to fetch the antibot key by opening a web browser using Selenium WebDriver.
    It accesses the login page of Termino and attempts to extract the `antibot_key` which may be set dynamically 
    by JavaScript on the page. If the key is not successfully retrieved within the allowed number of attempts, 
    it returns an empty string.

    The function simulates human behavior by introducing random sleep intervals between actions to avoid detection.
    It also clicks randomly on elements (such as buttons) on the page during each try to further simulate human-like actions.

    The function first tries to retrieve the key multiple times within each attempt. If the key is not found, 
    it retries fetching the key for up to a maximum of 20 overall attempts. After each attempt, the browser session is closed.

    Parameters:
    None

    Returns:
    - str: The extracted antibot key, or an empty string if it couldn't be retrieved after multiple attempts.

    Example:
    The function will return the antibot key if it successfully finds it on the page. For example:
    ```
    "abcdef1234567890"
    ```

    If there was an error or it couldn't retrieve the key, it returns an empty string:
    ```
    ""
    ```

    Notes:
    - The maximum number of attempts to fetch the antibot key is set to 20 (`max_try = 20`).
    - The WebDriver used is from the Chrome browser, and the ChromeDriver is automatically managed via `ChromeDriverManager`.
    - Random sleep intervals and clicks are used to simulate human-like behavior during the process.
    """
    
    max_try = 20
    nr_try = 0
    max_inner_tries = 5 
    antibot_key = ""  # Initialize empty string to store the antibot key

    # Try to fetch the antibot key up to a maximum of max_try attempts
    while nr_try <= max_try and len(antibot_key) < 1:
        nr_try += 1
        print(f"Fetching antibot_key try Nr: {nr_try}\n\n")

        # Initialize the WebDriver service and start ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)

        # Open the login page of Termino
        driver.get("https://www.termino.gv.at/meet/de/user")

        # Wait for a random time between 3 and 12 seconds to simulate human behavior
        sleep_time = random.uniform(3, 12)
        time.sleep(sleep_time)

        inner_try = 0
        while inner_try < max_inner_tries and len(antibot_key) < 1:
            inner_try += 1
            try:
                # Versuche, den antibot_key abzurufen
                antibot_key = driver.find_element(By.NAME, "antibot_key").get_attribute("value")
                if antibot_key:
                    print(f"Antibot key gefunden: {antibot_key}")
                    break  # Wenn der antibot_key gefunden wird, breche die innere Schleife ab
            except Exception as e:
                print(f"Fehler beim Abrufen des antibot_key: {e}")
            
            # Zufällige Klicks auf der Seite simulieren (z.B. auf zufällige Buttons)
            click_elements = driver.find_elements(By.TAG_NAME, 'button')  # Suche alle Buttons
            if click_elements:
                random_button = random.choice(click_elements)  # Wähle zufällig einen Button aus
                random_button.click()
                print(f"Klicke auf einen zufälligen Button: {random_button}")

            sleep_time = random.uniform(2, 5)  # Wartezeit zwischen den Versuchen
            time.sleep(sleep_time)

        # Schließe den WebDriver nach den Versuchen
        driver.quit()
        
        # Falls antibot_key noch leer ist, versuche es nochmal
        if len(antibot_key) < 1:
            print("Kein antibot_key gefunden. Versuche es erneut...\n\n")
        
    return antibot_key


def session():
    """
    This function creates a new session to store cookies. This session is crucial as all other functions use this session 
    to maintain consistent communication with the website.

    The created session stores cookies between requests, which is necessary to keep the session active on Termino.

    Returns:
    - session_id: A `requests.Session` object that is used to perform all HTTP requests with stored cookies.

    Example:
    ```
    session_id = session()
    ```

    Note:
    - This session is used by other functions to access the website and is essential for the proper functioning of the program.
    """
    
    # Create a session to store cookies -> THIS IS ESSENTIAL -> ALL OTHERS USE THIS SESSION
    session_id = requests.Session()

    return session_id


def termino_login(env_data, antibot_key, session_id):
    """
    This function handles the login process for the Termino website using the provided credentials, antibot key, and session.

    It sends a POST request to the Termino login page with the user’s credentials and the antibot key, then checks the response
    to verify whether the login attempt was successful or not. If successful, it prints the cookies received during the login.

    Args:
    - env_data (dict): A dictionary containing the login credentials. It should have the keys 'username_termino' and 'password_termino'.
    - antibot_key (str): The antibot key obtained from the Termino login page to prevent bot detection.
    - session_id (requests.Session): The session object that will be used for the POST request to maintain session state.

    Returns:
    - logged_url (str): The current URL after attempting the login. If successful, this will be the logged-in page URL.
    - kekse (dict): A dictionary of cookies returned after a successful login.

    Example:
    ```
    logged_url, kekse = termino_login(env_data, antibot_key, session_id)
    ```

    Note:
    - The function prints various messages based on the status of the login attempt (successful or failed).
    - The `session_id` should be a valid `requests.Session` object created in advance.
    """
    
    # URL for login
    login_url = "https://www.termino.gv.at/meet/de/user"  

    # Create the login_data with the correct antibot_key
    login_data = {
        "name": env_data['username_termino'],  
        "pass": env_data['password_termino'],           
        "form_build_id": "form-IfujXxcz1-yoPlksIZ8TE_3zcwBHhodq0AAOwe5BZzk",  # This could cause issues, check if it changes
        "form_id": "user_login",
        "antibot_key": antibot_key,
        "op": "Login"
    }
    
    # 1. Send a POST request for login
    response = session_id.post(login_url, data=login_data)

    print(">>> Login request sent!\n\n")

    # 2. Check the server's response
    if response.status_code != 200:
        print(f"⚠️ Error: Server returned status code {response.status_code}!")
        print("Possible causes: incorrect URL, server issues, or too many requests blocked.")
        
    elif "nicht akzeptiert" in response.text or "Haben Sie Ihr Passwort vergessen?" in response.text:
        print("❌ The provided login credentials are incorrect!")
        print("Please check your login data!")
        
    elif response.url == login_url:
        print("🚨 Login failed! The URL is still the login page.\n\n")
        print("This means the server did not log us in.\n\n")
        print("Possible causes: incorrect username/password or missing additional parameters.\n\n")

    elif "Ansicht" in response.text or "Verlauf" in response.text:
        kekse = session_id.cookies.get_dict()
        # Display cookies after login
        print("Cookies after login = ", kekse, "\n")
        print("✅ Login successful!\n\n")
        logged_url = response.url
        print(f"Current URL after login: {logged_url}")

    else:
        print("❓ Unexpected response received.\n\n")
        print("Here are the first 500 characters of the response to see what's going on:\n")
        print(response.text[:500])

    return logged_url, kekse



def bookinglist_url(session_id, logged_url):
    """
    This function retrieves the booking list URL from the logged-in page on the Termino website.

    It sends a GET request to the provided logged-in URL using the session, then searches the HTML response for the booking 
    list URL using a regular expression. If the URL is found, it is returned; otherwise, an error message is printed.

    Args:
    - session_id (requests.Session): The session object used to maintain the login session while making the request.
    - logged_url (str): The URL of the logged-in page from where the booking list URL needs to be extracted.

    Returns:
    - str: The booking list URL if found, or an empty string if not found.

    Example:
    ```
    bookinglist_url(session_id, logged_url)
    ```

    Note:
    - The function uses a regular expression to search for the booking list URL (`https://www.termino.gv.at/meet/de/user/<user_id>/mybookings`).
    - The function prints the booking list URL if found or an error message if the URL is not found.
    """
    
    r = session_id.get(logged_url)

    # Assume r.text contains the HTML content
    text = r.text  

    # Regex to find the booking list URL
    match = re.search(r'<a href="(https://www\.termino\.gv\.at/meet/de/user/\d+/mybookings)"', text)

    if match:
        buchungslisten_url = match.group(1)
        print("Found booking list URL:", buchungslisten_url, "\n\n")
    else:
        print("No booking list URL found... \n\n")
        
    return buchungslisten_url

  
  
    
def get_buchungsliste_nummer(session_id, buchungslisten_url, config_data):
    """
    This function retrieves the booking list number from the Termino website based on the provided booking list name.

    It sends a GET request to the given `buchungslisten_url` and searches the HTML content for a specific link
    containing the booking list name from the `config_data`. If the booking list is found, it extracts and returns
    the booking list number. If the booking list is not found, the user is prompted to either provide a new name
    for the booking list or exit the program.

    Args:
    - session_id (requests.Session): The session object used to maintain the login session while making the request.
    - buchungslisten_url (str): The URL of the booking list page.
    - config_data (dict): Configuration data that includes the name of the booking list to search for.

    Returns:
    - str: The booking list number if found, or prompts the user to input a new name if not found.

    Example:
    ```
    get_buchungsliste_nummer(session_id, buchungslisten_url, config_data)
    ```

    Note:
    - The function searches for a link containing the name of the booking list and extracts the booking list number.
    - If the list is not found, it asks the user for a new name or to exit.
    - The function ensures the user provides a valid response and repeats the process if necessary.
    """
    
    r = session_id.get(buchungslisten_url)

    # Assume r.text contains the HTML content
    booking_text = r.text 

    # Regex pattern to find the number before the specified name
    pattern = rf'<a href="/meet/de/b/[a-f0-9]+-(\d+)">{config_data['booking_list']}</a>'

    # Perform search
    match = re.search(pattern, booking_text)

    if match:
        buchungsliste_nummer = match.group(1)
        print("Found number:", buchungsliste_nummer, "\nBooking list found :D\n\n")
    else:
        print(f"\n\nNo number found for booking list {config_data['booking_list']}.\nIt seems no booking list exists with this name!")
        
        option = 3
        # Option to enter a new name or exit the program
        while option == 3: 
            answer = input("\n\nWould you like to enter a different name for the booking list? (yes/no): ").lower()

            if answer in ["yes", "y", "ja", "j"]:
                booking_list_new = input("\nPlease enter a new name for the booking list: ")
                
                # Regex pattern to find the number before the new specified name
                pattern_new = rf'<a href="/meet/de/b/[a-f0-9]+-(\d+)">{booking_list_new}</a>'

                # Search with the new name
                match = re.search(pattern_new, booking_text)

                if match:
                    buchungsliste_nummer = match.group(1)
                    print(f"Found number: {buchungsliste_nummer}\nBooking list found :D\n\n")
                    option = 1
                else:
                    print(f"No number found for booking list '{booking_list_new}'.\n\n")
                    option = 3
                
            elif answer in ["no", "n", "nein"]:
                print("You chose 'No'! \nThe program will now exit!\n\n")
                option = 2
                
            else:
                print("Invalid input. Please enter 'yes' or 'no'.\n\n")
                option = 3  # Reset value to continue the loop
    
    return buchungsliste_nummer

        


def termino_csv_download(session_id, config_data, buchungsliste_nummer):
    """
    This function downloads the booking list in CSV format from the Termino website.

    It constructs the URL for downloading the CSV file based on the provided booking list number (`buchungsliste_nummer`) 
    and uses the session object to send a GET request. If the request is successful, it saves the CSV file to the specified 
    path on the local system. The path is determined using the provided booking list name from `config_data`.

    Args:
    - session_id (requests.Session): The session object used for maintaining the login session during the request.
    - config_data (dict): Configuration data that includes the name of the booking list to be used in the filename.
    - buchungsliste_nummer (str): The unique identifier for the booking list.

    Returns:
    - str: The path where the CSV file has been saved.

    Example:
    ```
    termino_csv_download(session_id, config_data, buchungsliste_nummer)
    ```

    Notes:
    - The function constructs the download URL using the booking list number (`buchungsliste_nummer`) and sends a GET request to it.
    - The file is saved under the directory `"data"` with the name `<booking_list>_booking_list.csv`.
    - If the download is successful, it writes the file to the disk; otherwise, an error message is printed.
    """
    
    # Construct the download URL for the CSV file
    download_url = f"https://www.termino.gv.at/meet/de/node/{buchungsliste_nummer}/export"

    # Path where the CSV file will be saved
    actual_booking_list_csv = os.path.join("data", f"{config_data['booking_list']}_booking_list.csv")

    # Download the file
    csv_response = session_id.get(download_url)
    if csv_response.status_code == 200:
        with open(actual_booking_list_csv, "wb") as file:
            file.write(csv_response.content)
        print(f"CSV file {config_data['booking_list']} has been successfully downloaded and saved to {actual_booking_list_csv}\n\n")
    else:
        print(f"Error downloading the CSV file. Status code: {csv_response.status_code}")
        
    return actual_booking_list_csv

        
        

def termino_bookings(session_id, editing_url):
    """
    This function retrieves booking data from the Termino website by parsing the editing page's HTML content.

    It sends a GET request to the provided URL, which represents the page where bookings can be edited. The function
    uses BeautifulSoup to parse the HTML and extract information related to the booking time, place, and date. It then 
    compiles the extracted data into a structured DataFrame.

    The function identifies relevant input elements on the page that match a pattern and contains specific booking information. 
    The data is extracted, processed, and returned as a pandas DataFrame.

    Args:
    - session_id (requests.Session): The session object used for maintaining the login session.
    - editing_url (str): The URL for the editing page of the Termino booking system.

    Returns:
    - pd.DataFrame: A DataFrame containing the extracted booking data, including:
        - Short ID
        - Place (Booking location/number)
        - Time
        - Date

    Example:
    ```
    df_termino = termino_bookings(session_id, editing_url)
    ```

    Notes:
    - The function uses regex patterns to identify time-related inputs and matches them to the booking data.
    - The function builds a DataFrame from the extracted booking information for easy processing.
    """
    
    # Send GET request to the editing page
    r = session_id.get(editing_url)
    
    # Parse the HTML of the response
    editing_text = r.text
    soup = BeautifulSoup(editing_text, "html.parser")

    # Regex pattern to match time format (HH:MM)
    time_pattern = re.compile(r"^\d{2}:\d{2}$")

    # Find all relevant input elements for the booking time
    inputs = soup.find_all("input", {"id": lambda x: x and "edit-field-flagcollection" in x})
    
    # Filter matching inputs with valid time format
    matching_inputs = [inp for inp in inputs if time_pattern.match(inp.get("value", ""))]
    
    # Extract short IDs (first part of the ID) for each matching input
    short_ids = []
    for t in matching_inputs:
        full_id = t["id"]
        parts = full_id.split("-")
        short_id = "-".join(parts[:5])  # e.g., edit-field-flagcollection-und-29
        short_ids.append(short_id)
    
    # Extract place numbers (part after 'und')
    numbers = []
    for t in matching_inputs:
        full_id = t["id"]
        parts = full_id.split("-")
        if len(parts) >= 5:
            number = parts[4]  # This is the number after 'und'
            numbers.append(number)
    
    # Suffix for the date fields in the HTML
    date_suffix = "-field-optiondate-und-0-value-datepicker-popup-0"
    
    # Generate full date IDs
    date_ids = [short_id + date_suffix for short_id in short_ids]
    
    # Extract the date values for each entry
    date_values = []
    for date_id in date_ids:
        date_input = soup.find("input", {"id": date_id})
        if date_input:
            date_values.append(date_input.get("value", None))
        else:
            date_values.append(None)
    
    # Compile the extracted data into a structured list of dictionaries
    data = []
    for i in range(len(matching_inputs)):
        data.append({
            "Short ID": short_ids[i],
            "Place": numbers[i],
            "Time": matching_inputs[i]["value"],
            "Date": date_values[i]
        })
    
    # Convert the data into a pandas DataFrame
    df_termino = pd.DataFrame(data)
    
    df_termino['Date'] = pd.to_datetime(df_termino['Date'], format="%d.%m.%Y", errors='coerce')

    return df_termino

    
   


def id_to_remove(buttons_list, removed_ids):
    """
    This function processes a list of button IDs, removes one from the list, and adjusts the remaining button IDs.

    The function removes the first button ID from the list, updates the indices of the remaining buttons, 
    and appends the `removed_ids` counter to the button IDs. The function ensures the list remains continuous
    without gaps in indices after a button is removed.

    Args:
    - buttons_list (list): A list of button IDs, where each button ID follows a specific naming pattern that includes an index.
    - removed_ids (int): A counter used to keep track of how many IDs have been removed so far, which is appended to updated button IDs.

    Returns:
    - tuple: A tuple containing three elements:
        - `removed_button_id` (str): The ID of the button that was removed.
        - `updated_buttons` (list): A list of updated button IDs, with adjusted indices.
        - `removed_ids` (int): The updated counter reflecting the number of removed buttons.

    Example:
    ```
    removed_button_id, updated_buttons, removed_ids = id_to_remove(buttons_list, removed_ids)
    ```

    Notes:
    - The function assumes that the button IDs follow a pattern like `button-<something>-<index>`, where the index is an integer.
    - The updated button IDs are adjusted so that there are no gaps in the indices after a button is removed.
    """
    
    # Remove the first button ID from the list
    removed_button_id = buttons_list.pop(0)
    print(f"Button ID to be removed: {removed_button_id}")
    
    # Extract the index of the removed button from the ID
    removed_index = int(removed_button_id.split('-')[4])
    print(f"Removed Index: {removed_index}")
    
    updated_buttons = []

    # Adjust the button IDs in the remaining list
    for i, button in enumerate(buttons_list):
        button_index = int(button.split('-')[4])  # Get the index from the current ID

        # Skip the removed element
        if button_index == removed_index:
            continue  
        
        # Adjust the indices of remaining buttons
        if button_index > removed_index:
            new_index = button_index - 1
            updated_button = button.replace(f"-{button_index}-", f"-{new_index}-")
        else:
            updated_button = button

        # Update the button ID by appending the removed_ids counter
        if removed_ids == 0:
            updated_button += "--" + str(removed_ids + 2)
        else:
            updated_button = re.sub(r'\d+$', str(removed_ids + 2), updated_button)
        
        updated_buttons.append(updated_button)
        
    removed_ids = removed_ids + 1
    
    return removed_button_id, updated_buttons, removed_ids



def remove_all_buttons(driver, buttons_list):
    """
    This function iterates over a list of button IDs, clicks each button to remove it, 
    and ensures that all buttons are processed one by one.

    The function will repeatedly call `id_to_remove` to update the button list and remove the first button in the list. 
    For each button, it waits for the button to be clickable, clicks it, and waits for a random time to simulate human behavior. 
    The process continues until all buttons have been removed.

    Args:
    - driver (WebDriver): The Selenium WebDriver instance used to interact with the web page.
    - buttons_list (list): A list of button IDs to be removed from the web page.

    Returns:
    - None: The function performs the action of removing buttons and does not return any value.

    Example:
    ```
    remove_all_buttons(driver, buttons_list)
    ```

    Notes:
    - The function assumes that the buttons are identified by unique IDs that can be clicked via Selenium's WebDriver.
    - A random sleep time between 2 and 10 seconds is used to simulate a more human-like interaction and avoid detection.
    - The `id_to_remove` function is used to manage the removal of buttons and the adjustment of button indices in the list.
    """
    removed_ids = 0

    # Iterate over the list of buttons and remove them one by one
    while buttons_list:
        removed_button_id, buttons_list, removed_ids = id_to_remove(buttons_list, removed_ids)

        try:
            # Wait for the button to be clickable and click it
            remove_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, removed_button_id))
            )
            remove_button.click()
            print(f"Button with ID '{removed_button_id}' was clicked.")
        except Exception as e:
            print(f"Error while clicking button '{removed_button_id}': {e}")
            break

        # Wait for a random period to simulate human behavior
        sleep_time = random.uniform(2, 10)
        print(f"Waiting {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)

    print("All buttons have been removed.")

    

def deleting_bookings(kekse, editing_url, to_remove_ids, today):
    """
    This function deletes booking entries from the Termino platform by clicking on the appropriate buttons to remove them.
    It simulates human-like interactions with the website using Selenium WebDriver and cookies to maintain the session.

    The function uses the provided cookies to ensure that the user is logged in and interacts with the Termino website. It clicks buttons to remove the bookings and then clicks the "Save" button to confirm the changes. Finally, the WebDriver session is closed.

    Args:
    - kekse (dict): A dictionary of cookies, where each key-value pair corresponds to a cookie name and its value.
    - editing_url (str): The URL of the page where bookings need to be deleted.
    - to_remove_ids (list): A list of button IDs that need to be clicked to remove the bookings.
    - today (str): The date when the deletions are being made, used for logging.

    Returns:
    - None: The function performs the action of deleting bookings but does not return any value.

    Example:
    ```
    deleting_bookings(cookies, editing_url, button_ids, "2025-04-30")
    ```

    Notes:
    - The function relies on the Selenium WebDriver to interact with the webpage.
    - Cookies are added to maintain the session, so the user remains logged in during the process.
    - The function waits for elements to load and ensures that the necessary buttons are clicked.
    - After the bookings are deleted, the "Save" button is clicked to apply the changes.
    """
    # Convert the cookies into the format expected by Selenium
    cookies = [{'name': key, 'value': value, 'domain': '.termino.gv.at', 'path': '/'} for key, value in kekse.items()]

    # Use WebDriverManager to start the ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    # Open the editing page (ensure that you are already logged in before visiting this URL)
    driver.get(editing_url)

    # Wait a short time for the page to load
    time.sleep(2)

    # Add the cookies to the WebDriver
    for cookie in cookies:
        driver.add_cookie(cookie)

    # Refresh the page so the cookies take effect
    driver.refresh()

    # Wait to ensure the page has loaded with the cookies applied
    time.sleep(4)

    # Call the function to remove the buttons
    remove_all_buttons(driver, to_remove_ids)

    # Wait to ensure all interactions are processed
    time.sleep(3)

    # Wait until the Save button is visible and click it
    try:
        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "edit-submit"))
        )
        save_button.click()
        print("Save button clicked.")
        print(f"\n\nAll bookings for today, {today}, have been deleted from Termino.")
    except Exception as e:
        print(f"Error while clicking the Save button: {e}")

    print("\n\nAll bookings to be deleted have been removed from Termino!\n\n")

    # Optional: Wait to ensure the Save button has been processed
    time.sleep(3)

    # Close the WebDriver session
    driver.quit()



################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################


          

def new_appointment(datum_zu_eintragen, zeit, place, short_id, driver, more_app_index):
    """
    This function automates the process of adding a new appointment (or scheduling) on the Termino platform using Selenium WebDriver.
    It interacts with the page's form fields, including date, time, and place, and inserts the specified values. 
    The function also clicks the "More" button to add another entry if needed.

    Args:
    - datum_zu_eintragen (str): The date to be entered for the appointment.
    - zeit (str): The time to be entered for the appointment.
    - place (int): The place (position) to be set for the appointment.
    - short_id (str): The ID of the element (used to identify the form field inputs for the specific appointment).
    - driver (webdriver.Chrome): The Selenium WebDriver instance that interacts with the Termino website.
    - more_app_index (int): An index to handle multiple appointments. If it's 1, it selects the first "More" button; otherwise, it constructs the appropriate button ID based on the index.

    Returns:
    - int: The updated `more_app_index` after the new appointment is added.

    Example:
    ```
    new_appointment("2025-04-30", "15:00", 2, "edit-field-flagcollection-und-1", driver, 1)
    ```

    Notes:
    - The function assumes that the necessary fields (date, time, and place) are available and interactable on the page.
    - The function waits for the necessary elements to be clickable before interacting with them to ensure smooth operation.
    - The function modifies the `place` to account for an off-by-one index, and custom logic is applied for special cases of place values (e.g., 1 becomes 11, 11 becomes 1111).
    - The function supports multiple appointments by incrementing the `more_app_index`.
    """
    
    if more_app_index == 1:
        button_id = "edit-field-flagcollection-und-add-more"
    else:
        button_id = f"edit-field-flagcollection-und-add-more--{more_app_index}" 
    
    try:
        more_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, button_id))
        )
        more_button.click()
        print("More Button was clicked.")
    except Exception as e:
        print(f"Error while clicking the More button: {e}")
    
    time.sleep(2)
       
    try: 
        date_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"{short_id}-field-optiondate-und-0-value-datepicker-popup-0"))
        )
        date_field.click()
        print(f"{datum_zu_eintragen} was inserted")
        # Enter the date
        date_field.send_keys(datum_zu_eintragen)
        
    except Exception as e:
        print(f"Error while entering the date {datum_zu_eintragen}: {e}")
    
    time.sleep(2)   
    
    try:
        time_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"{short_id}-field-optiondate-und-0-value-timeEntry-popup-1"))
        )
        time_field.click()
        print(f"{zeit} was inserted")
        
        time_field.send_keys(zeit)
        
    except Exception as e:
        print(f"Error while entering the time {zeit}: {e}")
        
    time.sleep(2)   
    
    try:
        place_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, f"{short_id}-weight"))
        )
        place_field.click()
        print(f"The appointment was inserted at {place - 1}. position")
        
        insert_place = int(place - 1)
        
        if insert_place == 1:
            insert_place = 11
        elif insert_place == 11:
            insert_place = 1111
        
        print(insert_place)
            
        place_field.send_keys(insert_place)
        
        time.sleep(2)  
        
    except Exception as e:
        print(f"Error while entering the place: {e}")
    
    more_app_index += 1
    
    print(f"New appointment: ({datum_zu_eintragen} {zeit}) has been created and inserted as the {place-1}. appointment at Termino.\n\n")
    
    return more_app_index


def insert_new_app_in_termino(kekse, editing_url, df_kombiniert):
    """
    This function automates the process of inserting new appointments into the Termino platform.
    It interacts with the page using Selenium WebDriver, adds the provided cookies, and then inserts
    appointments based on the data from a DataFrame (`df_kombiniert`). The function supports multiple appointments
    and ensures that the correct fields (date, time, place, and short ID) are entered.

    Args:
    - kekse (dict): A dictionary containing the cookies required for the session. The keys are cookie names, 
                    and the values are the corresponding cookie values.
    - editing_url (str): The URL of the Termino page where appointments are to be added.
    - df_kombiniert (pandas.DataFrame): A DataFrame containing appointment data. It should have columns for 
                                         'Date', 'Time', 'Place', 'Short ID', and a boolean 'Neuer_Termin' 
                                         indicating whether a new appointment should be added.

    Returns:
    - None: The function doesn't return any value. It performs the action of inserting appointments 
            into Termino and handles the WebDriver interaction.

    Example:
    ```
    insert_new_app_in_termino(cookies, "https://www.termino.gv.at/editing_page_url", df_appointments)
    ```

    Notes:
    - The function assumes that the cookies provided are valid and that the page is correctly loaded before interacting.
    - It waits for the "Zeilen mittels numerischer Gewichtung" button to be clickable before proceeding.
    - The function loops through all rows in the DataFrame where the `Neuer_Termin` column is `True` and adds appointments accordingly.
    - After adding the appointments, it clicks the "Save" button to submit the changes.
    """
    
    # Convert cookies to the format expected by Selenium
    cookies = [{'name': key, 'value': value, 'domain': '.termino.gv.at', 'path': '/'} for key, value in kekse.items()]

    # Start the Selenium WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    # Open the editing URL
    driver.get(editing_url)

    # Wait briefly to allow the page to load
    time.sleep(2)

    # Add cookies to the driver session
    for cookie in cookies:
        driver.add_cookie(cookie)

    # Refresh the page to apply the cookies
    driver.refresh()

    # Wait for the button to sort rows numerically and click it
    try:
        numbers_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[title="Zeilen mittels numerischer Gewichtung ordnen statt mit Drag-and-Drop"]'))
        )
        numbers_button.click()
        print("numbers_button was clicked.")
    except Exception as e:
        print(f"Error while clicking the numbers_button: {e}")

    time.sleep(2)

    # Initialize the index for more appointments
    more_app_index = 1
    
    # Loop through the DataFrame and add appointments
    for _, row in df_kombiniert[df_kombiniert['Neuer_Termin'] == True].iterrows():
        datum_zu_eintragen = row['Date']
        zeit = row['Time']
        place = row['Place']
        short_id = row['Short ID']

        # Call the function to add a new appointment
        new_appointment(datum_zu_eintragen, zeit, place, short_id, driver, more_app_index)

    # Wait to ensure all interactions have been processed
    time.sleep(5)

    # Wait for the "Save" button to be clickable and click it
    try:
        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "edit-submit"))
        )
        save_button.click()
        print("Save button was clicked.")
        print("\n\nAll appointments have been added in Termino!")
    except Exception as e:
        print(f"Error while clicking the Save button: {e}")

    # Optionally, wait for a few seconds to ensure the save operation is complete
    time.sleep(5)

    # Close the WebDriver session
    driver.quit()




