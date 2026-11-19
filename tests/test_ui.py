"""Optional real-browser flow; RUN_UI_TESTS=1 pytest tests/test_ui.py."""

import os
import re
from pathlib import Path
from threading import Thread

import pytest
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_UI_TESTS") != "1", reason="Set RUN_UI_TESTS=1 and install the ui extra/browser."
)


def test_user_and_admin_flows_at_desktop_and_mobile_sizes(demo):
    playwright = pytest.importorskip("playwright.sync_api")
    demo.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("a-long-test-password")
    demo.config["WTF_CSRF_ENABLED"] = True
    server = make_server("127.0.0.1", 0, demo, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=os.getenv("RAIL_BROWSER") or None,
                args=["--no-sandbox"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, locale="pl-PL")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            base = f"http://127.0.0.1:{server.server_port}"
            page.goto(base)
            page.screenshot(path=str(output / "home-desktop.png"), full_page=True)
            page.locator("[name=start]").select_option("1")
            page.locator("[name=end]").select_option("5")
            page.locator("[name=date]").fill("2026-01-10")
            page.locator("[name=transfers]").select_option("0")
            page.get_by_role("button", name=re.compile("Znajdź połączenie")).click()
            page.get_by_role("link", name="Zobacz podróż →").first.click()
            assert page.locator(".continuation").count() == 1
            assert page.locator(".stock-view").nth(1).locator(".wagon-tabs button").count() == 5
            page.locator(".stock-view").nth(1).locator(".wagon-tabs button").last.click()
            assert (
                "200" in page.locator(".stock-view").nth(1).locator(".wagon-caption").inner_text()
            )
            page.screenshot(path=str(output / "journey.png"), full_page=True)
            page.goto(base + "/admin")
            page.locator("[name=password]").fill("a-long-test-password")
            page.get_by_role("button", name="Zaloguj", exact=True).click()
            assert page.url.endswith("/admin")
            url = base + "/admin/laczenia?date=2026-01-10&station=4"
            page.goto(url)
            page.screenshot(path=str(output / "couplings.png"), full_page=True)
            page.on("dialog", lambda dialog: dialog.accept())
            card = page.locator("article.card").filter(has_text="2026-01-10")
            assert card.count() == 1
            card.get_by_role("button", name="Usuń", exact=True).click()
            page.goto(url)
            for selector, part in [
                ("source_a", "11:00 · IC 100"),
                ("source_b", "10:50 · IC 200"),
                ("target", "11:15 · IC 300"),
            ]:
                value = (
                    page.locator(f"[name={selector}] option")
                    .filter(has_text=part)
                    .get_attribute("value")
                )
                page.locator(f"[name={selector}]").select_option(value)
            page.get_by_role("button", name="Połącz oba pociągi").click()
            assert "Połączono oba składy" in page.locator(".notice.success").inner_text()
            page.goto(base + "/admin/trasy/nowa")
            page.locator("[name=number]").fill("900")
            page.locator("[name=name]").fill("Nowa trasa testowa")
            page.locator("[name=station_id]").nth(0).select_option("1")
            page.locator("[name=station_id]").nth(1).select_option("5")
            for selector in ["arrival", "departure"]:
                page.locator(f"[name={selector}]").nth(0).fill("23:30")
                page.locator(f"[name={selector}]").nth(1).fill("25:15")
            page.locator("[name=dates]").fill("2026-01-11")
            page.get_by_role("button", name="Zapisz trasę").click()
            assert page.url.endswith("/admin/trasy")
            assert "Nowa trasa testowa" in page.locator("table").inner_text()
            page.locator("tr").filter(has_text="Nowa trasa testowa").get_by_role(
                "button", name="Usuń", exact=True
            ).click()
            assert "Nowa trasa testowa" not in page.locator("table").inner_text()
            page.goto(base)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.screenshot(path=str(output / "home-mobile.png"), full_page=True)
            assert not errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
