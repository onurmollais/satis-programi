from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QLineEdit, QFormLayout, QComboBox, QTextEdit,
                             QDialog, QMessageBox, QGroupBox, QAbstractItemView,
                             QDialogButtonBox, QDateEdit, QProgressBar, QLabel,
                             QFileDialog, QListWidget)
from PyQt6.QtCore import QDate, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QIcon, QAction
import pandas as pd
import re
from events import Event, EventManager, EVENT_DATA_UPDATED, EVENT_UI_UPDATED, EVENT_ERROR_OCCURRED
from veri_yukleme_worker import VeriYuklemeWorker
from satis_worker import SatisEklemeWorker, ZiyaretEklemeWorker, SatisSilmeWorker, ZiyaretSilmeWorker
from ui_interface import UIInterface

class AnaPencere(QMainWindow, UIInterface):
    data_updated_signal = pyqtSignal(Event)
   
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Event aboneligi
        if hasattr(self, 'event_manager') and self.event_manager:
            self.event_manager.subscribe(EVENT_DATA_UPDATED, self.tum_sekmeleri_guncelle)
            self.event_manager.subscribe(EVENT_UI_UPDATED, self._on_ui_updated)
    
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
        
        # Gorsellestirici'den gelen grafik yenileme isteklerini isle
        if event.data.get("source") == "gorsellestirici" and event.data.get("action") == "refresh_charts":
            if hasattr(self, 'gosterge_paneli_guncelle'):
                self.gosterge_paneli_guncelle()
    
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
    
    def satisci_yonetimi_olustur(self):
        sekme = QWidget()
        self.sekme_widget.addTab(sekme, "Satisci Yonetimi")
        
        ana_yerlesim = QVBoxLayout()
        sekme.setLayout(ana_yerlesim)

        # Ust kisim - Butonlar
        buton_grup = QGroupBox("Islemler")
        buton_yerlesim = QHBoxLayout()
        
        satisci_ekle_butonu = QPushButton("Yeni Satisci Ekle")
        satisci_ekle_butonu.clicked.connect(self.satisci_ekle)
        buton_yerlesim.addWidget(satisci_ekle_butonu)
        
        self.satisci_duzenle_butonu = QPushButton("Satisci Duzenle")
        self.satisci_duzenle_butonu.clicked.connect(self.satisci_duzenle)
        buton_yerlesim.addWidget(self.satisci_duzenle_butonu)
        
        satisci_sil_butonu = QPushButton("Satisci Sil")
        satisci_sil_butonu.clicked.connect(self.satisci_sil)
        buton_yerlesim.addWidget(satisci_sil_butonu)
        
        buton_grup.setLayout(buton_yerlesim)
        ana_yerlesim.addWidget(buton_grup)

        # Satisci tablosu
        self.satisci_tablosu = QTableWidget()
        self.satisci_tablosu.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.satisci_tablosu.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.satisci_tablosu.setColumnCount(5)
        self.satisci_tablosu.setHorizontalHeaderLabels([
            "Isim", "Bolge", "E-posta", "Telefon", "Durum"
        ])
        self.satisci_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ana_yerlesim.addWidget(self.satisci_tablosu)
        
        # Tabloyu guncelle
        self.satisci_tablosu_guncelle()

    def satisci_tablosu_guncelle(self):
        """Satisci tablosunu gunceller"""
        try:
            satiscilar_df = self.services.data_manager.satiscilar_df
            
            self.satisci_tablosu.setRowCount(0)
            
            if satiscilar_df is None or satiscilar_df.empty:
                return
                
            self.satisci_tablosu.setRowCount(len(satiscilar_df))
            
            for i, row in satiscilar_df.iterrows():
                self.satisci_tablosu.setItem(i, 0, QTableWidgetItem(str(row.get("Isim", ""))))
                self.satisci_tablosu.setItem(i, 1, QTableWidgetItem(str(row.get("Bolge", ""))))
                self.satisci_tablosu.setItem(i, 2, QTableWidgetItem(str(row.get("E-posta", ""))))
                self.satisci_tablosu.setItem(i, 3, QTableWidgetItem(str(row.get("Telefon", ""))))
                self.satisci_tablosu.setItem(i, 4, QTableWidgetItem(str(row.get("Durum", ""))))
        except Exception as e:
            self.loglayici.error(f"Satisci tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Satisci tablosu guncellenirken hata: {str(e)}")

    def satisci_ekle(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Satisci Ekle")
        yerlesim = QFormLayout()

        isim_giris = QLineEdit()
        bolge_giris = QLineEdit()
        eposta_giris = QLineEdit()
        telefon_giris = QLineEdit()
        durum_giris = QComboBox()
        durum_giris.addItems(["Aktif", "Pasif"])

        yerlesim.addRow("Isim:", isim_giris)
        yerlesim.addRow("Bolge:", bolge_giris)
        yerlesim.addRow("E-posta:", eposta_giris)
        yerlesim.addRow("Telefon:", telefon_giris)
        yerlesim.addRow("Durum:", durum_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def satisci_kaydet():
            try:
                yeni_satisci = {
                    "Isim": isim_giris.text().strip(),
                    "Bolge": bolge_giris.text().strip(),
                    "E-posta": eposta_giris.text().strip(),
                    "Telefon": telefon_giris.text().strip(),
                    "Durum": durum_giris.currentText()
                }
                if not yeni_satisci["Isim"]:
                    raise ValueError("Satisci adi bos olamaz.")
                self.services.add_sales_rep(yeni_satisci)
                self.satisci_tablosu_guncelle()
                QMessageBox.information(self, "Basarili", f"Satisci '{yeni_satisci['Isim']}' eklendi.")
                dialog.accept()
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
                self.loglayici.error(f"Satisci ekleme hatasi: {str(ve)}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Satisci eklenirken hata: {str(e)}")
                self.loglayici.error(f"Satisci ekleme hatasi: {str(e)}")

        kaydet_butonu.clicked.connect(satisci_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def satisci_duzenle(self):
        """Secili satisciyi duzenler"""
        secili_satirlar = self.satisci_tablosu.selectedIndexes()
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek icin bir satisci secin.")
            return
            
        secili_satir = secili_satirlar[0].row()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Satisci Duzenle")
        dialog.setMinimumWidth(400)
        
        form_yerlesim = QFormLayout(dialog)
        
        isim_giris = QLineEdit(self.satisci_tablosu.item(secili_satir, 0).text())
        bolge_giris = QLineEdit(self.satisci_tablosu.item(secili_satir, 1).text())
        eposta_giris = QLineEdit(self.satisci_tablosu.item(secili_satir, 2).text())
        telefon_giris = QLineEdit(self.satisci_tablosu.item(secili_satir, 3).text())
        
        durum_giris = QComboBox()
        durum_giris.addItems(["Aktif", "Pasif"])
        durum_giris.setCurrentText(self.satisci_tablosu.item(secili_satir, 4).text())
        
        form_yerlesim.addRow("Isim:", isim_giris)
        form_yerlesim.addRow("Bolge:", bolge_giris)
        form_yerlesim.addRow("E-posta:", eposta_giris)
        form_yerlesim.addRow("Telefon:", telefon_giris)
        form_yerlesim.addRow("Durum:", durum_giris)
        
        buton_kutusu = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form_yerlesim.addRow(buton_kutusu)
        
        buton_kutusu.accepted.connect(dialog.accept)
        buton_kutusu.rejected.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                guncellenmis_satisci = {
                    "Isim": isim_giris.text().strip(),
                    "Bolge": bolge_giris.text().strip(),
                    "E-posta": eposta_giris.text().strip(),
                    "Telefon": telefon_giris.text().strip(),
                    "Durum": durum_giris.currentText()
                }
                
                if not guncellenmis_satisci["Isim"]:
                    raise ValueError("Satisci adi bos olamaz.")
                
                # Satisci ismi degistiyse kontrol et
                eski_isim = self.satisci_tablosu.item(secili_satir, 0).text()
                if guncellenmis_satisci["Isim"] != eski_isim:
                    # Ayni isimde baska bir satisci var mi kontrol et
                    if not self.services.data_manager.satiscilar_df.empty and guncellenmis_satisci["Isim"] in self.services.data_manager.satiscilar_df["Isim"].values:
                        raise ValueError(f"'{guncellenmis_satisci['Isim']}' isimli bir satisci zaten mevcut.")
                
                # Satisciyi guncelle
                self.services.update_sales_rep(secili_satir, guncellenmis_satisci)
                self.satisci_tablosu_guncelle()
                QMessageBox.information(self, "Bilgi", "Satisci basariyla guncellendi.")
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
                self.loglayici.error(f"Satisci guncelleme hatasi: {str(ve)}")
            except Exception as e:
                self.loglayici.error(f"Satisci guncellenirken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Satisci guncellenirken hata: {str(e)}")

    def satisci_sil(self):
        selected_items = self.satisci_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            satisci_isim = self.satisci_tablosu.item(row, 0).text()
            self.services.delete_sales_rep(satisci_isim)
            self.satisci_tablosu.removeRow(row)
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek istediginiz satisciyi secin.")
    
    def tum_sekmeleri_guncelle(self, event: Event = None) -> None:
        """Tum sekmeleri gunceller"""
        if not hasattr(self, 'is_initialized') or not self.is_initialized:
            return
            
        try:
            # Satis modulu ile ilgili tablolari guncelle
            if hasattr(self, 'satisci_tablosu_guncelle'):
                self.satisci_tablosu_guncelle()
            
            if hasattr(self, 'satis_hedefleri_tablosu_guncelle'):
                self.satis_hedefleri_tablosu_guncelle()
                
            if hasattr(self, 'pipeline_tablosu_guncelle'):
                self.pipeline_tablosu_guncelle()
                
            if hasattr(self, 'musteri_tablosu_guncelle'):
                self.musteri_tablosu_guncelle()
                
            if hasattr(self, 'satis_tablosu_guncelle'):
                self.satis_tablosu_guncelle()
                
            if hasattr(self, 'ziyaret_tablosu_guncelle'):
                self.ziyaret_tablosu_guncelle()
            
            # Gosterge paneli guncelleme
            if hasattr(self, 'gosterge_paneli_guncelle'):
                self.gosterge_paneli_guncelle()
            
            # Status bar guncelleme
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage("Tum veriler guncellendi")
                
        except Exception as e:
            if hasattr(self, 'loglayici') and self.loglayici:
                self.loglayici.error(f"Tablolar guncellenirken hata: {str(e)}")
            
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"Guncelleme hatasi: {str(e)}")

    def satis_hedefleri_olustur(self):
        sekme = QWidget()
        self.sekme_widget.addTab(sekme, "Satis Hedefleri")
    
        yerlesim = QVBoxLayout()
        sekme.setLayout(yerlesim)

        # Butonlari yukariya tasi ve yatay olarak esitle
        buton_yerlesim = QHBoxLayout()
        
        hedef_ekle_butonu = QPushButton("Yeni Hedef Ekle")
        hedef_ekle_butonu.clicked.connect(self.satis_hedefi_ekle)
        buton_yerlesim.addWidget(hedef_ekle_butonu)
        
        hedef_duzenle_butonu = QPushButton("Hedef Duzenle")
        hedef_duzenle_butonu.clicked.connect(self.satis_hedefi_duzenle)
        buton_yerlesim.addWidget(hedef_duzenle_butonu)
        
        hedef_sil_butonu = QPushButton("Hedef Sil")
        hedef_sil_butonu.clicked.connect(self.satis_hedefi_sil)
        buton_yerlesim.addWidget(hedef_sil_butonu)
        
        yerlesim.addLayout(buton_yerlesim)

        # Hedef tablosu
        self.hedefler_tablosu = QTableWidget()
        self.hedefler_tablosu.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.hedefler_tablosu.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.hedefler_tablosu.setColumnCount(3)
        self.hedefler_tablosu.setHorizontalHeaderLabels([
            "Ay", "Hedef", "Para Birimi"
        ])
        self.hedefler_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        yerlesim.addWidget(self.hedefler_tablosu)

    def satis_hedefi_duzenle(self):
        selected_items = self.hedefler_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            dialog = QDialog(self)
            dialog.setWindowTitle("Hedef Duzenle")
            yerlesim = QFormLayout()

            mevcut_ay = self.hedefler_tablosu.item(row, 0).text()  # "03-2025"
            ay, yil = mevcut_ay.split("-") if "-" in mevcut_ay else (mevcut_ay, "2025")
            ay_secim = QComboBox()
            ay_secim.addItems([f"{i:02d}" for i in range(1, 13)])
            ay_secim.setCurrentText(ay)
            yil_secim = QComboBox()
            yillar = [str(y) for y in range(2020, 2031)]
            yil_secim.addItems(yillar)
            yil_secim.setCurrentText(yil)
            hedef_giris = QLineEdit(self.hedefler_tablosu.item(row, 1).text())
            para_birimi_giris = QComboBox()
            para_birimi_giris.addItems(["TL", "USD", "EUR"])
            para_birimi_giris.setCurrentText(self.hedefler_tablosu.item(row, 2).text())

            yerlesim.addRow("Ay (MM):", ay_secim)
            yerlesim.addRow("Yil (YYYY):", yil_secim)
            yerlesim.addRow("Hedef:", hedef_giris)
            yerlesim.addRow("Para Birimi:", para_birimi_giris)

            butonlar = QHBoxLayout()
            kaydet_butonu = QPushButton("Kaydet")
            iptal_butonu = QPushButton("Iptal")
            butonlar.addWidget(kaydet_butonu)
            butonlar.addWidget(iptal_butonu)
            yerlesim.addRow(butonlar)
            dialog.setLayout(yerlesim)

            def hedef_guncelle():
                try:
                    ay_str = f"{ay_secim.currentText()}-{yil_secim.currentText()}"  # "03-2025" (MM-YYYY formati)
                    self.loglayici.debug(f"Hedef guncelleme - Gonderilen Ay degeri: '{ay_str}' (MM-YYYY formati)")
                    hedef = float(hedef_giris.text().replace(',', '.'))
                    if hedef <= 0:
                        raise ValueError("Hedef pozitif bir sayi olmali.")
                    yeni_hedef = {
                        "Ay": ay_str,
                        "Hedef": hedef,
                        "Para Birimi": para_birimi_giris.currentText()
                    }
                    self.services.update_sales_target(row, yeni_hedef)  # Degistirildi
                    self.satis_hedefleri_tablosu_guncelle()
                    # Gosterge panelini guncelle
                    if hasattr(self, 'gosterge_paneli_guncelle'):
                        self.gosterge_paneli_guncelle()
                    # Olay yayinla
                    self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_duzenle"}))
                    dialog.accept()
                    self.loglayici.info(f"Hedef guncellendi: {ay_str} - {hedef} {yeni_hedef['Para Birimi']}")
                except ValueError as ve:
                    QMessageBox.warning(self, "Uyari", str(ve))
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Hedef guncellenirken hata: {str(e)}")
                    self.loglayici.error(f"Hedef guncelleme hatasi: {str(e)}")

            kaydet_butonu.clicked.connect(hedef_guncelle)
            iptal_butonu.clicked.connect(dialog.reject)
            dialog.exec()
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek istediginiz hedefi secin.")

    def satis_hedefleri_tablosu_guncelle(self):
        if self.services.data_manager.aylik_hedefler_df is not None and not self.services.data_manager.aylik_hedefler_df.empty:
            df = self.services.data_manager.aylik_hedefler_df.copy()
            
            # Ay formatini kontrol et ve logla
            if 'Ay' in df.columns:
                self.loglayici.debug(f"Hedefler tablosu guncelleniyor. Ay sutunu degerleri: {df['Ay'].tolist()}")
                
                # Ay degerlerini string'e donustur
                df['Ay'] = df['Ay'].astype(str)
                
                # Ay formatini kontrol et
                for i, ay in enumerate(df['Ay']):
                    if '-' not in ay:
                        self.loglayici.warning(f"Hedefler tablosunda gecersiz ay formati: {ay}")
                        try:
                            # Pandas'in otomatik tarih tanima ozelligini kullan
                            ay_obj = pd.to_datetime(ay)
                            yeni_ay = f"{ay_obj.strftime('%m')}-{ay_obj.strftime('%Y')}"
                            df.at[i, 'Ay'] = yeni_ay
                            self.loglayici.info(f"Ay formati duzeltildi: {ay} -> {yeni_ay}")
                        except:
                            self.loglayici.error(f"Ay formati duzeltilemiyor: {ay}")
            
            self.hedefler_tablosu.setColumnCount(len(df.columns))
            self.hedefler_tablosu.setRowCount(len(df))
            self.hedefler_tablosu.setHorizontalHeaderLabels(df.columns)
            for i in range(len(df)):
                for j in range(len(df.columns)):
                    self.hedefler_tablosu.setItem(i, j, QTableWidgetItem(str(df.iloc[i, j])))
            self.hedefler_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            self.hedefler_tablosu.clear()
            self.hedefler_tablosu.setRowCount(0)
            self.hedefler_tablosu.setColumnCount(0)

    def satis_hedefi_sil(self):
        selected_items = self.hedefler_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            ay = self.hedefler_tablosu.item(row, 0).text()
            self.services.delete_sales_target(ay)  # Degistirildi
            self.satis_hedefleri_tablosu_guncelle()
            # Gosterge panelini guncelle
            if hasattr(self, 'gosterge_paneli_guncelle'):
                self.gosterge_paneli_guncelle()
            # Olay yayinla
            self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_sil"}))
            QMessageBox.information(self, "Bilgi", f"{ay} ayi icin hedef silindi.")
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek istediginiz hedefi secin.")


    def pipeline_yonetimi_olustur(self):
        sekme = QWidget()
        self.sekme_widget.addTab(sekme, "Pipeline Yonetimi")
        
        ana_yerlesim = QVBoxLayout()
        sekme.setLayout(ana_yerlesim)

        # Ust kisim - Butonlar
        buton_yerlesim = QHBoxLayout()
        
        firsat_ekle_butonu = QPushButton("Pipeline Firsati Ekle")
        firsat_ekle_butonu.clicked.connect(self.pipeline_firsati_ekle)
        buton_yerlesim.addWidget(firsat_ekle_butonu)
        
        firsat_duzenle_butonu = QPushButton("Pipeline Firsati Duzenle")
        firsat_duzenle_butonu.clicked.connect(self.pipeline_firsati_duzenle)
        buton_yerlesim.addWidget(firsat_duzenle_butonu)
        
        firsat_sil_butonu = QPushButton("Pipeline Firsati Sil")
        firsat_sil_butonu.clicked.connect(self.pipeline_firsati_sil)
        buton_yerlesim.addWidget(firsat_sil_butonu)
        
        ana_yerlesim.addLayout(buton_yerlesim)
        
        # Arama ve filtreleme alani
        arama_filtre_yerlesim = QHBoxLayout()
        
        # Arama kutusu
        arama_etiket = QLabel("Musteri Ara:")
        self.pipeline_arama_kutusu = QLineEdit()
        self.pipeline_arama_kutusu.setPlaceholderText("Musteri adi girin...")
        self.pipeline_arama_kutusu.textChanged.connect(self.pipeline_ara)
        arama_filtre_yerlesim.addWidget(arama_etiket)
        arama_filtre_yerlesim.addWidget(self.pipeline_arama_kutusu)
        
        # Asama filtresi
        asama_etiket = QLabel("Asama Filtrele:")
        self.pipeline_asama_filtre = QComboBox()
        self.pipeline_asama_filtre.addItems(["Tumu", "Ilk Gorusme", "Ihtiyac Analizi", "Teklif Hazirlama", 
                                            "Teklif Sunumu", "Muzakere", "Sozlesme", "Kapali/Kazanildi", 
                                            "Kapali/Kaybedildi", "Beklemede"])
        self.pipeline_asama_filtre.currentTextChanged.connect(self.pipeline_filtrele)
        arama_filtre_yerlesim.addWidget(asama_etiket)
        arama_filtre_yerlesim.addWidget(self.pipeline_asama_filtre)
        
        # Tarih filtresi
        tarih_etiket = QLabel("Tarih Filtrele:")
        self.pipeline_tarih_filtre = QComboBox()
        self.pipeline_tarih_filtre.addItems(["Tumu", "Bu Ay", "Bu Ceyrek", "Bu Yil", "Gecmis", "Gelecek"])
        self.pipeline_tarih_filtre.currentTextChanged.connect(self.pipeline_filtrele)
        arama_filtre_yerlesim.addWidget(tarih_etiket)
        arama_filtre_yerlesim.addWidget(self.pipeline_tarih_filtre)
        
        ana_yerlesim.addLayout(arama_filtre_yerlesim)

        # Pipeline tablosu
        self.pipeline_tablosu = QTableWidget()
        self.pipeline_tablosu.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pipeline_tablosu.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pipeline_tablosu.setColumnCount(8)
        self.pipeline_tablosu.setHorizontalHeaderLabels([
            "Musteri Adi", "Satis Temsilcisi", "Sektor", "Potansiyel Ciro", 
            "Pipeline Asamasi", "Ilerleme", "Tahmini Kapanis Tarihi", "Son Islem Tarihi"
        ])
        self.pipeline_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pipeline_tablosu.setAlternatingRowColors(True)
        self.pipeline_tablosu.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ana_yerlesim.addWidget(self.pipeline_tablosu)
        
        # Ozet bilgiler
        ozet_grup = QGroupBox("Pipeline Ozeti")
        ozet_yerlesim = QHBoxLayout()
        
        # Toplam firsat sayisi
        self.toplam_firsat_etiket = QLabel("Toplam Firsat: 0")
        ozet_yerlesim.addWidget(self.toplam_firsat_etiket)
        
        # Toplam potansiyel ciro
        self.toplam_ciro_etiket = QLabel("Toplam Potansiyel Ciro: 0 TL")
        ozet_yerlesim.addWidget(self.toplam_ciro_etiket)
        
        # Kazanilma orani
        self.kazanilma_orani_etiket = QLabel("Kazanilma Orani: 0%")
        ozet_yerlesim.addWidget(self.kazanilma_orani_etiket)
        
        # Bu ay kapanmasi beklenen firsatlar
        self.bu_ay_kapanacak_etiket = QLabel("Bu Ay Kapanacak: 0")
        ozet_yerlesim.addWidget(self.bu_ay_kapanacak_etiket)
        
        ozet_grup.setLayout(ozet_yerlesim)
        ana_yerlesim.addWidget(ozet_grup)
        
        # Tabloyu guncelle
        self.pipeline_tablosu_guncelle()

    def pipeline_ara(self):
        """Pipeline tablosunda musteri adina gore arama yapar"""
        aranan_metin = self.pipeline_arama_kutusu.text().lower()
        asama_filtresi = self.pipeline_asama_filtre.currentText()
        tarih_filtresi = self.pipeline_tarih_filtre.currentText()
        
        for i in range(self.pipeline_tablosu.rowCount()):
            musteri_adi = self.pipeline_tablosu.item(i, 0).text().lower()
            asama = self.pipeline_tablosu.item(i, 4).text()
            kapanis_tarihi = self.pipeline_tablosu.item(i, 6).text()
            
            # Arama metnine gore kontrol
            arama_eslesme = aranan_metin == "" or aranan_metin in musteri_adi
            
            # Asama filtresine gore kontrol
            asama_eslesme = asama_filtresi == "Tumu" or asama_filtresi == asama
            
            # Tarih filtresine gore kontrol
            tarih_eslesme = True
            if tarih_filtresi != "Tumu" and kapanis_tarihi:
                try:
                    kapanis_date = QDate.fromString(kapanis_tarihi, "yyyy-MM-dd")
                    bugun = QDate.currentDate()
                    
                    if tarih_filtresi == "Bu Ay":
                        tarih_eslesme = (kapanis_date.year() == bugun.year() and 
                                        kapanis_date.month() == bugun.month())
                    elif tarih_filtresi == "Bu Ceyrek":
                        current_quarter = (bugun.month() - 1) // 3 + 1
                        kapanis_quarter = (kapanis_date.month() - 1) // 3 + 1
                        tarih_eslesme = (kapanis_date.year() == bugun.year() and 
                                        kapanis_quarter == current_quarter)
                    elif tarih_filtresi == "Bu Yil":
                        tarih_eslesme = kapanis_date.year() == bugun.year()
                    elif tarih_filtresi == "Gecmis":
                        tarih_eslesme = kapanis_date < bugun
                    elif tarih_filtresi == "Gelecek":
                        tarih_eslesme = kapanis_date > bugun
                except:
                    tarih_eslesme = False
            
            # Tum filtrelere gore satiri goster/gizle
            self.pipeline_tablosu.setRowHidden(i, not (arama_eslesme and asama_eslesme and tarih_eslesme))
    
    def pipeline_filtrele(self):
        """Pipeline tablosunu filtreleme kriterlerine gore filtreler"""
        # Mevcut arama metnini de dikkate alarak filtreleme yap
        self.pipeline_ara()

    def pipeline_tablosu_guncelle(self):
        try:
            if self.services.data_manager.pipeline_df is None or self.services.data_manager.pipeline_df.empty:
                self.pipeline_tablosu.clear()
                self.pipeline_tablosu.setRowCount(0)
                self.pipeline_tablosu.setColumnCount(8)
                self.pipeline_tablosu.setHorizontalHeaderLabels([
                    "Musteri Adi", "Satis Temsilcisi", "Sektor", "Potansiyel Ciro", 
                    "Pipeline Asamasi", "Ilerleme", "Tahmini Kapanis Tarihi", "Son Islem Tarihi"
                ])
                
                # Ozet bilgileri sifirla
                self.toplam_firsat_etiket.setText("Toplam Firsat: 0")
                self.toplam_ciro_etiket.setText("Toplam Potansiyel Ciro: 0 TL")
                self.kazanilma_orani_etiket.setText("Kazanilma Orani: 0%")
                self.bu_ay_kapanacak_etiket.setText("Bu Ay Kapanacak: 0")
                return
            
            df = self.services.data_manager.pipeline_df.copy()
            
            # Eksik sutunlari ekle
            columns = ['Musteri Adi', 'Satis Temsilcisi', 'Sektor', 'Potansiyel Ciro', 
                      'Pipeline Asamasi', 'Tahmini Kapanis Tarihi', 'Son Islem Tarihi']
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            
            # Tabloyu hazirla
            self.pipeline_tablosu.setColumnCount(8)  # Ilerleme sutunu icin +1
            self.pipeline_tablosu.setRowCount(len(df))
            self.pipeline_tablosu.setHorizontalHeaderLabels([
                "Musteri Adi", "Satis Temsilcisi", "Sektor", "Potansiyel Ciro", 
                "Pipeline Asamasi", "Ilerleme", "Tahmini Kapanis Tarihi", "Son Islem Tarihi"
            ])
        
            # Asama-ilerleme eslesmeleri
            asama_ilerleme = {
                "Ilk Gorusme": 10,
                "Ihtiyac Analizi": 25,
                "Teklif Hazirlama": 40,
                "Teklif Sunumu": 55,
                "Muzakere": 70,
                "Sozlesme": 85,
                "Kapali/Kazanildi": 100,
                "Kapali/Kaybedildi": 0,
                "Beklemede": 50
            }
            
            # Verileri tabloya ekle
            toplam_ciro = 0
            kazanilan_firsatlar = 0
            kaybedilen_firsatlar = 0
            bu_ay_kapanacak = 0
            bugun = QDate.currentDate()
            
            for i, row in df.iterrows():
                # Musteri Adi
                self.pipeline_tablosu.setItem(i, 0, QTableWidgetItem(str(row.get('Musteri Adi', ""))))
                
                # Satis Temsilcisi
                self.pipeline_tablosu.setItem(i, 1, QTableWidgetItem(str(row.get('Satis Temsilcisi', ""))))
                
                # Sektor
                self.pipeline_tablosu.setItem(i, 2, QTableWidgetItem(str(row.get('Sektor', ""))))
                
                # Potansiyel Ciro
                ciro_str = ""
                ciro_value = 0
                if pd.notna(row.get('Potansiyel Ciro')):
                    ciro_value = float(row.get('Potansiyel Ciro'))
                    ciro_str = f"{ciro_value:,.2f} {row.get('Para Birimi', 'TL')}"
                    if row.get('Pipeline Asamasi') != "Kapali/Kaybedildi":
                        toplam_ciro += ciro_value
                self.pipeline_tablosu.setItem(i, 3, QTableWidgetItem(ciro_str))
                
                # Pipeline Asamasi
                asama = str(row.get('Pipeline Asamasi', "Ilk Gorusme"))
                self.pipeline_tablosu.setItem(i, 4, QTableWidgetItem(asama))
                
                # Ilerleme - ProgressBar ekle
                ilerleme = asama_ilerleme.get(asama, 0)
                progress_bar = QProgressBar()
                progress_bar.setMinimum(0)
                progress_bar.setMaximum(100)
                progress_bar.setValue(ilerleme)
                
                # Asama durumuna gore renklendirme
                if asama == "Kapali/Kazanildi":
                    progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")  # Yesil
                    kazanilan_firsatlar += 1
                elif asama == "Kapali/Kaybedildi":
                    progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }")  # Kirmizi
                    kaybedilen_firsatlar += 1
                elif asama == "Beklemede":
                    progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")  # Sari
                else:
                    progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2196F3; }")  # Mavi
                
                self.pipeline_tablosu.setCellWidget(i, 5, progress_bar)
                
                # Tahmini Kapanis Tarihi
                kapanis_tarihi = str(row.get('Tahmini Kapanis Tarihi', ""))
                self.pipeline_tablosu.setItem(i, 6, QTableWidgetItem(kapanis_tarihi))
                
                # Bu ay kapanacak firsatlari say
                if kapanis_tarihi:
                    try:
                        kapanis_date = QDate.fromString(kapanis_tarihi, "yyyy-MM-dd")
                        if (kapanis_date.year() == bugun.year() and 
                            kapanis_date.month() == bugun.month() and
                            asama != "Kapali/Kazanildi" and asama != "Kapali/Kaybedildi"):
                            bu_ay_kapanacak += 1
                    except:
                        pass
                
                # Son Islem Tarihi
                son_islem_tarihi = str(row.get('Son Islem Tarihi', ""))
                self.pipeline_tablosu.setItem(i, 7, QTableWidgetItem(son_islem_tarihi))
                
                # Satir renklendirme
                for j in range(self.pipeline_tablosu.columnCount()):
                    item = self.pipeline_tablosu.item(i, j)
                    if item:
                        if asama == "Kapali/Kazanildi":
                            item.setBackground(QColor(232, 245, 233))  # Acik yesil
                        elif asama == "Kapali/Kaybedildi":
                            item.setBackground(QColor(255, 235, 238))  # Acik kirmizi
                        elif asama == "Beklemede":
                            item.setBackground(QColor(255, 248, 225))  # Acik sari
            
            # Ozet bilgileri guncelle
            self.toplam_firsat_etiket.setText(f"Toplam Firsat: {len(df)}")
            self.toplam_ciro_etiket.setText(f"Toplam Potansiyel Ciro: {toplam_ciro:,.2f} TL")
            
            # Kazanilma orani hesapla
            toplam_kapali = kazanilan_firsatlar + kaybedilen_firsatlar
            kazanilma_orani = 0
            if toplam_kapali > 0:
                kazanilma_orani = (kazanilan_firsatlar / toplam_kapali) * 100
            self.kazanilma_orani_etiket.setText(f"Kazanilma Orani: {kazanilma_orani:.1f}%")
            
            # Bu ay kapanacak firsatlar
            self.bu_ay_kapanacak_etiket.setText(f"Bu Ay Kapanacak: {bu_ay_kapanacak}")
            
            # Sutunlari otomatik genislige ayarla
            self.pipeline_tablosu.resizeColumnsToContents()
            
        except Exception as e:
            self.loglayici.error(f"Pipeline tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Pipeline tablosu guncellenirken hata: {str(e)}")

    def pipeline_firsati_ekle(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Potansiyel Musteri Ekle")
        dialog.setMinimumWidth(500)
        yerlesim = QFormLayout()

        # Temel bilgiler
        musteri_giris = QLineEdit()
        
        # Satisci secimi
        satisci_giris = QComboBox()
        if self.services.data_manager.satiscilar_df is not None and not self.services.data_manager.satiscilar_df.empty:
            satisci_isim_sutunu = "Isim" if "Isim" in self.services.data_manager.satiscilar_df.columns else list(self.services.data_manager.satiscilar_df.columns)[0]
            satisci_giris.addItems(self.services.data_manager.satiscilar_df[satisci_isim_sutunu].astype(str).tolist())
        else:
            satisci_giris.addItem("Satiscilar yuklenmedi")
            QMessageBox.warning(self, "Uyari", "Satiscilar yuklenmedi. Lutfen veri yukleyin.")
    
        # Sektor ve alt sektor
        sektor_giris = QLineEdit()
        alt_sektor_giris = QLineEdit()
        
        # Finansal bilgiler
        potansiyel_ciro_giris = QLineEdit()
        para_birimi_giris = QComboBox()
        para_birimi_giris.addItems(["TL", "USD", "EUR"])
        
        # Kar marji tahmini
        kar_marji_giris = QLineEdit()
        kar_marji_giris.setPlaceholderText("Ornek: 25 (yuzde olarak)")
        
        # Asama secimi - Genisletilmis
        asama_giris = QComboBox()
        asama_giris.addItems([
            "Ilk Gorusme", 
            "Ihtiyac Analizi", 
            "Teklif Hazirlama", 
            "Teklif Sunumu", 
            "Muzakere", 
            "Sozlesme", 
            "Kapali/Kazanildi", 
            "Kapali/Kaybedildi", 
            "Beklemede"
        ])
        
        # Tarih bilgileri
        kapanis_tarihi_giris = QDateEdit()
        kapanis_tarihi_giris.setDate(QDate.currentDate().addMonths(1))  # Varsayilan olarak 1 ay sonra
        
        son_islem_tarihi_giris = QDateEdit()
        son_islem_tarihi_giris.setDate(QDate.currentDate())
        
        # Iletisim bilgileri
        iletisim_kisi_giris = QLineEdit()
        iletisim_kisi_giris.setPlaceholderText("Ornek: Ahmet Yilmaz")
        
        iletisim_pozisyon_giris = QLineEdit()
        iletisim_pozisyon_giris.setPlaceholderText("Ornek: Satin Alma Muduru")
        
        iletisim_telefon_giris = QLineEdit()
        iletisim_telefon_giris.setPlaceholderText("Ornek: 0555 123 4567")
        
        iletisim_email_giris = QLineEdit()
        iletisim_email_giris.setPlaceholderText("Ornek: ahmet@sirket.com")
        
        # Notlar
        notlar_giris = QTextEdit()
        notlar_giris.setPlaceholderText("Firsat ile ilgili notlar...")
        notlar_giris.setMaximumHeight(100)
        
        # Kazanma olasiligi
        kazanma_olasiligi_giris = QComboBox()
        kazanma_olasiligi_giris.addItems(["Dusuk (%0-33)", "Orta (%34-66)", "Yuksek (%67-100)"])
        
        # Rekabet durumu
        rekabet_durumu_giris = QComboBox()
        rekabet_durumu_giris.addItems(["Rekabet Yok", "Az Rekabet", "Orta Rekabet", "Yogun Rekabet"])

        # Formu duzenle
        yerlesim.addRow("Potansiyel Musteri Adi: *", musteri_giris)
        yerlesim.addRow("Satis Temsilcisi: *", satisci_giris)
        yerlesim.addRow("Sektor:", sektor_giris)
        yerlesim.addRow("Alt Sektor:", alt_sektor_giris)
        yerlesim.addRow("Potansiyel Ciro:", potansiyel_ciro_giris)
        yerlesim.addRow("Para Birimi:", para_birimi_giris)
        yerlesim.addRow("Tahmini Kar Marji (%):", kar_marji_giris)
        yerlesim.addRow("Pipeline Asamasi: *", asama_giris)
        yerlesim.addRow("Tahmini Kapanis Tarihi: *", kapanis_tarihi_giris)
        yerlesim.addRow("Son Islem Tarihi:", son_islem_tarihi_giris)
        yerlesim.addRow("Iletisim Kisi:", iletisim_kisi_giris)
        yerlesim.addRow("Pozisyon:", iletisim_pozisyon_giris)
        yerlesim.addRow("Telefon:", iletisim_telefon_giris)
        yerlesim.addRow("E-posta:", iletisim_email_giris)
        yerlesim.addRow("Kazanma Olasiligi:", kazanma_olasiligi_giris)
        yerlesim.addRow("Rekabet Durumu:", rekabet_durumu_giris)
        yerlesim.addRow("Notlar:", notlar_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def firsat_kaydet():
            try:
                # Zorunlu alanlar
                musteri_adi = musteri_giris.text().strip()
                if not musteri_adi:
                    raise ValueError("Potansiyel musteri adi bos birakilamaz.")
                
                # Potansiyel ciro kontrolu
                potansiyel_ciro = potansiyel_ciro_giris.text().strip()
                if potansiyel_ciro:
                    try:
                        potansiyel_ciro = float(potansiyel_ciro.replace(',', '.'))
                        if potansiyel_ciro < 0:
                            raise ValueError("Potansiyel ciro negatif olamaz.")
                    except ValueError:
                        raise ValueError("Potansiyel ciro gecerli bir sayi olmali.")
                else:
                    potansiyel_ciro = None
                
                # Kar marji kontrolu
                kar_marji = kar_marji_giris.text().strip()
                if kar_marji:
                    try:
                        kar_marji = float(kar_marji.replace(',', '.'))
                        if kar_marji < 0 or kar_marji > 100:
                            raise ValueError("Kar marji 0-100 arasinda olmali.")
                    except ValueError:
                        raise ValueError("Kar marji gecerli bir sayi olmali.")
                else:
                    kar_marji = None
                
                # Yeni firsat bilgilerini olustur
                yeni_firsat = {
                    "Musteri Adi": musteri_adi,
                    "Satis Temsilcisi": satisci_giris.currentText(),
                    "Sektor": sektor_giris.text().strip() or None,
                    "Alt Sektor": alt_sektor_giris.text().strip() or None,
                    "Potansiyel Ciro": potansiyel_ciro,
                    "Para Birimi": para_birimi_giris.currentText(),
                    "Kar Marji": kar_marji,
                    "Pipeline Asamasi": asama_giris.currentText(),
                    "Tahmini Kapanis Tarihi": kapanis_tarihi_giris.date().toString("yyyy-MM-dd"),
                    "Son Islem Tarihi": son_islem_tarihi_giris.date().toString("yyyy-MM-dd"),
                    "Iletisim Kisi": iletisim_kisi_giris.text().strip() or None,
                    "Pozisyon": iletisim_pozisyon_giris.text().strip() or None,
                    "Telefon": iletisim_telefon_giris.text().strip() or None,
                    "E-posta": iletisim_email_giris.text().strip() or None,
                    "Kazanma Olasiligi": kazanma_olasiligi_giris.currentText(),
                    "Rekabet Durumu": rekabet_durumu_giris.currentText(),
                    "Notlar": notlar_giris.toPlainText().strip() or None
                }
                
                # Veri yoneticisine ekle
                self.services.add_pipeline_opportunity(yeni_firsat)
                
                # Tabloyu guncelle
                self.pipeline_tablosu_guncelle()
                dialog.accept()
                self.loglayici.info(f"Yeni potansiyel musteri eklendi: {musteri_adi}")
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
                self.loglayici.error(f"Deger hatasi: {str(ve)}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Potansiyel musteri eklenirken hata: {str(e)}")
                self.loglayici.error(f"Potansiyel musteri ekleme hatasi: {str(e)}")

        kaydet_butonu.clicked.connect(firsat_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()


    def pipeline_firsati_duzenle(self):
        selected_items = self.pipeline_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
        
            dialog = QDialog(self)
            dialog.setWindowTitle("Potansiyel Musteri Duzenle")
            dialog.setMinimumWidth(500)
            yerlesim = QFormLayout()

            # Mevcut veriyi al
            mevcut_firsat = self.services.data_manager.pipeline_df.iloc[row]
            
            # Temel bilgiler
            musteri_giris = QLineEdit(str(mevcut_firsat.get("Musteri Adi", "")))
            
            # Satisci secimi
            satisci_giris = QComboBox()
            if self.services.data_manager.satiscilar_df is not None and not self.services.data_manager.satiscilar_df.empty:
                satisci_isim_sutunu = "Isim" if "Isim" in self.services.data_manager.satiscilar_df.columns else list(self.services.data_manager.satiscilar_df.columns)[0]
                satisci_giris.addItems(self.services.data_manager.satiscilar_df[satisci_isim_sutunu].astype(str).tolist())
                satisci_giris.setCurrentText(str(mevcut_firsat.get("Satis Temsilcisi", "")))
            else:
                satisci_giris.addItem("Satiscilar yuklenmedi")
                QMessageBox.warning(self, "Uyari", "Satiscilar yuklenmedi. Lutfen veri yukleyin.")
        
            # Sektor ve alt sektor
            sektor_giris = QLineEdit(str(mevcut_firsat.get("Sektor", "")))
            alt_sektor_giris = QLineEdit(str(mevcut_firsat.get("Alt Sektor", "")))
            
            # Finansal bilgiler
            potansiyel_ciro_giris = QLineEdit()
            if pd.notna(mevcut_firsat.get("Potansiyel Ciro")):
                potansiyel_ciro_giris.setText(str(mevcut_firsat.get("Potansiyel Ciro")))
                
            para_birimi_giris = QComboBox()
            para_birimi_giris.addItems(["TL", "USD", "EUR"])
            para_birimi_giris.setCurrentText(str(mevcut_firsat.get("Para Birimi", "TL")))
            
            # Kar marji tahmini
            kar_marji_giris = QLineEdit()
            if pd.notna(mevcut_firsat.get("Kar Marji")):
                kar_marji_giris.setText(str(mevcut_firsat.get("Kar Marji")))
            kar_marji_giris.setPlaceholderText("Ornek: 25 (yuzde olarak)")
            
            # Asama secimi - Genisletilmis
            asama_giris = QComboBox()
            asama_giris.addItems([
                "Ilk Gorusme", 
                "Ihtiyac Analizi", 
                "Teklif Hazirlama", 
                "Teklif Sunumu", 
                "Muzakere", 
                "Sozlesme", 
                "Kapali/Kazanildi", 
                "Kapali/Kaybedildi", 
                "Beklemede"
            ])
            asama_giris.setCurrentText(str(mevcut_firsat.get("Pipeline Asamasi", "Ilk Gorusme")))
            
            # Tarih bilgileri
            kapanis_tarihi_giris = QDateEdit()
            kapanis_tarihi_str = str(mevcut_firsat.get("Tahmini Kapanis Tarihi", ""))
            if kapanis_tarihi_str:
                kapanis_tarihi_giris.setDate(QDate.fromString(kapanis_tarihi_str, "yyyy-MM-dd"))
            else:
                kapanis_tarihi_giris.setDate(QDate.currentDate().addMonths(1))
            
            son_islem_tarihi_giris = QDateEdit()
            son_islem_tarihi_str = str(mevcut_firsat.get("Son Islem Tarihi", ""))
            if son_islem_tarihi_str:
                son_islem_tarihi_giris.setDate(QDate.fromString(son_islem_tarihi_str, "yyyy-MM-dd"))
            else:
                son_islem_tarihi_giris.setDate(QDate.currentDate())
            
            # Iletisim bilgileri
            iletisim_kisi_giris = QLineEdit(str(mevcut_firsat.get("Iletisim Kisi", "")))
            iletisim_kisi_giris.setPlaceholderText("Ornek: Ahmet Yilmaz")
            
            iletisim_pozisyon_giris = QLineEdit(str(mevcut_firsat.get("Pozisyon", "")))
            iletisim_pozisyon_giris.setPlaceholderText("Ornek: Satin Alma Muduru")
            
            iletisim_telefon_giris = QLineEdit(str(mevcut_firsat.get("Telefon", "")))
            iletisim_telefon_giris.setPlaceholderText("Ornek: 0555 123 4567")
            
            iletisim_email_giris = QLineEdit(str(mevcut_firsat.get("E-posta", "")))
            iletisim_email_giris.setPlaceholderText("Ornek: ahmet@sirket.com")
            
            # Notlar
            notlar_giris = QTextEdit()
            notlar_giris.setPlainText(str(mevcut_firsat.get("Notlar", "")))
            notlar_giris.setPlaceholderText("Firsat ile ilgili notlar...")
            notlar_giris.setMaximumHeight(100)
            
            # Kazanma olasiligi
            kazanma_olasiligi_giris = QComboBox()
            kazanma_olasiligi_giris.addItems(["Dusuk (%0-33)", "Orta (%34-66)", "Yuksek (%67-100)"])
            kazanma_olasiligi_giris.setCurrentText(str(mevcut_firsat.get("Kazanma Olasiligi", "Orta (%34-66)")))
            
            # Rekabet durumu
            rekabet_durumu_giris = QComboBox()
            rekabet_durumu_giris.addItems(["Rekabet Yok", "Az Rekabet", "Orta Rekabet", "Yogun Rekabet"])
            rekabet_durumu_giris.setCurrentText(str(mevcut_firsat.get("Rekabet Durumu", "Orta Rekabet")))

            # Formu duzenle
            yerlesim.addRow("Potansiyel Musteri Adi: *", musteri_giris)
            yerlesim.addRow("Satis Temsilcisi: *", satisci_giris)
            yerlesim.addRow("Sektor:", sektor_giris)
            yerlesim.addRow("Alt Sektor:", alt_sektor_giris)
            yerlesim.addRow("Potansiyel Ciro:", potansiyel_ciro_giris)
            yerlesim.addRow("Para Birimi:", para_birimi_giris)
            yerlesim.addRow("Tahmini Kar Marji (%):", kar_marji_giris)
            yerlesim.addRow("Pipeline Asamasi: *", asama_giris)
            yerlesim.addRow("Tahmini Kapanis Tarihi: *", kapanis_tarihi_giris)
            yerlesim.addRow("Son Islem Tarihi:", son_islem_tarihi_giris)
            yerlesim.addRow("Iletisim Kisi:", iletisim_kisi_giris)
            yerlesim.addRow("Pozisyon:", iletisim_pozisyon_giris)
            yerlesim.addRow("Telefon:", iletisim_telefon_giris)
            yerlesim.addRow("E-posta:", iletisim_email_giris)
            yerlesim.addRow("Kazanma Olasiligi:", kazanma_olasiligi_giris)
            yerlesim.addRow("Rekabet Durumu:", rekabet_durumu_giris)
            yerlesim.addRow("Notlar:", notlar_giris)

            butonlar = QHBoxLayout()
            kaydet_butonu = QPushButton("Kaydet")
            iptal_butonu = QPushButton("Iptal")
            butonlar.addWidget(kaydet_butonu)
            butonlar.addWidget(iptal_butonu)
            yerlesim.addRow(butonlar)
            dialog.setLayout(yerlesim)

            def firsat_guncelle():
                try:
                    # Zorunlu alanlar
                    musteri_adi_text = musteri_giris.text().strip()
                    if not musteri_adi_text:
                        raise ValueError("Potansiyel musteri adi bos birakilamaz.")
                
                    # Potansiyel ciro kontrolu
                    potansiyel_ciro_text = potansiyel_ciro_giris.text().strip()
                    if potansiyel_ciro_text:
                        try:
                            potansiyel_ciro_value = float(potansiyel_ciro_text.replace(',', '.'))
                            if potansiyel_ciro_value < 0:
                                raise ValueError("Potansiyel ciro negatif olamaz.")
                        except ValueError:
                            raise ValueError("Potansiyel ciro gecerli bir sayi olmali.")
                    else:
                        potansiyel_ciro_value = None
                    
                    # Kar marji kontrolu
                    kar_marji_text = kar_marji_giris.text().strip()
                    if kar_marji_text:
                        try:
                            kar_marji_value = float(kar_marji_text.replace(',', '.'))
                            if kar_marji_value < 0 or kar_marji_value > 100:
                                raise ValueError("Kar marji 0-100 arasinda olmali.")
                        except ValueError:
                            raise ValueError("Kar marji gecerli bir sayi olmali.")
                    else:
                        kar_marji_value = None

                    # Guncellenmis firsat bilgilerini olustur
                    yeni_veriler = {
                        "Musteri Adi": musteri_adi_text,
                        "Satis Temsilcisi": satisci_giris.currentText(),
                        "Sektor": sektor_giris.text().strip() or None,
                        "Alt Sektor": alt_sektor_giris.text().strip() or None,
                        "Potansiyel Ciro": potansiyel_ciro_value,
                        "Para Birimi": para_birimi_giris.currentText(),
                        "Kar Marji": kar_marji_value,
                        "Pipeline Asamasi": asama_giris.currentText(),
                        "Tahmini Kapanis Tarihi": kapanis_tarihi_giris.date().toString("yyyy-MM-dd"),
                        "Son Islem Tarihi": son_islem_tarihi_giris.date().toString("yyyy-MM-dd"),
                        "Iletisim Kisi": iletisim_kisi_giris.text().strip() or None,
                        "Pozisyon": iletisim_pozisyon_giris.text().strip() or None,
                        "Telefon": iletisim_telefon_giris.text().strip() or None,
                        "E-posta": iletisim_email_giris.text().strip() or None,
                        "Kazanma Olasiligi": kazanma_olasiligi_giris.currentText(),
                        "Rekabet Durumu": rekabet_durumu_giris.currentText(),
                        "Notlar": notlar_giris.toPlainText().strip() or None
                    }
                    
                    # Veri yoneticisinde guncelle
                    self.services.update_pipeline_opportunity(row, yeni_veriler)
                    
                    # Tabloyu guncelle
                    self.pipeline_tablosu_guncelle()
                    dialog.accept()
                    self.loglayici.info(f"Potansiyel musteri guncellendi: {musteri_adi_text}")
                except ValueError as ve:
                    QMessageBox.warning(self, "Uyari", str(ve))
                    self.loglayici.error(f"Deger hatasi: {str(ve)}")
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Potansiyel musteri guncellenirken hata: {str(e)}")
                    self.loglayici.error(f"Potansiyel musteri guncelleme hatasi: {str(e)}")

            kaydet_butonu.clicked.connect(firsat_guncelle)
            iptal_butonu.clicked.connect(dialog.reject)
            dialog.exec()
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek istediginiz potansiyel musteriyi secin.")

    def pipeline_firsati_sil(self):
        selected_items = self.pipeline_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            musteri_adi = self.pipeline_tablosu.item(row, 0).text()
            asama = self.pipeline_tablosu.item(row, 4).text()
            
            # Onay mesaji
            onay_mesaji = f"{musteri_adi} musterisi icin pipeline firsatini silmek istediginize emin misiniz?"
            
            # Eger firsat kapanmissa ek uyari goster
            if asama == "Kapali/Kazanildi" or asama == "Kapali/Kaybedildi":
                onay_mesaji += f"\n\nDikkat: Bu firsat '{asama}' durumunda. Silme islemi geri alinamaz."
            
            onay = QMessageBox.question(
                self, 
                "Firsat Silme Onayi", 
                onay_mesaji,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # Varsayilan olarak Hayir
            )
            
            if onay == QMessageBox.StandardButton.Yes:
                try:
                    # Firsati sil
                    self.services.delete_pipeline_opportunity(musteri_adi)
                    
                    # Tabloyu guncelle
                    self.pipeline_tablosu_guncelle()
                    
                    # Bilgi mesaji goster
                    QMessageBox.information(
                        self, 
                        "Islem Basarili", 
                        f"{musteri_adi} musterisi icin firsat basariyla silindi."
                    )
                    
                    # Log kaydi
                    self.loglayici.info(f"Pipeline firsati silindi: {musteri_adi} - {asama}")
                except Exception as e:
                    QMessageBox.critical(
                        self, 
                        "Hata", 
                        f"Firsat silinirken bir hata olustu: {str(e)}"
                    )
                    self.loglayici.error(f"Pipeline firsati silme hatasi: {str(e)}")
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek istediginiz firsati secin.")

    def satis_hedefi_ekle(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Hedef Ekle")
        yerlesim = QFormLayout()

        ay_secim = QComboBox()
        ay_secim.addItems([f"{i:02d}" for i in range(1, 13)])
        ay_secim.setCurrentText(QDate.currentDate().toString("MM"))
        yil_secim = QComboBox()
        yillar = [str(y) for y in range(2020, 2031)]
        yil_secim.addItems(yillar)
        yil_secim.setCurrentText(str(QDate.currentDate().year()))
        hedef_giris = QLineEdit()
        para_birimi_giris = QComboBox()
        para_birimi_giris.addItems(["TL", "USD", "EUR"])

        yerlesim.addRow("Ay (MM):", ay_secim)
        yerlesim.addRow("Yil (YYYY):", yil_secim)
        yerlesim.addRow("Hedef:", hedef_giris)
        yerlesim.addRow("Para Birimi:", para_birimi_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def hedef_kaydet():
            try:
                ay_str = f"{ay_secim.currentText()}-{yil_secim.currentText()}"  # "03-2025" (MM-YYYY formati)
                self.loglayici.debug(f"Hedef ekleme - Gonderilen Ay degeri: '{ay_str}' (MM-YYYY formati)")
                hedef = float(hedef_giris.text().replace(',', '.'))
                
                # Hedef degerinin pozitif olup olmadigini kontrol et
                if hedef <= 0:
                    raise ValueError("Hedef degeri pozitif bir sayi olmalidir.")
                
                yeni_hedef = {
                    "Ay": ay_str,
                    "Hedef": hedef,
                    "Para Birimi": para_birimi_giris.currentText()
                }
                self.services.add_sales_target(yeni_hedef)
                self.satis_hedefleri_tablosu_guncelle()
                # Gosterge panelini guncelle
                if hasattr(self, 'gosterge_paneli_guncelle'):
                    self.gosterge_paneli_guncelle()
                # Olay yayinla
                self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_ekle"}))
                dialog.accept()
                
                # Basarili mesaji goster
                QMessageBox.information(self, "Basarili", f"{ay_str} icin {hedef} {para_birimi_giris.currentText()} hedef basariyla eklendi.")
                self.loglayici.info(f"Yeni hedef eklendi: {ay_str} - {hedef} {para_birimi_giris.currentText()}")
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Hedef eklenirken hata: {str(e)}")
                self.loglayici.error(f"Hedef ekleme hatasi: {str(e)}")

        kaydet_butonu.clicked.connect(hedef_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()
  

    def musteri_profili_olustur(self):
        sekme = QWidget()
        self.sekme_widget.addTab(sekme, "Musteri Profili")
    
        yerlesim = QVBoxLayout()
        sekme.setLayout(yerlesim)

        # Butonlari yukariya tasi
        buton_yerlesim = QHBoxLayout()
        musteri_ekle_butonu = QPushButton("Yeni Musteri Ekle")
        musteri_ekle_butonu.clicked.connect(self.musteri_ekle)
        buton_yerlesim.addWidget(musteri_ekle_butonu)

        musteri_duzenle_butonu = QPushButton("Musteri Duzenle")
        musteri_duzenle_butonu.clicked.connect(self.musteri_guncelle)  # musteri_duzenle -> musteri_guncelle
        buton_yerlesim.addWidget(musteri_duzenle_butonu)

        musteri_sil_butonu = QPushButton("Musteri Sil")
        musteri_sil_butonu.clicked.connect(self.musteri_sil)
        buton_yerlesim.addWidget(musteri_sil_butonu)

        yerlesim.addLayout(buton_yerlesim)

        # Tabloyu butonlarin altina ekle
        self.musteri_tablosu = QTableWidget()
        # Sutun sayisini ve basliklarini manuel olarak ayarla
        self.musteri_tablosu.setColumnCount(7)
        self.musteri_tablosu.setHorizontalHeaderLabels([
            "Musteri Adi", "Sektor", "Bolge", "Global/Lokal", 
            "Musteri Turu", "Ana Musteri", "Son Satin Alma Tarihi"
        ])
        self.musteri_tablosu.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.musteri_tablosu.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.musteri_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        yerlesim.addWidget(self.musteri_tablosu)

        self.musteri_tablosu_guncelle()  # Ilk acilista tabloyu guncelle

    def musteri_tablosu_guncelle(self):
        if self.services.data_manager.musteriler_df is not None and not self.services.data_manager.musteriler_df.empty:
            df = self.services.data_manager.musteriler_df
            self.musteri_tablosu.setRowCount(len(df))
            
            # Sutun sayisi ve basliklar zaten ayarlandi, sadece verileri ekle
            for i, (_, musteri) in enumerate(df.iterrows()):
                self.musteri_tablosu.setItem(i, 0, QTableWidgetItem(str(musteri.get("Musteri Adi", ""))))
                self.musteri_tablosu.setItem(i, 1, QTableWidgetItem(str(musteri.get("Sektor", ""))))
                self.musteri_tablosu.setItem(i, 2, QTableWidgetItem(str(musteri.get("Bolge", ""))))
                self.musteri_tablosu.setItem(i, 3, QTableWidgetItem(str(musteri.get("Global/Lokal", ""))))
                self.musteri_tablosu.setItem(i, 4, QTableWidgetItem(str(musteri.get("Musteri Turu", ""))))
                self.musteri_tablosu.setItem(i, 5, QTableWidgetItem(str(musteri.get("Ana Musteri", ""))))
                self.musteri_tablosu.setItem(i, 6, QTableWidgetItem(str(musteri.get("Son Satin Alma Tarihi", ""))))
        else:
            self.musteri_tablosu.setRowCount(0)

    def musteri_ekle(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Musteri Ekle")
        yerlesim = QFormLayout()

        isim_giris = QLineEdit()
        sektor_giris = QLineEdit()
        bolge_giris = QLineEdit()
        buyukluk_giris = QComboBox()
        buyukluk_giris.addItems(["Global", "Lokal"])
        musteri_turu_giris = QComboBox()
        musteri_turu_giris.addItems(["Ana Musteri", "Alt Musteri"])
        ana_musteri_giris = QComboBox()
        ana_musteri_giris.addItem("Yok")
        if self.services.data_manager.musteriler_df is not None and not self.services.data_manager.musteriler_df.empty:
            ana_musteriler = self.services.data_manager.musteriler_df[
                self.services.data_manager.musteriler_df["Musteri Turu"] == "Ana Musteri"
            ]["Musteri Adi"].astype(str).tolist()
            ana_musteri_giris.addItems(ana_musteriler)

        yerlesim.addRow("Musteri Adi:", isim_giris)
        yerlesim.addRow("Sektor:", sektor_giris)
        yerlesim.addRow("Bolge:", bolge_giris)
        yerlesim.addRow("Global/Lokal:", buyukluk_giris)
        yerlesim.addRow("Musteri Turu:", musteri_turu_giris)
        yerlesim.addRow("Ana Musteri:", ana_musteri_giris)

        def musteri_turu_degisti():
            ana_musteri_giris.setEnabled(musteri_turu_giris.currentText() == "Alt Musteri")

        musteri_turu_giris.currentTextChanged.connect(musteri_turu_degisti)
        musteri_turu_degisti()

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def musteri_kaydet():
            yeni_musteri = {
                "Musteri Adi": isim_giris.text(),
                "Sektor": sektor_giris.text(),
                "Bolge": bolge_giris.text(),
                "Global/Lokal": buyukluk_giris.currentText(),
                "Musteri Turu": musteri_turu_giris.currentText(),
                "Ana Musteri": ana_musteri_giris.currentText() if musteri_turu_giris.currentText() == "Alt Musteri" and ana_musteri_giris.currentText() != "Yok" else None,
                "Son Satin Alma Tarihi": None
            }
            if not yeni_musteri["Musteri Adi"]:
                QMessageBox.warning(self, "Uyari", "Musteri adi bos birakilamaz.")
                return
            self.services.add_customer(yeni_musteri)  # Degistirildi
            self.musteri_tablosu_guncelle()
            dialog.accept()
            self.loglayici.info(f"Yeni musteri eklendi: {yeni_musteri['Musteri Adi']} ({yeni_musteri['Musteri Turu']})")

        kaydet_butonu.clicked.connect(musteri_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def musteri_guncelle(self):
        selected_items = self.musteri_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            dialog = QDialog(self)
            dialog.setWindowTitle("Musteri Duzenle")
            yerlesim = QFormLayout()

            mevcut_musteri = self.services.data_manager.musteriler_df.iloc[row]  # self.veri_yoneticisi -> self.services.data_manager
            isim_giris = QLineEdit(mevcut_musteri["Musteri Adi"])
            sektor_giris = QLineEdit(str(mevcut_musteri["Sektor"]) if pd.notna(mevcut_musteri["Sektor"]) else "")
            bolge_giris = QLineEdit(str(mevcut_musteri["Bolge"]) if pd.notna(mevcut_musteri["Bolge"]) else "")
            buyukluk_giris = QComboBox()
            buyukluk_giris.addItems(["Global", "Lokal"])
            buyukluk_giris.setCurrentText(str(mevcut_musteri["Global/Lokal"]) if pd.notna(mevcut_musteri["Global/Lokal"]) else "Lokal")
            musteri_turu_giris = QComboBox()
            musteri_turu_giris.addItems(["Ana Musteri", "Alt Musteri"])
            musteri_turu_giris.setCurrentText(str(mevcut_musteri["Musteri Turu"]))
            ana_musteri_giris = QComboBox()
            ana_musteri_giris.addItem("Yok")
            if self.services.data_manager.musteriler_df is not None and not self.services.data_manager.musteriler_df.empty:  # self.veri_yoneticisi -> self.services.data_manager
                ana_musteriler = self.services.data_manager.musteriler_df[
                    self.services.data_manager.musteriler_df["Musteri Turu"] == "Ana Musteri"
                ]["Musteri Adi"].astype(str).tolist()
                ana_musteri_giris.addItems(ana_musteriler)
            ana_musteri_giris.setCurrentText(str(mevcut_musteri["Ana Musteri"]) if pd.notna(mevcut_musteri["Ana Musteri"]) else "Yok")

            yerlesim.addRow("Musteri Adi:", isim_giris)
            yerlesim.addRow("Sektor:", sektor_giris)
            yerlesim.addRow("Bolge:", bolge_giris)
            yerlesim.addRow("Global/Lokal:", buyukluk_giris)
            yerlesim.addRow("Musteri Turu:", musteri_turu_giris)
            yerlesim.addRow("Ana Musteri:", ana_musteri_giris)

            def musteri_turu_degisti():
                ana_musteri_giris.setEnabled(musteri_turu_giris.currentText() == "Alt Musteri")

            musteri_turu_giris.currentTextChanged.connect(musteri_turu_degisti)
            musteri_turu_degisti()

            butonlar = QHBoxLayout()
            kaydet_butonu = QPushButton("Kaydet")
            iptal_butonu = QPushButton("Iptal")
            butonlar.addWidget(kaydet_butonu)
            butonlar.addWidget(iptal_butonu)
            yerlesim.addRow(butonlar)
            dialog.setLayout(yerlesim)

            def musteri_guncelle():
                try:
                    yeni_bilgiler = {
                        "Musteri Adi": isim_giris.text(),
                        "Sektor": sektor_giris.text() if sektor_giris.text() else None,
                        "Bolge": bolge_giris.text() if bolge_giris.text() else None,
                        "Global/Lokal": buyukluk_giris.currentText(),
                        "Musteri Turu": musteri_turu_giris.currentText(),
                        "Ana Musteri": ana_musteri_giris.currentText() if musteri_turu_giris.currentText() == "Alt Musteri" and ana_musteri_giris.currentText() != "Yok" else None,
                        "Son Satin Alma Tarihi": mevcut_musteri["Son Satin Alma Tarihi"]  # Mevcut degeri koru
                    }
                    if not yeni_bilgiler["Musteri Adi"]:
                        QMessageBox.warning(self, "Uyari", "Musteri adi bos birakilamaz.")
                        return
                    # Duzeltme: Dogrudan DataFrame guncellemesi ve repository.save yerine services kullaniyoruz
                    self.services.data_manager.musteriler_df.iloc[row] = pd.Series(yeni_bilgiler)
                    self.services.data_manager.repository.save(self.services.data_manager.musteriler_df, "customers")  # Servis uzerinden kaydetme
                    self.musteri_tablosu_guncelle()
                    dialog.accept()
                    self.loglayici.info(f"Musteri guncellendi: {yeni_bilgiler['Musteri Adi']} ({yeni_bilgiler['Musteri Turu']})")
                except ValueError as ve:
                    QMessageBox.warning(self, "Uyari", str(ve))
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Musteri guncellenirken hata: {str(e)}")
                    self.loglayici.error(f"Musteri guncelleme hatasi: {str(e)}")

            kaydet_butonu.clicked.connect(musteri_guncelle)
            iptal_butonu.clicked.connect(dialog.reject)
            dialog.exec()
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek icin bir musteri secin.")


    def musteri_sil(self):
        selected_items = self.musteri_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            musteri_adi = self.musteri_tablosu.item(row, 0).text()
            onay = QMessageBox.question(self, "Onay", f"{musteri_adi} musterisini silmek istediginize emin misiniz?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if onay == QMessageBox.StandardButton.Yes:
                # Duzeltme: self.veri_yoneticisi ve self.repository.save kaldirildi
                self.services.data_manager.musteriler_df = self.services.data_manager.musteriler_df[
                    self.services.data_manager.musteriler_df["Musteri Adi"] != musteri_adi
                ]
                self.services.data_manager.repository.save(self.services.data_manager.musteriler_df, "customers")  # Servis uzerinden kaydetme
                self.musteri_tablosu.removeRow(row)
                self.loglayici.info(f"Musteri silindi: {musteri_adi}")
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir musteri secin.")


    def aylik_satis_takibi_olustur(self):
        """Aylik Satis Takibi sekmesini olusturur"""
        self.satis_tab = QWidget()
        self.sekme_widget.addTab(self.satis_tab, "Aylik Satis Takibi")
        
        ana_yerlesim = QVBoxLayout()
        self.satis_tab.setLayout(ana_yerlesim)
        
        # Ust kisim - Butonlar
        buton_yerlesim = QHBoxLayout()
        
        self.satis_ekle_butonu = QPushButton("Yeni Satis Ekle")
        self.satis_ekle_butonu.clicked.connect(self.satis_ekle)
        buton_yerlesim.addWidget(self.satis_ekle_butonu)
        
        self.satis_duzenle_butonu = QPushButton("Satis Duzenle")
        self.satis_duzenle_butonu.clicked.connect(self.satis_duzenle)
        buton_yerlesim.addWidget(self.satis_duzenle_butonu)
        
        self.satis_sil_butonu = QPushButton("Satis Sil")
        self.satis_sil_butonu.clicked.connect(self.satis_sil)
        buton_yerlesim.addWidget(self.satis_sil_butonu)
        
        ana_yerlesim.addLayout(buton_yerlesim)
        
        # Tablo
        self.satis_tablosu = QTableWidget()
        self.satis_tablosu.setColumnCount(10)
        self.satis_tablosu.setHorizontalHeaderLabels([
            "Ana Musteri", "Alt Musteri", "Satis Temsilcisi", "Ay", 
            "Urun Kodu", "Urun Adi", "Miktar", "Birim Fiyat", 
            "Satis Miktari", "Para Birimi"
        ])
        self.satis_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.satis_tablosu.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.satis_tablosu.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        ana_yerlesim.addWidget(self.satis_tablosu)
        
        # Tabloyu guncelle
        self.satis_tablosu_guncelle()

    def satis_tablosu_guncelle(self):
        """Satis tablosunu gunceller"""
        try:
            satis_df = self.services.data_manager.satislar_df
            
            self.satis_tablosu.setRowCount(0)
            
            if satis_df is None or satis_df.empty:
                return
                
            self.satis_tablosu.setRowCount(len(satis_df))
            
            columns = ["Ana Musteri", "Alt Musteri", "Satis Temsilcisi", "Ay", 
                      "Urun Kodu", "Urun Adi", "Miktar", "Birim Fiyat", 
                      "Satis Miktari", "Para Birimi"]
            
            for i, row in satis_df.iterrows():
                for j, col in enumerate(columns):
                    value = str(row.get(col, "")) if not pd.isna(row.get(col, "")) else "Yok" if col == "Alt Musteri" else ""
                    self.satis_tablosu.setItem(i, j, QTableWidgetItem(value))
        except Exception as e:
            self.loglayici.error(f"Satis tablosu guncellenirken hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Satis tablosu guncellenirken hata: {str(e)}")

    def satis_ekle(self):
        if not hasattr(self.services.data_manager, 'musteriler_df') or self.services.data_manager.musteriler_df is None or self.services.data_manager.musteriler_df.empty:
            QMessageBox.warning(self, "Uyari", "Once en az bir musteri ekleyin.")
            return
        if not hasattr(self.services.data_manager, 'satiscilar_df') or self.services.data_manager.satiscilar_df is None or self.services.data_manager.satiscilar_df.empty:
            QMessageBox.warning(self, "Uyari", "Once en az bir satisci ekleyin.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Satis Ekle")
        yerlesim = QFormLayout()

        ana_musteri_giris = QComboBox()
        ana_musteriler = self.services.data_manager.musteriler_df[
            self.services.data_manager.musteriler_df["Musteri Turu"] == "Ana Musteri"
        ]["Musteri Adi"].astype(str).tolist()
        ana_musteri_giris.addItems(ana_musteriler)
        alt_musteri_giris = QComboBox()
        alt_musteri_giris.addItem("Yok")
        alt_musteriler = self.services.data_manager.musteriler_df[
            self.services.data_manager.musteriler_df["Musteri Turu"] == "Alt Musteri"
        ]["Musteri Adi"].astype(str).tolist()
        alt_musteri_giris.addItems(alt_musteriler)
        satisci_giris = QComboBox()
        satisci_giris.addItems(self.services.data_manager.satiscilar_df["Isim"].astype(str).tolist())
        ay_secim = QComboBox()
        ay_secim.addItems([f"{i:02d}" for i in range(1, 13)])
        ay_secim.setCurrentText(QDate.currentDate().toString("MM"))
        yil_secim = QComboBox()
        yillar = [str(y) for y in range(2020, 2031)]
        yil_secim.addItems(yillar)
        yil_secim.setCurrentText(str(QDate.currentDate().year()))
        urun_kodu_giris = QLineEdit()
        urun_adi_giris = QLineEdit()
        miktar_giris = QLineEdit("1")
        birim_fiyat_giris = QLineEdit()
        satis_miktari_giris = QLineEdit()
        para_birimi_giris = QComboBox()
        para_birimi_giris.addItems(["TL", "USD", "EUR"])

        yerlesim.addRow("Ana Musteri:", ana_musteri_giris)
        yerlesim.addRow("Alt Musteri:", alt_musteri_giris)
        yerlesim.addRow("Satis Temsilcisi:", satisci_giris)
        yerlesim.addRow("Ay:", ay_secim)
        yerlesim.addRow("Yil:", yil_secim)
        yerlesim.addRow("Urun Kodu:", urun_kodu_giris)
        yerlesim.addRow("Urun Adi:", urun_adi_giris)
        yerlesim.addRow("Miktar:", miktar_giris)
        yerlesim.addRow("Birim Fiyat:", birim_fiyat_giris)
        yerlesim.addRow("Satis Miktari:", satis_miktari_giris)
        yerlesim.addRow("Para Birimi:", para_birimi_giris)

        def hesapla_satis_miktari():
            try:
                miktar = float(miktar_giris.text().replace(',', '.')) if miktar_giris.text() else 0
                birim_fiyat = float(birim_fiyat_giris.text().replace(',', '.')) if birim_fiyat_giris.text() else 0
                satis_miktari_giris.setText(str(miktar * birim_fiyat))
            except ValueError:
                pass

        miktar_giris.textChanged.connect(hesapla_satis_miktari)
        birim_fiyat_giris.textChanged.connect(hesapla_satis_miktari)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def satis_kaydet():
            try:
                ay_str = f"{ay_secim.currentText()}-{yil_secim.currentText()}"
                satis_miktari = float(satis_miktari_giris.text().replace(',', '.'))
                if satis_miktari <= 0:
                    raise ValueError("Satis miktari pozitif bir sayi olmali.")
                miktar = float(miktar_giris.text().replace(',', '.'))
                birim_fiyat = float(birim_fiyat_giris.text().replace(',', '.'))
                if miktar <= 0 or birim_fiyat <= 0:
                    raise ValueError("Miktar ve birim fiyat pozitif olmali.")
                if not ana_musteri_giris.currentText():
                    raise ValueError("Ana Musteri secimi zorunludur.")
                yeni_satis = {
                    "Ana Musteri": ana_musteri_giris.currentText(),
                    "Alt Musteri": alt_musteri_giris.currentText() if alt_musteri_giris.currentText() != "Yok" else None,
                    "Satis Temsilcisi": satisci_giris.currentText(),
                    "Ay": ay_str,
                    "Urun Kodu": urun_kodu_giris.text(),
                    "Urun Adi": urun_adi_giris.text(),
                    "Miktar": miktar,
                    "Birim Fiyat": birim_fiyat,
                    "Satis Miktari": satis_miktari,
                    "Para Birimi": para_birimi_giris.currentText()
                }
                self.satis_worker = SatisEklemeWorker(yeni_satis, self.services)
                self.satis_worker.tamamlandi.connect(self._satis_ekle_tamamlandi)
                self.satis_worker.hata.connect(self._islem_hata)
                self.satis_worker.start()
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))

        kaydet_butonu.clicked.connect(satis_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def satis_duzenle(self):
        selected_items = self.satis_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            dialog = QDialog(self)
            dialog.setWindowTitle("Satis Duzenle")
            yerlesim = QFormLayout()

            satis = self.services.data_manager.satislar_df.iloc[row]  # self.veri_yoneticisi -> self.services.data_manager
            ana_musteri_giris = QComboBox()
            ana_musteriler = self.services.data_manager.musteriler_df[  # self.veri_yoneticisi -> self.services.data_manager
                self.services.data_manager.musteriler_df["Musteri Turu"] == "Ana Musteri"
            ]["Musteri Adi"].astype(str).tolist()
            ana_musteri_giris.addItems(ana_musteriler)
            ana_musteri_giris.setCurrentText(str(satis["Ana Musteri"]))
            alt_musteri_giris = QComboBox()
            alt_musteri_giris.addItem("Yok")
            alt_musteriler = self.services.data_manager.musteriler_df[  # self.veri_yoneticisi -> self.services.data_manager
                self.services.data_manager.musteriler_df["Musteri Turu"] == "Alt Musteri"
            ]["Musteri Adi"].astype(str).tolist()
            alt_musteri_giris.addItems(alt_musteriler)
            satisci_giris = QComboBox()
            satisci_giris.addItems(self.services.data_manager.satiscilar_df["Isim"].astype(str).tolist())  # self.veri_yoneticisi -> self.services.data_manager
            satisci_giris.setCurrentText(str(satis["Satis Temsilcisi"]))
            
            # Ay ve yil bilgisi
            ay_str = str(satis["Ay"])
            ay_secim = QComboBox()
            ay_secim.addItems([f"{i:02d}" for i in range(1, 13)])
            
            # Ay formatini kontrol et ve dogru sekilde ayir
            if "-" in ay_str:
                # Format kontrolu: YYYY-MM mi yoksa MM-YYYY mi?
                ay_parcalari = ay_str.split("-")
                if len(ay_parcalari) == 2:
                    # Ilk parca 4 haneli ise YYYY-MM formatindadir
                    if len(ay_parcalari[0]) == 4:
                        ay_secim.setCurrentText(ay_parcalari[1])  # YYYY-MM formatinda ay ikinci parcadir
                        yil = ay_parcalari[0]
                    else:
                        ay_secim.setCurrentText(ay_parcalari[0])  # MM-YYYY formatinda ay ilk parcadir
                        yil = ay_parcalari[1]
                else:
                    ay_secim.setCurrentText("01")
                    yil = str(QDate.currentDate().year())
            else:
                ay_secim.setCurrentText("01")
                yil = str(QDate.currentDate().year())
                
            yil_secim = QComboBox()
            yillar = [str(y) for y in range(2020, 2031)]
            yil_secim.addItems(yillar)
            yil_secim.setCurrentText(yil)
            
            # Urun bilgileri
            urun_kodu_giris = QLineEdit(str(satis["Urun Kodu"]))
            urun_adi_giris = QLineEdit(str(satis["Urun Adi"]))
            
            # Mevcut urun BOM verilerinden urun kodlarini yukle
            if hasattr(self.services.data_manager, 'urun_bom_df') and self.services.data_manager.urun_bom_df is not None and not self.services.data_manager.urun_bom_df.empty:
                try:
                    urun_combo = QComboBox()
                    urunler = self.services.data_manager.urun_bom_df[["Urun Kodu", "Urun Adi"]].drop_duplicates()
                    if not urunler.empty:
                        urun_combo.addItem("", "")  # Bos secim
                        for _, urun in urunler.iterrows():
                            urun_kodu = str(urun["Urun Kodu"]) if not pd.isna(urun["Urun Kodu"]) else ""
                            urun_adi = str(urun["Urun Adi"]) if not pd.isna(urun["Urun Adi"]) else ""
                            if urun_kodu:  # Bos olmayan kodlari ekle
                                urun_combo.addItem(f"{urun_kodu} - {urun_adi}", {"kod": urun_kodu, "ad": urun_adi})
                        
                        # Mevcut urunu sec
                        for i in range(urun_combo.count()):
                            data = urun_combo.itemData(i)
                            if data and data["kod"] == str(satis["Urun Kodu"]):
                                urun_combo.setCurrentIndex(i)
                                break
                        
                        # Urun secildiginde kod ve ad alanlarini doldur
                        def urun_secildi(index):
                            if index > 0:  # Bos secim degil
                                data = urun_combo.itemData(index)
                                urun_kodu_giris.setText(data["kod"])
                                urun_adi_giris.setText(data["ad"])
                        
                        urun_combo.currentIndexChanged.connect(urun_secildi)
                        yerlesim.addRow("Urun Sec:", urun_combo)
                        
                        if self.loglayici:
                            self.loglayici.info(f"Urun BOM verilerinden {len(urunler)} urun yuklendi")
                except Exception as e:
                    if self.loglayici:
                        self.loglayici.error(f"Urun BOM verilerinden urun yuklenirken hata: {str(e)}")
            
            miktar_giris = QLineEdit(str(satis["Miktar"]))
            birim_fiyat_giris = QLineEdit(str(satis["Birim Fiyat"]))
            satis_miktari_giris = QLineEdit(str(satis["Satis Miktari"]))
            
            para_birimi_giris = QComboBox()
            para_birimi_giris.addItems(["TL", "USD", "EUR"])
            para_birimi_giris.setCurrentText(str(satis["Para Birimi"]))

            yerlesim.addRow("Ana Musteri:", ana_musteri_giris)
            yerlesim.addRow("Alt Musteri:", alt_musteri_giris)
            yerlesim.addRow("Satis Temsilcisi:", satisci_giris)
            yerlesim.addRow("Ay (MM):", ay_secim)
            yerlesim.addRow("Yil (YYYY):", yil_secim)
            yerlesim.addRow("Urun Kodu:", urun_kodu_giris)
            yerlesim.addRow("Urun Adi:", urun_adi_giris)
            yerlesim.addRow("Miktar:", miktar_giris)
            yerlesim.addRow("Birim Fiyat:", birim_fiyat_giris)
            yerlesim.addRow("Satis Miktari:", satis_miktari_giris)
            yerlesim.addRow("Para Birimi:", para_birimi_giris)

            # Miktar ve birim fiyat değiştiğinde satış miktarını otomatik hesapla
            def hesapla_satis_miktari():
                try:
                    miktar = float(miktar_giris.text().replace(',', '.')) if miktar_giris.text() else 0
                    birim_fiyat = float(birim_fiyat_giris.text().replace(',', '.')) if birim_fiyat_giris.text() else 0
                    satis_miktari = miktar * birim_fiyat
                    satis_miktari_giris.setText(str(satis_miktari))
                except ValueError:
                    pass
            
            miktar_giris.textChanged.connect(hesapla_satis_miktari)
            birim_fiyat_giris.textChanged.connect(hesapla_satis_miktari)

            butonlar = QHBoxLayout()
            kaydet_butonu = QPushButton("Kaydet")
            iptal_butonu = QPushButton("Iptal")
            butonlar.addWidget(kaydet_butonu)
            butonlar.addWidget(iptal_butonu)
            yerlesim.addRow(butonlar)
            dialog.setLayout(yerlesim)

            def satis_guncelle():
                try:
                    ay_str = f"{ay_secim.currentText()}-{yil_secim.currentText()}"  # "03-2025" (MM-YYYY formati)
                    self.loglayici.debug(f"Satis guncelleme - Gonderilen Ay degeri: '{ay_str}' (MM-YYYY formati)")
                    
                    # Satış miktarı kontrolü
                    satis_miktari = float(satis_miktari_giris.text().replace(',', '.'))
                    if satis_miktari <= 0:
                        raise ValueError("Satis miktari pozitif bir sayi olmali.")
                    
                    # Miktar ve birim fiyat kontrolü
                    miktar = float(miktar_giris.text().replace(',', '.'))
                    birim_fiyat = float(birim_fiyat_giris.text().replace(',', '.'))
                    
                    if miktar <= 0:
                        raise ValueError("Miktar pozitif bir sayi olmali.")
                    if birim_fiyat <= 0:
                        raise ValueError("Birim fiyat pozitif bir sayi olmali.")
                    
                    if not ana_musteri_giris.currentText():
                        raise ValueError("Ana Musteri secimi zorunludur.")
                    
                    yeni_bilgiler = {
                        "Ana Musteri": ana_musteri_giris.currentText(),
                        "Alt Musteri": alt_musteri_giris.currentText() if alt_musteri_giris.currentText() != "Yok" else None,
                        "Satis Temsilcisi": satisci_giris.currentText(),
                        "Ay": ay_str,
                        "Urun Kodu": urun_kodu_giris.text(),
                        "Urun Adi": urun_adi_giris.text(),
                        "Miktar": miktar,
                        "Birim Fiyat": birim_fiyat,
                        "Satis Miktari": satis_miktari,
                        "Para Birimi": para_birimi_giris.currentText()
                    }
                    
                    # Duzeltme: Mevcut sutunlara gore guncelleme yap
                    for col, value in yeni_bilgiler.items():
                        if col in self.services.data_manager.satislar_df.columns:
                            self.services.data_manager.satislar_df.at[row, col] = value
                    
                    self.services.data_manager.repository.save(self.services.data_manager.satislar_df, "sales")  # Satislari kaydetme
                    
                    # Musterinin son satin alma tarihini guncelle
                    musteri_adi = yeni_bilgiler["Ana Musteri"]
                    self.services.data_manager.musteriler_df.loc[
                        self.services.data_manager.musteriler_df["Musteri Adi"] == musteri_adi,
                        "Son Satin Alma Tarihi"
                    ] = ay_str
                    self.services.data_manager.repository.save(self.services.data_manager.musteriler_df, "customers")  # Musterileri kaydetme
                    self.satis_tablosu_guncelle()
                    self.musteri_tablosu_guncelle()
                    
                    # Gosterge panelini guncelle
                    if hasattr(self, 'gosterge_paneli_guncelle'):
                        self.gosterge_paneli_guncelle()
                    
                    # Olay yayinla
                    self.data_updated_signal.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_duzenle"}))
                    
                    dialog.accept()
                    self.loglayici.info(f"Satis guncellendi: {yeni_bilgiler['Ana Musteri']} - {yeni_bilgiler.get('Alt Musteri', 'Yok')} - {yeni_bilgiler['Satis Miktari']} {yeni_bilgiler['Para Birimi']}")
                except ValueError as ve:
                    QMessageBox.warning(self, "Uyari", str(ve))
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Satis guncellenirken hata: {str(e)}")
                    self.loglayici.error(f"Satis guncelleme hatasi: {str(e)}")

            kaydet_butonu.clicked.connect(satis_guncelle)
            iptal_butonu.clicked.connect(dialog.reject)
            dialog.exec()
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek icin bir satis secin.")

    def satis_sil(self):
        selected_items = self.satis_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            musteri_adi = self.satis_tablosu.item(row, 0).text()
            ay = self.satis_tablosu.item(row, 3).text()
            onay = QMessageBox.question(self, "Onay", f"{musteri_adi} - {ay} satis kaydini silmek istediginize emin misiniz?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if onay == QMessageBox.StandardButton.Yes:
                self.satis_worker = SatisSilmeWorker(self.services, row)  # Yeni worker
                self.satis_worker.tamamlandi.connect(lambda: self._satis_sil_tamamlandi(row))
                self.satis_worker.hata.connect(self._islem_hata)
                self.satis_worker.start()
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir satis secin.")

    def ziyaret_planlama_olustur(self):
        """Ziyaret planlama sekmesini olusturur"""
        ziyaret_tab = QWidget()
        ziyaret_layout = QVBoxLayout()
        
        # Butonlar
        buton_layout = QHBoxLayout()
        
        ekle_butonu = QPushButton("Yeni Ziyaret Ekle")
        ekle_butonu.clicked.connect(self.ziyaret_ekle)
        buton_layout.addWidget(ekle_butonu)
        
        duzenle_butonu = QPushButton("Ziyaret Duzenle")
        duzenle_butonu.clicked.connect(self.ziyaret_duzenle)
        buton_layout.addWidget(duzenle_butonu)
        
        sil_butonu = QPushButton("Ziyaret Sil")
        sil_butonu.clicked.connect(self.ziyaret_sil)
        buton_layout.addWidget(sil_butonu)
        
        # Arama kutusu
        arama_layout = QHBoxLayout()
        arama_label = QLabel("Musteri Ara:")
        self.ziyaret_arama_kutusu = QLineEdit()
        self.ziyaret_arama_kutusu.setPlaceholderText("Musteri adi girin...")
        self.ziyaret_arama_kutusu.textChanged.connect(self.ziyaret_ara)
        arama_layout.addWidget(arama_label)
        arama_layout.addWidget(self.ziyaret_arama_kutusu)
        
        # Tablo
        self.ziyaret_tablosu = QTableWidget()
        self.ziyaret_tablosu.setColumnCount(7)  # Sutun sayisini 7'ye guncelle
        self.ziyaret_tablosu.setHorizontalHeaderLabels(["Musteri Adi", "Satis Temsilcisi", "Tarih", "Saat", "Ziyaret Konusu", "Notlar", "Durum"])
        self.ziyaret_tablosu.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ziyaret_tablosu.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ziyaret_tablosu.setAlternatingRowColors(True)
        
        # Durum filtreleme
        filtre_layout = QHBoxLayout()
        filtre_label = QLabel("Durum Filtrele:")
        self.durum_filtre_combo = QComboBox()
        self.durum_filtre_combo.addItems(["Tumu", "Planlanmis", "Tamamlandi", "Iptal Edildi", "Ertelendi"])
        self.durum_filtre_combo.currentTextChanged.connect(self.ziyaret_filtrele)
        filtre_layout.addWidget(filtre_label)
        filtre_layout.addWidget(self.durum_filtre_combo)
        filtre_layout.addStretch()
        
        # Layout'a ekle
        ziyaret_layout.addLayout(buton_layout)
        ziyaret_layout.addLayout(arama_layout)
        ziyaret_layout.addLayout(filtre_layout)
        ziyaret_layout.addWidget(self.ziyaret_tablosu)
        
        ziyaret_tab.setLayout(ziyaret_layout)
        
        # Ziyaret tablosunu guncelle
        self.ziyaret_tablosu_guncelle()
        
        # Sekmeyi ana sekme widget'ina ekle
        self.sekme_widget.addTab(ziyaret_tab, "Ziyaret Takibi")
        
        return ziyaret_tab

    def ziyaret_tablosu_guncelle(self):
        try:
            # Ziyaret tablosu nesnesinin var olup olmadigini kontrol et
            if not hasattr(self, 'ziyaret_tablosu') or self.ziyaret_tablosu is None:
                return
                
            if self.services.data_manager.ziyaretler_df is None or self.services.data_manager.ziyaretler_df.empty:
                self.ziyaret_tablosu.setRowCount(0)
                self.ziyaret_tablosu.setColumnCount(0)
                return
            
            # Sutun basliklarini ayarla
            sutunlar = ["Musteri Adi", "Satis Temsilcisi", "Tarih", "Saat", "Ziyaret Konusu", "Notlar", "Durum"]
            self.ziyaret_tablosu.setColumnCount(len(sutunlar))
            self.ziyaret_tablosu.setHorizontalHeaderLabels(sutunlar)
            
            # Verileri tabloya ekle
            self.ziyaret_tablosu.setRowCount(len(self.services.data_manager.ziyaretler_df))
            for i, (_, ziyaret) in enumerate(self.services.data_manager.ziyaretler_df.iterrows()):
                # Musteri Adi
                self.ziyaret_tablosu.setItem(i, 0, QTableWidgetItem(str(ziyaret.get("Musteri Adi", ""))))
                
                # Satis Temsilcisi
                self.ziyaret_tablosu.setItem(i, 1, QTableWidgetItem(str(ziyaret.get("Satis Temsilcisi", ""))))
                
                # Tarih - Eski "Ziyaret Tarihi" alanini da kontrol et
                tarih = ziyaret.get("Tarih", ziyaret.get("Ziyaret Tarihi", ""))
                self.ziyaret_tablosu.setItem(i, 2, QTableWidgetItem(str(tarih)))
                
                # Saat
                self.ziyaret_tablosu.setItem(i, 3, QTableWidgetItem(str(ziyaret.get("Saat", ""))))
                
                # Ziyaret Konusu
                self.ziyaret_tablosu.setItem(i, 4, QTableWidgetItem(str(ziyaret.get("Ziyaret Konusu", ""))))
                
                # Notlar
                notlar = str(ziyaret.get("Notlar", ""))
                # Notlar cok uzunsa kisalt
                if len(notlar) > 50:
                    notlar = notlar[:47] + "..."
                self.ziyaret_tablosu.setItem(i, 5, QTableWidgetItem(notlar))
                
                # Durum
                self.ziyaret_tablosu.setItem(i, 6, QTableWidgetItem(str(ziyaret.get("Durum", "Planlanmis"))))
                
                # Durum sutununa gore renklendirme
                durum = str(ziyaret.get("Durum", "Planlanmis"))
                if durum == "Tamamlandi":
                    for j in range(self.ziyaret_tablosu.columnCount()):
                        item = self.ziyaret_tablosu.item(i, j)
                        if item:
                            item.setBackground(QColor(200, 255, 200))  # Acik yesil
                elif durum == "Iptal Edildi":
                    for j in range(self.ziyaret_tablosu.columnCount()):
                        item = self.ziyaret_tablosu.item(i, j)
                        if item:
                            item.setBackground(QColor(255, 200, 200))  # Acik kirmizi
                elif durum == "Ertelendi":
                    for j in range(self.ziyaret_tablosu.columnCount()):
                        item = self.ziyaret_tablosu.item(i, j)
                        if item:
                            item.setBackground(QColor(255, 255, 200))  # Acik sari
            
            # Sutunlari otomatik genislige ayarla
            self.ziyaret_tablosu.resizeColumnsToContents()
            
            # Notlar sutununu biraz daha genis yap
            self.ziyaret_tablosu.setColumnWidth(5, 150)
            
        except Exception as e:
            self.loglayici.error(f"Ziyaret tablosu guncellenirken hata: {str(e)}")
            # QMessageBox.critical(self, "Hata", f"Ziyaret tablosu guncellenirken hata: {str(e)}")

    def ziyaret_ekle(self):
        if not hasattr(self.services.data_manager, 'musteriler_df') or self.services.data_manager.musteriler_df is None or self.services.data_manager.musteriler_df.empty:
            QMessageBox.warning(self, "Uyari", "Once en az bir musteri ekleyin.")
            return
        if not hasattr(self.services.data_manager, 'satiscilar_df') or self.services.data_manager.satiscilar_df is None or self.services.data_manager.satiscilar_df.empty:
            QMessageBox.warning(self, "Uyari", "Once en az bir satisci ekleyin.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Ziyaret Planla")
        yerlesim = QFormLayout()

        musteri_giris = QComboBox()
        musteri_giris.addItems(self.services.data_manager.musteriler_df["Musteri Adi"].astype(str).tolist())
        satisci_giris = QListWidget()
        satisci_giris.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        satisci_giris.addItems(self.services.data_manager.satiscilar_df["Isim"].astype(str).tolist())
        tarih_giris = QDateEdit()
        tarih_giris.setDate(QDate.currentDate())
        saat_giris = QLineEdit()
        saat_giris.setPlaceholderText("HH:MM (Orn: 14:30)")
        konu_giris = QLineEdit()
        notlar_giris = QTextEdit()
        notlar_giris.setMaximumHeight(100)
        durum_giris = QComboBox()
        durum_giris.addItems(["Planlanmis", "Tamamlandi", "Iptal Edildi", "Ertelendi"])

        yerlesim.addRow("Musteri:", musteri_giris)
        yerlesim.addRow("Satis Muhendisleri:", satisci_giris)
        yerlesim.addRow("Ziyaret Tarihi:", tarih_giris)
        yerlesim.addRow("Ziyaret Saati:", saat_giris)
        yerlesim.addRow("Ziyaret Konusu:", konu_giris)
        yerlesim.addRow("Notlar:", notlar_giris)
        yerlesim.addRow("Durum:", durum_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def ziyaret_kaydet():
            try:
                secili_satismuhendisleri = [item.text() for item in satisci_giris.selectedItems()]
                if not secili_satismuhendisleri:
                    raise ValueError("En az bir satis muhendisi secmelisiniz.")
                if not konu_giris.text().strip():
                    raise ValueError("Ziyaret konusu bos birakilamaz.")
                saat = saat_giris.text().strip()
                if saat and not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', saat):
                    raise ValueError("Saat formati gecersiz. HH:MM formatinda giriniz.")
                yeni_ziyaret = {
                    "Musteri Adi": musteri_giris.currentText(),
                    "Satis Temsilcisi": ", ".join(secili_satismuhendisleri),
                    "Tarih": tarih_giris.date().toString("yyyy-MM-dd"),
                    "Saat": saat,
                    "Ziyaret Konusu": konu_giris.text().strip(),
                    "Notlar": notlar_giris.toPlainText().strip(),
                    "Durum": durum_giris.currentText()
                }
                self.worker = ZiyaretEklemeWorker(self.services, yeni_ziyaret)  # Yeni worker
                self.worker.tamamlandi.connect(lambda: self._ziyaret_ekle_tamamlandi(dialog))
                self.worker.hata.connect(self._islem_hata)
                self.worker.start()
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))

        kaydet_butonu.clicked.connect(ziyaret_kaydet)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def ziyaret_sil(self):
        selected_items = self.ziyaret_tablosu.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            musteri_adi = self.ziyaret_tablosu.item(row, 0).text()
            tarih = self.ziyaret_tablosu.item(row, 2).text()
            onay = QMessageBox.question(self, "Onay", f"{musteri_adi} - {tarih} ziyaretini silmek istediginize emin misiniz?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if onay == QMessageBox.StandardButton.Yes:
                self.worker = ZiyaretSilmeWorker(self.services, row)  # Yeni worker
                self.worker.tamamlandi.connect(lambda: self._ziyaret_sil_tamamlandi(row))
                self.worker.hata.connect(self._islem_hata)
                self.worker.start()
        else:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir ziyaret secin.")

    def ziyaret_duzenle(self):
        selected_items = self.ziyaret_tablosu.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlemek icin bir ziyaret secin.")
            return

        if (self.services.data_manager.musteriler_df is None or  # self.veri_yoneticisi -> self.services.data_manager
            self.services.data_manager.musteriler_df.empty or 
            "Musteri Adi" not in self.services.data_manager.musteriler_df.columns):
            QMessageBox.warning(self, "Uyari", "Musteri listesi bos veya yuklenemedi.")
            return
    
        if (self.services.data_manager.satiscilar_df is None or  # self.veri_yoneticisi -> self.services.data_manager
            self.services.data_manager.satiscilar_df.empty or 
            "Isim" not in self.services.data_manager.satiscilar_df.columns):
            QMessageBox.warning(self, "Uyari", "Satisci listesi bos veya yuklenemedi.")
            return

        row = selected_items[0].row()
        dialog = QDialog(self)
        dialog.setWindowTitle("Ziyaret Duzenle")
        yerlesim = QFormLayout()

        ziyaret = self.services.data_manager.ziyaretler_df.iloc[row]  # self.veri_yoneticisi -> self.services.data_manager
        musteri_giris = QComboBox()
        musteri_giris.addItems(self.services.data_manager.musteriler_df["Musteri Adi"].astype(str).tolist())  # self.veri_yoneticisi -> self.services.data_manager
        musteri_giris.setCurrentText(str(ziyaret["Musteri Adi"]))

        satisci_giris = QListWidget()
        satisci_giris.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        satisci_giris.addItems(self.services.data_manager.satiscilar_df["Isim"].astype(str).tolist())  # self.veri_yoneticisi -> self.services.data_manager
        # Satis temsilcisi bir string listesi degilse (orn: integer ID), donusum ve kontrol
        mevcut_satismuhendisleri = str(ziyaret["Satis Temsilcisi"])  # Once string'e cevir
        if "," in mevcut_satismuhendisleri:  # Eger birden fazla isim iceriyorsa
            mevcut_satismuhendisleri = mevcut_satismuhendisleri.split(", ")
        else:
            mevcut_satismuhendisleri = [mevcut_satismuhendisleri]  # Tek bir isim/ID ise liste yap
        for i in range(satisci_giris.count()):
            item = satisci_giris.item(i)
            if item.text() in mevcut_satismuhendisleri:
                item.setSelected(True)
    
        # Tarih alani
        tarih_giris = QDateEdit()
        tarih_str = ziyaret.get("Tarih", ziyaret.get("Ziyaret Tarihi", ""))
        if tarih_str:
            tarih_giris.setDate(QDate.fromString(tarih_str, "yyyy-MM-dd"))
        else:
            tarih_giris.setDate(QDate.currentDate())
            
        # Saat alani
        saat_giris = QLineEdit()
        saat_giris.setText(str(ziyaret.get("Saat", "")))
        saat_giris.setPlaceholderText("HH:MM (Orn: 14:30)")
        
        # Konu alani
        konu_giris = QLineEdit()
        konu_giris.setText(str(ziyaret.get("Ziyaret Konusu", "")))
        
        # Notlar alani
        notlar_giris = QTextEdit()
        notlar_giris.setPlainText(str(ziyaret.get("Notlar", "")))
        notlar_giris.setMaximumHeight(100)
        
        # Durum alani
        durum_giris = QComboBox()
        durum_giris.addItems(["Planlanmis", "Tamamlandi", "Iptal Edildi", "Ertelendi"])
        mevcut_durum = str(ziyaret.get("Durum", "Planlanmis"))
        index = durum_giris.findText(mevcut_durum)
        if index >= 0:
            durum_giris.setCurrentIndex(index)

        yerlesim.addRow("Musteri:", musteri_giris)
        yerlesim.addRow("Satis Muhendisleri:", satisci_giris)
        yerlesim.addRow("Ziyaret Tarihi:", tarih_giris)
        yerlesim.addRow("Ziyaret Saati:", saat_giris)
        yerlesim.addRow("Ziyaret Konusu:", konu_giris)
        yerlesim.addRow("Notlar:", notlar_giris)
        yerlesim.addRow("Durum:", durum_giris)

        butonlar = QHBoxLayout()
        kaydet_butonu = QPushButton("Kaydet")
        iptal_butonu = QPushButton("Iptal")
        butonlar.addWidget(kaydet_butonu)
        butonlar.addWidget(iptal_butonu)
        yerlesim.addRow(butonlar)
        dialog.setLayout(yerlesim)

        def ziyaret_guncelle():
            try:
                secili_satismuhendisleri = [item.text() for item in satisci_giris.selectedItems()]
                if not secili_satismuhendisleri:
                    raise ValueError("En az bir satis muhendisi secmelisiniz.")
                if not konu_giris.text().strip():
                    raise ValueError("Ziyaret konusu bos birakilamaz.")
                
                # Saat formatini kontrol et
                saat = saat_giris.text().strip()
                if saat:
                    import re
                    if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', saat):
                        raise ValueError("Saat formati gecersiz. Lutfen HH:MM formatinda giriniz (Orn: 14:30)")
            
                yeni_bilgiler = {
                    "Musteri Adi": musteri_giris.currentText(),
                    "Satis Temsilcisi": ", ".join(secili_satismuhendisleri),
                    "Tarih": tarih_giris.date().toString("yyyy-MM-dd"),
                    "Saat": saat_giris.text().strip(),
                    "Notlar": notlar_giris.toPlainText().strip(),
                    "Durum": durum_giris.currentText(),
                    "Ziyaret Tarihi": tarih_giris.date().toString("yyyy-MM-dd"),  # Eski alan icin uyumluluk
                    "Ziyaret Konusu": konu_giris.text().strip()  # Eski alan icin uyumluluk
                }
                # Duzeltme: self.veri_yoneticisi ve self.repository.save yerine services kullaniyoruz
                self.services.data_manager.ziyaretler_df.iloc[row] = pd.Series(yeni_bilgiler)
                self.services.data_manager.repository.save(self.services.data_manager.ziyaretler_df, "visits")  # Veritabanini kaydetme
                self.ziyaret_tablosu_guncelle()
                dialog.accept()
                self.loglayici.info(f"Ziyaret guncellendi: {yeni_bilgiler['Musteri Adi']} - {yeni_bilgiler['Satis Temsilcisi']}")
            except ValueError as ve:
                QMessageBox.warning(self, "Uyari", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Ziyaret guncellenirken hata: {str(e)}")
                self.loglayici.error(f"Ziyaret guncelleme hatasi: {str(e)}")

        kaydet_butonu.clicked.connect(ziyaret_guncelle)
        iptal_butonu.clicked.connect(dialog.reject)
        dialog.exec()

    def ziyaret_ara(self):
        """Ziyaret tablosunda musteri adina gore arama yapar"""
        aranan_metin = self.ziyaret_arama_kutusu.text().lower()
        durum_filtresi = self.durum_filtre_combo.currentText()
        
        for i in range(self.ziyaret_tablosu.rowCount()):
            musteri_adi = self.ziyaret_tablosu.item(i, 0).text().lower()
            durum = self.ziyaret_tablosu.item(i, 6).text()
            
            # Hem arama metnine hem de durum filtresine gore kontrol et
            arama_eslesme = aranan_metin == "" or aranan_metin in musteri_adi
            durum_eslesme = durum_filtresi == "Tumu" or durum_filtresi == durum
            
            self.ziyaret_tablosu.setRowHidden(i, not (arama_eslesme and durum_eslesme))
    
    def ziyaret_filtrele(self):
        """Ziyaret tablosunu duruma gore filtreler"""
        # Mevcut arama metnini de dikkate alarak filtreleme yap
        self.ziyaret_ara()

    def _islem_hata(self, hata_mesaji):
        """Worker'dan gelen hata mesajlarini kullaniciya gosterir."""
        QMessageBox.critical(self, "Hata", str(hata_mesaji))
        self.loglayici.error(f"Islem sirasinda hata: {hata_mesaji}")
        
    def _satis_ekle_tamamlandi(self, dialog, musteri_adi, ay):
        """Satis ekleme islemi tamamlandiginda cagrilir."""
        dialog.accept()
        self.satis_tablosu_guncelle()
        QMessageBox.information(self, "Bilgi", f"{musteri_adi} icin {ay} ayina satis basariyla eklendi.")
        self.loglayici.info(f"Satis eklendi: {musteri_adi}, {ay}")
        # Veri guncellendi sinyali gonder
        if hasattr(self, 'event_manager') and self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "add"}))

    def _ziyaret_ekle_tamamlandi(self, dialog):
        """Ziyaret ekleme islemi tamamlandiginda cagrilir."""
        dialog.accept()
        self.ziyaret_tablosu_guncelle()
        QMessageBox.information(self, "Bilgi", "Ziyaret basariyla eklendi.")
        self.loglayici.info("Ziyaret eklendi")
        # Veri guncellendi sinyali gonder
        if hasattr(self, 'event_manager') and self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "visits", "action": "add"}))

    def _satis_sil_tamamlandi(self, row):
        """Satis silme islemi tamamlandiginda cagrilir."""
        self.satis_tablosu_guncelle()
        QMessageBox.information(self, "Bilgi", "Satis basariyla silindi.")
        self.loglayici.info(f"Satis silindi: Satir {row}")
        # Veri guncellendi sinyali gonder
        if hasattr(self, 'event_manager') and self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "delete"}))
            
    def _ziyaret_sil_tamamlandi(self, row):
        """Ziyaret silme islemi tamamlandiginda cagrilir."""
        self.ziyaret_tablosu_guncelle()
        QMessageBox.information(self, "Bilgi", "Ziyaret basariyla silindi.")
        self.loglayici.info(f"Ziyaret silindi: Satir {row}")
        # Veri guncellendi sinyali gonder
        if hasattr(self, 'event_manager') and self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "visits", "action": "delete"}))
