# loading all the needed data from the config and env file

import os
import json
from pathlib import Path
from utils.styles import RED, BLUE, BG_RED, GREEN, BG_WHITE, CYAN, RESET, DATA_INPUT_ASCI, OPTIONAL_INPUT_ASCI 


def save_env_file(env_vars, filename="sensible.env"):
    """
    Saves environment variables to a .env file.

    This function takes a dictionary of environment variables (key-value pairs) 
    and writes them to a specified .env file. The default filename is 'sensible.env'. 
    Each key-value pair is written in the format: 'KEY=VALUE'.

    Args:
    - env_vars (dict): A dictionary containing the environment variables to save.
                        The keys are the variable names, and the values are their corresponding values.
    - filename (str, optional): The name of the .env file to save the variables to. 
                                Defaults to "sensible.env".

    Returns:
    - None: The function doesn't return any value. It writes the environment variables to a file.

    Example:
    ```
    env_vars = {"DB_HOST": "localhost", "DB_USER": "root", "DB_PASSWORD": "secret"}
    save_env_file(env_vars, "config.env")
    ```

    Notes:
    - The function overwrites the file if it already exists.
    - The file is saved with UTF-8 encoding to support special characters.
    """
    with open(filename, "w", encoding="utf-8") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print(f"{filename} has been saved.")




def save_config_json(config, filename="config.json"):
    """
    Saves configuration data to a JSON file.

    This function takes a dictionary containing configuration data and writes it to a 
    specified JSON file. The default filename is "config.json". The JSON data is 
    formatted with an indentation of 4 spaces for readability.

    Args:
    - config (dict): A dictionary containing the configuration data to be saved.
    - filename (str, optional): The name of the JSON file to save the configuration data to. 
                                Defaults to "config.json".

    Returns:
    - None: The function doesn't return any value. It writes the configuration data to a file.

    Example:
    ```
    config_data = {"username": "user123", "password": "securepassword"}
    save_config_json(config_data, "user_config.json")
    ```

    Notes:
    - The function overwrites the file if it already exists.
    - The file is saved with UTF-8 encoding to support special characters.
    - The JSON data is formatted for readability with an indentation of 4 spaces.
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"{filename} has been saved.")



def validate_yes_no_input(prompt):
    """
    Handles yes/no input validation.
    
    Args:
    - prompt (str): The question or prompt to display to the user.

    Returns:
    - int: Returns 1 if the user answered 'yes'/'ja', and 2 if the user answered 'no'/'nein'.
    """
    response = None
    while response not in ['ja', 'yes', 'y', 'j', 'nein', 'no', 'n', 'noo']:
        response = input(prompt).strip().lower()
        if response in ['ja', 'yes', 'y', 'j']:
            return 1
        elif response in ['nein', 'no', 'n', 'noo']:
            return 2
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

def validate_google_integration():
    """
    Handles Google Spreadsheet integration validation.
    
    Asks the user whether they want to use Google Spreadsheet features and collects
    the necessary information (URL and page name) if they choose to.

    Returns:
    - tuple: Contains three elements:
        - int: 1 if the user chooses to use Google Spreadsheet, 2 if not.
        - str or None: Google spreadsheet URL if the user chose to use it, else None.
        - str or None: Name of the page in the spreadsheet where information is stored, else None.
    """
    implement_google = 3
    while implement_google == 3:
        google_input = input(f"{RESET}Do you want to use the cool feature of informing the study lead the day before about the next day? (yes/no) ")
        
        if google_input in ["ja", "yes", "y", "j"]:
            print(f"\n{RESET}NICE BRO")
            google_spreadsheet_url = input(f"\n\nPlease paste the {GREEN}{BG_WHITE}URL to your Google Spreadsheet{RESET}: ")
            print(f"\n\n {RESET}your {GREEN}{BG_WHITE}google spreadsheet url{RESET} is: {GREEN}{BG_WHITE}", google_spreadsheet_url, f"{RESET}\n\n")
            information = input(f"\n\nPlease enter the name of the spreadsheet page where {BLUE}{BG_WHITE}information{RESET} about the study lead is located: ")
            print(f"\n\n {RESET}the name of your {BLUE}{BG_WHITE}information page{RESET} is: {BLUE}{BG_WHITE}", information, f"{RESET}\n\n")
            implement_google = 1
            return implement_google, google_spreadsheet_url, information
            
        elif google_input in ["nein", "no", "n", "noo"]:
            print("\nYOU'RE NOT USING THIS FEATURE :( PRETTY WHACK")
            implement_google = 2
            return implement_google, None, None
        
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")
            implement_google = 3  # Reset value to continue loop


def collect_all_inputs():
    """
    Collects all the necessary input data from the user.

    This function collects configuration data, such as login details, study information,
    booking list preferences, email credentials, and whether the user wants to use Google Spreadsheet features.

    Returns:
    - dict: A dictionary containing all the collected user inputs.
    """
    print(DATA_INPUT_ASCI)
    
    print("\nPlease enter the necessary configuration data:\n")
    
    # Collecting user input for various configuration parameters
    username_termino = input(f"Enter your {RED}Termino username{RESET}: ")
    print(f"\nYour Termino username is: {RED}", username_termino, f"{RESET}\n\n")

    password_termino = input(f"Enter your {RED}Termino password{RESET}: ")
    print(f"\nYour Termino password is: {RED}", password_termino, f"{RESET}\n\n")

    booking_list = input(f"Enter the name of your {BG_RED}booking list{RESET}: ")
    print(f"\nYour booking list is named: {BG_RED}", booking_list, f"{RESET}\n\n")

    mail = input(f"Enter your {BLUE}YAHOO email address{RESET}: ")
    print(f"\nYour email address is: {BLUE}", mail, f"{RESET}\n\n")

    password_mail = input("Enter your Yahoo email password: ")
    print("\nYour Yahoo email password is: ", password_mail, "\n\n")

    app_password_mail = input("Enter your app password for Yahoo email: ")
    print("\nYour app password for Yahoo email is: ", app_password_mail, "\n\n")

    study_name = input("Enter the name of your study: (e.g., Music Therapy Study) ")
    print("\nThe name of your study is: ", study_name, "\n\n")
    
    # Asking if the user wants to see current bookings
    actual_list_printing = validate_yes_no_input("\nWould you like to see all current bookings? (yes/no): ")
    
    to_send_first_mail = validate_yes_no_input("\nWould you like to see the list of people who will receive the first mail? (yes/no): ")
    
    fist_mail_recieved_printing = validate_yes_no_input("\nWould you like to see the list of people who have already received the first mail? (yes/no): ")

    # Collecting Google Spreadsheet integration details
    implement_google, google_spreadsheet_url, information = validate_google_integration()
    
    # Saving the collected data in a dictionary
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

    print("\nAll inputs have been collected! \n")
    
    return user_data


def split_data(data):
    """
    Splits the provided data dictionary into two separate dictionaries:
    - env_data: Contains environment-related keys (e.g., credentials, email).
    - config_data: Contains configuration-related keys (e.g., booking list, study name).
    
    Args:
        data (dict): The dictionary containing all the data to be split.
    
    Returns:
        tuple: A tuple containing two dictionaries:
            - env_data (dict): Contains environment-related data.
            - config_data (dict): Contains configuration-related data.
    """
    
    # Define the keys for environment-related data
    env_keys = [
        "username_termino", "password_termino",
        "mail", "password_mail", "app_password_mail",
        "google_spreadsheet_url"
    ]
    
    # Define the keys for configuration-related data
    config_keys = [
        "booking_list", "study_name",
        "actual_list_printing", "fist_mail_recieved_printing",
        "to_send_first_mail", "implement_google",
        "information"
    ]
    
    # Create dictionaries for the environment data and configuration data
    env_data = {k: data[k] for k in env_keys}
    config_data = {k: data[k] for k in config_keys}
    
    # Return the two dictionaries as a tuple
    return env_data, config_data



def main():
    """
    Main function that performs the configuration of the application by:
    1. Collecting user input data (such as credentials and configuration details).
    2. Splitting the collected data into environment variables and configuration settings.
    3. Saving the environment variables to an `.env` file.
    4. Saving the configuration settings to a `config.json` file.

    The function changes the working directory to the script's directory to ensure that 
    all file paths are relative to the script's location.

    Steps:
    1. The user is prompted to provide various pieces of information (e.g., username, password, study name, etc.).
    2. The gathered input is split into two categories: 
        - Environment-related data (e.g., credentials, email).
        - Configuration-related data (e.g., study name, mailing preferences).
    3. The environment-related data is saved into an `.env` file, while the configuration data is saved into a `config.json` file.
    4. The function prints status messages to indicate the process flow.

    This function is executed only if the script is run directly (not when imported as a module).
    """
    # Change the current working directory to the directory where the script is located
    os.chdir(Path(__file__).parent)

    # Print a message to indicate that configuration is starting
    print("Konfiguration wird ausgeführt... \n\n\n")
    
    # Collect user inputs using the collect_all_inputs function
    user_data = collect_all_inputs()
    
    # Split the user_data into environment and configuration data
    env_data, config_data = split_data(user_data)
    
    # Save the environment data to a file (env file)
    save_env_file(env_data)
    
    # Save the configuration data to a JSON file
    save_config_json(config_data)
    
    # Print a message indicating that the configuration process is complete
    print("\n\nKonfiguration abgeschlossen.")
    
    
if __name__ == "__main__":
    # If this script is executed directly, call the main function
    main()

