import PyInstaller.__main__


def main() -> None:
    PyInstaller.__main__.run(
        [
            "app.py",
            "--name",
            "RulesetNotebook",
            "--onedir",
            "--windowed",
            "--clean",
            "--noconfirm",
            "--noupx",
        ]
    )


if __name__ == "__main__":
    main()
