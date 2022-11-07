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
    # TODO: clear all print ops from functions
    # TODO: clear browser from params of all functions instead use self.browser variable
    PC_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.24'
    MOBILE_USER_AGENT = 'Mozilla/5.0 (Linux; Android 12; SM-N9750) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36 EdgA/107.0.1418.28'
    logs: dict = {}
    
    def __init__(self, accounts, accounts_path: str, config: dict):
        self.accounts_path = Path(accounts_path)
        self.accounts = accounts
        self.config: dict = config
        self.points_counter: int = 0
        self.finished_accounts: list = [] 
        self.current_account: str = None
        self.browser: WebDriver = None
        self.lang: str = None
    
    def check_internet_connection(self):
        system = platform.system()
        while True:
            try:
                if system == "Windows":
                    subprocess.check_output(["ping", "-n", "1", "8.8.8.8"], timeout=5)
                elif system == "Linux":
                    subprocess.check_output(["ping", "-c", "1", "8.8.8.8"], timeout=5)
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                time.sleep(1)
    
    def get_or_create_logs(self):
        '''
        Read logs and check whether account farmed or not
        '''
        # access to logs attribute
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
        except FileNotFoundError:
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
        self.browser = chrome_browser_obj
        return self.browser
    
    def login(self, browser: WebDriver, email: str, pwd: str, isMobile: bool = False):
        """Login into  Microsoft account"""
        # Close welcome tab for new sessions
        if self.config.get("session", False):
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
        if self.config.get("session", False):
            if self.browser.title == "We're updating our terms" or self.is_element_exists(By.ID, 'iAccrualForm'):
                time.sleep(2)
                self.browser.find_element(By.ID, 'iNext').click()
                time.sleep(5)
            if self.browser.title == 'Microsoft account | Home' or self.is_element_exists(By.ID, 'navs_container'):
                # prGreen('[LOGIN] Account already logged in !')
                self.rewards_login(self.browser)
                print('[LOGIN]', 'Ensuring login on Bing...')
                self.check_bing_login(self.browser, isMobile)
                return
            elif self.browser.title == 'Your account has been temporarily suspended':
                self.logs[self.current_account]['Last check'] = 'Your account has been locked !'
                self.finished_accounts.append(self.current_account)
                self.update_logs()
                self.clean_logs()
                raise Exception('Your account has been locked !')
        # Wait complete loading
        self.wait_until_visible(self.browser, By.ID, 'loginHeader', 10)
        # Enter email
        print('[LOGIN]', 'Writing email...')
        self.browser.find_element(By.NAME, "loginfmt").send_keys(email)
        # Click next
        self.browser.find_element(By.ID, 'idSIButton9').click()
        # Wait 2 seconds
        time.sleep(5 if not self.config["globalOptions"]["fast"] else 2)
        # Wait complete loading
        self.wait_until_visible(self.browser, By.ID, 'loginHeader', 10)
        # Enter password
        self.browser.find_element(By.ID, "i0118").send_keys(pwd)
        # self.browser.execute_script("document.getElementById('i0118').value = '" + pwd + "';")
        print('[LOGIN]', 'Writing password...')
        # Click next
        self.browser.find_element(By.ID, 'idSIButton9').click()
        # Wait 5 seconds
        time.sleep(5)
        try:
            if self.browser.title == "We're updating our terms" or self.is_element_exists(By.ID, 'iAccrualForm'):
                time.sleep(2)
                self.browser.find_element(By.ID, 'iNext').click()
                time.sleep(5)
            if self.config.get("session", False):
                # Click Yes to stay signed in.
                self.browser.find_element(By.ID, 'idSIButton9').click()
            else:
                # Click No.
                self.browser.find_element(By.ID, 'idBtn_Back').click()
        except NoSuchElementException:
            # Check for if account has been locked.
            if self.browser.title == "Your account has been temporarily suspended" or self.is_element_exists(By.CLASS_NAME, "serviceAbusePageContainer  PageContainer"):
                self.logs[self.current_account]['Last check'] = 'Your account has been locked !'
                self.finished_accounts.append(self.current_account)
                self.update_logs()
                self.clean_logs()
                raise Exception('[ERROR] Your account has been locked !')
            elif self.browser.title == "Help us protect your account":
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
                raise Exception('[ERROR] Unknown error !')
        # Wait 5 seconds
        time.sleep(5)
        # Click Security Check
        print('[LOGIN]', 'Passing security checks...')
        try:
            self.browser.find_element(By.ID, 'iLandingViewAction').click()
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        # Wait complete loading
        try:
            self.wait_until_visible(self.browser, By.ID, 'KmsiCheckboxField', 10)
        except (TimeoutException) as e:
            pass
        # Click next
        try:
            self.browser.find_element(By.ID, 'idSIButton9').click()
            # Wait 5 seconds
            time.sleep(5)
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        print('[LOGIN]', 'Logged-in !')
        # Check Microsoft Rewards
        print('[LOGIN] Logging into Microsoft Rewards...')
        self.rewards_login(self.browser)
        # Check Login
        print('[LOGIN]', 'Ensuring login on Bing...')
        self.check_bing_login(self.browser, isMobile)

    def rewards_login(self, browser: WebDriver):
        #Login into Rewards
        self.browser.get('https://rewards.microsoft.com/dashboard')
        try:
            time.sleep(10 if not self.config["globalOptions"] else 5)
            self.browser.find_element(By.ID, 'raf-signin-link-id').click()
        except:
            pass
        time.sleep(10 if not self.config["globalOptions"]["fast"] else 5)
        # Check for ErrorMessage
        try:
            self.browser.find_element(By.ID, 'error').is_displayed()
            # Check wheter account suspended or not
            if self.browser.find_element(By.XPATH, '//*[@id="error"]/h1').get_attribute('innerHTML') == ' Uh oh, it appears your Microsoft Rewards account has been suspended.':
                self.logs[self.current_account]['Last check'] = 'Your account has been suspended'
                self.logs[self.current_account]["Today's points"] = 'N/A' 
                self.logs[self.current_account]["Points"] = 'N/A' 
                self.clean_logs()
                self.update_logs()
                self.finished_accounts.append(self.current_account)
                raise Exception('Your Microsoft Rewards account has been suspended !')
            # Check whether Rewards is available in your region or not
            elif self.browser.find_element(By.XPATH, '//*[@id="error"]/h1').get_attribute('innerHTML') == 'Microsoft Rewards is not available in this country or region.':
                # prRed('[ERROR] Microsoft Rewards is not available in this country or region !')
                input('[ERROR] Press any key to close...')
                os._exit()
        except NoSuchElementException:
            pass

    @func_set_timeout(300)
    def check_bing_login(self, browser: WebDriver, isMobile: bool = False):
        #Access Bing.com
        self.browser.get('https://bing.com/')
        # Wait 15 seconds
        time.sleep(15 if not self.config["globalOptions"]["fast"] else 5)
        # try to get points at first if account already logged in
        if self.config.get("session", False):
            try:
                if not isMobile:
                    try:
                        self.points_counter = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                    except ValueError:
                        if self.browser.find_element(By.ID, 'id_s').is_displayed():
                            self.browser.find_element(By.ID, 'id_s').click()
                            time.sleep(15)
                            self.check_bing_login(self.browser, isMobile)
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
                    # prRed('[LOGIN] Please complete the Security Check on ' + self.current_account)
                    self.finished_accounts.append(self.current_account)
                    self.logs[self.current_account]['Last check'] = 'Requires manual check!'
                    self.update_logs()
                    exit()
        #Wait 5 seconds
        time.sleep(5)
        # Refresh page
        self.browser.get('https://bing.com/')
        # Wait 15 seconds
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
                        self.check_bing_login(self.browser, isMobile)
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
            self.check_bing_login(self.browser, isMobile)
            
    def wait_until_visible(self, browser: WebDriver, by_: By, selector: str, time_to_wait: int = 10):
        WebDriverWait(self.browser, time_to_wait).until(ec.visibility_of_element_located((by_, selector)))

    def wait_until_clickable(self, browser: WebDriver, by_: By, selector: str, time_to_wait: int = 10):
        WebDriverWait(self.browser, time_to_wait).until(ec.element_to_be_clickable((by_, selector)))

    def wait_until_question_refresh(self, browser: WebDriver):
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

    def wait_until_quiz_loads(self, browser: WebDriver):
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

    def get_dashboard_data(self, browser: WebDriver) -> dict:
        dashboard = self.find_between(self.browser.find_element(By.XPATH, '/html/body').get_attribute('innerHTML'), "var dashboard = ", ";\n        appDataModule.constant(\"prefetchedDashboard\", dashboard);")
        dashboard = json.loads(dashboard)
        return dashboard
    
    def get_account_points(self, browser: WebDriver) -> int:
        return self.get_dashboard_data(self.browser)['userStatus']['availablePoints']
    
    def get_ccode_lang_and_offset(self) -> tuple:
        try:
            nfo = ipapi.location()
            self.lang = nfo['languages'].split(',')[0]
            self.geo = nfo['country']
            self.tz = str(round(int(nfo['utc_offset']) / 100 * 60))
            return(self.lang, self.geo, self.tz)
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
        
    def reset_tabs(self, browser: WebDriver):
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
            self.browser.get('https://rewards.microsoft.com/')
        except:
            self.browser.get('https://rewards.microsoft.com/')
            
    def get_answer_code(self, key: str, string: str) -> str:
        """Get answer code for this or that quiz"""
        t = 0
        for i in range(len(string)):
            t += ord(string[i])
        t += int(key[-2:], 16)
        return str(t)
    
    def bing_searches(self, browser: WebDriver, numberOfSearches: int, isMobile: bool = False):
        i = 0
        r = RandomWords()
        search_terms = r.get_random_words(limit = numberOfSearches)
        if search_terms == None:
            search_terms = self.get_google_trends(numberOfSearches)
        for word in search_terms:
            i += 1
            print('[BING]', str(i) + "/" + str(numberOfSearches))
            points = self.bing_search(self.browser, word, isMobile)
            if points <= self.points_counter :
                relatedTerms = self.get_related_terms(word)
                for term in relatedTerms :
                    points = self.bing_search(self.browser, term, isMobile)
                    if points >= self.points_counter:
                        break
            if points > 0:
                self.points_counter = points
            else:
                break
            
    def bing_search(self, browser: WebDriver, word: str, isMobile: bool):
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
            if not isMobile:
                try:
                    points = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML'))
                except ValueError:
                    points = int(self.browser.find_element(By.ID, 'id_rc').get_attribute('innerHTML').replace(",", ""))
            else:
                try :
                    self.browser.find_element(By.ID, 'mHamburger').click()
                except UnexpectedAlertPresentException:
                    try :
                        self.browser.switch_to.alert.accept()
                        time.sleep(1)
                        self.browser.find_element(By.ID, 'mHamburger').click()
                    except NoAlertPresentException :
                        pass
                time.sleep(1)
                points = int(self.browser.find_element(By.ID, 'fly_id_rc').get_attribute('innerHTML'))
        except:
            pass
        return points
    
    def complete_promotional_items(self, browser: WebDriver):
        try:
            item = self.get_dashboard_data(self.browser)["promotionalItem"]
            if (item["pointProgressMax"] == 100 or item["pointProgressMax"] == 200) and item["complete"] == False and item["destinationUrl"] == "https://rewards.microsoft.com/":
                self.browser.find_element(By.XPATH, '//*[@id="promo-item"]/section/div/div/div/a').click()
                time.sleep(1)
                self.browser.switch_to.window(window_name = self.browser.window_handles[1])
                time.sleep(8)
                self.browser.close()
                time.sleep(2)
                self.browser.switch_to.window(window_name = self.browser.window_handles[0])
                time.sleep(2)
        except:
            pass
        
    def complete_daily_set_search(self, browser: WebDriver, cardNumber: int):
        time.sleep(5)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-daily-set-item-content/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(random.randint(13, 17) if not self.config["globalOptions"]["fast"] else random.randint(6, 9))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_daily_set_survey(self, browser: WebDriver, cardNumber: int):
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
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_daily_set_quiz(self, browser: WebDriver, cardNumber: int):
        time.sleep(5)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section[1]/div/mee-card-group[1]/div[1]/mee-card[{str(cardNumber)}]/div[1]/card-content[1]/mee-rewards-daily-set-item-content[1]/div[1]/a[1]/div[3]/span[1]').click()
        time.sleep(3)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(12 if not self.config["globalOptions"]["fast"] else random.randint(5, 8))
        if not self.wait_until_quiz_loads(self.browser):
            self.reset_tabs(self.browser)
            return
        # Accept cookie popup
        if self.is_element_exists(By.ID, 'bnp_container'):
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
            time.sleep(2)
        self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(self.browser, By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
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
                    if not self.wait_until_question_refresh(self.browser):
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
        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)

    def complete_daily_set_variable_activity(self, browser: WebDriver, cardNumber: int):
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
            self.wait_until_visible(self.browser, By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 3)
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
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_daily_set_this_or_that(self, browser: WebDriver, cardNumber: int):
        time.sleep(2)
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-daily-set-item-content/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(15 if not self.config["globalOptions"]["fast"] else random.randint(5, 8))
        # Accept cookie popup
        if self.is_element_exists(By.ID, 'bnp_container'):
            self.browser.find_element(By.ID, 'bnp_btn_accept').click()
            time.sleep(2)
        if not self.wait_until_quiz_loads(self.browser):
            self.reset_tabs(self.browser)
            return
        self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(self.browser, By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
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

        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
    
    def complete_daily_set(self, browser: WebDriver):
        print('[DAILY SET]', 'Trying to complete the Daily Set...')
        d = self.get_dashboard_data(self.browser)
        error = False
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
                        print('[DAILY SET]', 'Completing search of card ' + str(cardNumber))
                        self.complete_daily_set_search(self.browser, cardNumber)
                    if activity['promotionType'] == "quiz":
                        if activity['pointProgressMax'] == 50 and activity['pointProgress'] == 0:
                            print('[DAILY SET]', 'Completing This or That of card ' + str(cardNumber))
                            self.complete_daily_set_this_or_that(self.browser, cardNumber)
                        elif (activity['pointProgressMax'] == 40 or activity['pointProgressMax'] == 30) and activity['pointProgress'] == 0:
                            print('[DAILY SET]', 'Completing quiz of card ' + str(cardNumber))
                            self.complete_daily_set_quiz(self.browser, cardNumber)
                        elif activity['pointProgressMax'] == 10 and activity['pointProgress'] == 0:
                            searchUrl = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(activity['destinationUrl']).query)['ru'][0])
                            searchUrlQueries = urllib.parse.parse_qs(urllib.parse.urlparse(searchUrl).query)
                            filters = {}
                            for filter in searchUrlQueries['filters'][0].split(" "):
                                filter = filter.split(':', 1)
                                filters[filter[0]] = filter[1]
                            if "PollScenarioId" in filters:
                                print('[DAILY SET]', 'Completing poll of card ' + str(cardNumber))
                                self.complete_daily_set_survey(self.browser, cardNumber)
                            else:
                                print('[DAILY SET]', 'Completing quiz of card ' + str(cardNumber))
                                self.complete_daily_set_variable_activity(self.browser, cardNumber)
            except:
                error = True
                self.reset_tabs(self.browser)
        self.logs[self.current_account]['Daily'] = True
        self.update_logs() 
        
    def complete_punch_card(self, browser: WebDriver, url: str, childPromotions: dict):
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
                    self.wait_until_visible(self.browser, By.XPATH, '//*[@id="currentQuestionContainer"]', 10)
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
                
    def complete_punch_cards(self, browser: WebDriver):
        print('[PUNCH CARDS]', 'Trying to complete the Punch Cards...')
        punchCards = self.get_dashboard_data(self.browser)['punchCards']
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
                    self.complete_punch_card(self.browser, dest, punchCard['childPromotions'])
            except:
                self.reset_tabs(self.browser)
        time.sleep(2)
        self.browser.get('https://rewards.microsoft.com/dashboard/')
        time.sleep(2)
        self.logs[self.current_account]['Punch cards'] = True
        self.update_logs()
        
    def complete_more_promotion_search(self, browser: WebDriver, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name = self.browser.window_handles[1])
        time.sleep(random.randint(13, 17) if not self.config["globalOptions"]["fast"] else random.randint(5, 8))
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name = self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotion_quiz(self, browser: WebDriver, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(8 if not self.config["globalOptions"] else 5)
        if not self.wait_until_quiz_loads(self.browser):
            self.reset_tabs(self.browser)
            return
        CurrentQuestionNumber = self.browser.execute_script("return _w.rewardsQuizRenderInfo.currentQuestionNumber")
        if CurrentQuestionNumber == 1 and self.is_element_exists(By.XPATH, '//*[@id="rqStartQuiz"]'):
            self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(self.browser, By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
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
                    if not self.wait_until_question_refresh(self.browser):
                        return
                time.sleep(5)
            elif numberOfOptions == 4:
                correctOption = self.browser.execute_script("return _w.rewardsQuizRenderInfo.correctAnswer")
                for i in range(4):
                    if self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).get_attribute("data-option") == correctOption:
                        self.browser.find_element(By.ID, "rqAnswerOption" + str(i)).click()
                        time.sleep(5)
                        if not self.wait_until_question_refresh(self.browser):
                            return
                        break
                time.sleep(5)
        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotion_ABC(self, browser: WebDriver, cardNumber: int):
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
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotion_this_or_that(self, browser: WebDriver, cardNumber: int):
        self.browser.find_element(By.XPATH, f'//*[@id="app-host"]/ui-view/mee-rewards-dashboard/main/div/mee-rewards-more-activities-card/mee-card-group/div/mee-card[{str(cardNumber)}]/div/card-content/mee-rewards-more-activities-card-item/div/a/div/span').click()
        time.sleep(1)
        self.browser.switch_to.window(window_name=self.browser.window_handles[1])
        time.sleep(8 if not self.config["globalOptions"]["fast"] else 5)
        if not self.wait_until_quiz_loads(self.browser):
            self.reset_tabs(self.browser)
            return
        CrrentQuestionNumber = self.browser.execute_script("return _w.rewardsQuizRenderInfo.currentQuestionNumber")
        NumberOfQuestionsLeft = 10 - CrrentQuestionNumber + 1
        if CrrentQuestionNumber == 1 and self.is_element_exists(By.XPATH, '//*[@id="rqStartQuiz"]'):
            self.browser.find_element(By.XPATH, '//*[@id="rqStartQuiz"]').click()
        self.wait_until_visible(self.browser, By.XPATH, '//*[@id="currentQuestionContainer"]/div/div[1]', 10)
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

        time.sleep(5)
        self.browser.close()
        time.sleep(2)
        self.browser.switch_to.window(window_name=self.browser.window_handles[0])
        time.sleep(2)
        
    def complete_more_promotions(self, browser: WebDriver):
        print('[MORE PROMO]', 'Trying to complete More Promotions...')
        morePromotions = self.get_dashboard_data(self.browser)['morePromotions']
        i = 0
        for promotion in morePromotions:
            try:
                i += 1
                if promotion['complete'] == False and promotion['pointProgressMax'] != 0:
                    if promotion['promotionType'] == "urlreward":
                        self.complete_more_promotion_search(self.browser, i)
                    elif promotion['promotionType'] == "quiz":
                        if promotion['pointProgressMax'] == 10:
                            self.complete_more_promotion_ABC(self.browser, i)
                        elif promotion['pointProgressMax'] == 30 or promotion['pointProgressMax'] == 40:
                            self.complete_more_promotion_quiz(self.browser, i)
                        elif promotion['pointProgressMax'] == 50:
                            self.complete_more_promotion_this_or_that(self.browser, i)
                    else:
                        if promotion['pointProgressMax'] == 100 or promotion['pointProgressMax'] == 200:
                            self.complete_more_promotion_search(self.browser, i)
                if promotion['complete'] == False and promotion['pointProgressMax'] == 100 and promotion['promotionType'] == "" \
                    and promotion['destinationUrl'] == "https://rewards.microsoft.com":
                    self.complete_more_promotion_search(self.browser, i)
            except:
                self.reset_tabs(self.browser)
        self.logs[self.current_account]['More promotions'] = True
        self.update_logs()
        
    def get_remaining_searches(self, browser: WebDriver):
        dashboard = self.get_dashboard_data(self.browser)
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
    