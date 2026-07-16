import PyInstaller.__main__


def main() -> None:
    PyInstaller.__main__.run(
        [
            "src/ruleset_notebook/__main__.py",
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
