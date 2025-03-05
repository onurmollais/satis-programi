# -*- coding: utf-8 -*-
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
from events import Event, EVENT_DATA_UPDATED
from typing import Dict, Any, Optional

class WorkerSignals(QObject):
    """Worker sinyalleri için yardımcı sınıf"""
    tamamlandi = pyqtSignal()
    hata = pyqtSignal(str)
    result = pyqtSignal(dict)  # İşlem sonucunu döndürmek için ek sinyal

class SatisEklemeWorker(QRunnable):
    """
    Satış ekleme işlemlerini arka planda gerçekleştiren worker sınıfı.
    
    Bu sınıf, satış ekleme işlemlerini arka planda gerçekleştirerek
    kullanıcı arayüzünün donmasını engeller.
    """
    def __init__(self, yeni_satis: Dict[str, Any], services):
        """
        SatisEklemeWorker sınıfının constructor metodu.
        
        Args:
            yeni_satis (Dict[str, Any]): Eklenecek satış bilgileri
            services: Satış işlemlerini gerçekleştirecek servis nesnesi
        """
        super().__init__()
        self.yeni_satis = yeni_satis
        self.services = services
        self.signals = WorkerSignals()
        
    def run(self):
        """
        Thread çalıştırıldığında satış ekleme işlemini gerçekleştirir.
        """
        try:
            # Satış ekleme işlemini gerçekleştir
            self.services.add_sale(self.yeni_satis)
            self.signals.result.emit({"success": True})
            self.signals.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Satış ekleme hatası: {str(e)}"
            self.signals.hata.emit(hata_mesaji)


class ZiyaretEklemeWorker(QRunnable):
    """
    Ziyaret ekleme işlemlerini arka planda gerçekleştiren worker sınıfı.
    
    Bu sınıf, ziyaret ekleme işlemlerini arka planda gerçekleştirerek
    kullanıcı arayüzünün donmasını engeller.
    """
    def __init__(self, services, yeni_ziyaret: Dict[str, Any]):
        """
        ZiyaretEklemeWorker sınıfının constructor metodu.
        
        Args:
            services: Ziyaret işlemlerini gerçekleştirecek servis nesnesi
            yeni_ziyaret (Dict[str, Any]): Eklenecek ziyaret bilgileri
        """
        super().__init__()
        self.services = services
        self.yeni_ziyaret = yeni_ziyaret
        self.signals = WorkerSignals()
        
    def run(self):
        """
        Thread çalıştırıldığında ziyaret ekleme işlemini gerçekleştirir.
        """
        try:
            # Ziyaret ekleme işlemini gerçekleştir
            self.services.add_visit(self.yeni_ziyaret)
            self.signals.result.emit({"success": True})
            self.signals.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Ziyaret ekleme hatası: {str(e)}"
            self.signals.hata.emit(hata_mesaji)


class SatisSilmeWorker(QRunnable):
    """
    Satış silme işlemlerini arka planda gerçekleştiren worker sınıfı.
    
    Bu sınıf, satış silme işlemlerini arka planda gerçekleştirerek
    kullanıcı arayüzünün donmasını engeller.
    """
    def __init__(self, services, satis_index: int):
        """
        SatisSilmeWorker sınıfının constructor metodu.
        
        Args:
            services: Satış işlemlerini gerçekleştirecek servis nesnesi
            satis_index (int): Silinecek satışın indeksi
        """
        super().__init__()
        self.services = services
        self.satis_index = satis_index
        self.signals = WorkerSignals()
        
    def run(self):
        """
        Thread çalıştırıldığında satış silme işlemini gerçekleştirir.
        """
        try:
            # Satış silme işlemini gerçekleştir
            if hasattr(self.services, 'delete_sale'):
                self.services.delete_sale(self.satis_index)
            else:
                # Eğer delete_sale metodu yoksa, data_manager üzerinden silme işlemi yap
                if self.services.data_manager.satislar_df is not None and not self.services.data_manager.satislar_df.empty:
                    self.services.data_manager.satislar_df = self.services.data_manager.satislar_df.drop(self.satis_index).reset_index(drop=True)
                    self.services.data_manager.repository.save(self.services.data_manager.satislar_df, "sales")
                    if self.services.data_manager.event_manager:
                        self.services.data_manager.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_sil"}))
            
            self.signals.result.emit({"success": True})
            self.signals.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Satış silme hatası: {str(e)}"
            self.signals.hata.emit(hata_mesaji)


class ZiyaretSilmeWorker(QRunnable):
    """
    Ziyaret silme işlemlerini arka planda gerçekleştiren worker sınıfı.
    
    Bu sınıf, ziyaret silme işlemlerini arka planda gerçekleştirerek
    kullanıcı arayüzünün donmasını engeller.
    """
    def __init__(self, services, ziyaret_index: int):
        """
        ZiyaretSilmeWorker sınıfının constructor metodu.
        
        Args:
            services: Ziyaret işlemlerini gerçekleştirecek servis nesnesi
            ziyaret_index (int): Silinecek ziyaretin indeksi
        """
        super().__init__()
        self.services = services
        self.ziyaret_index = ziyaret_index
        self.signals = WorkerSignals()
        
    def run(self):
        """
        Thread çalıştırıldığında ziyaret silme işlemini gerçekleştirir.
        """
        try:
            # Ziyaret silme işlemini gerçekleştir
            if hasattr(self.services, 'delete_visit'):
                self.services.delete_visit(self.ziyaret_index)
            else:
                # Eğer delete_visit metodu yoksa, data_manager üzerinden silme işlemi yap
                if self.services.data_manager.ziyaretler_df is not None and not self.services.data_manager.ziyaretler_df.empty:
                    self.services.data_manager.ziyaretler_df = self.services.data_manager.ziyaretler_df.drop(self.ziyaret_index).reset_index(drop=True)
                    self.services.data_manager.repository.save(self.services.data_manager.ziyaretler_df, "visits")
                    if self.services.data_manager.event_manager:
                        self.services.data_manager.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "ziyaret_sil"}))
            
            self.signals.result.emit({"success": True})
            self.signals.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Ziyaret silme hatası: {str(e)}"
            self.signals.hata.emit(hata_mesaji)