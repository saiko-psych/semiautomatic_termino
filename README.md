# semiautomatic_termino


## HELLO PEOPLES 

This Python script is designed to help manage study participants more efficiently and reduce dropout rates. It integrates with the website "Termino.gv.at", a platform used to create booking lists and polls.

In many research studies, managing a large number of participants and coordinating multiple study leaders can quickly become time-consuming and chaotic. This script aims to simplify and automate this process.

Key features include:

Automated Reminder Emails: Participants receive reminder emails one day before their scheduled appointment, helping to minimize no-shows.

Automatic Cleanup: Past appointments are automatically removed to keep the system organized.

Google Sheets Integration: An optional extension allows study leaders to enter available time slots into a shared Google Spreadsheet. When a study leader signs up for a time slot, the slot is automatically offered on Termino. Additionally, study leaders receive a notification one day before their scheduled sessions, informing them about the number of participants expected.

This tool significantly reduces administrative workload and ensures smoother coordination in studies with many participants and study leaders.


## Requirements

* Termino account and an existing booking list
* yahoo-email account + your APP-key
* python 3.13 (manual installation)


### Limitations:
* currently only running on windows (i guess -> please try it on other devices and inform me about your errors)
* currently only works with a yahoo email 😞
* no full automation yet 😢 -> you have to run the script every day 
  * or you could make a task scedular yourself ;)



\___________________________________________________________________________\_

# HOW TO USE

\___________________________________________________________________________\_

1. download everything
2. create a new virtual environment with Python 3.13.2
3. runt setup.py (e.g. python setup.py)
4. run config.py
5. run main.py once every day without needing to change anything else 😃




If you have any questions or suggestions for improvement please send me an email:

david.matischek@edu.uni-graz.at

I used python 3.13.2 for this so please let me know if you have problems when running it in python 3.10 ect.
