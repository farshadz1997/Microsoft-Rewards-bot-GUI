from PyQt5 import QtCore, QtGui, QtWidgets
import json
from pathlib import Path

from .farmer import Farmer
from selenium.webdriver.chrome.webdriver import WebDriver


class UserInterface(object):
    def __init__(self):
        self.default_config = {
            "accountsPath": "",
            "time": "12:00 AM",
            "globalOptions": {
                "headless": False,
                "session": False,
                "fast": False,
                "saveErrors": False,
                "shutdownSystem": False
            },
            "farmOptions": {
                "dailyQuests": False,
                "punchCards": False,
                "moreActivities": False,
                "searchPC": False,
                "searchMobile": False,
            },
            "telegram": {"token": "", "chatID": ""},
        }
        self.sample_accounts = [{"username": "Your Email", "password": "Your Password"}]

    def setupUi(self, MainWindow):
        self.MainWindow = MainWindow
        MainWindow.setObjectName("MainWindow")
        MainWindow.setWindowModality(QtCore.Qt.NonModal)
        MainWindow.setEnabled(True)
        MainWindow.resize(600, 612)
        MainWindow.setFixedSize(MainWindow.size())

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("images/icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.accounts_label = QtWidgets.QLabel(self.centralwidget)
        self.accounts_label.setGeometry(QtCore.QRect(70, 120, 71, 41))
        self.accounts_label.setTextFormat(QtCore.Qt.MarkdownText)
        self.accounts_label.setObjectName("accounts_label")

        self.accounts_lineedit = QtWidgets.QLineEdit(self.centralwidget)
        self.accounts_lineedit.setGeometry(QtCore.QRect(140, 130, 311, 20))
        self.accounts_lineedit.setReadOnly(True)
        self.accounts_lineedit.setClearButtonEnabled(False)
        self.accounts_lineedit.setObjectName("accounts_lineedit")

        self.open_accounts_button = QtWidgets.QPushButton(self.centralwidget)
        self.open_accounts_button.setGeometry(QtCore.QRect(460, 130, 75, 21))
        self.open_accounts_button.setObjectName("open_accounts_button")

        self.title_frame = QtWidgets.QFrame(self.centralwidget)
        self.title_frame.setGeometry(QtCore.QRect(40, 10, 511, 81))
        self.title_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.title_frame.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.title_frame.setObjectName("title_frame")

        self.creator_label = QtWidgets.QLabel(self.title_frame)
        self.creator_label.setGeometry(QtCore.QRect(170, 50, 171, 21))

        font = QtGui.QFont()
        font.setFamily("Lucida Sans Unicode")
        font.setPointSize(12)

        self.creator_label.setFont(font)
        self.creator_label.setTextFormat(QtCore.Qt.MarkdownText)
        self.creator_label.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.creator_label.setObjectName("creator_label")

        self.title_label = QtWidgets.QLabel(self.title_frame)
        self.title_label.setGeometry(QtCore.QRect(110, 20, 291, 20))

        font = QtGui.QFont()
        font.setFamily("Lucida Sans Unicode")
        font.setPointSize(16)

        self.title_label.setFont(font)
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setObjectName("title_label")

        self.label = QtWidgets.QLabel(self.title_frame)
        self.label.setGeometry(QtCore.QRect(60, 10, 47, 61))
        self.label.setText("")
        self.label.setPixmap(QtGui.QPixmap("images/logo.png"))
        self.label.setScaledContents(True)
        self.label.setObjectName("label")

        self.label_2 = QtWidgets.QLabel(self.title_frame)
        self.label_2.setGeometry(QtCore.QRect(400, 10, 47, 61))
        self.label_2.setText("")
        self.label_2.setPixmap(QtGui.QPixmap("images/logo.png"))
        self.label_2.setScaledContents(True)
        self.label_2.setObjectName("label_2")

        self.set_time_label = QtWidgets.QLabel(self.centralwidget)
        self.set_time_label.setGeometry(QtCore.QRect(70, 170, 61, 21))
        self.set_time_label.setTextFormat(QtCore.Qt.MarkdownText)
        self.set_time_label.setObjectName("set_time_label")

        self.timeEdit = QtWidgets.QTimeEdit(self.centralwidget)
        self.timeEdit.setEnabled(False)
        self.timeEdit.setGeometry(QtCore.QRect(140, 170, 311, 22))
        self.timeEdit.setWrapping(False)
        self.timeEdit.setFrame(True)
        self.timeEdit.setReadOnly(False)
        self.timeEdit.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
        self.timeEdit.setTime(QtCore.QTime(1, 0, 0))
        self.timeEdit.setObjectName("timeEdit")

        self.active_timer_checkbox = QtWidgets.QCheckBox(self.centralwidget)
        self.active_timer_checkbox.setGeometry(QtCore.QRect(460, 160, 81, 41))
        self.active_timer_checkbox.setObjectName("active_timer_checkbox")

        self.global_options_groupbox = QtWidgets.QGroupBox(self.centralwidget)
        self.global_options_groupbox.setGeometry(QtCore.QRect(70, 210, 111, 141))
        self.global_options_groupbox.setObjectName("global_options_groupbox")

        self.verticalLayout = QtWidgets.QVBoxLayout(self.global_options_groupbox)
        self.verticalLayout.setObjectName("verticalLayout")

        self.headless_checkbox = QtWidgets.QCheckBox(self.global_options_groupbox)
        self.headless_checkbox.setStatusTip("")
        self.headless_checkbox.setObjectName("headless_checkbox")
        self.verticalLayout.addWidget(self.headless_checkbox)

        self.session_checkbox = QtWidgets.QCheckBox(self.global_options_groupbox)
        self.session_checkbox.setObjectName("session_checkbox")
        self.verticalLayout.addWidget(self.session_checkbox)

        self.fast_mode_checkbox = QtWidgets.QCheckBox(self.global_options_groupbox)
        self.fast_mode_checkbox.setObjectName("fast_mode_checkbox")
        self.verticalLayout.addWidget(self.fast_mode_checkbox)

        self.save_errors = QtWidgets.QCheckBox(self.global_options_groupbox)
        self.save_errors.setObjectName("save_errors")
        self.verticalLayout.addWidget(self.save_errors)

        self.shutdown_system = QtWidgets.QCheckBox(self.global_options_groupbox)
        self.shutdown_system.setObjectName("shutdown_system")
        self.verticalLayout.addWidget(self.shutdown_system)
        
        self.farm_options_groupbox = QtWidgets.QGroupBox(self.centralwidget)
        self.farm_options_groupbox.setGeometry(QtCore.QRect(190, 210, 121, 141))
        self.farm_options_groupbox.setObjectName("farm_options_groupbox")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.farm_options_groupbox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        self.daily_quests_checkbox = QtWidgets.QCheckBox(self.farm_options_groupbox)
        self.daily_quests_checkbox.setObjectName("daily_quests_checkbox")
        self.verticalLayout_2.addWidget(self.daily_quests_checkbox)

        self.punch_cards_checkbox = QtWidgets.QCheckBox(self.farm_options_groupbox)
        self.punch_cards_checkbox.setObjectName("punch_cards_checkbox")
        self.verticalLayout_2.addWidget(self.punch_cards_checkbox)

        self.more_activities_checkbox = QtWidgets.QCheckBox(self.farm_options_groupbox)
        self.more_activities_checkbox.setObjectName("more_activities_checkbox")
        self.verticalLayout_2.addWidget(self.more_activities_checkbox)

        self.search_pc_checkbox = QtWidgets.QCheckBox(self.farm_options_groupbox)
        self.search_pc_checkbox.setObjectName("search_pc_checkbox")
        self.verticalLayout_2.addWidget(self.search_pc_checkbox)

        self.search_mobile_checkbox = QtWidgets.QCheckBox(self.farm_options_groupbox)
        self.search_mobile_checkbox.setObjectName("search_mobile_checkbox")
        self.verticalLayout_2.addWidget(self.search_mobile_checkbox)

        self.telegram_groupbox = QtWidgets.QGroupBox(self.centralwidget)
        self.telegram_groupbox.setGeometry(QtCore.QRect(320, 210, 221, 141))
        self.telegram_groupbox.setObjectName("telegram_groupbox")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.telegram_groupbox)
        self.verticalLayout_3.setObjectName("verticalLayout_3")

        self.api_key_label = QtWidgets.QLabel(self.telegram_groupbox)
        self.api_key_label.setObjectName("api_key_label")
        self.verticalLayout_3.addWidget(self.api_key_label)

        self.api_key_lineedit = QtWidgets.QLineEdit(self.telegram_groupbox)
        self.api_key_lineedit.setEnabled(False)
        self.api_key_lineedit.setObjectName("api_key_lineedit")
        self.verticalLayout_3.addWidget(self.api_key_lineedit)

        self.chat_id_label = QtWidgets.QLabel(self.telegram_groupbox)
        self.chat_id_label.setObjectName("chat_id_label")
        self.verticalLayout_3.addWidget(self.chat_id_label)

        self.chat_id_lineedit = QtWidgets.QLineEdit(self.telegram_groupbox)
        self.chat_id_lineedit.setEnabled(False)
        self.chat_id_lineedit.setInputMethodHints(QtCore.Qt.ImhPreferNumbers)
        self.chat_id_lineedit.setObjectName("chat_id_lineedit")
        self.verticalLayout_3.addWidget(self.chat_id_lineedit)

        self.send_to_telegram_checkbox = QtWidgets.QCheckBox(self.telegram_groupbox)
        self.send_to_telegram_checkbox.setObjectName("send_to_telegram_checkbox")
        self.verticalLayout_3.addWidget(self.send_to_telegram_checkbox)

        self.progress_info_groupbox = QtWidgets.QGroupBox(self.centralwidget)
        self.progress_info_groupbox.setGeometry(QtCore.QRect(70, 360, 471, 201))
        self.progress_info_groupbox.setObjectName("progress_info_groupbox")

        self.start_button = QtWidgets.QPushButton(self.progress_info_groupbox)
        self.start_button.setEnabled(False)
        self.start_button.setGeometry(QtCore.QRect(140, 160, 75, 23))
        self.start_button.setObjectName("start_button")

        self.stop_button = QtWidgets.QPushButton(self.progress_info_groupbox)
        self.stop_button.setEnabled(False)
        self.stop_button.setGeometry(QtCore.QRect(230, 160, 75, 23))
        self.stop_button.setObjectName("stop_button")

        self.number_of_accounts_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.number_of_accounts_label.setGeometry(QtCore.QRect(10, 30, 111, 16))
        self.number_of_accounts_label.setObjectName("number_of_accounts_label")

        self.finished_accounts_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.finished_accounts_label.setGeometry(QtCore.QRect(10, 60, 101, 16))
        self.finished_accounts_label.setObjectName("finished_accounts_label")

        self.locked_accounts_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.locked_accounts_label.setGeometry(QtCore.QRect(10, 90, 91, 16))
        self.locked_accounts_label.setObjectName("locked_accounts_label")

        self.suspended_accounts_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.suspended_accounts_label.setGeometry(QtCore.QRect(10, 120, 111, 16))
        self.suspended_accounts_label.setObjectName("suspended_accounts_label")

        self.accounts_count = QtWidgets.QLabel(self.progress_info_groupbox)
        self.accounts_count.setGeometry(QtCore.QRect(140, 30, 47, 13))
        self.accounts_count.setObjectName("accounts_count")

        self.finished_accounts_count = QtWidgets.QLabel(self.progress_info_groupbox)
        self.finished_accounts_count.setGeometry(QtCore.QRect(140, 60, 47, 13))
        self.finished_accounts_count.setObjectName("finished_accounts_count")

        self.locked_accounts_count = QtWidgets.QLabel(self.progress_info_groupbox)
        self.locked_accounts_count.setGeometry(QtCore.QRect(140, 90, 47, 13))
        self.locked_accounts_count.setObjectName("locked_accounts_count")

        self.suspended_accounts_count = QtWidgets.QLabel(self.progress_info_groupbox)
        self.suspended_accounts_count.setGeometry(QtCore.QRect(140, 120, 47, 13))
        self.suspended_accounts_count.setObjectName("suspended_accounts_count")

        self.current_account_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.current_account_label.setGeometry(QtCore.QRect(250, 30, 91, 16))
        self.current_account_label.setObjectName("current_account_label")

        self.current_point_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.current_point_label.setGeometry(QtCore.QRect(250, 60, 81, 16))
        self.current_point_label.setObjectName("current_point_label")

        self.section_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.section_label.setGeometry(QtCore.QRect(250, 90, 81, 16))
        self.section_label.setObjectName("section_label")

        self.detail_label = QtWidgets.QLabel(self.progress_info_groupbox)
        self.detail_label.setGeometry(QtCore.QRect(250, 120, 81, 16))
        self.detail_label.setObjectName("detail_label")

        self.current_account = QtWidgets.QLabel(self.progress_info_groupbox)
        self.current_account.setGeometry(QtCore.QRect(340, 28, 111, 20))
        self.current_account.setObjectName("current_account")

        self.current_point = QtWidgets.QLabel(self.progress_info_groupbox)
        self.current_point.setGeometry(QtCore.QRect(340, 58, 81, 20))
        self.current_point.setObjectName("current_point")

        self.section = QtWidgets.QLabel(self.progress_info_groupbox)
        self.section.setGeometry(QtCore.QRect(340, 90, 47, 13))
        self.section.setObjectName("section")

        self.detail = QtWidgets.QLabel(self.progress_info_groupbox)
        self.detail.setGeometry(QtCore.QRect(340, 120, 47, 13))
        self.detail.setObjectName("detail")

        self.title_frame.raise_()
        self.accounts_label.raise_()
        self.accounts_lineedit.raise_()
        self.open_accounts_button.raise_()
        self.set_time_label.raise_()
        self.timeEdit.raise_()
        self.active_timer_checkbox.raise_()
        self.global_options_groupbox.raise_()
        self.farm_options_groupbox.raise_()
        self.telegram_groupbox.raise_()
        self.progress_info_groupbox.raise_()
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 600, 21))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.active_timer_checkbox.clicked["bool"].connect(self.timeEdit.setEnabled)
        self.send_to_telegram_checkbox.clicked["bool"].connect(self.api_key_lineedit.setEnabled)
        self.send_to_telegram_checkbox.clicked["bool"].connect(self.chat_id_lineedit.setEnabled)
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        self.open_accounts_button.clicked.connect(self.open_accounts)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        
    def disable_elements(self):
        self.start_button.setEnabled(False)
        self.global_options_groupbox.setEnabled(False)
        self.farm_options_groupbox.setEnabled(False)
        self.open_accounts_button.setEnabled(False)
        self.active_timer_checkbox.setEnabled(False)
        self.send_to_telegram_checkbox.setEnabled(False)
        self.api_key_lineedit.setEnabled(False)
        self.chat_id_lineedit.setEnabled(False)
        self.timeEdit.setEnabled(False)
        self.accounts_count.setText(str(len(self.accounts)))
        self.finished_accounts_count.setText("0")
        self.locked_accounts_count.setText("0")
        self.suspended_accounts_count.setText("0")
        self.current_account.setText("")
        self.current_point.setText("")
        self.section.setText("")
        self.detail.setText("")
        
    def enable_elements(self):
        self.current_account.setText("-")
        self.current_point.setText("-")
        self.section.setText("-")
        self.detail.setText("-")
        self.start_button.setEnabled(True)
        self.global_options_groupbox.setEnabled(True)
        self.farm_options_groupbox.setEnabled(True)
        self.open_accounts_button.setEnabled(True)
        self.active_timer_checkbox.setEnabled(True)
        if not self.active_timer_checkbox.isChecked():
            self.timeEdit.setEnabled(False)
        else:
            self.timeEdit.setEnabled(True)
        self.send_to_telegram_checkbox.setEnabled(True)
        if not self.send_to_telegram_checkbox.isChecked():
            self.api_key_lineedit.setEnabled(False)
            self.chat_id_lineedit.setEnabled(False)
        else:
            self.api_key_lineedit.setEnabled(True)
            self.chat_id_lineedit.setEnabled(True)
    
    def update_points_counter(self, value):
        self.current_point.setText(str(value))
    
    def update_stop_button(self, value: bool):
        self.stop_button.setEnabled(value)
      
    def update_section(self, value):
        self.section.setText(value)
        self.section.adjustSize()
        
    def update_detail(self, value):
        self.detail.setText(value)
        self.detail.adjustSize()
    
    def update_accounts_info(self):
        self.current_account.setText(self.farmer.current_account)
        self.finished_accounts_count.setText(str(len(self.farmer.finished_accounts)))
        self.locked_accounts_count.setText(str(len(self.farmer.locked_accounts)))
        self.suspended_accounts_count.setText(str(len(self.farmer.suspended_accounts)))
    
    def start(self):
        self.save_config()
        if not any(self.config["farmOptions"].values()):
            self.send_error(text="You must select at least one option to farm.")
            return None
        self.disable_elements()
        self.farmer_thread = QtCore.QThread(self.MainWindow.thread())
        self.farmer = Farmer(self)
        self.farmer.moveToThread(self.farmer_thread)
        self.farmer_thread.started.connect(self.farmer.perform_run)
        self.farmer.finished.connect(self.farmer_thread.quit)
        self.farmer.finished.connect(self.farmer.deleteLater)
        self.farmer_thread.finished.connect(self.farmer_thread.deleteLater)
        # update elements with signals
        self.farmer.finished.connect(self.enable_elements)
        self.farmer.finished.connect(lambda: self.stop_button.setEnabled(False))
        self.farmer.points.connect(self.update_points_counter)
        self.farmer.section.connect(self.update_section)
        self.farmer.detail.connect(self.update_detail)
        self.farmer.accounts_info_sig.connect(self.update_accounts_info)
        self.farmer.stop_button_enabled.connect(self.update_stop_button)
        
        self.farmer_thread.start()

    def stop(self):
        self.stop_button.setEnabled(False)
        if isinstance(self.farmer.browser, WebDriver) or self.farmer.browser is not None:
            self.farmer.browser.quit()
        self.farmer_thread.requestInterruption()

    def open_accounts(self):
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Open File", "", "JSON Files (*.json)")
        if fileName:
            self.accounts = self.get_accounts(fileName)

    def get_accounts(self, path=Path(__file__).parent.parent / "accounts.json"):
        try:
            accounts = json.load(open(path, "r"))
        except json.decoder.JSONDecodeError as e:
            self.send_error("Error", "JSON decode error", str(e))
        except FileNotFoundError:
            accounts_path = Path(__file__).parent.parent / "accounts.json"
            with open(accounts_path, "w") as f:
                f.write(json.dumps(self.sample_accounts, indent=4))
            self.send_info(
                "Info",
                "accounts file not found",
                "accounts file not found," f"a new one has been created at '{str(accounts_path)}'. Edit it then open it.",
            )
            self.accounts = self.sample_accounts
        else:
            for account in accounts:
                if "username" and "password" in account.keys():
                    continue
                else:
                    self.send_error(
                        "Error",
                        "Accounts need to have 'username' and 'password'",
                        "One or some of your accounts do not have username or password.",
                    )
                    self.accounts_lineedit.clear()
                    return None
            self.accounts_lineedit.setText(str(path))
            self.start_button.setEnabled(True)
            self.accounts = accounts
            return accounts

    def send_error(self, window_title: str = "Error", text: str = None, detail: str = None):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setWindowTitle(window_title)
        msg.setText(text)
        msg.setInformativeText(detail)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def send_info(self, window_title: str = "Info", text: str = None, detail: str = None):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle(window_title)
        msg.setText(text)
        msg.setInformativeText(detail)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def get_config(self):
        """Get config from config.json or create it if it doesn't exist"""
        try:
            config = json.load(open(f"{Path(__file__).parent.parent}/config.json", "r"))
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open(f"{Path(__file__).parent.parent}/config.json", "w") as f:
                f.write(json.dumps(self.default_config, indent=4))
            self.config = self.default_config
            return self.config
        else:
            if Path(config["accountsPath"]).is_file():
                self.accounts = self.get_accounts(config["accountsPath"])
            else:
                self.get_accounts()
            self.config = config
            return self.config

    def set_config(self):
        """Set config from config.json"""
        self.timeEdit.setTime(QtCore.QTime.fromString(self.config["time"], "hh:mm AP"))
        self.headless_checkbox.setChecked(self.config["globalOptions"]["headless"])
        self.session_checkbox.setChecked(self.config["globalOptions"]["session"])
        self.fast_mode_checkbox.setChecked(self.config["globalOptions"]["fast"])
        self.save_errors.setChecked(self.config["globalOptions"]["saveErrors"])
        self.shutdown_system.setChecked(self.config["globalOptions"]["shutdownSystem"])
        self.daily_quests_checkbox.setChecked(self.config["farmOptions"]["dailyQuests"])
        self.punch_cards_checkbox.setChecked(self.config["farmOptions"]["punchCards"])
        self.more_activities_checkbox.setChecked(self.config["farmOptions"]["moreActivities"])
        self.search_pc_checkbox.setChecked(self.config["farmOptions"]["searchPC"])
        self.search_mobile_checkbox.setChecked(self.config["farmOptions"]["searchMobile"])
        self.api_key_lineedit.setText(self.config["telegram"]["token"])
        self.chat_id_lineedit.setText(self.config["telegram"]["chatID"])

    def save_config(self):
        """Save config to config.json"""
        self.config = {
            "accountsPath": self.accounts_lineedit.text(),
            "time": self.timeEdit.text(),
            "globalOptions": {
                "headless": self.headless_checkbox.isChecked(),
                "session": self.session_checkbox.isChecked(),
                "fast": self.fast_mode_checkbox.isChecked(),
                "saveErrors": self.save_errors.isChecked(),
                "shutdownSystem": self.shutdown_system.isChecked(),
            },
            "farmOptions": {
                "dailyQuests": self.daily_quests_checkbox.isChecked(),
                "punchCards": self.punch_cards_checkbox.isChecked(),
                "moreActivities": self.more_activities_checkbox.isChecked(),
                "searchPC": self.search_pc_checkbox.isChecked(),
                "searchMobile": self.search_mobile_checkbox.isChecked(),
            },
            "telegram": {"token": self.api_key_lineedit.text(), "chatID": self.chat_id_lineedit.text()},
        }
        with open(f"{Path(__file__).parent.parent}/config.json", "w") as f:
            f.write(json.dumps(self.config, indent=4))

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Microsoft Rewards Farmer"))
        self.accounts_label.setText(_translate("MainWindow", "**Accounts:**"))
        self.open_accounts_button.setText(_translate("MainWindow", "Open"))
        self.creator_label.setText(_translate("MainWindow", "By [Farshad](https://github.com/farshadz1997/)"))
        self.title_label.setText(_translate("MainWindow", "Microsoft Rewards Farmer"))
        self.set_time_label.setText(_translate("MainWindow", "**Set time**:"))
        self.timeEdit.setDisplayFormat(_translate("MainWindow", "hh:mm AP"))
        self.active_timer_checkbox.setText(_translate("MainWindow", "Active timer"))
        self.global_options_groupbox.setTitle(_translate("MainWindow", "Global options"))
        self.headless_checkbox.setText(_translate("MainWindow", "Headless"))
        self.session_checkbox.setText(_translate("MainWindow", "Session"))
        self.fast_mode_checkbox.setText(_translate("MainWindow", "Fast mode"))
        self.save_errors.setText(_translate("MainWindow", "Save errors"))
        self.shutdown_system.setText(_translate("MainWindow", "Shutdown PC"))
        self.farm_options_groupbox.setTitle(_translate("MainWindow", "Farm options"))
        self.daily_quests_checkbox.setText(_translate("MainWindow", "Daily quests"))
        self.punch_cards_checkbox.setText(_translate("MainWindow", "Punch cards"))
        self.more_activities_checkbox.setText(_translate("MainWindow", "More Activities"))
        self.search_pc_checkbox.setText(_translate("MainWindow", "Search (PC)"))
        self.search_mobile_checkbox.setText(_translate("MainWindow", "Search (Mobile)"))
        self.telegram_groupbox.setTitle(_translate("MainWindow", "Send report to Telegram"))
        self.api_key_label.setText(_translate("MainWindow", "Token:"))
        self.chat_id_label.setText(_translate("MainWindow", "Chat ID:"))
        self.send_to_telegram_checkbox.setText(_translate("MainWindow", "Send to Telegram"))
        self.progress_info_groupbox.setTitle(_translate("MainWindow", "Progress info"))
        self.start_button.setText(_translate("MainWindow", "Start"))
        self.stop_button.setText(_translate("MainWindow", "Stop"))
        self.number_of_accounts_label.setText(_translate("MainWindow", "Number of accounts:"))
        self.finished_accounts_label.setText(_translate("MainWindow", "Finished accounts:"))
        self.locked_accounts_label.setText(_translate("MainWindow", "Locked accounts:"))
        self.suspended_accounts_label.setText(_translate("MainWindow", "Suspended accounts:"))
        self.accounts_count.setText(_translate("MainWindow", "-"))
        self.finished_accounts_count.setText(_translate("MainWindow", "-"))
        self.locked_accounts_count.setText(_translate("MainWindow", "-"))
        self.suspended_accounts_count.setText(_translate("MainWindow", "-"))
        self.current_account_label.setText(_translate("MainWindow", "Current account:"))
        self.current_point_label.setText(_translate("MainWindow", "Current point:"))
        self.section_label.setText(_translate("MainWindow", "Section:"))
        self.detail_label.setText(_translate("MainWindow", "Detail:"))
        self.current_account.setText(_translate("MainWindow", "-"))
        self.current_point.setText(_translate("MainWindow", "-"))
        self.section.setText(_translate("MainWindow", "-"))
        self.detail.setText(_translate("MainWindow", "-"))
