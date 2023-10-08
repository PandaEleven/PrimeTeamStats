# This is a sample Python script.
from typing import List

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import requests
import json
from datetime import datetime
import tzlocal
import gspread

# Define stats to track as defined in riot API
STATISTICS_LIST = {"kills", "deaths", "assists", "totalDamageDealtToChampions", "totalDamageTaken", "wardsPlaced",
                   "wardsKilled", "visionWardsBoughtInGame", "goldEarned", "totalMinionsKilled", "neutralMinionsKilled"}

# Define stats to be tracked on the sheet itself
# This list is only different if cs is tracked, as cs is comprised of totalMinionsKilled and neutralMinionsKilled
DISPLAY_STATS = ["champion", "kills", "deaths", "assists", "totalDamageDealtToChampions", "totalDamageTaken",
                 "wardsPlaced",
                 "wardsKilled", "visionWardsBoughtInGame", "goldEarned", "cs"]

# Location of Datadragon champion.json
DATADRAGON_CHAMPIONS = "champion.json"

# User will always be riot
USER = 'riot'

# Load config from config.json
with open('config.json') as f:
    config = json.load(f)
top = config['top']
jgl = config['jgl']
mid = config['mid']
adc = config['adc']
sup = config['sup']
worksheet_name = config['workbook name']
spreadsheetname = config['spreadsheet name']
lockfile = f'{config['league install']}/lockfile'

# gspread setup, no need to change
# have your credentials.json in %APPDATA%/gspread/
# C:\Users\<User>\AppData\Roaming\gspread
GC = gspread.oauth()
SH = GC.open(spreadsheetname)
WORKSHEET = SH.worksheet(worksheet_name)

# Create Player list
player_list = [top, jgl, mid, adc, sup]
role_list = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']

# Get port and password from lockfile
with open(lockfile) as lf:
    lockfile_contents: list[str] = lf.read().split(':')
    port = lockfile_contents[2]
    pw = lockfile_contents[3]

# First LCU API request to get Game ID
url = f'https://127.0.0.1:{port}/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=0'
request = requests.get(url, auth=(USER, pw), verify=False)
game_json: dict = request.json()
game_ID = game_json["games"]["games"][0]['gameId']

# Second LCU API request to get Game Stats
url = f'https://127.0.0.1:{port}/lol-match-history/v1/games/{game_ID}'
request = requests.get(url, auth=(USER, pw), verify=False)
full_game_json: dict = request.json()

# import statistics from json
statistics = {}
for i in full_game_json['participantIdentities']:
    if i['player']['summonerName'] in player_list:
        name = i['player']['summonerName']
        pi = i['participantId']
        st = full_game_json['participants'][pi - 1]
        statistics[name] = {}
        for stat in STATISTICS_LIST:
            statistics[name][stat] = st["stats"][stat]
        statistics[name]['champion'] = st["championId"]
        if st['teamId'] == 100:
            side = 'Blue'
            outcome = full_game_json['teams'][0]['win']
        else:
            side = "Red"
            outcome = full_game_json['teams'][1]['win']

# Rename Champions from IDs
with open(DATADRAGON_CHAMPIONS, encoding="utf8") as datadragon:
    datadragon_str = datadragon.read()
    champions_json = json.loads(datadragon_str)
for champ_name in champions_json["data"]:
    for player in statistics:
        if champions_json["data"][champ_name]["key"] == str(statistics[player]["champion"]):
            statistics[player]["champion"] = champions_json["data"][champ_name]['name']

# Calculate Total CS
if 'totalMinionsKilled' and 'neutralMinionsKilled' in STATISTICS_LIST:
    for player in statistics:
        statistics[player]["cs"] = statistics[player]['totalMinionsKilled'] + statistics[player]['neutralMinionsKilled']
        del statistics[player]['totalMinionsKilled'], statistics[player]['neutralMinionsKilled']
elif 'totalMinionsKilled' in STATISTICS_LIST:
    for player in statistics:
        statistics[player]["cs"] = statistics[player]['totalMinionsKilled']
        del statistics[player]['totalMinionsKilled']
elif 'neutralMinionsKilled' in STATISTICS_LIST:
    for player in statistics:
        statistics[player]["cs"] = statistics[player]['neutralMinionsKilled']
        del statistics[player]['neutralMinionsKilled']

# Get Team, Side and Outcome
statistics['game'] = {}
statistics['game']['gameTime'] = round(full_game_json['gameDuration'] / 60, 2)
start_time_unix = float(full_game_json['gameCreation']) / 1000
local_timezone = tzlocal.get_localzone()
local_time = datetime.fromtimestamp(start_time_unix, tz=local_timezone)
date = local_time.strftime('%d-%m-%Y')
ToD = local_time.strftime('%H:%M')
statistics['game']['start'] = ToD
statistics['game']['date'] = date
if outcome == 'Win':
    outcome = 'Victory'
else:
    outcome = 'Defeat'
statistics['game']['outcome'] = outcome
statistics['game']['side'] = side

# Get general game stats
values_game = [statistics['game']['date'], statistics['game']['start'], statistics['game']['side'],
               statistics['game']['outcome'],
               statistics['game']['gameTime']]

# Get player stats, create empty field for missing players
values_role = {}
for role in player_list:
    if role in statistics:
        temp_vr = []
        for i in range(len(DISPLAY_STATS)):
            temp_vr.append(statistics[role][DISPLAY_STATS[i]])
        values_role[role] = temp_vr
    else:
        temp_vr = ['']*len(DISPLAY_STATS)
        values_role[role] = temp_vr

# Create List of Values for the sheet and push them to the data sheet
sheet_values = values_game
for i in values_role:
    sheet_values = sheet_values + [*values_role[i]]
sheet_values = [sheet_values]
print(sheet_values)
SH.values_append(f'{worksheet_name}!A1', {'valueInputOption': 'USER_ENTERED'},
                 {'values': sheet_values})

# Print Stats
print(json.dumps(statistics, indent=2))

# Optional: Output player and game stats as <gameId>.json
# stroutfile = f'{game_ID}.json'
# with open(stroutfile,'w') as outfile:
#    outfile.write(json.dumps(statistics, indent=2))
