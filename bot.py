#!/usr/bin/python3

import datetime
import os
import sqlite3
import time
from slackclient import SlackClient

# This code is inspired by https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
# Visit that webpage to get the whole setup guide

# timebot's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

# Open up the database
conn = sqlite3.connect('team.db')
c = conn.cursor()


# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

def initialize_db():
    # Open up the database
    conn = sqlite3.connect('team.db')
    c = conn.cursor()

    try:
        c.execute(''' DROP TABLE users''')
    except sqlite3.OperationalError:
        # The table doesn't exist, which is okay.
        pass
    c.execute('''CREATE TABLE users (id TEXT, realName TEXT, currentLate REAL, checkInDate INTEGER, active INTEGER)''')

    count = 0
    if slack_client.rtm_connect():
        output = slack_client.api_call("users.list")
        if output:
            for user in output['members']:
                if not user['is_bot']:
                    count += 1
                    print( user['id'])
                    print( user['name'])
                    c.execute('INSERT INTO users VALUES (?, ?, 0.0, 0, 0)', (user['id'], user['name']))

            print( "Found " + str(count) + " users and added them to database.")
        else:
            print("I didn't get a list of users. Something is wrong.")
    else:
        print("Connection failed. Invalid Slack token or bot ID?")

    conn.commit()

    print("User Table:")
    for row in c.execute('''SELECT * FROM users'''):
        print(row)

    conn.close()

def toTime(seconds):
    '''
    Takes a number of seconds and converts it to a string '''

    seconds = int(seconds)

    if seconds > 3600:
        text = str(seconds//3600) + " hours, " + str((seconds%3600)//60) + " minutes, " + str(seconds % 3600 % 60) + " seconds"
    elif seconds > 60:
        text = str(seconds//60) + " minutes, " + str(seconds%60) + " seconds"
    else:
        text = str(seconds) + " seconds"
    return text



def handle_command(command):
    """
    Receives commands directed at the bot and determines if they
    are valid commands. If so, then acts on the commands. If not,
    returns back what it needs for clarification.
    """
    if command['text'].startswith('!in') and not command['text'].startswith('!intime') and command['channel'][0] == 'D':

        today = datetime.date.today()

        # Weekday besides Wednesday
        if today.weekday() in [0, 1, 3, 4]:
            timeToBegin = 8
        # Wednesday
        elif today.weekday() == 2:
            timeToBegin = 7
        # Weekend
        else:
            slack_client.api_call("chat.postMessage", channel=command['channel'], 
                    text="Why are you coming in on the weekend???", as_user = True)
            timeToBegin = 8


        startTime = datetime.datetime(today.year, today.month, today.day, hour=timeToBegin)
        difference = datetime.datetime.fromtimestamp(float(command['ts'])) - startTime

        if difference.total_seconds() < 0:
            # You weren't late, so there's no need to update the table.
            delta = 0
        else:
            delta = difference.total_seconds()

        currentLate = c.execute('''SELECT currentLate, checkInDate FROM users WHERE id=?''', (command['user'],))
        row = currentLate.fetchone()
        if row[1] != datetime.date.today().toordinal():
            c.execute('''UPDATE users SET currentLate=?, checkInDate=? WHERE id=?''', (row[0] + delta, datetime.date.today().toordinal(), command['user']))

            slack_client.api_call("reactions.add", channel=command['channel'], 
                name='thumbsup', timestamp=command['ts'])
        else:
            slack_client.api_call("chat.postMessage", channel=command['channel'],
                    text="You already clocked in today!", as_user=True)


    elif command['text'].startswith('!standings'):
        # Show current standings
        text = "*Here are the current latest people this week:*\n"
        origText = text
        for user in c.execute('''SELECT realName, currentLate FROM users WHERE active=1 ORDER BY currentLate DESC LIMIT 5'''):
            if user[1] > 0:
                text += "*"+user[0]+"*: " + toTime(user[1]) + " late\n"

        if text == origText:
            text = "Nobody has been late this week. At least not _yet_"
        else:
            text+= "Better luck next time!"

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=text, linkNames=False)

    elif command['text'].startswith('!!reset') and command['channel'][0] == 'D':
        # Resets the time for the week
        c.execute('''UPDATE users SET currentLate=0.0, checkInDate=0''')
        slack_client.api_call("chat.postMessage", channel=command['channel'], 
                text="Standings reset!", as_user=True)


    elif command['text'].startswith('!active') and command['channel'][0] == 'D':
        # Users mark themselves active
        c.execute('''UPDATE users SET active=1 WHERE id=?''', (command['user'],))
        slack_client.api_call("reactions.add", channel=command['channel'], 
                name='white_check_mark', timestamp=command['ts'])
        print( command['user'] + " marked themselves active")

    elif command['text'].startswith('!inactive') and command['channel'][0] == 'D':
        # Users mark themselves inactive
        c.execute('''UPDATE users SET active=0 WHERE id=?''', (command['user'],))
        slack_client.api_call("reactions.add", channel=command['channel'], 
                name='white_check_mark', timestamp=command['ts'])
        print( command['user'] + " marked themselves inactive")

    elif command['text'].startswith('!status') and command['channel'][0] == 'D':
        # Prints out their current late time
        response = c.execute('''SELECT id, currentLate FROM users WHERE id=?''', (command['user'],)).fetchone()

        if response[1] > 0:
            text = "You have been " + toTime(response[1]) + " late this week."
        else:
            text = "You have not been late yet this week."
        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=text)

    elif command['text'].startswith('!whoshere'):
        rows = c.execute('''SELECT * FROM users WHERE checkInDate=? AND active=1''', (datetime.date.today().toordinal(),)).fetchall()
        attendance = len(rows)
        quantifier = "people have" if attendance != 1 else "person has"
        text = str(attendance) + " " + quantifier + " clocked in so far today."
        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=text)
    elif command['text'].startswith('!sumtime'):
        rows = c.execute('''SELECT currentLate FROM users WHERE active=1''')
        totalTime = 0.0
        for row in rows:
            totalTime += row[0]

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text="The total time that we've been late this week is " + toTime(totalTime) + ".")

    elif command['text'].startswith('!intime'):
        today = datetime.date.today()

        try:
            minutesLate = int(command['text'].split(' ')[1])
        except:
            slack_client.api_call("chat.postMessage", channel=command['channel'], 
                    text="Invalid usage. Put the number of minutes late after *!intime*.", as_user = True)
            return

        secondsLate = minutesLate * 60
        
        if secondsLate < 0:
            # You weren't late, so there's no need to update the table.
            secondsLate = 0

        currentLate = c.execute('''SELECT currentLate, checkInDate FROM users WHERE id=?''', (command['user'],))
        row = currentLate.fetchone()
        if row[1] != datetime.date.today().toordinal():
            c.execute('''UPDATE users SET currentLate=?, checkInDate=? WHERE id=?''', (row[0] + secondsLate, datetime.date.today().toordinal(), command['user']))

            slack_client.api_call("reactions.add", channel=command['channel'], 
                name='thumbsup', timestamp=command['ts'])
        else:
            slack_client.api_call("chat.postMessage", channel=command['channel'],
                    text="You already clocked in today!", as_user=True)


    elif command['text'].startswith('!usage'):
        # If it's a direct message
        if command['channel'][0] == 'D':
            text=privateUsage()
            
        # If it's in a regular channel
        else:
            text=publicUsage()

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=text)

    else:
        # Unknown command, print usage statement

        # If it's a direct message
        if command['channel'][0] == 'D':
            text="I don't understand " + command['text'] + ". " + privateUsage()
            
        # If it's in a regular channel
        else:
            text="I don't understand " + command['text'] + ". " + publicUsage()

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=text)

    conn.commit()

def publicUsage(text, channel):
       return "I can only do this in public channels:\n"\
                + "*!standings*: View current standings for the week\n"\
                + "*!whoshere*: See current number of people checked in for today\n"\
                + "*!sumtime*: See the cumulative time that people have been late this week"

def privateUsage():
    return "Try one of these:\n"\
                + "*!in*: Clock in\n"\
                + "*!intime number*: Clock in being _number_ minutes late. (For when you forget to clock in). Ex: !intime 5\n"\
                + "*!standings*: View current standings for the week\n"\
                + "*!active*: Mark yourself active\n"\
                + "*!status*: See your current late time this week\n"\
                + "*!whoshere*: See current number of people checked in for today\n"\
                + "*!sumtime*: See the cumulative time that people have been late this week"




def parse_slack_output(slack_rtm_output):
    """
    The Slack Real Time Messaging API is an events firehose.
    this parsing function returns None unless a message is
    directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list:
        print(datetime.datetime.now(), end='')
        print(output_list)
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and output['text'].startswith('!') and output['user'] != BOT_ID:
                return {'text': output['text'].strip().lower(),
                        'channel': output['channel'], 
                        'user': output['user'],
                        'ts': output['ts']}
    return {}


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("TimeBot connected and running!")
        try:
            while True:
                try:
                    command = parse_slack_output(slack_client.rtm_read())
                except TimeoutError:
                    if slack_client.rtm_connect():
                        continue
                    else:
                        print(str(datetime.datetime.now()) + "Slack client failed to reconnect")
                        conn.close()
                        break
                if command:
                    handle_command(command)
                if not command:
                    time.sleep(READ_WEBSOCKET_DELAY)
        except KeyboardInterrupt:
            print()
            print( "Exiting cleanly")
            conn.close()
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
