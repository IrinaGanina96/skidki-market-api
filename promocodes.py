# vk_miniapp/backend/promocodes.py
"""
Модуль для работы с промокодами Яндекс Маркета
"""

import random
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PromocodeManager:
    """Управление промокодами"""
    
    def __init__(self):
        self.promocodes = []
        self.last_update = None
        self._init_mock_promocodes()
    
    def _init_mock_promocodes(self):
        """Инициализация тестовых промокодов"""
        today = datetime.now()
        self.promocodes = [
            {
                'id': 'promo_1',
                'code': 'SKIDKA20',
                'description': 'Скидка 20% на первый заказ в приложении Яндекс Маркет',
                'shop': 'Яндекс Маркет',
                'expires': (today + timedelta(days=30)).strftime('%d.%m.%Y'),
                'link': 'https://market.yandex.ru/promo/skidka20',
                'type': 'welcome',
                'discount': 20
            },
            {
                'id': 'promo_2',
                'code': 'PLUS10',
                'description': 'Дополнительная скидка 10% для подписчиков Яндекс Плюс',
                'shop': 'Яндекс Маркет',
                'expires': (today + timedelta(days=15)).strftime('%d.%m.%Y'),
                'link': 'https://market.yandex.ru/promo/plus10',
                'type': 'plus',
                'discount': 10
            },
            {
                'id': 'promo_3',
                'code': 'FREESHIP',
                'description': 'Бесплатная доставка при заказе от 2000 ₽',
                'shop': 'Яндекс Маркет',
                'expires': (today + timedelta(days=7)).strftime('%d.%m.%Y'),
                'link': 'https://market.yandex.ru/promo/freeship',
                'type': 'delivery',
                'discount': None
            },
            {
                'id': 'promo_4',
                'code': 'TECH30',
                'description': 'Скидка 30% на электронику при заказе от 10 000 ₽',
                'shop': 'Яндекс Маркет',
                'expires': (today + timedelta(days=10)).strftime('%d.%m.%Y'),
                'link': 'https://market.yandex.ru/promo/tech30',
                'type': 'category',
                'discount': 30
            }
        ]
    
    def get_active_promocodes(self) -> List[Dict]:
        """Возвращает актуальные промокоды"""
        active = []
        today = datetime.now()
        
        for p in self.promocodes:
            try:
                expires = datetime.strptime(p['expires'], '%d.%m.%Y')
                if expires >= today:
                    active.append(p)
            except:
                active.append(p)
        
        return active
    
    def get_random_promocode(self) -> Optional[Dict]:
        """Возвращает случайный промокод для добавления в пост"""
        active = self.get_active_promocodes()
        if active:
            return random.choice(active)
        return None
    
    def get_promocode_by_type(self, promo_type: str) -> Optional[Dict]:
        """Возвращает промокод по типу"""
        active = self.get_active_promocodes()
        for p in active:
            if p.get('type') == promo_type:
                return p
        return None
    
    def should_post_promocode(self) -> bool:
        """Определяет, нужно ли публиковать отдельный пост с промокодом"""
        return len(self.get_active_promocodes()) > 0
    
    def format_promocode_post(self, promocode: Dict) -> str:
        """Форматирует отдельный пост с промокодом"""
        caption = "🎁 **ПРОМОКОД ДНЯ!**\n\n"
        caption += f"**{promocode['code']}**\n"
        caption += f"{promocode['description']}\n\n"
        
        if promocode.get('discount'):
            caption += f"💰 Скидка: {promocode['discount']}%\n"
        
        caption += f"📅 Действует до: {promocode['expires']}\n"
        caption += f"🛍 Магазин: {promocode['shop']}\n\n"
        caption += f"🔗 Активировать: {promocode['link']}\n\n"
        caption += "👇 Не упусти выгоду!"
        
        return caption
    
    def format_promocode_block(self, promocode: Dict) -> str:
        """Форматирует блок с промокодом для вставки в обычный пост"""
        text = f"\n🎁 **Промокод:** `{promocode['code']}`\n"
        text += f"   {promocode['description']}\n"
        text += f"   ⏰ Действует до: {promocode['expires']}\n"
        return text


# Создаем глобальный экземпляр
promocode_manager = PromocodeManager()