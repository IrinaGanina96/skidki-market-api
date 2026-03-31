# vk_miniapp/backend/config.py
import os
import sys
from dotenv import load_dotenv

# Добавляем путь к корневой папке
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Правильная загрузка .env
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env")
load_dotenv(env_path)

print(f"Загрузка .env из: {env_path}")
print("VK_ACCESS_TOKEN:", os.getenv("VK_ACCESS_TOKEN", "НЕ НАЙДЕН")[:20] + "..." if os.getenv("VK_ACCESS_TOKEN") else "НЕ НАЙДЕН")
print("VK_GROUP_ID:", os.getenv("VK_GROUP_ID", "НЕ НАЙДЕН"))

# ========== ПАРТНЕРСКИЙ CLID ==========
VK_CLID = os.getenv("VK_CLID", "")

# ========== НАСТРОЙКИ ПОИСКА ==========
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", "30"))
MIN_RATING = float(os.getenv("MIN_RATING", "4.5"))
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS_IN_COLLECTION", "5"))

# ========== РЕЖИМ ==========
MODE = os.getenv("BACKEND_MODE", "mock")

# ========== VK ДЛЯ ПУБЛИКАЦИИ ==========
VK_APP_ID = os.getenv("VK_APP_ID", "")
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")

# ========== ИНТЕРВАЛ ПУБЛИКАЦИИ ==========
POST_INTERVAL = int(os.getenv("VK_POST_INTERVAL", "7200"))

# ========== CORS ==========
ALLOWED_ORIGINS = [
    "https://vk.com",
    "https://m.vk.com",
    "https://localhost",
    "http://localhost",
    "http://127.0.0.1",
    "null"
]

# ========== ПРОВЕРКИ ==========
if MODE == "real" and not VK_CLID:
    print("⚠️ BACKEND_MODE=real, но VK_CLID не задан. Используем mock.")
    MODE = "mock"

if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
    print("⚠️ VK_ACCESS_TOKEN или VK_GROUP_ID не заданы. Автопостинг работать не будет.")
else:
    print(f"✅ VK автопостинг настроен: группа {VK_GROUP_ID}")

print(f"📱 VK API Config: mode={MODE}, post_interval={POST_INTERVAL//60} мин")