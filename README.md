# buzzerbeater_botaki

Bot that collects stats from [buzzerbeater.com](https://www.buzzerbeater.com/), and [buzzer-manager.com](https://www.buzzer-manager.com/) and posts a roster update on specified Google Spreadsheet every Friday at 12:30 PM (Athens).

Libraries used : Selenium, BeautifulSoup, Pandas, google, gspread, PyDrive

You need to set some variables that are defined in a "secrets.py" file. These are : 

* **TEAM_URL** : buzzerbeater.com team roster URL
* **USERNAME** & **PASSWORD** : buzzerbeater.com login credentials
* **GOOGLE_CREDENTIALS_JSON** : extracted from Google Cloud Console (more info [here](https://medium.com/@jb.ranchana/write-and-append-dataframes-to-google-sheets-in-python-f62479460cf0))
* **SHEET_KEY** : ID of Google Spreadsheet (docs.google.com/spreadsheets/d/{  >>> SHEET_KEY <<< }/edit#gid={SHEET_ID})