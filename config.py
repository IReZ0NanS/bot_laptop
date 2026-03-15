import os
from dotenv import load_dotenv

# Завантажуємо змінні оточення
load_dotenv()

EBAY_APP_ID = os.getenv("EBAY_APP_ID", "YOUR_APP_ID_HERE")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID", "YOUR_CERT_ID_HERE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

# Налаштування пошуку
EBAY_CATEGORY_ID = "175672" # Laptops & Netbooks
POLLING_INTERVAL = 120 # Інтервал у секундах (2 хвилини)

# Мінус-слова (фільтрація сміття та зламаних)
NEGATIVE_KEYWORDS = [
    "as is", "parts", "repair", "broken", "cracked", "no power", 
    "bios lock", "mdm", "icloud", "water damage", "no os", 
    "bad motherboard", "screen damage", "defective",
    "salvage", "untested", "lcd issue", "keyboard damage", "incomplete",
    "missing", "not working", "for parts",
    "sleeve"
]