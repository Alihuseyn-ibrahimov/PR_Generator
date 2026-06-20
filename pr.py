"""
╔══════════════════════════════════════════════════════════════╗
║         AZƏRBAYCAN PR MONİTORİNQ SİSTEMİ v2.0              ║
║         Çoxlu mənbəli | AI analiz | Telegram bildiriş       ║
╚══════════════════════════════════════════════════════════════╝
"""

import time
import datetime
import json
import os
import socket
import hashlib
import logging
import schedule
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import google.generativeai as genai

from config import (
    GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    KEYWORDS, INTERVAL_MINUTES, MAX_WORKERS, SEEN_LINKS_FILE,
    HOURS_BACK, REQUEST_TIMEOUT, RETRY_COUNT, RETRY_DELAY
)
from sources import get_all_sources
from date_checker import validate_batch
from az_filter import filter_az
from ai_analyzer import analyze_with_ai
from telegram_sender import send_telegram_alert

# ── Logging quraşdırması ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitor.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)

socket.setdefaulttimeout(REQUEST_TIMEOUT)
genai.configure(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════
# GÖRÜLMÜŞ LİNKLƏR - duplikat önləmə
# ══════════════════════════════════════════════════════════════
def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def load_seen() -> set:
    if not os.path.exists(SEEN_LINKS_FILE):
        return set()
    try:
        with open(SEEN_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_seen(hashes: set):
    existing = load_seen()
    merged = list(existing | hashes)
    # Son 5000 hash-i saxla (fayl şişməsin)
    if len(merged) > 5000:
        merged = merged[-5000:]
    with open(SEEN_LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f)


# ══════════════════════════════════════════════════════════════
# HTTP KÖMƏKÇISI - retry mexanizmi ilə
# ══════════════════════════════════════════════════════════════
def safe_get(url: str, headers: dict = None, timeout: int = REQUEST_TIMEOUT) -> requests.Response | None:
    """Təhlükəsiz HTTP GET.

    Retry siyasəti:
      - Timeout        → dərhal None (sayt mövcuddur, amma yavaşdır; retry vaxt itkisidir)
      - 4xx            → dərhal None (sabit xəta, retry faydasız)
      - ConnectionError → 1 dəfə retry (müvəqqəti şəbəkə kəsilməsi)
      - 5xx            → 2 dəfə retry (server müvəqqəti xəta)
    """
    _headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }
    if headers:
        _headers.update(headers)

    NO_RETRY_CODES = {400, 401, 403, 404, 405, 410, 451}

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.get(url, headers=_headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code in NO_RETRY_CODES:
                log.debug(f"HTTP {resp.status_code} (keçilir): {url[:70]}")
                return None
            # 5xx → retry
            log.warning(f"HTTP {resp.status_code} → {url[:60]}... (cəhd {attempt}/{RETRY_COUNT})")

        except requests.exceptions.Timeout:
            # Timeout → dərhal None, retry etmə (vaxt itkisi)
            log.debug(f"Timeout (keçilir): {url[:60]}")
            return None

        except requests.exceptions.ConnectionError:
            if attempt == RETRY_COUNT:
                log.debug(f"Bağlantı xətası (sayt əlçatmazdır): {url[:60]}")
                return None
            # 1 dəfə retry
            log.debug(f"Bağlantı xətası (cəhd {attempt}/{RETRY_COUNT}): {url[:60]}")

        except Exception as e:
            log.debug(f"Xəta: {e} | {url[:60]}")
            return None

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY)

    return None


# ══════════════════════════════════════════════════════════════
# ƏSAS AXTARIŞ FUNKSİYASI
# ══════════════════════════════════════════════════════════════
def fetch_for_keyword(keyword: str, seen_hashes: set) -> list[dict]:
    """Bir açar söz üçün bütün mənbələrdən məlumat toplayır."""
    sources = get_all_sources(keyword, HOURS_BACK)
    collected = []

    for src in sources:
        try:
            items = src.fetch(safe_get)
            for item in items:
                h = _url_hash(item["link"])
                if h not in seen_hashes:
                    item["keyword"] = keyword
                    item["source_type"] = src.source_type
                    collected.append(item)
        except Exception as e:
            log.debug(f"Mənbə xətası ({src.name}): {e}")

    if collected:
        # 1. AZ sferası filteri — xarici domenli, AZ-la əlaqəsiz elementlər atılır
        before_az = len(collected)
        collected = filter_az(collected)
        if len(collected) < before_az:
            log.info(f"🌍 [{keyword}] → AZ filteri: {before_az - len(collected)} xarici atıldı")

        # 2. Tarix + link yoxlaması — köhnə və açılmayan linklər atılır
        if collected:
            log.info(f"🔍 [{keyword}] → {len(collected)} element tapıldı, tarix+link yoxlanılır...")
            collected = validate_batch(collected, safe_get,
                                       hours_back=HOURS_BACK, max_workers=4)
        if collected:
            log.info(f"✅ [{keyword}] → {len(collected)} keçərli element qaldı")
    else:
        log.info(f"✅ [{keyword}] → yeni məlumat tapılmadı")

    return collected


# ══════════════════════════════════════════════════════════════
# ƏSAS İŞ SİKLİ
# ══════════════════════════════════════════════════════════════
def job():
    start = datetime.datetime.now()
    log.info(f"\n{'═'*55}")
    log.info(f"🚀 MONİTORİNQ BAŞLADI → {start.strftime('%d.%m.%Y %H:%M')}")
    log.info(f"{'═'*55}")

    seen_hashes = load_seen()
    all_new_items = []
    new_hashes = set()

    # Paralel axtarış
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(fetch_for_keyword, kw, seen_hashes): kw
            for kw in KEYWORDS
        }
        for future in as_completed(futures):
            kw = futures[future]
            try:
                items = future.result()
                all_new_items.extend(items)
                for it in items:
                    new_hashes.add(_url_hash(it["link"]))
            except Exception as e:
                log.error(f"❌ [{kw}] işləmə xətası: {e}")

    # AI analizi → Telegram
    if all_new_items:
        log.info(f"\n🧠 Cəmi {len(all_new_items)} element AI ilə analiz edilir...")
        analyzed = analyze_with_ai(all_new_items)

        sent = 0
        for item in analyzed:
            ok = send_telegram_alert(item)
            if ok:
                sent += 1
            time.sleep(0.5)  # Telegram flood qoruması

        log.info(f"📨 {sent}/{len(analyzed)} bildiriş göndərildi")
        save_seen(seen_hashes | new_hashes)
    else:
        log.info("💤 Göndəriləcək yeni məlumat yoxdur")

    elapsed = (datetime.datetime.now() - start).seconds
    log.info(f"⏱  Tamamlandı ({elapsed}s) │ Növbəti yoxlama: {INTERVAL_MINUTES} dəqiqə sonra\n")


# ══════════════════════════════════════════════════════════════
# BAŞLANĞIC
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("🟢 PR Monitoring Sistemi işə salındı")
    job()  # Dərhal bir dəfə işlət

    schedule.every(INTERVAL_MINUTES).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
