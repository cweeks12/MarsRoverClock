Mars Rover Clock
======
This is the Slack bot that is used by the BYU Mars Rover team to keep track of when people come in and how late they are.

I pulled the ideas from [Full Stack Python's Slack Bot Guide](https://www.fullstackpython.com/blog/build-first-slack-bot-python.html "Great read"). It's easy to set up and use. This link also gives a base line for setting up your own Slack Bot. Here's how you set up the bot for running on your own.

1. Go to the [Slack Bot API Page](https://api.slack.com/bot-users), sign into your Slack team, then scroll down to 'Custom Bot Users' and click on the 'Creating a New Bot User' link.
1. Name your bot, and copy the API token after you get it.
1. Open up your `~/.bashrc` and copy the following command into the bottom: `export SLACK_BOT_TOKEN='your token here'`.
1. Edit `starter.py` and change the bot name `'Timebot'` to the name of your own bot, then save it. Run `python3 starter.py`. The output of this program will be the `BOT_ID` of your bot. Copy the `U*******`, and put that into your `/.bashrc` as `export BOT_ID='copied bot id'`.
1. You're all set! Run `bot.py` and it should say it's connected and running! Send a direct message to him, and see what happens!

Usage
------
TBD

