<h2 align="center">Mircrosoft Rewards Bot</h2>

<p align="center">
  <img src="https://forthebadge.com/images/badges/made-with-python.svg"/>
  <img src="http://ForTheBadge.com/images/badges/built-by-developers.svg"/>
  <img src="http://ForTheBadge.com/images/badges/uses-git.svg"/>
  <img src="http://ForTheBadge.com/images/badges/built-with-love.svg"/>
</p>
<h3 align="center">A simple script that uses Selenium and PyQt5 to farm Microsoft Rewards.</h3>
<br>
<p align="center">
<img src="https://user-images.githubusercontent.com/60227955/206023577-f933334c-edf3-49fe-b30e-12d806847ab7.png"</img>
</p>

## Installation
<p align="left">
  <ul>
    <li>Install requirements with the following command : <pre>pip install -r requirements.txt</pre></li>
    <li>Make sure you have Chrome installed</li>
    <li>Install ChromeDriver :<ul>
      <li>Windows :<ul>
        <li>Download Chrome WebDriver as same as your Google Chrome version : https://chromedriver.chromium.org/downloads</li>
        <li>Place the file in X:\Windows (X as your Windows disk letter)</li>
      </ul>
      <li>MacOS or Linux :<ul>
        <li><pre>apt install chromium-chromedriver</pre></li>
        <li>or if you have brew : <pre>brew cask install chromedriver</pre></li>
      </ul>
    </ul></li>
    <li>Edit the accounts.json.sample with your accounts credentials and rename it by removing .sample at the end<br/>
    If you want to add more than one account, the syntax is the following (<code>mobile_user_agent</code> is optional): <pre>[
    {
        "username": "Your Email",
        "password": "Your Password",
        "mobile_user_agent": "your preferred mobile user agent"
    },
    {
        "username": "Your Email 2",
        "password": "Your Password 2",
        "mobile_user_agent": "your preferred mobile user agent"
    }
]</pre></li>
  <li>Run main.pyw</li>
  </ul>
</p>

## Features
<p align="left">
  <ul>
    <li>Save progress of accounts in logs</li>
    <li>Use headless to create browser instance without graphical user interface (Not recommended)</li>
    <li>You can use fast mode to redeuce delays in bot if you have high speed Internet connection</li>
    <li>Save errors in a txt file for any unpredicted errors</li>
    <li>You can save your account in browser session by enabling it to skip login on each start</li>
    <li>You can choose to farm which part of Microsoft Rewards among daily quests, punch cards, more activities, Bing searches (PC, Mobile)</li>
    <li>You can set time for bot to start at your desired time</li>
    <li>Send logs to your Telegram through your Telegram bot with setting Token and Chat ID</li>
    <li>Shutdown PC after farm</li>
   </ul>
</p>

## Credits
Core script created by [@charlesbel](https://github.com/charlesbel/Microsoft-Rewards-Farmer).
