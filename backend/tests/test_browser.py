"""Real Chromium, HTTPS and PostgreSQL; NVIDIA alone is a named mock."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from conftest import PASSWORD
from cryptography.fernet import Fernet
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import create_engine, text

from mgai.models import Base


@pytest.fixture(scope="module")
def browser_server(database_urls, tmp_path_factory):
    root = tmp_path_factory.mktemp("mgai-https")
    engine = create_engine(database_urls[1])
    with engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE "
                + ",".join('"' + t.name + '"' for t in Base.metadata.sorted_tables)
                + " RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"https://127.0.0.1:{port}"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(root / "key.pem"),
            "-out",
            str(root / "cert.pem"),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    env = {
        **os.environ,
        "MGAI_TEST_DATABASE_URL": database_urls[0],
        "MGAI_TEST_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "MGAI_TEST_ORIGIN": base,
    }
    backend = Path(__file__).resolve().parents[1]
    with (root / "server.log").open("w") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "browser_server:app",
                "--app-dir",
                str(backend / "tests"),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--ssl-keyfile",
                str(root / "key.pem"),
                "--ssl-certfile",
                str(root / "cert.pem"),
                "--no-access-log",
            ],
            cwd=backend,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(verify=False) as client:
                for _ in range(150):
                    if proc.poll() is not None:
                        pytest.fail((root / "server.log").read_text())
                    try:
                        if client.get(base + "/ready").status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.1)
                else:
                    pytest.fail("Browser server did not start")
            yield base
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@pytest.fixture
def page(browser_server):
    with sync_playwright() as p:
        executable = os.getenv("CHROMIUM_EXECUTABLE") or shutil.which("chromium")
        browser = p.chromium.launch(
            **({"executable_path": executable} if executable else {}),
            args=["--no-sandbox"],
        )
        context = browser.new_context(
            ignore_https_errors=True, viewport={"width": 1440, "height": 1050}
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(browser_server)
        page.get_by_label("E-posta", exact=True).fill("admin@example.test")
        page.get_by_label("Parola", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Giriş yap", exact=True).click()
        expect(page.get_by_role("heading", name="Merhaba, Test")).to_be_visible()
        yield page
        assert not errors, errors
        context.close()
        browser.close()


def test_desktop_workspace_model_generation_and_usage(page):
    page.get_by_role("button", name="Çalışma alanları", exact=True).click()
    page.get_by_role("button", name="Yeni çalışma alanı", exact=True).click()
    page.get_by_label("Proje adı", exact=True).fill("ParaRadar Test")
    page.get_by_label("Kısa açıklama").fill("Bağımsız test alanı")
    page.get_by_role("button", name="Oluştur", exact=True).click()
    expect(
        page.get_by_role("heading", name="ParaRadar Test", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="AI stüdyosu", exact=True).click()
    page.get_by_label("Çalışma alanı", exact=True).select_option(label="ParaRadar Test")
    page.get_by_label("Metin modeli", exact=True).select_option(
        "nvidia/llama-3.1-nemotron-70b-instruct"
    )
    page.get_by_label("İsteğiniz").fill("Türkçe bir eğitim video senaryosu yaz.")
    page.get_by_role("button", name="Üret", exact=True).click()
    expect(page.locator(".message.assistant")).to_contain_text(
        "gerçek NVIDIA üretimi değildir", timeout=15000
    )
    expect(page.locator(".job-status")).to_contain_text("Tamamlandı")
    page.get_by_role("button", name="Kullanım ve krediler", exact=True).click()
    expect(page.locator(".token-bars")).to_contain_text("80")
    expect(page.locator(".token-bars")).to_contain_text("30")
    expect(page.get_by_text("Ödeme sağlayıcısı bekleniyor")).to_be_visible()


def test_admin_invites_and_user_isolation(page):
    page.get_by_role("button", name="Yönetim paneli", exact=True).click()
    page.get_by_label("E-posta", exact=True).fill("browser-member@example.test")
    page.get_by_role("button", name="Davet oluştur", exact=True).click()
    expect(page.get_by_label("Davet kodu", exact=True)).to_be_visible()
    token = page.get_by_label("Davet kodu", exact=True).input_value()
    page.get_by_role("button", name="Oturumu kapat", exact=True).click()
    page.get_by_role("button", name="Hesap oluştur", exact=True).click()
    page.get_by_label("Adınız", exact=True).fill("Browser Member")
    page.get_by_label("E-posta", exact=True).fill("browser-member@example.test")
    page.get_by_label("Parola", exact=True).fill(PASSWORD)
    page.get_by_label("Davet kodu", exact=True).fill(token)
    page.get_by_role("button", name="Hesap oluştur", exact=True).click()
    expect(page.get_by_role("heading", name="Merhaba, Browser")).to_be_visible()
    expect(page.get_by_role("button", name="Yönetim paneli", exact=True)).to_have_count(
        0
    )
    page.get_by_role("button", name="Çalışma alanları", exact=True).click()
    expect(
        page.get_by_role("heading", name="İlk çalışma alanım", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="ParaRadar Test", exact=True)
    ).to_have_count(0)


def test_mobile_navigation_layout_and_screenshot(page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Menüyü aç", exact=True).click()
    page.get_by_role("button", name="AI stüdyosu", exact=True).click()
    expect(page.get_by_role("heading", name="AI stüdyosu", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    expect(page.get_by_label("İsteğiniz")).to_be_visible()
    page.screenshot(
        path="/tmp/mgai-mobile-preview.png", full_page=True, animations="disabled"
    )


def test_dashboard_screenshot_and_no_private_key_in_browser(page):
    page.screenshot(
        path="/tmp/mgai-dashboard-preview.png", full_page=True, animations="disabled"
    )
    text = page.locator("body").inner_text()
    assert "test-provider-api-key" not in text and "test-password-only-2026" not in text
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
