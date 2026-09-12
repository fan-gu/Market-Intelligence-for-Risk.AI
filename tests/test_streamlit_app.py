from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_all_dashboard_pages_render_without_exceptions():
    pages = [
        "Dashboard",
        "VaR",
        "P&L",
        "Sensitivities",
        "Stress",
        "Scenario Lab",
        "Controls",
        "Architecture & Governance",
        "Ask MIRAI",
    ]
    for page in pages:
        app = AppTest.from_file(Path(__file__).parents[1] / "streamlit_app.py", default_timeout=45)
        app.session_state["v29_active_page"] = page
        app.run()
        assert not app.exception, f"{page}: {[item.value for item in app.exception]}"
        assert app.header, f"{page} rendered a blank page"



def test_navigation_reruns_do_not_render_blank_pages():
    entrypoint = Path(__file__).parents[1] / "streamlit_app.py"
    app = AppTest.from_file(entrypoint, default_timeout=45).run()
    assert app.header[0].value == "Dashboard"
    app.session_state["v29_active_page"] = "VaR"
    app.run()
    assert app.header[0].value == "VaR"
    app.session_state["v29_active_page"] = "P&L"
    app.run()
    assert app.header[0].value.startswith("P&L")
