"""
CRM (Musteri Iliskileri Yonetimi) Uygulamasi

Bu modul, CRM uygulamasinin ana giris noktasini ve temel yapilandirmasini icerir.
Uygulama baslatma, gerekli servislerin ve yoneticilerin olusturulmasi ve
hata yonetimi islemlerini gerceklestirir.

Ozellikler:
    - Olay tabanli mimari (Event-driven architecture)
    - Otomatik yedekleme sistemi
    - Asset yonetimi
    - Hata izleme ve raporlama
    - Veritabani optimizasyonu
    - Hassas veri sifreleme
"""

# -*- coding: utf-8 -*-
import sys
import logging
from PyQt6.QtWidgets import QApplication, QGroupBox
from kullanici_arayuzu import AnaPencere
from veritabani import SQLiteRepository, BackupManager
from zamanlayici import Zamanlayici
from gunlukleyici import loglayici_olustur
from veri_yoneticisi import VeriYoneticisi
from services import CRMServices
from events import EventManager, Event, EVENT_DATA_UPDATED, EVENT_ERROR_OCCURRED
from asset_manager import AssetManager
from error_manager import ErrorManager
from sifreleme import SifrelemeYoneticisi
from dotenv import load_dotenv
import os
from ui_interface import UIInterface

# Uygulama seviyesi hata kodlari
HATA_KODLARI = {
    "BASLATMA_001": "Uygulama baslatma hatasi"
}

def main() -> int:
    """
    Ana uygulama fonksiyonu. Tum sistem bilesenlerini baslatir ve yonetir.
    
    Returns:
        int: Uygulama cikis kodu. 0 basarili, 1 hata durumu
    
    Islemler:
        1. Ortam degiskenlerini yukle
        2. Loglama sistemini baslatir
        3. Olay yonetim sistemini olusturur
        4. Asset kontrolu ve indirme islemlerini gerceklestirir
        5. Veritabani baglantisini kurar
        6. Servis katmanini olusturur
        7. Kullanici arayuzunu baslatir
        8. Zamanlayiciyi aktif hale getirir
    """
    try:
        # Ortam degiskenlerini yukle
        load_dotenv()
        
        # Loglayici olustur
        loglayici = loglayici_olustur()
        loglayici.setLevel(logging.INFO)
        
        # Olay yoneticisi olustur
        event_manager = EventManager(loglayici)
        
        # Asset Manager olustur ve asset'leri kontrol et
        asset_manager = AssetManager(loglayici, event_manager)
        asset_manager.check_and_download_assets()
        
        # Sifreleme yoneticisi olustur
        sifreleme = SifrelemeYoneticisi(loglayici, event_manager)
        
        # Veritabani baglantisi olustur
        repository = SQLiteRepository(
            db_path=os.getenv("DATABASE_PATH", "crm_database.db"),
            event_manager=event_manager
        )
        
        # Yedekleme yoneticisi olustur
        backup_manager = BackupManager(
            backup_dir=os.getenv("BACKUP_DIR", "backups"),
            event_manager=event_manager,
            sifreleme_yoneticisi=sifreleme
        )
        
        # Veri yoneticisi olustur
        veri_yoneticisi = VeriYoneticisi(repository, loglayici, event_manager)
        
        # Zamanlayici olustur
        zamanlayici = Zamanlayici(loglayici, event_manager)
        
        # Otomatik yedeklemeyi ayarla
        yedekleme_suresi = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
        zamanlayici.yedekleme_zamanla(backup_manager, repository.db_path, yedekleme_suresi)
        
        # Qt uygulamasini baslat
        uygulama = QApplication(sys.argv)
        loglayici.info("Uygulama baslatiliyor...")

        repository.optimize()
        
        services = CRMServices(veri_yoneticisi, loglayici, event_manager)
        
        pencere = AnaPencere(services=services, zamanlayici=zamanlayici, loglayici=loglayici, event_manager=event_manager)
        pencere.show()
        
        zamanlayici.baslat()
        
        loglayici.info("Uygulama basariyla baslatildi.")
        loglayici.setLevel(logging.DEBUG)
        return uygulama.exec()
    except Exception as e:
        loglayici.error(f"Uygulama baslatma hatasi: {str(e)}")
        return 1
    finally:
        if 'repository' in locals() and repository is not None:
            try:
                repository.close()
            except Exception as e:
                event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": f"Veritabani kapatilirken hata: {str(e)}"}))
        if 'zamanlayici' in locals() and zamanlayici is not None:
            try:
                zamanlayici.durdur()
            except Exception as e:
                event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": f"Zamanlayici durdurulurken hata: {str(e)}"}))

if __name__ == "__main__":
    sys.exit(main())
