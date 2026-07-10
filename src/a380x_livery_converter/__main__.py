import sys


def main() -> None:
    if len(sys.argv) > 1:
        from a380x_livery_converter.cli import app
        app()
    else:
        from a380x_livery_converter.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
