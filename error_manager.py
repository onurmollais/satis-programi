"""
Hata yonetimi modulu.

Bu modul, uygulama genelinde hata yonetimi, raporlama ve kullanici bilgilendirme
islemlerini gerceklestirir. Ozel hata siniflari ve hata yonetim sinifini icerir.
"""

from typing import Dict, Optional, List
from events import Event, EventManager
import logging

class CRMError(Exception):
    """
    CRM uygulamasi icin temel hata sinifi.
    
    Tum ozel hata siniflari bu siniftan turetilir.
    
    Attributes:
        message: Hata mesaji
        error_code: Benzersiz hata kodu
        details: Hata ile ilgili ek detaylar
    """
    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        """
        Args:
            message: Hata mesaji
            error_code: Benzersiz hata kodu
            details: Hata ile ilgili ek detaylar (varsayilan: None)
        """
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
    Hata yonetimi sinifi - kullanici dostu hata mesajlari ve cozum onerileri sunar.
    
    Bu sinif, uygulama genelinde olusan hatalari yakalar, siniflandirir ve
    kullaniciya anlasilir mesajlar sunar. Ayrica hata kayitlarini tutar ve
    gerektiginde ilgili birimlere bildirim yapar.
    
    Attributes:
        HATA_MESAJLARI (Dict): Hata kodlarina karsilik gelen mesaj ve cozum onerileri
        
    Methods:
        hata_mesaji_olustur(): Hata kodu icin kullanici dostu mesaj olusturur
        hata_bildir(): Hatayi kaydeder ve ilgili birimlere bildirir
        cozum_onerisi_ekle(): Mevcut hata koduna yeni cozum onerisi ekler
        yeni_hata_tanimla(): Sisteme yeni hata kodu ve mesaji ekler
    """
    
    HATA_MESAJLARI = {
        # Veritabani Hatalari
        "DB001": {
            "baslik": "Veritabani Baglanti Hatasi",
            "aciklama": "Veritabanina baglanti saglanamadi.",
            "cozum_onerileri": [
                "Internet baglantinizi kontrol edin",
                "Veritabani sunucusunun calistigini dogrulayin",
                "Guvenlik duvari ayarlarinizi kontrol edin"
            ]
        },
        "DB002": {
            "baslik": "Tablo Bulunamadi",
            "aciklama": "Islem yapilmak istenen tablo veritabaninda bulunamadi.",
            "cozum_onerileri": [
                "Veritabani yapisini kontrol edin",
                "Tablonun dogru isimle olusturuldugundan emin olun",
                "Veritabani guncelleme scriptlerini calistirin"
            ]
        },
        "DB003": {
            "baslik": "Veri Kaydetme Hatasi",
            "aciklama": "Veriler veritabanina kaydedilemedi.",
            "cozum_onerileri": [
                "Disk alanini kontrol edin",
                "Veritabani baglantisini kontrol edin",
                "Veritabani izinlerini kontrol edin"
            ]
        },
        # Dosya Islemleri Hatalari
        "FILE001": {
            "baslik": "Dosya Bulunamadi",
            "aciklama": "Islem yapilmak istenen dosya bulunamadi.",
            "cozum_onerileri": [
                "Dosya yolunu kontrol edin",
                "Dosyanin var oldugundan emin olun",
                "Dosya izinlerini kontrol edin"
            ]
        },
        "FILE002": {
            "baslik": "Dosya Erisim Hatasi",
            "aciklama": "Dosyaya erisim saglanamadi.",
            "cozum_onerileri": [
                "Dosya izinlerini kontrol edin",
                "Dosyanin baska bir program tarafindan kullanilmadigini dogrulayin",
                "Yonetici haklariyla calistirmayi deneyin"
            ]
        },
        "FILE003": {
            "baslik": "Dosya Formati Hatasi",
            "aciklama": "Dosya formati desteklenmiyor veya bozuk.",
            "cozum_onerileri": [
                "Dosya formatini kontrol edin",
                "Dosyanin bozuk olmadigindan emin olun",
                "Desteklenen formatlari kullanin"
            ]
        },
        # Veri Dogrulama Hatalari
        "DATA001": {
            "baslik": "Gecersiz Veri Formati",
            "aciklama": "Girilen veri beklenen formata uygun degil.",
            "cozum_onerileri": [
                "Veri formatini kontrol edin",
                "Gerekli alanlarin dolduruldugundan emin olun",
                "Tarih formatlarinin dogru oldugundan emin olun"
            ]
        },
        "DATA002": {
            "baslik": "Zorunlu Alan Eksik",
            "aciklama": "Zorunlu alanlar doldurulmamis.",
            "cozum_onerileri": [
                "Tum zorunlu alanlari doldurun",
                "Form validasyonunu kontrol edin",
                "Eksik alanlari tamamlayin"
            ]
        },
        "DATA003": {
            "baslik": "Veri Tutarsizligi",
            "aciklama": "Veriler arasinda tutarsizlik tespit edildi.",
            "cozum_onerileri": [
                "Veri bÃ¼tÃ¼nlÃ¼gÃ¼nÃ¼ kontrol edin",
                "Iliskili tablolari kontrol edin",
                "Veri gÃ¼ncelleme islemlerini kontrol edin"
            ]
        },
        # Internet Baglanti Hatalari
        "NET001": {
            "baslik": "Internet Baglantisi Yok",
            "aciklama": "Internet baglantisi kurulamadi.",
            "cozum_onerileri": [
                "Internet baglantinizi kontrol edin",
                "Proxy ayarlarinizi kontrol edin",
                "Offline modda calismayi deneyin"
            ]
        },
        "NET002": {
            "baslik": "Sunucu Baglanti Hatasi",
            "aciklama": "Uzak sunucuya baglanilamadi.",
            "cozum_onerileri": [
                "Sunucunun calisir durumda oldugundan emin olun",
                "Guvenlik duvari ayarlarini kontrol edin",
                "VPN baglantinizi kontrol edin"
            ]
        },
        "NET003": {
            "baslik": "Zaman Asimi",
            "aciklama": "Islem zaman asimina ugradi.",
            "cozum_onerileri": [
                "Internet baglanti hizinizi kontrol edin",
                "Sunucu yukunu kontrol edin",
                "Daha sonra tekrar deneyin"
            ]
        }
    }
    
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager: Optional[EventManager] = None):
        self.loglayici = loglayici or logging.getLogger(__name__)
        self.event_manager = event_manager
        
    def hata_mesaji_olustur(self, hata_kodu: str, ek_detaylar: Optional[str] = None) -> Dict:
        """Hata kodu icin kullanici dostu mesaj olusturur"""
        if hata_kodu not in self.HATA_MESAJLARI:
            return {
                "baslik": "Bilinmeyen Hata",
                "aciklama": f"Hata kodu: {hata_kodu}",
                "cozum_onerileri": ["Teknik destek ile iletisime gecin"]
            }
            
        mesaj = self.HATA_MESAJLARI[hata_kodu].copy()
        if ek_detaylar:
            mesaj["aciklama"] = f"{mesaj['aciklama']} Detay: {ek_detaylar}"
        return mesaj
        
    def hata_bildir(self, hata_kodu: str, ek_detaylar: Optional[str] = None, exception: Optional[Exception] = None) -> None:
        """Hatayi loglar ve kullaniciya bildirir"""
        hata_mesaji = self.hata_mesaji_olustur(hata_kodu, ek_detaylar)
        
        # Hata tipine gore sinif olustur
        hata_sinifi = None
        if hata_kodu.startswith("DB"):
            hata_sinifi = DatabaseError
        elif hata_kodu.startswith("FILE"):
            hata_sinifi = FileOperationError
        elif hata_kodu.startswith("DATA"):
            hata_sinifi = ValidationError
        elif hata_kodu.startswith("NET"):
            hata_sinifi = NetworkError
        else:
            hata_sinifi = CRMError
            
        # Exception detaylarini ekle
        if exception:
            hata_mesaji["aciklama"] += f"\nOrijinal Hata: {str(exception)}"
            
        # Hatayi logla
        self.loglayici.error(
            f"Hata: {hata_mesaji['baslik']} - {hata_mesaji['aciklama']}",
            exc_info=exception is not None
        )
        
        # Event gonder
        if self.event_manager:
            self.event_manager.emit(Event("Error", {
                "code": hata_kodu,
                "title": hata_mesaji["baslik"],
                "description": hata_mesaji["aciklama"],
                "solutions": hata_mesaji["cozum_onerileri"],
                "error_type": hata_sinifi.__name__ if hata_sinifi else "Unknown"
            }))
            
        # Hata nesnesini olustur ve firlat
        if hata_sinifi:
            raise hata_sinifi(
                message=hata_mesaji["aciklama"],
                error_code=hata_kodu,
                details={
                    "title": hata_mesaji["baslik"],
                    "solutions": hata_mesaji["cozum_onerileri"]
                }
            )
            
    def cozum_onerisi_ekle(self, hata_kodu: str, oneri: str) -> None:
        """Var olan hata koduna yeni cozum onerisi ekler"""
        if hata_kodu in self.HATA_MESAJLARI:
            self.HATA_MESAJLARI[hata_kodu]["cozum_onerileri"].append(oneri)
            
    def yeni_hata_tanimla(self, hata_kodu: str, baslik: str, aciklama: str, cozum_onerileri: List[str]) -> None:
        """Yeni bir hata kodu ve mesajlarini tanimlar"""
        self.HATA_MESAJLARI[hata_kodu] = {
            "baslik": baslik,
            "aciklama": aciklama,
            "cozum_onerileri": cozum_onerileri
        } 
