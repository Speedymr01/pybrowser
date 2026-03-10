import tkinter as tk
from tkinter import ttk
import webview
import argparse
import threading
import time


# SAFER ADBLOCK SCRIPT — avoids breaking sites
ADBLOCK_JS = r"""
function safeRemoveAds() {
    // Remove known ad containers
    const knownSelectors = `
        iframe[src*="doubleclick"],
        iframe[src*="googlesyndication"],
        iframe[src*="adservice"],
        .advert,
        .advertisement,
        .ads,
        .ad-container,
        .ad-slot,
        .ad-unit,
        .banner-ad,
        .sponsored,
        .sponsor,
        .promo-banner
    `;
    document.querySelectorAll(knownSelectors).forEach(e => e.remove());

    // Word-boundary ad detection (avoids removing "header", "loader", etc.)
    const maybeAds = document.querySelectorAll("[id], [class]");
    maybeAds.forEach(el => {
        const id = (el.id || "").toLowerCase();
        const cls = (el.className || "").toLowerCase();

        const patterns = [
            /\bad\b/,
            /\bads\b/,
            /\badvert\b/,
            /\badvertisement\b/,
            /\bbanner\b/
        ];

        if (patterns.some(p => p.test(id)) || patterns.some(p => p.test(cls))) {
            el.remove();
        }
    });
}

// Run once
safeRemoveAds();

// Keep cleaning dynamically
const observer = new MutationObserver(safeRemoveAds);
observer.observe(document.body, { childList: true, subtree: true });
"""


class BrowserApp:
    def __init__(self, start_url):
        self.root = tk.Tk()
        self.root.title("Tk + PyWebView Browser")
        self.root.geometry("1100x750")

        # --- Top bar ---
        top = ttk.Frame(self.root)
        top.pack(side="top", fill="x")

        self.url_var = tk.StringVar(value=start_url)

        ttk.Button(top, text="◀", width=3, command=self.go_back).pack(side="left", padx=3)
        ttk.Button(top, text="▶", width=3, command=self.go_forward).pack(side="left", padx=3)
        ttk.Button(top, text="⟳", width=3, command=self.reload_page).pack(side="left", padx=3)

        url_entry = ttk.Entry(top, textvariable=self.url_var)
        url_entry.pack(side="left", fill="x", expand=True, padx=5)
        url_entry.bind("<Return>", self.load_page)

        ttk.Button(top, text="Go", command=self.load_page).pack(side="left", padx=5)

        # Create the webview window
        self.browser = webview.create_window("Browser", start_url)

        # Start PyWebView with callback
        webview.start(self._inject_adblock, self.browser)

    # --- Adblock injection callback ---
    def _inject_adblock(self, window):
        thread = threading.Thread(target=self._adblock_loop, daemon=True)
        thread.start()

    def _adblock_loop(self):
        while True:
            try:
                self.browser.evaluate_js(ADBLOCK_JS)
            except:
                pass
            time.sleep(1)

    # --- Navigation functions ---
    def load_page(self, event=None):
        url = self.url_var.get().strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_var.set(url)
        self.browser.load_url(url)

    def go_back(self):
        try:
            self.browser.go_back()
        except:
            pass

    def go_forward(self):
        try:
            self.browser.go_forward()
        except:
            pass

    def reload_page(self):
        try:
            self.browser.reload()
        except:
            pass


def parse_args():
    parser = argparse.ArgumentParser(description="Tk + PyWebView Browser")
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.python.org",
        help="Starting URL for the browser"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = BrowserApp(args.url)
