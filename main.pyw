from src.ui import UserInterface, QtWidgets
from pathlib import Path
from datetime import datetime
import sys

def main():
    try:
        app = QtWidgets.QApplication(sys.argv)
        MainWindow = QtWidgets.QMainWindow()
        ui = UserInterface()
        ui.setupUi(MainWindow)
        MainWindow.show()
        ui.get_config()
        ui.set_config()
        sys.exit(app.exec_())
    except Exception as e:
        with open(f"{Path.cwd()}/errors.txt", "a") as f:
            f.write(f"\n-------------------{datetime.now()}-------------------\r\n")
            f.write("CRASH_ERR:'\r\n")
            f.write(f"{str(e)}\n")
    
if __name__ == "__main__":
    main()