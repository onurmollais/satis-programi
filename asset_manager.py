import os
import json
import requests
import logging
from pathlib import Path
from typing import Dict, List, Optional
from events import Event, EventManager

class AssetManager:
    """
    Asset dosyalarini yoneten sinif.
    
    Bu sinif, uygulamanin ihtiyac duydugu harici kaynaklari (JS, CSS, veri dosyalari vb.)
    yonetir. Dosyalarin varligini kontrol eder, gerektiginde indirir ve yerel erisim
    saglar.
    
    Attributes:
        ASSETS (Dict): Yonetilen asset'lerin listesi ve konfigurasyonu
            - url: Indirme kaynagi
            - path: Yerel kayit yolu
            - local_fallback: Cevrimdisi kullanim icin yedek dosya
            
    Methods:
        check_and_download_assets(): Tum asset'leri kontrol eder ve gerekirse indirir
        get_asset_path(): Belirtilen asset'in yerel yolunu dondurur
    """
    
    ASSETS = {
        "plotly": {
            "url": "https://cdn.plot.ly/plotly-3.0.1.min.js",
            "path": "assets/js/plotly.min.js",
            "local_fallback": "assets/js/plotly.min.js"
        },
        "turkey_geojson": {
            "url": "https://raw.githubusercontent.com/cihadturhan/tr-geojson/master/geo/tr-cities-utf8.json",
            "path": "assets/data/turkey.geojson",
            "local_fallback": "assets/data/turkey.geojson"
        }
    }
    
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager: Optional[EventManager] = None):
        """
        AssetManager sinifinin kurucu metodu.
        
        Args:
            loglayici: Loglama islemleri icin logger nesnesi
            event_manager: Olay yonetimi icin EventManager nesnesi
        """
        self.loglayici = loglayici or logging.getLogger(__name__)
        self.event_manager = event_manager
        
    def _create_directories(self) -> None:
        """
        Asset dosyalari icin gerekli dizin yapisini olusturur.
        Var olan dizinler tekrar olusturulmaz.
        """
        directories = ["assets/js", "assets/css", "assets/data", "assets/themes"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            
    def _download_file(self, url: str, path: str) -> bool:
        """
        Belirtilen URL'den dosyayi indirir ve yerel diske kaydeder.
        
        Args:
            url: Indirilecek dosyanin URL'i
            path: Dosyanin kaydedilecegi yerel yol
            
        Returns:
            bool: Indirme islemi basarili ise True, degilse False
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            with open(path, 'wb') as f:
                f.write(response.content)
                
            self.loglayici.info(f"Dosya indirildi: {path}")
            return True
        except Exception as e:
            self.loglayici.error(f"Dosya indirme hatasi ({url}): {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("AssetError", {
                    "message": f"Dosya indirilemedi: {path}",
                    "error": str(e)
                }))
            return False
            
    def check_and_download_assets(self) -> bool:
        """Asset dosyalarinin varligini kontrol eder ve eksik olanlari indirir.
        Indirme basarisiz olursa yerel dosyalari kullanir."""
        try:
            self._create_directories()
            
            for asset_name, asset_info in self.ASSETS.items():
                asset_path = asset_info["path"]
                if not os.path.exists(asset_path):
                    self.loglayici.info(f"Asset dosyasi eksik, indiriliyor: {asset_name}")
                    if not self._download_file(asset_info["url"], asset_path):
                        # Indirme basarisiz olduysa yerel dosyayi kontrol et
                        local_path = asset_info["local_fallback"]
                        if os.path.exists(local_path):
                            self.loglayici.info(f"Indirme basarisiz, yerel dosya kullaniliyor: {local_path}")
                            if local_path != asset_path:
                                # Yerel dosyayi hedef konuma kopyala
                                import shutil
                                shutil.copy2(local_path, asset_path)
                        else:
                            self.loglayici.error(f"Asset dosyasi bulunamadi: {asset_name}")
                            if self.event_manager:
                                self.event_manager.emit(Event("AssetError", {
                                    "message": f"Asset dosyasi bulunamadi: {asset_name}",
                                    "error": "Indirme basarisiz ve yerel dosya mevcut degil"
                                }))
                            return False
                        
            self.loglayici.info("Tum asset dosyalari hazir")
            return True
            
        except Exception as e:
            self.loglayici.error(f"Asset kontrolu sirasinda hata: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("AssetError", {
                    "message": "Asset dosyalari kontrol edilirken hata olustu",
                    "error": str(e)
                }))
            return False
            
    def get_asset_path(self, asset_name: str) -> Optional[str]:
        """Asset dosyasinin yolunu dondurur"""
        if asset_name in self.ASSETS:
            return self.ASSETS[asset_name]["path"]
        return None 
