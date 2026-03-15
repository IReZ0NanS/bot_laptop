import asyncio
import base64
import time
import logging
from config import EBAY_APP_ID, EBAY_CERT_ID, EBAY_CATEGORY_ID

MAX_RETRIES = 3
RETRY_DELAY = 5

logger = logging.getLogger(__name__)

class EbayAPI:
    def __init__(self):
        self.token = None
        self.token_expiry = 0

    async def get_token(self, session):
        """Отримує новий OAuth 2.0 токен від eBay або повертає активний."""
        if self.token and time.time() < self.token_expiry:
            return self.token
            
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        credentials = f"{EBAY_APP_ID}:{EBAY_CERT_ID}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.token = result.get("access_token")
                        # Токен дійсний 7200 сек. Віднімаємо 5 хвилин для запасу.
                        expires_in = result.get("expires_in", 7200)
                        self.token_expiry = time.time() + expires_in - 300
                        logger.info("Successfully generated new eBay OAuth token.")
                        return self.token
                    else:
                        logger.error(f"Failed to get eBay token. Status {response.status}: {await response.text()}")
                        return None
            except Exception as e:
                logger.warning(f"Token request exception (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
        return None

    async def search_laptops(self, session):
        """Здійснює пошук нових ноутбуків за вказаними параметрами."""
        token = await self.get_token(session)
        if not token:
            return []
            
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        }
        
        params = {
            "category_ids": EBAY_CATEGORY_ID,
            "sort": "newlyListed",
            "limit": "50",
            "filter": "conditionIds:{1000|1500|2000|2500|3000|4000|5000|6000}"
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("itemSummaries", [])
                    elif response.status == 401:
                        logger.warning(f"Got 401 on search (attempt {attempt}), refreshing token...")
                        self.token = None
                        token = await self.get_token(session)
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                    else:
                        logger.error(f"Failed to fetch items from eBay API. Status {response.status}: {await response.text()}")
                        return []
            except Exception as e:
                logger.warning(f"Search request exception (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
        return []
