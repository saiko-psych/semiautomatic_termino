import os
import time
from pathlib import Path


os.chdir(Path(__file__).parent) #das vill hinfällig wenn man das skript eh über das terminal aufruft



from utils.styles import TERMINO_SCRIPT_ASCI, DELETING_ASCI, EXTENSIONS
from utils.preperation import (
    load_config, 
    load_env_data, 
    config_text, 
    booking_list_preperation, 
    date_creation, 
    tomorrow_today_data, 
    get_ids_to_remove
    )
from utils.web_interaction import (
    termino_antibot_key,
    session,
    termino_login,
    bookinglist_url,
    get_buchungsliste_nummer,
    termino_csv_download,
    termino_bookings,
    deleting_bookings,
    insert_new_app_in_termino
)
from utils.mailing import first_message, reminder, vl_mail, termin_missing
from utils.extensions import download_g_s, google_dp, data_prep, data_prep_2








def main():

    os.chdir(Path(__file__).parent)
    
    
    print(TERMINO_SCRIPT_ASCI)
    time.sleep(2)
    
    today, tomorrow, today_as_datetime, tomorrow_as_datetime = date_creation()
    
    env_data = load_env_data()  
    config_data = load_config()
    
    config_text(config_data,env_data)
    
    antibot_key = termino_antibot_key()
    session_id = session()
    logged_url, kekse = termino_login(env_data, antibot_key, session_id)
    booking_url = bookinglist_url(session_id, logged_url)
    

    buchungsliste_nummer = get_buchungsliste_nummer(session_id, booking_url, config_data)
    actual_booking_list_csv = termino_csv_download(session_id, config_data, buchungsliste_nummer)
    
    date_prob, name_prob, email_prob, date_first_mail_sended, name_first_mail_sended, email_first_mail_sended, to_send_name, to_send_mail, to_send_date = booking_list_preperation(actual_booking_list_csv, config_data)
    first_message(env_data, config_data, to_send_name, to_send_mail, to_send_date)
    
    tomorrow_name, tomorrow_email, tomorrow_date, tomorrow_time, today_name, today_email, today_date = tomorrow_today_data(date_prob, name_prob, email_prob, tomorrow, today)
    reminder(env_data, config_data, tomorrow_name, tomorrow_email, tomorrow_date)
    
    
    print(DELETING_ASCI)
    time.sleep(2)
    
    editing_url = f"https://www.termino.gv.at/meet/de/node/{buchungsliste_nummer}/edit"
    df_termino = termino_bookings(session_id, editing_url)
    to_remove_ids = get_ids_to_remove(df_termino, today_as_datetime, tomorrow_as_datetime, tomorrow_time)
    deleting_bookings(kekse, editing_url, to_remove_ids, today)
    
    
    print(EXTENSIONS)
    time.sleep(2)
    
    if config_data['implement_google'] ==1:
        download_g_s(env_data, config_data) 
        name_vl, email_vl, date_vl, time_vl = google_dp(tomorrow)
        print("tomorrow_time: ", tomorrow_time)
        print("name_vl: ", name_vl)
        print("email_vl: ", email_vl)
        print("date_vl: ", date_vl)
        print("time_vl: ", time_vl)
        vl_mail(env_data, config_data, name_vl, email_vl, time_vl, tomorrow_time, tomorrow_name, tomorrow_email, tomorrow)
    
    differenz_termino, zukuenftige_ereignisse = data_prep(tomorrow, df_termino)
    if len(differenz_termino["Place"]) > 0:
        termin_missing(env_data, config_data, differenz_termino)
        
    df_kombiniert = data_prep_2(zukuenftige_ereignisse, df_termino)
    insert_new_app_in_termino(kekse, editing_url, df_kombiniert)
    
    
if __name__ == "__main__":
    main()
    
    







