import socket
import requests
import logging
from typing import Optional
from events import Event, EventManager

class InternetBaglantisi:
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager: Optional[EventManager] = None):
        self.loglayici = loglayici or logging.getLogger(__name__)
        self.event_manager = event_manager
        self.offline_mod = False
        
    def offline_moda_gec(self):
        """Programi offline moda gecirir"""
        self.offline_mod = True
        self.loglayici.info("Program offline moda gecti")
        if self.event_manager:
            self.event_manager.emit(Event("InternetBaglanti", {
                "status": "offline_mod",
                "message": "Program offline modda calisiyor"
            }))
            
    def online_moda_gec(self):
        """Programi online moda gecirir"""
        self.offline_mod = False
        self.loglayici.info("Program online moda gecti")
        if self.event_manager:
            self.event_manager.emit(Event("InternetBaglanti", {
                "status": "online_mod",
                "message": "Program online modda calisiyor"
            }))
        
    def baglanti_kontrol(self) -> bool:
        """Internet baglantisini kontrol eder"""
        if self.offline_mod:
            return False
            
        try:
            # DNS sunucusuna baglanti kontrolu
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            # HTTP istegi ile baglanti testi
            requests.get("http://www.google.com", timeout=3)
            
            if self.event_manager:
                self.event_manager.emit(Event("InternetBaglanti", {"status": "bagli"}))
            
            self.loglayici.info("Internet baglantisi basarili")
            return True
            
        except (socket.error, requests.RequestException) as e:
            hata_mesaji = f"Internet baglantisi hatasi: {str(e)}"
            self.loglayici.error(hata_mesaji)
            
            if self.event_manager:
                self.event_manager.emit(Event("InternetBaglanti", {
                    "status": "baglanti_yok",
                    "hata": hata_mesaji
                }))
            
            return False
            
    def baglanti_bekle(self, max_deneme: int = 3, bekleme_suresi: int = 5) -> bool:
        """Internet baglantisi kurulana kadar bekler"""
        if self.offline_mod:
            return False
            
        import time
        deneme = 0
        
        while deneme < max_deneme:
            if self.baglanti_kontrol():
                return True
                
            deneme += 1
            self.loglayici.warning(f"Internet baglantisi bekleniyor... Deneme {deneme}/{max_deneme}")
            time.sleep(bekleme_suresi)
            
        # Baglanti kurulamadi, offline moda gec
        self.offline_moda_gec()
        return False 
