import sys
import os
import argparse
import threading
import time
import logging
import io
import ctypes
import string
import random
from urllib.parse import urlparse

CODE_FILE = os.path.join(os.path.dirname(__file__), "auth_code.txt")
USED_CODES_FILE = os.path.join(os.path.dirname(__file__), ".used_codes")

def load_used_codes():
    try:
        if os.path.exists(USED_CODES_FILE):
            with open(USED_CODES_FILE, 'rb') as f:
                return set(f.read().decode('utf-8', errors='ignore').splitlines())
    except:
        pass
    return set()

def mark_code_used(code):
    try:
        with open(USED_CODES_FILE, 'a') as f:
            f.write(code.upper().replace('-', '') + '\n')
        try:
            import subprocess
            subprocess.run(['attrib', '+H', USED_CODES_FILE], check=False)
        except:
            pass
    except:
        pass

USED_CODES = load_used_codes()

def generate_from_seed(seed_full):
    seed_part = seed_full[:2]
    iteration = int(seed_full[2])
    
    random.seed(seed_part)
    result = ''
    for _ in range(iteration):
        result = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    return result

def validate_code(code):
    try:
        code_clean = code.upper().replace('-', '')
        if len(code_clean) != 9:
            return False
        
        if code_clean in USED_CODES:
            return False
        
        seed_full = code_clean[:3]
        generated_part = code_clean[6:]
        
        expected = generate_from_seed(seed_full)
        return expected[-3:] == generated_part
    except:
        return False


print("Starting PyBrowser...")

kernel32 = ctypes.windll.kernel32
kernel32.SetConsoleMode(kernel32.GetStdHandle(-12), 0)

sys.stdout = io.StringIO()
sys.stderr = io.StringIO()

print("PyBrowser ready. Ignore console output below unless crash.")
print("Run with --debug for debug output, --js-debug for JS debug.")

os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging --disable-gpu-logging --enable-logging=0 --v=0 --disable-infobars"
os.environ["QTWEBENGINE_DISABLE_CONSOLE"] = "1"
os.environ["WEBENGINE_DISABLE_LOGGING"] = "1"
os.environ["CHROME_DEVEL_SANDBOX"] = ""
os.environ["ELECTRON_DISABLE_GPU"] = "1"

logging.getLogger("qt").setLevel(logging.CRITICAL)
logging.getLogger("PySide6").setLevel(logging.CRITICAL)

import adblock
from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QToolBar,
    QTabWidget, QWidget, QVBoxLayout, QMessageBox,
    QInputDialog, QDialog, QDialogButtonBox, QLabel
)
from PySide6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineUrlRequestInterceptor, QWebEnginePage
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtNetwork import QNetworkProxy


EASYLIST_PATH = os.path.join(os.path.dirname(__file__), "easylist.txt")

ADBLOCK_CSS = """
(function() {
    const selectors = [
        '[id*="google_ads"]', '[id*="doubleclick"]', '[id*="googlesyndication"]',
        '[class*="google_ads"]', '[class*="doubleclick"]', '[class*="sponsored"]',
        '[class*="advertisement"]', '[id*="advertisement"]', '[class*="ad-container"]',
        '[class*="ad-slot"]', '[class*="ad-unit"]', '[class*="banner-ad"]',
        'iframe[src*="doubleclick"]', 'iframe[src*="googlesyndication"]',
        'iframe[src*="adservice"]', 'ins.adsbygoogle', '[data-ad]',
        '[class*="ads-wrapper"]', '[id*="ads-wrapper"]',
        '[class*="ad-banner"]', '[id*="ad-banner"]', '[class*="sponsored-content"]',
        '[class*="promoted"]', '[class*="promo-"]', 'iframe[src*="ad"]',
        '[class*="-ad"]', '[id*="-ad"]', 'div[class*=" ad "]', 'div[class*=" ad-"]',
        'div[id*=" ad "]', 'div[id*=" ad-"]',
        'nitro-ad', '[id*="nitro-"]', '[class*="nitro-"]',
        'adnxs', '[id*="adnxs"]', '[class*="adnxs"]',
        '[id*="taboola"]', '[class*="taboola"]',
        '[id*="outbrain"]', '[class*="outbrain"]',
        '[id*="criteo"]', '[class*="criteo"]',
        '.ad', '.ads', '.advert', '.advertisement'
    ];
    
    function hideAds() {
        document.querySelectorAll(selectors.join(', ')).forEach(el => {
            el.style.display = 'none !important';
        });
    }
    
    hideAds();
    setTimeout(hideAds, 1000);
    setTimeout(hideAds, 2000);
    setTimeout(hideAds, 3000);
    
    const observer = new MutationObserver(() => { hideAds(); });
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
"""

adblocker = None
HAS_EASYLIST = False

def load_easylist(debug=False):
    global adblocker, HAS_EASYLIST
    try:
        with open(EASYLIST_PATH, 'r', encoding='utf-8') as f:
            rules = [line.strip() for line in f if line.strip() and not line.startswith('!')]
        fs = adblock.FilterSet()
        fs.add_filters(rules)
        adblocker = adblock.Engine(fs, True)
        HAS_EASYLIST = True
        if debug:
            print(f"Loaded {len(rules)} adblock rules")
    except Exception as e:
        if debug:
            print(f"Failed to load easylist: {e}")
        adblocker = None
        HAS_EASYLIST = False


class AdBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, js_debug=False):
        super().__init__()
        self.js_debug = js_debug
        self.blocked_domains = [
            "doubleclick", "googlesyndication", "adservice", "googletagmanager",
            "googleadservices", "moatads", "adnxs", "criteo", "taboola",
            "outbrain", "/ads?", "/ads/", "banner", "sponsor", "advert"
        ]

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        
        if self.js_debug:
            print(f"REQUEST: {url}")
        
        if HAS_EASYLIST and adblocker:
            for req_type in ["script", "image", "stylesheet", "xhr"]:
                try:
                    result = adblocker.check_network_urls(url, url, req_type)
                    if result.matched:
                        if self.js_debug:
                            print(f"BLOCKED: {url}")
                        info.block(True)
                        return
                except:
                    pass
        
        url_lower = url.lower()
        for domain in self.blocked_domains:
            if domain in url_lower:
                info.block(True)
                return


class BrowserTab(QWidget):
    def __init__(self, url, profile, url_callback, title_callback, enable_adblock=True):
        super().__init__()
        self.url_callback = url_callback
        self.title_callback = title_callback
        self.enable_adblock = enable_adblock

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView()
        page = QWebEnginePage(profile)
        self.view.setPage(page)

        if enable_adblock:
            self.view.loadFinished.connect(self._inject_adblock_css)

        self.view.urlChanged.connect(self._url_changed)
        self.view.loadFinished.connect(self._load_finished)

        layout.addWidget(self.view)
        self.setLayout(layout)

        self.view.load(QUrl(url))

    def _inject_adblock_css(self, ok):
        if ok and self.enable_adblock:
            try:
                self.view.page().runJavaScript(ADBLOCK_CSS)
            except:
                pass

    def _url_changed(self, qurl):
        self.url_callback(qurl.toString())

    def _load_finished(self, ok):
        if ok:
            self.title_callback(self.view.page().title())
        else:
            self.title_callback("Failed to load")

    def load_url(self, url):
        self.view.load(QUrl(url))

    def back(self):
        if self.view.history().canGoBack():
            self.view.back()

    def forward(self):
        if self.view.history().canGoForward():
            self.view.forward()

    def reload(self):
        self.view.reload()


class Browser(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.setWindowTitle("PyBrowser")
        self.resize(1200, 800)

        self.profile = QWebEngineProfile.defaultProfile()

        if args.proxy:
            self._setup_proxy(args.proxy)

        if not args.no_adblock:
            self.interceptor = AdBlocker(js_debug=args.js_debug)
            self.profile.setUrlRequestInterceptor(self.interceptor)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self._create_toolbar()
        self.add_tab(args.url)

    def _setup_proxy(self, proxy_url):
        proxy = QNetworkProxy()
        if proxy_url.startswith("socks5://"):
            proxy.setType(QNetworkProxy.Socks5Proxy)
            proxy_url = proxy_url.replace("socks5://", "")
        else:
            proxy.setType(QNetworkProxy.HttpProxy)

        if ":" in proxy_url:
            host, port = proxy_url.rsplit(":", 1)
            proxy.setHostName(host)
            proxy.setPort(int(port))

        QNetworkProxy.setApplicationProxy(proxy)

    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.back_btn = QAction("◀", self)
        self.back_btn.triggered.connect(self.go_back)
        toolbar.addAction(self.back_btn)

        self.forward_btn = QAction("▶", self)
        self.forward_btn.triggered.connect(self.go_forward)
        toolbar.addAction(self.forward_btn)

        self.reload_btn = QAction("⟳", self)
        self.reload_btn.triggered.connect(self.reload_page)
        toolbar.addAction(self.reload_btn)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL...")
        self.url_bar.returnPressed.connect(self.load_page)
        toolbar.addWidget(self.url_bar)

        new_tab_btn = QAction("+", self)
        new_tab_btn.triggered.connect(lambda: self.add_tab("https://www.google.com"))
        toolbar.addAction(new_tab_btn)

    def add_tab(self, url):
        tab = BrowserTab(url, self.profile, self.update_url_bar, self.update_tab_title)
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        self.update_url_bar(url)

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()

    def load_page(self):
        url = self.url_bar.text().strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.tabs.currentWidget().load_url(url)

    def go_back(self):
        self.tabs.currentWidget().back()

    def go_forward(self):
        self.tabs.currentWidget().forward()

    def reload_page(self):
        self.tabs.currentWidget().reload()

    def update_url_bar(self, url):
        self.url_bar.setText(url)

    def update_tab_title(self, title):
        index = self.tabs.currentIndex()
        if index >= 0:
            self.tabs.setTabText(index, title[:30] or "Untitled")


class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setModal(True)
        self.setFixedSize(380, 220)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 25, 30, 25)
        
        title = QLabel("Enter Access Code")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Enter your 9-char code (XXX-XXX-XXX)")
        subtitle.setStyleSheet("font-size: 11px; color: #666;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("XXX-XXX-XXX")
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.setMaxLength(11)
        self.code_input.setStyleSheet("""
            QLineEdit {
                font-size: 24px; padding: 12px 15px;
                border: 2px solid #ddd; border-radius: 8px;
                background: white;
            }
            QLineEdit:focus { border-color: #4a90d9; }
        """)
        self.code_input.setMinimumHeight(50)
        layout.addWidget(self.code_input)
        
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #d93025; font-size: 11px;")
        self.error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.error_label)
        
        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.check_code)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Ok).setText("Access Browser")
        self.button_box.button(QDialogButtonBox.Ok).setStyleSheet("""
            QPushButton {
                background: #4a90d9; color: white;
                padding: 10px 20px; border: none; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background: #357abd; }
        """)
        layout.addWidget(self.button_box)
        
        self.setLayout(layout)
        self.code_input.returnPressed.connect(self.check_code)
    
    def check_code(self):
        code = self.code_input.text().strip()
        
        if validate_code(code):
            mark_code_used(code.upper().replace('-', ''))
            self.accept()
        else:
            self.error_label.setText("Invalid or used code.")
            self.code_input.setText("")
            self.code_input.setFocus()


def parse_args():
    parser = argparse.ArgumentParser(description="PyBrowser")
    parser.add_argument("--url", default="https://www.google.com")
    parser.add_argument("--proxy", type=str)
    parser.add_argument("--no-adblock", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--js-debug", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    def qt_message_handler(msg_type, context, message):
        return
    
    from PySide6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(qt_message_handler)

    app = QApplication(sys.argv)
    app.setApplicationName("PyBrowser")
    app.setApplicationVersion("1.0")
    
    auth = AuthDialog()
    if auth.exec() != QDialog.Accepted:
        sys.exit(0)
    
    load_easylist(debug=args.debug)

    browser = Browser(args)
    browser.show()

    sys.exit(app.exec())
