from secrets import *

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from bs4 import BeautifulSoup
import pandas as pd
import json
import datetime

import gspread
from gspread_dataframe import set_with_dataframe
from gspread_formatting import set_column_widths, set_frozen, cellFormat, color, format_cell_range
from google.oauth2.service_account import Credentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# these have to be global variables, so that they are visible to both functions defined below
s_pos, f_pos = 'G', 'K' # positions PG - SG - SF - PF - C
s_os, f_os, s_is, f_is = 'L','Q','R','U' # skills outside/inside

def process_deez_(players, driver):
	# create a players dataframe, where we will store all this info
	players_df = pd.DataFrame(columns=['Player','Age','Potential','Salary','Game Shape',
									   'dominant','PG','SG','SF','PF','C',
									   'Jump Shot','Jump Range','Outside Def.','Handling','Driving','Passing',
									   'Inside Shot','Inside Def.','Rebounding','Shot Blocking',
									   'Stamina','Free Throw','Experience',
									   'Skill Outside','Skill Inside','Skill Points'])
	cnt=2
	for player in players:
		player_name = player.find('div', attrs={'style':'float: left; '}).find('a').get_text().replace(' ',' ')
		features = player.find('table')

		# get left side of 'features' table (salary, age, potential, game shape)
		left_features = features.find('table', attrs={'style':'margin: 1px;'}).find_all('tr')
		# it means that a match is ongoing (or injured player), so we have to get second "row" of table to move on
		if(len(left_features)>1):
			left_features = left_features[1]
		# parse it as text and use this ugly "split(blahblah)", then "split(blohbloh)"
		left_features = " ".join(left_features.find('td').get_text().split())

		salary = "".join(left_features.split(" Role:")[0].split("$ ")[1].split(" "))
		age = left_features.split("Height: ")[0].split("Age: ")[1].split(' ')[0]
		potential = left_features.split(" Game Shape:")[0].split("Potential: ")[1]
		game_shape = left_features.split(" Game Shape: ")[1]

		# now we are ready to move on to the "skills" side
		right_features = features.find('table', attrs={'style':'margin: 1px; padding: 0px;'}).find_all('tr')
		skills_list = []
		# this is how it will look like
		# skills_list = ["Jump Shot", "Jump Range", "Outside Def.", "Handling", "Driving", "Passing", 
		#                "Inside Shot", "Inside Def.", "Rebounding", "Shot Blocking", 
		#                "Stamina", "Free Throw", "Experience"]

		for row in right_features:
			row_feats = row.find_all('a')
			for r in row_feats:
				r = str(r).split('title="')[1].split('"')[0]
				skills_list.append(r)

		# we need this for the evaluation. it's the numerical potential (not text, like we parsed it before)
		potential_val = str(features.find('table', attrs={'style':'margin: 1px;'}).find_all('tr')).split('Potential:')[1].split('">')[0].split('title="')[1]

		buzzer_manager_url = 'https://www.buzzer-manager.com/api/getEstimatedSalary.php?'+ \
							 'potential=' + potential_val + '&JumpShot=' + skills_list[0] + '&JumpRange=' + skills_list[1] + \
							 '&perimDef=' + skills_list[2] + '&handling=' + skills_list[3] + '&driving=' + skills_list[4] + \
							 '&passing=' + skills_list[5] + '&insideShot=' + skills_list[6] + '&insideDef=' + skills_list[7] + \
							 '&rebound=' + skills_list[8] +'&shotBlock=' + skills_list[9]
		driver.get(buzzer_manager_url)
		response = driver.execute_script("return document.documentElement.outerHTML")
		response = json.loads(BeautifulSoup(response,'html.parser').get_text())
		# convert return of buzzer-manager evaluator in dictionary format (json)
		# and keep only "evaluation" from the available
		response = response['results']['evaluation']
		pg_rating = response['m']
		sg_rating = response['ar']
		sf_rating = response['as']
		pf_rating = response['af']
		c_rating = response['p']

		# keep top two positions of player, according to its ratings
		# where skills columns start and finish
		dominant_position = '=CONCAT(CONCAT(INDEX($'+s_pos+'$1:$'+f_pos+'$1,0,MATCH(  MAX($'+s_pos+str(cnt)+':$'+f_pos+str(cnt)+'),  $'+s_pos+str(cnt)+':$'+f_pos+str(cnt)+',0)),", "), \
											INDEX($'+s_pos+'$1:$'+f_pos+'$1,0,MATCH(LARGE($'+s_pos+str(cnt)+':$'+f_pos+str(cnt)+',2),$'+s_pos+str(cnt)+':$'+f_pos+str(cnt)+',0)))'

		# no we are ready to pack our data and append it as one row to our dataframe
		feats_list = []
		feats_list.append(player_name)
		feats_list.append(age)
		feats_list.append(potential)
		feats_list.append(salary)
		feats_list.append(game_shape)

		feats_list.append(dominant_position)
		feats_list.append(pg_rating)
		feats_list.append(sg_rating)
		feats_list.append(sf_rating)
		feats_list.append(pf_rating)
		feats_list.append(c_rating)

		for skill in skills_list:
			feats_list.append(skill)

		feats_list.append('=SUM('+s_os+str(cnt)+':'+f_os+str(cnt)+')')
		feats_list.append('=SUM('+s_is+str(cnt)+':'+f_is+str(cnt)+')')
		feats_list.append('=SUM('+s_os+str(cnt)+':'+f_is+str(cnt)+')')
		players_df.loc[len(players_df)] = feats_list
		cnt+=1

	print('Roster skills and extra data are obtained successfully from buzzerbeater.com!')
	return players_df

# Very useful : https://medium.com/@jb.ranchana/write-and-append-dataframes-to-google-sheets-in-python-f62479460cf0
# Everything in this tutorial is a prerequisite for the upload of data to Google Spreadsheets to be successful

def buzzer2spreadsheet(players_df):
	scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
	credentials = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_JSON, scopes=scopes)
	gc = gspread.authorize(credentials)
	gauth = GoogleAuth()
	drive = GoogleDrive(gauth)

	# open Google Sheet of players database
	gs = gc.open_by_key(SHEET_KEY)

	# create a new sheet in the file, for this week's update
	s_date = datetime.date.today() + datetime.timedelta(days=1)
	f_date = datetime.date.today() + datetime.timedelta(days=7)
	curr_title = s_date.strftime("%d/%m/%Y") + ' - ' + f_date.strftime("%d/%m/%Y")
	curr_worksheet = gs.add_worksheet(title=curr_title, rows=30, cols=25)

	# pass data from the newly generated players_df
	curr_worksheet.clear()
	set_with_dataframe(worksheet = curr_worksheet, dataframe=players_df, 
					   include_index=False, include_column_header=True) #, resize=True)

	# do some formatting work now (freeze rows/columns, set widths, set bold text, set colors)
	set_frozen(curr_worksheet, rows=1, cols=1)
	set_column_widths(curr_worksheet, [('A', 160), ('B', 45), ('C', 105), ('D', 75),  ('E', 88),  ('F', 75), ('G:K', 50), ('L:AA', 95)])

	curr_worksheet.format('A1:AA1', {'textFormat': {'bold': True}})
	curr_worksheet.format('A1:A', {'textFormat': {'bold': True}})
	curr_worksheet.format('B1:C', {'horizontalAlignment': 'CENTER'}) # columns B and C
	curr_worksheet.format('E1:F', {'horizontalAlignment': 'CENTER'}) # columns E and F

	fmt1 = cellFormat(backgroundColor=color(217/256,234/256,211/256), horizontalAlignment='CENTER') # light green 3
	fmt2 = cellFormat(backgroundColor=color(221/256,126/256,107/256), horizontalAlignment='CENTER') # light red berry 2
	fmt3 = cellFormat(backgroundColor=color(255/256,242/256,204/256), horizontalAlignment='CENTER') # light yellow 3
	fmt4 = cellFormat(backgroundColor=color(201/256,218/256,248/256), horizontalAlignment='CENTER') # cornflower blue 3
	fmt5 = cellFormat(backgroundColor=color(244/256,204/256,204/256), horizontalAlignment='CENTER') # light red 3

	format_cell_range(curr_worksheet, 'A1:E1', fmt1)
	format_cell_range(curr_worksheet, 'F1', fmt2)
	format_cell_range(curr_worksheet,  s_pos+'1:' + f_pos+'1', fmt2)
	format_cell_range(curr_worksheet,  s_os+'1:' + f_os+'1', fmt3)
	format_cell_range(curr_worksheet,  s_is+'1:' + f_is+'1', fmt4)
	format_cell_range(curr_worksheet, 'V1:X1', fmt5)
	format_cell_range(curr_worksheet, 'Y1:AA1', fmt1)

	print('Roster for dates ' + curr_title + ' is uploaded to Google Spreadsheets successfully!')

if __name__ == '__main__':
	# create a Firefox driver and open page
	options = FirefoxOptions()
	options.binary_location = '/home/pmpakos/snap/firefox/firefox'
	options.add_argument("--headless")
	WINDOW_SIZE = "1920,1080"
	options.add_argument("--window-size=%s" % WINDOW_SIZE)
	driver = webdriver.Firefox(options=options)
	driver.get(TEAM_URL)

	# Login to buzzerbeater with necessary credentials
	f1 = driver.find_element("id", "txtLoginName") 
	f1.send_keys(USERNAME)
	f2 = driver.find_element("id", "txtPassword") 
	f2.send_keys(PASSWORD)
	driver.find_element("name", "ctl00$btnLogin").click()

	# get HTML of the opened page
	res = driver.execute_script("return document.documentElement.outerHTML")
	# parse the html using beautiful soup and store in variable 'soup'
	soup = BeautifulSoup(res,'html.parser')
	players = soup.find_all('div', attrs={'id':'playerbox'})


	players_df = process_deez_(players, driver)
	# players_df.to_csv('players_df.csv', sep ='\t',index=False)

	# we are ready to 'close' our browser now
	driver.quit()

	# upload changes to Google Spreadsheets
	buzzer2spreadsheet(players_df)
