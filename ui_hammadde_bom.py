# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QLineEdit, QFormLayout, QComboBox, QDateEdit,
                             QDialog, QMessageBox, QFrame, QDialogButtonBox, QProgressBar, QLabel,
                             QAbstractItemView, QFileDialog, QGroupBox, QTextEdit, QProgressDialog,
                             QToolButton)
from PyQt6.QtCore import QDate, pyqtSignal, QThread, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QAction, QFont
from events import Event, EventManager, EVENT_DATA_UPDATED, EVENT_UI_UPDATED, EVENT_ERROR_OCCURRED
from veri_yukleme_worker import VeriYuklemeWorker
from ui_interface import UIInterface
import pandas as pd

class AnaPencere(QMainWindow, UIInterface):
    data_updated_signal = pyqtSignal(Event)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Event aboneligi
        if hasattr(self, 'event_manager') and self.event_manager:
            self.event_manager.subscribe(EVENT_DATA_UPDATED, self.tum_sekmeleri_guncelle)
            self.event_manager.subscribe(EVENT_UI_UPDATED, self._on_ui_updated)
        
        # Eksik veri uyarı sistemi için timer
        self.uyari_timer = QTimer(self)
        self.uyari_timer.timeout.connect(self.uyari_butonu_animasyon)
        self.uyari_aktif = False
        self.uyari_durum = False  # Yanıp sönme durumu
        self.eksik_veri_uyarilari = []  # Uyarı listesi
    
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
    
    def _on_ui_updated(self, event: Event) -> None:
        """UI guncellendiginde tepki ver"""
        if hasattr(self, 'loglayici') and self.loglayici:
            self.loglayici.info(f"UI guncellendi: {event.data}")
        
        # Hammadde ve BOM ile ilgili guncellemeleri isle
        if event.data.get("source") == "gorsellestirici" and event.data.get("action") == "refresh_charts":
            self.tum_sekmeleri_guncelle(event)
    
    def tum_verileri_yukle(self) -> None:
        """UIInterface'den gelen tum_verileri_yukle metodunun implementasyonu"""
        try:
            if hasattr(self, 'internet_baglantisi') and self.internet_baglantisi.offline_mod:
                QMessageBox.information(self, "Offline Mod", 
                    "Program offline modda. Sadece yerel veriler kullanilabilir.")
                return
            
            dosya_yolu, _ = QFileDialog.getOpenFileName(self, "Excel Dosyasi Sec", "", "Excel Dosyalari (*.xlsx)")
            if not dosya_yolu:
                if hasattr(self, 'event_manager') and self.event_manager:
                    self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": "Dosya secimi iptal edildi"}))
                return
                
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
            ilerleme_dialog.show()
            
            # VeriYuklemeWorker sinifi artik veri_yukleme_worker.py'den import ediliyor
            self.worker = VeriYuklemeWorker(self.services.data_manager, dosya_yolu)
            
            def ilerleme_guncelle(data):
                ilerleme_cubugu.setValue(int(data["progress"]))
                durum_etiketi.setText(f"Yukleniyor: {data['current_table']} ({data['loaded_tables']}/{data['total_tables']})")
            
            def yukleme_tamamlandi():
                ilerleme_dialog.accept()
                if hasattr(self, 'filtreleri_guncelle'):
                    self.filtreleri_guncelle()
                QMessageBox.information(self, "Basarili", "Veriler yuklendi ve veritabanina kaydedildi.")
                self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "tum_verileri_yukle"}))
                self.tum_sekmeleri_guncelle()
            
            def yukleme_hatasi(hata_mesaji):
                ilerleme_dialog.reject()
                QMessageBox.critical(self, "Hata", hata_mesaji)
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.error(hata_mesaji)
            
            self.worker.ilerleme.connect(ilerleme_guncelle)
            self.worker.tamamlandi.connect(yukleme_tamamlandi)
            self.worker.hata.connect(yukleme_hatasi)
            self.worker.start()
            
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Veri yukleme hatasi: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Veri yukleme sirasinda bir hata olustu: {str(e)}")
            if hasattr(self, 'event_manager') and self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": str(e)}))
    
    def hammadde_maliyetleri_olustur(self):
        """Hammadde maliyetleri sekmesini olusturur"""
        self.hammadde_tab = QWidget()
        self.sekme_widget.addTab(self.hammadde_tab, "Hammadde Maliyetleri")
        
        ana_yerlesim = QVBoxLayout()
        self.hammadde_tab.setLayout(ana_yerlesim)
        
        # Ust kisim - Butonlar
        buton_yerlesim = QHBoxLayout()
        
        self.hammadde_ekle_butonu = QPushButton("Hammadde Ekle")
        self.hammadde_ekle_butonu.clicked.connect(self.hammadde_ekle)
        buton_yerlesim.addWidget(self.hammadde_ekle_butonu)
        
        self.hammadde_duzenle_butonu = QPushButton("Hammadde Duzenle")
        self.hammadde_duzenle_butonu.clicked.connect(self.hammadde_duzenle)
        buton_yerlesim.addWidget(self.hammadde_duzenle_butonu)
        
        self.hammadde_sil_butonu = QPushButton("Hammadde Sil")
        self.hammadde_sil_butonu.clicked.connect(self.hammadde_sil)
        buton_yerlesim.addWidget(self.hammadde_sil_butonu)
        
        ana_yerlesim.addLayout(buton_yerlesim)
        
        # Tablo
        self.hammadde_tablosu = QTableWidget()
        self.hammadde_tablosu.setColumnCount(7)
        self.hammadde_tablosu.setHorizontalHeaderLabels([
            "Hammadde Kodu", "Hammadde Adi", "Hammadde Tipi", 
            "Mukavva Tipi", "Birim Maliyet", "Ay", "Para Birimi"
        ])
        self.hammadde_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ana_yerlesim.addWidget(self.hammadde_tablosu)
        
        # Tabloyu guncelle
        self.hammadde_tablosu_guncelle()
    
    def hammadde_tablosu_guncelle(self):
        """Hammadde tablosunu gunceller"""
        try:
            hammadde_df = self.services.data_manager.hammadde_df
            
            self.hammadde_tablosu.setRowCount(0)
            
            if hammadde_df is None or hammadde_df.empty:
                # Varsayilan basliklar
                self.hammadde_tablosu.setHorizontalHeaderLabels([
                    "Hammadde Kodu", "Hammadde Adi", "Hammadde Tipi", 
                    "Mukavva Tipi", "Birim Maliyet", "Ay", "Para Birimi"
                ])
                return
                
            self.hammadde_tablosu.setRowCount(len(hammadde_df))
            
            # Sunger tipi hammadde var mi kontrol et
            sunger_var = False
            for _, row in hammadde_df.iterrows():
                if str(row.get("Hammadde Tipi", "")) == "Sunger":
                    sunger_var = True
                    break
            
            # Basliklar
            basliklar = [
                "Hammadde Kodu", "Hammadde Adi", "Hammadde Tipi", 
                "Mukavva Tipi", "Birim Maliyet", "Ay", "Para Birimi"
            ]
            
            # Sunger varsa birim maliyet basligini degistir
            if sunger_var:
                basliklar[4] = "m2 Maliyet"
            
            # Tablo basliklarini ayarla
            self.hammadde_tablosu.setHorizontalHeaderLabels(basliklar)
            
            # Tablo icerigini doldur
            for i, row in hammadde_df.iterrows():
                self.hammadde_tablosu.setItem(i, 0, QTableWidgetItem(str(row.get("Hammadde Kodu", ""))))
                self.hammadde_tablosu.setItem(i, 1, QTableWidgetItem(str(row.get("Hammadde Adi", ""))))
                self.hammadde_tablosu.setItem(i, 2, QTableWidgetItem(str(row.get("Hammadde Tipi", ""))))
                self.hammadde_tablosu.setItem(i, 3, QTableWidgetItem(str(row.get("Mukavva Tipi", ""))))
                self.hammadde_tablosu.setItem(i, 4, QTableWidgetItem(str(row.get("Birim Maliyet", ""))))
                self.hammadde_tablosu.setItem(i, 5, QTableWidgetItem(str(row.get("Ay", ""))))
                self.hammadde_tablosu.setItem(i, 6, QTableWidgetItem(str(row.get("Para Birimi", ""))))
        except Exception as e:
            self.loglayici.error(f"Hammadde tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Hammadde tablosu guncellenirken hata: {str(e)}")

    def hammadde_ekle(self):
        """Yeni hammadde ekler"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Hammadde Ekle")
        dialog.setMinimumWidth(400)
        
        form_yerlesim = QFormLayout(dialog)
        
        hammadde_kodu_input = QLineEdit()
        hammadde_adi_input = QLineEdit()
        
        # Hammadde tipi secimi
        hammadde_tipi_combo = QComboBox()
        hammadde_tipleri = ["Oluklu Mukavva", "Ahsap", "Metal", "Kosebent", "Sunger"]
        hammadde_tipi_combo.addItems(hammadde_tipleri)
        
        # Mukavva tipi secimi (sadece oluklu mukavva icin)
        mukavva_tipi_frame = QFrame()
        mukavva_tipi_layout = QFormLayout(mukavva_tipi_frame)
        mukavva_tipi_combo = QComboBox()
        mukavva_tipleri = ["B Dalga", "C Dalga", "A Dalga", "BC Dalga", "AA Dalga", 
                          "AC Dalga", "BCA Dalga", "ACA Dalga"]
        mukavva_tipi_combo.addItems(mukavva_tipleri)
        mukavva_tipi_layout.addRow("Mukavva Tipi:", mukavva_tipi_combo)
        
        # Birim agirlik ve m2 (sadece oluklu mukavva icin)
        birim_agirlik_frame = QFrame()
        birim_agirlik_layout = QFormLayout(birim_agirlik_frame)
        birim_agirlik_input = QLineEdit()
        birim_agirlik_layout.addRow("m2 Agirlik:", birim_agirlik_input)
        
        birim_maliyet_input = QLineEdit()
        
        # Birim maliyet etiketi (dinamik olarak degisecek)
        birim_maliyet_label = QLabel("Birim Maliyet:")
        
        ay_combo = QComboBox()
        aylar = ["Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", 
                "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]
        ay_combo.addItems(aylar)
        
        para_birimi_combo = QComboBox()
        para_birimi_combo.addItems(["TL", "USD", "EUR"])
        
        form_yerlesim.addRow("Hammadde Kodu:", hammadde_kodu_input)
        form_yerlesim.addRow("Hammadde Adi:", hammadde_adi_input)
        form_yerlesim.addRow("Hammadde Tipi:", hammadde_tipi_combo)
        form_yerlesim.addWidget(mukavva_tipi_frame)
        form_yerlesim.addWidget(birim_agirlik_frame)
        form_yerlesim.addRow(birim_maliyet_label, birim_maliyet_input)
        form_yerlesim.addRow("Ay:", ay_combo)
        form_yerlesim.addRow("Para Birimi:", para_birimi_combo)
        
        # Baslangicta sadece oluklu mukavva icin alanlari goster
        mukavva_tipi_frame.setVisible(hammadde_tipi_combo.currentText() == "Oluklu Mukavva")
        birim_agirlik_frame.setVisible(hammadde_tipi_combo.currentText() == "Oluklu Mukavva")
        
        # Hammadde tipi degistiginde alanlari guncelle
        def hammadde_tipi_degisti():
            secili_tip = hammadde_tipi_combo.currentText()
            mukavva_tipi_frame.setVisible(secili_tip == "Oluklu Mukavva")
            birim_agirlik_frame.setVisible(secili_tip == "Oluklu Mukavva")
            
            # Sunger icin birim maliyet etiketini degistir
            if secili_tip == "Sunger":
                birim_maliyet_label.setText("m2 Maliyet:")
            else:
                birim_maliyet_label.setText("Birim Maliyet:")
        
        hammadde_tipi_combo.currentTextChanged.connect(hammadde_tipi_degisti)
        
        # Baslangicta hammadde tipine gore etiketi ayarla
        hammadde_tipi_degisti()
        
        buton_kutusu = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form_yerlesim.addRow(buton_kutusu)
        
        buton_kutusu.accepted.connect(dialog.accept)
        buton_kutusu.rejected.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Sayisal degerler icin kontrol
                try:
                    birim_agirlik = float(birim_agirlik_input.text()) if birim_agirlik_input.text() else 0
                    birim_maliyet = float(birim_maliyet_input.text()) if birim_maliyet_input.text() else 0
                except ValueError:
                    QMessageBox.warning(self, "Hata", "m2 Agirlik ve Birim Maliyet sayisal deger olmalidir.")
                    return
                
                yeni_hammadde = {
                    "Hammadde Kodu": hammadde_kodu_input.text(),
                    "Hammadde Adi": hammadde_adi_input.text(),
                    "Hammadde Tipi": hammadde_tipi_combo.currentText(),
                    "Mukavva Tipi": mukavva_tipi_combo.currentText() if hammadde_tipi_combo.currentText() == "Oluklu Mukavva" else None,
                    "m2 Agirlik": birim_agirlik,
                    "Birim Maliyet": birim_maliyet,
                    "Ay": ay_combo.currentText(),
                    "Para Birimi": para_birimi_combo.currentText()
                }
                
                self.services.add_hammadde(yeni_hammadde)
                self.hammadde_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Hammadde basariyla eklendi.")
            except Exception as e:
                self.loglayici.error(f"Hammadde eklenirken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Hammadde eklenirken hata: {str(e)}")
    
    def hammadde_duzenle(self):
        """Secili hammaddeyi duzenler"""
        secili_satirlar = self.hammadde_tablosu.selectedIndexes()
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek icin bir hammadde secin.")
            return
            
        secili_satir = secili_satirlar[0].row()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Hammadde Duzenle")
        dialog.setMinimumWidth(400)
        
        form_yerlesim = QFormLayout(dialog)
        
        hammadde_kodu_input = QLineEdit(self.hammadde_tablosu.item(secili_satir, 0).text())
        hammadde_adi_input = QLineEdit(self.hammadde_tablosu.item(secili_satir, 1).text())
        
        # Hammadde tipi secimi
        hammadde_tipi_combo = QComboBox()
        hammadde_tipleri = ["Oluklu Mukavva", "Ahsap", "Metal", "Kosebent", "Sunger"]
        hammadde_tipi_combo.addItems(hammadde_tipleri)
        hammadde_tipi_combo.setCurrentText(self.hammadde_tablosu.item(secili_satir, 2).text())
        
        # Mukavva tipi secimi (sadece oluklu mukavva icin)
        mukavva_tipi_frame = QFrame()
        mukavva_tipi_layout = QFormLayout(mukavva_tipi_frame)
        mukavva_tipi_combo = QComboBox()
        mukavva_tipleri = ["B Dalga", "C Dalga", "A Dalga", "BC Dalga", "AA Dalga", 
                          "AC Dalga", "BCA Dalga", "ACA Dalga"]
        mukavva_tipi_combo.addItems(mukavva_tipleri)
        
        # Mevcut mukavva tipini ayarla
        mukavva_tipi = self.hammadde_tablosu.item(secili_satir, 3).text()
        if mukavva_tipi and mukavva_tipi != "None":
            mukavva_tipi_combo.setCurrentText(mukavva_tipi)
        mukavva_tipi_layout.addRow("Mukavva Tipi:", mukavva_tipi_combo)
        
        # Birim agirlik ve m2 (sadece oluklu mukavva icin)
        birim_agirlik_frame = QFrame()
        birim_agirlik_layout = QFormLayout(birim_agirlik_frame)
        birim_agirlik_input = QLineEdit()
        
        # Veritabanindaki hammadde bilgilerini al
        hammadde_df = self.services.data_manager.hammadde_df
        if not hammadde_df.empty:
            hammadde_row = hammadde_df.iloc[secili_satir]
            if "m2 Agirlik" in hammadde_row and hammadde_row["m2 Agirlik"] is not None:
                birim_agirlik_input.setText(str(hammadde_row["m2 Agirlik"]))
        birim_agirlik_layout.addRow("m2 Agirlik:", birim_agirlik_input)
        
        birim_maliyet_input = QLineEdit(self.hammadde_tablosu.item(secili_satir, 4).text())
        
        # Birim maliyet etiketi (dinamik olarak degisecek)
        birim_maliyet_label = QLabel("Birim Maliyet:")
        
        ay_combo = QComboBox()
        aylar = ["Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", 
                "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]
        ay_combo.addItems(aylar)
        ay_combo.setCurrentText(self.hammadde_tablosu.item(secili_satir, 5).text())
        
        para_birimi_combo = QComboBox()
        para_birimi_combo.addItems(["TL", "USD", "EUR"])
        para_birimi_combo.setCurrentText(self.hammadde_tablosu.item(secili_satir, 6).text())
        
        form_yerlesim.addRow("Hammadde Kodu:", hammadde_kodu_input)
        form_yerlesim.addRow("Hammadde Adi:", hammadde_adi_input)
        form_yerlesim.addRow("Hammadde Tipi:", hammadde_tipi_combo)
        form_yerlesim.addWidget(mukavva_tipi_frame)
        form_yerlesim.addWidget(birim_agirlik_frame)
        form_yerlesim.addRow(birim_maliyet_label, birim_maliyet_input)
        form_yerlesim.addRow("Ay:", ay_combo)
        form_yerlesim.addRow("Para Birimi:", para_birimi_combo)
        
        # Baslangicta sadece ilgili hammadde tipine gore alanlari goster
        secili_tip = hammadde_tipi_combo.currentText()
        mukavva_tipi_frame.setVisible(secili_tip == "Oluklu Mukavva")
        birim_agirlik_frame.setVisible(secili_tip == "Oluklu Mukavva")
        
        # Hammadde tipi degistiginde alanlari guncelle
        def hammadde_tipi_degisti():
            secili_tip = hammadde_tipi_combo.currentText()
            mukavva_tipi_frame.setVisible(secili_tip == "Oluklu Mukavva")
            birim_agirlik_frame.setVisible(secili_tip == "Oluklu Mukavva")
            
            # Sunger icin birim maliyet etiketini degistir
            if secili_tip == "Sunger":
                birim_maliyet_label.setText("m2 Maliyet:")
            else:
                birim_maliyet_label.setText("Birim Maliyet:")
        
        hammadde_tipi_combo.currentTextChanged.connect(hammadde_tipi_degisti)
        
        buton_kutusu = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form_yerlesim.addRow(buton_kutusu)
        
        buton_kutusu.accepted.connect(dialog.accept)
        buton_kutusu.rejected.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Sayisal degerler icin kontrol
                try:
                    birim_agirlik = float(birim_agirlik_input.text()) if birim_agirlik_input.text() else 0
                    birim_maliyet = float(birim_maliyet_input.text()) if birim_maliyet_input.text() else 0
                except ValueError:
                    QMessageBox.warning(self, "Hata", "m2 Agirlik ve Birim Maliyet sayisal deger olmalidir.")
                    return
                
                guncellenmis_hammadde = {
                    "Hammadde Kodu": hammadde_kodu_input.text(),
                    "Hammadde Adi": hammadde_adi_input.text(),
                    "Hammadde Tipi": hammadde_tipi_combo.currentText(),
                    "Mukavva Tipi": mukavva_tipi_combo.currentText() if hammadde_tipi_combo.currentText() == "Oluklu Mukavva" else None,
                    "m2 Agirlik": birim_agirlik,
                    "Birim Maliyet": birim_maliyet,
                    "Ay": ay_combo.currentText(),
                    "Para Birimi": para_birimi_combo.currentText()
                }
                
                self.services.update_hammadde(secili_satir, guncellenmis_hammadde)
                self.hammadde_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Hammadde basariyla guncellendi.")
            except Exception as e:
                self.loglayici.error(f"Hammadde guncellenirken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Hammadde guncellenirken hata: {str(e)}")
    
    def hammadde_sil(self):
        """Secili hammaddeyi siler"""
        secili_satirlar = self.hammadde_tablosu.selectedIndexes()
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir hammadde secin.")
            return
            
        secili_satir = secili_satirlar[0].row()
        hammadde_kodu = self.hammadde_tablosu.item(secili_satir, 0).text()
        
        onay = QMessageBox.question(self, "Hammadde Sil", 
                                   f"'{hammadde_kodu}' kodlu hammaddeyi silmek istediginize emin misiniz?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                   
        if onay == QMessageBox.StandardButton.Yes:
            try:
                self.services.delete_hammadde(hammadde_kodu)
                self.hammadde_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Hammadde basariyla silindi.")
            except Exception as e:
                self.loglayici.error(f"Hammadde silinirken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Hammadde silinirken hata: {str(e)}")
    
    def tum_sekmeleri_guncelle(self, event: Event = None) -> None:
        """Tum sekmeleri gunceller"""
        if not hasattr(self, 'is_initialized') or not self.is_initialized:
            return
            
        try:
            # Hammadde ve BOM ile ilgili tablolari guncelle
            if hasattr(self, 'hammadde_tablosu_guncelle'):
                self.hammadde_tablosu_guncelle()
                
            if hasattr(self, 'urun_bom_tablosu_guncelle'):
                self.urun_bom_tablosu_guncelle()
            
            # Eksik veri kontrolü yap
            if hasattr(self, 'eksik_veri_kontrol'):
                self.eksik_veri_kontrol()
            
            # Status bar guncelleme
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage("Hammadde ve BOM verileri guncellendi")
                
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Hammadde tablolari guncellenirken hata: {str(e)}")
            
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"Guncelleme hatasi: {str(e)}")

    def urun_bom_olustur(self):
        """Urun BOM sekmesini olusturur"""
        self.urun_bom_tab = QWidget()
        self.sekme_widget.addTab(self.urun_bom_tab, "Urun BOM")
        
        ana_yerlesim = QVBoxLayout()
        self.urun_bom_tab.setLayout(ana_yerlesim)
        
        # Ust kisim - Butonlar
        buton_yerlesim = QHBoxLayout()
        
        self.urun_bom_ekle_butonu = QPushButton("Urun BOM Ekle")
        self.urun_bom_ekle_butonu.clicked.connect(self.urun_bom_ekle)
        buton_yerlesim.addWidget(self.urun_bom_ekle_butonu)
        
        self.urun_bom_duzenle_butonu = QPushButton("Urun BOM Duzenle")
        self.urun_bom_duzenle_butonu.clicked.connect(self.urun_bom_duzenle)
        buton_yerlesim.addWidget(self.urun_bom_duzenle_butonu)
        
        self.urun_bom_sil_butonu = QPushButton("Urun BOM Sil")
        self.urun_bom_sil_butonu.clicked.connect(self.urun_bom_sil)
        buton_yerlesim.addWidget(self.urun_bom_sil_butonu)
        
        self.urun_bazli_bom_goster_butonu = QPushButton("Urun Bazli BOM Goster")
        self.urun_bazli_bom_goster_butonu.clicked.connect(self.urun_bazli_bom_goster)
        buton_yerlesim.addWidget(self.urun_bazli_bom_goster_butonu)
        
        # Agirlik hesaplama butonu ekle
        self.agirlik_hesapla_butonu = QPushButton("Tum Agirliklari Hesapla")
        self.agirlik_hesapla_butonu.clicked.connect(self.tum_agirliklari_hesapla)
        self.agirlik_hesapla_butonu.setStyleSheet("background-color: #e6f7ff; font-weight: bold;")  # Acik mavi arka plan
        buton_yerlesim.addWidget(self.agirlik_hesapla_butonu)
        
        # Eksik veri uyarı butonu ekle
        self.uyari_butonu = QToolButton()
        self.uyari_butonu.setText("!")
        self.uyari_butonu.setToolTip("Eksik veri uyarıları")
        self.uyari_butonu.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.uyari_butonu.setStyleSheet("background-color: #f0f0f0; color: #666; border-radius: 12px; min-width: 24px; min-height: 24px;")
        self.uyari_butonu.clicked.connect(self.eksik_veri_uyarisi_goster)
        buton_yerlesim.addWidget(self.uyari_butonu)
        
        ana_yerlesim.addLayout(buton_yerlesim)
        
        # Tablo
        self.urun_bom_tablosu = QTableWidget()
        self.urun_bom_tablosu.setColumnCount(9)  # Bir sutun daha ekledik (Urun Agirligi)
        self.urun_bom_tablosu.setHorizontalHeaderLabels([
            "Urun Kodu", "Urun Adi", "Hammadde Kodu", "Hammadde Adi", 
            "Miktar", "Birim", "Hammadde Agirligi", "Urun Agirligi (Oluklu)", "Aciklama"
        ])
        self.urun_bom_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ana_yerlesim.addWidget(self.urun_bom_tablosu)
        
        # Bilgi etiketi ekle
        bilgi_etiketi = QLabel("Not: Urun agirligi hesaplamasina yalnizca 'Oluklu Mukavva' tipindeki hammaddeler dahil edilmektedir.")
        bilgi_etiketi.setStyleSheet("color: #666; font-style: italic;")
        ana_yerlesim.addWidget(bilgi_etiketi)
        
        # Tabloyu guncelle
        self.urun_bom_tablosu_guncelle()
        
        # Eksik veri kontrolü yap
        self.eksik_veri_kontrol()
    
    def urun_bom_tablosu_guncelle(self):
        """Urun BOM tablosunu gunceller"""
        try:
            urun_bom_df = self.services.data_manager.urun_bom_df
            
            self.urun_bom_tablosu.setRowCount(0)
            
            if urun_bom_df is None or urun_bom_df.empty:
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.warning("Urun BOM verisi bos")
                return
            
            # Urun BOM verilerini tabloya ekle
            for i, (_, satir) in enumerate(urun_bom_df.iterrows()):
                self.urun_bom_tablosu.insertRow(i)
                
                # Urun Kodu
                urun_kodu = str(satir["Urun Kodu"]) if "Urun Kodu" in satir and not pd.isna(satir["Urun Kodu"]) else ""
                self.urun_bom_tablosu.setItem(i, 0, QTableWidgetItem(urun_kodu))
                
                # Urun Adi
                urun_adi = str(satir["Urun Adi"]) if "Urun Adi" in satir and not pd.isna(satir["Urun Adi"]) else ""
                self.urun_bom_tablosu.setItem(i, 1, QTableWidgetItem(urun_adi))
                
                # Hammadde Kodu
                hammadde_kodu = str(satir["Hammadde Kodu"]) if "Hammadde Kodu" in satir and not pd.isna(satir["Hammadde Kodu"]) else ""
                self.urun_bom_tablosu.setItem(i, 2, QTableWidgetItem(hammadde_kodu))
                
                # Hammadde Adi
                hammadde_adi = str(satir["Hammadde Adi"]) if "Hammadde Adi" in satir and not pd.isna(satir["Hammadde Adi"]) else ""
                self.urun_bom_tablosu.setItem(i, 3, QTableWidgetItem(hammadde_adi))
                
                # Miktar
                miktar = str(satir["Miktar"]) if "Miktar" in satir and not pd.isna(satir["Miktar"]) else "0"
                self.urun_bom_tablosu.setItem(i, 4, QTableWidgetItem(miktar))
                
                # Birim
                birim = str(satir["Birim"]) if "Birim" in satir and not pd.isna(satir["Birim"]) else ""
                self.urun_bom_tablosu.setItem(i, 5, QTableWidgetItem(birim))
                
                # Hammadde Agirligi
                hammadde_agirligi = satir.get("Hammadde Agirligi", 0)
                if pd.isna(hammadde_agirligi):
                    hammadde_agirligi = 0
                hammadde_agirligi_item = QTableWidgetItem(f"{hammadde_agirligi:.2f} kg")
                hammadde_agirligi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.urun_bom_tablosu.setItem(i, 6, hammadde_agirligi_item)
                
                # Urun Agirligi
                urun_agirligi = satir.get("Urun Agirligi", 0)
                if pd.isna(urun_agirligi):
                    urun_agirligi = 0
                urun_agirligi_item = QTableWidgetItem(f"{urun_agirligi:.2f} kg")
                urun_agirligi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                # Ayni urun koduna sahip satirlarda ayni urun agirligi gosterilecek
                self.urun_bom_tablosu.setItem(i, 7, urun_agirligi_item)
                
                # Aciklama
                aciklama = str(satir["Aciklama"]) if "Aciklama" in satir and not pd.isna(satir["Aciklama"]) else ""
                self.urun_bom_tablosu.setItem(i, 8, QTableWidgetItem(aciklama))
            
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.info(f"Urun BOM tablosu guncellendi ({len(urun_bom_df)} kayit)")
            
            # Tabloyu güncelledikten sonra eksik veri kontrolü yap
            self.eksik_veri_kontrol()
                
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Urun BOM tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Urun BOM tablosu guncellenirken hata: {str(e)}")

    def urun_bom_ekle(self):
        """Yeni urun BOM ekler"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Urun BOM Ekle")
        dialog.setMinimumWidth(400)
        
        form_yerlesim = QFormLayout()
        
        # Bilgi etiketi
        bilgi_etiketi = QLabel("Bir urune birden fazla hammadde ekleyebilirsiniz. Her hammadde icin ayri kayit olusturun.")
        bilgi_etiketi.setWordWrap(True)
        form_yerlesim.addRow(bilgi_etiketi)
        
        # Urun bilgileri
        urun_kodu_combo = QComboBox()
        urun_kodu_combo.setStyleSheet("background-color: #f0f8ff; color: #000000;")  # Acik mavi arka plan, siyah yazi
        urun_adi_input = QLineEdit()
        urun_adi_input.setReadOnly(True)  # Urun adi degistirilemez
        urun_adi_input.setStyleSheet("background-color: #f0f0f0; color: #000000;")  # Gri arka plan, siyah yazi
        
        # Urun kodlarini yukle - once satislar_df'den, yoksa manuel giris
        urun_yuklendi = False
        
        # 1. Aylik satis takibinden urun kodlarini al
        if hasattr(self.services.data_manager, 'satislar_df') and not self.services.data_manager.satislar_df.empty:
            try:
                # Aylik satis takibinden urun kodlarini al
                urunler = self.services.data_manager.satislar_df[["Urun Kodu", "Urun Adi"]].drop_duplicates()
                if not urunler.empty:
                    # Bos secim ekle
                    urun_kodu_combo.addItem("", "")
                    
                    # Mevcut ürün kodlarını takip et
                    mevcut_kodlar = []
                    
                    for _, urun in urunler.iterrows():
                        urun_kodu = str(urun["Urun Kodu"]) if not pd.isna(urun["Urun Kodu"]) else ""
                        urun_adi = str(urun["Urun Adi"]) if not pd.isna(urun["Urun Adi"]) else ""
                        if urun_kodu and urun_kodu not in mevcut_kodlar:  # Bos olmayan ve tekrar etmeyen kodlari ekle
                            urun_kodu_combo.addItem(f"{urun_kodu} - {urun_adi}", {"kod": urun_kodu, "ad": urun_adi})
                            mevcut_kodlar.append(urun_kodu)  # Eklenen kodu listeye ekle
                    
                    urun_yuklendi = True
                    if hasattr(self, 'loglayici') and self.loglayici:
                        self.loglayici.info(f"Aylik satis takibinden {len(mevcut_kodlar)} urun kodu yuklendi")
            except Exception as e:
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.error(f"Satis verilerinden urun kodlari yuklenirken hata: {str(e)}")
        
        # 2. Eger satislar_df'den urun yuklenemezse, mevcut urun_bom_df'den yukle
        if hasattr(self.services.data_manager, 'urun_bom_df') and self.services.data_manager.urun_bom_df is not None and not self.services.data_manager.urun_bom_df.empty:
            try:
                urunler = self.services.data_manager.urun_bom_df[["Urun Kodu", "Urun Adi"]].drop_duplicates()
                if not urunler.empty:
                    # Bos secim ekle (eğer daha önce eklenmemişse)
                    if urun_kodu_combo.count() == 0:
                        urun_kodu_combo.addItem("", "")  # Bos secim
                    
                    # Mevcut ürün kodlarını kontrol et
                    mevcut_kodlar = []
                    for i in range(urun_kodu_combo.count()):
                        data = urun_kodu_combo.itemData(i)
                        if isinstance(data, dict) and "kod" in data:
                            mevcut_kodlar.append(data["kod"])
                        elif isinstance(data, str) and data:
                            mevcut_kodlar.append(data)
                    
                    # Sadece daha önce eklenmemiş ürünleri ekle
                    for _, urun in urunler.iterrows():
                        urun_kodu = str(urun["Urun Kodu"]) if not pd.isna(urun["Urun Kodu"]) else ""
                        urun_adi = str(urun["Urun Adi"]) if not pd.isna(urun["Urun Adi"]) else ""
                        if urun_kodu and urun_kodu not in mevcut_kodlar:  # Bos olmayan ve daha önce eklenmemiş kodlari ekle
                            urun_kodu_combo.addItem(f"{urun_kodu} - {urun_adi}", {"kod": urun_kodu, "ad": urun_adi})
                            mevcut_kodlar.append(urun_kodu)  # Eklenen kodu listeye ekle
            except Exception as e:
                self.services.logger.error(f"Urun kodlari yuklenirken hata: {str(e)}")
        
        # Hala urun yuklenemezse, manuel giris icin bir uyari goster
        if not urun_yuklendi:
            urun_kodu_combo.setEditable(True)
            urun_kodu_combo.setPlaceholderText("Urun kodu girin...")
            uyari_etiketi = QLabel("Urun verileri bulunamadi. Lutfen urun kodunu manuel girin.")
            uyari_etiketi.setStyleSheet("color: red;")
            form_yerlesim.addRow(uyari_etiketi)
        
        # Urun kodu degistiginde urun adini otomatik doldur
        def urun_kodu_degisti():
            index = urun_kodu_combo.currentIndex()
            if index > 0:  # Bos secim degil
                data = urun_kodu_combo.itemData(index)
                if data and "kod" in data and "ad" in data:
                    urun_adi_input.setText(data["ad"])
            elif urun_kodu_combo.isEditable():
                # Manuel giris durumunda urun adi da girilebilir
                urun_adi_input.setReadOnly(False)
                urun_adi_input.setStyleSheet("background-color: white; color: #000000;")
                urun_adi_input.setPlaceholderText("Urun adi girin...")
        
        urun_kodu_combo.currentIndexChanged.connect(urun_kodu_degisti)
        urun_kodu_combo.editTextChanged.connect(lambda: urun_adi_input.setReadOnly(False))
        
        # Baslangicta urun adini ayarla
        if urun_kodu_combo.count() > 0:
            urun_kodu_degisti()
        
        # Hammadde bilgileri
        hammadde_kodu_combo = QComboBox()
        hammadde_kodu_combo.setStyleSheet("background-color: #f0fff0; color: #000000;")  # Acik yesil arka plan, siyah yazi
        hammadde_adi_input = QLineEdit()
        hammadde_adi_input.setReadOnly(True)  # Hammadde adi degistirilemez
        hammadde_adi_input.setStyleSheet("background-color: #f0f0f0; color: #000000;")  # Gri arka plan, siyah yazi
        
        # Hammadde tablosundan hammadde kodlarini yukle
        hammadde_yuklendi = False
        
        if hasattr(self.services.data_manager, 'hammadde_df') and not self.services.data_manager.hammadde_df.empty:
            try:
                hammaddeler = self.services.data_manager.hammadde_df[["Hammadde Kodu", "Hammadde Adi"]].drop_duplicates()
                if not hammaddeler.empty:
                    # Bos secim ekle
                    hammadde_kodu_combo.addItem("", "")
                    for _, hammadde in hammaddeler.iterrows():
                        h_kodu = str(hammadde["Hammadde Kodu"]) if not pd.isna(hammadde["Hammadde Kodu"]) else ""
                        h_adi = str(hammadde["Hammadde Adi"]) if not pd.isna(hammadde["Hammadde Adi"]) else ""
                        if h_kodu:  # Bos olmayan kodlari ekle
                            hammadde_kodu_combo.addItem(f"{h_kodu} - {h_adi}", {"kod": h_kodu, "ad": h_adi})
                    
                    # Mevcut hammadde kodunu sec
                    for i in range(hammadde_kodu_combo.count()):
                        data = hammadde_kodu_combo.itemData(i)
                        if data and "kod" in data and data["kod"] == hammadde_kodu:
                            hammadde_kodu_combo.setCurrentIndex(i)
                            hammadde_adi_input.setText(data["ad"])
                            break
                    
                    hammadde_yuklendi = True
                    if hasattr(self, 'loglayici') and self.loglayici:
                        self.loglayici.info(f"Hammadde tablosundan {len(hammaddeler)} hammadde kodu yuklendi")
            except Exception as e:
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.error(f"Hammadde verilerinden hammadde kodlari yuklenirken hata: {str(e)}")
        
        # Hammadde yuklenemezse, manuel giris icin bir uyari goster
        if not hammadde_yuklendi:
            # Manuel giris yapilmasini engelleyelim
            hammadde_kodu_combo.setEditable(False)
            hammadde_kodu_combo.setPlaceholderText("Hammadde kodu secin...")
            uyari_etiketi = QLabel("Hammadde verileri bulunamadi. Lutfen once hammadde ekleyin.")
            uyari_etiketi.setStyleSheet("color: red;")
            form_yerlesim.addRow(uyari_etiketi)
        else:
            # Hammadde yuklendiyse de editable ozelligini kapatalim
            hammadde_kodu_combo.setEditable(False)
        
        # Hammadde kodu degistiginde hammadde adini otomatik doldur
        def hammadde_kodu_degisti():
            index = hammadde_kodu_combo.currentIndex()
            if index > 0:  # Bos secim degil
                data = hammadde_kodu_combo.itemData(index)
                if data and "kod" in data and "ad" in data:
                    hammadde_adi_input.setText(data["ad"])
            # Manuel giris kismini kaldiriyoruz
        
        hammadde_kodu_combo.currentIndexChanged.connect(hammadde_kodu_degisti)
        # editTextChanged baglantisini kaldiriyoruz cunku artik editable degil
        
        # Baslangicta hammadde adini ayarla
        if hammadde_kodu_combo.count() > 0:
            hammadde_kodu_degisti()
        
        miktar_input = QLineEdit()
        miktar_input.setPlaceholderText("Sadece sayisal deger giriniz")
        
        # Miktar alanina sadece sayisal deger girilmesini sagla
        def miktar_degisti(text):
            # Nokta ve rakam disindaki karakterleri temizle
            temiz_text = ''.join([c for c in text if c.isdigit() or c == '.'])
            # En fazla bir nokta olabilir
            if temiz_text.count('.') > 1:
                nokta_index = temiz_text.find('.')
                temiz_text = temiz_text[:nokta_index+1] + temiz_text[nokta_index+1:].replace('.', '')
            
            if temiz_text != text:
                miktar_input.setText(temiz_text)
        
        miktar_input.textChanged.connect(miktar_degisti)
        
        birim_combo = QComboBox()
        birim_combo.addItems(["Adet", "Kg", "m", "m2", "m3", "Litre"])
        birim_combo.setCurrentText("Adet")  # Varsayilan deger olarak "Adet" kullanilacak
        aciklama_input = QTextEdit()
        aciklama_input.setMaximumHeight(100)
        
        # Form yerlesimi
        form_yerlesim.addRow("Urun Kodu:", urun_kodu_combo)
        form_yerlesim.addRow("Urun Adi:", urun_adi_input)
        form_yerlesim.addRow("Hammadde Kodu:", hammadde_kodu_combo)
        form_yerlesim.addRow("Hammadde Adi:", hammadde_adi_input)
        form_yerlesim.addRow("Miktar:", miktar_input)
        form_yerlesim.addRow("Birim:", birim_combo)
        form_yerlesim.addRow("Aciklama:", aciklama_input)
        
        # Butonlar
        butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        butonlar.accepted.connect(dialog.accept)
        butonlar.rejected.connect(dialog.reject)
        
        # Yardim butonu ekle
        yardim_butonu = QPushButton("Yardim")
        yardim_butonu.clicked.connect(lambda: QMessageBox.information(dialog, "Yardim", 
            "Urun BOM (Bill of Materials) bir urunun uretiminde kullanilan hammaddelerin listesidir.\n\n"
            "Urun Kodu: Uretilen urunun benzersiz kodu\n"
            "Hammadde Kodu: Urunde kullanilan hammaddenin kodu\n"
            "Miktar: Bir urun icin gereken hammadde miktari\n"
            "Birim: Olcu birimi (Adet, Kg, m, vb.)\n\n"
            "Eger urun veya hammadde kodlari listede yoksa, manuel olarak girebilirsiniz."
        ))
        butonlar.addButton(yardim_butonu, QDialogButtonBox.ButtonRole.HelpRole)
        
        # Yerlesimi tamamla
        ana_yerlesim = QVBoxLayout()
        ana_yerlesim.addLayout(form_yerlesim)
        ana_yerlesim.addWidget(butonlar)
        dialog.setLayout(ana_yerlesim)
        
        # Dialog'u goster
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Verileri dogrula
                index = urun_kodu_combo.currentIndex()
                if index > 0:  # Bos secim degil ve combo box'tan secildi
                    data = urun_kodu_combo.itemData(index)
                    if data and "kod" in data and "ad" in data:
                        urun_kodu = data["kod"]
                        urun_adi = data["ad"]
                    else:
                        # Eger data yoksa veya beklenen formatta degilse, metin olarak al
                        urun_kodu_text = urun_kodu_combo.currentText().strip()
                        # Eger "kod - ad" formatindaysa, ayir
                        if " - " in urun_kodu_text:
                            urun_kodu = urun_kodu_text.split(" - ")[0].strip()
                        else:
                            urun_kodu = urun_kodu_text
                        urun_adi = urun_adi_input.text().strip()
                else:
                    # Manuel giris veya bos secim
                    urun_kodu_text = urun_kodu_combo.currentText().strip()
                    # Eger "kod - ad" formatindaysa, ayir
                    if " - " in urun_kodu_text:
                        urun_kodu = urun_kodu_text.split(" - ")[0].strip()
                    else:
                        urun_kodu = urun_kodu_text
                    urun_adi = urun_adi_input.text().strip()
                
                hammadde_kodu = hammadde_kodu_combo.currentText().strip()
                hammadde_adi = hammadde_adi_input.text().strip()
                
                # Hammadde kodu ve adi icin de benzer mantik uygula
                index = hammadde_kodu_combo.currentIndex()
                if index > 0:  # Bos secim degil ve combo box'tan secildi
                    data = hammadde_kodu_combo.itemData(index)
                    if data and "kod" in data and "ad" in data:
                        hammadde_kodu = data["kod"]
                        hammadde_adi = data["ad"]
                    else:
                        # Eger data yoksa veya beklenen formatta degilse, metin olarak al
                        hammadde_kodu_text = hammadde_kodu_combo.currentText().strip()
                        # Eger "kod - ad" formatindaysa, ayir
                        if " - " in hammadde_kodu_text:
                            hammadde_kodu = hammadde_kodu_text.split(" - ")[0].strip()
                            # Hammadde adini da ayir
                            hammadde_adi = hammadde_kodu_text.split(" - ")[1].strip()
                        else:
                            hammadde_kodu = hammadde_kodu_text
                            # Hammadde adi icin mevcut degeri kullan
                            hammadde_adi = hammadde_adi_input.text().strip()
                else:
                    # Bos secim yapildiginda hata mesaji goster
                    QMessageBox.warning(self, "Hata", "Lutfen bir hammadde kodu secin.")
                    return
                
                # Zorunlu alanlari kontrol et
                if not hammadde_kodu:
                    QMessageBox.warning(self, "Hata", "Hammadde kodu bos olamaz.")
                    return
                
                if not hammadde_adi:
                    # Hammadde adi bos ise, hammadde kodundan bir deger atayalim
                    if hasattr(self, 'loglayici') and self.loglayici:
                        self.loglayici.warning(f"Hammadde adi bos, hammadde kodu kullanilacak: {hammadde_kodu}")
                    hammadde_adi = f"Hammadde {hammadde_kodu}"
                
                # Log ekleyelim
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.info(f"Hammadde bilgileri: Kod={hammadde_kodu}, Ad={hammadde_adi}")
                
                # Urun kodu ve adi kontrollerini ekleyelim
                if not urun_kodu:
                    QMessageBox.warning(self, "Hata", "Urun kodu bos olamaz.")
                    return
                
                if not urun_adi:
                    QMessageBox.warning(self, "Hata", "Urun adi bos olamaz.")
                    return
                
                # Miktar kontrolu
                try:
                    miktar_text = miktar_input.text().strip()
                    if not miktar_text:
                        QMessageBox.warning(self, "Hata", "Miktar bos olamaz.")
                        return
                    miktar = float(miktar_text)
                    if miktar <= 0:
                        QMessageBox.warning(self, "Hata", "Miktar sifirdan buyuk olmalidir.")
                        return
                except ValueError:
                    QMessageBox.warning(self, "Hata", "Lutfen gecerli bir miktar girin.")
                    return
                
                birim = birim_combo.currentText()
                aciklama = aciklama_input.toPlainText().strip()
                
                # Ayni urun ve hammadde kombinasyonu var mi kontrol et
                if hasattr(self.services.data_manager, 'urun_bom_df') and self.services.data_manager.urun_bom_df is not None and not self.services.data_manager.urun_bom_df.empty:
                    mevcut_kayit = self.services.data_manager.urun_bom_df[
                        (self.services.data_manager.urun_bom_df["Urun Kodu"] == urun_kodu) & 
                        (self.services.data_manager.urun_bom_df["Hammadde Kodu"] == hammadde_kodu)
                    ]
                    
                    if not mevcut_kayit.empty:
                        yanit = QMessageBox.question(
                            self, 
                            "Kayit Mevcut", 
                            f"Bu urun icin {hammadde_kodu} kodlu hammadde zaten tanimli. Guncellenmesini ister misiniz?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        
                        if yanit == QMessageBox.StandardButton.No:
                            return
                
                # Guncellenmis urun BOM olustur
                guncellenmis_urun_bom = {
                    "Urun Kodu": urun_kodu,
                    "Urun Adi": urun_adi,
                    "Hammadde Kodu": hammadde_kodu,
                    "Hammadde Adi": hammadde_adi,
                    "Miktar": miktar,
                    "Birim": birim,
                    "Aciklama": aciklama
                }
                
                # Servise guncelle
                self.services.add_urun_bom(guncellenmis_urun_bom)  # update_urun_bom yerine add_urun_bom kullanildi
                
                # Tabloyu guncelle
                self.urun_bom_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Urun BOM basariyla eklendi.")
                
                # Ayni urune baska hammadde eklemek isteyip istemedigini sor
                yanit = QMessageBox.question(
                    self, 
                    "Baska Hammadde Ekle", 
                    f"{urun_kodu} kodlu urune baska bir hammadde daha eklemek ister misiniz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if yanit == QMessageBox.StandardButton.Yes:
                    self.urun_bom_ekle()
                
            except Exception as e:
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.error(f"Urun BOM eklenirken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Urun BOM eklenirken hata: {str(e)}")
                
    def urun_bom_duzenle(self):
        """Secili urun BOM'u duzenler"""
        secili_satir = self.urun_bom_tablosu.currentRow()
        if secili_satir < 0:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlenecek urun BOM'u secin.")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Urun BOM Duzenle")
        dialog.setMinimumWidth(400)
        
        form_yerlesim = QFormLayout()
        
        # Mevcut degerleri al
        urun_kodu = self.urun_bom_tablosu.item(secili_satir, 0).text()
        urun_adi = self.urun_bom_tablosu.item(secili_satir, 1).text()
        hammadde_kodu = self.urun_bom_tablosu.item(secili_satir, 2).text()
        hammadde_adi = self.urun_bom_tablosu.item(secili_satir, 3).text()
        miktar = self.urun_bom_tablosu.item(secili_satir, 4).text()
        birim = self.urun_bom_tablosu.item(secili_satir, 5).text()
        aciklama = self.urun_bom_tablosu.item(secili_satir, 6).text()
        
        # Urun bilgileri
        urun_kodu_input = QLineEdit(urun_kodu)
        urun_kodu_input.setReadOnly(True)  # Urun kodu degistirilemez
        urun_kodu_input.setStyleSheet("background-color: #f0f0f0; color: #000000;")  # Gri arka plan, siyah yazi
        urun_adi_input = QLineEdit(urun_adi)
        urun_adi_input.setReadOnly(True)  # Urun adi degistirilemez
        urun_adi_input.setStyleSheet("background-color: #f0f0f0; color: #000000;")  # Gri arka plan, siyah yazi
        
        # Hammadde bilgileri
        hammadde_kodu_combo = QComboBox()
        hammadde_kodu_combo.setStyleSheet("background-color: #f0fff0; color: #000000;")  # Acik yesil arka plan, siyah yazi
        hammadde_adi_input = QLineEdit()
        hammadde_adi_input.setReadOnly(True)  # Hammadde adi degistirilemez
        hammadde_adi_input.setStyleSheet("background-color: #f0f0f0; color: #000000;")  # Gri arka plan, siyah yazi
        
        # Hammadde tablosundan hammadde kodlarini yukle
        hammadde_yuklendi = False
        
        if hasattr(self.services.data_manager, 'hammadde_df') and not self.services.data_manager.hammadde_df.empty:
            try:
                hammaddeler = self.services.data_manager.hammadde_df[["Hammadde Kodu", "Hammadde Adi"]].drop_duplicates()
                if not hammaddeler.empty:
                    # Bos secim ekle
                    hammadde_kodu_combo.addItem("", "")
                    for _, hammadde in hammaddeler.iterrows():
                        h_kodu = str(hammadde["Hammadde Kodu"]) if not pd.isna(hammadde["Hammadde Kodu"]) else ""
                        h_adi = str(hammadde["Hammadde Adi"]) if not pd.isna(hammadde["Hammadde Adi"]) else ""
                        if h_kodu:  # Bos olmayan kodlari ekle
                            hammadde_kodu_combo.addItem(f"{h_kodu} - {h_adi}", {"kod": h_kodu, "ad": h_adi})
                    
                    # Mevcut hammadde kodunu sec
                    for i in range(hammadde_kodu_combo.count()):
                        data = hammadde_kodu_combo.itemData(i)
                        if data and "kod" in data and data["kod"] == hammadde_kodu:
                            hammadde_kodu_combo.setCurrentIndex(i)
                            hammadde_adi_input.setText(data["ad"])
                            break
                    
                    hammadde_yuklendi = True
                    if hasattr(self, 'loglayici') and self.loglayici:
                        self.loglayici.info(f"Hammadde tablosundan {len(hammaddeler)} hammadde kodu yuklendi")
            except Exception as e:
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.error(f"Hammadde verilerinden hammadde kodlari yuklenirken hata: {str(e)}")
        
        # Hammadde yuklenemezse, manuel giris icin bir uyari goster
        if not hammadde_yuklendi:
            # Manuel giris yapilmasini engelleyelim
            hammadde_kodu_combo.setEditable(False)
            hammadde_kodu_combo.setPlaceholderText("Hammadde kodu secin...")
            uyari_etiketi = QLabel("Hammadde verileri bulunamadi. Lutfen once hammadde ekleyin.")
            uyari_etiketi.setStyleSheet("color: red;")
            form_yerlesim.addRow(uyari_etiketi)
        else:
            # Hammadde yuklendiyse de editable ozelligini kapatalim
            hammadde_kodu_combo.setEditable(False)
        
        # Hammadde kodu degistiginde hammadde adini otomatik doldur
        def hammadde_kodu_degisti():
            index = hammadde_kodu_combo.currentIndex()
            if index > 0:  # Bos secim degil
                data = hammadde_kodu_combo.itemData(index)
                if data and "kod" in data and "ad" in data:
                    hammadde_adi_input.setText(data["ad"])
            # Manuel giris kismini kaldiriyoruz
        
        hammadde_kodu_combo.currentIndexChanged.connect(hammadde_kodu_degisti)
        # editTextChanged baglantisini kaldiriyoruz cunku artik editable degil
        
        # Baslangicta hammadde adini ayarla
        if hammadde_kodu_combo.count() > 0:
            hammadde_kodu_degisti()
        
        miktar_input = QLineEdit(miktar)
        miktar_input.setPlaceholderText("Sadece sayisal deger giriniz")
        
        # Miktar alanina sadece sayisal deger girilmesini sagla
        def miktar_degisti(text):
            # Nokta ve rakam disindaki karakterleri temizle
            temiz_text = ''.join([c for c in text if c.isdigit() or c == '.'])
            # En fazla bir nokta olabilir
            if temiz_text.count('.') > 1:
                nokta_index = temiz_text.find('.')
                temiz_text = temiz_text[:nokta_index+1] + temiz_text[nokta_index+1:].replace('.', '')
            
            if temiz_text != text:
                miktar_input.setText(temiz_text)
        
        miktar_input.textChanged.connect(miktar_degisti)
        
        birim_combo = QComboBox()
        birim_combo.addItems(["Adet", "Kg", "m", "m2", "m3", "Litre"])
        birim_combo.setCurrentText(birim if birim else "Adet")  # Eger birim bos ise varsayilan olarak "Adet" kullan
        aciklama_input = QTextEdit(aciklama)
        aciklama_input.setMaximumHeight(100)
        
        # Form yerlesimi
        form_yerlesim.addRow("Urun Kodu:", urun_kodu_input)
        form_yerlesim.addRow("Urun Adi:", urun_adi_input)
        form_yerlesim.addRow("Hammadde Kodu:", hammadde_kodu_combo)
        form_yerlesim.addRow("Hammadde Adi:", hammadde_adi_input)
        form_yerlesim.addRow("Miktar:", miktar_input)
        form_yerlesim.addRow("Birim:", birim_combo)
        form_yerlesim.addRow("Aciklama:", aciklama_input)
        
        # Butonlar
        butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        butonlar.accepted.connect(dialog.accept)
        butonlar.rejected.connect(dialog.reject)
        
        form_yerlesim.addRow(butonlar)
        dialog.setLayout(form_yerlesim)
        
        # Dialog'u goster
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Verileri dogrula
                urun_kodu = urun_kodu_input.text()
                urun_adi = urun_adi_input.text()
                hammadde_kodu = hammadde_kodu_combo.currentText()
                hammadde_adi = hammadde_adi_input.text()
                
                # Hammadde kodu ve adi icin de benzer mantik uygula
                index = hammadde_kodu_combo.currentIndex()
                if index > 0:  # Bos secim degil ve combo box'tan secildi
                    data = hammadde_kodu_combo.itemData(index)
                    if data and "kod" in data and "ad" in data:
                        hammadde_kodu = data["kod"]
                        hammadde_adi = data["ad"]
                    else:
                        # Eger data yoksa veya beklenen formatta degilse, metin olarak al
                        hammadde_kodu_text = hammadde_kodu_combo.currentText().strip()
                        # Eger "kod - ad" formatindaysa, ayir
                        if " - " in hammadde_kodu_text:
                            hammadde_kodu = hammadde_kodu_text.split(" - ")[0].strip()
                        else:
                            hammadde_kodu = hammadde_kodu_text
                        # Hammadde adi icin mevcut degeri kullan
                        hammadde_adi = hammadde_adi_input.text().strip()
                else:
                    # Manuel giris veya bos secim
                    hammadde_kodu_text = hammadde_kodu_combo.currentText().strip()
                    # Eger "kod - ad" formatindaysa, ayir
                    if " - " in hammadde_kodu_text:
                        hammadde_kodu = hammadde_kodu_text.split(" - ")[0].strip()
                        # Hammadde adini da ayir
                        hammadde_adi = hammadde_kodu_text.split(" - ")[1].strip()
                    else:
                        hammadde_kodu = hammadde_kodu_text
                        # Hammadde adi icin mevcut degeri kullan
                        hammadde_adi = hammadde_adi_input.text().strip()
                
                try:
                    miktar = float(miktar_input.text())
                except ValueError:
                    QMessageBox.warning(self, "Hata", "Lutfen gecerli bir miktar girin.")
                    return
                birim = birim_combo.currentText()
                aciklama = aciklama_input.toPlainText()
                
                # Guncellenmis urun BOM olustur
                guncellenmis_urun_bom = {
                    "Urun Kodu": urun_kodu,
                    "Urun Adi": urun_adi,
                    "Hammadde Kodu": hammadde_kodu,
                    "Hammadde Adi": hammadde_adi,
                    "Miktar": miktar,
                    "Birim": birim,
                    "Aciklama": aciklama
                }
                
                # Servise guncelle
                self.services.update_urun_bom(secili_satir, guncellenmis_urun_bom)
                
                # Tabloyu guncelle
                self.urun_bom_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Urun BOM basariyla guncellendi.")
                
            except Exception as e:
                if hasattr(self, 'loglayici') and self.loglayici:
                    self.loglayici.error(f"Urun BOM guncellenirken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Urun BOM guncellenirken hata: {str(e)}")
                
    def urun_bom_sil(self):
        """Secili urun BOM'u siler"""
        try:
            secili_satir = self.urun_bom_tablosu.currentRow()
            if secili_satir < 0:
                QMessageBox.warning(self, "Uyari", "Lutfen silinecek urun BOM'u secin.")
                return
                
            urun_kodu = self.urun_bom_tablosu.item(secili_satir, 0).text()
            hammadde_kodu = self.urun_bom_tablosu.item(secili_satir, 2).text()
            
            yanit = QMessageBox.question(self, "Urun BOM Sil", 
                f"{urun_kodu} kodlu urunun {hammadde_kodu} kodlu hammaddesini silmek istediginize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
            if yanit == QMessageBox.StandardButton.Yes:
                self.services.delete_urun_bom(urun_kodu, hammadde_kodu)
                self.urun_bom_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Urun BOM basariyla silindi.")
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Urun BOM silinirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Urun BOM silinirken hata: {str(e)}")

    def urun_bazli_bom_goster(self):
        """Urun bazli BOM goster"""
        try:
            if not hasattr(self.services.data_manager, 'urun_bom_df') or self.services.data_manager.urun_bom_df is None or self.services.data_manager.urun_bom_df.empty:
                QMessageBox.warning(self, "Uyari", "Gosterilecek BOM verisi bulunamadi.")
                return
                
            # Urun koduna gore grupla
            df = self.services.data_manager.urun_bom_df.copy()
            
            # Hammadde bilgilerini ekle
            if hasattr(self.services.data_manager, 'hammadde_df') and not self.services.data_manager.hammadde_df.empty:
                df = pd.merge(
                    df,
                    self.services.data_manager.hammadde_df[["Hammadde Kodu", "Hammadde Adi", "Hammadde Tipi", "Birim Maliyet"]],
                    on="Hammadde Kodu",
                    how="left"
                )
            
            # Urun secimi icin dialog olustur
            dialog = QDialog(self)
            dialog.setWindowTitle("Urun Bazli BOM Goster")
            dialog.setMinimumWidth(600)
            dialog.setMinimumHeight(500)
            
            layout = QVBoxLayout()
            
            # Urun secimi
            urun_secim_layout = QHBoxLayout()
            urun_secim_label = QLabel("Urun Sec:")
            urun_secim_layout.addWidget(urun_secim_label)
            
            urun_combo = QComboBox()
            urunler = df["Urun Kodu"].unique()
            for urun in urunler:
                urun_adi = df[df["Urun Kodu"] == urun]["Urun Adi"].iloc[0]
                urun_combo.addItem(f"{urun} - {urun_adi}", urun)
            
            urun_secim_layout.addWidget(urun_combo)
            layout.addLayout(urun_secim_layout)
            
            # BOM tablosu
            bom_tablo = QTableWidget()
            bom_tablo.setColumnCount(5)
            bom_tablo.setHorizontalHeaderLabels([
                "Hammadde Kodu", "Hammadde Adi", "Miktar", "Birim", "Birim Maliyet"
            ])
            bom_tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            layout.addWidget(bom_tablo)
            
            # Toplam maliyet gosterimi
            toplam_layout = QHBoxLayout()
            toplam_label = QLabel("Toplam Maliyet:")
            toplam_layout.addWidget(toplam_label)
            
            toplam_deger = QLabel("0.00 TL")
            toplam_deger.setStyleSheet("font-weight: bold; color: blue;")
            toplam_layout.addWidget(toplam_deger)
            
            layout.addLayout(toplam_layout)
            
            # Butonlar
            butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            butonlar.rejected.connect(dialog.reject)
            layout.addWidget(butonlar)
            
            dialog.setLayout(layout)
            
            # Urun degistiginde tabloyu guncelle
            def urun_degisti():
                secili_urun = urun_combo.currentData()
                if not secili_urun:
                    return
                    
                # Secili urune ait hammaddeleri filtrele
                urun_df = df[df["Urun Kodu"] == secili_urun]
                
                # Tabloyu doldur
                bom_tablo.setRowCount(len(urun_df))
                
                toplam_maliyet = 0.0
                
                for i, (_, satir) in enumerate(urun_df.iterrows()):
                    bom_tablo.setItem(i, 0, QTableWidgetItem(str(satir["Hammadde Kodu"])))
                    bom_tablo.setItem(i, 1, QTableWidgetItem(str(satir["Hammadde Adi"])))
                    bom_tablo.setItem(i, 2, QTableWidgetItem(str(satir["Miktar"])))
                    bom_tablo.setItem(i, 3, QTableWidgetItem(str(satir["Birim"])))
                    
                    birim_maliyet = satir.get("Birim Maliyet", 0)
                    if pd.notna(birim_maliyet):
                        bom_tablo.setItem(i, 4, QTableWidgetItem(f"{birim_maliyet:.2f}"))
                        # Toplam maliyeti hesapla
                        miktar = float(satir["Miktar"])
                        toplam_maliyet += miktar * birim_maliyet
                    else:
                        bom_tablo.setItem(i, 4, QTableWidgetItem("N/A"))
                
                # Toplam maliyeti goster
                toplam_deger.setText(f"{toplam_maliyet:.2f} TL")
                
                # Baslik guncelle
                urun_adi = urun_df["Urun Adi"].iloc[0]
                dialog.setWindowTitle(f"Urun BOM: {secili_urun} - {urun_adi} ({len(urun_df)} hammadde)")
            
            urun_combo.currentIndexChanged.connect(urun_degisti)
            
            # Ilk urunu sec
            if urun_combo.count() > 0:
                urun_combo.setCurrentIndex(0)
                urun_degisti()
            
            dialog.exec()
            
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Urun bazli BOM gosterilirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Urun bazli BOM gosterilirken hata: {str(e)}")

    def tum_agirliklari_hesapla(self):
        """Tum urunlerin agirliklarini hesaplar"""
        try:
            # Ilerleme dialogu olustur
            ilerleme_dialog = QProgressDialog("Urun agirliklari hesaplaniyor...", "Iptal", 0, 100, self)
            ilerleme_dialog.setWindowTitle("Agirlik Hesaplama")
            ilerleme_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            ilerleme_dialog.setMinimumDuration(0)
            ilerleme_dialog.setValue(10)
            
            # Tum urun agirliklarini guncelle
            self.services.data_manager.tum_urun_agirliklarini_guncelle()
            
            ilerleme_dialog.setValue(90)
            
            # Tabloyu guncelle
            self.urun_bom_tablosu_guncelle()
            
            ilerleme_dialog.setValue(100)
            
            QMessageBox.information(self, "Bilgi", "Tum urun agirliklari hesaplandi.\n\nNot: Hesaplamaya yalnizca 'Oluklu Mukavva' tipindeki hammaddeler dahil edilmistir.")
            
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.info("Tum urun agirliklari hesaplandi (sadece oluklu mukavva hammaddeler)")
                
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Agirlik hesaplanirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Agirlik hesaplanirken hata: {str(e)}")

    def eksik_veri_kontrol(self):
        """Eksik verileri kontrol eder ve uyarı butonunu günceller"""
        try:
            # Uyarı listesi
            self.eksik_veri_uyarilari = []
            
            # 1. BOM'u olmayan ürünleri kontrol et
            if hasattr(self.services.data_manager, 'satislar_df') and self.services.data_manager.satislar_df is not None and not self.services.data_manager.satislar_df.empty:
                # Satışlardaki ürün kodlarını al
                satis_urunleri = set()
                if 'Urun Kodu' in self.services.data_manager.satislar_df.columns:
                    satis_urunleri = set(self.services.data_manager.satislar_df['Urun Kodu'].dropna().unique())
                
                # BOM'daki ürün kodlarını al
                bom_urunleri = set()
                if hasattr(self.services.data_manager, 'urun_bom_df') and self.services.data_manager.urun_bom_df is not None and not self.services.data_manager.urun_bom_df.empty:
                    if 'Urun Kodu' in self.services.data_manager.urun_bom_df.columns:
                        bom_urunleri = set(self.services.data_manager.urun_bom_df['Urun Kodu'].dropna().unique())
                
                # BOM'u olmayan ürünleri bul
                bomu_olmayan_urunler = satis_urunleri - bom_urunleri
                
                if bomu_olmayan_urunler:
                    self.eksik_veri_uyarilari.append({
                        "tip": "BOM Eksik",
                        "mesaj": f"{len(bomu_olmayan_urunler)} ürünün BOM kaydı bulunmuyor",
                        "detay": f"BOM kaydı olmayan ürün kodları: {', '.join(sorted(list(bomu_olmayan_urunler)))}"
                    })
            
            # 2. Hammaddesi olmayan BOM kayıtlarını kontrol et
            if hasattr(self.services.data_manager, 'urun_bom_df') and self.services.data_manager.urun_bom_df is not None and not self.services.data_manager.urun_bom_df.empty:
                if 'Hammadde Kodu' in self.services.data_manager.urun_bom_df.columns:
                    bom_hammaddeleri = set(self.services.data_manager.urun_bom_df['Hammadde Kodu'].dropna().unique())
                    
                    # Hammadde tablosundaki kodları al
                    hammadde_kodlari = set()
                    if hasattr(self.services.data_manager, 'hammadde_df') and self.services.data_manager.hammadde_df is not None and not self.services.data_manager.hammadde_df.empty:
                        if 'Hammadde Kodu' in self.services.data_manager.hammadde_df.columns:
                            hammadde_kodlari = set(self.services.data_manager.hammadde_df['Hammadde Kodu'].dropna().unique())
                    
                    # Tanımlı olmayan hammaddeleri bul
                    tanimsiz_hammaddeler = bom_hammaddeleri - hammadde_kodlari
                    
                    if tanimsiz_hammaddeler:
                        self.eksik_veri_uyarilari.append({
                            "tip": "Hammadde Eksik",
                            "mesaj": f"{len(tanimsiz_hammaddeler)} hammadde tanımı eksik",
                            "detay": f"Tanımı eksik hammadde kodları: {', '.join(sorted(list(tanimsiz_hammaddeler)))}"
                        })
            
            # Uyarı butonu durumunu güncelle
            if self.eksik_veri_uyarilari:
                # Uyarı varsa butonu aktifleştir ve yanıp sönmeyi başlat
                self.uyari_butonu.setStyleSheet("background-color: #ffcc00; color: #000; font-weight: bold; border-radius: 12px; min-width: 24px; min-height: 24px;")
                self.uyari_butonu.setText(f"{len(self.eksik_veri_uyarilari)}")
                self.uyari_butonu.setToolTip(f"{len(self.eksik_veri_uyarilari)} adet eksik veri uyarısı")
                
                # Yanıp sönme animasyonunu başlat
                if not self.uyari_timer.isActive():
                    self.uyari_aktif = True
                    self.uyari_timer.start(500)  # 500ms aralıklarla yanıp sönsün
            else:
                # Uyarı yoksa butonu pasifleştir ve yanıp sönmeyi durdur
                self.uyari_butonu.setStyleSheet("background-color: #f0f0f0; color: #666; border-radius: 12px; min-width: 24px; min-height: 24px;")
                self.uyari_butonu.setText("!")
                self.uyari_butonu.setToolTip("Eksik veri uyarısı yok")
                
                # Yanıp sönme animasyonunu durdur
                if self.uyari_timer.isActive():
                    self.uyari_timer.stop()
                    self.uyari_aktif = False
            
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Eksik veri kontrolü yapılırken hata: {str(e)}")
    
    def uyari_butonu_animasyon(self):
        """Uyarı butonunun yanıp sönme animasyonu"""
        if not self.uyari_aktif:
            return
            
        self.uyari_durum = not self.uyari_durum
        
        if self.uyari_durum:
            # Parlak renk
            self.uyari_butonu.setStyleSheet("background-color: #ff9900; color: #000; font-weight: bold; border-radius: 12px; min-width: 24px; min-height: 24px;")
        else:
            # Normal renk
            self.uyari_butonu.setStyleSheet("background-color: #ffcc00; color: #000; font-weight: bold; border-radius: 12px; min-width: 24px; min-height: 24px;")
    
    def eksik_veri_uyarisi_goster(self):
        """Eksik veri uyarılarını gösteren popup"""
        if not hasattr(self, 'eksik_veri_uyarilari'):
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Eksik Veri Uyarıları")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Başlık
        baslik = QLabel("Eksik Veri Uyarıları")
        baslik.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        layout.addWidget(baslik)
        
        # Açıklama
        aciklama = QLabel("Aşağıdaki eksik veriler tespit edildi. Veri bütünlüğü için bu eksiklikleri tamamlamanız önerilir.")
        aciklama.setWordWrap(True)
        layout.addWidget(aciklama)
        
        # Uyarı listesi
        if self.eksik_veri_uyarilari:
            for i, uyari in enumerate(self.eksik_veri_uyarilari):
                uyari_grubu = QGroupBox(f"{i+1}. {uyari['tip']}")
                uyari_grubu.setStyleSheet("QGroupBox { font-weight: bold; }")
                uyari_layout = QVBoxLayout()
                
                mesaj = QLabel(uyari['mesaj'])
                mesaj.setStyleSheet("font-weight: bold; color: #cc3300;")
                uyari_layout.addWidget(mesaj)
                
                detay = QTextEdit()
                detay.setReadOnly(True)
                detay.setPlainText(uyari['detay'])
                detay.setMaximumHeight(100)
                uyari_layout.addWidget(detay)
                
                uyari_grubu.setLayout(uyari_layout)
                layout.addWidget(uyari_grubu)
        else:
            bilgi = QLabel("Şu anda eksik veri uyarısı bulunmuyor.")
            bilgi.setStyleSheet("color: green; font-weight: bold;")
            layout.addWidget(bilgi)
        
        # Butonlar
        butonlar = QDialogButtonBox()
        
        kapat_butonu = butonlar.addButton("Kapat", QDialogButtonBox.ButtonRole.RejectRole)
        kapat_butonu.clicked.connect(dialog.reject)
        
        if self.eksik_veri_uyarilari:
            # BOM'u olmayan ürünler için BOM ekle butonu
            bom_ekle_butonu = butonlar.addButton("BOM Ekle", QDialogButtonBox.ButtonRole.ActionRole)
            bom_ekle_butonu.clicked.connect(lambda: self.urun_bom_ekle())
            bom_ekle_butonu.clicked.connect(dialog.accept)
            
            # Hammadde ekle butonu
            hammadde_ekle_butonu = butonlar.addButton("Hammadde Ekle", QDialogButtonBox.ButtonRole.ActionRole)
            hammadde_ekle_butonu.clicked.connect(lambda: self.hammadde_ekle())
            hammadde_ekle_butonu.clicked.connect(dialog.accept)
        
        layout.addWidget(butonlar)
        
        dialog.setLayout(layout)
        dialog.exec()
