# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QMessageBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLineEdit, QFormLayout, QDateEdit,
                             QComboBox, QTextEdit, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon
from events import Event
import pandas as pd
from typing import Optional, List, Dict, Any

class SikayetYonetimi:
    """
    Sikayet yonetimi islemlerini gerceklestiren sinif.
    
    Bu sinif, kullanici arayuzunde sikayet yonetimi sekmesini olusturur ve
    sikayetlerin eklenmesi, duzenlenmesi, silinmesi gibi islemleri gerceklestirir.
    """
    
    def __init__(self, parent, services, loglayici):
        """
        SikayetYonetimi sinifinin kurucu metodu.
        
        Args:
            parent: Ebeveyn pencere
            services: Servis katmani
            loglayici: Loglama nesnesi
        """
        self.parent = parent
        self.services = services
        self.loglayici = loglayici
        self.sikayet_tab = None
        self.sikayet_tablosu = None
        
    def sikayet_yonetimi_olustur(self):
        """Sikayet Yonetimi sekmesini olusturur"""
        self.sikayet_tab = QWidget()
        self.parent.sekme_widget.addTab(self.sikayet_tab, "Sikayet Yonetimi")
        
        ana_yerlesim = QVBoxLayout()
        buton_yerlesim = QHBoxLayout()
        
        # Butonlar
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
        
        self.sikayet_tab.setLayout(ana_yerlesim)
        
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
                    value = str(row.get(col, ""))
                    self.sikayet_tablosu.setItem(i, j, QTableWidgetItem(value))
        except Exception as e:
            self.loglayici.error(f"Sikayet tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self.parent, "Hata", f"Sikayet tablosu guncellenirken hata: {str(e)}")
    
    def sikayet_ekle(self):
        """Yeni sikayet eklemek icin dialog olusturur"""
        try:
            dialog = QDialog(self.parent)
            dialog.setWindowTitle("Yeni Sikayet Ekle")
            dialog.setMinimumWidth(400)
            
            yerlesim = QFormLayout(dialog)
            
            musteri_giris = QComboBox()
            musteri_giris.addItems(self.services.data_manager.musteriler_df["Musteri Adi"].tolist())
            siparis_no_giris = QLineEdit()
            sikayet_turu_giris = QComboBox()
            sikayet_turu_giris.addItems(["Urun Kalitesi", "Teslimat Gecikmesi", "Ambalaj Hatasi", "Yanlis Urun", "Diger"])
            sikayet_detayi_giris = QTextEdit()
            sikayet_detayi_giris.setFixedHeight(100)  # Daha fazla detay icin alan
            tarih_giris = QDateEdit()
            tarih_giris.setDate(QDate.currentDate())
            tarih_giris.setCalendarPopup(True)
            durum_giris = QComboBox()
            durum_giris.addItems(["Acik", "Islemde", "Cozuldu", "Kapatildi"])
            
            yerlesim.addRow("Musteri:", musteri_giris)
            yerlesim.addRow("Siparis No:", siparis_no_giris)
            yerlesim.addRow("Sikayet Turu:", sikayet_turu_giris)
            yerlesim.addRow("Sikayet Detayi:", sikayet_detayi_giris)
            yerlesim.addRow("Tarih:", tarih_giris)
            yerlesim.addRow("Durum:", durum_giris)
            
            butonlar = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | 
                QDialogButtonBox.StandardButton.Cancel
            )
            
            yerlesim.addRow(butonlar)
            
            kaydet_butonu = butonlar.button(QDialogButtonBox.StandardButton.Ok)
            kaydet_butonu.setText("Kaydet")
            iptal_butonu = butonlar.button(QDialogButtonBox.StandardButton.Cancel)
            iptal_butonu.setText("Iptal")
            
            def sikayet_kaydet():
                try:
                    # Validasyon
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
                    
                    # Thread pool kullanarak arka planda sikayet ekleme islemi
                    if hasattr(self.parent, 'thread_pool') and self.parent.thread_pool is not None:
                        self.parent.thread_pool.submit(self._sikayet_ekle_thread, yeni_sikayet, dialog)
                    else:
                        # Thread pool yoksa normal sekilde ekle
                        self.services.add_complaint(yeni_sikayet)  # CRMServices uzerinden ekleme
                        self.sikayet_tablosu_guncelle()
                        dialog.accept()
                    
                    self.loglayici.info(f"Yeni sikayet eklendi: {yeni_sikayet['Musteri Adi']} - {yeni_sikayet['Sikayet Turu']}")
                    QMessageBox.information(self.parent, "Basarili", "Sikayet basariyla eklendi.")
                except Exception as e:
                    QMessageBox.critical(self.parent, "Hata", f"Sikayet eklenirken hata: {str(e)}")
                    self.loglayici.error(f"Sikayet ekleme hatasi: {str(e)}")
            
            kaydet_butonu.clicked.connect(sikayet_kaydet)
            iptal_butonu.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            self.loglayici.error(f"Sikayet ekleme dialog hatasi: {str(e)}")
            QMessageBox.critical(self.parent, "Hata", f"Sikayet ekleme dialog hatasi: {str(e)}")
    
    def sikayet_duzenle(self):
        selected_items = self.sikayet_tablosu.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.parent, "Uyari", "Lutfen duzenlemek icin bir sikayet secin.")
            return
            
        row = selected_items[0].row()
        
        try:
            dialog = QDialog(self.parent)
            dialog.setWindowTitle("Sikayet Duzenle")
            dialog.setMinimumWidth(400)
            
            sikayet = self.services.data_manager.sikayetler_df.iloc[row]  # self.veri_yoneticisi -> self.services.data_manager
            
            yerlesim = QFormLayout(dialog)
            musteri_giris = QComboBox()
            musteri_giris.addItems(self.services.data_manager.musteriler_df["Musteri Adi"].tolist())
            musteri_giris.setCurrentText(str(sikayet["Musteri Adi"]))
            siparis_no_giris = QLineEdit(str(sikayet["Siparis No"]))
            sikayet_turu_giris = QComboBox()
            sikayet_turu_giris.addItems(["Urun Kalitesi", "Teslimat Gecikmesi", "Ambalaj Hatasi", "Yanlis Urun", "Diger"])
            sikayet_turu_giris.setCurrentText(sikayet["Sikayet Turu"])
            sikayet_detayi_giris = QTextEdit(str(sikayet["Sikayet Detayi"]))  # numpy.int64 -> str donusumu
            sikayet_detayi_giris.setFixedHeight(100)
            
            tarih_giris = QDateEdit()
            tarih_giris.setDate(QDate.fromString(sikayet["Tarih"], "yyyy-MM-dd"))
            tarih_giris.setCalendarPopup(True)
            
            durum_giris = QComboBox()
            durum_giris.addItems(["Acik", "Islemde", "Cozuldu", "Kapatildi"])
            durum_giris.setCurrentText(sikayet["Durum"])
            
            yerlesim.addRow("Musteri:", musteri_giris)
            yerlesim.addRow("Siparis No:", siparis_no_giris)
            yerlesim.addRow("Sikayet Turu:", sikayet_turu_giris)
            yerlesim.addRow("Sikayet Detayi:", sikayet_detayi_giris)
            yerlesim.addRow("Tarih:", tarih_giris)
            yerlesim.addRow("Durum:", durum_giris)
            
            butonlar = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | 
                QDialogButtonBox.StandardButton.Cancel
            )
            
            yerlesim.addRow(butonlar)
            
            kaydet_butonu = butonlar.button(QDialogButtonBox.StandardButton.Ok)
            kaydet_butonu.setText("Guncelle")
            iptal_butonu = butonlar.button(QDialogButtonBox.StandardButton.Cancel)
            iptal_butonu.setText("Iptal")
            
            def sikayet_guncelle():
                try:
                    # Validasyon
                    if not sikayet_detayi_giris.toPlainText().strip():
                        raise ValueError("Sikayet detayi bos birakilamaz.")
                    
                    guncellenmis_sikayet = {
                        "Musteri Adi": musteri_giris.currentText(),
                        "Siparis No": siparis_no_giris.text(),
                        "Sikayet Turu": sikayet_turu_giris.currentText(),
                        "Sikayet Detayi": sikayet_detayi_giris.toPlainText(),
                        "Tarih": tarih_giris.date().toString("yyyy-MM-dd"),
                        "Durum": durum_giris.currentText()
                    }
                    
                    # Thread pool kullanarak arka planda sikayet guncelleme islemi
                    if hasattr(self.parent, 'thread_pool') and self.parent.thread_pool is not None:
                        self.parent.thread_pool.submit(self._sikayet_guncelle_thread, row, guncellenmis_sikayet, dialog)
                    else:
                        # Thread pool yoksa normal sekilde guncelle
                        # Sikayet guncelleme islemi
                        self.services.data_manager.sikayetler_df.iloc[row] = pd.Series(guncellenmis_sikayet)
                        self.services.data_manager.repository.save(self.services.data_manager.sikayetler_df, "complaints")
                        
                        self.sikayet_tablosu_guncelle()
                        dialog.accept()
                        
                        self.loglayici.info(f"Sikayet guncellendi: {guncellenmis_sikayet['Musteri Adi']} - {guncellenmis_sikayet['Sikayet Turu']}")
                        QMessageBox.information(self.parent, "Basarili", "Sikayet basariyla guncellendi.")
                except Exception as e:
                    QMessageBox.critical(self.parent, "Hata", f"Sikayet guncellenirken hata: {str(e)}")
                    self.loglayici.error(f"Sikayet guncelleme hatasi: {str(e)}")
            
            kaydet_butonu.clicked.connect(sikayet_guncelle)
            iptal_butonu.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            self.loglayici.error(f"Sikayet duzenleme dialog hatasi: {str(e)}")
            QMessageBox.critical(self.parent, "Hata", f"Sikayet duzenleme dialog hatasi: {str(e)}")
    
    def sikayet_sil(self):
        selected_items = self.sikayet_tablosu.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.parent, "Uyari", "Lutfen silmek icin bir sikayet secin.")
            return
            
        row = selected_items[0].row()
        
        try:
            sikayet = self.services.data_manager.sikayetler_df.iloc[row]
            musteri_adi = sikayet["Musteri Adi"]
            sikayet_turu = sikayet["Sikayet Turu"]
            
            cevap = QMessageBox.question(
                self.parent,
                "Sikayet Sil",
                f"{musteri_adi} musterisine ait {sikayet_turu} sikayetini silmek istediginize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if cevap == QMessageBox.StandardButton.Yes:
                # Thread pool kullanarak arka planda sikayet silme islemi
                if hasattr(self.parent, 'thread_pool') and self.parent.thread_pool is not None:
                    self.parent.thread_pool.submit(self._sikayet_sil_thread, row, musteri_adi, sikayet_turu)
                else:
                    # Thread pool yoksa normal sekilde sil
                    # Sikayet silme islemi
                    self.services.data_manager.sikayetler_df = self.services.data_manager.sikayetler_df.drop(row).reset_index(drop=True)
                    self.services.data_manager.repository.save(self.services.data_manager.sikayetler_df, "complaints")
                    
                    self.sikayet_tablosu_guncelle()
                    
                    self.loglayici.info(f"Sikayet silindi: {musteri_adi} - {sikayet_turu}")
                    QMessageBox.information(self.parent, "Basarili", "Sikayet basariyla silindi.")
        except Exception as e:
            self.loglayici.error(f"Sikayet silme hatasi: {str(e)}")
            QMessageBox.critical(self.parent, "Hata", f"Sikayet silinirken hata: {str(e)}")
    
    def _sikayet_ekle_thread(self, yeni_sikayet, dialog):
        """
        Thread pool ile arka planda sikayet ekleme islemini gerceklestirir.
        
        Args:
            yeni_sikayet: Eklenecek sikayet bilgileri
            dialog: Kapatilacak dialog
        """
        try:
            self.services.add_complaint(yeni_sikayet)
            
            # UI guncellemesi icin ana thread'e geri don
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_sikayet_ekleme_tamamlandi", 
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, True),
                                    Q_ARG(object, dialog))
        except Exception as e:
            self.loglayici.error(f"Sikayet ekleme thread hatasi: {str(e)}")
            # Hata durumunda ana thread'e geri don
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_sikayet_ekleme_tamamlandi", 
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, False),
                                    Q_ARG(object, dialog),
                                    Q_ARG(str, str(e)))
    
    def _sikayet_ekleme_tamamlandi(self, basarili, dialog, hata_mesaji=None):
        """
        Thread pool ile sikayet ekleme islemi tamamlandiginda cagrilan metod.
        
        Args:
            basarili: Islemin basarili olup olmadigi
            dialog: Kapatilacak dialog
            hata_mesaji: Hata durumunda hata mesaji
        """
        if basarili:
            self.sikayet_tablosu_guncelle()
            dialog.accept()
        else:
            QMessageBox.critical(self.parent, "Hata", f"Sikayet eklenirken hata: {hata_mesaji}") 

    def _sikayet_guncelle_thread(self, row, guncellenmis_sikayet, dialog):
        """
        Thread pool ile arka planda sikayet guncelleme islemi gerceklestirir.
        
        Args:
            row: Guncellenecek sikayetin indeksi
            guncellenmis_sikayet: Guncellenecek sikayet bilgileri
            dialog: Kapatilacak dialog
        """
        try:
            # Sikayet guncelleme islemi
            self.services.data_manager.sikayetler_df.iloc[row] = pd.Series(guncellenmis_sikayet)
            self.services.data_manager.repository.save(self.services.data_manager.sikayetler_df, "complaints")
            
            # UI guncellemesi icin ana thread'e geri don
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_sikayet_guncelleme_tamamlandi", 
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, True),
                                    Q_ARG(object, dialog),
                                    Q_ARG(dict, guncellenmis_sikayet))
        except Exception as e:
            self.loglayici.error(f"Sikayet guncelleme thread hatasi: {str(e)}")
            # Hata durumunda ana thread'e geri don
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_sikayet_guncelleme_tamamlandi", 
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, False),
                                    Q_ARG(object, dialog),
                                    Q_ARG(str, str(e)))
    
    def _sikayet_guncelleme_tamamlandi(self, basarili, dialog, guncellenmis_sikayet=None, hata_mesaji=None):
        """
        Thread pool ile sikayet guncelleme islemi tamamlandiginda cagrilan metod.
        
        Args:
            basarili: Islemin basarili olup olmadigi
            dialog: Kapatilacak dialog
            guncellenmis_sikayet: Guncellenen sikayet bilgileri
            hata_mesaji: Hata durumunda hata mesaji
        """
        if basarili:
            self.sikayet_tablosu_guncelle()
            dialog.accept()
            self.loglayici.info(f"Sikayet guncellendi: {guncellenmis_sikayet['Musteri Adi']} - {guncellenmis_sikayet['Sikayet Turu']}")
            QMessageBox.information(self.parent, "Basarili", "Sikayet basariyla guncellendi.")
        else:
            QMessageBox.critical(self.parent, "Hata", f"Sikayet guncellenirken hata: {hata_mesaji}")

    def _sikayet_sil_thread(self, row, musteri_adi, sikayet_turu):
        """
        Thread pool ile arka planda sikayet silme islemini gerceklestirir.
        
        Args:
            row: Silinecek sikayetin indeksi
            musteri_adi: Silinecek sikayetin musteri adi
            sikayet_turu: Silinecek sikayetin turu
        """
        try:
            # Sikayet silme islemi
            self.services.data_manager.sikayetler_df = self.services.data_manager.sikayetler_df.drop(row).reset_index(drop=True)
            self.services.data_manager.repository.save(self.services.data_manager.sikayetler_df, "complaints")
            
            # UI guncellemesi icin ana thread'e geri don
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_sikayet_silme_tamamlandi", 
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, True),
                                    Q_ARG(str, musteri_adi),
                                    Q_ARG(str, sikayet_turu))
        except Exception as e:
            self.loglayici.error(f"Sikayet silme thread hatasi: {str(e)}")
            # Hata durumunda ana thread'e geri don
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_sikayet_silme_tamamlandi", 
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, False),
                                    Q_ARG(str, str(e)))
    
    def _sikayet_silme_tamamlandi(self, basarili, musteri_adi=None, sikayet_turu=None, hata_mesaji=None):
        """
        Thread pool ile sikayet silme islemi tamamlandiginda cagrilan metod.
        
        Args:
            basarili: Islemin basarili olup olmadigi
            musteri_adi: Silinen sikayetin musteri adi
            sikayet_turu: Silinen sikayetin turu
            hata_mesaji: Hata durumunda hata mesaji
        """
        if basarili:
            self.sikayet_tablosu_guncelle()
            self.loglayici.info(f"Sikayet silindi: {musteri_adi} - {sikayet_turu}")
            QMessageBox.information(self.parent, "Basarili", "Sikayet basariyla silindi.")
        else:
            QMessageBox.critical(self.parent, "Hata", f"Sikayet silinirken hata: {hata_mesaji}")
