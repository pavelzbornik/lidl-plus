"""
Lidl Plus api
"""

import base64
import html
import logging
import re
import time
from datetime import datetime, timedelta

import requests

from lidlplus.cache import FileCache, cached
from lidlplus.exceptions import (
    WebBrowserException,
    LoginError,
    LegalTermsException,
    MissingLogin,
)
from lidlplus.html_receipt import parse_html_receipt

# Browser-login dependencies are optional (install with the "auth" extra). They are
# only needed for login(); importing the package for refresh-token use must not require
# them, so keep these inside the try/except — do NOT import seleniumwire at module top.
try:
    from getuseragent import UserAgent
    from oic.oic import Client
    from oic.utils.authn.client import CLIENT_AUTHN_METHOD
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions
    from selenium.webdriver.support.ui import WebDriverWait
    from seleniumwire import webdriver
    from seleniumwire.utils import decode
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.core.os_manager import ChromeType
except ImportError:
    pass


class LidlPlusApi:
    """Lidl Plus api connector"""

    _CLIENT_ID = "LidlPlusNativeClient"
    _AUTH_API = "https://accounts.lidl.com"
    _TICKET_API = "https://tickets.lidlplus.com/api"
    _COUPONS_APP_API = "https://coupons.lidlplus.com/app/api"
    _PROFILE_API = "https://profile.lidlplus.com/api"
    _STORES_API = "https://stores.lidlplus.com/api"
    _CONFIG_API = "https://appgateway.lidlplus.com/configurationapp"
    _APP = "com.lidlplus.app"
    _OS = "iOs"
    # Sent on the unauthenticated stores/countries endpoints, which reject requests
    # without a Lidl Plus client User-Agent.
    _USER_AGENT = "LidlPlus/16.0.0 (iPhone; iOS 17.0; Scale/3.00)"
    # Lidl now tarpits (silently holds open, never responds) requests carrying an
    # implausible app version such as the old "999.99.9" sentinel. A realistic,
    # current app version is required for the API to respond.
    _APP_VERSION = "15.30.0"
    _TIMEOUT = 10

    # Per-endpoint cache lifetimes in seconds; ``None`` means cache forever.
    # A past receipt is immutable, so its detail is cached permanently; volatile
    # data (coupons, ticket lists) gets a short TTL, and near-static data (stores,
    # countries, profile) a long one.
    _CACHE_TTL = {
        "ticket": None,
        "tickets": 5 * 60,
        "coupons": 5 * 60,
        "stores": 24 * 60 * 60,
        "countries": 7 * 24 * 60 * 60,
        "user_info": 24 * 60 * 60,
        "loyalty_id": 24 * 60 * 60,
    }

    def __init__(self, language, country, refresh_token="", cache=False, cache_dir=None):
        self._login_url = ""
        self._code_verifier = ""
        self._refresh_token = refresh_token
        self._expires = None
        self._token = ""
        self._country = country.upper()
        self._language = language.lower()
        # Opt-in local cache. Enabled when cache=True or an explicit cache_dir is
        # given; otherwise every call goes to the network as before.
        self._cache = FileCache(cache_dir) if (cache or cache_dir) else None

    @property
    def refresh_token(self):
        """Lidl Plus api refresh token"""
        return self._refresh_token

    @property
    def token(self):
        """Current token to query api"""
        return self._token

    def _register_oauth_client(self):
        if self._login_url:
            return self._login_url
        client = Client(client_authn_method=CLIENT_AUTHN_METHOD, client_id=self._CLIENT_ID)
        client.provider_config(self._AUTH_API)
        code_challenge, self._code_verifier = client.add_code_challenge()
        args = {
            "client_id": client.client_id,
            "response_type": "code",
            "scope": ["openid profile offline_access lpprofile lpapis"],
            "redirect_uri": f"{self._APP}://callback",
            **code_challenge,
        }
        auth_req = client.construct_AuthorizationRequest(request_args=args)
        self._login_url = auth_req.request(client.authorization_endpoint)
        return self._login_url

    def _init_chrome(self, headless=True):
        user_agent = UserAgent(self._OS.lower()).Random()
        logging.getLogger("WDM").setLevel(logging.NOTSET)
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("headless")
        options.add_experimental_option("mobileEmulation", {"userAgent": user_agent})
        # Prefer Selenium Manager (built into selenium >= 4.6): it resolves a matching
        # chromedriver automatically and avoids the slow/flaky webdriver_manager
        # download that can hang or fetch a wrong-arch binary.
        try:
            return webdriver.Chrome(options=options)
        except Exception:  # pylint: disable=broad-except
            pass
        # Fallback: legacy webdriver_manager for Chrome / Edge / Chromium.
        for chrome_type in [ChromeType.GOOGLE, ChromeType.MSEDGE, ChromeType.CHROMIUM]:
            try:
                service = Service(ChromeDriverManager(chrome_type=chrome_type).install())
                return webdriver.Chrome(service=service, options=options)
            except AttributeError:
                continue
        raise WebBrowserException("Unable to find a suitable Chrome driver")

    def _init_firefox(self, headless=True):
        user_agent = UserAgent(self._OS.lower()).Random()
        logging.getLogger("WDM").setLevel(logging.NOTSET)
        options = webdriver.FirefoxOptions()
        if headless:
            options.headless = True
        profile = webdriver.FirefoxProfile()
        profile.set_preference("general.useragent.override", user_agent)
        return webdriver.Firefox(
            executable_path=GeckoDriverManager().install(),
            firefox_binary="/usr/bin/firefox",
            options=options,
            firefox_profile=profile,
        )

    def _get_browser(self, headless=True):
        try:
            return self._init_chrome(headless=headless)
        # pylint: disable=broad-except
        except Exception as exc1:
            try:
                return self._init_firefox(headless=headless)
            except Exception as exc2:
                raise WebBrowserException from exc1 and exc2

    def _auth(self, payload):
        default_secret = base64.b64encode(f"{self._CLIENT_ID}:secret".encode()).decode()
        headers = {
            "Authorization": f"Basic {default_secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        kwargs = {"headers": headers, "data": payload, "timeout": self._TIMEOUT}
        response = requests.post(f"{self._AUTH_API}/connect/token", **kwargs).json()
        if "expires_in" not in response:
            print("[ERROR] Unexpected token response:", response)
            raise KeyError("'expires_in' not in token response")
        self._expires = datetime.utcnow() + timedelta(seconds=response["expires_in"])
        self._token = response["access_token"]
        self._refresh_token = response["refresh_token"]

    def _renew_token(self):
        payload = {"refresh_token": self._refresh_token, "grant_type": "refresh_token"}
        return self._auth(payload)

    def _authorization_code(self, code):
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{self._APP}://callback",
            "code_verifier": self._code_verifier,
        }
        return self._auth(payload)

    @property
    def _register_link(self):
        args = {
            "Country": self._country,
            "language": f"{self._language}-{self._country}",
        }
        params = "&".join([f"{key}={value}" for key, value in args.items()])
        return f"{self._register_oauth_client()}&{params}"

    @staticmethod
    def _accept_legal_terms(browser, wait, accept=True):
        wait.until(expected_conditions.visibility_of_element_located((By.ID, "checkbox_Accepted"))).click()
        if not accept:
            title = browser.find_element(By.TAG_NAME, "h2").text
            raise LegalTermsException(title)
        browser.find_element(By.TAG_NAME, "button").click()

    def _parse_code(self, browser, wait, accept_legal_terms=True):
        for request in reversed(browser.requests):
            if f"{self._AUTH_API}/connect" not in request.url:
                continue
            location = request.response.headers.get("Location", "")
            if "legalTerms" in location:
                self._accept_legal_terms(browser, wait, accept=accept_legal_terms)
                return self._parse_code(browser, wait, False)
            if code := re.findall("code=([0-9A-F]+)", location):
                return code[0]
        return ""

    def _click(self, browser, button, request=""):
        del browser.requests
        browser.backend.storage.clear_requests()
        browser.find_element(*button).click()
        self._check_input_error(browser)
        if request and browser.wait_for_request(request, 10):
            self._check_input_error(browser)

    @staticmethod
    def _check_input_error(browser):
        if errors := browser.find_elements(By.CLASS_NAME, "input-error-message"):
            for error in errors:
                if error.text:
                    raise LoginError(error.text)

    def _check_login_error(self, browser):
        response = browser.wait_for_request(f"{self._AUTH_API}/Account/Login.*", 10).response
        body = html.unescape(decode(response.body, response.headers.get("Content-Encoding", "identity")).decode())
        if error := re.findall('app-errors="\\{[^:]*?:.(.*?).}', body):
            raise LoginError(error[0])

    def _check_2fa_auth(self, browser, wait, verify_mode="phone", verify_token_func=None):
        if verify_mode not in ["phone", "email"]:
            raise ValueError(f'Unknown 2fa-mode "{verify_mode}" - Only "phone" or "email" supported')
        req = browser.wait_for_request(f"{self._AUTH_API}/Account/Login.*", 10)
        response = getattr(req, "response", None)
        location = None
        if response is not None and hasattr(response, "headers"):
            location = response.headers.get("Location")
        if response is None or location is None:
            # If no response or Location header, assume 2FA is not required or login failed
            return
        if "/connect/authorize/callback" not in location:
            element = wait.until(expected_conditions.visibility_of_element_located((By.CLASS_NAME, verify_mode)))
            element.find_element(By.TAG_NAME, "button").click()
            verify_code = verify_token_func()
            browser.find_element(By.NAME, "VerificationCode").send_keys(verify_code)
            self._click(browser, (By.CLASS_NAME, "role_next"))

    def login(self, email, password, **kwargs):
        """Simulate app auth with updated selectors for new Lidl Plus login form."""
        browser = self._get_browser(headless=kwargs.get("headless", True))
        browser.get(self._register_link)
        wait = WebDriverWait(browser, 20)
        # Wait for the primary login button and click it to show the email/password form
        wait.until(
            expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, "button[data-testid='button-primary']"))
        ).click()
        # Wait for the email input and enter the email
        wait.until(
            expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, "input[data-testid='input-email']"))
        ).send_keys(email)
        # Wait for the password input and enter the password.
        # Lidl renamed this field's testid to "login-input-password"; keep the old
        # "input-password" as a fallback in case the form flips back.
        password_selector = "input[data-testid='login-input-password'], input[data-testid='input-password']"
        wait.until(expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, password_selector))).send_keys(
            password
        )
        # Click the primary login button to submit
        browser.find_element(By.CSS_SELECTOR, "button[data-testid='button-primary']").click()

        # Wait for a browser log message containing the protocol (language-agnostic), or timeout after 20 seconds
        start_time = time.monotonic()
        found = False
        while time.monotonic() - start_time < 20:
            for entry in browser.get_log("browser"):
                msg = entry.get("message", "")
                if "com.lidlplus.app://callback?code=" in msg:
                    found = True
                    break
            if found:
                break
            time.sleep(0.5)
        if not found:
            print("[WARNING] Did not find the expected browser log message for callback within 20 seconds.")
        self._check_login_error(browser)
        self._check_2fa_auth(
            browser,
            wait,
            kwargs.get("verify_mode", "phone"),
            kwargs.get("verify_token_func"),
        )
        # Look for the error message in browser logs
        code = None
        for entry in browser.get_log("browser"):
            msg = entry.get("message", "")
            if "com.lidlplus.app://callback?code=" in msg:
                match = re.search(r"code=([0-9A-F]+)", msg)
                if match:
                    code = match.group(1)
                    break
        if not code:
            # fallback to old method if not found in logs
            browser.wait_for_request(f"{self._AUTH_API}/connect.*")
            code = self._parse_code(browser, wait, accept_legal_terms=kwargs.get("accept_legal_terms", True))
        if not code:
            print(
                "[ERROR] No authorization code found after login. "
                "The login may have failed or the form flow has changed."
            )
            raise LoginError(
                "No authorization code found after login. Check credentials, 2FA, or if the login form has changed."
            )
        print(f"[DEBUG] Authorization code: {code}")
        self._authorization_code(code)

    def _default_headers(self):
        if (not self._token and self._refresh_token) or datetime.utcnow() >= self._expires:
            self._renew_token()
        if not self._token:
            raise MissingLogin("You need to login!")
        return {
            "Authorization": f"Bearer {self._token}",
            "App-Version": self._APP_VERSION,
            "Operating-System": self._OS,
            "App": "com.lidl.eci.lidl.plus",
            "Accept-Language": self._language,
        }

    def tickets(self, only_favorite=False):
        """
        Get a list of all tickets.

        :param onlyFavorite: A boolean value indicating whether to only retrieve favorite tickets.
            If set to True, only favorite tickets will be returned.
            If set to False (the default), all tickets will be retrieved.
        :type onlyFavorite: bool
        """

        def _fetch():
            url = f"{self._TICKET_API}/v2/{self._country}/tickets"
            kwargs = {"headers": self._default_headers(), "timeout": self._TIMEOUT}
            first = requests.get(f"{url}?pageNumber=1&onlyFavorite={only_favorite}", **kwargs).json()
            result = first["tickets"]
            for i in range(2, int(first["totalCount"] / first["size"] + 2)):
                result += requests.get(f"{url}?pageNumber={i}", **kwargs).json()["tickets"]
            return result

        key = f"tickets:{self._country}:{only_favorite}"
        return cached(self._cache, key, self._CACHE_TTL["tickets"], _fetch)

    def ticket(self, ticket_id):
        """Get full data of single ticket by id"""

        def _fetch():
            kwargs = {"headers": self._default_headers(), "timeout": self._TIMEOUT}
            url = f"{self._TICKET_API}/v3/{self._country}/tickets/{ticket_id}"
            receipt_json = requests.get(url, **kwargs).json()
            return parse_html_receipt(
                date=receipt_json["date"],
                html_receipt=receipt_json["htmlPrintedReceipt"],
            )

        key = f"ticket:{self._country}:{ticket_id}"
        return cached(self._cache, key, self._CACHE_TTL["ticket"], _fetch)

    def coupon_promotions_v1(self):
        """Get list of all coupon promotions.

        Uses the current app endpoint ``/app/api/v3/promotionslist`` (the method name is
        kept for backwards compatibility). Returns
        ``{"sections": [{"name": ..., "promotions": [...]}]}``.
        """

        def _fetch():
            url = f"{self._COUPONS_APP_API}/v3/promotionslist"
            kwargs = {"headers": {**self._default_headers(), "Country": self._country}, "timeout": self._TIMEOUT}
            return requests.get(url, **kwargs).json()

        return cached(self._cache, self._coupons_cache_key(), self._CACHE_TTL["coupons"], _fetch)

    def _coupons_cache_key(self):
        return f"coupons:{self._country}"

    def _invalidate_coupons(self):
        """Drop the cached coupon list after a change so the next read is fresh."""
        if self._cache is not None:
            self._cache.delete(self._coupons_cache_key())

    def activate_coupon_promotion_v1(self, promotion_id):
        """Activate a single coupon promotion by id (``/app/api/v2/promotions/{id}/activation``)."""
        url = f"{self._COUPONS_APP_API}/v2/promotions/{promotion_id}/activation"
        kwargs = {"headers": {**self._default_headers(), "Country": self._country}, "timeout": self._TIMEOUT}
        response = requests.post(url, **kwargs)
        self._invalidate_coupons()
        return response

    def coupons(self):
        """Get list of all coupon promotions.

        The legacy v2 endpoint (``coupons.lidlplus.com/api/v2/{country}``) was retired
        by Lidl (404); this delegates to the current promotions API. Returns
        ``{"sections": [{"name": ..., "promotions": [...]}]}``.
        """
        return self.coupon_promotions_v1()

    def activate_coupon(self, coupon_id):
        """Activate single coupon by id (promotions API)."""
        return self.activate_coupon_promotion_v1(coupon_id)

    def deactivate_coupon(self, coupon_id):
        """Deactivate single coupon by id (``/app/api/v2/promotions/{id}/activation``)."""
        url = f"{self._COUPONS_APP_API}/v2/promotions/{coupon_id}/activation"
        kwargs = {"headers": {**self._default_headers(), "Country": self._country}, "timeout": self._TIMEOUT}
        response = requests.delete(url, **kwargs)
        self._invalidate_coupons()
        return response

    def user_info(self):
        """Get the OpenID Connect profile claims for the logged-in user.

        Served by ``accounts.lidl.com/connect/userinfo``; includes ``sub`` (a stable
        per-account identifier), ``name``, ``email``, ``phone_number`` and more.
        """

        def _fetch():
            url = f"{self._AUTH_API}/connect/userinfo"
            kwargs = {"headers": self._default_headers(), "timeout": self._TIMEOUT}
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response.json()

        return cached(self._cache, f"user_info:{self._country}", self._CACHE_TTL["user_info"], _fetch)

    def loyalty_id(self):
        """Get your loyalty card ID (the number behind your in-store Lidl Plus barcode).

        Served as plain text by ``profile.lidlplus.com/api/v1/{country}/loyalty``.
        (The package previously used a wrong ``/profile/api/...`` path that 404'd.)
        """

        def _fetch():
            url = f"{self._PROFILE_API}/v1/{self._country}/loyalty"
            kwargs = {"headers": self._default_headers(), "timeout": self._TIMEOUT}
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response.text

        return cached(self._cache, f"loyalty_id:{self._country}", self._CACHE_TTL["loyalty_id"], _fetch)

    def stores(self):
        """Get the list of stores for the configured country.

        Public endpoint (no authentication) on ``stores.lidlplus.com/api/v4/{country}``;
        returns store key, name, address and geo-location.
        """

        def _fetch():
            url = f"{self._STORES_API}/v4/{self._country}"
            kwargs = {"headers": {"User-Agent": self._USER_AGENT}, "timeout": self._TIMEOUT}
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response.json()

        return cached(self._cache, f"stores:{self._country}", self._CACHE_TTL["stores"], _fetch)

    def countries(self):
        """Get the list of supported Lidl Plus countries (public, no authentication)."""

        def _fetch():
            url = f"{self._CONFIG_API}/v3/countries"
            kwargs = {"headers": {"User-Agent": self._USER_AGENT}, "timeout": self._TIMEOUT}
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response.json()

        return cached(self._cache, "countries", self._CACHE_TTL["countries"], _fetch)

    def clear_cache(self):
        """Remove all locally cached API responses (no-op if caching is disabled)."""
        if self._cache is not None:
            self._cache.clear()
