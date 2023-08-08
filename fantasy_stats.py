import pandas as pd
from yahoo_oauth import OAuth2
import json
from json import dumps
import datetime
import requests
import os
import csv
import time
import math
import sys

draftData = []
keeperValues = []

class Yahoo_Api():
    def __init__(self, consumer_key, consumer_secret,
                access_key):
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_key = access_key
        self._authorization = None
    def _login(self):
        global oauth
        oauth = OAuth2(None, None, from_file='./auth/oauth2yahoo.json')
        if not oauth.token_is_valid():
            oauth.refresh_access_token()

class UpdateData():
    #def __init__(self):

    def UpdateTransactions(self):
        # TRANSACTIONS
        # Convert existing 'Transactions_new.json' into 'Transactions_old.json' before
        #### downloading up-to-date new transactions
        try:
            load_file = open('./transactions/Transaction_old.json', 'a+') # load old_transactions
            #old_transactions = json.load(load_file)
            load_file.close()


            load_file = open('./transactions/Transaction_new.json') # load new_transactions (this will get written over once we download the newest data from Yahoo)
            new_transactions = json.load(load_file)
            load_file.close()

            with open('./transactions/Transaction_old.json', 'w') as outfile: # save the new*_transactions as old so we can compare the actual new transactions
                json.dump(new_transactions, outfile)

            load_file = open('./transactions/Transaction_old.json') # now load the *new* old_transactions as the base for comparison
            old_transactions = json.load(load_file)
            load_file.close()
        except:
            print("Transaction files not found")

        yahoo_api._login() # get the newest transactions and write over the existing new_transactions
        #url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/transactions'
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/transactions'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        with open('./transactions/Transaction_new.json', 'w') as outfile:
            json.dump(r, outfile)
        #### load in newest transaction data
        load_file = open('./transactions/Transaction_new.json')
        new_transactions = json.load(load_file)
        load_file.close()

        #### get number of new transactions since last transaction download
        if 'old_transactions' in locals():
            old_trans = old_transactions['fantasy_content']['league'][1]['transactions']['count']
        else:
            old_trans = 0
        new_trans = new_transactions['fantasy_content']['league'][1]['transactions']['count']
        newest_trans = new_trans-old_trans

        transactions = new_transactions['fantasy_content']['league'][1]['transactions']

        #load team number and names references as a dictionary
        team_numbers = {}
        with open('./teams/team_numbers.txt', 'r') as f:
            #for line in f:
            team_numbers= eval(f.read())

        if new_trans > 0: # only run if there are new transactions
            transaction = 0

            #for transaction in range(len(transactions)-1):
            for transaction in range(newest_trans-1, -1, -1):

                # transaction(tr) info
                tr_num = str(transaction).zfill(2) #adds zeros to the front of the number to keep it all the same length
                tr_id = transactions[str(transaction)]['transaction'][0]['transaction_id']
                tr_type = transactions[str(transaction)]['transaction'][0]['type']
                tr_date = datetime.datetime.fromtimestamp(int(transactions[str(transaction)]['transaction'][0]['timestamp'])).strftime('%m-%d-%Y %H:%M:%S')

                # DROPS ### need to update to handle multiple drops, can only handle 1 at a time right now and "AND also dropped..."
                if tr_type == 'drop':
                    players = transactions[str(transaction)]['transaction'][1]['players']
                    for player in range(len(players)-1):
                        tm_name = players[str(player)]['player'][1]['transaction_data']['source_team_name']
                        tm_key = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][1]['transaction_data']['destination_type']
                        #tm_real_nm = team_numbers[str(tm_key)]
                        player_name = players[str(player)]['player'][0][2]['name']['full']
                        status = tm_name, " (", tm_name ,") dropped", player_name

                        # print(status)
                        # add code to append transaction to list, this was originalyl used to Tweet every transaction


                # TRADES
                elif tr_type == "trade":
                    pX_name = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][0][2]['name']['full']
                    pX_pos = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][0][4]['display_position']
                    pY_name = transactions[str(transaction)]['transaction'][1]['players']['1']['player'][0][2]['name']['full']
                    pY_pos = transactions[str(transaction)]['transaction'][1]['players']['1']['player'][0][4]['display_position']
                    trader = transactions[str(transaction)]['transaction'][0]['trader_team_name']
                    trader_key = transactions[str(transaction)]['transaction'][0]['trader_team_key']
                    trader_real_nm = team_numbers[str(trader_key)]
                    tradee = transactions[str(transaction)]['transaction'][0]['tradee_team_name']
                    tradee_key = transactions[str(transaction)]['transaction'][0]['tradee_team_key']
                    tradee_real_nm = team_numbers[str(tradee_key)]

                    trade = trader + " (" +trader_real_nm+ ") traded "+ pX_name+ \
                                "-"+ pX_pos+ " to "+ tradee+ " (" + tradee_real_nm +") for "+ pY_name+ "-"+ pY_pos
                    status = trade

                    # print(status)
                    # add code to append transaction to list, this was originalyl used to Tweet every transaction


                # ADD/DROP
                elif tr_type == "add/drop":
                    tm_name = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][1]['transaction_data'][0]['destination_team_name']
                    tm_key = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][1]['transaction_data'][0]['destination_team_key']
                    tm_real_nm = team_numbers[str(tm_key)]
                    pl_add = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][0][2]['name']['full']
                    pl_add_pos = transactions[str(transaction)]['transaction'][1]['players']['0']['player'][0][4]['display_position']
                    pl_drop = transactions[str(transaction)]['transaction'][1]['players']['1']['player'][0][2]['name']['full']
                    pl_drop_pos = transactions[str(transaction)]['transaction'][1]['players']['1']['player'][0][4]['display_position']
                    try:
                        faab = transactions[str(transaction)]['transaction'][0]['faab_bid']
                    except:
                        faab = '0'
                    if int(faab) > 0:
                        faab = transactions[str(transaction)]['transaction'][0]['faab_bid']
                        faab = " || FAAB Spent: $"+ faab
                    else:
                        faab = ''

                    add_drop = tm_name + " (" + tm_real_nm + ") added " + \
                                pl_add + "-" + pl_add_pos + " and dropped " + pl_drop + "-" + pl_drop_pos + faab
                    status = add_drop

                    # print(status)
                    # add code to append transaction to list, this was originalyl used to Tweet every transaction

                # ADD
                elif tr_type == 'add':
                    players = transactions[str(transaction)]['transaction'][1]['players']
                    for player in range(0, len(players)-1):
                        tm_name = players[str(player)]['player'][1]['transaction_data'][0]['destination_team_name']
                        tm_key = players[str(player)]['player'][1]['transaction_data'][0]['destination_team_key']
                        tm_real_nm = team_numbers[str(tm_key)]
                        player_name = players[str(player)]['player'][0][2]['name']['full']
                        status = tm_name, " (", tm_real_nm, ") added", player_name

                        # print(status)
                        # add code to append transaction to list, this was originalyl used to Tweet every transaction

                # COMMISH
                elif tr_type == "commish":
                    status = "Commish made some changes to [Enter League Name Here]"

                    # print(status)
                    # add code to append transaction to list, this was originalyl used to Tweet every transaction

                transaction += transaction
            return;

    def UpdateLeague(self):
        # LEAGUE OVERVIEW
        yahoo_api._login()
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        with open('league.json', 'a') as outfile:
            json.dump(r, outfile)
        return;

    def UpdateLeagueStandings(self):
        # STANDINGS
        yahoo_api._login()
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/standings'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        with open('standings.json', 'a') as outfile:
            json.dump(r, outfile)
        
        return;

    def UpdateScoreboards(self):
        # WEEKLY SCORE BOARD
        yahoo_api._login()
        week = 1
        while week < num_weeks+1: #assumes 16 week-schedule
            url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/scoreboard;week='+str(week)
            response = oauth.session.get(url, params={'format': 'json'})
            r = response.json()
            file_name = 'week_' + str(week) + 'scoreboard.json'
            with open('./weekly_scoreboard/'+file_name, 'a') as outfile:
                json.dump(r, outfile)
            week += 1
        return;

    def UpdateYahooLeagueInfo(self):
        # UPDATE LEAGUE GAME ID
        yahoo_api._login()
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/game/nfl'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        with open('YahooGameInfo.json', 'a') as outfile:
            json.dump(r, outfile)
            
        global game_key

        #game_key = r['fantasy_content']['game'][0]['game_key'] # game key as type-string
        #game_key = '406' #2021
        game_key = '414' #2022
        return;


    def UpdateRosters(self):
        # WEEKLY ROSTERS - TAKES A WHILE
        yahoo_api._login()
        week = 1
        for week in range(1, num_weeks+1): #assumes 16-week schedule
            team = 1
            for team in range(1, num_teams+1): #assumes 12-team league
                url = 'https://fantasysports.yahooapis.com/fantasy/v2/team/'+game_key+'.l.'+league_id+'.t.'+str(team)+'/roster;week='+str(week)
                response = oauth.session.get(url, params={'format': 'json'})
                r = response.json()
                file_name = 'team_'+str(team)+'_wk_' + str(week) + '_roster.json'
                with open('./rosters/week_'+str(week)+'/'+ file_name, 'a') as outfile:
                    json.dump(r, outfile)
                team =+ 1
            print("Week",week, "roster update - done")
            week += 1
        return;

    def UpdateDraftResults(self):
        global draftData
        #"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.get_league_key()}/draftresults"
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/draftresults'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        header = ['Draft Pick', 'Drafted Value', 'Player', 'Player ID', 'Team Name']
        file_name = 'draft_results_' + league_id + '.csv'
        outfile = open('./draft_results/'+file_name, 'w+')
        writer = csv.writer(outfile, lineterminator='\n')
        writer.writerow(header)
        for x in r['fantasy_content']['league'][1]['draft_results']:  
            if x != "count":
                player_key = r['fantasy_content']['league'][1]['draft_results'][x]['draft_result']['player_key']
                #Only used for Dojo data
                #player_cost = r['fantasy_content']['league'][1]['draft_results'][x]['draft_result']['cost'] 
                player_cost = math.floor(int(x)/12) + 1
                team_key = r['fantasy_content']['league'][1]['draft_results'][x]['draft_result']['team_key']
                player_url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/players;player_keys='+player_key
                team_url = 'https://fantasysports.yahooapis.com/fantasy/v2/team/' + team_key + '/metadata' 
                player_response = oauth.session.get(player_url, params={'format': 'json'})
                player_r = player_response.json()
                team_response = oauth.session.get(team_url, params={'format': 'json'})
                team_r = team_response.json()
                # data = [int(x)+1, player_cost, player_r['fantasy_content']['league'][1]['players']['0']['player'][0][2]['name']['full'],player_key, team_r['fantasy_content']['team'][0][2]['name']]
                draftData.append([int(x)+1, player_cost, player_r['fantasy_content']['league'][1]['players']['0']['player'][0][2]['name']['full'],player_key, team_r['fantasy_content']['team'][0][2]['name']])
                # writer.writerow(data)
                time.sleep(0.1)
                print(x)
            else:
                break
        writer.writerows(draftData)
        outfile.close()
            
    def ReadDraftResults(self):
        global draftData
        file_name = 'draft_results_' + league_id + '.csv'
        try:
            with open('./draft_results/'+file_name, newline='\n') as csvfile:
                print("Saved draft data found")
                reader = csv.reader(csvfile)
                draftData = list(reader)
        except IOError:
            print("Saved draft data not found, pulling from Yahoo!")
            self.UpdateDraftResults()

        print("Draft data read")
        
    def UpdatePlayerList(self):
        #https://fantasysports.yahooapis.com/fantasy/v2/league/{self.get_league_key()}/players
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/'+game_key+'.l.'+league_id+'/players'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        file_name = 'player_list_' + league_id + '.json'
        with open('./player_list/'+file_name, 'a') as outfile:
            json.dump(r, outfile)

    def CalcDraftValue(self):
        global draftData
        global keeperValues
        adp = {}
        playerFound = 0
        foundInTransactions = 0
        header = ['Team', 'Player', 'Keeper Value', 'Drafted Value', 'Prev ADP', 'Curr ADP']
        file_name = 'keeper_values_' + league_id + '.csv'
        outfile = open('./keeper_values/'+file_name, 'w')
        writer = csv.writer(outfile, lineterminator='\n')
        writer.writerow(header)

        #Grab the ADPS
        responseCur = requests.get('https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=2023')
        dataCur = responseCur.json()
        responsePrev = requests.get('https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=2022')
        dataPrev = responsePrev.json()

        load_file = open('./transactions/Transaction_new.json') # load transactions from previous season
        transactions_prev = json.load(load_file)
        load_file.close()

        yahoo_api._login()
        week = 16
        team = 1
        for team in range(1, num_teams+1): #assumes 12-team league
            url = 'https://fantasysports.yahooapis.com/fantasy/v2/team/'+game_key+'.l.'+league_id+'.t.'+str(team)+'/roster;week='+str(week)
            response = oauth.session.get(url, params={'format': 'json'})
            r = response.json()
            teamname = r['fantasy_content']['team'][0][2]['name']
            print("Team: ")
            print(teamname)
            print("\r\n")
            for y in r['fantasy_content']['team'][1]['roster']['0']['players']:
                if y != "count":
                    foundADPCurr = 0.0
                    foundADPPrev = 0.0
                    foundDraft = 0.0
                    i = 0
                    is_keeper_idx = 0
                    player_to_find = r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0][2]['name']['full'].replace('.', '')
                    player_yahoo_key = r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0][0]['player_key']
                    #Search Current ADPS
                    for x in dataCur['players']:
                        if player_to_find == x['name'].replace('.', ''):
                            playerFound += 1
                            foundADPCurr = x['adp']
                            break
                    #Search Previous ADPs
                    for x in dataPrev['players']:
                        if player_to_find == x['name'].replace('.', ''):
                            playerFound += 1
                            foundADPPrev = x['adp']
                            break
                    #Search Draft data
                    for x in draftData:
                        i += 1
                        if i < 168:
                            #Player found in draft data
                            #if player_to_find in draftData[i]:
                            if player_yahoo_key in draftData[i]:
                                playerFound += 1
                                #search to see if the player involved in a transaction
                                for x in transactions_prev['fantasy_content']['league'][1]['transactions']:
                                    #if 'add/drop' in hay:
                                    if x != "count":
                                        if "add" in transactions_prev['fantasy_content']['league'][1]['transactions'][x]['transaction'][0]['type']:
                                            #if player_to_find == transactions_prev['fantasy_content']['league'][1]['transactions'][x]['transaction'][1]['players']['0']['player'][0][2]['name']['full'].replace('.', ''):
                                            if player_yahoo_key == transactions_prev['fantasy_content']['league'][1]['transactions'][x]['transaction'][1]['players']['0']['player'][0][0]['player_key']:
                                                #Player found in transaction data, free agent pick up
                                                foundInTransactions = 1
                                                break
                                        # elif "add/drop" in transactions_prev['fantasy_content']['league'][1]['transactions'][x]['transaction'][0]['type']:
                                        #     if 'add' in transactions_prev['fantasy_content']['league'][1]['transactions'][x]['transaction'][1]['players']['0']['player'][1]['transaction_data'][0]['type']:
                                        #         if player_yahoo_key == transactions_prev['fantasy_content']['league'][1]['transactions'][x]['transaction'][1]['players']['0']['player'][0][0]['player_key']:
                                        #             #Player found in transaction data, free agent pick up
                                        #             foundInTransactions = 1
                                        #             break
                                if foundInTransactions == 0:    
                                    #the index where is_keeper is found changes, so search the list and save the index
                                    for z,  hay in enumerate(r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0]):
                                        if 'is_keeper' in hay:
                                            is_keeper_idx = z
                                            break
                                    
                                    #check if the player was a keeper
                                    if r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0][is_keeper_idx]['is_keeper']['status'] == False:
                                        #Store the drafed round
                                        foundDraft = int(draftData[i][1]) 
                                    elif r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0][is_keeper_idx]['is_keeper']['status'] == True:
                                        #Store the keeper value
                                        foundDraft = int(r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0][is_keeper_idx]['is_keeper']['cost'])
                                    break
                                else:
                                    #Player found in transaction data
                                    foundDraft = 8.0
                                    foundInTransactions = 0
                                    break
                        else:
                            #Player not found in draft data, free agent pick up
                            playerFound += 1
                            foundDraft = 8.0
                            break
                        
                    if playerFound != 0:
                        if foundADPCurr != 0.0:
                            foundADPCurr = int((foundADPCurr/12)+1)
                        if foundADPPrev != 0.0:
                            foundADPPrev = int((foundADPPrev/12)+1)
                        adp = int(((foundADPCurr + foundADPPrev + foundDraft)/playerFound))
                        #Team, Player, Keeper Value, Drafted Round, Prev ADP, Curr ADP 
                        keeperValues.append([teamname, r['fantasy_content']['team'][1]['roster']['0']['players'][y]['player'][0][2]['name']['full'], adp, foundDraft, foundADPPrev, foundADPCurr])
                    
                    print("Player: " + player_to_find + " ADP: " + str(foundADPPrev) + "+" + str(foundADPCurr) + "+" + str(foundDraft) + "/" + str(playerFound) + " = " + str(adp))
                    playerFound = 0
                    adp = 0.0
                    is_keeper_idx = 0
                    foundDraft = 0.0
                
            team =+ 1

        writer.writerows(keeperValues)
        outfile.close()    

def CurrentWeek():
    current_week = 1
    #with open('./league.json', 'r') as fobj:
    #    info = json.load(fobj)
    #current_week = info['fantasy_content']['league'][0]['current_week']
    return current_week;

def FFC_ADP():
    

    with open('./rosters/week_16/team_1_wk_16_roster.json', 'a+') as myFile:
        jsondata=myFile.read()

    team1Week16 = json.loads(jsondata)
    team1Week16 = team1Week16
### WHERE ALL THE MAGIC HAPPENS #########

def main():
##### Get Yahoo Auth ####
    
    # Yahoo Keys
    with open('./auth/oauth2yahoo.json') as json_yahoo_file:
        auths = json.load(json_yahoo_file)
    yahoo_consumer_key = auths['consumer_key']
    yahoo_consumer_secret = auths['consumer_secret']
    yahoo_access_key = auths['access_token']
    #yahoo_access_secret = auths['access_token_secret']
    json_yahoo_file.close()

#### Declare Yahoo, and Current Week Variable ####

    global yahoo_api
    yahoo_api = Yahoo_Api(yahoo_consumer_key, yahoo_consumer_secret, yahoo_access_key)#, yahoo_access_secret)

    global current_week
    current_week = CurrentWeek()

    # with open('./Initial_Setup/league_info_form.txt', 'r') as f:
    #with open('./Initial_Setup/league_info_form_dojo_22.txt', 'r') as f:
    with open('./Initial_Setup/league_info_form_keeper_22.txt') as curr:
        rosters_curr = eval(curr.read())

    global num_teams
    num_teams = rosters_curr['num_teams']

    global num_weeks
    num_weeks = rosters_curr['num_weeks']
    
    global league_id
    league_id = str(rosters_curr['league_id'])

#### Where the tweets happen ####
    bot = Bot(yahoo_api)
    bot.run()

    
    
class Bot():
    def __init__(self, yahoo_api):
        self._yahoo_api = yahoo_api
    def menu(self):
        UD = UpdateData()

        print("\r\n************Yahoo Fantasy Football API**************")
        print()

        choice = input("""
                        A: Download Draft Results
                        B: Download Rosters
                        C: Download Transaction Data
                        D: Calculate Keeper Values
                        Q: Quit

                        Please enter your choice: """)

        if choice == "A" or choice =="a":
            UD.UpdateDraftResults()
            print('Draft Results - Done')
            self.menu() 
        elif choice == "B" or choice =="b":
            UD.UpdatePlayerList()
            print('Current Team Roster Update - Done')
            self.menu() 
        elif choice == 'C' or choice == 'c':
            UD.UpdateTransactions()
            print('Transactions update - Done')
            self.menu() 
        elif choice == 'D' or choice == 'd':
            UD.UpdateTransactions()
            print('Transactions update - Done')

            UD.ReadDraftResults()
            print('Draft Results - Done')

            UD.CalcDraftValue()              
            print('Draft Value - done')
            self.menu() 
        elif choice=="Q" or choice=="q":
            sys.exit
        else:
            print("You must only select either A, B, C, or D")
            print("Please try again")
            self.menu()    

        

    def run(self):
        # Data Updates
        UD = UpdateData()
                           
        UD.UpdateYahooLeagueInfo()
        print('Yahoo League Info Updated')
                           
        UD.UpdateLeague()
        print('League update - Done')

        #Wait for decision on what to do.
        self.menu()

        # UD.UpdatePlayerList()
        # print('Current Team Roster Update - Done')

        # UD.UpdateTransactions()
        # print('Transactions update - Done')

        #UD.UpdateDraftResults()
        # UD.ReadDraftResults()
        # print('Draft Results - Done')
        
        # UD.CalcDraftValue()              
        # print('Draft Value - done')

        # UD.UpdateLeagueStandings()
        # print('Standings update - Done')
                           
        # UD.UpdateScoreboards()
        # print('Scoreboards update - Done')
                              
        # UD.UpdateRosters()
        # print('Rosters update - Done')
                           
        #print('Update Complete')



if __name__ == "__main__":
    main()

    try:
        pass
    except Exception as e:
        raise
    else:
        pass
