# -*- coding: utf-8 -*-
from PyQt6.QtCore import QThread, pyqtSignal
from events import Event, EVENT_DATA_UPDATED
from typing import Dict, Any, Optional

class SatisEklemeWorker(QThread):
    """
    Satis ekleme islemlerini arka planda gerceklestiren worker sinifi.
    
    Bu sinif, satis ekleme islemlerini arka planda gerceklestirerek
    kullanici arayuzunun donmasini engeller.
    
    Attributes:
        tamamlandi (pyqtSignal): Islem tamamlandiginda tetiklenen sinyal
        hata (pyqtSignal): Hata durumunda tetiklenen sinyal
    """
    tamamlandi = pyqtSignal()
    hata = pyqtSignal(str)
    
    def __init__(self, yeni_satis: Dict[str, Any], services):
        """
        SatisEklemeWorker sinifinin constructor metodu.
        
        Args:
            yeni_satis (Dict[str, Any]): Eklenecek satis bilgileri
            services: Satis islemlerini gerceklestirecek servis nesnesi
        """
        super().__init__()
        self.yeni_satis = yeni_satis
        self.services = services
        
    def run(self):
        """
        Thread calistiginda satis ekleme islemini gerceklestirir.
        """
        try:
            # Satis ekleme islemini gerceklestir
            self.services.add_sale(self.yeni_satis)
            self.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Satis ekleme hatasi: {str(e)}"
            self.hata.emit(hata_mesaji)


class ZiyaretEklemeWorker(QThread):
    """
    Ziyaret ekleme islemlerini arka planda gerceklestiren worker sinifi.
    
    Bu sinif, ziyaret ekleme islemlerini arka planda gerceklestirerek
    kullanici arayuzunun donmasini engeller.
    
    Attributes:
        tamamlandi (pyqtSignal): Islem tamamlandiginda tetiklenen sinyal
        hata (pyqtSignal): Hata durumunda tetiklenen sinyal
    """
    tamamlandi = pyqtSignal()
    hata = pyqtSignal(str)
    
    def __init__(self, services, yeni_ziyaret: Dict[str, Any]):
        """
        ZiyaretEklemeWorker sinifinin constructor metodu.
        
        Args:
            services: Ziyaret islemlerini gerceklestirecek servis nesnesi
            yeni_ziyaret (Dict[str, Any]): Eklenecek ziyaret bilgileri
        """
        super().__init__()
        self.services = services
        self.yeni_ziyaret = yeni_ziyaret
        
    def run(self):
        """
        Thread calistiginda ziyaret ekleme islemini gerceklestirir.
        """
        try:
            # Ziyaret ekleme islemini gerceklestir
            self.services.add_visit(self.yeni_ziyaret)
            self.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Ziyaret ekleme hatasi: {str(e)}"
            self.hata.emit(hata_mesaji)


class SatisSilmeWorker(QThread):
    """
    Satis silme islemlerini arka planda gerceklestiren worker sinifi.
    
    Bu sinif, satis silme islemlerini arka planda gerceklestirerek
    kullanici arayuzunun donmasini engeller.
    
    Attributes:
        tamamlandi (pyqtSignal): Islem tamamlandiginda tetiklenen sinyal
        hata (pyqtSignal): Hata durumunda tetiklenen sinyal
    """
    tamamlandi = pyqtSignal()
    hata = pyqtSignal(str)
    
    def __init__(self, services, satis_index: int):
        """
        SatisSilmeWorker sinifinin constructor metodu.
        
        Args:
            services: Satis islemlerini gerceklestirecek servis nesnesi
            satis_index (int): Silinecek satisin indeksi
        """
        super().__init__()
        self.services = services
        self.satis_index = satis_index
        
    def run(self):
        """
        Thread calistiginda satis silme islemini gerceklestirir.
        """
        try:
            # Satis silme islemini gerceklestir
            # Not: Servis sinifinda delete_sale metodu eklenmeli
            if hasattr(self.services, 'delete_sale'):
                self.services.delete_sale(self.satis_index)
            else:
                # Eger delete_sale metodu yoksa, data_manager uzerinden silme islemi yap
                if self.services.data_manager.satislar_df is not None and not self.services.data_manager.satislar_df.empty:
                    self.services.data_manager.satislar_df = self.services.data_manager.satislar_df.drop(self.satis_index).reset_index(drop=True)
                    self.services.data_manager.repository.save(self.services.data_manager.satislar_df, "sales")
                    if self.services.data_manager.event_manager:
                        self.services.data_manager.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_sil"}))
            
            self.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Satis silme hatasi: {str(e)}"
            self.hata.emit(hata_mesaji)


class ZiyaretSilmeWorker(QThread):
    """
    Ziyaret silme islemlerini arka planda gerceklestiren worker sinifi.
    
    Bu sinif, ziyaret silme islemlerini arka planda gerceklestirerek
    kullanici arayuzunun donmasini engeller.
    
    Attributes:
        tamamlandi (pyqtSignal): Islem tamamlandiginda tetiklenen sinyal
        hata (pyqtSignal): Hata durumunda tetiklenen sinyal
    """
    tamamlandi = pyqtSignal()
    hata = pyqtSignal(str)
    
    def __init__(self, services, ziyaret_index: int):
        """
        ZiyaretSilmeWorker sinifinin constructor metodu.
        
        Args:
            services: Ziyaret islemlerini gerceklestirecek servis nesnesi
            ziyaret_index (int): Silinecek ziyaretin indeksi
        """
        super().__init__()
        self.services = services
        self.ziyaret_index = ziyaret_index
        
    def run(self):
        """
        Thread calistiginda ziyaret silme islemini gerceklestirir.
        """
        try:
            # Ziyaret silme islemini gerceklestir
            # Not: Servis sinifinda delete_visit metodu eklenmeli
            if hasattr(self.services, 'delete_visit'):
                self.services.delete_visit(self.ziyaret_index)
            else:
                # Eger delete_visit metodu yoksa, data_manager uzerinden silme islemi yap
                if self.services.data_manager.ziyaretler_df is not None and not self.services.data_manager.ziyaretler_df.empty:
                    self.services.data_manager.ziyaretler_df = self.services.data_manager.ziyaretler_df.drop(self.ziyaret_index).reset_index(drop=True)
                    self.services.data_manager.repository.save(self.services.data_manager.ziyaretler_df, "visits")
                    if self.services.data_manager.event_manager:
                        self.services.data_manager.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "ziyaret_sil"}))
            
            self.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Ziyaret silme hatasi: {str(e)}"
            self.hata.emit(hata_mesaji) 