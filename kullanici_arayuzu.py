# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QPushButton, QMessageBox, QLabel, QScrollArea, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLineEdit, QFormLayout, QDateEdit,
                             QComboBox, QTextEdit, QDialog, QProgressBar, QFileDialog, QListWidget,
                             QGroupBox, QSizePolicy, QGridLayout, QScrollArea, QPushButton, QDialog,
                             QDialogButtonBox, QAbstractItemView, QFrame, QButtonGroup, QStackedWidget,
                             QApplication)
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
# Yeni importlar
from raporlama import Raporlama
from sikayet_yonetimi import SikayetYonetimi
from datetime import datetime

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
        self.gorsellestirici = Gorsellestirici(self.loglayici, self.event_manager, self.services)

        # Internet baglantisi kontrolu ekle
        self.internet_baglantisi = InternetBaglantisi(loglayici, event_manager)
        
        # Raporlama ve Sikayet Yonetimi siniflarini olustur
        self.raporlama = Raporlama(self, services, loglayici, self.gorsellestirici)
        self.sikayet_yonetimi = SikayetYonetimi(self, services, loglayici)
        
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
        self.sikayet_yonetimi.sikayet_yonetimi_olustur()
        
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
        """Ana menuyu olusturur"""
        menubar = self.menuBar()
        
        # Dosya menusu
        dosya_menu = menubar.addMenu('Dosya')
        
        veri_yukle_action = QAction('Veri Yukle', self)
        veri_yukle_action.triggered.connect(self.tum_verileri_yukle)
        dosya_menu.addAction(veri_yukle_action)
        
        veri_kaydet_action = QAction('Veri Kaydet', self)
        veri_kaydet_action.triggered.connect(self.tum_verileri_kaydet)
        dosya_menu.addAction(veri_kaydet_action)
        
        cikis_action = QAction('Cikis', self)
        cikis_action.triggered.connect(self.close)
        dosya_menu.addAction(cikis_action)
        
        # Raporlar menusu
        raporlar_menusu = self.raporlama.raporlar_menusu_olustur()
        
        # Yardim menusu
        yardim_menu = menubar.addMenu('Yardim')
        
        hakkinda_action = QAction('Hakkinda', self)
        hakkinda_action.triggered.connect(self.hakkinda_goster)
        yardim_menu.addAction(hakkinda_action)

    def create_action(self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False):
        """
        Yeni bir QAction olusturur ve yapilandirir.
        
        Args:
            text (str): Aksiyon metni
            slot: Tetiklendiginde calisacak fonksiyon
            shortcut: Klavye kisayolu
            icon: Ikon dosyasi
            tip: Ipucu metni
            checkable (bool): Isaretlenebilir olup olmadigi
            
        Returns:
            QAction: Olusturulan aksiyon nesnesi
        """
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon(icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.triggered.connect(slot)
        if checkable:
            action.setCheckable(True)
        return action

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

    def gosterge_paneli_olustur(self):
        sekme = QWidget()
        self.sekme_widget.addTab(sekme, "Gosterge Paneli")
    
        ana_yerlesim = QVBoxLayout()
        ana_yerlesim.setContentsMargins(5, 2, 5, 2)  # Ust margin 5'ten 2'ye dusuruldu
        ana_yerlesim.setSpacing(1)  # Ana yerlesim spacing'i 2'den 1'e dusuruldu
        sekme.setLayout(ana_yerlesim)
        sekme.setStyleSheet("""
            QWidget {
                background-color: #333;
            }
            QGroupBox {
                margin-top: 1px;  /* GroupBox margin 2'den 1'e dusuruldu */
                padding-top: 1px;  /* GroupBox padding 2'den 1'e dusuruldu */
            }
        """)
        
        # Filtre container'i olustur
        filtre_container = QWidget()
        filtre_container_layout = QVBoxLayout()
        filtre_container_layout.setContentsMargins(0, 0, 0, 0)  # Container margin'lerini sifirla
        filtre_container_layout.setSpacing(0)  # Container icindeki spacing'i sifirla
        filtre_container.setLayout(filtre_container_layout)
        
        # Hamburger menu baslik butonu
        filtre_baslik_container = QWidget()
        filtre_baslik_layout = QHBoxLayout()
        filtre_baslik_layout.setContentsMargins(5, 1, 5, 1)  # Ust ve alt margin'i 1'e dusur
        filtre_baslik_container.setLayout(filtre_baslik_layout)
        filtre_baslik_container.setStyleSheet("""
            QWidget {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 8px;
                margin: 0px;
                padding: 1px;  /* Padding'i azalt */
            }
        """)
        
        filtre_baslik = QLabel("Filtreler")
        filtre_baslik.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
            margin: 0px;
            padding: 1px;  /* Padding'i azalt */
        """)
        filtre_baslik_layout.addWidget(filtre_baslik)
        
        filtre_baslik_layout.addStretch()
        
        self.filtre_toggle_buton = QPushButton("▼")  # Asagi ok
        self.filtre_toggle_buton.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 1px;  /* Padding'i azalt */
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        self.filtre_toggle_buton.setFixedSize(20, 20)  # Buton boyutunu kucult
        self.filtre_toggle_buton.clicked.connect(self.filtre_paneli_toggle)
        filtre_baslik_layout.addWidget(self.filtre_toggle_buton)
        
        filtre_container_layout.addWidget(filtre_baslik_container)
        
        # Filtre paneli icerigi
        self.filtre_icerik_container = QWidget()
        filtre_icerik_layout = QVBoxLayout()
        filtre_icerik_layout.setContentsMargins(0, 0, 0, 0)  # Tum margin'leri sifirla
        filtre_icerik_layout.setSpacing(1)  # Spacing'i azalt
        self.filtre_icerik_container.setLayout(filtre_icerik_layout)
        
        # Filtre paneli
        filtre_grup = QGroupBox()
        filtre_grup.setStyleSheet("""
            QGroupBox {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 8px;
                margin-top: 0px;
                padding-top: 2px;
                font-weight: bold;
                color: white;
            }
        """)
        
        filtre_yerlesim = QHBoxLayout()
        filtre_yerlesim.setSpacing(5)  # Spacing azaltildi
        filtre_yerlesim.setContentsMargins(5, 2, 5, 2)  # Margin'ler azaltildi
        
        # Grafik ayarlari grubu
        grafik_ayarlari_grup = QGroupBox("Grafik Ayarlari")
        grafik_ayarlari_grup.setStyleSheet("""
            QGroupBox {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #333;
                color: white;
            }
            QComboBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 120px;
                background-color: #444;
                color: white;
            }
            QComboBox:hover {
                border: 1px solid #1565C0;
                background-color: #505050;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #444;
                color: white;
                selection-background-color: #1565C0;
            }
            QLabel {
                color: white;
                font-weight: normal;
            }
        """)
        
        grafik_ayarlari_layout = QVBoxLayout()
        grafik_ayarlari_layout.setSpacing(8)
        
        # Grafik turu
        grafik_turu_layout = QHBoxLayout()
        grafik_turu_layout.addWidget(QLabel("Grafik Turu:"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(['bar', 'line', 'area', 'pie', 'funnel', 'treemap'])
        self.chart_type_combo.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        grafik_turu_layout.addWidget(self.chart_type_combo)
        grafik_ayarlari_layout.addLayout(grafik_turu_layout)
        
        # Tema
        tema_layout = QHBoxLayout()
        tema_layout.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['plotly', 'plotly_dark', 'ggplot2', 'seaborn'])
        self.theme_combo.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        tema_layout.addWidget(self.theme_combo)
        grafik_ayarlari_layout.addLayout(tema_layout)
        
        grafik_ayarlari_grup.setLayout(grafik_ayarlari_layout)
        filtre_yerlesim.addWidget(grafik_ayarlari_grup)
        
        # Tarih filtresi grubu
        tarih_filtresi_grup = QGroupBox("Tarih Araligi")
        tarih_filtresi_grup.setStyleSheet("""
            QGroupBox {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #333;
                color: white;
            }
            QDateEdit {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 120px;
                background-color: #444;
                color: white;
            }
            QDateEdit:hover {
                border: 1px solid #1565C0;
                background-color: #505050;
            }
            QDateEdit::drop-down {
                border: none;
                width: 20px;
            }
            QCalendarWidget {
                background-color: #444;
                color: white;
            }
            QLabel {
                color: white;
                font-weight: normal;
            }
        """)
        
        tarih_yerlesim = QVBoxLayout()
        tarih_yerlesim.setSpacing(8)
        
        # Baslangic tarihi
        baslangic_layout = QHBoxLayout()
        baslangic_layout.addWidget(QLabel("Baslangic:"))
        self.baslangic_tarihi = QDateEdit()
        self.baslangic_tarihi.setCalendarPopup(True)  # Takvim widget'ini acik hale getir
        self.baslangic_tarihi.setDisplayFormat("dd.MM.yyyy")  # Tarih formati
        self.baslangic_tarihi.setMinimumDate(QDate(2000, 1, 1))  # Minimum tarih
        self.baslangic_tarihi.setMaximumDate(QDate.currentDate())  # Maksimum tarih
        self.baslangic_tarihi.setDate(QDate.currentDate().addMonths(-6))  # Varsayilan deger: 6 ay once
        self.baslangic_tarihi.dateChanged.connect(self.gosterge_paneli_guncelle)
        baslangic_layout.addWidget(self.baslangic_tarihi)
        tarih_yerlesim.addLayout(baslangic_layout)
        
        # Bitis tarihi
        bitis_layout = QHBoxLayout()
        bitis_layout.addWidget(QLabel("Bitis:"))
        self.bitis_tarihi = QDateEdit()
        self.bitis_tarihi.setCalendarPopup(True)  # Takvim widget'ini acik hale getir
        self.bitis_tarihi.setDisplayFormat("dd.MM.yyyy")  # Tarih formati
        self.bitis_tarihi.setMinimumDate(QDate(2000, 1, 1))  # Minimum tarih
        self.bitis_tarihi.setMaximumDate(QDate.currentDate().addYears(1))  # Maksimum tarih: 1 yil sonrasi
        self.bitis_tarihi.setDate(QDate.currentDate())  # Varsayilan deger: bugun
        self.bitis_tarihi.dateChanged.connect(self.gosterge_paneli_guncelle)
        bitis_layout.addWidget(self.bitis_tarihi)
        tarih_yerlesim.addLayout(bitis_layout)
        
        tarih_filtresi_grup.setLayout(tarih_yerlesim)
        filtre_yerlesim.addWidget(tarih_filtresi_grup)
        
        # Veri filtresi grubu
        veri_filtresi_grup = QGroupBox("Veri Filtreleri")
        veri_filtresi_grup.setStyleSheet("""
            QGroupBox {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #333;
                color: white;
            }
            QComboBox, QLineEdit {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 150px;
                background-color: #444;
                color: white;
            }
            QComboBox:hover, QLineEdit:hover {
                border: 1px solid #1565C0;
                background-color: #505050;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #444;
                color: white;
                selection-background-color: #1565C0;
            }
            QLabel {
                color: white;
                font-weight: normal;
            }
        """)
        
        veri_filtresi_layout = QGridLayout()
        veri_filtresi_layout.setSpacing(8)
        
        # Satisci filtresi
        veri_filtresi_layout.addWidget(QLabel("Satisci:"), 0, 0)
        self.satisci_filtre = QComboBox()
        self.satisci_filtre.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.satisci_filtre.addItem("Tum Satiscilar")
        self.satisci_filtre.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        veri_filtresi_layout.addWidget(self.satisci_filtre, 0, 1)
        
        # Bolge filtresi
        veri_filtresi_layout.addWidget(QLabel("Il:"), 1, 0)
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
        veri_filtresi_layout.addWidget(self.bolge_filtre, 1, 1)
        
        # Sektor filtresi
        veri_filtresi_layout.addWidget(QLabel("Sektor:"), 0, 2)
        self.sektor_filtre = QComboBox()
        self.sektor_filtre.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sektor_filtre.addItem("Tum Sektorler")
        self.sektor_filtre.currentTextChanged.connect(self.gosterge_paneli_guncelle)
        veri_filtresi_layout.addWidget(self.sektor_filtre, 0, 3)
        
        # Musteri adi filtresi
        veri_filtresi_layout.addWidget(QLabel("Musteri:"), 1, 2)
        self.musteri_adi_filtre = QLineEdit()
        self.musteri_adi_filtre.setPlaceholderText("Musteri Adi Ara...")
        self.musteri_adi_filtre.textChanged.connect(self.gosterge_paneli_guncelle)
        veri_filtresi_layout.addWidget(self.musteri_adi_filtre, 1, 3)
        
        veri_filtresi_grup.setLayout(veri_filtresi_layout)
        filtre_yerlesim.addWidget(veri_filtresi_grup)
        
        # Filtrele butonu
        filtrele_buton = QPushButton("Filtrele")
        filtrele_buton.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
            QPushButton:pressed {
                background-color: #0A3D91;
            }
        """)
        filtrele_buton.clicked.connect(self.gosterge_paneli_guncelle)
        filtre_yerlesim.addWidget(filtrele_buton, alignment=Qt.AlignmentFlag.AlignBottom)
    
        filtre_grup.setLayout(filtre_yerlesim)
        filtre_icerik_layout.addWidget(filtre_grup)
        
        filtre_container_layout.addWidget(self.filtre_icerik_container)
        ana_yerlesim.addWidget(filtre_container, 0, Qt.AlignmentFlag.AlignTop)  # Filtre container'i uste hizala
        ana_yerlesim.addWidget(self.filtre_icerik_container)
        
        
        # Baslangicta filtre panelini gizle
        self.filtre_icerik_container.setVisible(False)
        self.filtre_toggle_buton.setText("▼")  # Asagi ok

        # Sayfa secim menusu olustur - Filtrelerden hemen sonra eklendi
        self.sayfa_secim_container = QWidget()
        sayfa_secim_layout = QHBoxLayout()
        sayfa_secim_layout.setContentsMargins(0, 0, 0, 0)  # Tum margin'leri sifirla
        sayfa_secim_layout.setSpacing(0)
        self.sayfa_secim_container.setLayout(sayfa_secim_layout)
        
        # Sayfa butonlari icin stil
        sayfa_buton_stili = """
        QPushButton {
            background-color: #333;
            border: none;
            border-bottom: 3px solid transparent;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: bold;
            color: white;
            min-width: 150px;
        }
        QPushButton:hover {
            background-color: #444;
        }
        QPushButton:checked {
            border-bottom: 3px solid #1565C0;
            color: #ffffff;
            background-color: #3a3a3a;
        }
        """
        
        # Sayfa butonlari
        self.sayfa_butonlari = []
        
        sayfa_bilgileri = [
            {"id": "genel", "baslik": "Genel Rapor", "icon": "📑"},
            {"id": "satis", "baslik": "Satis Performansi", "icon": "📊"},
            {"id": "musteri", "baslik": "Musteri Analizi", "icon": "👥"},
            {"id": "harita", "baslik": "Bolgesel Analiz", "icon": "🗺️"},
            {"id": "pipeline", "baslik": "Pipeline Analizi", "icon": "📈"}
        ]
        
        # Buton grubu olustur
        self.sayfa_buton_grubu = QButtonGroup(self)
        self.sayfa_buton_grubu.setExclusive(True)
        
        for sayfa in sayfa_bilgileri:
            buton = QPushButton(f"{sayfa['icon']} {sayfa['baslik']}")
            buton.setCheckable(True)
            buton.setProperty("sayfa_id", sayfa["id"])
            buton.setStyleSheet(sayfa_buton_stili)
            self.sayfa_buton_grubu.addButton(buton)
            self.sayfa_butonlari.append(buton)
            sayfa_secim_layout.addWidget(buton)
            buton.clicked.connect(self.sayfa_degistir)
        
        # Ilk butonu secili yap
        if self.sayfa_butonlari:
            self.sayfa_butonlari[0].setChecked(True)
        
        sayfa_secim_layout.addStretch()
        ana_yerlesim.addWidget(self.sayfa_secim_container)
        
        # Sayfa icerik alani
        self.sayfa_icerik_container = QStackedWidget()
        self.sayfa_icerik_container.setMinimumHeight(500)
        self.sayfa_icerik_container.setStyleSheet("""
            QStackedWidget {
                background-color: #333;
            }
        """)
        ana_yerlesim.addWidget(self.sayfa_icerik_container)
        
        # Pasta grafik container'larini ve ilgili layout'lari siliyorum

        # Baslangicta filtre panelini gizle
        self.filtre_icerik_container.setVisible(False)
        self.filtre_toggle_buton.setText("▼")  # Asagi ok
        
        # Sayfalari olustur
        self.sayfalari_olustur()
        
        self.filtreleri_guncelle()
        self.gosterge_paneli_guncelle()
    
    def filtre_paneli_toggle(self):
        """Filtre panelini acip kapatir"""
        if self.filtre_icerik_container.isVisible():
            self.filtre_icerik_container.setVisible(False)
            self.filtre_toggle_buton.setText("▼")  # Asagi ok
        else:
            self.filtre_icerik_container.setVisible(True)
            self.filtre_toggle_buton.setText("▲")  # Yukari ok

    def sayfalari_olustur(self):
        """Gosterge paneli sayfalarini olusturur"""
        # Sayfa arka plan stili
        sayfa_stili = """
        QWidget {
            background-color: #333;
        }
        """
        
        # Baslik stili
        baslik_stili = "font-size: 16px; font-weight: bold; color: white;"
        
        # 0. Genel Rapor Sayfası
        genel_sayfasi = QWidget()
        genel_sayfasi.setStyleSheet("""
            QWidget {
                background-color: #333;
            }
        """)
        genel_layout = QVBoxLayout()
        genel_layout.setContentsMargins(0, 10, 0, 0)
        genel_layout.setSpacing(20)
        genel_sayfasi.setLayout(genel_layout)


        # Özet bilgiler container'ı (üstte dört kutu)
        ozet_bilgiler_container = QWidget()
        ozet_bilgiler_layout = QHBoxLayout()
        ozet_bilgiler_layout.setContentsMargins(10, 10, 10, 10)
        ozet_bilgiler_layout.setSpacing(20)
        ozet_bilgiler_container.setLayout(ozet_bilgiler_layout)

        # Özet bilgi kutuları için stiller (mevcut kod korundu)
        bilgi_kutusu_stili = """
            QFrame {
                background-color: #2C3E50;
                border-radius: 12px;
                padding: 15px;
                min-width: 200px;
                max-width: 300px;
            }
            QFrame:hover {
                background-color: #34495E;
            }
            QLabel {
                color: white;
            }
        """

        bilgi_baslik_stili = """
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #FF6B6B;
                padding-bottom: 5px;
                border-bottom: 1px solid #FF6B6B;
                margin-bottom: 3px;
            }
        """

        bilgi_deger_stili = """
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: white;
                padding: 3px 0;
            }
        """

        # Toplam Satış kutusu
        self.toplam_satis_kutusu = QFrame()
        self.toplam_satis_kutusu.setStyleSheet(bilgi_kutusu_stili)
        self.toplam_satis_kutusu.setFrameShape(QFrame.Shape.StyledPanel)
        self.toplam_satis_kutusu.setFrameShadow(QFrame.Shadow.Raised)
        toplam_satis_layout = QVBoxLayout()
        toplam_satis_layout.setContentsMargins(5, 5, 5, 5)
        toplam_satis_layout.setSpacing(2)
        toplam_satis_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toplam_satis_baslik = QLabel("Toplam Satış")
        toplam_satis_baslik.setStyleSheet(bilgi_baslik_stili)
        toplam_satis_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplam_satis_deger = QLabel("Yükleniyor...")
        self.toplam_satis_deger.setStyleSheet(bilgi_deger_stili)
        self.toplam_satis_deger.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplam_satis_deger.setWordWrap(True)
        toplam_satis_layout.addWidget(toplam_satis_baslik)
        toplam_satis_layout.addWidget(self.toplam_satis_deger)
        self.toplam_satis_kutusu.setLayout(toplam_satis_layout)
        ozet_bilgiler_layout.addWidget(self.toplam_satis_kutusu)

        # Toplam Maliyet kutusu
        self.toplam_maliyet_kutusu = QFrame()
        self.toplam_maliyet_kutusu.setStyleSheet(bilgi_kutusu_stili)
        self.toplam_maliyet_kutusu.setFrameShape(QFrame.Shape.StyledPanel)
        self.toplam_maliyet_kutusu.setFrameShadow(QFrame.Shadow.Raised)
        toplam_maliyet_layout = QVBoxLayout()
        toplam_maliyet_layout.setContentsMargins(5, 5, 5, 5)
        toplam_maliyet_layout.setSpacing(2)
        toplam_maliyet_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toplam_maliyet_baslik = QLabel("Toplam Maliyet")
        toplam_maliyet_baslik.setStyleSheet(bilgi_baslik_stili)
        toplam_maliyet_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplam_maliyet_deger = QLabel("Yükleniyor...")
        self.toplam_maliyet_deger.setStyleSheet(bilgi_deger_stili)
        self.toplam_maliyet_deger.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplam_maliyet_deger.setWordWrap(True)
        toplam_maliyet_layout.addWidget(toplam_maliyet_baslik)
        toplam_maliyet_layout.addWidget(self.toplam_maliyet_deger)
        self.toplam_maliyet_kutusu.setLayout(toplam_maliyet_layout)
        ozet_bilgiler_layout.addWidget(self.toplam_maliyet_kutusu)

        # Ortalama AV kutusu
        self.ortalama_av_kutusu = QFrame()
        self.ortalama_av_kutusu.setStyleSheet(bilgi_kutusu_stili)
        self.ortalama_av_kutusu.setFrameShape(QFrame.Shape.StyledPanel)
        self.ortalama_av_kutusu.setFrameShadow(QFrame.Shadow.Raised)
        ortalama_av_layout = QVBoxLayout()
        ortalama_av_layout.setContentsMargins(5, 5, 5, 5)
        ortalama_av_layout.setSpacing(2)
        ortalama_av_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ortalama_av_baslik = QLabel("Ortalama AV")
        ortalama_av_baslik.setStyleSheet(bilgi_baslik_stili)
        ortalama_av_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ortalama_av_deger = QLabel("Yükleniyor...")
        self.ortalama_av_deger.setStyleSheet(bilgi_deger_stili)
        self.ortalama_av_deger.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ortalama_av_deger.setWordWrap(True)
        ortalama_av_layout.addWidget(ortalama_av_baslik)
        ortalama_av_layout.addWidget(self.ortalama_av_deger)
        self.ortalama_av_kutusu.setLayout(ortalama_av_layout)
        ozet_bilgiler_layout.addWidget(self.ortalama_av_kutusu)

        # Toplam Ağırlık kutusu
        self.toplam_agirlik_kutusu = QFrame()
        self.toplam_agirlik_kutusu.setStyleSheet(bilgi_kutusu_stili)
        self.toplam_agirlik_kutusu.setFrameShape(QFrame.Shape.StyledPanel)
        self.toplam_agirlik_kutusu.setFrameShadow(QFrame.Shadow.Raised)
        toplam_agirlik_layout = QVBoxLayout()
        toplam_agirlik_layout.setContentsMargins(5, 5, 5, 5)
        toplam_agirlik_layout.setSpacing(2)
        toplam_agirlik_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toplam_agirlik_baslik = QLabel("Toplam Ağırlık")
        toplam_agirlik_baslik.setStyleSheet(bilgi_baslik_stili)
        toplam_agirlik_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplam_agirlik_deger = QLabel("Yükleniyor...")
        self.toplam_agirlik_deger.setStyleSheet(bilgi_deger_stili)
        self.toplam_agirlik_deger.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplam_agirlik_deger.setWordWrap(True)
        toplam_agirlik_layout.addWidget(toplam_agirlik_baslik)
        toplam_agirlik_layout.addWidget(self.toplam_agirlik_deger)
        self.toplam_agirlik_kutusu.setLayout(toplam_agirlik_layout)
        ozet_bilgiler_layout.addWidget(self.toplam_agirlik_kutusu)

        genel_layout.addWidget(ozet_bilgiler_container)

        # Eski pasta grafikler container'larini kaldir
        # pasta_grafikler_container = QWidget()
        # pasta_grafikler_layout = QHBoxLayout()
        # pasta_grafikler_layout.setContentsMargins(10, 10, 10, 10)
        # pasta_grafikler_layout.setSpacing(20)
        # pasta_grafikler_container.setLayout(pasta_grafikler_layout)

        # # Maliyet/Satış oranları için üç pasta grafik
        # self.genel_maliyet_satis_container = QWidget()
        # self.genel_maliyet_satis_container.setMinimumSize(300, 300)
        # self.genel_maliyet_satis_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # pasta_grafikler_layout.addWidget(self.genel_maliyet_satis_container)

        # self.zer_maliyet_satis_container = QWidget()
        # self.zer_maliyet_satis_container.setMinimumSize(300, 300)
        # self.zer_maliyet_satis_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # pasta_grafikler_layout.addWidget(self.zer_maliyet_satis_container)

        # self.diger_maliyet_satis_container = QWidget()
        # self.diger_maliyet_satis_container.setMinimumSize(300, 300)
        # self.diger_maliyet_satis_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # pasta_grafikler_layout.addWidget(self.diger_maliyet_satis_container)

        # genel_layout.addWidget(pasta_grafikler_container)

        # # Ek pasta grafikler için container (ağırlık, m² ve ZER satış dağılımı)
        # ek_pasta_grafikler_container = QWidget()
        # ek_pasta_grafikler_layout = QHBoxLayout()
        # ek_pasta_grafikler_layout.setContentsMargins(10, 10, 10, 10)
        # ek_pasta_grafikler_layout.setSpacing(20)
        # ek_pasta_grafikler_container.setLayout(ek_pasta_grafikler_layout)

        # self.agirlik_dagilim_container = QWidget()
        # self.agirlik_dagilim_container.setMinimumSize(300, 300)
        # self.agirlik_dagilim_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # ek_pasta_grafikler_layout.addWidget(self.agirlik_dagilim_container)

        # self.m2_dagilim_container = QWidget()
        # self.m2_dagilim_container.setMinimumSize(300, 300)
        # self.m2_dagilim_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # ek_pasta_grafikler_layout.addWidget(self.m2_dagilim_container)

        # self.zer_satis_dagilim_container = QWidget()
        # self.zer_satis_dagilim_container.setMinimumSize(300, 300)
        # self.zer_satis_dagilim_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # ek_pasta_grafikler_layout.addWidget(self.zer_satis_dagilim_container)

        # genel_layout.addWidget(ek_pasta_grafikler_container)
        
        # Birlesik grafik icin container olustur
        birlesik_grafik_container = QWidget()
        birlesik_grafik_layout = QVBoxLayout()
        birlesik_grafik_layout.setContentsMargins(10, 10, 10, 10)
        birlesik_grafik_layout.setSpacing(10)
        birlesik_grafik_container.setLayout(birlesik_grafik_layout)
        
        # Grafik container'i
        self.birlesik_genel_rapor_container = QWidget()
        self.birlesik_genel_rapor_container.setMinimumSize(800, 600)
        self.birlesik_genel_rapor_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        birlesik_grafik_layout.addWidget(self.birlesik_genel_rapor_container, 1)
        
        # Tam ekran butonu
        tam_ekran_buton_container = QWidget()
        tam_ekran_buton_layout = QHBoxLayout()
        tam_ekran_buton_layout.setContentsMargins(0, 0, 0, 0)
        tam_ekran_buton_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        tam_ekran_buton_container.setLayout(tam_ekran_buton_layout)
        
        self.genel_rapor_tam_ekran_buton = QPushButton("Tam Ekran")
        self.genel_rapor_tam_ekran_buton.setStyleSheet("""
            QPushButton {
                background-color: #2C3E50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #34495E;
            }
            QPushButton:pressed {
                background-color: #1ABC9C;
            }
        """)
        self.genel_rapor_tam_ekran_buton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.genel_rapor_tam_ekran_buton.clicked.connect(lambda: self.tam_ekran_goster(self.birlesik_genel_rapor_container))
        tam_ekran_buton_layout.addWidget(self.genel_rapor_tam_ekran_buton)
        
        birlesik_grafik_layout.addWidget(tam_ekran_buton_container)
        genel_layout.addWidget(birlesik_grafik_container)

        # Sayfayı stacked widget'a ekle
        self.sayfa_icerik_container.addWidget(genel_sayfasi)
        
        self.filtreleri_guncelle()
        self.gosterge_paneli_guncelle()

        # 1. Satis Performansi Sayfasi
        satis_sayfasi = QWidget()
        satis_sayfasi.setStyleSheet(sayfa_stili)
        satis_layout = QVBoxLayout()
        satis_layout.setContentsMargins(0, 10, 0, 0)
        satis_layout.setSpacing(20)
        satis_sayfasi.setLayout(satis_layout)
        
        # Satis performansi ve satis temsilcisi performansi grafikleri
        satis_grid = QGridLayout()
        satis_grid.setContentsMargins(0, 0, 0, 0)
        satis_grid.setSpacing(20)
        
        # Satis performansi grafigi
        satis_perf_container = QWidget()
        satis_perf_container.setStyleSheet(sayfa_stili)
        satis_perf_layout = QVBoxLayout()
        satis_perf_layout.setContentsMargins(0, 0, 0, 0)
        satis_perf_baslik = QLabel("Satis Performansi")
        satis_perf_baslik.setStyleSheet(baslik_stili)
        satis_perf_layout.addWidget(satis_perf_baslik)
        self.satis_performans_container.setMinimumSize(300, 300)
        self.satis_performans_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        satis_perf_layout.addWidget(self.satis_performans_container)
        tam_ekran_butonu1 = QPushButton("Tam Ekran")
        tam_ekran_butonu1.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
        """)
        tam_ekran_butonu1.clicked.connect(lambda: self.tam_ekran_goster(self.satis_performans_container))
        satis_perf_layout.addWidget(tam_ekran_butonu1, alignment=Qt.AlignmentFlag.AlignCenter)
        satis_perf_container.setLayout(satis_perf_layout)
        satis_grid.addWidget(satis_perf_container, 0, 0)
        
        # Satis temsilcisi performansi grafigi
        satis_temsilci_container = QWidget()
        satis_temsilci_container.setStyleSheet(sayfa_stili)
        satis_temsilci_layout = QVBoxLayout()
        satis_temsilci_layout.setContentsMargins(0, 0, 0, 0)
        satis_temsilci_baslik = QLabel("Satis Temsilcisi Performansi")
        satis_temsilci_baslik.setStyleSheet(baslik_stili)
        satis_temsilci_layout.addWidget(satis_temsilci_baslik)
        self.satis_temsilcisi_performans_container.setMinimumSize(300, 300)
        self.satis_temsilcisi_performans_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        satis_temsilci_layout.addWidget(self.satis_temsilcisi_performans_container)
        tam_ekran_butonu2 = QPushButton("Tam Ekran")
        tam_ekran_butonu2.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
        """)
        tam_ekran_butonu2.clicked.connect(lambda: self.tam_ekran_goster(self.satis_temsilcisi_performans_container))
        satis_temsilci_layout.addWidget(tam_ekran_butonu2, alignment=Qt.AlignmentFlag.AlignCenter)
        satis_temsilci_container.setLayout(satis_temsilci_layout)
        satis_grid.addWidget(satis_temsilci_container, 0, 1)
        
        satis_layout.addLayout(satis_grid)
        
        # 2. Musteri Analizi Sayfasi
        musteri_sayfasi = QWidget()
        musteri_sayfasi.setStyleSheet(sayfa_stili)
        musteri_layout = QVBoxLayout()
        musteri_layout.setContentsMargins(0, 10, 0, 0)
        musteri_layout.setSpacing(20)
        musteri_sayfasi.setLayout(musteri_layout)
        
        # Musteri segmentasyon ve aylik potansiyel gelir grafikleri
        musteri_grid = QGridLayout()
        musteri_grid.setContentsMargins(0, 0, 0, 0)
        musteri_grid.setSpacing(20)
        
        # Musteri segmentasyon grafigi
        musteri_seg_container = QWidget()
        musteri_seg_container.setStyleSheet(sayfa_stili)
        musteri_seg_layout = QVBoxLayout()
        musteri_seg_layout.setContentsMargins(0, 0, 0, 0)
        musteri_seg_baslik = QLabel("Musteri Sektor Dagilimi")
        musteri_seg_baslik.setStyleSheet(baslik_stili)
        musteri_seg_layout.addWidget(musteri_seg_baslik)
        self.musteri_segmentasyon_container.setMinimumSize(300, 300)
        self.musteri_segmentasyon_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        musteri_seg_layout.addWidget(self.musteri_segmentasyon_container)
        tam_ekran_butonu3 = QPushButton("Tam Ekran")
        tam_ekran_butonu3.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
        """)
        tam_ekran_butonu3.clicked.connect(lambda: self.tam_ekran_goster(self.musteri_segmentasyon_container))
        musteri_seg_layout.addWidget(tam_ekran_butonu3, alignment=Qt.AlignmentFlag.AlignCenter)
        musteri_seg_container.setLayout(musteri_seg_layout)
        musteri_grid.addWidget(musteri_seg_container, 0, 0)
        
        # Aylik potansiyel gelir grafigi
        potansiyel_gelir_container = QWidget()
        potansiyel_gelir_container.setStyleSheet(sayfa_stili)
        potansiyel_gelir_layout = QVBoxLayout()
        potansiyel_gelir_layout.setContentsMargins(0, 0, 0, 0)
        potansiyel_gelir_baslik = QLabel("Aylik Potansiyel Gelir")
        potansiyel_gelir_baslik.setStyleSheet(baslik_stili)
        potansiyel_gelir_layout.addWidget(potansiyel_gelir_baslik)
        self.aylik_potansiyel_gelir_container.setMinimumSize(300, 300)
        self.aylik_potansiyel_gelir_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        potansiyel_gelir_layout.addWidget(self.aylik_potansiyel_gelir_container)
        tam_ekran_butonu4 = QPushButton("Tam Ekran")
        tam_ekran_butonu4.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
        """)
        tam_ekran_butonu4.clicked.connect(lambda: self.tam_ekran_goster(self.aylik_potansiyel_gelir_container))
        potansiyel_gelir_layout.addWidget(tam_ekran_butonu4, alignment=Qt.AlignmentFlag.AlignCenter)
        potansiyel_gelir_container.setLayout(potansiyel_gelir_layout)
        musteri_grid.addWidget(potansiyel_gelir_container, 0, 1)
        
        musteri_layout.addLayout(musteri_grid)
        
        # 3. Bolgesel Analiz Sayfasi
        harita_sayfasi = QWidget()
        harita_sayfasi.setStyleSheet(sayfa_stili)
        harita_layout = QVBoxLayout()
        harita_layout.setContentsMargins(0, 10, 0, 0)
        harita_layout.setSpacing(20)
        harita_sayfasi.setLayout(harita_layout)
        
        # Turkiye haritasi
        harita_container = QWidget()
        harita_container.setStyleSheet(sayfa_stili)
        harita_layout_inner = QVBoxLayout()
        harita_layout_inner.setContentsMargins(0, 0, 0, 0)
        harita_baslik = QLabel("Turkiye Il Satis Haritasi")
        harita_baslik.setStyleSheet(baslik_stili)
        harita_layout_inner.addWidget(harita_baslik)
        self.musteri_bolge_dagilim_container.setMinimumSize(600, 400)
        self.musteri_bolge_dagilim_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        harita_layout_inner.addWidget(self.musteri_bolge_dagilim_container)
        tam_ekran_butonu5 = QPushButton("Tam Ekran")
        tam_ekran_butonu5.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
        """)
        tam_ekran_butonu5.clicked.connect(lambda: self.tam_ekran_goster(self.musteri_bolge_dagilim_container))
        harita_layout_inner.addWidget(tam_ekran_butonu5, alignment=Qt.AlignmentFlag.AlignCenter)
        harita_container.setLayout(harita_layout_inner)
        harita_layout.addWidget(harita_container)
        
        # 4. Pipeline Analizi Sayfasi
        pipeline_sayfasi = QWidget()
        pipeline_sayfasi.setStyleSheet(sayfa_stili)
        pipeline_layout = QVBoxLayout()
        pipeline_layout.setContentsMargins(0, 10, 0, 0)
        pipeline_layout.setSpacing(20)
        pipeline_sayfasi.setLayout(pipeline_layout)
        
        # Pipeline grafigi
        pipeline_container_widget = QWidget()
        pipeline_container_widget.setStyleSheet(sayfa_stili)
        pipeline_layout_inner = QVBoxLayout()
        pipeline_layout_inner.setContentsMargins(0, 0, 0, 0)
        pipeline_baslik = QLabel("Pipeline Dagilimi")
        pipeline_baslik.setStyleSheet(baslik_stili)
        pipeline_layout_inner.addWidget(pipeline_baslik)
        self.pipeline_container.setMinimumSize(600, 400)
        self.pipeline_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pipeline_layout_inner.addWidget(self.pipeline_container)
        tam_ekran_butonu6 = QPushButton("Tam Ekran")
        tam_ekran_butonu6.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0D47A1;
            }
        """)
        tam_ekran_butonu6.clicked.connect(lambda: self.tam_ekran_goster(self.pipeline_container))
        pipeline_layout_inner.addWidget(tam_ekran_butonu6, alignment=Qt.AlignmentFlag.AlignCenter)
        pipeline_container_widget.setLayout(pipeline_layout_inner)
        pipeline_layout.addWidget(pipeline_container_widget)
        
        # Sayfalari stack widget'a ekle
        self.sayfa_icerik_container.addWidget(genel_sayfasi)
        self.sayfa_icerik_container.addWidget(satis_sayfasi)
        self.sayfa_icerik_container.addWidget(musteri_sayfasi)
        self.sayfa_icerik_container.addWidget(harita_sayfasi)
        self.sayfa_icerik_container.addWidget(pipeline_sayfasi)
    
    def sayfa_degistir(self):
        """Secilen sayfaya gore gosterge panelini gunceller"""
        buton = self.sender()
        if buton:
            sayfa_id = buton.property("sayfa_id")
            if sayfa_id == "genel":
                self.sayfa_icerik_container.setCurrentIndex(0)
            elif sayfa_id == "satis":
                self.sayfa_icerik_container.setCurrentIndex(1)
            elif sayfa_id == "musteri":
                self.sayfa_icerik_container.setCurrentIndex(2)
            elif sayfa_id == "harita":
                self.sayfa_icerik_container.setCurrentIndex(3)
            elif sayfa_id == "pipeline":
                self.sayfa_icerik_container.setCurrentIndex(4)
            
            # Secilen sayfaya gore grafikleri guncelle
            self.gosterge_paneli_guncelle()

    def gosterge_paneli_guncelle(self):
        """
        Gosterge panelindeki secili sayfadaki grafikleri gunceller.
        
        Bu metod, ana is parcaciginda calisir ve secili sayfadaki grafikleri guncellemek icin
        QTimer.singleShot kullanarak asenkron olarak calisir. Her grafik icin:
        1. Gorsellestirici'den HTML icerik alinir (html_only=True)
        2. HTML icerik, ana is parcaciginda QWebEngineView'a donusturulur
        3. Olusturulan QWebEngineView, ilgili container'a eklenir
        """
        try:
            self.loglayici.debug(f"gosterge_paneli_guncelle çağrıldı, iş parçacığı: {QThread.currentThread()}")
            # Kullanici filtrelerini al
            
            # Tarih filtrelerini ayarla - son 6 ay
            bugun = QDate.currentDate()
            alti_ay_once = bugun.addMonths(-6)
            
            # Eger tarih filtreleri ayarlanmamissa, varsayilan degerleri kullan
            if self.baslangic_tarihi.date() == self.baslangic_tarihi.minimumDate():
                self.baslangic_tarihi.setDate(alti_ay_once)
            
            if self.bitis_tarihi.date() == self.bitis_tarihi.minimumDate():
                self.bitis_tarihi.setDate(bugun)
            
            # Baslangic tarihi bitis tarihinden sonra ise, baslangic tarihini bitis tarihinden 6 ay once olarak ayarla
            if self.baslangic_tarihi.date() > self.bitis_tarihi.date():
                self.baslangic_tarihi.setDate(self.bitis_tarihi.date().addMonths(-6))
                self.loglayici.warning("Baslangic tarihi bitis tarihinden sonra, otomatik olarak duzeltildi")
            
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

            # Grafik ayarlarını al
            chart_type = self.chart_type_combo.currentText().lower()
            theme = self.theme_combo.currentText()

            # Veri çerçevelerini kopyala
            satislar_df = self.services.data_manager.satislar_df.copy() if self.services.data_manager.satislar_df is not None else pd.DataFrame()
            pipeline_df = self.services.data_manager.pipeline_df.copy() if self.services.data_manager.pipeline_df is not None else pd.DataFrame()
            musteriler_df = self.services.data_manager.customers_df.copy() if self.services.data_manager.customers_df is not None else pd.DataFrame()
            hedefler_df = self.services.data_manager.targets_df.copy() if self.services.data_manager.targets_df is not None else pd.DataFrame()

            # Veri yoksa uyarı göster ve çık
            if all(df.empty for df in [satislar_df, pipeline_df, musteriler_df, hedefler_df]):
                if self.is_initialized:
                    QMessageBox.warning(self, "Uyarı", "Gösterge paneli için veri bulunamadı")
                return

            # Satislar verisi hakkinda log
            if not satislar_df.empty:
                self.loglayici.info(f"Satislar verisi mevcut. Satır sayısı: {len(satislar_df)}")
            else:
                self.loglayici.warning("Satislar verisi boş veya mevcut değil.")

            # Ana is parcaciginda QWebEngineView olusturma fonksiyonu
            def create_web_view_from_html(html_content):
                """HTML içeriğinden QWebEngineView oluşturur."""
                try:
                    # Plotly.js CDN'ini ekle
                    if "<script src=" not in html_content and "plotly-graph-div" in html_content:
                        plotly_cdn = '<script src="https://cdn.plot.ly/plotly-3.0.1.min.js"></script>'
                        html_content = f"{plotly_cdn}\n{html_content}"
                    
                    # Responsive davranisi icin HTML wrapper ekle
                    responsive_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body {{
                                margin: 0;
                                padding: 0;
                                overflow: hidden;
                                background-color: #333;
                            }}
                            .container {{
                                width: 100%;
                                height: 100vh;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                            }}
                            .plotly-graph-div {{
                                width: 100% !important;
                                height: 100% !important;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            {html_content}
                        </div>
                        <script>
                            window.addEventListener('resize', function() {{
                                if (typeof Plotly !== 'undefined') {{
                                    var graphDivs = document.getElementsByClassName('plotly-graph-div');
                                    for (var i = 0; i < graphDivs.length; i++) {{
                                        Plotly.Plots.resize(graphDivs[i]);
                                    }}
                                }}
                            }});
                        </script>
                    </body>
                    </html>
                    """
                    
                    web_view = QWebEngineView()
                    web_view.setHtml(responsive_html)
                    web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    return web_view
                except Exception as e:
                    self.loglayici.error(f"QWebEngineView olusturulurken hata: {str(e)}")
                    import traceback
                    self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                    return self.gorsellestirici._create_empty_web_view()
            
            # Secili sayfayi belirle
            secili_sayfa_index = self.sayfa_icerik_container.currentIndex()
            
            # Genel Rapor Sayfası (index 0)
            if secili_sayfa_index == 0:
                def update_ozet_bilgiler():
                    """Özet bilgi kutularını günceller. Ana iş parçacığında çalışır."""
                    try:
                        self.loglayici.debug(f"update_ozet_bilgiler çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        
                        # Veri çerçevelerinin durumunu logla
                        satislar_satir_sayisi = len(satislar_df) if satislar_df is not None else 0
                        self.loglayici.debug(f"Özet bilgiler için veri durumu: Satışlar={satislar_satir_sayisi} satır")
                        
                        # Eğer satışlar veri çerçevesi boşsa, bilgi kutularını varsayılan değerlerle doldur
                        if satislar_df is None or satislar_df.empty:
                            self.loglayici.warning("Satışlar veri çerçevesi boş. Özet bilgiler gösterilemiyor.")
                            self.toplam_satis_deger.setText("Veri yok")
                            self.toplam_maliyet_deger.setText("Veri yok")
                            self.ortalama_av_deger.setText("Veri yok")
                            self.toplam_agirlik_deger.setText("Veri yok")
                            return
                        
                        # Filtreleri uygula
                        filtered_df = satislar_df.copy()
                        
                        # Tarih filtresi uygula
                        if 'Ay' in filtered_df.columns:
                            try:
                                filtered_df['Tarih'] = filtered_df['Ay'].apply(lambda x: pd.to_datetime(f"01-{x}", format="%d-%m-%Y", errors='coerce'))
                                baslangic = pd.to_datetime(filtreler['baslangic_tarihi'])
                                bitis = pd.to_datetime(filtreler['bitis_tarihi'])
                                filtered_df = filtered_df[(filtered_df['Tarih'] >= baslangic) & (filtered_df['Tarih'] <= bitis)]
                            except Exception as e:
                                self.loglayici.error(f"Tarih filtresi uygulanırken hata: {str(e)}")
                        
                        # Diğer filtreleri uygula
                        if filtreler.get('satisci') and 'Satis Temsilcisi' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['Satis Temsilcisi'] == filtreler['satisci']]
                        
                        if filtreler.get('bolge') and 'Bolge' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['Bolge'] == filtreler['bolge']]
                        
                        if filtreler.get('sektor') and 'Sektor' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['Sektor'] == filtreler['sektor']]
                        
                        if filtreler.get('musteri_adi') and 'Ana Musteri' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['Ana Musteri'].str.contains(filtreler['musteri_adi'], case=False, na=False)]
                        
                        # Toplam satış hesapla
                        toplam_satis = 0
                        if 'Satis Miktari' in filtered_df.columns:
                            toplam_satis = filtered_df['Satis Miktari'].sum()
                        
                        # Toplam maliyet hesapla
                        maliyet_sonuc = self.services.data_manager.toplam_maliyet_hesapla(
                            baslangic_tarihi=filtreler['baslangic_tarihi'],
                            bitis_tarihi=filtreler['bitis_tarihi']
                        )
                        toplam_maliyet = maliyet_sonuc['toplam_maliyet']

                        # Ortalama AV hesapla
                        ortalama_av = 0
                        if toplam_satis > 0:
                            ortalama_av = 1 - (toplam_maliyet / toplam_satis)
                        
                        # Toplam ağırlık hesapla
                        agirlik_sonuc = self.services.data_manager.toplam_agirlik_hesapla(
                            baslangic_tarihi=filtreler['baslangic_tarihi'],
                            bitis_tarihi=filtreler['bitis_tarihi']
                        )
                        toplam_agirlik = agirlik_sonuc['toplam_agirlik']
                        
                        # Bilgi kutularını güncelle
                        self.toplam_satis_deger.setText(f"{toplam_satis:,.2f} TL")
                        self.toplam_maliyet_deger.setText(f"{toplam_maliyet:,.2f} TL")
                        self.ortalama_av_deger.setText(f"%{ortalama_av*100:.2f}")
                        self.toplam_agirlik_deger.setText(f"{toplam_agirlik:,.2f} kg")
                        
                        self.loglayici.debug("Özet bilgiler güncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Özet bilgiler güncellenirken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrıntıları:\n{traceback.format_exc()}")
                        # Hata durumunda bilgi kutularını varsayılan değerlerle doldur
                        self.toplam_satis_deger.setText("Hata")
                        self.toplam_maliyet_deger.setText("Hata")
                        self.ortalama_av_deger.setText("Hata")
                        self.toplam_agirlik_deger.setText("Hata")
                
                # Özet bilgileri güncelle
                QTimer.singleShot(0, update_ozet_bilgiler)

                # Pasta grafikleri için güncelleme
                def update_pasta_grafikler():
                    try:
                        # Eski pasta grafikleri yerine birlesik genel rapor grafigini olustur
                        birlesik_grafik = self.gorsellestirici.birlesik_genel_rapor_grafigi_olustur(
                            satislar_df, chart_type=chart_type, theme=theme, html_only=True
                        )
                        web_view_birlesik = create_web_view_from_html(birlesik_grafik)
                        self._temizle_ve_ekle_widget(self.birlesik_genel_rapor_container, web_view_birlesik)

                        self.loglayici.debug("Birlesik genel rapor grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Birlesik genel rapor grafigi guncellenirken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrıntıları:\n{traceback.format_exc()}")
                        # Hata durumunda container'ı temizle
                        self._temizle_ve_ekle_widget(self.birlesik_genel_rapor_container, self.gorsellestirici._create_empty_web_view())

                # Pasta grafikleri güncelle
                QTimer.singleShot(0, update_pasta_grafikler)
                
                # Genel Rapor sayfasi icin bos bir container olustur
                # Yeni icerik icin hazirlandi
                try:
                    # Eski container'lar yerine yeni container'i kullan
                    if hasattr(self, 'birlesik_genel_rapor_container'):
                        self._temizle_ve_ekle_widget(self.birlesik_genel_rapor_container, self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Genel rapor container'i guncellenirken hata: {str(e)}")
                
            # Satis Performansi Sayfasi (index 1)
            elif secili_sayfa_index == 1:
                # Satis performansi grafigini guncelle
                def update_satis_grafik():
                    """Satis performansi grafigini gunceller. Ana is parcaciginda calisir."""
                    try:
                        self.loglayici.debug(f"update_satis_grafik çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        
                        # Veri cercevelerinin durumunu logla
                        hedefler_satir_sayisi = len(hedefler_df) if hedefler_df is not None else 0
                        satislar_satir_sayisi = len(satislar_df) if satislar_df is not None else 0
                        self.loglayici.debug(f"Satis grafigi icin veri durumu: Hedefler={hedefler_satir_sayisi} satir, Satislar={satislar_satir_sayisi} satir")
                        
                        # Eger hedefler veri cercevesi bossa, kullaniciya bilgi ver
                        if hedefler_df is None or hedefler_df.empty:
                            self.loglayici.warning("Hedefler veri cercevesi bos. Lutfen once satis hedefleri ekleyin.")
                        
                        html_content = self.gorsellestirici.satis_performansi_grafigi_olustur(
                            hedefler_df, satislar_df, filtreler, chart_type, theme, html_only=True
                        )
                        web_view = create_web_view_from_html(html_content)
                        self._temizle_ve_ekle_widget(self.satis_performans_container, web_view)
                        self.loglayici.debug("Satis performansi grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Satis performansi grafigi olusturulurken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                        self._temizle_ve_ekle_widget(self.satis_performans_container, self.gorsellestirici._create_empty_web_view())
                
                QTimer.singleShot(0, update_satis_grafik)
                
                # Satis temsilcisi performans grafigini guncelle
                def update_temsilci_grafik():
                    try:
                        self.loglayici.debug(f"update_temsilci_grafik çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        html_content = self.gorsellestirici.satis_temsilcisi_performansi_grafigi_olustur(
                            satislar_df, chart_type, theme, html_only=True
                        )
                        web_view = create_web_view_from_html(html_content)
                        self._temizle_ve_ekle_widget(self.satis_temsilcisi_performans_container, web_view)
                        self.loglayici.debug("Satis temsilcisi performans grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Satis temsilcisi performansi grafigi olusturulurken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                        self._temizle_ve_ekle_widget(self.satis_temsilcisi_performans_container, self.gorsellestirici._create_empty_web_view())
                
                QTimer.singleShot(0, update_temsilci_grafik)
                
            # Musteri Analizi Sayfasi (index 2)
            elif secili_sayfa_index == 2:
                # Musteri segmentasyon grafigini guncelle
                def update_segmentasyon_grafik():
                    try:
                        self.loglayici.debug(f"update_segmentasyon_grafik çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        html_content = self.gorsellestirici.musteri_sektor_grafigi_olustur(
                            musteriler_df, 
                            chart_type if chart_type in ['pie', 'bar', 'treemap'] else 'pie',
                            theme,
                            html_only=True
                        )
                        web_view = create_web_view_from_html(html_content)
                        self._temizle_ve_ekle_widget(self.musteri_segmentasyon_container, web_view)
                        self.loglayici.debug("Musteri segmentasyon grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Musteri sektor grafigi olusturulurken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                        self._temizle_ve_ekle_widget(self.musteri_segmentasyon_container, self.gorsellestirici._create_empty_web_view())
                
                QTimer.singleShot(0, update_segmentasyon_grafik)
                
                # Aylik potansiyel gelir grafigini guncelle
                def update_potansiyel_grafik():
                    try:
                        self.loglayici.debug(f"update_potansiyel_grafik çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        html_content = self.gorsellestirici.aylik_potansiyel_gelir_grafigi_olustur(
                            pipeline_df, filtreler, chart_type, theme, html_only=True
                        )
                        web_view = create_web_view_from_html(html_content)
                        self.loglayici.debug(f"Aylik potansiyel gelir widget olusturuldu mu: {web_view is not None}")
                        self._temizle_ve_ekle_widget(self.aylik_potansiyel_gelir_container, web_view)
                        self.loglayici.debug("Aylik potansiyel gelir grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Aylik potansiyel gelir grafigi olusturulurken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                        self._temizle_ve_ekle_widget(self.aylik_potansiyel_gelir_container, self.gorsellestirici._create_empty_web_view())
                
                QTimer.singleShot(0, update_potansiyel_grafik)
                
            # Bolgesel Analiz Sayfasi (index 2)
            elif secili_sayfa_index == 2:
                # Harita grafigini guncelle
                def update_harita_grafik():
                    try:
                        self.loglayici.debug(f"update_harita_grafik çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        html_content = self.gorsellestirici.musteri_bolge_dagilimi_grafigi_olustur(
                            musteriler_df, chart_type='choropleth', theme=theme, html_only=True
                        )
                        web_view = create_web_view_from_html(html_content)
                        self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, web_view)
                        self.loglayici.debug("Harita grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Harita grafigi olusturulurken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                        self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, self.gorsellestirici._create_empty_web_view())
                
                QTimer.singleShot(0, update_harita_grafik)
                
            # Pipeline Analizi Sayfasi (index 3)
            elif secili_sayfa_index == 3:
                # Pipeline grafigini guncelle
                def update_pipeline_grafik():
                    try:
                        self.loglayici.debug(f"update_pipeline_grafik çağrıldı, iş parçacığı: {QThread.currentThread()}")
                        html_content = self.gorsellestirici.pipeline_grafigi_olustur(
                            pipeline_df, 
                            chart_type if chart_type in ['pie', 'bar', 'funnel'] else 'pie', 
                            theme, 
                            html_only=True
                        )
                        web_view = create_web_view_from_html(html_content)
                        self._temizle_ve_ekle_widget(self.pipeline_container, web_view)
                        self.loglayici.debug("Pipeline grafigi guncellendi")
                    except Exception as e:
                        self.loglayici.error(f"Pipeline grafigi olusturulurken hata: {str(e)}")
                        import traceback
                        self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
                        self._temizle_ve_ekle_widget(self.pipeline_container, self.gorsellestirici._create_empty_web_view())
                
                QTimer.singleShot(0, update_pipeline_grafik)

            self.loglayici.info(f"Secili sayfa {secili_sayfa_index} icin grafiklerin guncellenmesi baslatildi")

        except Exception as e:
            self.loglayici.error(f"Gosterge paneli guncellenirken genel hata: {str(e)}")
            import traceback
            self.loglayici.debug(f"Hata ayrintilari:\n{traceback.format_exc()}")
            QMessageBox.warning(self, "Hata", f"Gosterge paneli guncellenemedi: {str(e)}")
            
            # Secili sayfadaki grafikleri temizle
            secili_sayfa_index = self.sayfa_icerik_container.currentIndex()
            if secili_sayfa_index == 0:
                self.toplam_satis_deger.setText("Veri yok")
                self.toplam_maliyet_deger.setText("Veri yok")
                self.ortalama_av_deger.setText("Veri yok")
                self.toplam_agirlik_deger.setText("Veri yok")
                
                # Eski container'lar yerine yeni container'i kullan
                try:
                    if hasattr(self, 'birlesik_genel_rapor_container'):
                        self._temizle_ve_ekle_widget(self.birlesik_genel_rapor_container, self.gorsellestirici._create_empty_web_view())
                except Exception as e:
                    self.loglayici.error(f"Genel rapor container'i temizlenirken hata: {str(e)}")
            elif secili_sayfa_index == 1:
                self._temizle_ve_ekle_widget(self.satis_performans_container, self.gorsellestirici._create_empty_web_view())
                self._temizle_ve_ekle_widget(self.satis_temsilcisi_performans_container, self.gorsellestirici._create_empty_web_view())
            elif secili_sayfa_index == 2:
                self._temizle_ve_ekle_widget(self.musteri_segmentasyon_container, self.gorsellestirici._create_empty_web_view())
                self._temizle_ve_ekle_widget(self.aylik_potansiyel_gelir_container, self.gorsellestirici._create_empty_web_view())
            elif secili_sayfa_index == 3:
                self._temizle_ve_ekle_widget(self.musteri_bolge_dagilim_container, self.gorsellestirici._create_empty_web_view())
            elif secili_sayfa_index == 4:
                self._temizle_ve_ekle_widget(self.pipeline_container, self.gorsellestirici._create_empty_web_view())

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
                try:
                    ilerleme_dialog.accept()
                    self.filtreleri_guncelle()
                    QMessageBox.information(self, "Basarili", "Veriler yuklendi ve veritabanina kaydedildi.")
                    # Sinyali 100 ms gecikmeyle ana is parcaciginda gonder
                    QTimer.singleShot(100, lambda: self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "tum_verileri_yukle"})))
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
                    
            def veri_yuklendi(df, attr, table):
                # Ana thread'de calisir - DataFrame'i veri_yoneticisi'ne ata
                try:
                    setattr(self.services.data_manager, attr, df)
                    self.loglayici.debug(f"DataFrame atandi: {attr}, {table}")
                except Exception as e:
                    self.loglayici.error(f"DataFrame atanirken hata: {attr}, {str(e)}")
            
            # Sinyalleri bagla
            self.worker.ilerleme.connect(ilerleme_guncelle)
            self.worker.tamamlandi.connect(yukleme_tamamlandi)
            self.worker.hata.connect(yukleme_hatasi)
            self.worker.veri_yuklendi.connect(veri_yuklendi)  # Yeni sinyal baglantisi
            
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
                # Veri kaydetme islemini ana thread'de calistir
                def kaydet_islemi():
                    try:
                        self.services.data_manager.tum_verileri_kaydet(dosya_yolu)
                        QMessageBox.information(self, "Basarili", "Tum veriler basariyla Excel dosyasina kaydedildi.")
                        self.loglayici.info("Tum veriler basariyla Excel dosyasina kaydedildi.")
                    except Exception as e:
                        QMessageBox.critical(self, "Hata", f"Veri kaydetme sirasinda bir hata olustu: {str(e)}")
                        self.loglayici.error(f"Veri kaydetme hatasi: {str(e)}")
                
                # Ana thread'de calistir
                QTimer.singleShot(0, kaydet_islemi)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri kaydetme sirasinda bir hata olustu: {str(e)}")
            self.loglayici.error(f"Veri kaydetme hatasi: {str(e)}")

    def hakkinda_goster(self):
        QMessageBox.about(self, "Hakkinda", "Satis Yonetimi ve CRM Programi\nVersiyon 1.0\u00A9 2025 Omio")

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
            
            # Sikayet tablosunu guncelle
            self.sikayet_yonetimi.sikayet_tablosu_guncelle()
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

    def filtreleri_guncelle(self):
        """Filtre seceneklerini veriyle dinamik olarak gunceller"""
        try:
            # Veriler henüz yüklenmemişse güncellemeyi atla
            if not hasattr(self.services.data_manager, 'sales_df') or \
               not hasattr(self.services.data_manager, 'customers_df'):
                self.loglayici.warning("Veriler henuz yuklenmemis")
                return

            # Satici filtresi
            self.satisci_filtre.clear()
            self.satisci_filtre.addItem("Tum Satiscilar")
            if (self.services.data_manager.sales_df is not None and 
                not self.services.data_manager.sales_df.empty and 
                'Satis Temsilcisi' in self.services.data_manager.sales_df.columns):
                satiscilar = self.services.data_manager.sales_df['Satis Temsilcisi'].dropna().unique().tolist()
                self.satisci_filtre.addItems([str(s) for s in satiscilar])  # String donusumu
                self.loglayici.info(f"Satisci filtresi guncellendi: {len(satiscilar)} secenek")
            else:
                self.loglayici.debug("Satisci verisi yok veya 'Satis Temsilcisi' sutunu eksik, filtreye sadece 'Tum Satiscilar' eklendi.")

            # Bolge filtresi
            self.bolge_filtre.clear()
            self.bolge_filtre.addItem("Tum Iller")
            if (self.services.data_manager.customers_df is not None and 
                not self.services.data_manager.customers_df.empty and 
                'Bolge' in self.services.data_manager.customers_df.columns):
                bolgeler = self.services.data_manager.customers_df['Bolge'].dropna().unique().tolist()
                self.bolge_filtre.addItems([str(b) for b in bolgeler])  # String donusumu
                self.loglayici.info(f"Bolge filtresi guncellendi: {len(bolgeler)} secenek")
            else:
                self.loglayici.debug("Musteri verisi yok veya 'Bolge' sutunu eksik, filtreye sadece 'Tum Iller' eklendi.")

            # Sektor filtresi
            self.sektor_filtre.clear()
            self.sektor_filtre.addItem("Tum Sektorler")
            if (self.services.data_manager.customers_df is not None and 
                not self.services.data_manager.customers_df.empty and 
                'Sektor' in self.services.data_manager.customers_df.columns):
                sektorler = self.services.data_manager.customers_df['Sektor'].dropna().unique().tolist()
                self.sektor_filtre.addItems([str(s) for s in sektorler])  # String donusumu
                self.loglayici.info(f"Sektor filtresi guncellendi: {len(sektorler)} secenek")
            else:
                self.loglayici.debug("Musteri verisi yok veya 'Sektor' sutunu eksik, filtreye sadece 'Tum Sektorler' eklendi.")

        except Exception as e:
            self.loglayici.error(f"Filtreler guncellenirken hata: {str(e)}")
            QMessageBox.warning(self, "Hata", f"Filtreler guncellenemedi: {str(e)}")

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
            
            # Raporu goster
            self.rapor_goster("Kohort Analizi Raporu", sonuc.get("report", ""))
            
        except Exception as e:
            self.loglayici.error(f"Kohort analizi olusturulurken hata: {str(e)}")
            ilerleme_dialog.accept()
            QMessageBox.critical(self, "Hata", f"Kohort analizi olusturulurken hata: {str(e)}")
            
    def rapor_goster(self, baslik, rapor):
        """Raporu gosterir"""
        dialog = QDialog(self)
        dialog.setWindowTitle(baslik)
        dialog.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # Rapor icerigi
        rapor_alani = QTextEdit()
        rapor_alani.setReadOnly(True)
        rapor_alani.setHtml(rapor)
        layout.addWidget(rapor_alani)
        
        # Kaydet butonu
        kaydet_butonu = QPushButton("Raporu Kaydet")
        kaydet_butonu.clicked.connect(lambda: self._raporu_kaydet(baslik, rapor))
        layout.addWidget(kaydet_butonu)
        
        dialog.setLayout(layout)
        dialog.exec()
        
    def _raporu_kaydet(self, baslik, rapor):
        """Raporu dosyaya kaydeder"""
        try:
            dosya_adi = f"{baslik}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            dosya_yolu, _ = QFileDialog.getSaveFileName(
                self,
                "Raporu Kaydet",
                dosya_adi,
                "HTML Dosyalari (*.html);;Tum Dosyalar (*)"
            )
            
            if dosya_yolu:
                with open(dosya_yolu, 'w', encoding='utf-8') as f:
                    f.write(rapor)
                QMessageBox.information(self, "Bilgi", f"Rapor basariyla kaydedildi:\n{dosya_yolu}")
                
        except Exception as e:
            self.loglayici.error(f"Rapor kaydedilirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Rapor kaydedilirken hata: {str(e)}")

    def _temizle_ve_ekle_widget(self, container, widget):
        """Container icerigini temizle ve yeni widget ekle"""
        self.loglayici.debug(f"_temizle_ve_ekle_widget cagirildi, container: {container}, widget: {widget}, is parcacigi: {QThread.currentThread()}")
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout()
            container.setLayout(layout)
        else:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        layout.addWidget(widget)
        self.loglayici.debug("Widget layout'a eklendi")

    def tam_ekran_goster(self, container):
        """Grafigi tam ekran gosteren yeni bir pencere acar"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Tam Ekran Grafik")
        
        # Ekran boyutunun %90'ini kullan
        screen_size = QApplication.primaryScreen().size()
        dialog.setGeometry(
            int(screen_size.width() * 0.01),  # Ekranin %1'i soldan bosluk
            int(screen_size.height() * 0.01), # Ekranin %1'i usttten bosluk
            int(screen_size.width() * 0.9),   # Ekranin %90'i genislik
            int(screen_size.height() * 0.9)   # Ekranin %90'i yukseklik
        )
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        dialog.setLayout(layout)
        
        # Container'in icerigini al
        original_layout = container.layout()
        if original_layout and original_layout.count() > 0:
            # Ilk widget'i al (QWebEngineView olmali)
            original_widget = original_layout.itemAt(0).widget()
            
            if isinstance(original_widget, QWebEngineView):
                # Yeni bir QWebEngineView olustur
                web_view = QWebEngineView()
                web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                
                # Orijinal HTML icerigini al ve yeni web view'a ayarla
                original_widget.page().toHtml(lambda html: 
                    # HTML icerigini isleyip yeni web view'a ayarla
                    web_view.setHtml(html)
                )
                
                # Tam ekran dialog'a ekle
                layout.addWidget(web_view, 1)  # 1 stretch factor ile ekle
                
                # Kapat butonu
                kapat_buton = QPushButton("Kapat")
                kapat_buton.setStyleSheet("""
                    QPushButton {
                        background-color: #2C3E50;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 8px 15px;
                        font-weight: bold;
                        min-width: 100px;
                    }
                    QPushButton:hover {
                        background-color: #34495E;
                    }
                    QPushButton:pressed {
                        background-color: #E74C3C;
                    }
                """)
                kapat_buton.setCursor(Qt.CursorShape.PointingHandCursor)
                kapat_buton.clicked.connect(dialog.close)
                
                buton_container = QWidget()
                buton_layout = QHBoxLayout()
                buton_layout.setContentsMargins(0, 10, 0, 0)
                buton_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                buton_layout.addWidget(kapat_buton)
                buton_container.setLayout(buton_layout)
                
                layout.addWidget(buton_container)
                
                # Dialog'u goster
                dialog.exec()

