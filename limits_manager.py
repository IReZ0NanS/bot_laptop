import json
import re
import os
import logging

logger = logging.getLogger(__name__)

LIMITS_FILE = "limits.json"

DEFAULT_LIMITS = {
    "settings": {
        "usd_rate": 45
    },
    "gpu": {
        "rtx 4090": 95000,
        "rtx 4080": 50000,
        "rtx 4070": 38000,
        "rtx 4060": 24700,
        "rtx 4050": 25000,
        "rtx 3080": 33000,
        "rtx 3070": 24900,
        "rtx 3060": 22500,
        "rtx 3050 ti": 19000,
        "rtx 3050": 17000,
        "quadro t1000": 12000,
        "quadro t2000": 14000,
        "quadro rtx 3000": 18000,
        "rtx a2000": 26000,
        "quadro rtx 4000": 23000,
        "rtx a3000": 32000,
        "rtx a4000": 42000,
        "rtx a5000": 55000,
        "rtx 2050": 11500,
        "rtx 3070 ti": 35000,
        "rtx a1000": 31000,
        "radeon rx 6600m": 24000,
        "radeon rx 7600s": 30000
    },
    "cpu": {
        "i9-14900hx": 53000,
        "i9-13980hx": 47000,
        "i9-13900h": 34000,
        "i9-12900h": 30000,
        "i9-10885h": 20000,
        "i7-14700h": 33000,
        "i7-13700h": 25500,
        "i7-12700h": 23000,
        "i7-11800h": 18000,
        "i7-10750h": 15000,
        "i5-14500h": 25000,
        "i5-13500h": 22000,
        "i5-12500h": 18000,
        "i5-11400h": 15000,
        "i5-10300h": 12000,
        "i7-1355u": 19000,
        "i7-1255u": 13500,
        "i7-1165g7": 10500,
        "i7-10510u": 8500,
        "i5-1335u": 15000,
        "i5-1235u": 11000,
        "i5-1145g7": 10000,
        "i5-1135g7": 8500,
        "i5-10210u": 7000,
        "i3-1215u": 8500,
        "i3-1115g4": 6500,
        "i3-1005g1": 5500,
        "ryzen 9 7940hs": 35000,
        "ryzen 9 6900hs": 30000,
        "ryzen 9 5900hx": 24900,
        "ryzen 9": 24000,
        "ryzen 7 5800h": 16500,
        "ryzen 7 4800h": 13000,
        "ryzen 7 5700u": 11000,
        "ryzen 7 4700u": 8500,
        "ryzen 7": 16000,
        "ryzen 5 5600h": 14500,
        "ryzen 5 4600h": 11000,
        "ryzen 5 5500u": 8500,
        "ryzen 5 4500u": 7000,
        "ryzen 5": 12000,
        "ryzen 3 5300u": 6000,
        "ryzen 3 4300u": 5000,
        "m3 max": 69200,
        "m3 pro": 55000,
        "m3": 30000,
        "m2 max": 68000,
        "m2 pro": 42000,
        "m2": 23000,
        "m1 max": 50000,
        "m1 pro": 33000,
        "m1": 13900,
        "r3 4300u": 5000,
        "r3 5300u": 6000,
        "r5": 12000,
        "r5 4500u": 7000,
        "r5 4600h": 11000,
        "r5 5500u": 8500,
        "r5 5600h": 14500,
        "r7": 16000,
        "r7 4700u": 8500,
        "r7 4800h": 13000,
        "r7 5700u": 11000,
        "r7 5800h": 16500,
        "r9": 24000,
        "r9 5900hx": 24900,
        "r9 6900hs": 30000,
        "r9 7940hs": 35000,
        "i5-11320h": 14000,
        "i5-12450h": 15000,
        "i7-1185g7": 12500,
        "i7-12650h": 18000,
        "i5-13420h": 20000,
        "i7-13620h": 26000,
        "i9-11900h": 30000,
        "i9-11950h": 40000,
        "ultra 5 125h": 31600,
        "ultra 7 155h": 25000,
        "ultra 9 185h": 30900,
        "ryzen 5 6600h": 16500,
        "ryzen 7 6800h": 22000,
        "ryzen 5 7535hs": 20900,
        "ryzen 7 7735hs": 24000,
        "ryzen 7 7840hs": 35000,
        "ryzen 9 7945hx": 31600,
        "ryzen 7 8845hs": 45000,
        "ryzen 9 8945hs": 53000,
        "m4": 35000,
        "i5 10th": 10000,
        "i5 11th": 12500,
        "i5 12th": 15500,
        "i5 13th": 19000,
        "i5 14th": 23000,
        "i5 15th": 27000,
        "i7 10th": 13000,
        "i7 11th": 16000,
        "i7 12th": 20000,
        "i7 13th": 26000,
        "i7 14th": 30000,
        "i7 15th": 36000,
        "i9 10th": 22000,
        "i9 11th": 33000,
        "i9 12th": 32000,
        "i9 13th": 42000,
        "i9 14th": 50000,
        "i9 15th": 58000
    }
}

class LimitsManager:
    def __init__(self):
        self.limits = self.load_limits()

    def load_limits(self):
        if os.path.exists(LIMITS_FILE):
            try:
                with open(LIMITS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Міграція: якщо старий файл без settings
                if "settings" not in data:
                    data["settings"] = {"usd_rate": 45}
                    self.save_limits(data)
                return data
            except Exception as e:
                logger.error(f"Error loading limits.json: {e}")

        # Якщо файлу немає або він пошкоджений - зберігаємо дефолтні значення
        self.save_limits(DEFAULT_LIMITS)
        return DEFAULT_LIMITS

    def save_limits(self, data):
        try:
            with open(LIMITS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving limits.json: {e}")

    def update_limit(self, key: str, price: float) -> str:
        key = key.lower().strip()
        # Перевіряємо в якій категорії знаходиться ключ
        if key in self.limits["gpu"]:
            self.limits["gpu"][key] = price
            self.save_limits(self.limits)
            return f"Оновлено ліміт GPU: {key.upper()} = {price:,.0f} грн"
        elif key in self.limits["cpu"]:
            self.limits["cpu"][key] = price
            self.save_limits(self.limits)
            return f"Оновлено ліміт CPU: {key.upper()} = {price:,.0f} грн"
        else:
            # Якщо ключ новий, додаємо його до CPU (як універсальну категорію)
            self.limits["cpu"][key] = price
            self.save_limits(self.limits)
            return f"Додано новий критерій: {key.upper()} = {price:,.0f} грн"

    def delete_limit(self, key: str) -> str:
        key = key.lower().strip()
        if key in self.limits["gpu"]:
            del self.limits["gpu"][key]
            self.save_limits(self.limits)
            return f"Видалено GPU критерій: {key.upper()}"
        elif key in self.limits["cpu"]:
            del self.limits["cpu"][key]
            self.save_limits(self.limits)
            return f"Видалено CPU критерій: {key.upper()}"
        else:
            return f"Критерій {key.upper()} не знайдено"

    def get_rate(self) -> float:
        return float(self.limits.get("settings", {}).get("usd_rate", 45))

    def set_rate(self, rate: float) -> str:
        self.limits.setdefault("settings", {})["usd_rate"] = rate
        self.save_limits(self.limits)
        return f"Курс долара оновлено: 1 USD = {rate} грн"

    def get_limit(self, key: str):
        key = key.lower().strip()
        if key in self.limits["gpu"]: 
            return self.limits["gpu"][key]
        if key in self.limits["cpu"]: 
            return self.limits["cpu"][key]
        return None

    def get_all_limits_text(self):
        text_gpu = "🎮 <b>Ліміти GPU:</b>\n"
        for k, v in sorted(self.limits["gpu"].items()):
            text_gpu += f"• <code>{k.upper()}</code>: {v:,.0f} грн\n"
            
        text_cpu = "💻 <b>Ліміти CPU (та інші):</b>\n"
        for k, v in sorted(self.limits["cpu"].items()):
            text_cpu += f"• <code>{k.upper()}</code>: {v:,.0f} грн\n"
            
        return [text_gpu, text_cpu]

    def _match_keyword(self, keyword: str, title: str) -> bool:
        title_lower = title.lower()
        variants = [
            keyword,
            keyword.replace("-", " "),
            keyword.replace("-", ""),
        ]
        for variant in variants:
            pattern = r"(?<![a-z0-9])" + re.escape(variant) + r"(?![a-z0-9])"
            title_check = title_lower.replace("-", " " if " " in variant else "")
            if re.search(pattern, title_check):
                return True
        return False

    def find_criterion_and_max_cost(self, title: str):
        # 1. Шукаємо GPU. Сортуємо ключі за довжиною
        for gpu, max_cost in sorted(self.limits["gpu"].items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_keyword(gpu, title):
                return gpu.upper(), max_cost

        # 2. Якщо GPU немає, шукаємо CPU
        for cpu, max_cost in sorted(self.limits["cpu"].items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_keyword(cpu, title):
                return cpu.upper(), max_cost
                
        return None, None

limits_manager = LimitsManager()