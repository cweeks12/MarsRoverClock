import os
import time
from slackclient import SlackClient

# This code is taken from https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
# Visit that webpage to get the whole setup guide

# starterbot's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")


# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))


def handle_command(command):
    """
    Receives commands directed at the bot and determines if they
    are valid commands. If so, then acts on the commands. If not,
    returns back what it needs for clarification.
    """
    if command['text'].startswith('!in'):
        slack_client.api_call("reactions.add", channel=command['channel'], 
                name='thumbsup', timestamp=command['ts'])
    elif command['text'].startswith('!standings'):
        # Show current standings
        pass
    elif command['text'].startswith('!final'): # And it's a specific user
        # Reports the standings for the week, and resets the current values
        # Moves the current values to the last week column
        pass
    elif command['text'].startswith('!lastweek'): # And it's a specific user
        # Reports the standings for last week
        pass
    else:
        # Unknown command, print usage statement
        pass


def parse_slack_output(slack_rtm_output):
    """
    The Slack Real Time Messaging API is an events firehose.
    this parsing function returns None unless a message is
    directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    print output_list
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and output['text'].startswith('!'):
            # return text after the @ mention, whitespace removed
                return {'text': output['text'].strip().lower(),
                        'channel': output['channel'], 
                        'user': output['user'],
                        'ts': output['ts']}
    return {}


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            command = parse_slack_output(slack_client.rtm_read())
            if command:
                handle_command(command)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
