# -*- coding: utf-8 -*-
import logging
from logging.handlers import TimedRotatingFileHandler  # Zaman bazli rotasyon icin eklendi
import os
import zipfile  # Arsivleme icin eklendi
from datetime import datetime
from typing import Optional  # Type hints icin


HATA_KODLARI = {  # gunlukleyici.py icin ozel hata kodlari
    "ARSIV_001": "Eski gunluk dosyalari arsivleme hatasi"
}

def arsivle_eski_dosyalar(log_dosyasi):
    arsiv_adi = f"crm_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    try:
        with zipfile.ZipFile(arsiv_adi, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for dosya in os.listdir():
                if dosya.startswith('crm_log.log.') and dosya.endswith('.log'):
                    zipf.write(dosya)
                    os.remove(dosya)
        return arsiv_adi
    except Exception as e:
        hata_mesaji = f"Eski gunluk dosyalari arsivlenemedi: {str(e)} Hata Kodu: ARSIV_001"
        print(hata_mesaji)  # Konsola yazdir
        try:
            logging.getLogger('crm_logger').error(hata_mesaji)  # Logger hazirsa logla
        except:
            pass  # Logger henuz hazir degilse sessizce gec
        raise

def loglayici_olustur(log_dosyasi: str = "crm_log.log", event_manager=None) -> logging.Logger:  # EventManager eklendi
    logger = logging.getLogger('crm_logger')
    if logger.hasHandlers():  # Mevcut handler'lari temizle
        logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    file_handler = TimedRotatingFileHandler(
        'crm_log.log',
        when='midnight',
        interval=1,
        backupCount=7
    )
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Arsivlemeyi her calismada yap
    arsiv_adi = arsivle_eski_dosyalar('crm_log.log')
    logger.info(f"Eski gunluk dosyalari arsivlendi: {arsiv_adi}")
    if event_manager:
        event_manager.emit(Event(EVENT_BACKUP_COMPLETED, {"backup_file": arsiv_adi}))  # Arsivleme tamamlandi olayi
    
    return logger
