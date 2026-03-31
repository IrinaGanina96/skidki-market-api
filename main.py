# vk_miniapp/backend/main.py
"""
Бэкенд для VK Mini App
Возвращает тематические подборки скидок через API
И автоматически публикует подборки в VK-сообщество (только текст, без картинок)
"""

import sys
import os
import logging
import asyncio
import random
import requests
import re
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from vk_miniapp.backend.config import (
    VK_CLID, MIN_DISCOUNT, MIN_RATING, MAX_PRODUCTS, MODE, ALLOWED_ORIGINS,
    VK_GROUP_ID, VK_ACCESS_TOKEN, VK_APP_ID, POST_INTERVAL
)
from vk_miniapp.backend.promocodes import promocode_manager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем приложение FastAPI
app = FastAPI(
    title="Скидки Маркета API",
    description="API для получения тематических подборок скидок на Яндекс Маркете",
    version="2.0.0"
)

# Настройка CORS для VK
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== КАТЕГОРИИ ТОВАРОВ ==========
CATEGORIES = {
    "смартфоны": {
        "keywords": [
            "смартфон", "телефон", "iphone", "apple", "xiaomi", "redmi", "poco",
            "samsung", "galaxy", "realme", "honor", "huawei", "pixel", "google pixel"
        ],
        "header": "📱 СМАРТФОНЫ СО СКИДКОЙ",
        "hashtag": "#смартфоны"
    },
    "наушники": {
        "keywords": [
            "наушники", "беспроводные наушники", "airpods", "headphones", "tws", 
            "harman", "jbl", "sony", "samsung buds", "huawei freebuds"
        ],
        "header": "🎧 НАУШНИКИ СО СКИДКОЙ",
        "hashtag": "#наушники"
    },
    "умный дом": {
        "keywords": [
            "умный дом", "умная колонка", "яндекс станция", "робот-пылесос", 
            "умная розетка", "датчик", "камера видеонаблюдения", "умный звонок"
        ],
        "header": "🏠 УМНЫЙ ДОМ СО СКИДКОЙ",
        "hashtag": "#умныйдом"
    },
    "ноутбуки": {
        "keywords": [
            "ноутбук", "laptop", "macbook", "ultrabook", "игровой ноутбук", 
            "asus", "lenovo", "hp", "acer", "dell", "msi"
        ],
        "header": "💻 НОУТБУКИ СО СКИДКОЙ",
        "hashtag": "#ноутбуки"
    },
    "часы": {
        "keywords": [
            "часы", "smart watch", "умные часы", "apple watch", "amazfit", 
            "garmin", "фитнес браслет", "huawei watch", "samsung watch"
        ],
        "header": "⌚️ УМНЫЕ ЧАСЫ СО СКИДКОЙ",
        "hashtag": "#умныечасы"
    },
    "витамины и бады": {
        "keywords": [
            "витамины", "бады", "омега-3", "магний", "витамин д", "витамин с",
            "комплекс витаминов", "коллаген", "цинк", "железо"
        ],
        "header": "💊 ВИТАМИНЫ И БАДЫ СО СКИДКОЙ",
        "hashtag": "#витамины"
    },
    "спортивное питание": {
        "keywords": [
            "протеин", "гейнер", "аминокислоты", "bcaa", "креатин", 
            "л-карнитин", "спортивное питание"
        ],
        "header": "💪 СПОРТИВНОЕ ПИТАНИЕ СО СКИДКОЙ",
        "hashtag": "#спортпит"
    },
    "товары для дома": {
        "keywords": [
            "пылесос", "чайник", "мультиварка", "утюг", "микроволновка", 
            "холодильник", "стиральная машина", "кофеварка", "блендер"
        ],
        "header": "🏡 ТОВАРЫ ДЛЯ ДОМА СО СКИДКОЙ",
        "hashtag": "#товарыдлядома"
    }
}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

SUPER_DISCOUNT_HEADERS = [
    "⚡️ СКИДКА {discount}%",
    "🔥 УСПЕЙ! -{discount}%",
    "💥 СУПЕР-СКИДКА {discount}%"
]

UNIVERSAL_HEADERS = [
    "🔥 ЛУЧШИЕ ПРЕДЛОЖЕНИЯ",
    "💰 ЭКОНОМИЯ ДО 70%",
    "⭐️ ТОП СКИДОК СЕГОДНЯ"
]

CTA = [
    "Нажми на ссылку, чтобы купить со скидкой!"
]

SEPARATOR = "─" * 30


def _random_header(max_discount: int = 0) -> str:
    if max_discount >= 70:
        return random.choice(SUPER_DISCOUNT_HEADERS).format(discount=max_discount)
    else:
        return random.choice(UNIVERSAL_HEADERS)


def _shorten_url(url: str) -> str:
    """Сокращает URL для отображения в VK, сохраняя CLID"""
    if not url:
        return ""
    clean_url = url.replace('https://', '').replace('http://', '')
    if len(clean_url) > 45:
        match = re.search(r'(market\.yandex\.ru/product/\d+)', clean_url)
        if match:
            base_short = match.group(1)
            clid_match = re.search(r'clid=(\d+)', clean_url)
            if clid_match:
                return f"{base_short}?clid={clid_match.group(1)}"
            return base_short
        clean_url = clean_url[:42] + "..."
    return clean_url


def format_rating(rating: float, count: int = None) -> str:
    """Форматирует рейтинг: одна звезда + цифра + количество отзывов"""
    if not rating or rating == 0:
        return "⭐ Нет отзывов"
    
    result = f"⭐ {rating}"
    if count and count > 0:
        result += f" ({count} отзывов)"
    
    return result


def _detect_category(product_name: str) -> Optional[str]:
    """Определяет категорию товара по ключевым словам"""
    product_lower = product_name.lower()
    for category, data in CATEGORIES.items():
        for keyword in data["keywords"]:
            if keyword.lower() in product_lower:
                return category
    return None


def _group_by_category(products: List[Dict]) -> Dict[str, List[Dict]]:
    """Группирует товары по категориям"""
    grouped = defaultdict(list)
    for product in products:
        category = _detect_category(product.get('name', ''))
        if category:
            grouped[category].append(product)
        else:
            grouped["разное"].append(product)
    return grouped


def _get_best_category(grouped: Dict[str, List[Dict]]) -> Tuple[Optional[str], List[Dict]]:
    """Выбирает лучшую категорию для публикации"""
    # Проверяем супер-скидки (70%+)
    super_discount_products = []
    for products in grouped.values():
        for p in products:
            if p.get('discount', 0) >= 70:
                super_discount_products.append(p)
    
    if super_discount_products:
        return "супер-скидки", super_discount_products
    
    # Выбираем категорию с максимальным количеством товаров
    best_category = None
    best_products = []
    best_count = 0
    
    for category, products in grouped.items():
        if len(products) > best_count:
            best_count = len(products)
            best_category = category
            best_products = products
    
    if best_category and best_products:
        return best_category, best_products
    
    return None, []


def _get_hashtags(category: str, max_discount: int = 0) -> str:
    """Возвращает хэштеги для поста"""
    base_hashtags = ["#скидки", "#яндексмаркет", "#выгодныепокупки"]
    
    if category in CATEGORIES:
        base_hashtags.append(CATEGORIES[category]["hashtag"])
    elif category == "супер-скидки":
        base_hashtags.append("#суперскидки")
    
    if max_discount >= 70:
        base_hashtags.append("#скидка70")
    elif max_discount >= 50:
        base_hashtags.append("#скидка50")
    
    return " ".join(base_hashtags)


def format_collection_post(products: List[Dict], category: str = None, include_promocode: bool = True) -> str:
    """
    Стильное оформление поста для VK с визуальными разделителями
    """
    if not products:
        return ""
    
    max_discount = max(p.get('discount', 0) for p in products)
    header = _random_header(max_discount)
    
    # БЛОК 1: ЗАГОЛОВОК + разделитель
    caption = f"{header}\n{SEPARATOR}\n\n"
    
    # БЛОК 2: ТОВАРЫ
    for i, product in enumerate(products, 1):
        name = product.get('name', 'Товар')
        price = product.get('price', 0)
        old_price = product.get('old_price', 0)
        discount = product.get('discount', 0)
        rating = product.get('rating', 0)
        rating_count = product.get('rating_count', 0)
        url = product.get('url', '')
        
        rating_text = format_rating(rating, rating_count)
        
        caption += f"📌 **{i}. {name}**\n"
        caption += f"   {rating_text}\n"
        caption += f"   💰 {old_price:,} ₽ → **{price:,} ₽** (-{discount}%)\n"
        
        if url:
            short_url = _shorten_url(url)
            caption += f"   🛒 {short_url}\n"
        
        caption += "\n"
    
    caption = caption.replace(',', ' ')
    
    # БЛОК 3: ПРОМОКОД (если есть) + разделитель
    if include_promocode:
        promocode = promocode_manager.get_random_promocode()
        if promocode:
            caption += f"{SEPARATOR}\n"
            caption += f"🎁 **Промокод:** {promocode['code']}\n"
            caption += f"   {promocode['description']}\n"
            caption += f"   ⏰ Действует до: {promocode['expires']}\n\n"
    
    # БЛОК 4: ПРИЗЫВ + разделитель
    caption += f"{SEPARATOR}\n"
    caption += f"👇 {random.choice(CTA)}\n\n"
    
    # БЛОК 5: ХЭШТЕГИ + разделитель
    hashtags = _get_hashtags(category, max_discount)
    caption += f"{SEPARATOR}\n"
    caption += f"{hashtags}\n\n"
    
    # БЛОК 6: ПРИЛОЖЕНИЕ
    caption += f"📱 Все скидки в приложении: vk.com/app{VK_APP_ID}"
    
    return caption


# ========== МОК-ДАННЫЕ ==========

MOCK_PRODUCTS = [
    {
        'id': 'mock_1',
        'name': 'Смарт-часы Amazfit GTR 4',
        'price': 6590,
        'old_price': 21990,
        'discount': 70,
        'rating': 4.7,
        'rating_count': 3400,
        'url': f'https://market.yandex.ru/product/234567?clid={VK_CLID}',
        'picture': None
    },
    {
        'id': 'mock_2',
        'name': 'Беспроводные наушники HUAWEI FreeBuds 6i',
        'price': 5990,
        'old_price': 11990,
        'discount': 50,
        'rating': 4.8,
        'rating_count': 2500,
        'url': f'https://market.yandex.ru/product/123456?clid={VK_CLID}',
        'picture': None
    },
    {
        'id': 'mock_3',
        'name': 'Робот-пылесос Xiaomi Robot Vacuum S20',
        'price': 18990,
        'old_price': 29990,
        'discount': 37,
        'rating': 4.6,
        'rating_count': 1890,
        'url': f'https://market.yandex.ru/product/345678?clid={VK_CLID}',
        'picture': None
    }
]


# ========== РЕАЛЬНЫЙ ПАРСЕР ==========

def get_products(min_discount: int = 30, limit: int = 30) -> List[Dict]:
    """Получает товары (мок или реальные)"""
    if MODE == "real" and VK_CLID:
        try:
            from shared.market_parser import YandexMarketParser
            parser = YandexMarketParser(VK_CLID, "rubles", MIN_RATING)
            products = parser.search_discounts(min_discount=min_discount, limit=limit)
            formatted = []
            for p in products:
                formatted.append({
                    'id': p.get('id', ''),
                    'name': p.get('name', ''),
                    'price': p.get('price', 0),
                    'old_price': p.get('old_price', 0),
                    'discount': p.get('discount', 0),
                    'rating': p.get('rating', 0),
                    'rating_count': p.get('rating_count', 0),
                    'url': p.get('url', ''),
                    'picture': p.get('picture')
                })
            return formatted
        except Exception as e:
            logger.error(f"Ошибка реального парсера: {e}")
            return MOCK_PRODUCTS[:limit]
    else:
        return MOCK_PRODUCTS[:limit]


# ========== ПУБЛИКАЦИЯ В VK ==========

def post_to_vk_wall(products: List[Dict], category: str = None, caption: str = None) -> bool:
    """Публикует подборку в VK-сообщество"""
    if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
        logger.warning("VK_ACCESS_TOKEN или VK_GROUP_ID не заданы")
        return False
    
    if not caption:
        caption = format_collection_post(products, category)
    
    if not caption:
        return False
    
    params = {
        'access_token': VK_ACCESS_TOKEN,
        'owner_id': f'-{VK_GROUP_ID}',
        'message': caption,
        'v': '5.131'
    }
    
    try:
        response = requests.post(
            'https://api.vk.com/method/wall.post',
            params=params,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'error' in data:
                logger.error(f"Ошибка VK API: {data['error']}")
                return False
            logger.info(f"✅ Опубликовано в VK: {len(products)} товаров")
            return True
        else:
            logger.error(f"Ошибка VK: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка публикации в VK: {e}")
        return False


async def post_promocode():
    """Публикует отдельный пост с промокодом"""
    promocode = promocode_manager.get_random_promocode()
    if not promocode:
        return False
    
    caption = promocode_manager.format_promocode_post(promocode)
    
    try:
        response = requests.post(
            'https://api.vk.com/method/wall.post',
            params={
                'access_token': VK_ACCESS_TOKEN,
                'owner_id': f'-{VK_GROUP_ID}',
                'message': caption,
                'v': '5.131'
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'error' in data:
                logger.error(f"Ошибка VK API: {data['error']}")
                return False
            logger.info(f"✅ Опубликован пост с промокодом: {promocode['code']}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка публикации промокода: {e}")
        return False


# ========== ФОНЕВАЯ ЗАДАЧА ==========

async def scheduled_posting():
    """Фоновая задача: публикует подборки и промокоды"""
    post_counter = 0
    last_promocode_post = 0
    
    while True:
        try:
            logger.info(f"🔍 VK API: проверка новых товаров...")
            products = get_products(MIN_DISCOUNT, 30)
            
            if products:
                grouped = _group_by_category(products)
                best_category, best_products = _get_best_category(grouped)
                
                if best_products:
                    best_products.sort(key=lambda x: x['discount'], reverse=True)
                    products_to_post = best_products[:MAX_PRODUCTS]
                    
                    include_promo = (post_counter % 3 == 0)
                    
                    caption = format_collection_post(products_to_post, best_category, include_promo)
                    success = post_to_vk_wall(products_to_post, best_category, caption)
                    
                    if success:
                        logger.info(f"✅ Опубликована подборка '{best_category}' из {len(products_to_post)} товаров")
                        post_counter += 1
                    else:
                        logger.warning("Не удалось опубликовать подборку")
                else:
                    logger.info("Не удалось определить категорию")
            else:
                logger.info("Новых товаров нет")
            
            if post_counter - last_promocode_post >= 5 and post_counter > 0:
                await post_promocode()
                last_promocode_post = post_counter
                
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче: {e}")
        
        await asyncio.sleep(POST_INTERVAL)


# ========== МОДЕЛИ ДАННЫХ ==========

class OfferResponse(BaseModel):
    id: str
    name: str
    price: int
    old_price: int
    discount: int
    rating: float
    url: str
    picture: Optional[str] = None


class DiscountsResponse(BaseModel):
    status: str
    count: int
    category: str
    offers: List[OfferResponse]


# ========== ЭНДПОИНТЫ API ==========

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduled_posting())
    logger.info(f"🚀 Фоновая задача запущена: публикация каждые {POST_INTERVAL//60} минут")


@app.get("/")
async def root():
    return {
        "name": "Скидки Маркета API",
        "version": "2.0.0",
        "status": "running",
        "mode": MODE,
        "post_interval_minutes": POST_INTERVAL // 60
    }


@app.get("/api/discounts", response_model=DiscountsResponse)
async def get_discounts(
    min_discount: int = MIN_DISCOUNT,
    limit: int = MAX_PRODUCTS,
    min_rating: float = MIN_RATING
):
    try:
        if limit > 10:
            limit = 10
        
        products = get_products(min_discount, 30)
        
        if min_rating > 0:
            products = [p for p in products if p.get('rating', 0) >= min_rating]
        
        grouped = _group_by_category(products)
        best_category, best_products = _get_best_category(grouped)
        
        if best_products:
            best_products.sort(key=lambda x: x['discount'], reverse=True)
            offers = best_products[:limit]
        else:
            offers = products[:limit]
        
        return {
            "status": "success",
            "count": len(offers),
            "category": best_category if best_category else "разное",
            "offers": offers
        }
        
    except Exception as e:
        logger.error(f"Ошибка в /api/discounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/post_now")
async def post_now(background_tasks: BackgroundTasks):
    products = get_products(MIN_DISCOUNT, 30)
    if products:
        grouped = _group_by_category(products)
        best_category, best_products = _get_best_category(grouped)
        if best_products:
            best_products.sort(key=lambda x: x['discount'], reverse=True)
            background_tasks.add_task(post_to_vk_wall, best_products[:MAX_PRODUCTS], best_category)
            return {"status": "success", "message": f"Публикация подборки '{best_category}' запущена"}
    return {"status": "error", "message": "Нет товаров для публикации"}


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "mode": MODE,
        "clid_configured": bool(VK_CLID)
    }


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Запуск VK Mini App Backend")
    print("=" * 50)
    print(f"📱 Режим: {MODE}")
    print(f"⏱ Автопостинг: каждые {POST_INTERVAL//60} минут")
    print(f"🎯 Скидка от: {MIN_DISCOUNT}%")
    print(f"⭐️ Рейтинг от: {MIN_RATING}")
    print("=" * 50)
    print("🌐 API: http://localhost:8000")
    print("📊 Скидки: http://localhost:8000/api/discounts")
    print("🏥 Здоровье: http://localhost:8000/api/health")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)