# -*- coding: utf-8 -*-
import pandas as pd
from typing import Dict, Any
from events import Event, EVENT_DATA_UPDATED

class UrunYoneticisi:
    """
    Urun, hammadde ve BOM ile ilgili islemleri gerceklestiren sinif.
    
    Bu sinif, hammadde ve urun BOM ile ilgili islemleri gerceklestirir.
    """
    
    def __init__(self, veri_yoneticisi):
        """
        UrunYoneticisi sinifinin kurucu metodu.
        
        Args:
            veri_yoneticisi: Veri yoneticisi nesnesi
        """
        self.veri_yoneticisi = veri_yoneticisi
        self.repository = veri_yoneticisi.repository
        self.loglayici = veri_yoneticisi.loglayici
        self.event_manager = veri_yoneticisi.event_manager
        self.urun_hesaplayici = veri_yoneticisi.urun_hesaplayici
    
    def hammadde_ekle(self, yeni_hammadde: Dict[str, Any]) -> None:
        """
        Yeni bir hammadde ekler.
        
        Args:
            yeni_hammadde: Yeni hammadde bilgilerini iceren sozluk
        """
        yeni_hammadde_df = pd.DataFrame([yeni_hammadde])
        if self.veri_yoneticisi.hammadde_df is None or self.veri_yoneticisi.hammadde_df.empty:
            self.veri_yoneticisi.hammadde_df = yeni_hammadde_df
        else:
            self.veri_yoneticisi.hammadde_df = pd.concat([self.veri_yoneticisi.hammadde_df, yeni_hammadde_df], ignore_index=True)
        self.repository.save(self.veri_yoneticisi.hammadde_df, "hammadde")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "hammadde_ekle"}))
    
    def hammadde_duzenle(self, index: int, yeni_hammadde: Dict[str, Any]) -> None:
        """
        Bir hammaddeyi gunceller.
        
        Args:
            index: Guncellenecek hammaddenin indeksi
            yeni_hammadde: Guncel hammadde bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.hammadde_df):
            for key, value in yeni_hammadde.items():
                self.veri_yoneticisi.hammadde_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.hammadde_df, "hammadde")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "hammadde_duzenle"}))
    
    def hammadde_sil(self, hammadde_kodu: str) -> None:
        """
        Bir hammaddeyi siler.
        
        Args:
            hammadde_kodu: Silinecek hammaddenin kodu
        """
        if self.veri_yoneticisi.hammadde_df is not None and not self.veri_yoneticisi.hammadde_df.empty:
            self.veri_yoneticisi.hammadde_df = self.veri_yoneticisi.hammadde_df[self.veri_yoneticisi.hammadde_df["Hammadde Kodu"] != hammadde_kodu]
            self.repository.save(self.veri_yoneticisi.hammadde_df, "hammadde")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "hammadde_sil"}))
    
    def urun_bom_ekle(self, yeni_urun_bom: Dict[str, Any]) -> None:
        """
        Yeni bir urun BOM ekler.
        
        Args:
            yeni_urun_bom: Yeni urun BOM bilgilerini iceren sozluk
        """
        # Hammadde Adi kontrolu
        if self.veri_yoneticisi.hammadde_df is not None and not self.veri_yoneticisi.hammadde_df.empty:
            hammadde_kodu = yeni_urun_bom.get("Hammadde Kodu")
            if hammadde_kodu:
                hammadde_df = self.veri_yoneticisi.hammadde_df
                hammadde_adi = hammadde_df[hammadde_df["Hammadde Kodu"] == hammadde_kodu]["Hammadde Adi"].values
                if len(hammadde_adi) > 0:
                    yeni_urun_bom["Hammadde Adi"] = hammadde_adi[0]
        
        # Urun Agirligi hesapla
        urun_kodu = yeni_urun_bom.get("Urun Kodu")
        if urun_kodu:
            self.urun_hesaplayici.set_data_frames(self.veri_yoneticisi.hammadde_df, self.veri_yoneticisi.urun_bom_df)
            
            # Yeni BOM'u gecici olarak ekle
            temp_df = pd.DataFrame([yeni_urun_bom])
            if self.veri_yoneticisi.urun_bom_df is None or self.veri_yoneticisi.urun_bom_df.empty:
                temp_urun_bom_df = temp_df
            else:
                temp_urun_bom_df = pd.concat([self.veri_yoneticisi.urun_bom_df, temp_df], ignore_index=True)
            
            # Urun agirligini hesapla
            self.urun_hesaplayici.set_data_frames(self.veri_yoneticisi.hammadde_df, temp_urun_bom_df)
            urun_agirligi = self.urun_hesaplayici.urun_agirligi_hesapla(urun_kodu)
            yeni_urun_bom["Urun Agirligi"] = urun_agirligi
            
            # Urun maliyetini hesapla
            urun_maliyeti = self.urun_hesaplayici.urun_maliyeti_hesapla(urun_kodu)
            yeni_urun_bom["Urun Maliyeti"] = urun_maliyeti
        
        # Veri cercevesine ekle
        yeni_urun_bom_df = pd.DataFrame([yeni_urun_bom])
        if self.veri_yoneticisi.urun_bom_df is None or self.veri_yoneticisi.urun_bom_df.empty:
            self.veri_yoneticisi.urun_bom_df = yeni_urun_bom_df
        else:
            self.veri_yoneticisi.urun_bom_df = pd.concat([self.veri_yoneticisi.urun_bom_df, yeni_urun_bom_df], ignore_index=True)
        
        # Veritabanina kaydet
        self.repository.save(self.veri_yoneticisi.urun_bom_df, "urun_bom")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "urun_bom_ekle"}))
    
    def urun_bom_duzenle(self, index: int, yeni_urun_bom: Dict[str, Any]) -> None:
        """
        Bir urun BOM'u gunceller.
        
        Args:
            index: Guncellenecek urun BOM'un indeksi
            yeni_urun_bom: Guncel urun BOM bilgilerini iceren sozluk
        """
        # Eski urun kodunu al (agirlik guncellemesi icin)
        eski_urun_kodu = None
        if index >= 0 and index < len(self.veri_yoneticisi.urun_bom_df):
            eski_urun_kodu = self.veri_yoneticisi.urun_bom_df.at[index, "Urun Kodu"]
        
        # Hammadde Adi kontrolu
        if self.veri_yoneticisi.hammadde_df is not None and not self.veri_yoneticisi.hammadde_df.empty:
            hammadde_kodu = yeni_urun_bom.get("Hammadde Kodu")
            if hammadde_kodu:
                hammadde_df = self.veri_yoneticisi.hammadde_df
                hammadde_adi = hammadde_df[hammadde_df["Hammadde Kodu"] == hammadde_kodu]["Hammadde Adi"].values
                if len(hammadde_adi) > 0:
                    yeni_urun_bom["Hammadde Adi"] = hammadde_adi[0]
        
        # Guncelleme yap
        if index >= 0 and index < len(self.veri_yoneticisi.urun_bom_df):
            for key, value in yeni_urun_bom.items():
                self.veri_yoneticisi.urun_bom_df.at[index, key] = value
            
            # Urun Agirligi ve Maliyeti guncelle
            urun_kodu = yeni_urun_bom.get("Urun Kodu", eski_urun_kodu)
            if urun_kodu:
                self.urun_agirligi_guncelle(urun_kodu)
                self.urun_maliyeti_guncelle(urun_kodu)
            
            # Eski urun kodu farkli ise, eski urun kodunun agirligini da guncelle
            if eski_urun_kodu and eski_urun_kodu != urun_kodu:
                self.urun_agirligi_guncelle(eski_urun_kodu)
                self.urun_maliyeti_guncelle(eski_urun_kodu)
            
            # Veritabanina kaydet
            self.repository.save(self.veri_yoneticisi.urun_bom_df, "urun_bom")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "urun_bom_duzenle"}))
    
    def urun_bom_sil(self, urun_kodu: str, hammadde_kodu: str) -> None:
        """
        Bir urun BOM'u siler.
        
        Args:
            urun_kodu: Silinecek urun BOM'un urun kodu
            hammadde_kodu: Silinecek urun BOM'un hammadde kodu
        """
        if self.veri_yoneticisi.urun_bom_df is not None and not self.veri_yoneticisi.urun_bom_df.empty:
            # Filtreleme yap
            self.veri_yoneticisi.urun_bom_df = self.veri_yoneticisi.urun_bom_df[
                ~((self.veri_yoneticisi.urun_bom_df["Urun Kodu"] == urun_kodu) & 
                  (self.veri_yoneticisi.urun_bom_df["Hammadde Kodu"] == hammadde_kodu))
            ]
            
            # Veritabanina kaydet
            self.repository.save(self.veri_yoneticisi.urun_bom_df, "urun_bom")
            
            # Urun agirligini guncelle
            self.urun_agirligi_guncelle(urun_kodu)
            self.urun_maliyeti_guncelle(urun_kodu)
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "urun_bom_sil"}))
    
    def urun_agirligi_guncelle(self, urun_kodu: str) -> float:
        """
        Bir urunun agirligini hesaplar ve gunceller.
        
        Args:
            urun_kodu: Agirligi guncellenecek urunun kodu
            
        Returns:
            Urunun guncel agirligi
        """
        self.urun_hesaplayici.set_data_frames(self.veri_yoneticisi.hammadde_df, self.veri_yoneticisi.urun_bom_df)
        urun_agirligi = self.urun_hesaplayici.urun_agirligi_hesapla(urun_kodu)
        
        # Urun BOM tablosunda ilgili urunun agirligini guncelle
        self.veri_yoneticisi.urun_bom_df.loc[self.veri_yoneticisi.urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Agirligi"] = urun_agirligi
        
        return urun_agirligi
    
    def tum_urun_agirliklarini_guncelle(self) -> None:
        """
        Tum urunlerin agirliklarini hesaplar ve gunceller.
        """
        if self.veri_yoneticisi.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Urun BOM verisi bos, agirlik hesaplanamadi")
            return
        
        # Urun hesaplayici ile tum agirliklari guncelle
        self.urun_hesaplayici.set_data_frames(self.veri_yoneticisi.hammadde_df, self.veri_yoneticisi.urun_bom_df)
        self.veri_yoneticisi.urun_bom_df = self.urun_hesaplayici.tum_urun_agirliklarini_guncelle(self.veri_yoneticisi.urun_bom_df)
        
        # Veritabanina kaydet
        self.repository.save(self.veri_yoneticisi.urun_bom_df, "urun_bom")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"}))
    
    def urun_maliyeti_guncelle(self, urun_kodu: str) -> float:
        """
        Bir urunun maliyetini hesaplar ve gunceller.
        
        Args:
            urun_kodu: Maliyeti guncellenecek urunun kodu
            
        Returns:
            Urunun guncel maliyeti
        """
        self.urun_hesaplayici.set_data_frames(self.veri_yoneticisi.hammadde_df, self.veri_yoneticisi.urun_bom_df)
        urun_maliyeti = self.urun_hesaplayici.urun_maliyeti_hesapla(urun_kodu)
        
        # Urun BOM tablosunda ilgili urunun maliyetini guncelle
        self.veri_yoneticisi.urun_bom_df.loc[self.veri_yoneticisi.urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Maliyeti"] = urun_maliyeti
        
        return urun_maliyeti
    
    def tum_urun_maliyetlerini_guncelle(self) -> None:
        """
        Tum urunlerin maliyetlerini hesaplar ve gunceller.
        """
        if self.veri_yoneticisi.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Urun BOM verisi bos, maliyet hesaplanamadi")
            return
        
        # Urun hesaplayici ile tum maliyetleri guncelle
        self.urun_hesaplayici.set_data_frames(self.veri_yoneticisi.hammadde_df, self.veri_yoneticisi.urun_bom_df)
        self.veri_yoneticisi.urun_bom_df = self.urun_hesaplayici.tum_urun_maliyetlerini_guncelle(self.veri_yoneticisi.urun_bom_df)
        
        # Veritabanina kaydet
        self.repository.save(self.veri_yoneticisi.urun_bom_df, "urun_bom")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"})) 