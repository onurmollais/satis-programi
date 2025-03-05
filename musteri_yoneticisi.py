# -*- coding: utf-8 -*-
import pandas as pd
from typing import Dict, Any
from events import Event, EVENT_DATA_UPDATED

class MusteriYoneticisi:
    """
    Musteri ve ziyaretlerle ilgili islemleri gerceklestiren sinif.
    
    Bu sinif, musteri, ziyaret ve sikayet ile ilgili islemleri gerceklestirir.
    """
    
    def __init__(self, veri_yoneticisi):
        """
        MusteriYoneticisi sinifinin kurucu metodu.
        
        Args:
            veri_yoneticisi: Veri yoneticisi nesnesi
        """
        self.veri_yoneticisi = veri_yoneticisi
        self.repository = veri_yoneticisi.repository
        self.loglayici = veri_yoneticisi.loglayici
        self.event_manager = veri_yoneticisi.event_manager
    
    def musteri_ekle(self, yeni_musteri: Dict[str, Any]) -> None:
        """
        Yeni bir musteri ekler.
        
        Args:
            yeni_musteri: Yeni musteri bilgilerini iceren sozluk
        """
        yeni_musteri_df = pd.DataFrame([yeni_musteri])
        if self.veri_yoneticisi.musteriler_df is None or self.veri_yoneticisi.musteriler_df.empty:
            self.veri_yoneticisi.musteriler_df = yeni_musteri_df
        else:
            self.veri_yoneticisi.musteriler_df = pd.concat([self.veri_yoneticisi.musteriler_df, yeni_musteri_df], ignore_index=True)
        self.repository.save(self.veri_yoneticisi.musteriler_df, "customers")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "musteri_ekle"}))
    
    def musteri_duzenle(self, index: int, guncellenmis_musteri: Dict[str, Any]) -> None:
        """
        Bir musteriyi gunceller.
        
        Args:
            index: Guncellenecek musterinin indeksi
            guncellenmis_musteri: Guncel musteri bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.musteriler_df):
            for key, value in guncellenmis_musteri.items():
                self.veri_yoneticisi.musteriler_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.musteriler_df, "customers")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "musteri_duzenle"}))
    
    def musteri_sil(self, musteri_adi: str) -> None:
        """
        Bir musteriyi siler.
        
        Args:
            musteri_adi: Silinecek musterinin adi
        """
        if self.veri_yoneticisi.musteriler_df is not None and not self.veri_yoneticisi.musteriler_df.empty:
            self.veri_yoneticisi.musteriler_df = self.veri_yoneticisi.musteriler_df[self.veri_yoneticisi.musteriler_df["Musteri Adi"] != musteri_adi]
            self.repository.save(self.veri_yoneticisi.musteriler_df, "customers")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "musteri_sil"}))
    
    def ziyaret_ekle(self, yeni_ziyaret: Dict[str, Any]) -> None:
        """
        Yeni bir ziyaret ekler.
        
        Args:
            yeni_ziyaret: Yeni ziyaret bilgilerini iceren sozluk
        """
        yeni_ziyaret_df = pd.DataFrame([yeni_ziyaret])
        if self.veri_yoneticisi.ziyaretler_df is None or self.veri_yoneticisi.ziyaretler_df.empty:
            self.veri_yoneticisi.ziyaretler_df = yeni_ziyaret_df
        else:
            self.veri_yoneticisi.ziyaretler_df = pd.concat([self.veri_yoneticisi.ziyaretler_df, yeni_ziyaret_df], ignore_index=True)
        self.repository.save(self.veri_yoneticisi.ziyaretler_df, "visits")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "ziyaret_ekle"}))
    
    def ziyaret_duzenle(self, index: int, guncellenmis_ziyaret: Dict[str, Any]) -> None:
        """
        Bir ziyareti gunceller.
        
        Args:
            index: Guncellenecek ziyaretin indeksi
            guncellenmis_ziyaret: Guncel ziyaret bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.ziyaretler_df):
            for key, value in guncellenmis_ziyaret.items():
                self.veri_yoneticisi.ziyaretler_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.ziyaretler_df, "visits")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "ziyaret_duzenle"}))
    
    def ziyaret_sil(self, index: int) -> None:
        """
        Bir ziyareti siler.
        
        Args:
            index: Silinecek ziyaretin indeksi
        """
        if self.veri_yoneticisi.ziyaretler_df is not None and not self.veri_yoneticisi.ziyaretler_df.empty and index >= 0 and index < len(self.veri_yoneticisi.ziyaretler_df):
            self.veri_yoneticisi.ziyaretler_df = self.veri_yoneticisi.ziyaretler_df.drop(index).reset_index(drop=True)
            self.repository.save(self.veri_yoneticisi.ziyaretler_df, "visits")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "ziyaret_sil"}))
    
    def sikayet_ekle(self, yeni_sikayet: Dict[str, Any]) -> None:
        """
        Yeni bir sikayet ekler.
        
        Args:
            yeni_sikayet: Yeni sikayet bilgilerini iceren sozluk
        """
        yeni_sikayet_df = pd.DataFrame([yeni_sikayet])
        if self.veri_yoneticisi.sikayetler_df is None or self.veri_yoneticisi.sikayetler_df.empty:
            self.veri_yoneticisi.sikayetler_df = yeni_sikayet_df
        else:
            self.veri_yoneticisi.sikayetler_df = pd.concat([self.veri_yoneticisi.sikayetler_df, yeni_sikayet_df], ignore_index=True)
        self.repository.save(self.veri_yoneticisi.sikayetler_df, "complaints")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "sikayet_ekle"}))
    
    def sikayet_duzenle(self, index: int, guncellenmis_sikayet: Dict[str, Any]) -> None:
        """
        Bir sikayeti gunceller.
        
        Args:
            index: Guncellenecek sikayetin indeksi
            guncellenmis_sikayet: Guncel sikayet bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.sikayetler_df):
            for key, value in guncellenmis_sikayet.items():
                self.veri_yoneticisi.sikayetler_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.sikayetler_df, "complaints")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "sikayet_duzenle"}))
    
    def sikayet_sil(self, index: int) -> None:
        """
        Bir sikayeti siler.
        
        Args:
            index: Silinecek sikayetin indeksi
        """
        if self.veri_yoneticisi.sikayetler_df is not None and not self.veri_yoneticisi.sikayetler_df.empty and index >= 0 and index < len(self.veri_yoneticisi.sikayetler_df):
            self.veri_yoneticisi.sikayetler_df = self.veri_yoneticisi.sikayetler_df.drop(index).reset_index(drop=True)
            self.repository.save(self.veri_yoneticisi.sikayetler_df, "complaints")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "sikayet_sil"})) 