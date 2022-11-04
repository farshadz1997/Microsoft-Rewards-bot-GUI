import json
import os
import platform
import random
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from argparse import ArgumentParser
from datetime import date, datetime, timedelta

import ipapi
import requests
from func_timeout import FunctionTimedOut, func_set_timeout
from random_word import RandomWords
from selenium import webdriver
from selenium.common.exceptions import (ElementNotInteractableException,
                                        NoAlertPresentException,
                                        NoSuchElementException,
                                        SessionNotCreatedException,
                                        TimeoutException,
                                        UnexpectedAlertPresentException)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options


class Farmer:
    PC_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.24'
    MOBILE_USER_AGENT = 'Mozilla/5.0 (Linux; Android 12; SM-N9750) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36 EdgA/107.0.1418.28'
    
    def __init__(self, accounts_path: str, config: dict):
        self.accounts_path = Path(accounts_path)
        self.accounts = json.load(open(self.accounts_path, "r"))
        self.config: dict = config
        self.logs: dict = {}
        self.points_counter: int = 0
        self.finished_accounts: list = [] 
        self.current_account: str = None
        self.browser: WebDriver = None
        self.lang: str = None
        
    def get_or_create_logs(self):
        '''
        Read logs and check whether account farmed or not
        '''
        shared_items =[]
        try:
            # Read datas on 'logs_accounts.txt'
            self.logs = json.load(open(f"{self.accounts_path}/Logs_{self.accounts_path.stem}.txt", "r"))
            # delete Time period from logs
            self.logs.pop("Time period", None)
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
                if self.logs[account]["Last check"] == str(date.today()) and list(self.logs[account].keys()) == ['Last check', "Today's points", 'Points']:
                    self.finished_accounts.append(account)
                elif self.logs[account]['Last check'] == 'Your account has been suspended':
                    self.finished_accounts.append(account)
                elif self.logs[account]['Last check'] == str(date.today()) and list(self.logs[account].keys()) == ['Last check', "Today's points", 'Points',
                                                                                                        'Daily', 'Punch cards', 'More promotions', 'PC searches']:
                    continue
                else:
                    self.logs[account]['Daily'] = False
                    self.logs[account]['Punch cards'] = False
                    self.logs[account]['More promotions'] = False
                    self.logs[account]['PC searches'] = False 
            self.update_logs()               
            # prGreen('\n[LOGS] Logs loaded successfully.\n')
        except FileNotFoundError:
            # prRed(f'\n[LOGS] "Logs_{account_path.stem}.txt" file not found.')
            LOGS = {}
            for account in self.accounts:
                self.logs[account["username"]] = {"Last check": "",
                                            "Today's points": 0,
                                            "Points": 0,
                                            "Daily": False,
                                            "Punch cards": False,
                                            "More promotions": False,
                                            "PC searches": False}
            self.update_logs()
            # prGreen(f'[LOGS] "Logs_{account_path.stem}.txt" created.\n')
        
    def update_logs(self):
        with open(f'{self.accounts_path.parent}/Logs_{self.accounts_path.stem}.txt', 'w') as file:
            file.write(json.dumps(self.logs, indent = 4))

    def clean_logs(self):
        del self.logs[self.current_account]["Daily"]
        del self.logs[self.current_account]["Punch cards"]
        del self.logs[self.current_account]["More promotions"]
        del self.logs[self.current_account]["PC searches"]
        
    def is_element_exists(self, _by: By, element: str) -> bool:
        '''Returns True if given element exists else False'''
        try:
            self.browser.find_element(_by, element)
        except NoSuchElementException:
            return False
        return True
        
    def browser_setup(self, isMobile: bool = False, user_agent = PC_USER_AGENT):
        # Create Chrome browser
        options = Options()
        if self.config.get("session", False):
            if not isMobile:
                options.add_argument(f'--user-data-dir={Path(__file__).parent}/Profiles/{self.current_account}/PC')
            else:
                options.add_argument(f'--user-data-dir={Path(__file__).parent}/Profiles/{self.current_account}/Mobile')
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
        if self.config.get("headless", False):
            options.add_argument("--headless")
        options.add_argument('log-level=3')
        options.add_argument("--start-maximized")
        if platform.system() == 'Linux':
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        chrome_browser_obj = webdriver.Chrome(options=options)
        return chrome_browser_obj
    
    def login(self, browser: WebDriver, email: str, pwd: str, isMobile: bool = False):
        """Login into  Microsoft account"""
        # Close welcome tab for new sessions
        if self.config.get("session", False):
            time.sleep(2)
            if len(browser.window_handles) > 1:
                current_window = browser.current_window_handle
                for handler in browser.window_handles:
                    if handler != current_window:
                        browser.switch_to.window(handler)
                        time.sleep(0.5)
                        browser.close()
                browser.switch_to.window(current_window)
        # Access to bing.com
        browser.get('https://login.live.com/')
        # Check if account is already logged in
        if self.config.get("session", False):
            if browser.title == "We're updating our terms" or self.is_element_exists(browser, By.ID, 'iAccrualForm'):
                time.sleep(2)
                browser.find_element(By.ID, 'iNext').click()
                time.sleep(5)
            if browser.title == 'Microsoft account | Home' or self.is_element_exists(browser, By.ID, 'navs_container'):
                # prGreen('[LOGIN] Account already logged in !')
                self.RewardsLogin(browser)
                print('[LOGIN]', 'Ensuring login on Bing...')
                self.check_bing_login(browser, isMobile)
                return
            elif browser.title == 'Your account has been temporarily suspended':
                self.logs[self.current_account]['Last check'] = 'Your account has been locked !'
                self.finished_accounts.append(self.current_account)
                self.update_logs()
                self.clean_logs()
                raise Exception(prRed('[ERROR] Your account has been locked !'))
        # Wait complete loading
        self.wait_until_visible(browser, By.ID, 'loginHeader', 10)
        # Enter email
        print('[LOGIN]', 'Writing email...')
        browser.find_element(By.NAME, "loginfmt").send_keys(email)
        # Click next
        browser.find_element(By.ID, 'idSIButton9').click()
        # Wait 2 seconds
        time.sleep(5 if not self.config["globalOptions"]["fast"] else 2)
        # Wait complete loading
        self.wait_until_visible(browser, By.ID, 'loginHeader', 10)
        # Enter password
        browser.find_element(By.ID, "i0118").send_keys(pwd)
        # browser.execute_script("document.getElementById('i0118').value = '" + pwd + "';")
        print('[LOGIN]', 'Writing password...')
        # Click next
        browser.find_element(By.ID, 'idSIButton9').click()
        # Wait 5 seconds
        time.sleep(5)
        try:
            if browser.title == "We're updating our terms" or self.is_element_exists(browser, By.ID, 'iAccrualForm'):
                time.sleep(2)
                browser.find_element(By.ID, 'iNext').click()
                time.sleep(5)
            if self.config.get("session", False):
                # Click Yes to stay signed in.
                browser.find_element(By.ID, 'idSIButton9').click()
            else:
                # Click No.
                browser.find_element(By.ID, 'idBtn_Back').click()
        except NoSuchElementException:
            # Check for if account has been locked.
            if browser.title == "Your account has been temporarily suspended" or self.is_element_exists(browser, By.CLASS_NAME, "serviceAbusePageContainer  PageContainer"):
                self.logs[self.current_account]['Last check'] = 'Your account has been locked !'
                self.finished_accounts.append(self.current_account)
                self.update_logs()
                self.clean_logs()
                raise Exception(prRed('[ERROR] Your account has been locked !'))
            elif browser.title == "Help us protect your account":
                # prRed('[ERROR] Unusual activity detected !')
                self.logs[self.current_account]['Last check'] = 'Unusual activity detected !'
                self.finished_accounts.append(self.current_account)       
                self.update_logs()
                self.clean_logs()
                input('Press any key to close...')
                os._exit(0)
            else:
                self.logs[self.current_account]['Last check'] = 'Unknown error !'
                self.finished_accounts.append(self.current_account)
                self.update_logs()
                self.clean_logs()
                raise Exception(prRed('[ERROR] Unknown error !'))
        # Wait 5 seconds
        time.sleep(5)
        # Click Security Check
        print('[LOGIN]', 'Passing security checks...')
        try:
            browser.find_element(By.ID, 'iLandingViewAction').click()
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        # Wait complete loading
        try:
            self.wait_until_visible(browser, By.ID, 'KmsiCheckboxField', 10)
        except (TimeoutException) as e:
            pass
        # Click next
        try:
            browser.find_element(By.ID, 'idSIButton9').click()
            # Wait 5 seconds
            time.sleep(5)
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        print('[LOGIN]', 'Logged-in !')
        # Check Microsoft Rewards
        print('[LOGIN] Logging into Microsoft Rewards...')
        self.RewardsLogin(browser)
        # Check Login
        print('[LOGIN]', 'Ensuring login on Bing...')
        self.check_bing_login(browser, isMobile)

    def RewardsLogin(self, browser: WebDriver):
        #Login into Rewards
        browser.get('https://rewards.microsoft.com/dashboard')
        try:
            time.sleep(10 if not self.config["globalOptions"] else 5)
            browser.find_element(By.ID, 'raf-signin-link-id').click()
        except:
            pass
        time.sleep(10 if not self.config["globalOptions"]["fast"] else 5)
        # Check for ErrorMessage
        try:
            browser.find_element(By.ID, 'error').is_displayed()
            # Check wheter account suspended or not
            if browser.find_element(By.XPATH, '//*[@id="error"]/h1').get_attribute('innerHTML') == ' Uh oh, it appears your Microsoft Rewards account has been suspended.':
                self.logs[self.current_account]['Last check'] = 'Your account has been suspended'
                self.logs[self.current_account]["Today's points"] = 'N/A' 
                self.logs[self.current_account]["Points"] = 'N/A' 
                self.clean_logs()
                self.update_logs()
                self.finished_accounts.append(self.current_account)
                raise Exception(prRed('[ERROR] Your Microsoft Rewards account has been suspended !'))
            # Check whether Rewards is available in your region or not
            elif browser.find_element(By.XPATH, '//*[@id="error"]/h1').get_attribute('innerHTML') == 'Microsoft Rewards is not available in this country or region.':
                # prRed('[ERROR] Microsoft Rewards is not available in this country or region !')
                input('[ERROR] Press any key to close...')
                os._exit()
        except NoSuchElementException:
            pass

    @func_set_timeout(300)
    def check_bing_login(self, browser: WebDriver, isMobile: bool = False):
        #Access Bing.com
        browser.get('https://bing.com/')
        # Wait 15 seconds
        time.sleep(15 if not self.config["globalOptions"]["fast"] else 5)
        # try to get points at first if account already logged in
        if self.config.get("session", False):
            try:
                if not isMobile:
                    try:
                        self.points_counter = int(browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                    except ValueError:
                        if browser.find_element(By.ID, 'id_s').is_displayed():
                            browser.find_element(By.ID, 'id_s').click()
                            time.sleep(15)
                            self.check_bing_login(browser, isMobile)
                        time.sleep(2)
                        self.points_counter = int(browser.find_element(By.ID, "id_rc").get_attribute("innerHTML").replace(",", ""))
                else:
                    browser.find_element(By.ID, 'mHamburger').click()
                    time.sleep(1)
                    self.points_counter = int(browser.find_element(By.ID, 'fly_id_rc').get_attribute('innerHTML'))
            except:
                pass
            else:
                return None
        #Accept Cookies
        try:
            browser.find_element(By.ID, 'bnp_btn_accept').click()
        except:
            pass
        if isMobile:
            # close bing app banner
            if self.is_element_exists(By.ID, 'bnp_rich_div'):
                try:
                    browser.find_element(By.XPATH, '//*[@id="bnp_bop_close_icon"]/img').click()
                except NoSuchElementException:
                    pass
            try:
                time.sleep(1)
                browser.find_element(By.ID, 'mHamburger').click()
            except:
                try:
                    browser.find_element(By.ID, 'bnp_btn_accept').click()
                except:
                    pass
                time.sleep(1)
                if self.is_element_exists(By.XPATH, '//*[@id="bnp_ttc_div"]/div[1]/div[2]/span'):
                    browser.execute_script("""var element = document.evaluate('/html/body/div[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                            element.remove();""")
                    time.sleep(5)
                time.sleep(1)
                try:
                    browser.find_element(By.ID, 'mHamburger').click()
                except:
                    pass
            try:
                time.sleep(1)
                browser.find_element(By.ID, 'HBSignIn').click()
            except:
                pass
            try:
                time.sleep(2)
                browser.find_element(By.ID, 'iShowSkip').click()
                time.sleep(3)
            except:
                if str(browser.current_url).split('?')[0] == "https://account.live.com/proofs/Add":
                    # prRed('[LOGIN] Please complete the Security Check on ' + self.current_account)
                    self.finished_accounts.append(self.current_account)
                    self.logs[self.current_account]['Last check'] = 'Requires manual check!'
                    self.update_logs()
                    exit()
        #Wait 5 seconds
        time.sleep(5)
        # Refresh page
        browser.get('https://bing.com/')
        # Wait 15 seconds
        time.sleep(15 if not self.config["globalOptions"]["fast"] else 5)
        #Update Counter
        try:
            if not isMobile:
                try:
                    self.points_counter = int(browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                except:
                    if browser.find_element(By.ID, 'id_s').is_displayed():
                        browser.find_element(By.ID, 'id_s').click()
                        time.sleep(15)
                        self.check_bing_login(browser, isMobile)
                    time.sleep(5)
                    self.points_counter = int(browser.find_element(By.ID, "id_rc").get_attribute("innerHTML").replace(",", ""))
            else:
                try:
                    browser.find_element(By.ID, 'mHamburger').click()
                except:
                    try:
                        browser.find_element(By.ID, 'bnp_close_link').click()
                        time.sleep(4)
                        browser.find_element(By.ID, 'bnp_btn_accept').click()
                    except:
                        pass
                    time.sleep(1)
                    browser.find_element(By.ID, 'mHamburger').click()
                time.sleep(1)
                self.points_counter = int(browser.find_element(By.ID, 'fly_id_rc').get_attribute('innerHTML'))
        except:
            self.check_bing_login(browser, isMobile)
            
    def wait_until_visible(self, browser: WebDriver, by_: By, selector: str, time_to_wait: int = 10):
        WebDriverWait(browser, time_to_wait).until(ec.visibility_of_element_located((by_, selector)))

    def wait_until_clickable(self, browser: WebDriver, by_: By, selector: str, time_to_wait: int = 10):
        WebDriverWait(browser, time_to_wait).until(ec.element_to_be_clickable((by_, selector)))

    def wait_until_question_refresh(self, browser: WebDriver):
        tries = 0
        refreshCount = 0
        while True:
            try:
                browser.find_elements(By.CLASS_NAME, 'rqECredits')[0]
                return True
            except:
                if tries < 10:
                    tries += 1
                    time.sleep(0.5)
                else:
                    if refreshCount < 5:
                        browser.refresh()
                        refreshCount += 1
                        tries = 0
                        time.sleep(5)
                    else:
                        return False

    def wait_until_quiz_loads(self, browser: WebDriver):
        tries = 0
        refreshCount = 0
        while True:
            try:
                browser.find_element(By.XPATH, '//*[@id="currentQuestionContainer"]')
                return True
            except:
                if tries < 10:
                    tries += 1
                    time.sleep(0.5)
                else:
                    if refreshCount < 5:
                        browser.refresh()
                        refreshCount += 1
                        tries = 0
                        time.sleep(5)
                    else:
                        return False

    def find_between(self, s: str, first: str, last: str) -> str:
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def get_ccode_lang_and_offset(self) -> tuple:
        try:
            nfo = ipapi.location()
            self.lang = nfo['languages'].split(',')[0]
            self.geo = nfo['country']
            self.tz = str(round(int(nfo['utc_offset']) / 100 * 60))
            return(self.lang, self.geo, self.tz)
        except:
            return('en-US', 'US', '-480')