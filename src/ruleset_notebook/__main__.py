import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Ruleset Notebook")
    window.setCentralWidget(QLabel("Ruleset Notebook"))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
