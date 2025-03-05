import os
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from dotenv import load_dotenv
import logging
from events import Event, EventManager

class SifrelemeYoneticisi:
    """
    Hassas verilerin sifrelenmesi ve cozulmesi icin kullanilan sinif.
    
    Bu sinif, verilerin guvenli bir sekilde saklanmasini ve yonetilmesini saglar.
    Fernet simetrik sifreleme kullanir ve anahtarlari guvenli bir sekilde yonetir.
    
    Attributes:
        HASSAS_ALANLAR (Dict): Hangi tablolardaki hangi alanlarin sifrelenmesi gerektigini belirtir
    """
    
    HASSAS_ALANLAR = {
        "musteriler": ["tc_kimlik", "vergi_no", "telefon", "email"],
        "satislar": ["kredi_karti_no", "musteri_notu"],
        "sikayetler": ["musteri_bilgileri"],
        "ziyaretler": ["gorusme_notlari"]
    }
    
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager: Optional[EventManager] = None):
        """
        Args:
            loglayici: Loglama islemleri icin logger nesnesi
            event_manager: Olay yonetimi icin EventManager nesnesi
        """
        load_dotenv()  # .env dosyasindan ortam degiskenlerini yukle
        
        self.loglayici = loglayici or logging.getLogger(__name__)
        self.event_manager = event_manager
        
        # Sifreleme anahtarini olustur veya yukle
        self.anahtar = self._anahtar_yukle_veya_olustur()
        self.fernet = Fernet(self.anahtar)
        
    def _anahtar_yukle_veya_olustur(self) -> bytes:
        """Sifreleme anahtarini yukler veya yeni bir anahtar olusturur"""
        anahtar_dosyasi = os.getenv("SIFRELEME_ANAHTAR_DOSYASI", "sifreleme.key")
        
        if os.path.exists(anahtar_dosyasi):
            with open(anahtar_dosyasi, "rb") as f:
                return f.read()
        
        # Yeni anahtar olustur
        tuz = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=tuz,
            iterations=100000,
        )
        anahtar = base64.urlsafe_b64encode(kdf.derive(os.getenv("MASTER_KEY", "default").encode()))
        
        # Anahtari dosyaya kaydet
        with open(anahtar_dosyasi, "wb") as f:
            f.write(anahtar)
        
        return anahtar
    
    def sifrele(self, veri: str) -> str:
        """Veriyi sifreler"""
        try:
            return self.fernet.encrypt(veri.encode()).decode()
        except Exception as e:
            self.loglayici.error(f"Sifreleme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "ENCRYPTION_001",
                    "message": "Veri sifreleme hatasi"
                }))
            raise
    
    def sifre_coz(self, sifreli_veri: str) -> str:
        """Sifreli veriyi cozer"""
        try:
            return self.fernet.decrypt(sifreli_veri.encode()).decode()
        except Exception as e:
            self.loglayici.error(f"Sifre cozme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "ENCRYPTION_002",
                    "message": "Sifre cozme hatasi"
                }))
            raise
    
    def veri_cercevesi_sifrele(self, df, tablo_adi: str):
        """Veri cercevesindeki hassas alanlari sifreler"""
        if tablo_adi in self.HASSAS_ALANLAR:
            for alan in self.HASSAS_ALANLAR[tablo_adi]:
                if alan in df.columns:
                    df[alan] = df[alan].apply(lambda x: self.sifrele(str(x)) if pd.notna(x) else x)
        return df
    
    def veri_cercevesi_sifre_coz(self, df, tablo_adi: str):
        """Veri cercevesindeki sifreli alanlarin sifresini cozer"""
        if tablo_adi in self.HASSAS_ALANLAR:
            for alan in self.HASSAS_ALANLAR[tablo_adi]:
                if alan in df.columns:
                    df[alan] = df[alan].apply(lambda x: self.sifre_coz(str(x)) if pd.notna(x) else x)
        return df
    
    def yedekleme_sifrele(self, dosya_yolu: str) -> str:
        """Yedekleme dosyasini sifreler"""
        try:
            with open(dosya_yolu, 'rb') as f:
                veri = f.read()
            
            sifreli_veri = self.fernet.encrypt(veri)
            sifreli_dosya = f"{dosya_yolu}.encrypted"
            
            with open(sifreli_dosya, 'wb') as f:
                f.write(sifreli_veri)
                
            return sifreli_dosya
        except Exception as e:
            self.loglayici.error(f"Yedekleme sifreleme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "ENCRYPTION_003",
                    "message": "Yedekleme sifreleme hatasi"
                }))
            raise
    
    def yedekleme_sifre_coz(self, sifreli_dosya: str) -> str:
        """Sifreli yedekleme dosyasinin sifresini cozer"""
        try:
            with open(sifreli_dosya, 'rb') as f:
                sifreli_veri = f.read()
            
            veri = self.fernet.decrypt(sifreli_veri)
            cozulmus_dosya = sifreli_dosya.replace('.encrypted', '')
            
            with open(cozulmus_dosya, 'wb') as f:
                f.write(veri)
                
            return cozulmus_dosya
        except Exception as e:
            self.loglayici.error(f"Yedekleme sifre cozme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "ENCRYPTION_004", 
                    "message": "Yedekleme sifre cozme hatasi"
                }))
            raise 
