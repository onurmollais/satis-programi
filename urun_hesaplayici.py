import pandas as pd
import logging
from typing import Dict, Optional, List, Tuple, Any
from events import Event, EventManager

# Olay tanimlari
EVENT_DATA_UPDATED = "data_updated"

class UrunHesaplayici:
    """
    Urun hesaplamalarini yoneten sinif.
    
    Bu sinif, urunlerin agirlik, maliyet, m2 gibi hesaplamalarini yapar ve
    bu bilgileri diger modullere saglar.
    
    Attributes:
        hammadde_df (pd.DataFrame): Hammadde verileri
        urun_bom_df (pd.DataFrame): Urun BOM verileri
    """
    
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager: Optional[EventManager] = None):
        """
        UrunHesaplayici sinifini baslatir.
        
        Args:
            loglayici: Loglama islemleri icin logger nesnesi
            event_manager: Olay yonetimi icin EventManager nesnesi
        """
        self.loglayici = loglayici
        self.event_manager = event_manager
        self.hammadde_df = None
        self.urun_bom_df = None
    
    def set_data_frames(self, hammadde_df: pd.DataFrame, urun_bom_df: pd.DataFrame) -> None:
        """
        Hesaplamalar icin kullanilacak veri cercevelerini ayarlar.
        
        Args:
            hammadde_df: Hammadde verileri
            urun_bom_df: Urun BOM verileri
        """
        self.hammadde_df = hammadde_df
        self.urun_bom_df = urun_bom_df
    
    def urun_agirligi_hesapla(self, urun_kodu: str) -> float:
        """
        Belirli bir urunun toplam agirligini hesaplar.
        
        Args:
            urun_kodu: Agirligi hesaplanacak urunun kodu
            
        Returns:
            float: Hesaplanan toplam agirlik (kg)
        """
        if self.urun_bom_df is None or self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Urun BOM verisi bos, agirlik hesaplanamadi: {urun_kodu}")
            return 0
        
        # Urun icin tum hammaddeleri bul
        urun_hammaddeleri = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu].copy()
        
        if urun_hammaddeleri.empty:
            if self.loglayici:
                self.loglayici.warning(f"Urun icin hammadde bulunamadi, agirlik hesaplanamadi: {urun_kodu}")
            return 0
        
        # Hammadde agirliklarini topla - YALNIZCA OLUKLU MUKAVVA HAMMADDELER ICIN
        toplam_agirlik = 0
        
        for _, hammadde in urun_hammaddeleri.iterrows():
            hammadde_kodu = hammadde.get("Hammadde Kodu", "")
            
            # Hammadde tipini kontrol et
            if self.hammadde_df is not None and not self.hammadde_df.empty and hammadde_kodu in self.hammadde_df["Hammadde Kodu"].values:
                hammadde_bilgisi = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == hammadde_kodu].iloc[0]
                hammadde_tipi = hammadde_bilgisi.get("Hammadde Tipi", "")
                
                # Sadece Oluklu Mukavva tipindeki hammaddelerin agirligini topla
                if hammadde_tipi == "Oluklu Mukavva":
                    hammadde_agirligi = hammadde.get("Hammadde Agirligi", 0)
                    if pd.notna(hammadde_agirligi):
                        toplam_agirlik += float(hammadde_agirligi)
                        if self.loglayici:
                            self.loglayici.debug(f"Oluklu mukavva hammadde agirligi eklendi: {hammadde_kodu} - {hammadde_agirligi:.2f} kg")
        
        if self.loglayici:
            self.loglayici.info(f"Urun toplam agirligi hesaplandi (sadece oluklu mukavva): {urun_kodu} - {toplam_agirlik:.2f} kg")
        
        return toplam_agirlik
    
    def urun_maliyeti_hesapla(self, urun_kodu: str) -> float:
        """
        Belirli bir urunun toplam maliyetini hesaplar.
        
        Args:
            urun_kodu: Maliyeti hesaplanacak urunun kodu
            
        Returns:
            float: Hesaplanan toplam maliyet
        """
        if self.urun_bom_df is None or self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Urun BOM verisi bos, maliyet hesaplanamadi: {urun_kodu}")
            return 0
        
        # Urun icin tum hammaddeleri bul
        urun_hammaddeleri = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu].copy()
        
        if urun_hammaddeleri.empty:
            if self.loglayici:
                self.loglayici.warning(f"Urun icin hammadde bulunamadi, maliyet hesaplanamadi: {urun_kodu}")
            return 0
        
        # Hammadde maliyetlerini topla
        toplam_maliyet = 0
        
        for _, hammadde in urun_hammaddeleri.iterrows():
            hammadde_maliyeti = hammadde.get("Toplam Maliyet", 0)
            if pd.notna(hammadde_maliyeti):
                toplam_maliyet += float(hammadde_maliyeti)
                if self.loglayici:
                    self.loglayici.debug(f"Hammadde maliyeti eklendi: {hammadde['Hammadde Kodu']} - {hammadde_maliyeti:.2f}")
        
        if self.loglayici:
            self.loglayici.info(f"Urun toplam maliyeti hesaplandi: {urun_kodu} - {toplam_maliyet:.2f}")
        
        return toplam_maliyet
    
    def urun_oluklu_mukavva_m2_hesapla(self, urun_kodu: str) -> float:
        """
        Belirli bir urunun oluklu mukavva m2 miktarini hesaplar.
        
        Args:
            urun_kodu: m2 hesaplanacak urunun kodu
            
        Returns:
            float: Hesaplanan toplam oluklu mukavva m2
        """
        if self.urun_bom_df is None or self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Urun BOM verisi bos, oluklu mukavva m2 hesaplanamadi: {urun_kodu}")
            return 0
        
        # Urun icin tum hammaddeleri bul
        urun_hammaddeleri = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu].copy()
        
        if urun_hammaddeleri.empty:
            if self.loglayici:
                self.loglayici.warning(f"Urun icin hammadde bulunamadi, oluklu mukavva m2 hesaplanamadi: {urun_kodu}")
            return 0
        
        # Oluklu mukavva m2 hesapla
        toplam_oluklu_m2 = 0
        
        for _, hammadde in urun_hammaddeleri.iterrows():
            hammadde_kodu = hammadde.get("Hammadde Kodu", "")
            
            # Hammadde tipini kontrol et
            if self.hammadde_df is not None and not self.hammadde_df.empty and hammadde_kodu in self.hammadde_df["Hammadde Kodu"].values:
                hammadde_bilgisi = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == hammadde_kodu].iloc[0]
                hammadde_tipi = hammadde_bilgisi.get("Hammadde Tipi", "")
                
                # Sadece Oluklu Mukavva tipindeki hammaddelerin m2'sini topla
                if hammadde_tipi == "Oluklu Mukavva" and hammadde.get("Birim", "") == "m2":
                    miktar = hammadde.get("Miktar", 0)
                    if pd.notna(miktar):
                        toplam_oluklu_m2 += float(miktar)
                        if self.loglayici:
                            self.loglayici.debug(f"Oluklu mukavva m2 eklendi: {hammadde_kodu} - {miktar:.2f} m2")
        
        if self.loglayici:
            self.loglayici.info(f"Urun icin oluklu mukavva m2 hesaplandi: {urun_kodu} - {toplam_oluklu_m2:.2f} m2")
        
        return toplam_oluklu_m2
    
    def satis_icin_urun_bilgilerini_hesapla(self, satis: Dict) -> Dict:
        """
        Satis kaydi icin urun bilgilerini hesaplar ve ekler.
        
        Args:
            satis: Satis bilgilerini iceren sozluk
            
        Returns:
            Dict: Urun bilgileri eklenmiÅŸ satis sozlugu
        """
        # Satis sozlugunu kopyala
        guncellenmis_satis = satis.copy()
        
        # Urun kodu varsa ve urun BOM bilgisi mevcutsa, oluklu mukavva m2 hesapla
        if "Urun Kodu" in satis and self.urun_bom_df is not None and not self.urun_bom_df.empty:
            urun_kodu = satis["Urun Kodu"]
            
            # Oluklu mukavva m2 hesapla
            toplam_oluklu_m2 = self.urun_oluklu_mukavva_m2_hesapla(urun_kodu)
            
            # Satis miktarini da hesaba kat (adet olarak satilan urunler icin)
            if "Miktar" in satis and pd.notna(satis["Miktar"]):
                satis_miktari = float(satis["Miktar"])
                toplam_oluklu_m2 *= satis_miktari
            
            # Hesaplanan m2 degerini satis kaydina ekle
            guncellenmis_satis["Oluklu Mukavva m2"] = toplam_oluklu_m2
            
            # Agirlik bilgisini ekle
            urun_bilgisi = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu]
            
            if not urun_bilgisi.empty and "Urun Agirligi" in urun_bilgisi.columns:
                # Urun agirligini al (ilk satirdaki deger)
                urun_agirligi = urun_bilgisi["Urun Agirligi"].iloc[0]
                
                # Satis miktarini da hesaba kat
                if "Miktar" in satis and pd.notna(satis["Miktar"]):
                    satis_miktari = float(satis["Miktar"])
                    toplam_agirlik = float(urun_agirligi) * satis_miktari
                    guncellenmis_satis["Agirlik (kg)"] = toplam_agirlik
                else:
                    guncellenmis_satis["Agirlik (kg)"] = urun_agirligi
            else:
                guncellenmis_satis["Agirlik (kg)"] = 0
            
            # Urun maliyeti bilgisini ekle
            if not urun_bilgisi.empty and "Urun Maliyeti" in urun_bilgisi.columns:
                # Urun maliyetini al (ilk satirdaki deger)
                urun_maliyeti = urun_bilgisi["Urun Maliyeti"].iloc[0]
                
                # Satis miktarini da hesaba kat
                if "Miktar" in satis and pd.notna(satis["Miktar"]):
                    satis_miktari = float(satis["Miktar"])
                    toplam_maliyet = float(urun_maliyeti) * satis_miktari
                    guncellenmis_satis["Urun Maliyeti"] = toplam_maliyet
                    
                    # Kar marji hesapla (eger birim fiyat varsa)
                    if "Birim Fiyat" in satis and pd.notna(satis["Birim Fiyat"]):
                        birim_fiyat = float(satis["Birim Fiyat"])
                        toplam_satis_tutari = birim_fiyat * satis_miktari
                        
                        if toplam_maliyet > 0:
                            kar_marji = ((toplam_satis_tutari - toplam_maliyet) / toplam_maliyet) * 100
                            guncellenmis_satis["Kar Marji (%)"] = kar_marji
                            
                            if self.loglayici:
                                self.loglayici.info(f"Kar marji hesaplandi: {kar_marji:.2f}%")
                else:
                    guncellenmis_satis["Urun Maliyeti"] = urun_maliyeti
            else:
                guncellenmis_satis["Urun Maliyeti"] = 0
        else:
            # Urun kodu yoksa veya BOM bilgisi yoksa, degerleri 0 olarak ayarla
            guncellenmis_satis["Oluklu Mukavva m2"] = 0
            guncellenmis_satis["Agirlik (kg)"] = 0
            guncellenmis_satis["Urun Maliyeti"] = 0
        
        return guncellenmis_satis
    
    def hammadde_agirligi_hesapla(self, hammadde_kodu: str, miktar: float, birim: str = "m2") -> float:
        """
        Hammadde agirligini hesaplar.
        
        Args:
            hammadde_kodu: Hammadde kodu
            miktar: Hammadde miktari
            birim: Miktar birimi (varsayilan: m2)
            
        Returns:
            float: Hesaplanan hammadde agirligi (kg)
        """
        if self.hammadde_df is None or self.hammadde_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Hammadde verisi bos, agirlik hesaplanamadi: {hammadde_kodu}")
            return 0
        
        # Hammadde bilgisini bul
        hammadde_bilgisi = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == hammadde_kodu]
        
        if hammadde_bilgisi.empty:
            if self.loglayici:
                self.loglayici.warning(f"Hammadde bilgisi bulunamadi, agirlik hesaplanamadi: {hammadde_kodu}")
            return 0
        
        # Hammadde tipini kontrol et
        hammadde_tipi = hammadde_bilgisi.iloc[0].get("Hammadde Tipi", "")
        
        # Oluklu mukavva icin m2 agirlik hesapla
        if hammadde_tipi == "Oluklu Mukavva" and birim == "m2":
            m2_agirlik = hammadde_bilgisi.iloc[0].get("m2 Agirlik", 0)
            
            if pd.notna(m2_agirlik) and pd.notna(miktar):
                hammadde_agirligi = float(m2_agirlik) * float(miktar)
                
                if self.loglayici:
                    self.loglayici.info(f"Hammadde agirligi hesaplandi: {hammadde_kodu} - {hammadde_agirligi:.2f} kg")
                
                return hammadde_agirligi
        
        # Diger hammadde tipleri veya birimler icin 0 dondur
        return 0
    
    def tum_urun_agirliklarini_guncelle(self, urun_bom_df: pd.DataFrame) -> pd.DataFrame:
        """
        Tum urunlerin agirliklarini hesaplar ve gunceller.
        
        Args:
            urun_bom_df: Guncellenecek urun BOM veri cercevesi
            
        Returns:
            pd.DataFrame: Agirlik bilgileri guncellenmis urun BOM veri cercevesi
        """
        if urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Urun BOM verisi bos, agirlik hesaplanamadi")
            return urun_bom_df
        
        # Benzersiz urun kodlarini al
        urun_kodlari = urun_bom_df["Urun Kodu"].unique()
        
        for urun_kodu in urun_kodlari:
            # Urun agirligini hesapla
            toplam_agirlik = self.urun_agirligi_hesapla(urun_kodu)
            
            # Urun agirligini guncelle
            urun_bom_df.loc[urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Agirligi"] = toplam_agirlik
        
        if self.loglayici:
            self.loglayici.info(f"Tum urun agirliklari guncellendi ({len(urun_kodlari)} urun)")
        
        return urun_bom_df
    
    def tum_urun_maliyetlerini_guncelle(self, urun_bom_df: pd.DataFrame) -> pd.DataFrame:
        """
        Tum urunlerin maliyetlerini hesaplar ve gunceller.
        
        Args:
            urun_bom_df: Guncellenecek urun BOM veri cercevesi
            
        Returns:
            pd.DataFrame: Maliyet bilgileri guncellenmis urun BOM veri cercevesi
        """
        if urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Urun BOM verisi bos, maliyet hesaplanamadi")
            return urun_bom_df
        
        # Benzersiz urun kodlarini al
        urun_kodlari = urun_bom_df["Urun Kodu"].unique()
        
        for urun_kodu in urun_kodlari:
            # Urun maliyetini hesapla
            toplam_maliyet = self.urun_maliyeti_hesapla(urun_kodu)
            
            # Urun maliyetini guncelle
            urun_bom_df.loc[urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Maliyeti"] = toplam_maliyet
        
        if self.loglayici:
            self.loglayici.info(f"Toplam {len(urun_kodlari)} urunun maliyeti guncellendi")
        
        return urun_bom_df 
