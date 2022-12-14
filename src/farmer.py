import json
import os
import platform
import random
import subprocess
import time
import urllib.parse
from urllib3.exceptions import MaxRetryError, NewConnectionError
from pathlib import Path
from datetime import date, datetime, timedelta
from notifiers import get_notifier
from PyQt5.QtCore import QObject, pyqtSignal, QTime
import copy
from .exceptions import *

import ipapi
import requests
from func_timeout import FunctionTimedOut, func_set_timeout
from random_word import RandomWords
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import (ElementNotInteractableException,
                                        NoAlertPresentException,
                                        NoSuchElementException,
                                        SessionNotCreatedException,
                                        TimeoutException,
                                        UnexpectedAlertPresentException,
                                        InvalidSessionIdException,)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options


class Farmer(QObject):
    finished = pyqtSignal()
    points = pyqtSignal(int)
    section = pyqtSignal(str)
    detail = pyqtSignal(str)
    stop_button_enabled = pyqtSignal(bool)
    accounts_info_sig = pyqtSignal()
    
    PC_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.46'
    MOBILE_USER_AGENT = 'Mozilla/5.0 (Linux; Android 12; SM-N9750) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36 EdgA/108.0.1462.48'
    base_url = "https://rewards.microsoft.com"
    
    def __init__(self, ui):
        super(Farmer, self).__init__()
        self.ui = ui
        self.accounts = self.ui.accounts
        self.config: dict = self.ui.config
        self.accounts_path = Path(self.ui.accounts_lineedit.text())
        self.browser: WebDriver = None
        self.points_counter: int = 0
        self.finished_accounts: list = []
        self.locked_accounts: list = []
        self.suspended_accounts: list = []
        self.current_account: str = None
        self.browser: WebDriver = None
        self.starting_points: int = None
        self.point_counter: int = 0
        self.logs: dict = {}
        self.get_or_create_logs()
        self.lang, self.geo, self.tz = self.get_ccode_lang_and_offset()
    
    def create_message(self):
        """Create message from logs to send to Telegram"""
        today = date.today().strftime("%d/%m/%Y")
        message = f'???? Daily report {today}\n\n'
        for index, value in enumerate(self.logs.items(), 1):
            redeem_message = None
            if value[1].get("Redeem goal title", None):
                redeem_title = value[1].get("Redeem goal title", None)
                redeem_price = value[1].get("Redeem goal price")
                redeem_count = value[1]["Points"] // redeem_price
                if redeem_count > 1:
                    redeem_message = f"???? Ready to redeem: {redeem_title} for {redeem_price} points ({redeem_count}x)\n\n"
                else:
                    redeem_message = f"???? Ready to redeem: {redeem_title} for {redeem_price} points\n\n"
            if value[1]['Last check'] == str(date.today()):
                status = '??? Farmed'
                new_points = value[1]["Today's points"]
                total_points = value[1]["Points"]
                message += f"{index}. {value[0]}\n???? Status: {status}\n?????? Earned points: {new_points}\n???? Total points: {total_points}\n"
                if redeem_message:
                    message += redeem_message
                else:
                    message += "\n"
            elif value[1]['Last check'] == 'Your account has been suspended':
                status = '??? Suspended'
                message += f"{index}. {value[0]}\n???? Status: {status}\n\n"
            elif value[1]['Last check'] == 'Your account has been locked !':
                status = '?????? Locked'
                message += f"{index}. {value[0]}\n???? Status: {status}\n\n"
            elif value[1]['Last check'] == 'Unusual activity detected !':
                status = '?????? Unusual activity detected'
                message += f"{index}. {value[0]}\n???? Status: {status}\n\n"
            elif value[1]['Last check'] == 'Unknown error !':
                status = '?????? Unknow error occured'
                message += f"{index}. {value[0]}\n???? Status: {status}\n\n"
            else:
                status = f'Farmed on {value[1]["Last check"]}'
                new_points = value[1]["Today's points"]
                total_points = value[1]["Points"]
                message += f"{index}. {value[0]}\n???? Status: {status}\n?????? Earned points: {new_points}\n???? Total points: {total_points}\n"
                if redeem_message:
                    message += redeem_message
                else:
                    message += "\n"
        return message

    def send_report_to_telegram(self, message):
        t = get_notifier('telegram') 
        t.notify(message=message, token=self.config["telegram"]["token"], chat_id=self.config["telegram"]["chatID"])
    
    def check_internet_connection(self):
        system = platform.system()
        while True:
            try:
                if self.ui.farmer_thread.isInterruptionRequested():
                    self.finished.emit()
                    self.ui.enable_elements()
                    return False
                if system == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.check_output(["ping", "-n", "1", "8.8.8.8"], timeout=5, startupinfo=si)
                elif system == "Linux":
                    subprocess.check_output(["ping", "-c", "1", "8.8.8.8"], timeout=5)
                self.section.emit("-")
                self.detail.emit("-")
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                self.section.emit("No internet connection...")
                self.detail.emit("Checking...")
                time.sleep(1)
    
    def get_or_create_logs(self):
        """Read logs and check whether account farmed or not"""
        shared_items =[]
        try:
            self.logs = json.load(open(f"{self.accounts_path.parent}/Logs_{self.accounts_path.stem}.txt", "r"))
            # delete Time period from logs
            self.logs.pop("Elapsed time", None)
            # sync accounts and logs file for new accounts or remove accounts from logs.
            for user in self.accounts:
                shared_items.append(user['username'])
                if not user['username'] in self.logs.keys():
                    self.logs[user["username"]] = {"Last check": "",
                                            "Today's points": 0,
                                            "Points": 0}
            if shared_items != self.logs.keys():
                diff = self.logs.keys() - shared_items
                for accs in list(diff):
                    del self.logs[accs]
            
            # check that if any of accounts has farmed today or not.
            for account in self.logs.keys():
                if self.logs[account]["Last check"] == str(date.today()) and list(self.logs[account].keys()) == ['Last check',
                                                                                                                "Today's points",
                                                                                                                'Points']:
                    self.finished_accounts.append(account)
                elif self.logs[account]['Last check'] == 'Your account has been suspended':
                    self.suspended_accounts.append(account)
                elif self.logs[account]['Last check'] == str(date.today()) and list(self.logs[account].keys()) == ['Last check', 
                                                                                                                   "Today's points", 
                                                                                                                   'Points',
                                                                                                                   'Daily',
                                                                                                                   'Punch cards',
                                                                                                                   'More promotions',
                                                                                                                   'PC searches',
                                                                                                                   'Mobile searches']:
                    if not self.does_account_need_farm(account):
                        self.current_account = account
                        self.clean_logs()
                        self.finished_accounts.append(account)
                        self.current_account = None
                    else:
                        continue
                else:
                    self.logs[account]['Daily'] = False
                    self.logs[account]['Punch cards'] = False
                    self.logs[account]['More promotions'] = False
                    self.logs[account]['PC searches'] = False 
                    self.logs[account]['Mobile searches'] = False
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            for account in self.accounts:
                self.logs[account["username"]] = {"Last check": "",
                                            "Today's points": 0,
                                            "Points": 0,
                                            "Daily": False,
                                            "Punch cards": False,
                                            "More promotions": False,
                                            "PC searches": False,
                                            "Mobile searches": False}
        finally:
            self.update_logs()
            self.accounts_info_sig.emit()
        
    def update_logs(self):
        """Update logs with new data"""
        logs = copy.deepcopy(self.logs)
        for account in logs:
            if account == "Elapsed time": continue
            logs[account].pop("Redeem goal title", None)
            logs[account].pop("Redeem goal price", None)
        with open(f'{self.accounts_path.parent}/Logs_{self.accounts_path.stem}.txt', 'w') as file:
            file.write(json.dumps(logs, indent = 4))

    def clean_logs(self):
        """Delete Daily, Punch cards, More promotions, PC searches and Mobile searches from logs"""
        self.logs[self.current_account].pop("Daily", None)
        self.logs[self.current_account].pop("Punch cards", None)
        self.logs[self.current_account].pop("More promotions", None)
        self.logs[self.current_account].pop("PC searches", None)
        self.logs[self.current_account].pop("Mobile searches", None)
    
    def is_pc_need(self) -> bool:
        """Check if browser for PC is needed or not based on farm options and account status"""
        if self.config["farmOptions"]["dailyQuests"] and self.logs[self.current_account]["Daily"] == False:
            return True
        elif self.config["farmOptions"]["punchCards"] and self.logs[self.current_account]["Punch cards"] == False:
            return True
        elif self.config["farmOptions"]["moreActivities"] and self.logs[self.current_account]["More promotions"] == False:
            return True
        elif self.config["farmOptions"]["searchPC"] and self.logs[self.current_account]["PC searches"] == False:
            return True
        else:
            return False
    
    def does_account_need_farm(self, account: str):
        """Check that does the account need to be farmed based on logs and options"""
        conditions = []
        if self.config["farmOptions"]["dailyQuests"] and not self.logs[account]["Daily"]:
            conditions.append(True)
        if self.config["farmOptions"]["punchCards"] and not self.logs[account]["Punch cards"]:
            conditions.append(True)
        if self.config["farmOptions"]["moreActivities"] and not self.logs[account]["More promotions"]:
            conditions.append(True)
        if self.config["farmOptions"]["searchPC"] and not self.logs[account]["PC searches"]:
            conditions.append(True)
        if self.config["farmOptions"]["searchMobile"] and not self.logs[account]["Mobile searches"]:
            conditions.append(True)
        if any(conditions):
            return True
        else:
            return False
    
    def is_element_exists(self, _by: By, element: str) -> bool:
        '''Returns True if given element exists else False'''
        try:
            self.browser.find_element(_by, element)
        except NoSuchElementException:
            return False
        return True
    
    def find_between(self, s: str, first: str, last: str) -> str:
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
    
    def browser_setup(self, isMobile: bool = False, user_agent = PC_USER_AGENT):
        # Create Chrome browser
        options = Options()
        if self.config["globalOptions"]["session"]:
            if not isMobile:
                options.add_argument(f'--user-data-dir={self.accounts_path.parent}/Profiles/{self.current_account}/PC')
            else:
                options.add_argument(f'--user-data-dir={self.accounts_path.parent}/Profiles/{self.current_account}/Mobile')
        options.add_argument("user-agent=" + user_agent)
        options.add_argument('lang=' + self.lang.split("-")[0])
        options.add_argument('--disable-blink-features=AutomationControlled')
        prefs = {"profile.default_content_setting_values.geolocation": 2,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "webrtc.ip_handling_policy": "disable_non_proxied_udp",
                "webrtc.multiple_routes_enabled": False,
                "webrtc.nonproxied_udp_enabled" : False}
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        if self.config.get("globalOptions", False).get("headless", False):
            options.add_argument("--headless")
        options.add_argument('log-level=3')
        options.add_argument("--start-maximized")
        chrome_service = ChromeService()
        if platform.system() == 'Linux':
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        if platform.system() == 'Windows':
            chrome_service.creationflags = subprocess.CREATE_NO_WINDOW
        chrome_browser_obj = webdriver.Chrome(options=options, service=chrome_service)
        self.browser = chrome_browser_obj
        return self.browser
    
    def login(self, email: str, pwd: str, isMobile: bool = False):
        """Login into  Microsoft account"""
        login_message = "Logging in..." if not isMobile else "Logging in mobile..."
        self.section.emit(login_message)
        # Close welcome tab for new sessions
        if self.config["globalOptions"]["session"]:
            time.sleep(2)
            if len(self.browser.window_handles) > 1:
                current_window = self.browser.current_window_handle
                for handler in self.browser.window_handles:
                    if handler != current_window:
                        self.browser.switch_to.window(handler)
                        time.sleep(0.5)
                        self.browser.close()
                self.browser.switch_to.window(current_window)
        # Access to bing.com
        self.browser.get('https://login.live.com/')
        # Check if account is already logged in
        if self.config["globalOptions"]["session"]:
            if self.browser.title == "We're updating our terms" or self.is_element_exists(By.ID, 'iAccrualForm'):
                time.sleep(2)
                self.browser.find_element(By.ID, 'iNext').click()
                time.sleep(5)
            if self.browser.title == 'Is your security info still accurate?' or self.is_element_exists(By.ID, 'iLooksGood'):
                time.sleep(2)
                self.browser.find_element(By.ID, 'iLooksGood').click()
                time.sleep(5)
            if self.browser.title == 'Microsoft account | Home' or self.is_element_exists(By.ID, 'navs_container'):
                self.detail.emit("Microsoft Rewards...")
                self.rewards_login()
                self.detail.emit("Bing...")
                self.check_bing_login(isMobile)
                return
            elif self.browser.title == 'Your account has been temporarily suspended':
                raise AccountLockedException('Your account has been locked !')
            elif self.is_element_exists(By.ID, 'mectrl_headerPicture') or 'Sign In or Create' in self.browser.title:
                if self.is_element_exists(By.ID, 'i0118'):
                    self.browser.find_element(By.ID, "i0118").send_keys(pwd)
                    time.sleep(2)
                    self.browser.find_element(By.ID, 'idSIButton9').click()
                    time.sleep(5)
                    self.section.emit("Logged in")
                    self.detail.emit("Microsoft Rewards...")
                    self.rewards_login()
                    self.detail.emit("Bing...")
                    self.check_bing_login(isMobile)
                    return None
        # Wait complete loading
        self.wait_until_visible(By.ID, 'loginHeader', 10)
        # Enter email
        self.browser.find_element(By.NAME, "loginfmt").send_keys(email)
        # Click next
        self.browser.find_element(By.ID, 'idSIButton9').click()
        # Wait 2 seconds
        time.sleep(5 if not self.config["globalOptions"]["fast"] else 2)
        # Wait complete loading
        self.wait_until_visible(By.ID, 'loginHeader', 10)
        # Enter password
        self.browser.find_element(By.ID, "i0118").send_keys(pwd)
        # Click next
        self.browser.find_element(By.ID, 'idSIButton9').click()
        # Wait 5 seconds
        time.sleep(5)
        try:
            if self.browser.title == "We're updating our terms" or self.is_element_exists(By.ID, 'iAccrualForm'):
                time.sleep(2)
                self.browser.find_element(By.ID, 'iNext').click()
                time.sleep(5)
            if self.browser.title == 'Is your security info still accurate?' or self.is_element_exists(By.ID, 'iLooksGood'):
                time.sleep(2)
                self.browser.find_element(By.ID, 'iLooksGood').click()
                time.sleep(5)
            if self.config["globalOptions"]["session"]:
                # Click Yes to stay signed in.
                self.browser.find_element(By.ID, 'idSIButton9').click()
            else:
                # Click No.
                self.browser.find_element(By.ID, 'idBtn_Back').click()
        except NoSuchElementException:
            # Check for if account has been locked.
            if self.browser.title == "Your account has been temporarily suspended" or self.is_element_exists(By.CLASS_NAME, "serviceAbusePageContainer  PageContainer"):
                raise AccountLockedException("Your account has been locked !")
            elif self.browser.title == "Help us protect your account":
                raise UnusualActivityException("Unusual activity detected")
            else:
                raise UnhandledException('Unknown error !')
        # Wait 5 seconds
        time.sleep(5)
        # Click Security Check
        try:
            self.browser.find_element(By.ID, 'iLandingViewAction').click()
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        # Wait complete loading
        try:
            self.wait_until_visible(By.ID, 'KmsiCheckboxField', 10)
        except (TimeoutException) as e:
            pass
        # Click next
        try:
            self.browser.find_element(By.ID, 'idSIButton9').click()
            # Wait 5 seconds
            time.sleep(5)
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        # Check Microsoft Rewards
        self.detail.emit("Microsoft Rewards...")
        self.rewards_login()
        # Check Login
        self.detail.emit("Bing...")
        self.check_bing_login(isMobile)

    def rewards_login(self):
        """Login into Microsoft rewards and check account"""
        self.browser.get(self.base_url)
        try:
            time.sleep(10 if not self.config["globalOptions"]["fast"] else 5)
            self.browser.find_element(By.ID, 'raf-signin-link-id').click()
        except:
            pass
        time.sleep(10 if not self.config["globalOptions"]["fast"] else 5)
        # Check for ErrorMessage in Microsoft rewards page
        try:
            self.browser.find_element(By.ID, 'error').is_displayed()
            if self.browser.find_element(By.XPATH, '//*[@id="error"]/h1').get_attribute('innerHTML') == ' Uh oh, it appears your Microsoft Rewards account has been suspended.':
                raise AccountSuspendedException('Your account has been suspended !')
            elif self.browser.find_element(By.XPATH, '//*[@id="error"]/h1').get_attribute('innerHTML') == 'Microsoft Rewards is not available in this country or region.':
                raise RegionException('Microsoft Rewards is not available in your region !')
        except NoSuchElementException:
            pass

    @func_set_timeout(300)
    def check_bing_login(self, isMobile: bool = False):
        self.browser.get('https://bing.com/')
        time.sleep(15 if not self.config["globalOptions"]["fast"] else 5)
        # try to get points at first if account already logged in
        if self.config["globalOptions"]["session"]:
            try:
                if not isMobile:
                    try:
                        self.points_counter = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                    except ValueError:
                        if self.browser.find_element(By.ID, 'id_s').is_displayed():
                            self.browser.find_element(By.ID, 'id_s').click()
                            time.sleep(15)
                            self.check_bing_login(isMobile)
                        time.sleep(2)
                        self.points_counter = int(self.browser.find_element(By.ID, "id_rc").get_attribute("innerHTML").replace(",", ""))
                else:
                    self.browser.find_element(By.ID, 'mHamburger').click()
                    time.sleep(1)
                    self.points_counter = int(self.browser.find_element(By.ID, 'fly_id_rc').get_attribute('innerHTML'))
            except:
                pass
            else:
                return None
        #Accept Cookies
        try:
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
        except:
            pass
        if isMobile:
            # close bing app banner
            if self.is_element_exists(By.ID, 'bnp_rich_div'):
                try:
                    self.browser.find_element(By.XPATH, '//*[@id="bnp_bop_close_icon"]/img').click()
                except NoSuchElementException:
                    pass
            try:
                time.sleep(1)
                self.browser.find_element(By.ID, 'mHamburger').click()
            except:
                try:
                    self.browser.find_element(By.ID, 'bnp_btn_accept').click()
                except:
                    pass
                time.sleep(1)
                if self.is_element_exists(By.XPATH, '//*[@id="bnp_ttc_div"]/div[1]/div[2]/span'):
                    self.browser.execute_script("""var element = document.evaluate('/html/body/div[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                            element.remove();""")
                    time.sleep(5)
                time.sleep(1)
                try:
                    self.browser.find_element(By.ID, 'mHamburger').click()
                except:
                    pass
            try:
                time.sleep(1)
                self.browser.find_element(By.ID, 'HBSignIn').click()
            except:
                pass
            try:
                time.sleep(2)
                self.browser.find_element(By.ID, 'iShowSkip').click()
                time.sleep(3)
            except:
                if str(self.browser.current_url).split('?')[0] == "https://account.live.com/proofs/Add":
                    self.finished_accounts.append(self.current_account)
                    self.logs[self.current_account]['Last check'] = 'Requires manual check!'
                    self.update_logs()
                    raise Exception
        time.sleep(5)
        # Refresh page
        self.browser.get('https://bing.com/')
        time.sleep(15 if not self.config["globalOptions"]["fast"] else 5)
        #Update Counter
        try:
            if not isMobile:
                try:
                    self.points_counter = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                except:
                    if self.browser.find_element(By.ID, 'id_s').is_displayed():
                        self.browser.find_element(By.ID, 'id_s').click()
                        time.sleep(15)
                        self.check_bing_login(isMobile)
                    time.sleep(5)
                    self.points_counter = int(self.browser.find_element(By.ID, "id_rc").get_attribute("innerHTML").replace(",", ""))
            else:
                try:
                    self.browser.find_element(By.ID, 'mHamburger').click()
                except:
                    try:
                        self.browser.find_element(By.ID, 'bnp_close_link').click()
                        time.sleep(4)
                        self.browser.find_element(By.ID, 'bnp_btn_accept').click()
                    except:
                        pass
                    time.sleep(1)
                    self.browser.find_element(By.ID, 'mHamburger').click()
                time.sleep(1)
                self.points_counter = int(self.browser.find_element(By.ID, 'fly_id_rc').get_attribute('innerHTML'))
        except:
            self.check_bing_login(isMobile)
            
    def wait_until_visible(self, by_: By, selector: str, time_to_wait: int = 10):
        WebDriverWait(self.browser, time_to_wait).until(ec.visibility_of_element_located((by_, selector)))

    def wait_until_clickable(self, by_: By, selector: str, time_to_wait: int = 10):
        WebDriverWait(self.browser, time_to_wait).until(ec.element_to_be_clickable((by_, selector)))

    def wait_until_question_refresh(self):
        tries = 0
        refreshCount = 0
        while True:
            try:
                self.browser.find_elements(By.CLASS_NAME, 'rqECredits')[0]
                return True
            except:
                if tries < 10:
                    tries += 1
                    time.sleep(0.5)
                else:
                    if refreshCount < 5:
                        self.browser.refresh()
                        refreshCount += 1
                        tries = 0
                        time.sleep(5)
                    else:
                        return False

    def wait_until_quiz_loads(self):
        tries = 0
        refreshCount = 0
        while True:
            try:
                self.browser.find_element(By.XPATH, '//*[@id="currentQuestionContainer"]')
                return True
            except:
                if tries < 10:
                    tries += 1
                    time.sleep(0.5)
                else:
                    if refreshCount < 5:
                        self.browser.refresh()
                        refreshCount += 1
                        tries = 0
                        time.sleep(5)
                    else:
                        return False

    def get_dashboard_data(self) -> dict:
        dashboard = self.find_between(self.browser.find_element(By.XPATH, '/html/body').get_attribute('innerHTML'), "var dashboard = ", ";\n        appDataModule.constant(\"prefetchedDashboard\", dashboard);")
        dashboard = json.loads(dashboard)
        return dashboard
    
    def get_account_points(self) -> int:
        return self.get_dashboard_data()['userStatus']['availablePoints']
    
    def get_redeem_goal(self):
        user_status = self.get_dashboard_data()["userStatus"]
        return (user_status["redeemGoal"]["title"], user_status["redeemGoal"]["price"])
    
    def get_ccode_lang_and_offset(self) -> tuple:
        try:
            nfo = ipapi.location()
            lang = nfo['languages'].split(',')[0]
            geo = nfo['country']
            tz = str(round(int(nfo['utc_offset']) / 100 * 60))
            return(lang, geo, tz)
        except:
            return('en-US', 'US', '-480')
        
    def get_google_trends(self, numberOfwords: int) -> list:
        search_terms = []
        i = 0
        while len(search_terms) < numberOfwords :
            i += 1
            r = requests.get('https://trends.google.com/trends/api/dailytrends?hl=' + self.lang + '&ed=' + str((date.today() - timedelta(days = i)).strftime('%Y%m%d')) + '&geo=' + self.geo + '&ns=15')
            google_trends = json.loads(r.text[6:])
            for topic in google_trends['default']['trendingSearchesDays'][0]['trendingSearches']:
                search_terms.append(topic['title']['query'].lower())
                for related_topic in topic['relatedQueries']:
                    search_terms.append(related_topic['query'].lower())
            search_terms = list(set(search_terms))
        del search_terms[numberOfwords:(len(search_terms)+1)]
        return search_terms
    
    def get_related_terms(self, word: str) -> list:
        try:
            r = requests.get('https://api.bing.com/osjson.aspx?query=' + word, headers = {'User-agent': self.PC_USER_AGENT})
            return r.json()[1]
        except:
            return []
        
    def reset_tabs(self):
        try:
            curr = self.browser.current_window_handle

            for handle in self.browser.window_handles:
                if handle != curr:
                    self.browser.switch_to.window(handle)
                    time.sleep(0.5)
                    self.browser.close()
                    time.sleep(0.5)

            self.browser.switch_to.window(curr)
            time.sleep(0.5)
            self.browser.get(self.base_url)
        except:
            self.browser.get(self.base_url)
            
    def get_answer_code(self, key: str, string: str) -> str:
        """Get answer code for this or that quiz"""
        t = 0
        for i in range(len(string)):
            t += ord(string[i])
        t += int(key[-2:], 16)
        return str(t)
    
    def bing_searches(self, numberOfSearches: int, isMobile: bool = False):
        if not isMobile:
            self.section.emit("PC Bing Searches")
        else:
            self.section.emit("Mobile Bing Searches")
        self.detail.emit(f"0/{numberOfSearches}")
        i = 0
        r = RandomWords()
        search_terms = r.get_random_words(limit = numberOfSearches)
        if search_terms == None:
            search_terms = self.get_google_trends(numberOfSearches)
        for word in search_terms:
            i += 1
            self.detail.emit(f"{i}/{numberOfSearches}")
            points = self.bing_search(word, isMobile)
            self.points.emit(points)
            if points <= self.points_counter :
                relatedTerms = self.get_related_terms(word)
                for term in relatedTerms :
                    points = self.bing_search(term, isMobile)
                    self.points.emit(points)
                    if points >= self.points_counter:
                        break
            if points > 0:
                self.points_counter = points
            else:
                break
            
    def bing_search(self, word: str, isMobile: bool):
        try:
            if not isMobile:
                self.browser.find_element(By.ID, 'sb_form_q').clear()
                time.sleep(1)
            else:
                self.browser.get('https://bing.com')
        except:
            self.browser.get('https://bing.com')
        time.sleep(2)
        searchbar = self.browser.find_element(By.ID, 'sb_form_q')
        if self.config["globalOptions"]["fast"]:
            searchbar.send_keys(word)
            time.sleep(1)
        else:
            for char in word:
                searchbar.send_keys(char)
                time.sleep(0.33)
        searchbar.submit()
        time.sleep(random.randint(12, 24) if not self.config["globalOptions"]["fast"] else random.randint(6, 9))
        points = 0
        try:
            points = self.get_points_from_bing(isMobile)
        except:
            pass
        return points
    
    def complete_promotional_items(self):
        try:
            self.detail.emit("Promotional items")
            item = self.get_dashboard_data()["promotionalItem"]
            if (item["pointProgressMax"] == 100 or item["pointProgressMax"] == 200) and item["complete"] == False and item["destinationUrl"] == self.base_url:
                self.browser.find_element(By.XPATH, '//*[@id="promo-item"]/section/div/div/div/a').click()
                time.sleep(1)
                self.browser.switch_to.window(window_name = self.browser.window_handles[1])
                time.sleep(8)
                self.points.emit(self.get_points_from_bing(False))
                self.browser.close()
                time.sleep(2)
                self.browser.switch_to.window(window_name = self.browser.window_handles[0])
                time.sleep(2)
        except:
            pass
        
    def complete_daily_set_search(self, cardNumber: int):
        time.sleep(5)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-daily-set-item-content/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(random.randint(13, 17) if not self.config["globalOptions"]["fast"] else random.randint(6, 9))
        self.points.emit(self.get_points_from_bing(False))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_daily_set_survey(self, cardNumber: int):
        time.sleep(5)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-daily-set-item-content/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
        # Accept cookie popup
        if self.is_element_exists(By.ID, 'bnp_container'):
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
            time.sleep(2)
        # Click on later on Bing wallpaper app popup
        if self.is_element_exists(By.ID, 'b_notificationContainer_bop'):
            self.browser.find_element(By.ID, 'bnp_hfly_cta2').click()
            time.sleep(2)
        self.browser.find_element(By.ID, "btoption" + str(random.randint(0, 1))).click()
        time.sleep(random.randint(10, 15) if not self.config["globalOptions"]["fast"] else 7)
        self.points.emit(self.get_points_from_bing(False))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_daily_set_quiz(self, cardNumber: int):
        time.sleep(5)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section[1]/div/mee-card-group[1]/div[1]/mee-card[{str(cardNumber)}]/div[1]/card-content[1]/mee-rewards-daily-set-item-content[1]/div[1]/a[1]/div[3]/span[1]').click()
        time.sleep(3)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(12 if not self.config["globalOptions"]["fast"] else random.randint(5, 8))
        if not self.wait_until_quiz_loads():
            self.reset_tabs()
            return
        # Accept cookie popup
        if self.is_element_exists(By.ID, 'bnp_container'):
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
            time.sleep(2)
        self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
        time.sleep(3)
        numberOfQuestions = self.browser.execute_script("return _w.rewardsQuizRenderInfo.maxQuestions")
        numberOfOptions = self.browser.execute_script("return _w.rewardsQuizRenderInfo.numberOfOptions")
        for _ in range(numberOfQuestions):
            if numberOfOptions == 8:
                answers = []
                for i in range(8):
                    if self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).get_attribute("iscorrectoption").lower() == "true":
                        answers.append("rqAnswerOption" + str(i))
                for answer in answers:
                    # Click on later on Bing wallpaper app popup
                    if self.is_element_exists(By.ID, 'b_notificationContainer_bop'):
                        self.browser.find_element(By.ID, 'bnp_hfly_cta2').click()
                        time.sleep(2)
                    self.browser.find_element(By.ID, answer).click()
                    time.sleep(5)
                    if not self.wait_until_question_refresh():
                        return
                time.sleep(5)
            elif numberOfOptions == 4:
                correctOption = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")
                for i in range(4):
                    if self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).get_attribute("data-option") == correctOption:
                        # Click on later on Bing wallpaper app popup
                        if self.is_element_exists(By.ID, 'b_notificationContainer_bop'):
                            self.browser.find_element(By.ID, 'bnp_hfly_cta2').click()
                            time.sleep(2)
                        self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).click()
                        time.sleep(5)
                        if not self.wait_until_question_refresh(self.browser):
                            return
                        break
                time.sleep(5)
            self.points.emit(self.get_points_from_bing(False))
        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)

    def complete_daily_set_variable_activity(self, cardNumber: int):
        time.sleep(2)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-daily-set-item-content/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(8)
        # Accept cookie popup
        if self.is_element_exists(By.ID, 'bnp_container'):
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
            time.sleep(2)
        try :
            self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
            self.wait_until_visible(By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 3)
        except (NoSuchElementException, TimeoutException):
            try:
                counter = str(self.browser.find_element(By.XPATH, '//*[@id="QuestionPane0"]/div[2]').get_attribute('innerHTML'))[:-1][1:]
                numberOfQuestions = max([int(s) for s in counter.split() if s.isdigit()])
                for question in range(numberOfQuestions):
                    # Click on later on Bing wallpaper app popup
                    if self.is_element_exists(By.ID, 'b_notificationContainer_bop'):
                        self.browser.find_element(By.ID, 'bnp_hfly_cta2').click()
                        time.sleep(2)
                        
                    self.browser.execute_script(f'document.evaluate("//*[@id=\'QuestionPane{str(question)}\']/div[1]/div[2]/a[{str(random.randint(1, 3))}]/div", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()')
                    time.sleep(8)
                    self.points.emit(self.get_points_from_bing(False))
                time.sleep(5)
                self.browser.close()
                time.sleep(2)
                self.browser.switch_to.window(window_name=self.browser.window_handles[0])
                time.sleep(2)
                return
            except NoSuchElementException:
                time.sleep(random.randint(5, 9))
                self.browser.close()
                time.sleep(2)
                self.browser.switch_to.window(window_name = self.browser.window_handles[0])
                time.sleep(2)
                return
        time.sleep(3)
        correctAnswer = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")
        if self.browser.find_element(By.ID, "rqAnswerOption0").get_attribute("data-option") == correctAnswer:
            self.browser.find_element(By.ID, "rqAnswerOption0").click()
        else :
            self.browser.find_element(By.ID, "rqAnswerOption1").click()
        time.sleep(10)
        self.points.emit(self.get_points_from_bing(False))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_daily_set_this_or_that(self, cardNumber: int):
        time.sleep(2)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-daily-set-item-content/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(15 if not self.config["globalOptions"]["fast"] else random.randint(5, 8))
        # Accept cookie popup
        if self.is_element_exists(By.ID, 'bnp_container'):
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
            time.sleep(2)
        if not self.wait_until_quiz_loads():
            self.reset_tabs()
            return
        self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
        time.sleep(5)
        for _ in range(10):
            # Click on later on Bing wallpaper app popup
            if self.is_element_exists(By.ID, 'b_notificationContainer_bop'):
                self.browser.find_element(By.ID, 'bnp_hfly_cta2').click()
                time.sleep(2)
            
            answerEncodeKey = self.browser.execute_script("return _G.IG")

            answer1 = self.browser.find_element(By.ID, "rqAnswerOption0")
            answer1Title = answer1.get_attribute('data-option')
            answer1Code = self.get_answer_code(answerEncodeKey, answer1Title)

            answer2 = self.browser.find_element(By.ID, "rqAnswerOption1")
            answer2Title = answer2.get_attribute('data-option')
            answer2Code = self.get_answer_code(answerEncodeKey, answer2Title)

            correctAnswerCode = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")

            if (answer1Code == correctAnswerCode):
                answer1.click()
                time.sleep(15 if not self.config["globalOptions"]["fast"] else 7)
            elif (answer2Code == correctAnswerCode):
                answer2.click()
                time.sleep(15 if not self.config["globalOptions"]["fast"] else 7)
            self.points.emit(self.get_points_from_bing(False))

        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
    
    def complete_daily_set(self):
        self.section.emit("Daily Set")
        d = self.get_dashboard_data()
        todayDate = datetime.today().strftime('%m/%d/%Y')
        todayPack = []
        for date, data in d['dailySetPromotions'].items():
            if date == todayDate:
                todayPack = data
        for activity in todayPack:
            try:
                if activity['complete'] == False:
                    cardNumber = int(activity['offerId'][-1:])
                    if activity['promotionType'] == "urlreward":
                        self.detail.emit(f'Search of card {str(cardNumber)}')
                        self.complete_daily_set_search(cardNumber)
                    if activity['promotionType'] == "quiz":
                        if activity['pointProgressMax'] == 50 and activity['pointProgress'] == 0:
                            self.detail.emit(f'This or That of card {str(cardNumber)}')
                            self.complete_daily_set_this_or_that(cardNumber)
                        elif (activity['pointProgressMax'] == 40 or activity['pointProgressMax'] == 30) and activity['pointProgress'] == 0:
                            self.detail.emit(f"Quiz of card {str(cardNumber)}")
                            self.complete_daily_set_quiz(cardNumber)
                        elif activity['pointProgressMax'] == 10 and activity['pointProgress'] == 0:
                            searchUrl = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(activity['destinationUrl']).query)['ru'][0])
                            searchUrlQueries = urllib.parse.parse_qs(urllib.parse.urlparse(searchUrl).query)
                            filters = {}
                            for filter in searchUrlQueries['filters'][0].split(" "):
                                filter = filter.split(':', 1)
                                filters[filter[0]] = filter[1]
                            if "PollScenarioId" in filters:
                                self.detail.emit(f"Poll of card {str(cardNumber)}")
                                self.complete_daily_set_survey(cardNumber)
                            else:
                                self.detail.emit(f"Quiz of card {str(cardNumber)}")
                                self.complete_daily_set_variable_activity(cardNumber)
            except:
                self.reset_tabs()
        self.logs[self.current_account]['Daily'] = True
        self.update_logs() 
        
    def complete_punch_card(self, url: str, childPromotions: dict):
        self.browser.get(url)
        for child in childPromotions:
            if child['complete'] == False:
                if child['promotionType'] == "urlreward":
                    self.browser.execute_script("document.getElementsByClassName('offer-cta')[0].click()")
                    time.sleep(1)
                    self.browser.switch_to.window(window_name = self.browser.window_handles[1])
                    time.sleep(random.randint(13, 17))
                    self.browser.close()
                    time.sleep(2)
                    self.browser.switch_to.window(window_name = self.browser.window_handles[0])
                    time.sleep(2)
                if child['promotionType'] == "quiz" and child['pointProgressMax'] >= 50 :
                    self.browser.find_element(By.XPATH, '//*[@id="rewards-dashboard-punchcard-details"]/div[2]/div[2]/div[7]/div[3]/div[1]/a').click()
                    time.sleep(1)
                    self.browser.switch_to.window(window_name = self.browser.window_handles[1])
                    time.sleep(15)
                    try:
                        self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
                    except:
                        pass
                    time.sleep(5)
                    self.wait_until_visible(By.XPATH, '//*[@id="currentQuestionContainer"]', 10)
                    numberOfQuestions = self.browser.execute_script("return _w.rewardsQuizRenderInfo.maxQuestions")
                    AnswerdQuestions = self.browser.execute_script("return _w.rewardsQuizRenderInfo.CorrectlyAnsweredQuestionCount")
                    numberOfQuestions -= AnswerdQuestions
                    for question in range(numberOfQuestions):
                        answer = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")
                        self.browser.find_element(By.XPATH, f'//input[@value="{answer}"]').click()
                        time.sleep(15)
                    time.sleep(5)
                    self.browser.close()
                    time.sleep(2)
                    self.browser.switch_to.window(window_name=self.browser.window_handles[0])
                    time.sleep(2)
                    self.browser.refresh()
                    break
                elif child['promotionType'] == "quiz" and child['pointProgressMax'] < 50:
                    self.browser.execute_script("document.getElementsByClassName('offer-cta')[0].click()")
                    time.sleep(1)
                    self.browser.switch_to.window(window_name = self.browser.window_handles[1])
                    time.sleep(8)
                    counter = str(self.browser.find_element(By.XPATH, '//*[@id="QuestionPane0"]/div[2]').get_attribute('innerHTML'))[:-1][1:]
                    numberOfQuestions = max([int(s) for s in counter.split() if s.isdigit()])
                    for question in range(numberOfQuestions):
                        self.browser.execute_script('document.evaluate("//*[@id=\'QuestionPane' + str(question) + '\']/div[1]/div[2]/a[' + str(random.randint(1, 3)) + ']/div", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()')
                        time.sleep(10)
                    time.sleep(5)
                    self.browser.close()
                    time.sleep(2)
                    self.browser.switch_to.window(window_name = self.browser.window_handles[0])
                    time.sleep(2)
                    self.browser.refresh()
                    break
                
    def complete_punch_cards(self):
        punchCards = self.get_dashboard_data()['punchCards']
        self.section.emit("Punch cards")
        self.detail.emit("-")
        for punchCard in punchCards:
            try:
                if punchCard['parentPromotion'] != None and punchCard['childPromotions'] != None and punchCard['parentPromotion']['complete'] == False and punchCard['parentPromotion']['pointProgressMax'] != 0:
                    url = punchCard['parentPromotion']['attributes']['destination']
                    if self.browser.current_url.startswith('https://rewards.'):
                        path = url.replace('https://rewards.microsoft.com', '')
                        new_url = 'https://rewards.microsoft.com/dashboard/'
                        userCode = path[11:15]
                        dest = new_url + userCode + path.split(userCode)[1]
                    else:
                        path = url.replace('https://account.microsoft.com/rewards/dashboard/','')
                        new_url = 'https://account.microsoft.com/rewards/dashboard/'
                        userCode = path[:4]
                        dest = new_url + userCode + path.split(userCode)[1]
                    self.complete_punch_card(url, punchCard['childPromotions'])
            except:
                self.reset_tabs()
        time.sleep(2)
        self.browser.get(self.base_url)
        time.sleep(2)
        self.logs[self.current_account]['Punch cards'] = True
        self.update_logs()
        
    def complete_more_promotion_search(self, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(random.randint(13, 17) if not self.config["globalOptions"]["fast"] else random.randint(5, 8))
        self.points.emit(self.get_points_from_bing(False))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotion_quiz(self, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(8 if not self.config["globalOptions"] else 5)
        if not self.wait_until_quiz_loads():
            self.reset_tabs()
            return
        CurrentQuestionNumber = self.browser.execute_script("return _w.rewardsQuizRenderInfo.currentQuestionNumber")
        if CurrentQuestionNumber == 1 and self.is_element_exists(By.XPATH, '//*[@id="rqStartQuiz"]'):
            self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
        time.sleep(3)
        numberOfQuestions = self.browser.execute_script("return _w.rewardsQuizRenderInfo.maxQuestions")
        Questions = numberOfQuestions - CurrentQuestionNumber + 1
        numberOfOptions = self.browser.execute_script("return _w.rewardsQuizRenderInfo.numberOfOptions")
        for _ in range(Questions):
            if numberOfOptions == 8:
                answers = []
                for i in range(8):
                    if self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).get_attribute("iscorrectoption").lower() == "true":
                        answers.append("rqAnswerOption" + str(i))
                for answer in answers:
                    self.browser.find_element(By.ID, answer).click()
                    time.sleep(5)
                    if not self.wait_until_question_refresh():
                        return
                time.sleep(5)
            elif numberOfOptions == 4:
                correctOption = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")
                for i in range(4):
                    if self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).get_attribute("data-option") == correctOption:
                        self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).click()
                        time.sleep(5)
                        if not self.wait_until_question_refresh():
                            return
                        break
                time.sleep(5)
            self.points.emit(self.get_points_from_bing(False))
        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotion_ABC(self, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
        counter = str(self.browser.find_element(By.XPATH, '//*[@id="QuestionPane0"]/div[2]').get_attribute('innerHTML'))[:-1][1:]
        numberOfQuestions = max([int(s) for s in counter.split() if s.isdigit()])
        for question in range(numberOfQuestions):
            self.browser.execute_script(f'document.evaluate("//*[@id=\'QuestionPane{str(question)}\']/div[1]/div[2]/a[{str(random.randint(1, 3))}]/div", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()')
            time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
        time.sleep(5)
        self.points.emit(self.get_points_from_bing(False))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotion_this_or_that(self, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
        if not self.wait_until_quiz_loads():
            self.reset_tabs()
            return
        CrrentQuestionNumber = self.browser.execute_script("return _w.rewardsQuizRenderInfo.currentQuestionNumber")
        NumberOfQuestionsLeft = 10 - CrrentQuestionNumber + 1
        if CrrentQuestionNumber == 1 and self.is_element_exists(By.XPATH, '//*[@id="rqStartQuiz"]'):
            self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
        time.sleep(3)
        for _ in range(NumberOfQuestionsLeft):
            answerEncodeKey = self.browser.execute_script("return _G.IG")

            answer1 = self.browser.find_element(By.ID, "rqAnswerOption0")
            answer1Title = answer1.get_attribute('data-option')
            answer1Code = self.get_answer_code(answerEncodeKey, answer1Title)

            answer2 = self.browser.find_element(By.ID, "rqAnswerOption1")
            answer2Title = answer2.get_attribute('data-option')
            answer2Code = self.get_answer_code(answerEncodeKey, answer2Title)

            correctAnswerCode = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")

            if (answer1Code == correctAnswerCode):
                answer1.click()
                time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
            elif (answer2Code == correctAnswerCode):
                answer2.click()
                time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
            self.points.emit(self.get_points_from_bing(False))

        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotions(self):
        self.section.emit("More activities")
        morePromotions = self.get_dashboard_data()['morePromotions']
        i = 0
        for promotion in morePromotions:
            try:
                i += 1
                if promotion['complete'] == False and promotion['pointProgressMax'] != 0:
                    if promotion['promotionType'] == "urlreward":
                        self.detail.emit("Search card")
                        self.complete_more_promotion_search(i)
                    elif promotion['promotionType'] == "quiz":
                        if promotion['pointProgressMax'] == 10:
                            self.detail.emit("ABC card")
                            self.complete_more_promotion_ABC(i)
                        elif promotion['pointProgressMax'] == 30 or promotion['pointProgressMax'] == 40:
                            self.detail.emit("Quiz card")
                            self.complete_more_promotion_quiz(i)
                        elif promotion['pointProgressMax'] == 50:
                            self.detail.emit("This or that card")
                            self.complete_more_promotion_this_or_that(i)
                    else:
                        if promotion['pointProgressMax'] == 100 or promotion['pointProgressMax'] == 200:
                            self.detail.emit("Search card")
                            self.complete_more_promotion_search(i)
                if promotion['complete'] == False and promotion['pointProgressMax'] == 100 and promotion['promotionType'] == "" \
                    and promotion['destinationUrl'] == self.base_url:
                        self.detail.emit("Search card")
                        self.complete_more_promotion_search(i)
            except:
                self.reset_tabs()
        self.logs[self.current_account]['More promotions'] = True
        self.update_logs()
        
    def get_remaining_searches(self):
        dashboard = self.get_dashboard_data()
        searchPoints = 1
        counters = dashboard['userStatus']['counters']
        if not 'pcSearch' in counters:
            return 0, 0
        progressDesktop = counters['pcSearch'][0]['pointProgress'] + counters['pcSearch'][1]['pointProgress']
        targetDesktop = counters['pcSearch'][0]['pointProgressMax'] + counters['pcSearch'][1]['pointProgressMax']
        if targetDesktop == 33 :
            #Level 1 EU
            searchPoints = 3
        elif targetDesktop == 55 :
            #Level 1 US
            searchPoints = 5
        elif targetDesktop == 102 :
            #Level 2 EU
            searchPoints = 3
        elif targetDesktop >= 170 :
            #Level 2 US
            searchPoints = 5
        remainingDesktop = int((targetDesktop - progressDesktop) / searchPoints)
        remainingMobile = 0
        if dashboard['userStatus']['levelInfo']['activeLevel'] != "Level1":
            progressMobile = counters['mobileSearch'][0]['pointProgress']
            targetMobile = counters['mobileSearch'][0]['pointProgressMax']
            remainingMobile = int((targetMobile - progressMobile) / searchPoints)
        return remainingDesktop, remainingMobile
    
    def get_points_from_bing(self, isMobile: bool = False):
        try:
            if not isMobile:
                try:
                    points = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                except ValueError:
                    points = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML').replace(",", ""))
            else:
                try:
                    self.browser.find_element(By.ID, 'mHamburger').click()
                except UnexpectedAlertPresentException:
                    try:
                        self.browser.switch_to.alert.accept()
                        time.sleep(1)
                        self.browser.find_element(By.ID, 'mHamburger').click()
                    except NoAlertPresentException:
                        pass
                time.sleep(1)
                points = int(self.browser.find_element(By.ID, 'fly_id_rc').get_attribute('innerHTML'))
        except NoSuchElementException:
            points = self.points_counter
        return points
    
    def perform_run(self):
        """Check whether timer is set to run it at time else run immediately"""
        if self.ui.active_timer_checkbox.isChecked():
            self.stop_button_enabled.emit(True)
            requested_time = self.ui.timeEdit.time().toString("HH:mm")
            self.section.emit(f"Starts at {requested_time}")
            while QTime.currentTime().toString("HH:mm") != requested_time:
                if self.ui.farmer_thread.isInterruptionRequested():
                    self.finished.emit()
                    return None
                time.sleep(1)
            else:
                return self.run()
        return self.run()
    
    def run(self):
        start = time.time()
        for account in self.accounts:
            while True:
                try:
                    self.current_account = account["username"]
                    if account["username"] in self.finished_accounts or account["username"] in self.suspended_accounts:
                        break
                    if self.logs[self.current_account]["Last check"] != str(date.today()):
                        self.logs[self.current_account]["Last check"] = str(date.today())
                        self.update_logs()
                    self.accounts_info_sig.emit()
                    if self.is_pc_need():

                        self.browser_setup(False, self.PC_USER_AGENT)
                        self.stop_button_enabled.emit(True)
                        self.login(account["username"], account["password"])
                        self.detail.emit("Logged in")
                        
                        self.browser.get(self.base_url)
                        self.starting_points = self.get_account_points()
                        redeem_goal_title, redeem_goal_price = self.get_redeem_goal()
                        self.points_counter = self.starting_points
                        self.points.emit(self.points_counter)

                        if self.config["farmOptions"]["dailyQuests"] and not self.logs[self.current_account]["Daily"]:
                            self.complete_daily_set()
                            self.points.emit(self.points_counter)

                        if self.config["farmOptions"]["punchCards"] and not self.logs[self.current_account]["Punch cards"]:
                            self.complete_punch_cards()
                            self.points.emit(self.points_counter)

                        if self.config["farmOptions"]["moreActivities"] and not self.logs[self.current_account]["More promotions"]:
                            self.complete_more_promotions()
                            self.points.emit(self.points_counter)

                        if self.config["farmOptions"]["searchPC"] and not self.logs[self.current_account]["PC searches"]:
                            remainingSearches = self.get_remaining_searches()[0]
                            self.bing_searches(remainingSearches)
                            self.logs[self.current_account]["PC searches"] = True
                            self.update_logs()
                            
                        self.stop_button_enabled.emit(False)
                        self.browser.quit()
                        self.detail.emit("-")
                        self.section.emit("-")
                        

                    if self.config["farmOptions"]["searchMobile"] and not self.logs[self.current_account]["Mobile searches"]:
                        self.browser_setup(True, account.get('mobile_user_agent', self.MOBILE_USER_AGENT))
                        self.stop_button_enabled.emit(True)
                        self.login(account["username"], account["password"], True)
                        self.browser.get(self.base_url)
                        redeem_goal_title, redeem_goal_price = self.get_redeem_goal()
                        if not self.starting_points:
                            self.starting_points = self.get_account_points()
                        remainingSearches = self.get_remaining_searches()[1]
                        if remainingSearches > 0:
                            self.bing_searches(remainingSearches, True)
                        self.logs[self.current_account]["Mobile searches"] = True
                        self.update_logs()
                        self.stop_button_enabled.emit(False)
                        self.browser.quit()
                        self.detail.emit("-")
                        self.section.emit("-")

                    self.finished_accounts.append(account["username"])
                    self.logs[account["username"]]["Today's points"] = self.points_counter - self.starting_points
                    self.logs[account["username"]]["Points"] = self.points_counter
                    
                    if self.ui.send_to_telegram_checkbox.isChecked() and redeem_goal_title != "" and redeem_goal_price <= self.points_counter:
                        self.logs[self.current_account]["Redeem goal title"] = redeem_goal_title
                        self.logs[self.current_account]["Redeem goal price"] = redeem_goal_price
                        
                    self.clean_logs()
                    self.update_logs()

                    self.points.emit(0)
                    self.accounts_info_sig.emit()
                    
                    break
                    
                except SessionNotCreatedException:
                    self.browser = None
                    self.section.emit("Update your web driver")
                    self.detail.emit("web driver error")
                    self.finished.emit()
                    return None
                
                except AccountLockedException:
                    self.browser.quit()
                    self.browser = None
                    self.logs[self.current_account]['Last check'] = 'Your account has been locked !'
                    self.locked_accounts.append(self.current_account)
                    self.update_logs()
                    self.clean_logs()
                    break
                
                except AccountSuspendedException:
                    self.browser.quit()
                    self.browser = None
                    self.suspended_accounts.append(self.current_account)
                    self.logs[self.current_account]['Last check'] = 'Your account has been suspended'
                    self.logs[self.current_account]["Today's points"] = 'N/A' 
                    self.logs[self.current_account]["Points"] = 'N/A' 
                    self.clean_logs()
                    self.update_logs()
                    self.finished_accounts.append(self.current_account)
                    self.accounts_info_sig.emit()
                    break
                
                except UnusualActivityException:
                    self.browser.quit()
                    self.browser = None
                    self.logs[self.current_account]['Last check'] = 'Unusual activity detected !'
                    self.finished_accounts.append(self.current_account)       
                    self.update_logs()
                    self.clean_logs()
                    self.finished.emit()
                    return None
                    
                except RegionException:
                    self.browser.quit()
                    self.browser = None
                    self.finished.emit()
                    self.section.emit("Not available in your region")
                    return None
                
                except UnhandledException:
                    self.browser.quit()
                    self.browser = None
                    self.logs[self.current_account]['Last check'] = 'Unknown error !'
                    self.finished_accounts.append(self.current_account)
                    self.update_logs()
                    self.clean_logs()
                    break
                
                except (InvalidSessionIdException, MaxRetryError, NewConnectionError):
                    if isinstance(self.browser, WebDriver):
                        self.browser.quit()
                        self.browser = None
                    if self.ui.farmer_thread.isInterruptionRequested():
                        self.finished.emit()
                        self.ui.enable_elements()
                        return None
                    internet = self.check_internet_connection()
                    if internet:
                        pass
                    else:
                        self.finished.emit()
                        self.ui.enable_elements()
                        return None
                    
                except (Exception, FunctionTimedOut) as e:
                    if isinstance(self.browser, WebDriver):
                        self.browser.quit()
                    self.starting_points = None
                    self.browser = None
                    if self.config["globalOptions"]["saveErrors"]:
                        with open(f"{Path.cwd()}/errors.txt", "a") as f:
                            f.write(f"\n-------------------{datetime.now()}-------------------\r\n")
                            f.write(f"{str(e)}\n")
                    internet = self.check_internet_connection()
                    if internet:
                        pass
                    else:
                        self.finished.emit()
                        self.ui.enable_elements()
                        return None
                    
        else:
            if self.ui.send_to_telegram_checkbox.isChecked():
                message = self.create_message()
                self.send_report_to_telegram(message)
            end = time.time()
            delta = end - start
            hour, remain = divmod(delta, 3600)
            min, sec = divmod(remain, 60)
            self.logs["Elapsed time"] = f"{hour:02.0f}:{min:02.0f}:{sec:02.0f}"
            self.update_logs()
            if self.config["globalOptions"]["shutdownSystem"]: os.system("shutdown /s")
            self.finished.emit()
        