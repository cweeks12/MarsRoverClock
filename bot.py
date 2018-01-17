#!/usr/bin/python3

import csv
import datetime
import os
import sqlite3
import time
import websocket
from slackclient import SlackClient

# This code is inspired by https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
# Visit that webpage to get the whole setup guide

# timebot's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")


# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

def initialize_db():
    # Open up the database
    conn = sqlite3.connect('team.db')
    c = conn.cursor()

    try:
        c.execute(''' DROP TABLE IF EXISTS users''')
    except sqlite3.OperationalError:
        # Make sure it doesn't crash
        pass
    c.execute('''CREATE TABLE users (id TEXT, realName TEXT, checkInDate INTEGER, timeLateThisWeek REAL, totalTimeLate REAL, 
                                    clockedIn INTEGER, timeClockedInAt REAL, timeSpentThisWeek REAL, totalTimeSpent REAL, active INTEGER)''')

    count = 0
    if slack_client.rtm_connect():
        output = slack_client.api_call("users.list")
        if output:
            for user in output['members']:
                if not user['is_bot']:
                    count += 1
                    print( user['id'])
                    print( user['name'])
                    c.execute('INSERT INTO users VALUES (?, ?, 0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0)', (user['id'], user['name']))

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

def getStartingTime():
    today = datetime.date.today()

    # Weekday besides Wednesday
    if today.weekday() in [0, 1, 3, 4]:
        return 8
    # Wednesday
    elif today.weekday() == 2:
        return 7
    # Weekend
    else:
        slack_client.api_call("chat.postMessage", channel=command['channel'], 
                text="Why are you coming in on the weekend???", as_user = True)
        return 8



def handle_command(command):
    """
    Receives commands directed at the bot and determines if they
    are valid commands. If so, then acts on the commands. If not,
    returns back what it needs for clarification.
    """

    # Clocks in late
    if command['text'].startswith('!intime') and command['channel'][0] == 'D':
        in_late(command)

    # Clock in
    elif command['text'].startswith('!in') and command['channel'][0] == 'D':
        clock_in(command)

    # Reset the week
    elif command['text'].startswith('!!reset') and command['channel'][0] == 'D':
        reset(command)

    # Mark as active
    elif command['text'].startswith('!active') and command['channel'][0] == 'D':
        active(command)

    # Mark as inactive
    elif command['text'].startswith('!inactive') and command['channel'][0] == 'D':
        inactive(command)

    # Shows how late you are and how much time you've spent this week
    elif command['text'].startswith('!status') and command['channel'][0] == 'D':
        status(command)

    elif command['text'].startswith('!outtime') and command['channel'][0] == 'D':
        out_late(command)

    elif command['text'].startswith('!out') and command['channel'][0] == 'D':
        clock_out(command)

    elif command['text'].startswith('!addme') and command['channel'][0] == 'D':
        add_user(command)

    # Show current standings. Latest and time spent
    elif command['text'].startswith('!standings'):
        get_standings(command)
    
    elif command['text'].startswith('!lateweek'):
        rows = c.execute('''SELECT timeLateThisWeek FROM users WHERE active=1''')
        totalTime = 0.0
        for row in rows:
            totalTime += row[0]

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text="The total time that we've been late this week is " + toTime(totalTime) + ".")

    elif command['text'].startswith('!latesemester'):
        rows = c.execute('''SELECT totalTimeLate FROM users WHERE active=1''')
        totalTime = 0.0
        for row in rows:
            totalTime += row[0]

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text="The total time that we've been late this semester is " + toTime(totalTime) + ".")

    elif command['text'].startswith('!workweek'):
        rows = c.execute('''SELECT timeSpentThisWeek FROM users WHERE active=1''')
        totalTime = 0.0
        for row in rows:
            totalTime += row[0]

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text="The total time that we've been hard at work this week is " + toTime(totalTime) + ".")

    elif command['text'].startswith('!worksemester'):
        rows = c.execute('''SELECT totalTimeSpent from users where active=1''')
        totalTime = 0.0
        for row in rows:
            totalTime += row[0]

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text="The total time that we've been hard at work this semester is  " + toTime(totalTime) + ".")


    # Shows who hasn't clocked in
    elif command['text'].startswith('!attendance'):
        # Return the list of people that aren't here
        message = "These people haven't clocked in yet today:\n"
        rows = c.execute('''SELECT realName, checkInDate FROM users WHERE checkInDate != ? AND active = 1 ORDER BY checkInDate DESC''', (datetime.date.today().toordinal(),))

        for row in rows:
            message += "*" + row[0] + "*: " + str(datetime.date.today().toordinal() - row[1])
            message += " day ago\n" if datetime.date.today().toordinal() - row[1] == 1 else " days ago\n"

        slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=message)


    # Get the usage
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

def publicUsage():
       return ("I can only do this in public channels:\n"
                + "*!standings*: View current standings for the week\n"
                + "*!attendance*: See who hasn't clocked in today\n"
                + "*!workweek*: See the cumulative time that people have worked this week\n"
                + "*!worksemester*: See the cumulative time that people have worked this semester\n"
                + "*!lateweek*: See the cumulative time that people have been late this week\n"
                + "*!latesemester*: See the cumulative time that people have been late this semester\n"
                + "*!usage*: This usage statement")

def privateUsage():
    return ("Try one of these:\n"
                + "*!in*: Clock in\n"
                + "*!intime number*: Clock in being _number_ minutes late. (For when you forget to clock in). Ex: !intime 5\n"
                + "*!out*: Clock out\n"
                + "*!outtime number*: Clock out having worked _number_ hours. Ex: !outtime 2 (worked 2 hours)\n"
                + "*!active*: Mark yourself active\n"
                + "*!status*: See your current late time this week\n"
                + "*!sumtime*: See the cumulative time that people have been late this week\n"
                + "*!attendance*: See who hasn't clocked in yet today\n"
                + "*!usage*: This usage statement")

def clock_in(command):
    if any(char.isdigit() for char in command['text']):
        slack_client.api_call("chat.postMessage", channel=command['channel'], 
                text="I noticed you included a number in your message. Did you mean to do *!intime*?", as_user = True) 
        return
        

    timeToBegin = getStartingTime()

    today = datetime.datetime.today()

    # There's an issue here, but I don't know what it is.
    startTime = datetime.datetime(today.year, today.month, today.day, hour=timeToBegin)
    difference = datetime.datetime.now() - startTime

    if difference.total_seconds() < 0:
        # You weren't late, so there's no need to update the table.
        delta = 0
    else:
        delta = difference.total_seconds()

    timeLateThisWeek = c.execute('''SELECT timeLateThisWeek, totalTimeLate, clockedIn, timeClockedInAt, realName, checkInDate FROM users WHERE id=? AND active=1''', (command['user'],))
    row = timeLateThisWeek.fetchone()
    
    if not row:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database or you're not marked active. Talk to an administrator.", as_user=True)
        return

    elif row[5] == datetime.date.today().toordinal():
        c.execute('''UPDATE users SET timeClockedInAt=?, clockedIn=1 WHERE id=?''', 
                                        (datetime.datetime.now().timestamp(),
                                        command['user'],))

        slack_client.api_call("reactions.add", channel=command['channel'], 
            name='thumbsup', timestamp=command['ts'])
        print(str(datetime.datetime.now()) + ": " + str(row[4]) + ' clocked in again')
    
    elif row[2] != 1:
        c.execute('''UPDATE users SET timeLateThisWeek=?, totalTimeLate=?, timeClockedInAt=?, checkInDate=?, clockedIn=1 WHERE id=?''', 
                                        (row[0] + delta, 
                                        row[1] + delta, 
                                        datetime.datetime.now().timestamp(),
                                        datetime.date.today().toordinal(), 
                                        command['user'],))

        slack_client.api_call("reactions.add", channel=command['channel'], 
            name='thumbsup', timestamp=command['ts'])
        print(str(datetime.datetime.now()) + ": " + str(row[4]) + ' clocked in')
    else:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are already clocked in!", as_user=True)

def in_late(command):

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

    timeLateThisWeek = c.execute('''SELECT timeLateThisWeek, totalTimeLate, clockedIn, realName FROM users WHERE id=? AND active=1''', (command['user'],))
    row = timeLateThisWeek.fetchone()

    if not row:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database or inactive. Talk to an administrator.", as_user=True)
        return
    if row[2] != 1:
        c.execute('''UPDATE users SET timeLateThisWeek=?, totalTimeLate=?, timeClockedInAt=?, checkInDate=?, clockedIn=1 WHERE id=?''', 
                                        (row[0] + secondsLate, 
                                        row[1] + secondsLate, 
                                        datetime.datetime(today.year, today.month, today.day, hour=getStartingTime() + secondsLate // 3600,
                                                            minute=(secondsLate % 3600) // 60,
                                                            second=secondsLate % 3600 % 60).timestamp(),
                                        datetime.date.today().toordinal(), 
                                        command['user'],))

        slack_client.api_call("reactions.add", channel=command['channel'], 
            name='thumbsup', timestamp=command['ts'])

        print(str(datetime.datetime.now()) + ": " + str(row[3]) + ' clocked in with !intime')
    else:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You already clocked in today!", as_user=True)

def clock_out(command):
    if any(char.isdigit() for char in command['text']):
        slack_client.api_call("chat.postMessage", channel=command['channel'], 
                text="I noticed you included a number in your message. Did you mean to do *!outtime*?", as_user = True) 
        return

    currentRow = c.execute('''SELECT timeSpentThisWeek, totalTimeSpent, clockedIn, timeClockedInAt, realName FROM users WHERE id=? AND active=1''', (command['user'],))
    row = currentRow.fetchone()
    
    if not row:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database or you're not marked active. Talk to an administrator.", as_user=True)
        return

    delta = datetime.datetime.now().timestamp() - float(row[3]) # Time spent in seconds
    
    if row[2] != 0:
        c.execute('''UPDATE users SET timeSpentThisWeek=?, totalTimeSpent=?, clockedIn=0 WHERE id=?''', 
                                        (row[0] + delta, 
                                        row[1] + delta, 
                                        command['user'],))

        slack_client.api_call("reactions.add", channel=command['channel'], 
            name='thumbsup', timestamp=command['ts'])
        print(str(datetime.datetime.now()) + ": " + str(row[4]) + ' clocked out')
    else:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are already clocked out!", as_user=True)

def out_late(command):

    try:
        hoursSpent = float(command['text'].split(' ')[1])
    except:
        slack_client.api_call("chat.postMessage", channel=command['channel'], 
                text="Invalid usage. Put the number of hours spent after *!outtime*.", as_user = True)
        return

    currentRow = c.execute('''SELECT timeSpentThisWeek, totalTimeSpent, clockedIn, timeClockedInAt, realName FROM users WHERE id=? AND active=1''', (command['user'],))
    row = currentRow.fetchone()
    
    if not row:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database or you're not marked active. Talk to an administrator.", as_user=True)
        return

    delta = hoursSpent * 3600 # Change it to seconds
    
    if row[2] != 0:
        c.execute('''UPDATE users SET timeSpentThisWeek=?, totalTimeSpent=?, clockedIn=0 WHERE id=?''', 
                                        (row[0] + delta, 
                                        row[1] + delta, 
                                        command['user'],))

        slack_client.api_call("reactions.add", channel=command['channel'], 
            name='thumbsup', timestamp=command['ts'])

        print(str(datetime.datetime.now()) + ": " + str(row[4]) + ' clocked out with !outtime')
    else:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are already clocked out!", as_user=True)

def add_user(command):
    currentRow = c.execute('''SELECT * FROM users WHERE id=?''', (command['user'],))
    row = currentRow.fetchone()

    if row:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are already in the database, if you're having issues, try *!active*.", as_user=True)
    else:
        users = slack_client.api_call("users.list")
        for user in users['members']:
            if user['id'] == command['user']:
                c.execute('INSERT INTO users VALUES (?, ?, 0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0)', (command['user'], user['name']))
                break
        slack_client.api_call("reactions.add", channel=command['channel'], 
            name='thumbsup', timestamp=command['ts'])
        # Mark them active automatically
        active(command)

def get_standings(command):
    # Show current standings
    text = "*Here are the current latest people this week:*\n"
    origText = text
    for user in c.execute('''SELECT realName, timeLateThisWeek FROM users WHERE active=1 ORDER BY timeLateThisWeek DESC LIMIT 5'''):
        if user[1] > 0:
            text += "*"+user[0]+"*: " + toTime(user[1]) + " late\n"

    if text == origText:
        text = "Nobody has been late this week. At least not _yet_"
    else:
        text+= "Better luck next time!"

    slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
            text=text, linkNames=False)

def reset(command):
    rows = c.execute('''SELECT realName, timeLateThisWeek, timeSpentThisWeek FROM users WHERE active=1''')
    # Write the current status to a csv
    with open(str(datetime.date.today()) + '-timesheet.csv', 'w') as f:
        csv_writer = csv.writer(f)
        for row in rows:
            csv_writer.writerow(row)

    # Resets the time for the week
    c.execute('''UPDATE users SET timeLateThisWeek=0.0, timeSpentThisWeek=0.0''')
    slack_client.api_call("chat.postMessage", channel=command['channel'], 
            text="Standings reset!", as_user=True)
    with open('reset.log', 'a+') as f:
        f.write(str(datetime.datetime.now()) + ': ' + command['user'] + ' reset timebot.\n')


def active(command):
    # Users mark themselves active
    if not c.execute('''UPDATE users SET active=1 WHERE id=?''', (command['user'],)) :
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database. Talk to an administrator.", as_user=True)
        return
    
    slack_client.api_call("reactions.add", channel=command['channel'], 
            name='white_check_mark', timestamp=command['ts'])
    print( command['user'] + " marked themselves active")

def inactive(command):
    # Users mark themselves inactive
    if not c.execute('''UPDATE users SET active=0 WHERE id=?''', (command['user'],)) :
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database. Talk to an administrator.", as_user=True)
        return
    slack_client.api_call("reactions.add", channel=command['channel'], 
            name='white_check_mark', timestamp=command['ts'])
    print( command['user'] + " marked themselves inactive")

def status(command):
    # Prints out their current late time
    response = c.execute('''SELECT id, timeLateThisWeek, timeSpentThisWeek FROM users WHERE id=?''', (command['user'],)).fetchone()
    if not response:
        slack_client.api_call("chat.postMessage", channel=command['channel'],
                text="You are not in the database. Talk to an administrator.", as_user=True)
        return

    if response[1] > 0:
        text = "You have been " + toTime(response[1]) + " late this week. "
    else:
        text = "You have not been late yet this week."

    text += " "

    if response[2] > 0:
        text += "You have worked for " + toTime(response[2]) + " this week. "
    else:
        text += "You have not done any work yet this week. "
    slack_client.api_call("chat.postMessage", channel=command["channel"], as_user=True,
                text=text)

def parse_slack_output(slack_rtm_output):
    """
    The Slack Real Time Messaging API is an events firehose.
    this parsing function returns None unless a message is
    directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and output['text'].startswith('!') and output['user'] != BOT_ID:
                return {'text': output['text'].strip().lower(),
                        'channel': output['channel'], 
                        'user': output['user'],
                        'ts': output['ts']}
    return None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = .3 # .3 second delay between reading from firehose

    # If the database doesn't exist, you rebuild it
    if not os.path.isfile("team.db"):
        initialize_db()

    # Open up the database
    conn = sqlite3.connect('team.db')
    c = conn.cursor()

    if slack_client.rtm_connect():
        print("TimeBot connected and running!")
        try:
            while True:
                try:
                    command = parse_slack_output(slack_client.rtm_read())
                # Sometimes the socket closes
                except (TimeoutError, websocket._exceptions.WebSocketConnectionClosedException) as e:
                    # We write what time it happened and what happened
                    with open('crash.log', 'a+') as f:
                        f.write(str(datetime.datetime.now()) + ': ' + str(type(e)) + '\n')
                    # Then we reconnect
                    if slack_client.rtm_connect():
                        print(str(datetime.datetime.now()) + ": RECOVERED FROM A CRASH")
                        continue
                    else:
                        print(str(datetime.datetime.now()) + ": Slack client failed to reconnect")
                        conn.close()
                        break
                if command:
                    try:
                        handle_command(command)
                    except:
                        slack_client.api_call("chat.postMessage", channel=command['channel'],
                            text="Whoa! You almost killed me! Talk to an administrator.", as_user=True)
                if not command:
                    time.sleep(READ_WEBSOCKET_DELAY)
        except KeyboardInterrupt:
            print()
            print( "Exiting cleanly")
            conn.close()
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
