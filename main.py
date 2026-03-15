import asyncio
import aiohttp
import aiosqlite
import logging
import os
from config import POLLING_INTERVAL
from ebay_api import EbayAPI
from filters import process_item
from tg_bot import send_telegram_notification, poll_telegram_updates, setup_bot_commands

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "seen_items.db"

async def init_db():
    """Ініціалізація бази даних SQLite для збереження переглянутих лотів."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS seen_items (
                item_id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

async def is_item_seen(item_id: str) -> bool:
    """Перевіряє, чи лот вже відправлявся/перевірявся."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM seen_items WHERE item_id = ?", (item_id,)) as cursor:
            result = await cursor.fetchone()
            return result is not None

async def mark_item_seen(item_id: str):
    """Додає ID лота у базу даних як переглянутий."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO seen_items (item_id) VALUES (?)", (item_id,))
        await db.commit()

async def cleanup_old_items():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM seen_items WHERE timestamp < datetime('now', '-2 days')")
        await db.commit()
    logger.info("Old seen_items cleaned up.")

async def main():
    logger.info("Initializing eBay Laptop Monitor...")
    
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("EBAY_APP_ID=\nEBAY_CERT_ID=\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n")
        logger.warning(".env file created. Please fill it with your credentials.")
        
    await init_db()
    ebay = EbayAPI()
    cycle_count = 0

    async with aiohttp.ClientSession() as session:
        # ОНОВЛЮЄМО МЕНЮ КОМАНД (ВИДАЛЯЄМО СТАРІ)
        await setup_bot_commands(session)
        
        # ЗАПУСКАЄМО ПРОЦЕС ОТРИМАННЯ КОМАНД З ТЕЛЕГРАМУ У ФОНІ
        asyncio.create_task(poll_telegram_updates(session))
        
        while True:
            try:
                cycle_count += 1
                logger.info("Fetching new laptops from eBay...")
                items = await ebay.search_laptops(session)
                
                new_laptops_found = 0
                
                for item in items:
                    item_id = item.get("itemId")
                    if not item_id:
                        continue
                        
                    # Перевіряємо анти-дублікат
                    if await is_item_seen(item_id):
                        continue

                    # Запускаємо логіку фільтрації та розрахунку
                    processed_data = process_item(item)

                    # Позначаємо як переглянутий лише якщо лот має дату створення
                    if item.get("itemCreationDate"):
                        await mark_item_seen(item_id)

                    # Якщо товар пройшов всі фільтри
                    if processed_data:
                        logger.info(f"MATCH FOUND: {processed_data['title']} "
                                    f"| Profit: {processed_data['max_cost_uah'] - processed_data['final_uah']:.0f} UAH")
                        # Надсилаємо у Telegram
                        await send_telegram_notification(session, processed_data)
                        new_laptops_found += 1
                        
                logger.info(f"Cycle finished. Processed {len(items)} items. Sent {new_laptops_found} notifications.")
                
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                
            # Пауза перед наступним запитом (Polling)
            if cycle_count % 720 == 0:
                await cleanup_old_items()
            logger.info(f"Sleeping for {POLLING_INTERVAL} seconds...")
            await asyncio.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("eBay Laptop Monitor gracefully stopped by the user.")