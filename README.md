# Facebook Messenger Automation Bot

This project is a Telegram bot that automates the process of sending group messages on Facebook Messenger. It uses browser automation to log into Facebook, create group conversations, and send messages to multiple recipients simultaneously.

## Features

- Automated login to Facebook using cookies
- Bulk processing of multiple configurations
- Addition of multiple recipients to a group conversation
- Customizable group messages
- Telegram bot interface for easy interaction and control

## Requirements

- Python 3.7+
- playwright
- python-telegram-bot
- asyncio

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/taiayman/facebook-messenger-automation-bot.git
   cd facebook-messenger-automation-bot
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Telegram Bot Token:
   ```
   export TELEGRAM_BOT_TOKEN='your_telegram_bot_token_here'
   ```

## Usage

1. Start the bot:
   ```
   python facebook_group_inviter.py
   ```

2. Interact with the bot on Telegram using the following commands:
   - `/start` - Start the bot
   - `/help` - Show available commands
   - `/set_cookies` - Set Facebook cookies for authentication
   - `/add_name` - Add names from a text file
   - `/set_message <message>` - Set the message to be sent
   - `/show_config` - Display current configuration
   - `/run` - Start the automation process
   - `/bulk_cookies` - Start bulk cookie input process
   - `/finish_cookies` - Finish inputting cookies in bulk mode
   - `/finish_namesdata` - Finish inputting names in bulk mode

## Bulk Mode

The bot supports a bulk mode for processing multiple configurations:

1. Start with `/bulk_cookies`
2. Input cookies for each configuration
3. Use `/finish_cookies` when done
4. Upload text files with names for each configuration
5. Use `/finish_namesdata` when done
6. Input messages for each configuration
7. Use `/run` to start the bulk automation process

## Caution

This tool automates actions on Facebook. Make sure you comply with Facebook's terms of service and use this responsibly. Excessive or improper use may result in account restrictions.

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to check [issues page](https://github.com/taiayman/facebook-messenger-automation-bot/issues) if you want to contribute.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
