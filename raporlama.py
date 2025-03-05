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
import concurrent.futures

class RaporlamaWorker(QThread):
    """
    Raporlama işlemlerini arka planda ve paralel olarak gerçekleştiren worker sınıfı.
    """
    tamamlandi = pyqtSignal(dict)
    hata = pyqtSignal(str)
    ilerleme = pyqtSignal(dict)
    
    def __init__(self, services, baslangic_tarihi=None, bitis_tarihi=None, max_workers=4):
        super().__init__()
        self.services = services
        self.baslangic_tarihi = baslangic_tarihi
        self.bitis_tarihi = bitis_tarihi
        self.max_workers = max_workers  # Paralel iş parçacığı sayısı
    
    def _paralel_kohort_hesapla(self, ay_listesi):
        """Kohort analizini ay bazında paralel olarak hesaplar."""
        def hesapla_ay(ay):
            try:
                # Her ay için kohort verisini hesapla (örnek fonksiyon)
                kohort_veri = self.services.generate_kohort_for_month(
                    ay=ay,
                    baslangic_tarihi=self.baslangic_tarihi,
                    bitis_tarihi=self.bitis_tarihi
                )
                return {ay: kohort_veri}
            except Exception as e:
                return {ay: {"error": str(e)}}
        
        sonuclar = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ay = {executor.submit(hesapla_ay, ay): ay for ay in ay_listesi}
            tamamlanan = 0
            for future in concurrent.futures.as_completed(future_to_ay):
                ay = future_to_ay[future]
                try:
                    sonuc = future.result()
                    sonuclar.update(sonuc)
                except Exception as e:
                    sonuclar[ay] = {"error": str(e)}
                
                tamamlanan += 1
                yuzde = int((tamamlanan / len(ay_listesi)) * 100)
                self.ilerleme.emit({"yuzde": yuzde, "mesaj": f"Ay {ay} işlendi"})
        
        return sonuclar
    
    def run(self):
        try:
            # Örnek: Aylık kohort analizi için tarih aralığını böl
            baslangic = datetime.strptime(self.baslangic_tarihi, "%Y-%m-%d")
            bitis = datetime.strptime(self.bitis_tarihi, "%Y-%m-%d")
            ay_listesi = [(baslangic.year, baslangic.month + i) for i in range((bitis.year - baslangic.year) * 12 + bitis.month - baslangic.month + 1)]
            ay_listesi = [f"{yil}-{ay:02d}" for yil, ay in ay_listesi]
            
            # Paralel hesaplama
            kohort_sonuclar = self._paralel_kohort_hesapla(ay_listesi)
            
            # Sonuçları birleştir ve rapor oluştur
            rapor = self.services.finalize_kohort_report(kohort_sonuclar)
            self.tamamlandi.emit(rapor)
        except Exception as e:
            self.hata.emit(str(e))

class Raporlama:
    """
    Raporlama işlemlerini gerçekleştiren sınıf.
    Paralel işleme ile büyük veri setleri için performans artırılmıştır.
    """
    
    def __init__(self, parent, services, loglayici, gorsellestirici):
        """
        Args:
            parent: Ebeveyn pencere
            services: Servis katmanı
            loglayici: Loglama nesnesi
            gorsellestirici: Görselleştirme nesnesi
        """
        self.parent = parent
        self.services = services
        self.loglayici = loglayici
        self.gorsellestirici = gorsellestirici
    
    def _paralel_rapor_hesapla(self, rapor_fonksiyonu, rapor_adi, parametreler=None):
        """Genel bir paralel rapor hesaplama metodu."""
        def hesapla_parca(parca):
            try:
                return rapor_fonksiyonu(**parca)
            except Exception as e:
                return {"error": str(e)}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            parametreler = parametreler or [{}]
            future_to_parca = {executor.submit(hesapla_parca, parca): parca for parca in parametreler}
            sonuclar = []
            for future in concurrent.futures.as_completed(future_to_parca):
                try:
                    sonuc = future.result()
                    sonuclar.append(sonuc)
                except Exception as e:
                    self.loglayici.error(f"{rapor_adi} parça hesaplama hatası: {str(e)}")
            
            # Sonuçları birleştir
            return self._rapor_birlestir(sonuclar, rapor_adi)
    
    def _rapor_birlestir(self, sonuclar, rapor_adi):
        """Paralel hesaplanan rapor parçalarını birleştirir."""
        birlesik_rapor = ""
        for sonuc in sonuclar:
            if isinstance(sonuc, dict) and "error" in sonuc:
                birlesik_rapor += f"<p>Hata: {sonuc['error']}</p>"
            else:
                birlesik_rapor += sonuc
        return birlesik_rapor
    
    def raporlar_menusu_olustur(self):
        """Raporlar menüsünü oluşturur"""
        raporlar_menusu = self.parent.menuBar().addMenu("Raporlar")
        
        raporlar = [
            ("Satis Raporu", self.satis_raporu_olustur),
            ("Musteri Raporu", self.musteri_raporu_olustur),
            ("Ziyaret Raporu", self.ziyaret_raporu_olustur),
            ("Sikayet Raporu", self.sikayet_raporu_olustur),
            ("Pipeline Raporu", self.pipeline_raporu_olustur),
            ("Urun BOM Raporu", self.urun_bom_raporu_olustur),
            ("Urun Performans Raporu", self.urun_performans_raporu_olustur),
            ("Kohort Analizi Raporu", self.kohort_analizi_raporu_olustur),
        ]
        
        for ad, fonksiyon in raporlar:
            action = self.parent.create_action(ad, fonksiyon)
            raporlar_menusu.addAction(action)
        
        return raporlar_menusu
    
    def satis_raporu_olustur(self):
        """Satış raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_sales_report, "Satış Raporu")
        self.rapor_goster("Aylık Satış Raporu", rapor)
    
    def musteri_raporu_olustur(self):
        """Müşteri raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_customer_report, "Müşteri Raporu")
        self.rapor_goster("Müşteri Analiz Raporu", rapor)
    
    def ziyaret_raporu_olustur(self):
        """Ziyaret raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_visit_report, "Ziyaret Raporu")
        self.rapor_goster("Ziyaret Raporu", rapor)
    
    def sikayet_raporu_olustur(self):
        """Şikayet raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_complaint_report, "Şikayet Raporu")
        self.rapor_goster("Şikayet Raporu", rapor)
    
    def pipeline_raporu_olustur(self):
        """Pipeline raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_pipeline_report, "Pipeline Raporu")
        self.rapor_goster("Pipeline Raporu", rapor)
    
    def urun_bom_raporu_olustur(self):
        """Ürün BOM raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_urun_bom_report, "Ürün BOM Raporu")
        self.rapor_goster("Ürün BOM Raporu", rapor)
    
    def urun_performans_raporu_olustur(self):
        """Ürün performans raporunu paralel olarak oluşturur"""
        rapor = self._paralel_rapor_hesapla(self.services.generate_urun_performans_report, "Ürün Performans Raporu")
        self.rapor_goster("Ürün Performans Raporu", rapor)
    
    def rapor_goster(self, baslik, rapor):
        """Raporu gösterir"""
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
        """Kohort analizi raporunu oluşturur"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Kohort Analizi Parametreleri")
        dialog.setMinimumWidth(400)
        
        yerlesim = QFormLayout(dialog)
        
        baslangic_tarihi = QDateEdit()
        baslangic_tarihi.setDate(QDate.currentDate().addMonths(-12))
        baslangic_tarihi.setCalendarPopup(True)
        
        bitis_tarihi = QDateEdit()
        bitis_tarihi.setDate(QDate.currentDate())
        bitis_tarihi.setCalendarPopup(True)
        
        yerlesim.addRow("Başlangıç Tarihi:", baslangic_tarihi)
        yerlesim.addRow("Bitiş Tarihi:", bitis_tarihi)
        
        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        
        yerlesim.addRow(butonlar)
        
        olustur_butonu = butonlar.button(QDialogButtonBox.StandardButton.Ok)
        olustur_butonu.setText("Rapor Oluştur")
        iptal_butonu = butonlar.button(QDialogButtonBox.StandardButton.Cancel)
        iptal_butonu.setText("İptal")
        
        def rapor_olustur():
            baslangic = baslangic_tarihi.date().toString("yyyy-MM-dd")
            bitis = bitis_tarihi.date().toString("yyyy-MM-dd")
            
            dialog.accept()
            
            ilerleme_dialog = QProgressDialog("Kohort analizi raporu oluşturuluyor...", "İptal", 0, 100, self.parent)
            ilerleme_dialog.setWindowTitle("İşlem Devam Ediyor")
            ilerleme_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            ilerleme_dialog.setMinimumDuration(0)
            ilerleme_dialog.setValue(0)
            ilerleme_dialog.show()
            
            self._kohort_analizi_olustur(baslangic, bitis, ilerleme_dialog)
        
        olustur_butonu.clicked.connect(rapor_olustur)
        iptal_butonu.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _kohort_analizi_olustur(self, baslangic_tarihi, bitis_tarihi, ilerleme_dialog):
        try:
            self.worker = RaporlamaWorker(
                self.services,
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi,
                max_workers=4
            )
            
            # Sinyalleri ana iş parçacığına güvenli bir şekilde bağla
            self.worker.tamamlandi.connect(lambda sonuc: self._kohort_analizi_tamamlandi(sonuc, ilerleme_dialog))
            self.worker.hata.connect(lambda hata: self._kohort_analizi_hatasi(hata, ilerleme_dialog))
            self.worker.ilerleme.connect(lambda data: ilerleme_dialog.setValue(data.get("yuzde", 0)))
            
            self.worker.start()
        
        except Exception as e:
            ilerleme_dialog.close()
            self.loglayici.error(f"Kohort analizi başlatılırken hata: {str(e)}")
            self.parent.show_error(f"Kohort analizi başlatılırken hata: {str(e)}")
    
    def _kohort_analizi_tamamlandi(self, sonuc, ilerleme_dialog):
        ilerleme_dialog.close()
        if not sonuc.get("success", False):
            self.parent.show_error(sonuc.get("message", "Bilinmeyen hata"))
            return
        
        rapor_dosyasi = sonuc["rapor_dosyasi"]
        self.loglayici.info(f"Kohort analizi raporu oluşturuldu: {rapor_dosyasi}")
        self.gorsellestirici.html_goster(
            html_icerik=sonuc["html_rapor"],
            baslik="Kohort Analizi Raporu",
            dosya_yolu=rapor_dosyasi
        )
        self.parent.show_info("Başarılı", "Kohort analizi raporu oluşturuldu.")

    def _kohort_analizi_hatasi(self, hata_mesaji, ilerleme_dialog):
        ilerleme_dialog.close()
        self.loglayici.error(f"Kohort analizi hatası: {hata_mesaji}")
        self.parent.show_error(f"Kohort analizi hatası: {hata_mesaji}")
