import datetime
from config import NEGATIVE_KEYWORDS
from limits_manager import limits_manager
import unknown_tracker

def check_negative_keywords(title: str) -> bool:
    """Перевіряє назву лота на наявність мінус-слів."""
    title_lower = title.lower()
    for kw in NEGATIVE_KEYWORDS:
        if kw in title_lower:
            return True
    return False

def calculate_final_uah(price_usd: float, shipping_usd: float) -> float:
    """
    Розраховує підсумкову ціну в Україні (в гривнях).
    Формула: ((price_usd + shipping_usd) * 1.1 + 30) * usd_rate
    """
    usd_rate = limits_manager.get_rate()
    return ((price_usd + shipping_usd) * 1.1 + 30) * usd_rate

def process_item(item: dict) -> dict:
    """
    Основна логіка фільтрації одного лота з eBay.
    Якщо лот підходить, повертає підготовлений словник з даними для Telegram.
    Якщо ні - повертає None.
    """
    title = item.get("title", "")
    
    # 1. Перевірка мінус-слів
    if check_negative_keywords(title):
        return None
        
    # 2. Фільтр стану: Виключити Condition ID 7000 (For Parts)
    condition_id = str(item.get("conditionId", ""))
    if condition_id == "7000" or item.get("condition", "").lower() == "for parts or not working":
        return None
        
    # 3. Фільтр часу (Ігноруємо, якщо вік > 30 хв)
    creation_date_str = item.get("itemCreationDate")
    if not creation_date_str:
        return None
        
    try:
        creation_date = datetime.datetime.strptime(creation_date_str.split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ")
        creation_date = creation_date.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None
        
    now = datetime.datetime.now(datetime.timezone.utc)
    age_minutes = (now - creation_date).total_seconds() / 60
    
    if age_minutes > 30:
        return None
        
    # 4. Ціни
    price_dict = item.get("price", {})
    price_usd = float(price_dict.get("value", 0))
    if price_usd <= 0:
        return None
        
    shipping_options = item.get("shippingOptions", [])
    shipping_usd = 15.0
    free_shipping = False

    if shipping_options:
        shipping_cost = shipping_options[0].get("shippingCost", {})
        raw_value = float(shipping_cost.get("value", -1))
        if raw_value == 0.0:
            shipping_usd = 0.0
            free_shipping = True
        elif raw_value > 0:
            shipping_usd = raw_value
        # якщо -1 (не вказано) — залишаємо дефолт 15.0
        
    final_uah = calculate_final_uah(price_usd, shipping_usd)
    
    # 5. Фільтр продавця: відкидаємо з рейтингом 0
    seller = item.get("seller", {})
    try:
        feedback_score = int(seller.get("feedbackScore", 0))
    except (ValueError, TypeError):
        feedback_score = 0
        
    if feedback_score <= 0:
        return None
    
    # 6. Критерії та ліміти (зчитуємо з limits_manager)
    criterion, max_cost = limits_manager.find_criterion_and_max_cost(title)
    if not criterion:
        item_url = item.get("itemWebUrl", "")
        unknown_tracker.track_unknown(title, price_usd, item_url)
        return None
        
    if final_uah > max_cost:
        return None
        
    # 7. Збираємо додаткові дані для бота
    image_url = item.get("image", {}).get("imageUrl", "")
    feedback_percent = seller.get("feedbackPercentage", "N/A")
    condition_text = item.get("condition", "N/A")
    
    return {
        "item_id": item.get("itemId", ""),
        "title": title,
        "age_minutes": int(age_minutes),
        "criterion": criterion,
        "condition": condition_text,
        "feedback_percent": feedback_percent,
        "feedback_score": feedback_score,
        "price_usd": price_usd,
        "shipping_usd": shipping_usd,
        "free_shipping": free_shipping,
        "final_uah": final_uah,
        "max_cost_uah": max_cost,
        "image_url": image_url,
        "item_url": item.get("itemWebUrl", f"https://www.ebay.com/itm/{item.get('itemId', '').split('|')[-1]}")
    }