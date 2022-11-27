from src.ui import UserInterface, QtWidgets
import sys

def main():
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UserInterface()
    ui.setupUi(MainWindow)
    MainWindow.show()
    ui.get_config()
    ui.set_config()
    sys.exit(app.exec_())
    
if __name__ == "__main__":
    main()