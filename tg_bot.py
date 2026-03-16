import logging
import asyncio
import aiohttp
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from limits_manager import limits_manager
import unknown_tracker

logger = logging.getLogger(__name__)

async def setup_bot_commands(session: aiohttp.ClientSession):
    """Встановлює актуальні команди для меню в Telegram і видаляє старі"""
    if not TELEGRAM_BOT_TOKEN:
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    commands = [
        {"command": "unknown", "description": "Моделі не в списку (напр: /unknown або /unknown 14)"},
        {"command": "addcpu", "description": "Швидко додати CPU (напр: /addcpu i5-1335u 15000)"},
        {"command": "addgpu", "description": "Швидко додати GPU (напр: /addgpu rtx 4050 25000)"},
        {"command": "setlimit", "description": "Встановити новий або існуючий ліміт (напр: /setlimit m5 50000)"},
        {"command": "dellimit", "description": "Видалити критерій (напр: /dellimit rtx 4060)"},
        {"command": "getlimit", "description": "Дізнатись ліміт (напр: /getlimit rtx 4060)"},
        {"command": "getall", "description": "Показати всі ліміти"},
        {"command": "setrate", "description": "Встановити курс долара (напр: /setrate 41.5)"},
        {"command": "getrate", "description": "Показати поточний курс долара"},
        {"command": "help", "description": "Показати всі команди"}
    ]
    data = {"commands": commands}
    try:
        async with session.post(url, json=data) as response:
            if response.status == 200:
                logger.info("Bot commands menu updated successfully.")
            else:
                logger.error(f"Failed to update commands menu: {await response.text()}")
    except Exception as e:
        logger.error(f"Error setting bot commands: {e}")

async def send_unknown_notification(session: aiohttp.ClientSession, notif: dict):
    """Sends a notification about an unknown CPU/GPU model found on eBay."""
    model = notif['model'].upper()
    model_type = notif['model_type']
    title = notif['title']
    price_usd = notif['price_usd']
    item_url = notif.get('item_url', '')

    if model_type == 'gpu':
        add_cmd = f"/addgpu {notif['model']} [грн]"
        icon = "🎮"
    else:
        add_cmd = f"/addcpu {notif['model']} [грн]"
        icon = "💻"

    text = (
        f"❓ <b>Нова модель не в списку!</b>\n\n"
        f"{icon} <b>Модель:</b> <code>{model}</code>\n"
        f"📋 <b>Лот:</b> {title}\n"
        f"💵 <b>Ціна:</b> ~${price_usd:.0f}\n\n"
        f"Додати до списку:\n<code>{add_cmd}</code>"
    )
    if item_url:
        text += f"\n\n🔗 <a href='{item_url}'>Переглянути лот</a>"

    await send_telegram_message(session, text)


async def send_telegram_message(session: aiohttp.ClientSession, text: str):
    """Надсилає звичайне текстове повідомлення у Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        await session.post(url, data=data)
    except Exception as e:
        logger.error(f"Error sending text message: {e}")

async def send_telegram_notification(session: aiohttp.ClientSession, item_data: dict):
    """
    Асинхронно відправляє повідомлення у Telegram за допомогою методу sendPhoto.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials are not configured in .env file.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    # Розрахунок очікуваного прибутку
    profit_uah = item_data["max_cost_uah"] - item_data["final_uah"]
    
    # Форматування HTML-повідомлення (caption)
    caption = (
        f"🟢 <b>ЗНАЙДЕНО НОУТБУК</b>\n"
        f"<b>{item_data['title']}</b>\n\n"
        f"⏱ <b>На сайті:</b> <code>{item_data['age_minutes']} хв.</code>\n"
        f"💡 <b>Критерій:</b> <code>{item_data['criterion']}</code>\n"
        f"⚠️ <b>Стан:</b> {item_data['condition']}\n"
        f"👤 <b>Продавець:</b> {item_data['feedback_percent']}% позитивних (відгуків: {item_data['feedback_score']})\n\n"
        f"🇺🇸 Ціна eBay: ${item_data['price_usd']:.2f} + ${item_data['shipping_usd']:.2f}\n"
        f"🇺🇦 <b>В Україні під ключ: ~{item_data['final_uah']:,.0f} грн</b>\n"
        f"🎯 <i>Ліміт: {item_data['max_cost_uah']:,.0f} грн</i>\n"
        f"💰 <b>Очікуваний прибуток: ~{profit_uah:,.0f} грн</b>\n\n"
        f"🔗 <a href='{item_data['item_url']}'>Купити на eBay</a>"
    )
    
    # Якщо картинки немає (image_url порожній), використовуємо заглушку
    photo_url = item_data.get("image_url")
    if not photo_url:
        photo_url = "https://via.placeholder.com/600x400.png?text=No+Image+Available"
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    
    try:
        async with session.post(url, data=data) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Failed to send Telegram message. HTTP {response.status}: {error_text}")
            else:
                logger.info(f"Notification successfully sent for item {item_data['item_id']}")
    except Exception as e:
        logger.error(f"Exception during Telegram sending: {e}")

async def process_telegram_command(session: aiohttp.ClientSession, text: str):
    """Обробляє команди, отримані від користувача"""
    parts = text.split(maxsplit=2)
    raw_command = parts[0]
    command = raw_command.lower().split('@')[0]
    # Normalize text to strip @botname suffix from command (e.g. /addcpu@mybot → /addcpu)
    if '@' in raw_command:
        text = command + text[len(raw_command):]
    
    if command == "/start" or command == "/help":
        help_text = (
            "🤖 <b>Команди eBay Монітора:</b>\n\n"
            "🔍 <b>Невідомі моделі:</b>\n"
            "<code>/unknown</code> - Моделі не в списку (за 7 днів)\n"
            "<code>/unknown 14</code> - За останні 14 днів\n\n"
            "➕ <b>Швидке додавання:</b>\n"
            "<code>/addcpu i5-1335u 15000</code> - Додати CPU\n"
            "<code>/addgpu rtx 4050 25000</code> - Додати GPU\n\n"
            "⚙️ <b>Управління лімітами:</b>\n"
            "<code>/setlimit [модель] [ціна]</code> - Встановити ліміт. Приклад:\n"
            "<code>/setlimit m3 pro 90000</code>\n\n"
            "<code>/dellimit [модель]</code> - Видалити критерій. Приклад:\n"
            "<code>/dellimit rtx 4060</code>\n\n"
            "<code>/getlimit [модель]</code> - Дізнатись поточний ліміт. Приклад:\n"
            "<code>/getlimit rtx 4060</code>\n\n"
            "<code>/getall</code> - Показати список усіх лімітів\n\n"
            "💱 <b>Курс долара:</b>\n"
            "<code>/setrate 41.5</code> - Змінити курс\n"
            "<code>/getrate</code> - Показати поточний курс\n\n"
            "<code>/help</code> - Показати це меню"
        )
        await send_telegram_message(session, help_text)
        
    elif command == "/unknown":
        days_str = text[len("/unknown"):].strip()
        try:
            days = int(days_str) if days_str else 7
            if days <= 0 or days > 90:
                raise ValueError
        except ValueError:
            days = 7
        report = unknown_tracker.get_unknown_report(days)
        await send_telegram_message(session, report)

    elif command == "/addcpu":
        cmd_body = text[len("/addcpu"):].strip()
        body_parts = cmd_body.rsplit(maxsplit=1)
        if len(body_parts) == 2:
            model, price_str = body_parts
            try:
                price = float(price_str)
                response_text = limits_manager.add_to_category(model, price, 'cpu')
                await send_telegram_message(session, f"✅ {response_text}")
            except ValueError:
                await send_telegram_message(session, "❌ Помилка: Ціна має бути числом. Приклад: /addcpu i5-1335u 15000")
        else:
            await send_telegram_message(session, "❌ Неправильний формат. Приклад: /addcpu i5-1335u 15000")

    elif command == "/addgpu":
        cmd_body = text[len("/addgpu"):].strip()
        body_parts = cmd_body.rsplit(maxsplit=1)
        if len(body_parts) == 2:
            model, price_str = body_parts
            try:
                price = float(price_str)
                response_text = limits_manager.add_to_category(model, price, 'gpu')
                await send_telegram_message(session, f"✅ {response_text}")
            except ValueError:
                await send_telegram_message(session, "❌ Помилка: Ціна має бути числом. Приклад: /addgpu rtx 4050 25000")
        else:
            await send_telegram_message(session, "❌ Неправильний формат. Приклад: /addgpu rtx 4050 25000")

    elif command == "/getall":
        texts = limits_manager.get_all_limits_text()
        for msg in texts:
            await send_telegram_message(session, msg)
            
    elif command == "/setlimit":
        cmd_body = text[len("/setlimit"):].strip()
        body_parts = cmd_body.rsplit(maxsplit=1)
        if len(body_parts) == 2:
            model, price_str = body_parts
            try:
                price = float(price_str)
                response_text = limits_manager.update_limit(model, price)
                await send_telegram_message(session, f"✅ {response_text}")
            except ValueError:
                await send_telegram_message(session, "❌ Помилка: Ціна має бути числом!")
        else:
            await send_telegram_message(session, "❌ Неправильний формат. Використовуй: /setlimit m3 50000")
            
    elif command == "/dellimit":
        model = text[len("/dellimit"):].strip()
        if not model:
            await send_telegram_message(session, "❌ Вкажи критерій. Приклад: /dellimit rtx 4060")
            return
        response_text = limits_manager.delete_limit(model)
        await send_telegram_message(session, f"🗑 {response_text}")

    elif command == "/setrate":
        rate_str = text[len("/setrate"):].strip()
        try:
            rate = float(rate_str)
            if rate <= 0:
                raise ValueError
            response_text = limits_manager.set_rate(rate)
            await send_telegram_message(session, f"✅ {response_text}")
        except ValueError:
            await send_telegram_message(session, "❌ Невірний курс. Приклад: /setrate 41.5")

    elif command == "/getrate":
        rate = limits_manager.get_rate()
        await send_telegram_message(session, f"💱 Поточний курс: <b>1 USD = {rate} грн</b>")

    elif command == "/getlimit":
        model = text[len("/getlimit"):].strip()
        if not model:
            await send_telegram_message(session, "❌ Вкажи модель. Приклад: /getlimit rtx 4060")
            return
            
        price = limits_manager.get_limit(model)
        if price is not None:
            await send_telegram_message(session, f"ℹ️ Поточний ліміт для <b>{model.upper()}</b>: {price:,.0f} грн")
        else:
            await send_telegram_message(session, f"❓ Модель <b>{model.upper()}</b> не знайдена в базі.")

async def poll_telegram_updates(session: aiohttp.ClientSession):
    """Фоновий процес для отримання команд з Telegram (Long Polling)"""
    offset = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    logger.info("Started Telegram bot command polling...")
    
    while True:
        try:
            params = {"offset": offset, "timeout": 30}
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    await asyncio.sleep(5)
                    continue
                    
                data = await response.json()
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    message = result.get("message", {})
                    text = message.get("text", "")
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    
                    # Ігноруємо повідомлення не від власника бота
                    if chat_id != str(TELEGRAM_CHAT_ID):
                        continue
                        
                    if text.startswith("/"):
                        await process_telegram_command(session, text)
                        
        except asyncio.TimeoutError:
            pass # Timeout це нормально для long polling
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            await asyncio.sleep(5)