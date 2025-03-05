# events.py
# -*- coding: utf-8 -*-
"""
Olay yonetimi modulu.

Bu modul, uygulama genelinde olay tabanli iletisimi saglar. Olaylarin olusturulmasi,
yayinlanmasi ve dinlenmesi islemlerini yonetir.

Olay tipleri:
    - EVENT_DATA_UPDATED: Veri guncelleme olayi
    - EVENT_UI_UPDATED: Arayuz guncelleme olayi
    - EVENT_ERROR_OCCURRED: Hata olayi
    - EVENT_LOADING_PROGRESS: Veri yukleme ilerleme olayi
    - EVENT_LOADING_COMPLETED: Veri yukleme tamamlanma olayi
    - EVENT_LOADING_ERROR: Veri yukleme hatasi olayi
    - EVENT_BACKUP_COMPLETED: Yedekleme tamamlanma olayi
"""

from typing import Callable, Dict, List, Any
import logging

EVENT_DATA_UPDATED = "data_updated"
EVENT_UI_UPDATED = "ui_updated"
EVENT_ERROR_OCCURRED = "error_occurred"
EVENT_LOADING_PROGRESS = "loading_progress"  # Veri yukleme ilerleme durumu
EVENT_LOADING_COMPLETED = "loading_completed"  # Veri yukleme tamamlandi
EVENT_LOADING_ERROR = "loading_error"  # Veri yukleme hatasi

class Event:
    """
    Olay sinifi.
    
    Uygulamada meydana gelen olaylari temsil eder. Her olay bir isim ve
    ilgili veri tasir.
    
    Attributes:
        name: Olayin benzersiz ismi
        data: Olay ile ilgili tasÄ±nan veri
    """
    
    def __init__(self, name: str, data: Any = None):
        """
        Args:
            name: Olay ismi
            data: Olay ile ilgili veri (varsayilan: None)
        """
        self.name = name
        self.data = data

class EventManager:
    """
    Olay yonetim sinifi.
    
    Uygulamadaki olaylari yonetir. Olaylarin dinleyicilere dagitilmasi,
    dinleyicilerin kaydedilmesi ve silinmesi islemlerini gerceklestirir.
    
    Methods:
        subscribe(): Olay dinleyici kaydeder
        unsubscribe(): Olay dinleyici kaydini siler
        unsubscribe_all(): Tum dinleyicileri siler
        emit(): Olayi yayinlar
    """
    
    def __init__(self, logger: logging.Logger = None):
        """
        Args:
            logger: Loglama islemleri icin logger nesnesi
        """
        self._subscribers: Dict[str, List[Callable]] = {}
        self.logger = logger or logging.getLogger(__name__)
        
    def subscribe(self, event_name: str, callback: Callable) -> None:
        """
        Belirtilen olaya dinleyici ekler.
        
        Args:
            event_name: Dinlenecek olay ismi
            callback: Olay gerceklestiginde cagrilacak fonksiyon
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)
            
    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """
        Belirtilen olay dinleyicisini kaldirir.
        
        Args:
            event_name: Dinleyicinin kaldirilacagi olay ismi
            callback: Kaldirilacak dinleyici fonksiyon
        """
        if event_name in self._subscribers and callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)
            
    def unsubscribe_all(self) -> None:
        """Tum olay dinleyicilerini kaldirir."""
        self._subscribers.clear()
        
    def emit(self, event: Event) -> None:
        """
        Olayi tum dinleyicilere yayinlar.
        
        Args:
            event: Yayinlanacak olay nesnesi
        """
        if event.name in self._subscribers:
            for callback in self._subscribers[event.name]:
                try:
                    callback(event)
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Event isleme hatasi: {str(e)}")

# Olay turleri (ornek, genisletilebilir)
EVENT_BACKUP_COMPLETED = "BackupCompleted"  # Yedekleme tamamlandiginda
