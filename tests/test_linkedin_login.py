"""LinkedIn login flow against fake LinkedIn pages (no network).

Every https://www.linkedin.com request is answered by FakeLinkedIn below, which mimics the
page variants LinkedIn serves: the normal login form, "Welcome back" (remembered account,
password only), wrong-password errors and security checkpoints.
"""
import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest

playwright = pytest.importorskip("playwright.async_api")

from gt_linkedin_scraper.core.config import settings  # noqa: E402
from gt_linkedin_scraper.core.exceptions import LinkedInCheckpointError, LoginFailed  # noqa: E402
from gt_linkedin_scraper.crawler import linkedin  # noqa: E402

PASSWORD = "right-password"

LOGIN_SCRIPT = """
<script>
function submitLogin() {
  const user = document.querySelector('#username')?.value || 'remembered';
  const pass = document.querySelector('#password').value;
  location.href = '/login-submit?u=' + encodeURIComponent(user) + '&p=' + encodeURIComponent(pass);
}
function otherAccount() {
  document.querySelector('#who').remove();
  const u = document.createElement('input');
  u.id = 'username'; u.name = 'session_key';
  document.querySelector('form').prepend(u);
}
</script>
"""

FORM_PAGE = LOGIN_SCRIPT + """
<h1>Sign in</h1>
<form onsubmit="submitLogin(); return false;">
  <input id="username" name="session_key"><input id="password" name="session_password" type="password">
  <button type="submit">Sign in</button>
</form>"""

REMEMBERED_PAGE = LOGIN_SCRIPT + """
<h1>Welcome back</h1>
<form onsubmit="submitLogin(); return false;">
  <div id="who">Gaurav Talele <span>{hint}</span></div>
  <input id="password" name="session_password" type="password">
  <button type="submit">Sign in</button>
</form>
<a href="#" onclick="otherAccount(); return false;">Sign in using another account</a>"""

# LinkedIn's newer page (October 2026): no <form>, random React ids, no name attributes,
# type="button" buttons, and the whole sign-in block rendered twice with one copy hidden.
NEW_LAYOUT_BLOCK = """
<div {hidden}>
  <button type="button">Continue with Google</button>
  <button type="button">Sign in with Apple</button>
  <label>Email or phone <input type="email" id="_R_e3pp{n}_" autocomplete="username"></label>
  <label>Password <input type="password" id="_R_1lpp{n}_"></label>
  <button type="button" aria-label="Show password">show</button>
  <button type="button" onclick="newSubmit(this)"><span><span>Sign in</span></span></button>
</div>"""
NEW_LAYOUT_PAGE = """
<script>
function newSubmit(btn) {
  const box = btn.parentElement;
  const user = box.querySelector('input[type=email]').value;
  const pass = box.querySelector('input[type=password]').value;
  location.href = '/login-submit?u=' + encodeURIComponent(user) + '&p=' + encodeURIComponent(pass);
}
</script>
<h1>Sign in</h1>""" + NEW_LAYOUT_BLOCK.replace("{hidden}", 'style="display:none"').replace("{n}", "a")     + NEW_LAYOUT_BLOCK.replace("{hidden}", "").replace("{n}", "b")

ERROR_PAGE = FORM_PAGE.replace(
    "<h1>Sign in</h1>", '<h1>Sign in</h1><div id="error-for-password">Wrong email or password. Try again.</div>'
)


class FakeLinkedIn:
    def __init__(self, remembered_hint=None, challenge=False, new_layout=False):
        self.remembered_hint = remembered_hint  # shown when the browser has a "remember me" cookie
        self.challenge = challenge
        self.new_layout = new_layout
        self.submissions: list[dict] = []

    async def handle(self, route):
        url = urlparse(route.request.url)
        cookies = route.request.headers.get("cookie", "")
        # Redirects and cookies are done in-page: Chromium doesn't follow 3xx from route.fulfill.
        html = lambda body: route.fulfill(body=body, content_type="text/html")  # noqa: E731
        go = lambda path, extra="": html(f"<script>{extra}location.replace('{path}')</script>")  # noqa: E731

        if url.path.startswith("/feed"):
            return await (html("<h1>Feed</h1>") if "li_at=valid" in cookies else go("/login"))
        if url.path == "/login":
            if self.remembered_hint and "li_rm=" in cookies:
                return await html(REMEMBERED_PAGE.replace("{hint}", self.remembered_hint))
            return await html(NEW_LAYOUT_PAGE if self.new_layout else FORM_PAGE)
        if url.path == "/login-submit":
            self.submissions.append({k: v[0] for k, v in parse_qs(url.query).items()})
            if self.challenge:
                return await go("/checkpoint/challenge/abc")
            if self.submissions[-1].get("p") == PASSWORD:
                return await go("/feed/", "document.cookie='li_at=valid; path=/';")
            return await html(ERROR_PAGE)
        if url.path.startswith("/checkpoint/challenge"):
            return await html("<h1>Let's do a quick security check</h1>")
        await route.fulfill(status=404, body="not found")


@pytest.fixture
def login_env(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "linkedin_username", "gaurav@gmail.com")
    monkeypatch.setattr(settings, "linkedin_password", PASSWORD)
    monkeypatch.setattr(settings, "auth_state_path", str(tmp_path / "auth_state.json"))
    monkeypatch.setattr(linkedin, "DEBUG_DIR", tmp_path / "debug")
    (tmp_path / "debug").mkdir()
    monkeypatch.setattr(linkedin, "LOGIN_TIMEOUT_MS", 5_000)

    async def no_backoff(attempt):
        return None

    monkeypatch.setattr(linkedin.LinkedInCrawler, "_backoff", staticmethod(no_backoff))
    return tmp_path


def run_login(fake: FakeLinkedIn, cookies=None, method="ensure_login"):
    """Runs the crawler in headless Chromium against the fake; returns the final URL."""

    async def main():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            await context.route("https://www.linkedin.com/**", fake.handle)
            if cookies:
                await context.add_cookies(cookies)
            page = await context.new_page()
            try:
                await getattr(linkedin.LinkedInCrawler(context), method)(page)
                return page.url
            finally:
                await browser.close()

    return asyncio.run(main())


def cookie(name, value):
    return {"name": name, "value": value, "domain": ".linkedin.com", "path": "/"}


def test_normal_login_form(login_env):
    fake = FakeLinkedIn()
    assert run_login(fake).endswith("/feed/")
    assert fake.submissions == [{"u": "gaurav@gmail.com", "p": PASSWORD}]
    saved = json.loads((login_env / "auth_state.json").read_text())
    assert any(c["name"] == "li_at" for c in saved)


def test_new_login_page_layout(login_env):
    """Random ids, no <form>, type=button 'Sign in', and a hidden duplicate of the fields."""
    fake = FakeLinkedIn(new_layout=True)
    assert run_login(fake).endswith("/feed/")
    assert fake.submissions == [{"u": "gaurav@gmail.com", "p": PASSWORD}]


def test_expired_session_with_remembered_account_is_the_reported_bug(login_env):
    """Stale cookies used to produce a 'Welcome back' page with no email field
    ('Username field not found'). They are now cleared before logging in."""
    (login_env / "auth_state.json").write_text(json.dumps([cookie("li_at", "expired"), cookie("li_rm", "x")]))
    fake = FakeLinkedIn(remembered_hint="e*****@gmail.com")
    assert run_login(fake).endswith("/feed/")
    assert fake.submissions == [{"u": "gaurav@gmail.com", "p": PASSWORD}]


# The two tests below call _perform_login directly: ensure_login clears cookies first, so in
# practice LinkedIn shows the normal form. These cover the fallback if it still shows "Welcome back".

def test_welcome_back_page_for_the_same_account_only_needs_the_password(login_env):
    fake = FakeLinkedIn(remembered_hint="g*****@gmail.com")
    assert run_login(fake, cookies=[cookie("li_rm", "x")], method="_perform_login").endswith("/feed/")
    assert fake.submissions == [{"u": "remembered", "p": PASSWORD}]


def test_welcome_back_page_for_another_account_switches_account(login_env):
    fake = FakeLinkedIn(remembered_hint="e*****@gmail.com")
    assert run_login(fake, cookies=[cookie("li_rm", "x")], method="_perform_login").endswith("/feed/")
    assert fake.submissions == [{"u": "gaurav@gmail.com", "p": PASSWORD}]


def test_wrong_password_is_not_retried(login_env, monkeypatch):
    monkeypatch.setattr(settings, "linkedin_password", "wrong")
    fake = FakeLinkedIn()
    with pytest.raises(LoginFailed, match="Wrong email or password"):
        run_login(fake)
    assert len(fake.submissions) == 1  # retrying a bad password risks locking the account
    assert any(f.suffix == ".html" for f in (login_env / "debug").iterdir())


def test_security_checkpoint_stops_with_clear_message(login_env):
    fake = FakeLinkedIn(challenge=True)
    with pytest.raises(LinkedInCheckpointError, match="security verification"):
        run_login(fake)
    assert len(fake.submissions) == 1


def test_valid_saved_session_skips_login(login_env):
    (login_env / "auth_state.json").write_text(json.dumps([cookie("li_at", "valid")]))
    fake = FakeLinkedIn()
    assert run_login(fake).endswith("/feed/")
    assert fake.submissions == []


def test_masked_email_matching():
    assert linkedin.masked_email_matches("g*****@gmail.com", "Gaurav@Gmail.com")
    assert not linkedin.masked_email_matches("e*****@gmail.com", "gaurav@gmail.com")
    assert not linkedin.masked_email_matches("g*****@yahoo.com", "gaurav@gmail.com")
