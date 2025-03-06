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
    def __init__(self, services, yeni_satis):
        super().__init__()
        self.services = services
        self.yeni_satis = yeni_satis
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.services.data_manager.add_sale(self.yeni_satis)
            self.signals.tamamlandi.emit()
        except Exception as e:
            self.signals.hata.emit(f"Satış ekleme hatası: {str(e)}")


class ZiyaretEklemeWorker(QRunnable):
    def __init__(self, services, yeni_ziyaret):
        super().__init__()
        self.services = services
        self.yeni_ziyaret = yeni_ziyaret
        self.signals = WorkerSignals()  # Her worker için bağımsız bir sinyal nesnesi

    def run(self):
        try:
            self.services.data_manager.add_visit(self.yeni_ziyaret)
            self.signals.tamamlandi.emit()
        except Exception as e:
            self.signals.hata.emit(f"Ziyaret ekleme hatası: {str(e)}")


class SatisSilmeWorker(QRunnable):
    def __init__(self, services, satis_index):
        super().__init__()
        self.services = services
        self.satis_index = satis_index
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.services.data_manager.delete_sale(self.satis_index)
            self.signals.tamamlandi.emit()
        except Exception as e:
            self.signals.hata.emit(f"Satış silme hatası: {str(e)}")


class ZiyaretSilmeWorker(QRunnable):
    def __init__(self, services, ziyaret_index):
        super().__init__()
        self.services = services
        self.ziyaret_index = ziyaret_index
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.services.data_manager.delete_visit(self.ziyaret_index)
            self.signals.tamamlandi.emit()
        except Exception as e:
            self.signals.hata.emit(f"Ziyaret silme hatası: {str(e)}")

class ZiyaretDuzenlemeWorker(QRunnable):
    def __init__(self, services, row, yeni_bilgiler):
        super().__init__()
        self.services = services
        self.row = row
        self.yeni_bilgiler = yeni_bilgiler
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.services.data_manager.update_visit(self.row, self.yeni_bilgiler)
            self.signals.tamamlandi.emit()
        except Exception as e:
            self.signals.hata.emit(f"Ziyaret düzenleme hatası: {str(e)}")

class SatisDuzenlemeWorker(QRunnable):
    def __init__(self, services, row, yeni_bilgiler):
        super().__init__()
        self.services = services
        self.row = row
        self.yeni_bilgiler = yeni_bilgiler
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.services.data_manager.update_sale(self.row, self.yeni_bilgiler)
            self.signals.tamamlandi.emit()
        except Exception as e:
            self.signals.hata.emit(f"Satış düzenleme hatası: {str(e)}")