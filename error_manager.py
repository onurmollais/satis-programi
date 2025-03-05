# -*- coding: utf-8 -*-
"""
Hata yonetimi modulu.

Bu modul, uygulama genelinde hata yonetimi, raporlama ve kullanici bilgilendirme
islemlerini gelismis ozelliklerle gerceklestirir.
"""

from typing import Dict, Optional, List, Callable
from events import Event, EventManager
import logging
import sys
import traceback
import json
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from collections import defaultdict

class CRMError(Exception):
    """CRM uygulamasi icin temel hata sinifi."""
    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

class DatabaseError(CRMError):
    """Veritabani islemleri sirasinda olusan hatalari temsil eder."""
    pass

class FileOperationError(CRMError):
    """Dosya islemleri sirasinda olusan hatalari temsil eder."""
    pass

class ValidationError(CRMError):
    """Veri dogrulama islemleri sirasinda olusan hatalari temsil eder."""
    pass

class NetworkError(CRMError):
    """Ag islemleri sirasinda olusan hatalari temsil eder."""
    pass

class ErrorManager:
    """
    Gelismis merkezi hata yonetimi sinifi.
    
    Hatalari loglar, cesitli bildirimlerle kullaniciya sunar, istatistikleri tutar ve global hata yakalamayi saglar.
    """
    
    HATA_MESAJLARI = {
        "DB001": {"baslik": "Veritabani Baglanti Hatasi", "aciklama": "Veritabanina baglanti saglanamadi.", 
                  "cozum_onerileri": ["Internet baglantinizi kontrol edin", "Veritabani sunucusunun calistigini dogrulayin"]},
        "DB002": {"baslik": "Tablo Bulunamadi", "aciklama": "Islem yapilmak istenen tablo veritabaninda bulunamadi.", 
                  "cozum_onerileri": ["Veritabani yapisini kontrol edin", "Tablonun dogru isimle olusturuldugunu dogrulayin"]},
        "DB003": {"baslik": "Veri Kaydetme Hatasi", "aciklama": "Veriler veritabanina kaydedilemedi.", 
                  "cozum_onerileri": ["Disk alanini kontrol edin", "Veritabani izinlerini kontrol edin"]},
        "FILE001": {"baslik": "Dosya Bulunamadi", "aciklama": "Islem yapilmak istenen dosya bulunamadi.", 
                    "cozum_onerileri": ["Dosya yolunu kontrol edin", "Dosyanin var oldugundan emin olun"]},
        "FILE002": {"baslik": "Dosya Erisim Hatasi", "aciklama": "Dosyaya erisim saglanamadi.", 
                    "cozum_onerileri": ["Dosya izinlerini kontrol edin", "Yonetici haklariyla calistirmayi deneyin"]},
        "FILE003": {"baslik": "Dosya Formati Hatasi", "aciklama": "Dosya formati desteklenmiyor veya bozuk.", 
                    "cozum_onerileri": ["Dosya formatini kontrol edin", "Desteklenen formatlari kullanin"]},
        "DATA001": {"baslik": "Gecersiz Veri Formati", "aciklama": "Girilen veri beklenen formata uygun degil.", 
                    "cozum_onerileri": ["Veri formatini kontrol edin", "Gerekli alanlari dogru doldurun"]},
        "DATA002": {"baslik": "Zorunlu Alan Eksik", "aciklama": "Zorunlu alanlar doldurulmamis.", 
                    "cozum_onerileri": ["Tum zorunlu alanlari doldurun", "Formu kontrol edin"]},
        "DATA003": {"baslik": "Veri Tutarsizligi", "aciklama": "Veriler arasinda tutarsizlik tespit edildi.", 
                    "cozum_onerileri": ["Veri butunlugunu kontrol edin", "Iliskili tablolari kontrol edin"]},
        "NET001": {"baslik": "Internet Baglantisi Yok", "aciklama": "Internet baglantisi kurulamadi.", 
                   "cozum_onerileri": ["Internet baglantinizi kontrol edin", "Proxy ayarlarinizi kontrol edin"]},
        "NET002": {"baslik": "Sunucu Baglanti Hatasi", "aciklama": "Uzak sunucuya baglanilamadi.", 
                   "cozum_onerileri": ["Sunucunun calisir durumda oldugunu kontrol edin", "VPN baglantinizi kontrol edin"]},
        "NET003": {"baslik": "Zaman Asimi", "aciklama": "Islem zaman asimina ugradi.", 
                   "cozum_onerileri": ["Internet hizinizi kontrol edin", "Daha sonra tekrar deneyin"]},
        "SYS001": {"baslik": "Bilinmeyen Sistem Hatasi", "aciklama": "Beklenmeyen bir sistem hatasi olustu.", 
                   "cozum_onerileri": ["Uygulamayi yeniden baslatin", "Teknik destek ile iletisime gecin"]}
    }
    
    def __init__(self, log_dosyasi: str = "hatalar.log", event_manager: Optional[EventManager] = None, parent=None):
        """
        Hata yöneticisini başlatır ve loglama sistemini yapılandırır.
        
        Args:
            log_dosyasi: Hata loglarının kaydedileceği dosya
            event_manager: Olay yönetimi nesnesi (isteğe bağlı)
            parent: PyQt6 üst penceresi (bildirimler için)
        """
        self.event_manager = event_manager
        self.parent = parent
        
        # Loglama yapılandırması
        self.logger = logging.getLogger("ErrorManager")
        self.logger.setLevel(logging.ERROR)
        
        # Dosya handler
        file_handler = logging.FileHandler(log_dosyasi)
        file_handler.setLevel(logging.ERROR)
        
        # Konsol handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        
        # Log formatı
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Hata istatistikleri
        self.error_stats = defaultdict(int)
        
        # Global exception handler
        sys.excepthook = self.global_exception_handler
    
    def handle_error(self, hata_kodu: str, ek_detaylar: Optional[str] = None, exception: Optional[Exception] = None, 
                    raise_error: bool = True, show_notification: bool = True, notification_type: str = "error") -> Dict:
        hata_mesaji = self.HATA_MESAJLARI.get(hata_kodu, {
            "baslik": "Bilinmeyen Hata",
            "aciklama": f"Hata kodu: {hata_kodu}",
            "cozum_onerileri": ["Teknik destek ile iletisime gecin"]
        }).copy()
        
        tam_mesaj = f"{hata_mesaji['baslik']} - {hata_mesaji['aciklama']}"
        bildirim_mesaji = hata_mesaji["aciklama"]
        detay_mesaj = ""
        
        if ek_detaylar:
            tam_mesaj += f" Detay: {ek_detaylar}"
            bildirim_mesaji += f"\nDetay: {ek_detaylar}"
            detay_mesaj += f"Ek Detaylar: {ek_detaylar}"
        
        if exception:
            tam_mesaj += f"\nOrijinal Hata: {str(exception)}\n{traceback.format_exc()}"
            detay_mesaj += f"\nOrijinal Hata: {str(exception)}\n{traceback.format_exc()}"
        
        self.logger.error(tam_mesaj)
        self.error_stats[hata_kodu] += 1
        
        if self.event_manager:
            self.event_manager.emit(Event("Error", {
                "code": hata_kodu,
                "title": hata_mesaji["baslik"],
                "description": hata_mesaji["aciklama"],
                "solutions": hata_mesaji["cozum_onerileri"],
                "details": ek_detaylar,
                "exception": str(exception) if exception else None,
                "timestamp": datetime.now().isoformat()
            }))
        
        if show_notification and self.parent:
            self._show_notification(
                baslik=hata_mesaji["baslik"],
                mesaj=bildirim_mesaji,
                detay=f"Çözüm Önerileri:\n" + "\n".join(hata_mesaji["cozum_onerileri"]) + (f"\n\n{detay_mesaj}" if detay_mesaj else ""),
                notification_type=notification_type
            )
        
        hata_sinifi = self._get_error_class(hata_kodu)
        if raise_error:
            raise hata_sinifi(
                message=hata_mesaji["aciklama"],
                error_code=hata_kodu,
                details={"title": hata_mesaji["baslik"], "solutions": hata_mesaji["cozum_onerileri"], "extra": ek_detaylar}
            )
        
        return hata_mesaji
    
    def _get_error_class(self, hata_kodu: str) -> type:
        """Hata koduna göre uygun hata sınıfını döndürür."""
        if hata_kodu.startswith("DB"): return DatabaseError
        elif hata_kodu.startswith("FILE"): return FileOperationError
        elif hata_kodu.startswith("DATA"): return ValidationError
        elif hata_kodu.startswith("NET"): return NetworkError
        return CRMError
    
    def _show_notification(self, baslik: str, mesaj: str, detay: Optional[str] = None, notification_type: str = "error"):
        """Kullanıcıya özelleştirilmiş bildirim gösterir (ana iş parçacığında)."""
        def show_in_main_thread():
            msg_box = QMessageBox(self.parent)
            msg_box.setWindowTitle(baslik)
            
            if notification_type == "info":
                msg_box.setIcon(QMessageBox.Icon.Information)
            elif notification_type == "warning":
                msg_box.setIcon(QMessageBox.Icon.Warning)
            elif notification_type == "question":
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            else:
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.addButton("Sorunu Rapor Et", QMessageBox.ButtonRole.ActionRole)
            
            msg_box.setText(mesaj)
            if detay:
                msg_box.setDetailedText(detay)
            
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok if notification_type != "question" else msg_box.standardButtons())
            result = msg_box.exec()
            
            if msg_box.clickedButton() and msg_box.clickedButton().text() == "Sorunu Rapor Et":
                self._show_report_dialog(baslik, mesaj, detay)
            return result == QMessageBox.StandardButton.Yes if notification_type == "question" else None
        
        # Asenkron çalıştırma
        QTimer.singleShot(0, lambda: self._handle_notification_response(msg_box, notification_type))
    
    def _handle_notification_response(self, msg_box: QMessageBox, notification_type: str):
        """Bildirim yanıtını işler."""
        result = msg_box.exec()
        
        if notification_type == "question":
            return result == QMessageBox.StandardButton.Yes
        
        if msg_box.clickedButton() and msg_box.clickedButton().text() == "Sorunu Rapor Et":
            self._show_report_dialog(msg_box.windowTitle(), msg_box.text(), msg_box.detailedText())
    
    def _show_report_dialog(self, baslik: str, mesaj: str, detay: str):
        """Kullanıcıdan hata raporu alma diyaloğu gösterir."""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Hata Raporu Gönder")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Lütfen hatayla ilgili ek bilgiyi aşağıya girin:"))
        rapor_edit = QTextEdit()
        rapor_edit.setText(f"Hata: {baslik}\nMesaj: {mesaj}\nDetay:\n{detay}")
        layout.addWidget(rapor_edit)
        
        gonder_button = QPushButton("Raporu Gönder")
        gonder_button.clicked.connect(lambda: self._submit_report(dialog, rapor_edit.toPlainText()))
        layout.addWidget(gonder_button)
        
        dialog.exec()
    
    def _submit_report(self, dialog: QDialog, rapor: str):
        """Kullanıcı raporunu işler."""
        self.logger.info(f"Kullanıcı Raporu: {rapor}")
        if self.event_manager:
            self.event_manager.emit(Event("UserErrorReport", {"report": rapor, "timestamp": datetime.now().isoformat()}))
        dialog.accept()
        QMessageBox.information(self.parent, "Başarılı", "Hata raporu gönderildi. Teşekkür ederiz!")
    
    def cozum_onerisi_ekle(self, hata_kodu: str, oneri: str) -> None:
        """Var olan hata koduna yeni çözüm önerisi ekler."""
        if hata_kodu in self.HATA_MESAJLARI:
            self.HATA_MESAJLARI[hata_kodu]["cozum_onerileri"].append(oneri)
            self.logger.info(f"{hata_kodu} için yeni çözüm önerisi eklendi: {oneri}")
    
    def yeni_hata_tanimla(self, hata_kodu: str, baslik: str, aciklama: str, cozum_onerileri: List[str]) -> None:
        """Yeni bir hata kodu ve mesajlarını tanımlar."""
        self.HATA_MESAJLARI[hata_kodu] = {
            "baslik": baslik,
            "aciklama": aciklama,
            "cozum_onerileri": cozum_onerileri
        }
        self.logger.info(f"Yeni hata tanımlandı: {hata_kodu} - {baslik}")
    
    def global_exception_handler(self, exctype, value, tb):
        """Uygulama genelinde yakalanmamış hataları işler."""
        hata_mesaji = f"Yakalanmamış İstisna: {str(value)}\n{''.join(traceback.format_tb(tb))}"
        self.logger.critical(hata_mesaji)
        
        if self.parent:
            self._show_notification(
                baslik="Sistem Hatası",
                mesaj="Beklenmeyen bir hata oluştu.",
                detay=f"{hata_mesaji}\n\nÇözüm Önerileri:\n- Uygulamayı yeniden başlatın\n- Teknik destek ile iletişime geçin",
                notification_type="error"
            )
        
        if self.event_manager:
            self.event_manager.emit(Event("CriticalError", {
                "code": "SYS001",
                "title": "Sistem Hatası",
                "description": hata_mesaji,
                "solutions": ["Uygulamayı yeniden başlatın", "Teknik destek ile iletişime geçin"]
            }))
        sys.__excepthook__(exctype, value, tb)
    
    def get_error_stats(self) -> Dict[str, int]:
        """Hata istatistiklerini döndürür."""
        return dict(self.error_stats)
    
    def load_error_config(self, config_file: str = "error_config.json"):
        """Hata kodlarını JSON dosyasından yükler."""
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self.HATA_MESAJLARI.update(json.load(f))
            self.logger.info(f"Hata yapılandırması yüklendi: {config_file}")
        except Exception as e:
            self.logger.error(f"Hata yapılandırması yüklenemedi: {str(e)}")

