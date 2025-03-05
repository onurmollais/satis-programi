# -*- coding: utf-8 -*-
import schedule
import time
import threading
import logging  # Logging modulu eklendi
from typing import Optional  # Type hints icin

HATA_KODLARI = {  # zamanlayici.py icin ozel hata kodlari
    "ZAMANLAYICI_001": "Zamanlayici calisma hatasi"
}

class Zamanlayici:
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager=None):  # EventManager eklendi
        self.stop_flag = threading.Event()
        self.loglayici = loglayici
        self.event_manager = event_manager  # Olay yoneticisi eklendi
        self.thread = None

    def baslat(self):
        self.thread = threading.Thread(target=self.zamanlayici_calistir)  # Thread'i nesneye ata # Thread kontrolu icin
        self.thread.start()

    def durdur(self):
        self.stop_flag.set()
        if self.thread and self.thread.is_alive():  # Thread'in kapanmasini bekle
            self.thread.join(timeout=5)  # 5 saniye bekle
            if self.loglayici:
                self.loglayici.info("Zamanlayici thread'i durduruldu.")

    def zamanlayici_calistir(self) -> None:
        hata_sayaci = 0
        while not self.stop_flag.is_set():
            try:
                schedule.run_pending()
                time.sleep(1)
                hata_sayaci = 0
            except Exception as e:
                hata_sayaci += 1
                hata_mesaji = f"Zamanlayici hatasi: {str(e)} Hata Kodu: ZAMANLAYICI_001, Hata Sayaci: {hata_sayaci}"
                if self.loglayici:
                    self.loglayici.error(hata_mesaji)
                if hata_sayaci > 5:
                    if self.loglayici:
                        self.loglayici.critical("Zamanlayici tekrarlanan hatalar nedeniyle durduruluyor.")
                    self.stop_flag.set()  # Durduruldugunu bildir
                    break
                time.sleep(5)

    def is_ekle(self, islem, interval):
        schedule.every(interval).seconds.do(islem)

    # zamanlayici.py icine eklenecek burasi yeni eklendi

    def yedekleme_zamanla(self, backup_manager, database_path, interval_hours=24):
        if not isinstance(interval_hours, (int, float)) or interval_hours <= 0:
            hata_mesaji = "Interval saat pozitif bir sayi olmali"
            if self.loglayici:
                self.loglayici.error(hata_mesaji)
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": hata_mesaji}))
            raise ValueError(hata_mesaji)
        
        def yedekleme_yap():
            success, result = backup_manager.create_backup(database_path)
            if success and self.loglayici:
                self.loglayici.info(f"Otomatik yedekleme basarili: {result}")
            elif self.loglayici:
                self.loglayici.error(f"Otomatik yedekleme hatasi: {result}")
            # Yedekleme tamamlandi olayi zaten BackupManagerda tetikleniyor
        
        self.is_ekle(yedekleme_yap, interval_hours * 3600)

    #burasi yeni eklendi
