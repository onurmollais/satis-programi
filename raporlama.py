# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QMessageBox, QLabel, QScrollArea, QTextEdit,
                             QDialog, QDateEdit, QFormLayout, QDialogButtonBox, QProgressDialog)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from events import Event
from typing import Optional, Dict, Any
import os
from datetime import datetime

class RaporlamaWorker(QThread):
    """
    Raporlama islemlerini arka planda gerceklestiren worker sinifi.
    
    Bu sinif, uzun suren raporlama islemlerini arka planda gerceklestirerek
    kullanici arayuzunun donmasini engeller.
    """
    tamamlandi = pyqtSignal(dict)
    hata = pyqtSignal(str)
    ilerleme = pyqtSignal(dict)
    
    def __init__(self, services, baslangic_tarihi=None, bitis_tarihi=None):
        super().__init__()
        self.services = services
        self.baslangic_tarihi = baslangic_tarihi
        self.bitis_tarihi = bitis_tarihi
        
    def run(self):
        try:
            sonuc = self.services.generate_kohort_report(
                baslangic_tarihi=self.baslangic_tarihi,
                bitis_tarihi=self.bitis_tarihi
            )
            self.tamamlandi.emit(sonuc)
        except Exception as e:
            self.hata.emit(str(e))

class Raporlama:
    """
    Raporlama islemlerini gerceklestiren sinif.
    
    Bu sinif, kullanici arayuzunde raporlama menulerini olusturur ve
    cesitli raporlarin olusturulmasini saglar.
    """
    
    def __init__(self, parent, services, loglayici, gorsellestirici):
        """
        Raporlama sinifinin kurucu metodu.
        
        Args:
            parent: Ebeveyn pencere
            services: Servis katmani
            loglayici: Loglama nesnesi
            gorsellestirici: GorselleÅŸtirme nesnesi
        """
        self.parent = parent
        self.services = services
        self.loglayici = loglayici
        self.gorsellestirici = gorsellestirici
        
    def raporlar_menusu_olustur(self):
        """Raporlar menusunu olusturur"""
        raporlar_menusu = self.parent.menuBar().addMenu("Raporlar")
        
        # Satis Raporu
        satis_raporu_action = self.parent.create_action("Satis Raporu", self.satis_raporu_olustur)
        raporlar_menusu.addAction(satis_raporu_action)
        
        # Musteri Raporu
        musteri_raporu_action = self.parent.create_action("Musteri Raporu", self.musteri_raporu_olustur)
        raporlar_menusu.addAction(musteri_raporu_action)
        
        # Ziyaret Raporu
        ziyaret_raporu_action = self.parent.create_action("Ziyaret Raporu", self.ziyaret_raporu_olustur)
        raporlar_menusu.addAction(ziyaret_raporu_action)
        
        # Sikayet Raporu
        sikayet_raporu_action = self.parent.create_action("Sikayet Raporu", self.sikayet_raporu_olustur)
        raporlar_menusu.addAction(sikayet_raporu_action)
        
        # Pipeline Raporu
        pipeline_raporu_action = self.parent.create_action("Pipeline Raporu", self.pipeline_raporu_olustur)
        raporlar_menusu.addAction(pipeline_raporu_action)
        
        # Urun BOM Raporu
        urun_bom_raporu_action = self.parent.create_action("Urun BOM Raporu", self.urun_bom_raporu_olustur)
        raporlar_menusu.addAction(urun_bom_raporu_action)
        
        # Urun Performans Raporu
        urun_performans_raporu_action = self.parent.create_action("Urun Performans Raporu", self.urun_performans_raporu_olustur)
        raporlar_menusu.addAction(urun_performans_raporu_action)
        
        # Kohort Analizi Raporu
        kohort_analizi_action = self.parent.create_action("Kohort Analizi Raporu", self.kohort_analizi_raporu_olustur)
        raporlar_menusu.addAction(kohort_analizi_action)
        
        return raporlar_menusu
    
    def satis_raporu_olustur(self):
        """Satis raporu olusturur"""
        rapor = self.services.generate_sales_report()
        self.rapor_goster("Aylik Satis Raporu", rapor)
    
    def musteri_raporu_olustur(self):
        """Musteri raporu olusturur"""
        rapor = self.services.generate_customer_report()
        self.rapor_goster("Musteri Analiz Raporu", rapor)
    
    def ziyaret_raporu_olustur(self):
        """Ziyaret raporu olusturur"""
        rapor = self.services.generate_visit_report()
        self.rapor_goster("Ziyaret Raporu", rapor)
    
    def sikayet_raporu_olustur(self):
        """Sikayet raporu olusturur"""
        rapor = self.services.generate_complaint_report()
        self.rapor_goster("Sikayet Raporu", rapor)
    
    def pipeline_raporu_olustur(self):
        """Pipeline raporu olusturur"""
        rapor = self.services.generate_pipeline_report()
        self.rapor_goster("Pipeline Raporu", rapor)
    
    def urun_bom_raporu_olustur(self):
        """Urun BOM raporu olusturur"""
        rapor = self.services.generate_urun_bom_report()
        self.rapor_goster("Urun BOM Raporu", rapor)
    
    def urun_performans_raporu_olustur(self):
        """Urun performans raporu olusturur"""
        rapor = self.services.generate_urun_performans_report()
        self.rapor_goster("Urun Performans Raporu", rapor)
    
    def rapor_goster(self, baslik, rapor):
        """Raporu gosterir"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle(baslik)
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(rapor)
        
        layout.addWidget(text_edit)
        
        butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        butonlar.rejected.connect(dialog.reject)
        layout.addWidget(butonlar)
        
        dialog.exec()
    
    def kohort_analizi_raporu_olustur(self):
        """Kohort analizi raporu olusturur"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Kohort Analizi Parametreleri")
        dialog.setMinimumWidth(400)
        
        yerlesim = QFormLayout(dialog)
        
        # Tarih araligi secimi
        baslangic_tarihi = QDateEdit()
        baslangic_tarihi.setDate(QDate.currentDate().addMonths(-12))  # Son 12 ay
        baslangic_tarihi.setCalendarPopup(True)
        
        bitis_tarihi = QDateEdit()
        bitis_tarihi.setDate(QDate.currentDate())
        bitis_tarihi.setCalendarPopup(True)
        
        yerlesim.addRow("Baslangic Tarihi:", baslangic_tarihi)
        yerlesim.addRow("Bitis Tarihi:", bitis_tarihi)
        
        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        
        yerlesim.addRow(butonlar)
        
        olustur_butonu = butonlar.button(QDialogButtonBox.StandardButton.Ok)
        olustur_butonu.setText("Rapor Olustur")
        iptal_butonu = butonlar.button(QDialogButtonBox.StandardButton.Cancel)
        iptal_butonu.setText("Iptal")
        
        def rapor_olustur():
            # Parametreleri al
            baslangic = baslangic_tarihi.date().toString("yyyy-MM-dd")
            bitis = bitis_tarihi.date().toString("yyyy-MM-dd")
            
            dialog.accept()
            
            # Ilerleme dialogu
            ilerleme_dialog = QProgressDialog("Kohort analizi raporu olusturuluyor...", "Iptal", 0, 100, self.parent)
            ilerleme_dialog.setWindowTitle("Islem Devam Ediyor")
            ilerleme_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            ilerleme_dialog.setMinimumDuration(0)
            ilerleme_dialog.setValue(0)
            ilerleme_dialog.show()
            
            # Kohort analizini arka planda calistir
            self._kohort_analizi_olustur(baslangic, bitis, ilerleme_dialog)
        
        olustur_butonu.clicked.connect(rapor_olustur)
        iptal_butonu.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _kohort_analizi_olustur(self, baslangic_tarihi, bitis_tarihi, ilerleme_dialog):
        """Kohort analizini arka planda olusturur"""
        try:
            # Worker thread olustur
            self.worker = RaporlamaWorker(
                self.services,
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi
            )
            
            # Sinyalleri bagla
            self.worker.tamamlandi.connect(lambda sonuc: self._kohort_analizi_tamamlandi(sonuc, ilerleme_dialog))
            self.worker.hata.connect(lambda hata: self._kohort_analizi_hatasi(hata, ilerleme_dialog))
            self.worker.ilerleme.connect(lambda data: ilerleme_dialog.setValue(data.get("yuzde", 0)))
            
            # Thread'i baslat
            self.worker.start()
            
        except Exception as e:
            ilerleme_dialog.close()
            self.loglayici.error(f"Kohort analizi baslatilirken hata: {str(e)}")
            QMessageBox.critical(self.parent, "Hata", f"Kohort analizi baslatilirken hata: {str(e)}")
    
    def _kohort_analizi_tamamlandi(self, sonuc, ilerleme_dialog):
        """Kohort analizi tamamlandiginda cagrilir"""
        try:
            ilerleme_dialog.close()
            
            if not sonuc.get("success", False):
                QMessageBox.critical(self.parent, "Hata", sonuc.get("message", "Bilinmeyen hata"))
                return
            
            # Rapor dosyasini ac
            rapor_dosyasi = sonuc["rapor_dosyasi"]
            self.loglayici.info(f"Kohort analizi raporu olusturuldu: {rapor_dosyasi}")
            
            # Raporu goster
            self.gorsellestirici.html_goster(
                html_icerik=sonuc["html_rapor"],
                baslik="Kohort Analizi Raporu",
                dosya_yolu=rapor_dosyasi
            )
            
            # Basari mesaji
            QMessageBox.information(self.parent, "Basarili", "Kohort analizi raporu olusturuldu.")
            
        except Exception as e:
            self.loglayici.error(f"Kohort analizi raporu olusturulurken hata: {str(e)}")
            QMessageBox.critical(self.parent, "Hata", f"Kohort analizi raporu olusturulurken hata: {str(e)}")
    
    def _kohort_analizi_hatasi(self, hata_mesaji, ilerleme_dialog):
        """Kohort analizi sirasinda hata olustugunda cagrilir"""
        ilerleme_dialog.close()
        self.loglayici.error(f"Kohort analizi hatasi: {hata_mesaji}")
        QMessageBox.critical(self.parent, "Hata", f"Kohort analizi hatasi: {hata_mesaji}") 
