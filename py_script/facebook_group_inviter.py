import asyncio
import json
import logging
from datetime import datetime
import os
import random
from typing import List, Dict, Any

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, InvalidToken

# Suppress ResourceWarnings
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UserConfig:
    def _init_(self):
        self.cookies: List[Dict[str, Any]] | None = None
        self.names: List[str] | None = None
        self.message: str | None = None

    def is_complete(self):
        return all([self.cookies, self.names, self.message])

    def clear(self):
        self.cookies = None
        self.names = None
        self.message = None

class FacebookMessengerAutomation:
    def __init__(self, cookies: List[Dict[str, Any]], names: List[str], message: str):
        self.cookies = cookies
        self.names = names
        self.message = message
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.playwright = None

    async def initialize(self) -> None:
        logger.info("Initializing fresh browser session...")
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--no-first-run',
                '--no-default-browser-check',
                '--no-sandbox',
                '--disable-extensions',
                '--disable-sync',
                '--disable-default-apps',
                '--use-fake-ui-for-media-stream',
                '--disable-gpu',
                '--no-service-autorun',
                '--password-store=basic',
                '--use-mock-keychain',
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True,
        )
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(60000)  # Extended timeout to 60 seconds
        await self.load_cookies()

    async def load_cookies(self) -> None:
        logger.info("Loading cookies...")
        try:
            await self.context.add_cookies(self.cookies)
            logger.info(f"Successfully loaded {len(self.cookies)} cookies")
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}")
            raise

    async def open_facebook(self) -> None:
        logger.info("Navigating to Facebook main page...")
        await self.page.goto("https://www.facebook.com/")
        try:
            await self.page.wait_for_selector('div[role="main"]', state="visible", timeout=20000)
            logger.info("Successfully logged in to Facebook")
        except PlaywrightTimeoutError:
            logger.error("Failed to log in to Facebook. Cookie authentication may have failed.")
            await self.page.screenshot(path="facebook_login_failure.png")
            raise Exception("Failed to authenticate with Facebook using cookies")

    async def navigate_to_messenger(self) -> None:
        logger.info("Navigating to Messenger...")
        try:
            await self.page.goto("https://www.facebook.com/messages/t/")
            await self.page.wait_for_selector('a[aria-label="New message"]', state="visible", timeout=20000)
            logger.info("Successfully navigated to Messenger")
        except PlaywrightTimeoutError:
            logger.error("Failed to navigate to Messenger.")
            await self.page.screenshot(path="messenger_navigation_error.png")
            raise
        except Exception as e:
            logger.error(f"An error occurred while navigating to Messenger: {str(e)}")
            await self.page.screenshot(path="messenger_navigation_error.png")
            raise

    async def click_new_message(self) -> None:
        logger.info("Clicking 'New message' button...")
        try:
            await self.page.click('a[aria-label="New message"]')
            logger.info("Clicked 'New message' button")
        except PlaywrightTimeoutError:
            logger.error("Failed to find or click 'New message' button")
            await self.page.screenshot(path="new_message_button_error.png")
            raise

    async def add_user_to_conversation(self, user_name: str) -> bool:
        logger.info(f"Attempting to add {user_name} to the conversation...")
        try:
            input_selector = 'input[aria-label="Send message to"]'
            
            # Clear the input field before typing the new name
            await self.page.fill(input_selector, "")
            
            # Type the user name character by character with random delays
            for char in user_name:
                await self.page.type(input_selector, char, delay=random.uniform(100, 300))
                await asyncio.sleep(random.uniform(0.1, 0.3))

            await self.page.wait_for_selector('ul[role="listbox"]', state="visible", timeout=10000)
            await asyncio.sleep(random.uniform(1, 2))

            # Look for individual user option, not group
            user_options = await self.page.query_selector_all('li[role="option"]')
            individual_user = None
            for option in user_options:
                option_text = await option.inner_text()
                if user_name in option_text and "group" not in option_text.lower():
                    individual_user = option
                    break

            if individual_user:
                await individual_user.click()
                logger.info(f"Added user: {user_name}")
                
                # Wait for the user to be added and the input field to clear
                await self.page.wait_for_function(
                    '(selector) => document.querySelector(selector).value === ""',
                    input_selector
                )
                return True
            else:
                logger.warning(f"No matching individual user found for {user_name}")
                return False
        except Exception as e:
            logger.error(f"Error while trying to add {user_name}: {str(e)}")
            await self.page.screenshot(path=f"error_adding_{user_name}.png")
            return False

    async def process_names(self) -> None:
        logger.info("Processing names...")
        added_names = []
        failed_names = []

        try:
            for name in self.names:
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        success = await self.add_user_to_conversation(name)
                        if success:
                            added_names.append(name)
                            logger.info(f"Successfully added {name} to the conversation")
                            break
                        else:
                            logger.warning(f"Failed to add {name} to the conversation (Attempt {attempt + 1}/{max_attempts})")
                            if attempt == max_attempts - 1:
                                failed_names.append(name)
                    except Exception as e:
                        logger.error(f"Error adding {name}: {str(e)}")
                        if attempt == max_attempts - 1:
                            failed_names.append(name)
                    
                    await asyncio.sleep(random.uniform(3, 5))

            logger.info(f"Finished processing all names. Added: {len(added_names)}, Failed: {len(failed_names)}")

            if added_names:
                await self.send_group_message()
                await self.name_group()
                logger.info("Finished sending group message and naming the group")
            else:
                logger.warning("No names were added successfully. Skipping group creation.")

        except Exception as e:
            logger.error(f"Error in process_names: {str(e)}")
        finally:
            logger.info(f"Names added: {added_names}")
            logger.info(f"Names failed: {failed_names}")

    async def send_group_message(self) -> None:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                message_input_selector = 'div[aria-label="Message"][contenteditable="true"][role="textbox"]'
                await self.page.wait_for_selector(message_input_selector, state="visible", timeout=20000)
                await self.page.fill(message_input_selector, self.message)

                send_button_selector = 'div[aria-label="Press enter to send"][role="button"]'
                send_button = await self.page.wait_for_selector(send_button_selector, state="visible", timeout=20000)
                await send_button.click()
                logger.info("Clicked send button for group message")
                await self.page.wait_for_selector('span:has-text("Sent")', state="visible", timeout=20000)
                logger.info("Group message confirmed sent")
                break
            except Exception as e:
                logger.error(f"Error sending group message (Attempt {attempt + 1}/{max_attempts}): {str(e)}")
                if attempt == max_attempts - 1:
                    raise

    async def name_group(self) -> None:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                name_button_selector = 'div[aria-label="Name"][role="button"]'
                await self.page.wait_for_selector(name_button_selector, state="visible", timeout=20000)
                await self.page.click(name_button_selector)
                logger.info("Clicked 'Name' button")

                input_selector = 'input[maxlength="500"]'
                await self.page.wait_for_selector(input_selector, state="visible", timeout=20000)
                group_name = f"Automated Group {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                await self.page.fill(input_selector, group_name)
                logger.info(f"Entered group name: {group_name}")

                await asyncio.sleep(2)
                save_button_selector = 'div[aria-label="Save"][role="button"]:not([aria-disabled="true"])'
                await self.page.wait_for_selector(save_button_selector, state="visible", timeout=20000)
                await self.page.click(save_button_selector)
                logger.info("Clicked 'Save' button")
                await self.page.wait_for_selector('div[aria-label="Change chat name"]', state="hidden", timeout=20000)
                logger.info("Group naming completed")
                break
            except Exception as e:
                logger.error(f"Error naming the group (Attempt {attempt + 1}/{max_attempts}): {str(e)}")
                if attempt == max_attempts - 1:
                    raise



    async def process_names(self) -> None:
        logger.info("Processing names...")
        try:
            for name in self.names:
                success = await self.add_user_to_conversation(name)
                if not success:
                    logger.warning(f"Failed to add {name} to the conversation")
                await asyncio.sleep(random.uniform(2, 4))
            logger.info("Finished adding all users to the conversation")
            await self.send_group_message()
            logger.info("Finished sending group message and naming the group")
        except Exception as e:
            logger.error(f"Error processing names: {str(e)}")
            raise

    

    async def run(self) -> None:
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                await self.initialize()
                await self.open_facebook()
                if await self.page.query_selector('button[data-testid="royal_login_button"]'):
                    raise Exception("Cookie authentication failed")

                await self.navigate_to_messenger()
                await self.click_new_message()
                await self.process_names()
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("All authentication attempts failed")
                    await self.page.screenshot(path=f"auth_failure_attempt_{attempt + 1}.png")
            finally:
                await self.cleanup()

        logger.info("Automation process completed")

    async def cleanup(self) -> None:
        logger.info("Cleaning up browser session...")
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def fix_cookie(self, cookie: Dict[str, Any]) -> Dict[str, Any]:
        fixed_cookie = cookie.copy()
        required_fields = ['name', 'value', 'domain']
        for field in required_fields:
            if field not in fixed_cookie:
                raise ValueError(f"Cookie is missing required field: {field}")

        unsupported_fields = ['hostOnly', 'session', 'storeId']
        for field in unsupported_fields:
            fixed_cookie.pop(field, None)

        if 'sameSite' in fixed_cookie:
            valid_same_site = ['Strict', 'Lax', 'None']
            if fixed_cookie['sameSite'] not in valid_same_site:
                fixed_cookie['sameSite'] = 'Lax'

        if 'expirationDate' in fixed_cookie:
            fixed_cookie['expires'] = int(fixed_cookie['expirationDate'])
            del fixed_cookie['expirationDate']

        return fixed_cookie

    async def load_cookies(self) -> None:
        logger.info("Starting to load cookies...")
        try:
            fixed_cookies = []
            for cookie in self.cookies:
                try:
                    fixed_cookie = self.fix_cookie(cookie)
                    fixed_cookies.append(fixed_cookie)
                    logger.debug(f"Processed cookie: {fixed_cookie['name']}")
                except Exception as e:
                    logger.warning(f"Error processing cookie {cookie.get('name', 'unknown')}: {str(e)}")

            logger.info(f"Attempting to add {len(fixed_cookies)} cookies to the browser context")
            await self.context.add_cookies(fixed_cookies)
            logger.info("Cookies loaded successfully")
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}")
            raise

    async def open_facebook(self) -> None:
        logger.info("Navigating to Facebook main page...")
        await self.page.goto("https://www.facebook.com/")
        try:
            login_status = await self.page.wait_for_selector('div[aria-label="Facebook"], button[data-testid="royal_login_button"]', state="visible", timeout=20000)
            if await login_status.get_attribute('aria-label') == 'Facebook':
                logger.info("Successfully logged in to Facebook")
            else:
                logger.warning("Not logged in to Facebook. Cookie authentication may have failed.")
                await self.page.screenshot(path="facebook_login_page.png")
                raise Exception("Failed to authenticate with Facebook")
        except PlaywrightTimeoutError:
            logger.error("Failed to load Facebook main page or determine login status.")
            await self.page.screenshot(path="facebook_load_error.png")
            raise

async def navigate_to_messenger(self) -> None:
    logger.info("Navigating to Messenger...")
    try:
        # Replace "See more" click with the specified div click
        div_selector = 'div.x78zum5.xdt5ytf.xq8finb.x1xmf6yo.x1e56ztr.x1n2onr6.xamitd3.x1ywmky0.xnd27nj.xv2ei83.x1og3r51.xv3fwf9'
        await self.page.wait_for_selector(div_selector, state="visible", timeout=10000)
        await self.page.click(div_selector)
        logger.info("Clicked the specified div")

        messenger_link = await self.page.wait_for_selector('span:has-text("Messenger")', state="visible", timeout=10000)
        await messenger_link.click()
        logger.info("Clicked Messenger option")

        await self.page.wait_for_selector('a[aria-label="New message"]', state="visible", timeout=20000)
        logger.info("Successfully navigated to Messenger")

        await self.close_sync_history_popup()
    except PlaywrightTimeoutError:
        logger.error("Failed to navigate to Messenger. The layout might have changed.")
        await self.page.screenshot(path="messenger_navigation_error.png")
        raise
    except Exception as e:
        logger.error(f"An error occurred while navigating to Messenger: {str(e)}")
        await self.page.screenshot(path="messenger_navigation_error.png")
        raise


    async def close_sync_history_popup(self) -> None:
        logger.info("Checking for sync history popup...")
        try:
            close_button_selector = 'div[aria-label="Close"][role="button"]'
            close_button = await self.page.wait_for_selector(close_button_selector, state="visible", timeout=10000)

            if close_button:
                await close_button.click()
                logger.info("Clicked close button on sync history popup")

                dont_sync_selector = 'div[aria-label="Don\'t sync"][role="button"][tabindex="0"]'
                dont_sync_button = await self.page.wait_for_selector(dont_sync_selector, state="visible", timeout=5000)

                if dont_sync_button:
                    await asyncio.sleep(1)
                    await dont_sync_button.click()
                    logger.info("Clicked 'Don't sync' on the confirmation popup")
                    await self.page.wait_for_selector(dont_sync_selector, state="hidden", timeout=5000)
                    logger.info("Successfully closed sync history popup")
                else:
                    logger.warning("'Don't sync' button not found after closing initial popup")
            else:
                logger.warning("Close button not found on sync history popup")
        except PlaywrightTimeoutError as e:
            logger.warning(f"Timeout while handling sync history popup: {str(e)}")
            await self.page.screenshot(path="sync_popup_timeout.png")
        except Exception as e:
            logger.error(f"Error while handling sync history popup: {str(e)}")
            await self.page.screenshot(path="sync_popup_error.png")

class TelegramBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.user_config = UserConfig()
        self.bulk_configs: List[UserConfig] = []
        self.current_bulk_index = 0
        self.bulk_mode = False
        self.bulk_stage = None

        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("set_cookies", self.set_cookies))
        self.application.add_handler(CommandHandler("add_name", self.add_name))
        self.application.add_handler(CommandHandler("set_message", self.set_message))
        self.application.add_handler(CommandHandler("run", self.run_automation))
        self.application.add_handler(CommandHandler("show_config", self.show_config))
        self.application.add_handler(CommandHandler("bulk_cookies", self.start_bulk_cookies))
        self.application.add_handler(CommandHandler("finish_cookies", self.finish_cookies))
        self.application.add_handler(CommandHandler("finish_namesdata", self.finish_namesdata))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_input))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.process_name_file))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('Merhba bik f bot dyal l\'automation dyal Facebook Messenger! Kteb /help bach tchouf l\'awamir li kaynin.')

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = """
        Ha l'awamir li kaynin:
        /start - Bda l-bot
        /help - Werri had l-message dyal l-mosa3ada
        /set_cookies - Bda l-3amaliya dyal tsjil l-cookies
        /add_name - Zid smiyat men fichier txt
        /set_message <risala> - 7et risala li bghiti tsift
        /show_config - Werri l-configuration l7aliya
        /run - Bda l-automation
        /bulk_cookies - Bda l-3amaliya dyal bulk cookies
        /finish_cookies - Kmmel l-3amaliya dyal dkhal l-cookies
        /finish_namesdata - Kmmel l-3amaliya dyal dkhal l-smiyat
        """
        await update.message.reply_text(help_text)

    async def set_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.bulk_mode:
            await update.message.reply_text("3afak 3tini l-cookies dyalek. Json wla b ay tari9a bghiti 😉.")
        else:
            await update.message.reply_text(f"3afak 3tini l-cookies {self.current_bulk_index + 1}.")

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.bulk_mode:
            if self.bulk_stage == "cookies":
                await self.handle_bulk_cookies(update, context)
            elif self.bulk_stage == "message":
                await self.handle_bulk_message(update, context)
        else:
            await self.handle_cookie_input(update, context)

    async def handle_cookie_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            cookies_input = update.message.text.strip()
            if cookies_input.startswith('[') and cookies_input.endswith(']'):
                cookies = json.loads(cookies_input)
            else:
                cookies = self.parse_cookie_string(cookies_input)
            
            if self.bulk_mode:
                new_config = UserConfig()
                new_config.cookies = cookies
                self.bulk_configs.append(new_config)
                await update.message.reply_text(f"L-cookies {self.current_bulk_index + 1} tzado.")
                self.current_bulk_index += 1
                if self.current_bulk_index < 100:  # Limit to 100 configurations
                    await update.message.reply_text(f"3tini l-cookies {self.current_bulk_index + 1}, wla kteb /finish_cookies ila kmmelti.")
                else:
                    await self.finish_cookies(update, context)
            else:
                self.user_config.cookies = cookies
                await update.message.reply_text("L-cookies li 3titini s7a7 ✅ sir 3lah.")
        except json.JSONDecodeError:
            await update.message.reply_text("L-format dyal JSON ma s7i7ch. 3afak 3awed.")
        except Exception as e:
            await update.message.reply_text(f"kayn chi mochkil: {str(e)}")

    def parse_cookie_string(self, cookie_string: str) -> List[Dict[str, Any]]:
        cookies = []
        for cookie in cookie_string.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": ".facebook.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True
                })
        return cookies

    async def add_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.bulk_mode:
            await update.message.reply_text(f"3afak uploadiya fichier txt fih smiyat l-config {self.current_bulk_index + 1}.")
        else:
            await update.message.reply_text("3afak uploadiya fichier txt fih smiyat (kol smiya f ster wa7ed).")

    async def process_name_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message.document.file_name.lower().endswith('.txt'):
            file = await context.bot.get_file(update.message.document.file_id)
            file_content = await file.download_as_bytearray()
            try:
                names = file_content.decode('utf-8').split('\n')
                names = [name.strip() for name in names if name.strip()]
                if self.bulk_mode and self.bulk_stage == "names":
                    self.bulk_configs[self.current_bulk_index].names = names
                    await update.message.reply_text(f"Tmmat l-3amaliya. Tzado {len(names)} d smiyat l-config {self.current_bulk_index + 1}.")
                    self.current_bulk_index += 1
                    if self.current_bulk_index < len(self.bulk_configs):
                        await update.message.reply_text(f"3afak uploadiya fichier txt fih smiyat l-config {self.current_bulk_index + 1}.")
                    else:
                        await update.message.reply_text("Kmlti dkhal l-smiyat dyal ga3 l-configurations. Db clicki 3la /finish_namesdata bash tdoz l-message.")
                elif not self.bulk_mode:
                    self.user_config.names = names
                    await update.message.reply_text(f"Tmmat l-3amaliya. Tzado {len(names)} d smiyat men l-fichier.")
            except Exception as e:
                await update.message.reply_text(f"Mochkil f l-9raya dyal l-fichier: {str(e)}")
        else:
            await update.message.reply_text("3afak uploadiya fichier txt.")


    async def set_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.bulk_mode:
            await update.message.reply_text(f"3afak 3tini l-message l-config {self.current_bulk_index + 1}.")
        else:
            await update.message.reply_text("3afak 3tini l-message li bghiti tsift. Kifach tste3melha: /set_message Salam, labas?")



    async def handle_bulk_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            cookies_input = update.message.text.strip()
            if cookies_input.startswith('[') and cookies_input.endswith(']'):
                cookies = json.loads(cookies_input)
            else:
                cookies = self.parse_cookie_string(cookies_input)
            
            new_config = UserConfig()
            new_config.cookies = cookies
            self.bulk_configs.append(new_config)
            
            await update.message.reply_text(f"L-cookies {self.current_bulk_index + 1} tzado.")
            self.current_bulk_index += 1
            if self.current_bulk_index < 100:  # Limit to 100 configurations
                await update.message.reply_text(f"3tini l-cookies {self.current_bulk_index + 1}, wla kteb /finish_cookies ila kmmelti.")
            else:
                await self.finish_cookies(update, context)
        except json.JSONDecodeError:
            await update.message.reply_text("L-format dyal JSON ma s7i7ch. 3afak 3awed.")
        except Exception as e:
            await update.message.reply_text(f"kayn chi mochkil: {str(e)}")




    async def handle_bulk_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message.text.strip()
        self.bulk_configs[self.current_bulk_index].message = message
        await update.message.reply_text(f"L-message l-config {self.current_bulk_index + 1} t7et.")
        
        self.current_bulk_index += 1
        if self.current_bulk_index < len(self.bulk_configs):
            await update.message.reply_text(f"3tini l-message l-config {self.current_bulk_index + 1}.")
        else:
            await update.message.reply_text("Kmmelti dkhal ga3 l-messages. Kteb /run bash tbda l-automation.")
            self.bulk_mode = False
            self.bulk_stage = None

    async def show_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.bulk_mode:
            config_text = "L-bulk configurations l7aliyin:\n"
            for i, config in enumerate(self.bulk_configs, 1):
                config_text += f"\nConfiguration {i}:\n"
                config_text += f"Cookies: {'Kaynin' if config.cookies else 'Ma kaynin-ch'}\n"
                config_text += f"Smiyat: {len(config.names) if config.names else 'Ma kaynin-ch'}\n"
                config_text += f"Message: {config.message if config.message else 'Ma kayn-ch'}\n"
        else:
            config_text = "L-configuration l7aliya:\n"
            config_text += f"Cookies: {'Kaynin' if self.user_config.cookies else 'Ma kaynin-ch'}\n"
            config_text += f"Smiyat: {len(self.user_config.names) if self.user_config.names else 'Ma kaynin-ch'}\n"
            config_text += f"Message: {self.user_config.message if self.user_config.message else 'Ma kayn-ch'}"
        
        if len(config_text) > 4096:
            chunks = [config_text[i:i+4096] for i in range(0, len(config_text), 4096)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(config_text)

    async def start_bulk_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.bulk_mode = True
        self.bulk_stage = "cookies"
        self.bulk_configs = []
        self.current_bulk_index = 0
        await update.message.reply_text("Bda l-3amaliya dyal bulk cookies. 3tini l-cookies 1.")

    async def finish_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.bulk_stage = "names"
        self.current_bulk_index = 0
        await update.message.reply_text(f"Kmmelti dkhal l-cookies. Daba ghadi ndkhlou l-smiyat. 3afak uploadiya fichier txt fih smiyat l-config 1.")

    async def finish_namesdata(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.bulk_stage = "message"
        self.current_bulk_index = 0
        await update.message.reply_text(f"Kmmelti dkhal l-smiyat. Daba 3tini l-message l-config 1.")

    async def run_automation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.bulk_configs:
            try:
                await update.message.reply_text("Bda l-automation dyal bulk configurations. Ghadi yakhod chwiya d-lwe9t...")
                for i, config in enumerate(self.bulk_configs, 1):
                    if config.is_complete():
                        await update.message.reply_text(f"Kan kheddem configuration {i}/{len(self.bulk_configs)}...")
                        automation = FacebookMessengerAutomation(
                            config.cookies,
                            config.names,
                            config.message
                        )
                        await automation.run()
                        await update.message.reply_text(f"Configuration {i}/{len(self.bulk_configs)} kmelat.")
                    else:
                        await update.message.reply_text(f"Configuration {i}/{len(self.bulk_configs)} na9sa, kan fotha.")
                await update.message.reply_text("L-automation dyal bulk configurations kmelat.")
            except Exception as e:
                logger.error(f"Mochkil f l-automation: {e}", exc_info=True)
                error_message = f"T3te9 chi mochkil f l-automation: {str(e)}\n\n"
                error_message += "Honk 3la log files bach tchouf l-tafasil dyalhom."
                if hasattr(e, '_cause') and e.cause_:
                    error_message += f"\n\nSbab l-mochkil: {str(e._cause_)}"
                await update.message.reply_text(error_message)
        elif self.user_config.is_complete():
            try:
                await update.message.reply_text("Bda l-automation. Ghadi yakhod chwiya d-lwe9t...")
                automation = FacebookMessengerAutomation(
                    self.user_config.cookies,
                    self.user_config.names,
                    self.user_config.message
                )
                await automation.run()
                await update.message.reply_text("L-automation kmlat.")
            except Exception as e:
                logger.error(f"Mochkil f l-automation: {e}", exc_info=True)
                error_message = f"T3te9 chi mochkil f l-automation: {str(e)}\n\n"
                error_message += "Honk 3la log files bach tchouf l-tafasil dyalhom."
                if hasattr(e, '_cause') and e.cause_:
                    error_message += f"\n\nSbab l-mochkil: {str(e._cause_)}"
                await update.message.reply_text(error_message)
        else:
            missing = []
            if not self.user_config.cookies:
                missing.append("cookies")
            if not self.user_config.names:
                missing.append("smiyat")
            if not self.user_config.message:
                missing.append("message")
            await update.message.reply_text(f"3afak 7et ga3 l-m3lomat li khasin ({', '.join(missing)}) 9bel ma tbda l-automation.")

    async def start_polling(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self):
        await self.application.stop()
        await self.application.shutdown()

async def main():
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
        print("Please set your Telegram bot token as an environment variable and try again.")
        return

    bot = TelegramBot(telegram_bot_token)
    try:
        print("Bda l-bot...")
        await bot.start_polling()
        print("L-bot khdam. Wrek 3la Ctrl+C bach tw9fo.")
        while True:
            await asyncio.sleep(1)
    except InvalidToken:
        print("Error: The provided Telegram bot token is invalid.")
        print("Please check your token and try again.")
    except TimedOut:
        print("Error: The connection to the Telegram server timed out.")
        print("Please check your internet connection and try again.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        try:
            print("Kan w9ef l-bot...")
            await bot.stop()
            print("L-bot tw9ef.")
        except Exception as e:
            print(f"Error occurred while stopping the bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())