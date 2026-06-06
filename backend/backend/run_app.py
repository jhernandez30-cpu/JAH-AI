import platform
import sys
from pathlib import Path


# Work around slow/broken Windows WMI responses during Streamlit startup.
platform.system = lambda: "Windows"
platform.machine = lambda: "AMD64"
platform.win32_ver = lambda *args, **kwargs: ("", "", "", "")


def main():
    app_path = Path(__file__).resolve().with_name("app.py")
    sys.argv = ["streamlit", "run", str(app_path), *sys.argv[1:]]
    from streamlit.web.cli import main as streamlit_main

    raise SystemExit(streamlit_main())


if __name__ == "__main__":
    main()
