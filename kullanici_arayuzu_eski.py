# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QPushButton, QMessageBox, QLabel, QScrollArea, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLineEdit, QFormLayout, QDateEdit,
                             QComboBox, QTextEdit, QDialog, QProgressBar, QFileDialog, QListWidget,
                             QGroupBox, QSizePolicy, QGridLayout, QScrollArea, QPushButton, QDialog,
                             QDialogButtonBox, QAbstractItemView, QFrame)
from PyQt6.QtCore import Qt, QDate, QTimer, QUrl 
from PyQt6.QtGui import QIcon, QAction  # QAction sinifi buraya tasindi
from veri_yoneticisi import VeriYoneticisi
from gorsellestirici import Gorsellestirici  
from services import CRMServices, ServiceInterface  # Guncellenmis import
import pandas as pd
import sqlite3
import folium
from PyQt6.QtWebEngineWidgets import QWebEngineView
from io import BytesIO
import base64
import json  # Yeni eklenen kutuphane
from PyQt6.QtCore import QThread, pyqtSignal  # Thread icin eklendi
from typing import Optional, List  # Type hints icin
from repository import RepositoryInterface  # Yeni import
from events import Event, EventManager, EVENT_DATA_UPDATED, EVENT_UI_UPDATED, EVENT_ERROR_OCCURRED
from PyQt6.QtCore import pyqtSignal 
import os
import sys
from internet_baglantisi import InternetBaglantisi
from ui_satis import AnaPencere as SatisAnaPencere
from ui_hammadde_bom import AnaPencere as HammaddeAnaPencere
from veri_yukleme_worker import VeriYuklemeWorker
from ui_interface import UIInterface

HATA_KODLARI = {  # Ozel hata kodlari tanimlama
    "VERI_YUKLEME_001": "Dosya secimi iptal edildi",
    "VERI_YUKLEME_002": "Veri cercevesi bos veya yuklenmedi",
    "VERI_YUKLEME_003": "Veritabani kaydetme hatasi",
    "GENEL_001": "Bilinmeyen hata"
}

# UIInterface sinifi ui_interface.py dosyasina tasindi

# VeriYuklemeWorker sinifi veri_yukleme_worker.py dosyasina tasindi

# VeriYuklemeWorker sinifini diger dosyalarin kullanabilmesi icin export ediyoruz
__all__ = ['HataDialog', 'AnaPencere']

class HataDialog(QDialog):
    """Kullanici dostu hata mesajlari icin ozel dialog"""
    def __init__(self, baslik: str, aciklama: str, cozum_onerileri: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hata")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Hata basligi
        baslik_label = QLabel(f"<h3>{baslik}</h3>")
        layout.addWidget(baslik_label)
        
        # Hata aciklamasi
        aciklama_label = QLabel(aciklama)
        aciklama_label.setWordWrap(True)
        layout.addWidget(aciklama_label)
        
        # Cozum onerileri
        if cozum_onerileri:
            oneriler_label = QLabel("<h4>Cozum Onerileri:</h4>")
            layout.addWidget(oneriler_label)
            
            oneriler_text = QTextEdit()
            oneriler_text.setReadOnly(True)
            oneriler_text.setPlainText("\n".join(f"• {oneri}" for oneri in cozum_onerileri))
            layout.addWidget(oneriler_text)
        
        # Kapatma butonu
        kapat_btn = QPushButton("Kapat")
        kapat_btn.clicked.connect(self.accept)
        layout.addWidget(kapat_btn)
        
        self.setLayout(layout)

class AnaPencere(QMainWindow, UIInterface):
    data_updated_signal = pyqtSignal(Event)
    def __init__(self, services: ServiceInterface, zamanlayici, loglayici, event_manager):
        super().__init__()
        self.is_initialized = False  # Baslangicta False, uygulama basladiktan sonra True olacak
        self.setWindowTitle("Satis Yonetimi ve CRM Programi")
        #self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon('icon.png'))
        self.setMinimumSize(800, 600)
        #self.setMaximumSize(1920, 1080)

        self.services = services
        self.zamanlayici = zamanlayici
        self.loglayici = loglayici
        self.event_manager = event_manager
        self.gorsellestirici = Gorsellestirici(self.loglayici, self.event_manager)

        # Internet baglantisi kontrolu ekle
        self.internet_baglantisi = InternetBaglantisi(loglayici, event_manager)
        
        # UI olustur
        self.setWindowTitle("CRM Sistemi")
        self.setGeometry(100, 100, 1200, 800)
        
        # Status bar olustur
        self.statusBar().showMessage("Program baslatiliyor...")
        
        # Internet baglantisi kontrolu
        if not self.internet_baglantisi.baglanti_bekle():
            yanit = QMessageBox.question(self, "Baglanti Hatasi", 
                "Internet baglantisi kurulamadi. Offline modda devam etmek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
            if yanit == QMessageBox.StandardButton.Yes:
                self.internet_baglantisi.offline_moda_gec()
            else:
                sys.exit()
        
        # Event dinleyicileri ekle
        if self.event_manager:
            self.event_manager.subscribe("InternetBaglanti", self._on_internet_status_changed)
            self.event_manager.subscribe(EVENT_DATA_UPDATED, self._on_data_updated)
            self.event_manager.subscribe(EVENT_UI_UPDATED, self._on_ui_updated)
            self.event_manager.subscribe(EVENT_ERROR_OCCURRED, self._on_error_occurred)

     # Container'lar ve UI olusturma (degismedi, ayni kaliyor)
        self.satis_performans_container = QWidget()
        self.pipeline_container = QWidget()
        self.musteri_segmentasyon_container = QWidget()
        self.satis_temsilcisi_performans_container = QWidget()
        self.musteri_bolge_dagilim_container = QWidget()
        self.aylik_potansiyel_gelir_container = QWidget()

        merkez_widget = QWidget()
        self.setCentralWidget(merkez_widget)
        ana_yerlesim = QVBoxLayout()
        ana_yerlesim.setContentsMargins(10, 10, 10, 10)
        ana_yerlesim.setSpacing(10)
        merkez_widget.setLayout(ana_yerlesim)

        self.menu_olustur()
        self.veri_yukle_butonu = QPushButton("Verileri Yukle")
        self.veri_yukle_butonu.clicked.connect(self.tum_verileri_yukle)
        ana_yerlesim.addWidget(self.veri_yukle_butonu)

        self.sekme_widget = QTabWidget()
        ana_yerlesim.addWidget(self.sekme_widget)

        # Satis ve Hammadde siniflarini mixin olarak kullan
        self._satis_mixin = SatisAnaPencere()
        self._hammadde_mixin = HammaddeAnaPencere()
        
        # Gerekli ozellikleri mixin siniflardan bu sinifa aktar
        self._satis_mixin.services = self.services
        self._satis_mixin.loglayici = self.loglayici
        self._satis_mixin.event_manager = self.event_manager
        self._satis_mixin.sekme_widget = self.sekme_widget
        self._satis_mixin.is_initialized = False
        
        self._hammadde_mixin.services = self.services
        self._hammadde_mixin.loglayici = self.loglayici
        self._hammadde_mixin.event_manager = self.event_manager
        self._hammadde_mixin.sekme_widget = self.sekme_widget
        self._hammadde_mixin.is_initialized = False

        self.gosterge_paneli_olustur()
        
        # Satis modulu sekmelerini olustur
        self._satis_mixin.satisci_yonetimi_olustur()
        self._satis_mixin.satis_hedefleri_olustur()
        self._satis_mixin.pipeline_yonetimi_olustur()
        self._satis_mixin.musteri_profili_olustur()
        self._satis_mixin.aylik_satis_takibi_olustur()
        self._satis_mixin.ziyaret_planlama_olustur()
        self.sikayet_yonetimi_olustur()
        
        # Hammadde modulu sekmelerini olustur
        self._hammadde_mixin.hammadde_maliyetleri_olustur()
        self._hammadde_mixin.urun_bom_olustur()

        self.guncelleme_zamanlayicisi = QTimer(self)
        self.guncelleme_zamanlayicisi.timeout.connect(self.tum_sekmeleri_guncelle)
        self.guncelleme_zamanlayicisi.start(300000)  # 5 dakikada bir guncelle

        # Mixin siniflarin is_initialized degerlerini guncelle
        self._satis_mixin.is_initialized = True
        self._hammadde_mixin.is_initialized = True
        self.is_initialized = True  # Baslatma tamamlandiginda True yap

        # Sinyali bala
        self.data_updated_signal.connect(self.tum_sekmeleri_guncelle)

    def _on_internet_status_changed(self, event: Event) -> None:
        """Internet baglantisi durumu degistiginde calisir"""
        status = event.data.get("status")
        if status == "baglanti_yok":
            yanit = QMessageBox.question(self, "Baglanti Hatasi", 
                f"Internet baglantisi kesildi: {event.data.get('hata', 'Bilinmeyen hata')}\nOffline modda devam etmek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
            if yanit == QMessageBox.StandardButton.Yes:
                self.internet_baglantisi.offline_moda_gec()
            else:
                sys.exit()
                
        elif status == "offline_mod":
            self.statusBar().showMessage("Program offline modda calisiyor")
            
        elif status == "online_mod":
            self.statusBar().showMessage("Program online modda calisiyor")
            
        else:
            self.statusBar().showMessage("Internet baglantisi aktif")

    def menu_olustur(self):
        menubar = self.menuBar()
        
        # Dosya menusu
        dosya_menu = menubar.addMenu('Dosya')
        
        yukle_action = QAction('Verileri Yukle', self)
        yukle_action.triggered.connect(self.tum_verileri_yukle)
        dosya_menu.addAction(yukle_action)
        
        kaydet_action = QAction('Verileri Kaydet', self)
        kaydet_action.triggered.connect(self.tum_verileri_kaydet)
        dosya_menu.addAction(kaydet_action)
        
        # Ayirici ekle
        dosya_menu.addSeparator()
        
        # Cikis butonu ekle
        cikis_action = QAction('Cikis', self)
        cikis_action.triggered.connect(self.close)
        dosya_menu.addAction(cikis_action)
        
        # Raporlar menusu
        raporlar_menusu = self.raporlar_menusu_olustur()
        menubar.addMenu(raporlar_menusu)
        
        # Yardim menusu
        yardim_menu = menubar.addMenu('Yardim')
        
        hakkinda_action = QAction('Hakkinda', self)
        hakkinda_action.triggered.connect(self.hakkinda_goster)
        yardim_menu.addAction(hakkinda_action)

    def raporlar_menusu_olustur(self):
        """Raporlar menusunu olusturur"""
        raporlar_menusu = self.menuBar().addMenu("Raporlar")
        
        # Satis Raporu
        satis_raporu_action = QAction("Satis Raporu", self)
        satis_raporu_action.triggered.connect(self.satis_raporu_olustur)
        raporlar_menusu.addAction(satis_raporu_action)
        
        # Musteri Raporu
        musteri_raporu_action = QAction("Musteri Raporu", self)
        musteri_raporu_action.triggered.connect(self.musteri_raporu_olustur)
        raporlar_menusu.addAction(musteri_raporu_action)
        
        # Ziyaret Raporu
        ziyaret_raporu_action = QAction("Ziyaret Raporu", self)
        ziyaret_raporu_action.triggered.connect(self.ziyaret_raporu_olustur)
        raporlar_menusu.addAction(ziyaret_raporu_action)
        
        # Sikayet Raporu
        sikayet_raporu_action = QAction("Sikayet Raporu", self)
        sikayet_raporu_action.triggered.connect(self.sikayet_raporu_olustur)
        raporlar_menusu.addAction(sikayet_raporu_action)
        
        # Pipeline Raporu
        pipeline_raporu_action = QAction("Pipeline Raporu", self)
        pipeline_raporu_action.triggered.connect(self.pipeline_raporu_olustur)
        raporlar_menusu.addAction(pipeline_raporu_action)
        
        # Urun BOM Raporu
        urun_bom_raporu_action = QAction("Urun BOM Raporu", self)
        urun_bom_raporu_action.triggered.connect(self.urun_bom_raporu_olustur)
        raporlar_menusu.addAction(urun_bom_raporu_action)
        
        # Urun Performans Raporu
        urun_performans_raporu_action = QAction("Urun Performans Raporu", self)
        urun_performans_raporu_action.triggered.connect(self.urun_performans_raporu_olustur)
        raporlar_menusu.addAction(urun_performans_raporu_action)
        
        # Kohort Analizi Raporu
        kohort_analizi_action = QAction("Kohort Analizi", self)
        kohort_analizi_action.triggered.connect(self.kohort_analizi_raporu_olustur)
        raporlar_menusu.addAction(kohort_analizi_action)
        
        return raporlar_menusu

    def _on_ui_updated(self, event: Event) -> None:
        """UI guncellendiginde tepki ver"""
        self.loglayici.info(f"UI guncellendi: {event.data}")
        
        # Gorsellestirici'den gelen grafik yenileme isteklerini isle
        if event.data.get("source") == "gorsellestirici" and event.data.get("action") == "refresh_charts":
            self.gosterge_paneli_guncelle()
        # Kullanici etkilesimlerini isle
        elif event.data.get("source") == "user_interaction":
            self.gosterge_paneli_guncelle()

    def _on_error_occurred(self, event: Event) -> None:
        """Hata olustugunda cagrilir ve kullanici dostu hata mesaji gosterir"""
        hata_dialog = HataDialog(
            event.data.get("title", "Hata"),
            event.data.get("description", "Bilinmeyen bir hata olustu."),
            event.data.get("solutions", []),
            self
        )
        hata_dialog.exec()

    def _on_data_updated(self, event: Event) -> None:
        """Veri guncellendiginde cagrilir"""
        self.loglayici.info(f"Veri guncellendi: {event.data}")
        # Veri guncellendiginde tum sekmeleri guncelle
        self.tum_sekmeleri_guncelle(event)

    def tum_verileri_yukle(self) -> None:
        try:
            if self.internet_baglantisi.offline_mod:
                QMessageBox.information(self, "Offline Mod", 
                    "Program offline modda. Sadece yerel veriler kullanilabilir.")
                return
                
            # Onceki worker'i temizle
            if hasattr(self, 'worker') and self.worker is not None:
                try:
                    if self.worker.isRunning():
                        self.loglayici.warning("Onceki worker hala calisiyor, sonlandiriliyor.")
                        self.worker.terminate()
                        self.worker.wait(1000)  # 1 saniye bekle
                    self.worker = None
                except Exception as e:
                    self.loglayici.error(f"Onceki worker temizlenirken hata: {str(e)}")
                
            dosya_yolu, _ = QFileDialog.getOpenFileName(self, "Excel Dosyasi Sec", "", "Excel Dosyalari (*.xlsx)")
            if not dosya_yolu:
                raise ValueError("Dosya secimi iptal edildi")
                
            ilerleme_dialog = QDialog(self)
            ilerleme_dialog.setWindowTitle("Veriler Yukleniyor")
            ilerleme_dialog.setFixedSize(400, 100)
            
            yerlesim = QVBoxLayout()
            ilerleme_cubugu = QProgressBar()
            ilerleme_cubugu.setMinimum(0)
            ilerleme_cubugu.setMaximum(100)
            
            durum_etiketi = QLabel("Yukleniyor...")
            yerlesim.addWidget(durum_etiketi)
            yerlesim.addWidget(ilerleme_cubugu)
            
            ilerleme_dialog.setLayout(yerlesim)
            
            # Worker thread'i olustur
            self.worker = VeriYuklemeWorker(self.services.data_manager, dosya_yolu)
            
            # Sinyalleri ana thread'deki slot'lara bagla
            def ilerleme_guncelle(data):
                # Ana thread'de calisir
                ilerleme_cubugu.setValue(int(data["progress"]))
                durum_etiketi.setText(f"Yukleniyor: {data['current_table']} ({data['loaded_tables']}/{data['total_tables']})")
            
            def yukleme_tamamlandi():
                # Ana thread'de calisir
                try:
                    ilerleme_dialog.accept()
                    self.filtreleri_guncelle()
                    QMessageBox.information(self, "Basarili", "Veriler yuklendi ve veritabanina kaydedildi.")
                    # Veri guncelleme sinyalini ana thread'de yayinla
                    self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "tum_verileri_yukle"}))
                    
                    # Worker'i temizle
                    if hasattr(self, 'worker') and self.worker is not None:
                        self.worker = None
                except Exception as e:
                    self.loglayici.error(f"Yukleme tamamlandi islenirken hata: {str(e)}")
            
            def yukleme_hatasi(hata_mesaji):
                # Ana thread'de calisir
                try:
                    ilerleme_dialog.reject()
                    QMessageBox.critical(self, "Hata", hata_mesaji)
                    self.loglayici.error(hata_mesaji)
                    
                    # Worker'i temizle
                    if hasattr(self, 'worker') and self.worker is not None:
                        self.worker = None
                except Exception as e:
                    self.loglayici.error(f"Yukleme hatasi islenirken hata: {str(e)}")
            
            # Sinyalleri bagla
            self.worker.ilerleme.connect(ilerleme_guncelle)
            self.worker.tamamlandi.connect(yukleme_tamamlandi)
            self.worker.hata.connect(yukleme_hatasi)
            
            # Dialog'u goster
            ilerleme_dialog.show()
            
            # Thread'i baslat
            self.worker.start()
            
        except ValueError as ve:
            self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": str(ve)}))
        except Exception as e:
            self.loglayici.error(f"Veri yukleme sirasinda beklenmeyen hata: {str(e)}")
            import traceback
            self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Hata", f"Veri yukleme sirasinda beklenmeyen hata: {str(e)}")

    def tum_verileri_kaydet(self):
        try:
            dosya_yolu, _ = QFileDialog.getSaveFileName(self, "Excel Dosyasi Kaydet", "", "Excel Dosyalari (*.xlsx)")
            if dosya_yolu:
                self.services.data_manager.tum_verileri_kaydet(dosya_yolu)  # VeriYoneticisi'ne erisim serviceler uzerinden
                QMessageBox.information(self, "Basarili", "Tum veriler basariyla Excel dosyasina kaydedildi.")
                self.loglayici.info("Tum veriler basariyla Excel dosyasina kaydedildi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri kaydetme sirasinda bir hata olustu: {str(e)}")
            self.loglayici.error(f"Veri kaydetme hatasi: {str(e)}")

    def satis_raporu_olustur(self):
        rapor = self.services.generate_sales_report()
        self.rapor_goster("Aylik Satis Raporu", rapor)

    def musteri_raporu_olustur(self):
        rapor = self.services.generate_customer_report()  # self.services.data_manager -> self.services
        self.rapor_goster("Musteri Analiz Raporu", rapor)

    def ziyaret_raporu_olustur(self):
        rapor = self.services.generate_visit_report()  # self.services.data_manager -> self.services
        self.rapor_goster("Ziyaret Raporu", rapor)

    def sikayet_raporu_olustur(self):
        rapor = self.services.generate_complaint_report()  # self.services.data_manager -> self.services
        self.rapor_goster("Sikayet Raporu", rapor)

    def pipeline_raporu_olustur(self):
        rapor = self.services.generate_pipeline_report()  # self.services.data_manager -> self.services
        self.rapor_goster("Pipeline Raporu", rapor)

    def urun_bom_raporu_olustur(self):
        rapor = self.services.generate_urun_bom_report()
        self.rapor_goster("Urun BOM Raporu", rapor)

    def urun_performans_raporu_olustur(self):
        rapor = self.services.generate_urun_performans_report()
        self.rapor_goster("Urun Performans Raporu", rapor)

    def rapor_goster(self, baslik, rapor):
        dialog = QDialog(self)
        dialog.setWindowTitle(baslik)
        dialog.setGeometry(100, 100, 1000, 600)  # Boyut gerektiginde ayarlanabilir

        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setHtml(rapor)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        dialog.setLayout(layout)
        dialog.exec()

    def hakkinda_goster(self):
        QMessageBox.about(self, "Hakkinda", "Satis Yonetimi ve CRM Programi\nVersiyon 1.0\u00A9 2025 Omio")


    def sikayet_yonetimi_olustur(self):
        """Sikayet Yonetimi sekmesini olusturur"""
        self.sikayet_tab = QWidget()
        self.sekme_widget.addTab(self.sikayet_tab, "Sikayet Yonetimi")
        
        ana_yerlesim = QVBoxLayout()
        self.sikayet_tab.setLayout(ana_yerlesim)
        
        # Ust kisim - Butonlar
        buton_yerlesim = QHBoxLayout()
        
        self.sikayet_ekle_butonu = QPushButton("Yeni Sikayet Ekle")
        self.sikayet_ekle_butonu.clicked.connect(self.sikayet_ekle)
        buton_yerlesim.addWidget(self.sikayet_ekle_butonu)
        
        self.sikayet_duzenle_butonu = QPushButton("Sikayet Duzenle")
        self.sikayet_duzenle_butonu.clicked.connect(self.sikayet_duzenle)
        buton_yerlesim.addWidget(self.sikayet_duzenle_butonu)
        
        self.sikayet_sil_butonu = QPushButton("Sikayet Sil")
        self.sikayet_sil_butonu.clicked.connect(self.sikayet_sil)
        buton_yerlesim.addWidget(self.sikayet_sil_butonu)
        
        ana_yerlesim.addLayout(buton_yerlesim)
        
        # Tablo
        self.sikayet_tablosu = QTableWidget()
        self.sikayet_tablosu.setColumnCount(6)
        self.sikayet_tablosu.setHorizontalHeaderLabels([
            "Musteri Adi", "Siparis No", "Sikayet Turu", 
            "Sikayet Detayi", "Tarih", "Durum"
        ])
        self.sikayet_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sikayet_tablosu.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sikayet_tablosu.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        ana_yerlesim.addWidget(self.sikayet_tablosu)
        
        # Tabloyu guncelle
        self.sikayet_tablosu_guncelle()

    def sikayet_tablosu_guncelle(self):
        """Sikayet tablosunu gunceller"""
        try:
            sikayet_df = self.services.data_manager.sikayetler_df
            
            self.sikayet_tablosu.setRowCount(0)
            
            if sikayet_df is None or sikayet_df.empty:
                return
                
            self.sikayet_tablosu.setRowCount(len(sikayet_df))
            
            columns = ["Musteri Adi", "Siparis No", "Sikayet Turu", "Sikayet Detayi", "Tarih", "Durum"]
            
            for i, row in sikayet_df.iterrows():
                for j, col in enumerate(columns):
                    value = str(row.get(col, "")) if not pd.isna(row.get(col, "")) else ""
                    self.sikayet_tablosu.setItem(i, j, QTableWidgetItem(value))
        except Exception as e:
            self.loglayici.error(f"Sikayet tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Sikayet tablosu guncellenirken hata: {str(e)}")

    def sikayet_ekle(self):
        if (self.services.data_manager.musteriler_df is None or  # self.veri_yoneticisi -> self.services.data_manager
            self.services.data_manager.musteriler_df.empty or 
            "Musteri Adi" not in self.services.data_manager.musteriler_df.columns):
            QMessageBox.warning(self, "Uyari", "Once en az bir musteri ekleyin (Musteri Profili sekmesinden).")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Sikayet Ekle")
        yerlesim = QFormLayout()

        musteri_giris = QComboBox()
        musteri_giris.addItems(self.services.data_manager.musteriler_df["Musteri Adi"].astype(str).tolist())  # int -> str donusumu
        siparis_no_giris = QLineEdit()
        sikayet_turu_giris = QComboBox()
        sikayet_turu_giris.addItems(["Urun Kalitesi", "Teslimat Gecikmesi", "Ambalaj Hatasi", "Yanlis Urun", "Diger"])
        sikayet_detayi_giris = QTextEdit()
        sikayet_detayi_giris.setFixedHeight(100)  # Daha fazla detay icin alan
        tarih_giris = QDateEdit()
        tarih_giris.setDate(QDate.currentDate())
        durum_giris = QComboBox()
        durum_giris.addItems(["Acik", "Inceleniyor", "Cozuldu", "Kapali"])

        yerlesim.addRow("Musteri:", musteri_giris)
        yerlesim.addRow("Siparis No:", siparis_no_giris)
        yerlesim.addRow("Sikayet Turu:", sikayet_turu_giris)
        yerlesim.addRow("Sikayet Detayi:", sikayet_detayi_giris)
        yerlesim.addRow("Tarih:", tarih_giris)
        yerlesim.addRow("Durum:", durum_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def sikayet_kaydet():
            try:
                if not siparis_no_giris.text().strip():
                    raise ValueError("Siparis numarasi bos birakilamaz.")
                if not sikayet_detayi_giris.toPlainText().strip():
                    raise ValueError("Sikayet detayi bos birakilamaz.")
            
                yeni_sikayet = {
                    "Musteri Adi": musteri_giris.currentText(),
                    "Siparis No": siparis_no_giris.text(),
                    "Sikayet Turu": sikayet_turu_giris.currentText(),
                    "Sikayet Detayi": sikayet_detayi_giris.toPlainText(),
                    "Tarih": tarih_giris.date().toString("yyyy-MM-dd"),
                    "Durum": durum_giris.currentText()
                }
                # Duzeltme: self.veri_yoneticisi ve self.repository.save yerine services kullaniyoruz
                self.services.add_complaint(yeni_sikayet)  # CRMServices uzerinden ekleme
                self.sikayet_tablosu_guncelle()
                dialog.accept()
                self.loglayici.info(f"Yeni sikayet eklendi: {yeni_sikayet['Musteri Adi']} - {yeni_sikayet['Sikayet Turu']}")
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sikayet eklenirken hata: {str(e)}")
                self.loglayici.error(f"Sikayet ekleme hatasi: {str(e)}")

        kaydet_butonu.clicked.connect(sikayet_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def sikayet_duzenle(self):
        selected_items = self.sikayet_tablosu.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek icin bir sikayet secin.")
            return

        if (self.services.data_manager.musteriler_df is None or  # self.veri_yoneticisi -> self.services.data_manager
            self.services.data_manager.musteriler_df.empty or 
            "Musteri Adi" not in self.services.data_manager.musteriler_df.columns):
            QMessageBox.warning(self, "Uyari", "Musteri listesi bos veya yuklenemedi.")
            return

        row = selected_items[0].row()
        dialog = QDialog(self)
        dialog.setWindowTitle("Sikayet Duzenle")
        yerlesim = QFormLayout()

        sikayet = self.services.data_manager.sikayetler_df.iloc[row]  # self.veri_yoneticisi -> self.services.data_manager
        musteri_giris = QComboBox()
        musteri_giris.addItems(self.services.data_manager.musteriler_df["Musteri Adi"].astype(str).tolist())  # self.veri_yoneticisi -> self.services.data_manager
        musteri_giris.setCurrentText(str(sikayet["Musteri Adi"]))
        siparis_no_giris = QLineEdit(str(sikayet["Siparis No"]))
        sikayet_turu_giris = QComboBox()
        sikayet_turu_giris.addItems(["Urun Kalitesi", "Teslimat Gecikmesi", "Ambalaj Hatasi", "Yanlis Urun", "Diger"])
        sikayet_turu_giris.setCurrentText(sikayet["Sikayet Turu"])
        sikayet_detayi_giris = QTextEdit(str(sikayet["Sikayet Detayi"]))  # numpy.int64 -> str donusumu
        sikayet_detayi_giris.setFixedHeight(100)
        tarih_giris = QDateEdit()
        tarih_giris.setDate(QDate.fromString(sikayet["Tarih"], "yyyy-MM-dd"))
        durum_giris = QComboBox()
        durum_giris.addItems(["Acik", "Inceleniyor", "Cozuldu", "Kapali"])
        durum_giris.setCurrentText(sikayet["Durum"])

        yerlesim.addRow("Musteri:", musteri_giris)
        yerlesim.addRow("Siparis No:", siparis_no_giris)
        yerlesim.addRow("Sikayet Turu:", sikayet_turu_giris)
        yerlesim.addRow("Sikayet Detayi:", sikayet_detayi_giris)
        yerlesim.addRow("Tarih:", tarih_giris)
        yerlesim.addRow("Durum:", durum_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def sikayet_guncelle():
            try:
                if not siparis_no_giris.text().strip():
                    raise ValueError("Siparis numarasi bos birakilamaz.")
                if not sikayet_detayi_giris.toPlainText().strip():
                    raise ValueError("Sikayet detayi bos birakilamaz.")
            
                yeni_bilgiler = {
                    "Musteri Adi": musteri_giris.currentText(),
                    "Siparis No": siparis_no_giris.text(),
                    "Sikayet Turu": sikayet_turu_giris.currentText(),
                    "Sikayet Detayi": sikayet_detayi_giris.toPlainText(),
                    "Tarih": tarih_giris.date().toString("yyyy-MM-dd"),
                    "Durum": durum_giris.currentText()
                }
                # Duzeltme: self.veri_yoneticisi ve self.repository.save yerine services kullaniyoruz
                self.services.data_manager.sikayetler_df.iloc[row] = pd.Series(yeni_bilgiler)
                self.services.data_manager.repository.save(self.services.data_manager.sikayetler_df, "complaints")  # Veritabanini kaydetme
                self.sikayet_tablosu_guncelle()
                dialog.accept()
                self.loglayici.info(f"Sikayet guncellendi: {yeni_bilgiler['Musteri Adi']} - {yeni_bilgiler['Sikayet Turu']}")
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sikayet guncellenirken hata: {str(e)}")
                self.loglayici.error(f"Sikayet guncelleme hatasi: {str(e)}")

        kaydet_butonu.clicked.connect(sikayet_guncelle)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def sikayet_sil(self):
        selected_items = self.sikayet_tablosu.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir sikayet secin.")
            return

        row = selected_items[0].row()
        musteri_adi = self.sikayet_tablosu.item(row, 0).text()
        sikayet_turu = self.sikayet_tablosu.item(row, 2).text()
        onay = QMessageBox.question(self, "Onay", f"{musteri_adi} - {sikayet_turu} sikayetini silmek istediginize emin misiniz?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if onay == QMessageBox.StandardButton.Yes:
            try:
                # Duzeltme: self.veri_yoneticisi ve self.repository.save yerine services kullaniyoruz
                self.services.data_manager.sikayetler_df = self.services.data_manager.sikayetler_df.drop(row).reset_index(drop=True)
                self.services.data_manager.repository.save(self.services.data_manager.sikayetler_df, "complaints")  # Veritabanini kaydetme
                self.sikayet_tablosu.removeRow(row)
                self.loglayici.info(f"Sikayet silindi: {musteri_adi} - {sikayet_turu}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sikayet silinirken hata: {str(e)}")
                self.loglayici.error(f"Sikayet silme hatasi: {str(e)}")

    def gelismis_arama_dialog(self):
        """Gelismis arama penceresi"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Gelismis Arama")
        yerlesim = QFormLayout()

        # Arama kriterleri
        musteri_adi = QLineEdit()
        sektor = QComboBox()
        sektor.addItems(["", "Teknoloji", "Uretim", "Hizmet", "Diger"])
        bolge = QLineEdit()
        tarih_baslangic = QDateEdit()
        tarih_bitis = QDateEdit()

        yerlesim.addRow("Musteri Adi:", musteri_adi)
        yerlesim.addRow("Sektor:", sektor)
        yerlesim.addRow("Bolge:", bolge)
        yerlesim.addRow("Baslangic Tarihi:", tarih_baslangic)
        yerlesim.addRow("Bitis Tarihi:", tarih_bitis)

        # Butonlar
        butonlar = QHBoxLayout()
        ara_butonu = QPushButton("Ara")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(ara_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)

        dialog.setLayout(yerlesim)

        def arama_yap():
            kriterler = {
                'name': musteri_adi.text() if musteri_adi.text() else None,
                'sector': sektor.currentText() if sektor.currentText() else None,
                'region': bolge.text() if bolge.text() else None,
                'last_purchase_from': tarih_baslangic.date().toString("yyyy-MM-dd"),
                'last_purchase_to': tarih_bitis.date().toString("yyyy-MM-dd")
            }
            # Bos kriterleri kaldir
            kriterler = {k: v for k, v in kriterler.items() if v is not None}
        
            sonuclar = self.services.data_manager.gelismis_arama(kriterler)
            self.arama_sonuclarini_goster(sonuclar)
            dialog.accept()

        ara_butonu.clicked.connect(arama_yap)
        iptal_butonu.clicked.connect(dialog.reject)

        dialog.exec()

    def gosterge_paneli_olustur(self):
        sekme = QWidget()
        self.sekme_widget.addTab(sekme, "Gosterge Paneli")
    
        ana_yerlesim = QVBoxLayout()
        ana_yerlesim.setContentsMargins(5, 5, 5, 5)
        sekme.setLayout(ana_yerlesim)

        # Filtre paneli
        filtre_grup = QGroupBox("Filtreler")
        filtre_yerlesim = QHBoxLayout()
        filtre_yerlesim.setSpacing(10)

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(['bar', 'line', 'area', 'pie', 'funnel', 'treemap'])
        self.chart_type_combo.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(QLabel("Grafik Turu:"))
        filtre_yerlesim.addWidget(self.chart_type_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['plotly', 'plotly_dark', 'ggplot2', 'seaborn'])
        self.theme_combo.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(QLabel("Tema:"))
        filtre_yerlesim.addWidget(self.theme_combo)

        tarih_yerlesim = QVBoxLayout()
        self.baslangic_tarihi = QDateEdit()
        self.baslangic_tarihi.setDate(QDate.currentDate().addMonths(-6))
        self.baslangic_tarihi.dateChanged.connect(self.gosterge_paneli_guncelle)
        tarih_yerlesim.addWidget(QLabel("Baslangic Tarihi:"))
        tarih_yerlesim.addWidget(self.baslangic_tarihi)

        self.bitis_tarihi = QDateEdit()
        self.bitis_tarihi.setDate(QDate.currentDate())
        self.bitis_tarihi.dateChanged.connect(self.gosterge_paneli_guncelle)
        tarih_yerlesim.addWidget(QLabel("Bitis Tarihi:"))
        tarih_yerlesim.addWidget(self.bitis_tarihi)
        filtre_yerlesim.addLayout(tarih_yerlesim)

        self.satisci_filtre = QComboBox()
        self.satisci_filtre.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.satisci_filtre.addItem("Tum Satiscilar")
        self.satisci_filtre.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(QLabel("Satisci:"))
        filtre_yerlesim.addWidget(self.satisci_filtre)

        self.bolge_filtre = QComboBox()
        self.bolge_filtre.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.bolge_filtre.addItem("Tum Iller")
        TURKIYE_ILLERI = ['Adana', 'Adiyaman', 'Afyonkarahisar', 'Agri', 'Aksaray', 'Amasya', 'Ankara', 'Antalya', 'Ardahan',
                          'Artvin', 'Aydin', 'Balikesir', 'Bartin', 'Batman', 'Bayburt', 'Bilecik', 'Bingol', 'Bitlis', 'Bolu',
                          'Burdur', 'Bursa', 'Canakkale', 'Cankiri', 'Corum', 'Denizli', 'Diyarbakir', 'Duzce', 'Edirne',
                          'Elazig', 'Erzincan', 'Erzurum', 'Eskisehir', 'Gaziantep', 'Giresun', 'Gumushane', 'Hakkari', 'Hatay',
                          'Igdir', 'Isparta', 'Istanbul', 'Izmir', 'Kahramanmaras', 'Karabuk', 'Karaman', 'Kars', 'Kastamonu',
                          'Kayseri', 'Kilis', 'Kirikkale', 'Kirklareli', 'Kirsehir', 'Kocaeli', 'Konya', 'Kutahya', 'Malatya',
                          'Manisa', 'Mardin', 'Mersin', 'Mugla', 'Mus', 'Nevsehir', 'Nigde', 'Ordu', 'Osmaniye', 'Rize', 'Sakarya',
                          'Samsun', 'Sanliurfa', 'Siirt', 'Sinop', 'Sirnak', 'Sivas', 'Tekirdag', 'Tokat', 'Trabzon', 'Tunceli',
                          'Usak', 'Van', 'Yalova', 'Yozgat', 'Zonguldak']
        self.bolge_filtre.addItems(TURKIYE_ILLERI)
        self.bolge_filtre.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(QLabel("Il:"))
        filtre_yerlesim.addWidget(self.bolge_filtre)

        self.sektor_filtre = QComboBox()
        self.sektor_filtre.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sektor_filtre.addItem("Tum Sektorler")
        self.sektor_filtre.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(QLabel("Sektor:"))
        filtre_yerlesim.addWidget(self.sektor_filtre)

        self.musteri_adi_filtre = QLineEdit()
        self.musteri_adi_filtre.setPlaceholderText("Musteri Adi Ara...")
        self.musteri_adi_filtre.textChanged.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(QLabel("Musteri Adi:"))
        filtre_yerlesim.addWidget(self.musteri_adi_filtre)

        filtrele_buton = QPushButton("Filtrele")
        filtrele_buton.clicked.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(filtrele_buton)
    
        filtre_grup.setLayout(filtre_yerlesim)
        ana_yerlesim.addWidget(filtre_grup)

        # Grafik gridi (2x3 duzen)
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(10, 10, 10, 10)
        grid_layout.setSpacing(15)

        grafik_listesi = [
            ("Satis Performansi", self.satis_performans_container, 0, 0),
            ("Pipeline Dagilimi", self.pipeline_container, 0, 1),
            ("Musteri Sektor Grafigi", self.musteri_segmentasyon_container, 0, 2),  # Balk deiti
            ("Satis Temsilcisi Performansi", self.satis_temsilcisi_performans_container, 1, 0),
            ("Turkiye Il Satis Haritasi", self.musteri_bolge_dagilim_container, 1, 1),
            ("Aylik Potansiyel Gelir", self.aylik_potansiyel_gelir_container, 1, 2),
        ]

        for baslik, container, row, col in grafik_listesi:
            grafik_yerlesim = QVBoxLayout()
            grafik_widget = QWidget()
            grafik_widget.setLayout(grafik_yerlesim)

            container.setMinimumSize(300, 200)
            container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            grafik_yerlesim.addWidget(container)

            tam_ekran_butonu = QPushButton("Tam Ekran")
            tam_ekran_butonu.clicked.connect(lambda _, c=container: self.tam_ekran_goster(c))
            grafik_yerlesim.addWidget(tam_ekran_butonu, alignment=Qt.AlignmentFlag.AlignCenter)

            grid_layout.addWidget(grafik_widget, row, col)

        ana_yerlesim.addLayout(grid_layout)
        self.filtreleri_guncelle()
        self.gosterge_paneli_guncelle()

    def gosterge_paneli_guncelle(self):
        try:
            filtreler = {
                'baslangic_tarihi': self.baslangic_tarihi.date().toString('yyyy-MM-dd'),
                'bitis_tarihi': self.bitis_tarihi.date().toString('yyyy-MM-dd'),
                'satisci': self.satisci_filtre.currentText() if self.satisci_filtre.currentText() != "Tum Satiscilar" else None,
                'bolge': self.bolge_filtre.currentText() if self.bolge_filtre.currentText() != "Tum Iller" else None,
                'sektor': self.sektor_filtre.currentText() if self.sektor_filtre.currentText() != "Tum Sektorler" else None,
                'musteri_adi': self.musteri_adi_filtre.text().strip() if self.musteri_adi_filtre.text().strip() else None
            }
            if self.is_initialized:
                self.loglayici.info(f"Kullanilan filtreler: {filtreler}")

            chart_type = self.chart_type_combo.currentText().lower()
            theme = self.theme_combo.currentText()

            satislar_df = self.services.data_manager.satislar_df.copy() if self.services.data_manager.satislar_df is not None else pd.DataFrame()
            pipeline_df = self.services.data_manager.pipeline_df.copy() if self.services.data_manager.pipeline_df is not None else pd.DataFrame()
            musteriler_df = self.services.data_manager.musteriler_df.copy() if self.services.data_manager.musteriler_df is not None else pd.DataFrame()
            hedefler_df = self.services.data_manager.aylik_hedefler_df.copy() if self.services.data_manager.aylik_hedefler_df is not None else pd.DataFrame()

            if all(df.empty for df in [satislar_df, pipeline_df, musteriler_df, hedefler_df]):
                if self.is_initialized:
                    QMessageBox.warning(self, "Uyari", "Gosterge paneli icin veri yok.")
                return

            for df, tarih_sutunu in [(satislar_df, 'Ay'), (pipeline_df, 'Tahmini Kapanis Tarihi'), (musteriler_df, 'Son Satin Alma Tarihi')]:
                if not df.empty and tarih_sutunu in df.columns:
                    if tarih_sutunu == 'Ay':
                        df[tarih_sutunu] = pd.to_datetime(df[tarih_sutunu], format='%m-%Y', errors='coerce')
                    else:
                        df[tarih_sutunu] = pd.to_datetime(df[tarih_sutunu], format='%Y-%m-%d', errors='coerce')

            for df in [satislar_df, pipeline_df, musteriler_df]:
                if not df.empty:
                    filtered_df = df.copy()
                    if filtreler['satisci'] and 'Satis Temsilcisi' in df.columns:
                        filtered_df = filtered_df[filtered_df['Satis Temsilcisi'] == filtreler['satisci']]
                    if filtreler['bolge'] and 'Bolge' in df.columns:
                        filtered_df = filtered_df[filtered_df['Bolge'] == filtreler['bolge']]
                    if filtreler['sektor'] and 'Sektor' in df.columns:
                        filtered_df = filtered_df[filtered_df['Sektor'] == filtreler['sektor']]
                    if filtreler['musteri_adi'] and 'Musteri Adi' in df.columns:
                        filtered_df = filtered_df[filtered_df['Musteri Adi'].str.contains(filtreler['musteri_adi'], case=False, na=False)]
                    if filtreler['baslangic_tarihi'] and filtreler['bitis_tarihi']:
                        baslangic = pd.to_datetime(filtreler['baslangic_tarihi'])
                        bitis = pd.to_datetime(filtreler['bitis_tarihi'])
                        tarih_sutunu = 'Ay' if 'Ay' in df.columns else 'Tahmini Kapanis Tarihi' if 'Tahmini Kapanis Tarihi' in df.columns else 'Son Satin Alma Tarihi'
                        if tarih_sutunu in df.columns and df is not musteriler_df:
                            filtered_df = filtered_df[(filtered_df[tarih_sutunu] >= baslangic) & (filtered_df[tarih_sutunu] <= bitis)]
                    if df is satislar_df:
                        satislar_df = filtered_df[satislar_df.columns].astype(satislar_df.dtypes.to_dict())
                    elif df is pipeline_df:
                        pipeline_df = filtered_df[pipeline_df.columns].astype(pipeline_df.dtypes.to_dict())
                    elif df is musteriler_df:
                        musteriler_df = filtered_df[musteriler_df.columns].astype(musteriler_df.dtypes.to_dict())

            self.loglayici.info(f"Filtreleme sonrasi - Satislar: {len(satislar_df)}, Pipeline: {len(pipeline_df)}, Musteriler: {len(musteriler_df)}")
            self.loglayici.debug(f"Filtre sonrasi pipeline_df: {pipeline_df.to_dict(orient='records')}")

            # Grafikleri ana thread'de guncelle
            def update_satis_grafik():
                try:
                    satis_widget = self.gorsellestirici.satis_performansi_grafigi_olustur(hedefler_df, satislar_df, filtreler, chart_type, theme)
                    self._temizle_ve_ekle_widget(self.satis_performans_container, satis_widget or self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Satis performansi grafigi olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    self._temizle_ve_ekle_widget(self.satis_performans_container, self.gorsellestirici._create_empty_web_view())
            QTimer.singleShot(0, update_satis_grafik)

            def update_pipeline_grafik():
                try:
                    pipeline_widget = self.gorsellestirici.pipeline_grafigi_olustur(pipeline_df, chart_type if chart_type in ['pie', 'bar', 'funnel'] else 'pie', theme)
                    self._temizle_ve_ekle_widget(self.pipeline_container, pipeline_widget or self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Pipeline grafigi olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    self._temizle_ve_ekle_widget(self.pipeline_container, self.gorsellestirici._create_empty_web_view())
            QTimer.singleShot(0, update_pipeline_grafik)

            def update_segmentasyon_grafik():
                try:
                    sektor_widget = self.gorsellestirici.musteri_sektor_grafigi_olustur(  # Yeni metod ar
                        musteriler_df, 
                        chart_type if chart_type in ['pie', 'bar', 'treemap'] else 'pie',  # Pie varsaylan
                        theme
                    )
                    self._temizle_ve_ekle_widget(self.musteri_segmentasyon_container, sektor_widget or self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Musteri sektor grafigi olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    self._temizle_ve_ekle_widget(self.musteri_segmentasyon_container, self.gorsellestirici._create_empty_web_view())
            QTimer.singleShot(0, update_segmentasyon_grafik)

            def update_temsilci_grafik():
                try:
                    satis_temsilcisi_widget = self.gorsellestirici.satis_temsilcisi_performansi_grafigi_olustur(satislar_df, chart_type, theme)
                    self._temizle_ve_ekle_widget(self.satis_temsilcisi_performans_container, satis_temsilcisi_widget or self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Satis temsilcisi performansi grafigi olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    self._temizle_ve_ekle_widget(self.satis_temsilcisi_performans_container, self.gorsellestirici._create_empty_web_view())
            QTimer.singleShot(0, update_temsilci_grafik)

            def update_harita_grafik():
                try:
                    if not satislar_df.empty and not musteriler_df.empty:
                        if 'Bolge' not in musteriler_df.columns or musteriler_df['Bolge'].isna().all():
                            self.loglayici.warning("Musteriler_df'de 'Bolge' sutunu eksik veya tum degerler NaN, harita olusturulamiyor.")
                            empty_map = QWebEngineView()
                            empty_map.setHtml("<p>Harita icin 'Bolge' verisi eksik.</p>")
                            self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, empty_map)
                        else:
                            il_satis = satislar_df.merge(musteriler_df[['Musteri Adi', 'Bolge']], left_on='Ana Musteri', right_on='Musteri Adi', how='left')
                            il_satis['Bolge'] = il_satis['Bolge'].str.strip().str.title()
                            il_satis_grup = il_satis.groupby('Bolge')['Satis Miktari'].sum().reset_index()
                            self.loglayici.debug(f"Harita icin il bazinda satislar: {il_satis_grup.to_dict(orient='records')}")

                            m = folium.Map(location=[39.925533, 32.866287], zoom_start=6)
                            geojson_path = os.path.join(os.path.dirname(sys.argv[0]), "turkey.geojson")
                            if not os.path.exists(geojson_path):
                                self.loglayici.warning(f"turkey.geojson dosyasi bulunamadi: {geojson_path}. Harita olusturulamiyor.")
                                empty_map = QWebEngineView()
                                empty_map.setHtml("<p>Harita icin turkey.geojson dosyasi eksik.</p>")
                                self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, empty_map)
                            else:
                                self.loglayici.info(f"turkey.geojson dosyasi basariyla bulundu: {geojson_path}")
                                try:
                                    with open(geojson_path, 'r', encoding='utf-8') as f:
                                        geo_data = json.load(f)
                                    self.loglayici.debug("turkey.geojson dosyasi yuklendi.")
                                except Exception as e:
                                    self.loglayici.error(f"turkey.geojson dosyasi acilirken hata: {str(e)}")
                                    empty_map = QWebEngineView()
                                    empty_map.setHtml("<p>Harita icin turkey.geojson dosyasi gecersiz veya bozuk.</p>")
                                    self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, empty_map)
                                    return

                                for feature in geo_data['features']:
                                    feature['properties']['name'] = feature['properties']['name'].strip().title()

                                folium.Choropleth(
                                    geo_data=geo_data,
                                    name='choropleth',
                                    data=il_satis_grup,
                                    columns=['Bolge', 'Satis Miktari'],
                                    key_on='feature.properties.name',
                                    fill_color='YlOrRd',
                                    fill_opacity=0.7,
                                    line_opacity=0.2,
                                    legend_name='Satis Miktari (TL)'
                                ).add_to(m)

                                for feature in geo_data['features']:
                                    il_adi = feature['properties']['name']
                                    satis_miktari = il_satis_grup[il_satis_grup['Bolge'] == il_adi]['Satis Miktari'].sum() if il_adi in il_satis_grup['Bolge'].values else 0
                                    feature['properties']['Satis Miktari'] = float(satis_miktari)

                                folium.GeoJson(
                                    geo_data,
                                    tooltip=folium.GeoJsonTooltip(
                                        fields=['name', 'Satis Miktari'],
                                        aliases=['Il:', 'Satis Miktari:'],
                                        localize=True
                                    )
                                ).add_to(m)

                                html = m._repr_html_()
                                map_view = QWebEngineView()
                                map_view.setHtml(html)
                                map_view.setProperty("html", html)
                                self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, map_view)
                                self.musteri_bolge_dagilim_container.setProperty("html", html)
                                self.loglayici.info("Harita basariyla olusturuldu ve yuklendi.")
                    else:
                        self.loglayici.warning("Harita icin satis veya musteri verisi mevcut degil.")
                        empty_map = QWebEngineView()
                        empty_map.setHtml("<p>Harita icin satis veya musteri verisi mevcut degil.</p>")
                        self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, empty_map)
                except Exception as e:
                    self.loglayici.error(f"Harita grafigi olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, self.gorsellestirici._create_empty_web_view())
            QTimer.singleShot(0, update_harita_grafik)

            def update_potansiyel_grafik():
                try:
                    aylik_potansiyel_widget = self.gorsellestirici.aylik_potansiyel_gelir_grafigi_olustur(pipeline_df, filtreler, chart_type, theme)
                    self.loglayici.debug(f"Aylik potansiyel gelir widget olusturuldu mu: {aylik_potansiyel_widget is not None}")
                    self._temizle_ve_ekle_widget(self.aylik_potansiyel_gelir_container, aylik_potansiyel_widget or self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Aylik potansiyel gelir grafigi olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    self._temizle_ve_ekle_widget(self.aylik_potansiyel_gelir_container, self.gorsellestirici._create_empty_web_view())
            QTimer.singleShot(0, update_potansiyel_grafik)

        except Exception as e:
            self.loglayici.error(f"Gosterge paneli guncellenirken genel hata: {str(e)}")
            import traceback
            self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
            QMessageBox.warning(self, "Hata", f"Gosterge paneli guncellenemedi: {str(e)}")
            for container in [self.satis_performans_container, self.pipeline_container, 
                              self.musteri_segmentasyon_container, self.satis_temsilcisi_performans_container, 
                              self.musteri_bolge_dagilim_container, self.aylik_potansiyel_gelir_container]:
                self._temizle_ve_ekle_widget(container, self.gorsellestirici._create_empty_web_view())

    def tam_ekran_goster(self, container):
        """Grafigi tam ekran gosteren yeni bir pencere acar"""
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        dialog = QDialog(self)
        dialog.setWindowTitle("Tam Ekran Grafik")
        dialog.setGeometry(100, 100, 1000, 800)  # Tam ekran boyutu
        layout = QVBoxLayout()

        # Yeni bir QWebEngineView olustur
        web_view = QWebEngineView()

        # Container'in HTML icerigini al
        if container == self.musteri_bolge_dagilim_container:
            # Harita icin ozel durum: Container'in sakladigi HTML'i kullan
            html = container.property("html")
            if html:
                web_view.setHtml(html)
            else:
                web_view.setHtml("<p>Harita verisi bulunamadi.</p>")
        else:
            # Diger grafikler icin (Plotly gibi)
            if container.layout() and container.layout().count() > 0:
                grafik_widget = container.layout().itemAt(0).widget()
                html = grafik_widget.property("html") or grafik_widget.url().toString()
                if html:
                    web_view.setHtml(html)
                else:
                    web_view.setHtml("<p>Grafik bulunamadi.</p>")
            else:
                web_view.setHtml("<p>Grafik bulunamadi.</p>")

        layout.addWidget(web_view)
        dialog.setLayout(layout)
        dialog.exec()

    def _temizle_ve_ekle_widget(self, container, widget):
        """Container icerigini temizle ve yeni widget ekle"""
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout()
            container.setLayout(layout)
        else:
            # Mevcut widget'lari temizle
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
    
        layout.addWidget(widget)

    def filtreleri_guncelle(self):
        """Filtre seceneklerini veriyle dinamik olarak gunceller"""
        try:
            # Satici filtresi
            self.satisci_filtre.clear()
            self.satisci_filtre.addItem("Tum Satiscilar")
            if (self.services.data_manager.satiscilar_df is not None and 
                not self.services.data_manager.satiscilar_df.empty and 
                'Isim' in self.services.data_manager.satiscilar_df.columns):
                satiscilar = self.services.data_manager.satiscilar_df['Isim'].dropna().unique().tolist()
                self.satisci_filtre.addItems([str(s) for s in satiscilar])  # String donusumu
                self.loglayici.info(f"Satisci filtresi guncellendi: {len(satiscilar)} secenek")
            else:
                self.loglayici.debug("Satisci verisi yok veya 'Isim' sutunu eksik, filtreye sadece 'Tum Satiscilar' eklendi.")  # WARNING yerine DEBUG

            # Bolge filtresi
            self.bolge_filtre.clear()
            self.bolge_filtre.addItem("Tum Iller")
            if (self.services.data_manager.musteriler_df is not None and 
                not self.services.data_manager.musteriler_df.empty and 
                'Bolge' in self.services.data_manager.musteriler_df.columns):
                bolgeler = self.services.data_manager.musteriler_df['Bolge'].dropna().unique().tolist()
                self.bolge_filtre.addItems([str(b) for b in bolgeler])  # String donusumu
                self.loglayici.info(f"Bolge filtresi guncellendi: {len(bolgeler)} secenek")
            else:
                self.loglayici.debug("Musteri verisi yok veya 'Bolge' sutunu eksik, filtreye sadece 'Tum Iller' eklendi.")  # WARNING yerine DEBUG

            # Sektor filtresi
            self.sektor_filtre.clear()
            self.sektor_filtre.addItem("Tum Sektorler")
            if (self.services.data_manager.musteriler_df is not None and 
                not self.services.data_manager.musteriler_df.empty and 
                'Sektor' in self.services.data_manager.musteriler_df.columns):
                sektorler = self.services.data_manager.musteriler_df['Sektor'].dropna().unique().tolist()
                self.sektor_filtre.addItems([str(s) for s in sektorler])  # String donusumu
                self.loglayici.info(f"Sektor filtresi guncellendi: {len(sektorler)} secenek")
            else:
                self.loglayici.debug("Musteri verisi yok veya 'Sektor' sutunu eksik, filtreye sadece 'Tum Sektorler' eklendi.")  # WARNING yerine DEBUG

        except Exception as e:
            self.loglayici.error(f"Filtreler guncellenirken hata: {str(e)}")
            QMessageBox.warning(self, "Hata", f"Filtreler guncellenemedi: {str(e)}")

    def arama_sonuclarini_goster(self, sonuclar):
        dialog = QDialog(self)
        dialog.setWindowTitle("Arama Sonuclari")
        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setText(str(sonuclar))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        dialog.setLayout(layout)
        dialog.exec()

    def tum_sekmeleri_guncelle(self, event: Event = None) -> None:
        """Tum sekmeleri gunceller"""
        if not self.is_initialized:
            return
            
        try:
            # Satis modulu tablolarini guncelle
            if hasattr(self._satis_mixin, 'satisci_tablosu_guncelle'):
                self._satis_mixin.satisci_tablosu_guncelle()
                
            if hasattr(self._satis_mixin, 'satis_hedefleri_tablosu_guncelle'):
                self._satis_mixin.satis_hedefleri_tablosu_guncelle()
                
            if hasattr(self._satis_mixin, 'pipeline_tablosu_guncelle'):
                self._satis_mixin.pipeline_tablosu_guncelle()
                
            if hasattr(self._satis_mixin, 'musteri_tablosu_guncelle'):
                self._satis_mixin.musteri_tablosu_guncelle()
                
            if hasattr(self._satis_mixin, 'satis_tablosu_guncelle'):
                self._satis_mixin.satis_tablosu_guncelle()
                
            if hasattr(self._satis_mixin, 'ziyaret_tablosu_guncelle'):
                self._satis_mixin.ziyaret_tablosu_guncelle()
            
            # Hammadde modulu tablolarini guncelle
            if hasattr(self._hammadde_mixin, 'hammadde_tablosu_guncelle'):
                self._hammadde_mixin.hammadde_tablosu_guncelle()
                
            if hasattr(self._hammadde_mixin, 'urun_bom_tablosu_guncelle'):
                self._hammadde_mixin.urun_bom_tablosu_guncelle()
            
            self.sikayet_tablosu_guncelle()
            self.gosterge_paneli_guncelle()
            
            self.statusBar().showMessage("Tum veriler guncellendi")
        except Exception as e:
            self.loglayici.error(f"Tablolar guncellenirken hata: {str(e)}")
            self.statusBar().showMessage(f"Guncelleme hatasi: {str(e)}")

    def closeEvent(self, event):
        """Program kapatildiginda tum islemleri duzgun sekilde sonlandir"""
        try:
            self.loglayici.info("Program kapatiliyor...")
            
            # Zamanlayiciyi durdur
            if self.zamanlayici:
                try:
                    self.zamanlayici.durdur()
                    self.loglayici.info("Zamanlayici durduruldu.")
                except Exception as e:
                    self.loglayici.error(f"Zamanlayici durdurulurken hata: {str(e)}")
                
            # Guncelleme zamanlayicisini durdur
            if hasattr(self, 'guncelleme_zamanlayicisi'):
                try:
                    self.guncelleme_zamanlayicisi.stop()
                    self.loglayici.info("Guncelleme zamanlayicisi durduruldu.")
                except Exception as e:
                    self.loglayici.error(f"Guncelleme zamanlayicisi durdurulurken hata: {str(e)}")
                
            # Tum thread'leri sonlandir
            if hasattr(self, 'worker') and self.worker:
                try:
                    if self.worker.isRunning():
                        self.loglayici.info("Worker thread sonlandiriliyor...")
                        self.worker.terminate()
                        self.worker.wait(2000)  # 2 saniye bekle
                        if self.worker.isRunning():
                            self.loglayici.warning("Worker thread 2 saniye icinde sonlanmadi, zorla kapatiliyor.")
                            import sys
                            sys.exit(0)  # Zorla kapat
                    self.worker = None
                    self.loglayici.info("Worker thread sonlandirildi.")
                except Exception as e:
                    self.loglayici.error(f"Worker thread sonlandirilirken hata: {str(e)}")
            
            # Event manager'i temizle
            if self.event_manager:
                try:
                    self.event_manager.unsubscribe_all()
                    self.loglayici.info("Event manager temizlendi.")
                except Exception as e:
                    self.loglayici.error(f"Event manager temizlenirken hata: {str(e)}")
                
            # Veritabani baglantisini kapat
            if self.services and self.services.data_manager and self.services.data_manager.repository:
                try:
                    self.services.data_manager.repository.close()
                    self.loglayici.info("Veritabani baglantisi kapatildi.")
                except Exception as e:
                    self.loglayici.error(f"Veritabani baglantisi kapatilirken hata: {str(e)}")
                
            # Mixin siniflarin kaynaklarini temizle
            if hasattr(self, '_satis_mixin'):
                self._satis_mixin = None
                
            if hasattr(self, '_hammadde_mixin'):
                self._hammadde_mixin = None
                
            self.loglayici.info("Program duzgun sekilde kapatildi")
            event.accept()
            
        except Exception as e:
            self.loglayici.error(f"Program kapatilirken hata: {str(e)}")
            import traceback
            self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
            event.accept()  # Yine de kabul et

    def kohort_analizi_raporu_olustur(self):
        """Kohort analizi raporu olusturur"""
        try:
            # Tarih secme dialogu
            dialog = QDialog(self)
            dialog.setWindowTitle("Kohort Analizi Parametreleri")
            dialog.setMinimumWidth(400)
            
            layout = QVBoxLayout()
            
            # Tarih araligi secimi
            form_layout = QFormLayout()
            
            # Baslangic tarihi
            baslangic_tarihi_label = QLabel("Baslangic Tarihi:")
            baslangic_tarihi_edit = QDateEdit()
            baslangic_tarihi_edit.setCalendarPopup(True)
            baslangic_tarihi_edit.setDate(QDate.currentDate().addMonths(-12))  # Son 12 ay
            form_layout.addRow(baslangic_tarihi_label, baslangic_tarihi_edit)
            
            # Bitis tarihi
            bitis_tarihi_label = QLabel("Bitis Tarihi:")
            bitis_tarihi_edit = QDateEdit()
            bitis_tarihi_edit.setCalendarPopup(True)
            bitis_tarihi_edit.setDate(QDate.currentDate())
            form_layout.addRow(bitis_tarihi_label, bitis_tarihi_edit)
            
            # Aciklama
            aciklama_label = QLabel("Kohort analizi, musterilerin ilk satin alma tarihlerine gore gruplandirarak, zaman icindeki davranislarini analiz eder. Bu analiz, musteri tutma oranlarini, ortalama siparis degerlerini ve toplam satis miktarlarini gosterir.")
            aciklama_label.setWordWrap(True)
            
            # Butonlar
            butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            
            layout.addLayout(form_layout)
            layout.addWidget(aciklama_label)
            layout.addWidget(butonlar)
            
            dialog.setLayout(layout)
            
            butonlar.accepted.connect(dialog.accept)
            butonlar.rejected.connect(dialog.reject)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Secilen tarih araligini al
                baslangic_tarihi = baslangic_tarihi_edit.date().toString("yyyy-MM-dd")
                bitis_tarihi = bitis_tarihi_edit.date().toString("yyyy-MM-dd")
                
                # Ilerleme dialogu
                ilerleme_dialog = QDialog(self)
                ilerleme_dialog.setWindowTitle("Kohort Analizi Olusturuluyor")
                ilerleme_dialog.setFixedSize(400, 100)
                
                ilerleme_layout = QVBoxLayout()
                ilerleme_label = QLabel("Kohort analizi olusturuluyor, lutfen bekleyin...")
                ilerleme_cubugu = QProgressBar()
                ilerleme_cubugu.setRange(0, 0)  # Belirsiz ilerleme
                
                ilerleme_layout.addWidget(ilerleme_label)
                ilerleme_layout.addWidget(ilerleme_cubugu)
                
                ilerleme_dialog.setLayout(ilerleme_layout)
                ilerleme_dialog.show()
                
                # Islem sirasinda UI'nin donmasini onlemek icin QTimer kullan
                QTimer.singleShot(100, lambda: self._kohort_analizi_olustur(baslangic_tarihi, bitis_tarihi, ilerleme_dialog))
                
        except Exception as e:
            self.loglayici.error(f"Kohort analizi raporu olusturulurken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Kohort analizi raporu olusturulurken hata: {str(e)}")
    
    def _kohort_analizi_olustur(self, baslangic_tarihi, bitis_tarihi, ilerleme_dialog):
        """Kohort analizi raporunu olusturur ve gosterir"""
        try:
            # Kohort analizi raporu olustur
            sonuc = self.services.generate_kohort_report(
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi
            )
            
            # Ilerleme dialogunu kapat
            ilerleme_dialog.accept()
            
            if not sonuc.get("success", False):
                QMessageBox.warning(self, "Uyari", sonuc.get("message", "Kohort analizi olusturulamadi."))
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
            QMessageBox.information(self, "Basarili", "Kohort analizi raporu olusturuldu.")
            
        except Exception as e:
            self.loglayici.error(f"Kohort analizi raporu olusturulurken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Kohort analizi raporu olusturulurken hata: {str(e)}")

