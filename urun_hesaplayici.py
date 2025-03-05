import pandas as pd
import logging
from typing import Dict, Optional, List, Tuple, Any
from events import Event, EventManager
from functools import lru_cache

# Olay tanımları
EVENT_DATA_UPDATED = "data_updated"

class UrunHesaplayici:
    """
    Ürün hesaplamalarını yöneten sınıf.
    
    Bu sınıf, ürünlerin ağırlık, maliyet, m2 gibi hesaplamalarını yapar ve önbellekleme ile optimize edilir.
    """
    
    def __init__(self, loglayici: Optional[logging.Logger] = None, event_manager: Optional[EventManager] = None):
        """
        UrunHesaplayici sınıfını başlatır.
        """
        self.loglayici = loglayici
        self.event_manager = event_manager
        self.hammadde_df = None
        self.urun_bom_df = None
        self._data_version = 0  # Veri değişimini izlemek için sürüm numarası
    
    def set_data_frames(self, hammadde_df: pd.DataFrame, urun_bom_df: pd.DataFrame) -> None:
        """
        Veri çerçevelerini ayarlar ve önbelleği temizler.
        """
        self.hammadde_df = hammadde_df
        self.urun_bom_df = urun_bom_df
        self._data_version += 1  # Veri değiştiğinde sürüm numarasını artır
        self.onbellek_temizle()  # Önbelleği temizle
        if self.loglayici:
            self.loglayici.info("Veri çerçeveleri güncellendi ve önbellek temizlendi.")
    
    def onbellek_temizle(self) -> None:
        """Tüm önbellekleri temizler."""
        self.urun_agirligi_hesapla.cache_clear()
        self.urun_maliyeti_hesapla.cache_clear()
        self.urun_oluklu_mukavva_m2_hesapla.cache_clear()
        self.hammadde_agirligi_hesapla.cache_clear()
        if self.loglayici:
            self.loglayici.debug("Önbellek temizlendi.")
    
    @lru_cache(maxsize=128)
    def urun_agirligi_hesapla(self, urun_kodu: str, data_version: int) -> float:
        """
        Belirli bir ürünün toplam ağırlığını hesaplar (önbelleklenmiş).
        """
        if self.urun_bom_df is None or self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Ürün BOM verisi boş, ağırlık hesaplanamadı: {urun_kodu}")
            return 0
        
        urun_hammaddeleri = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu].copy()
        if urun_hammaddeleri.empty:
            if self.loglayici:
                self.loglayici.warning(f"Ürün için hammadde bulunamadı, ağırlık hesaplanamadı: {urun_kodu}")
            return 0
        
        toplam_agirlik = 0
        for _, hammadde in urun_hammaddeleri.iterrows():
            hammadde_kodu = hammadde.get("Hammadde Kodu", "")
            if self.hammadde_df is not None and not self.hammadde_df.empty and hammadde_kodu in self.hammadde_df["Hammadde Kodu"].values:
                hammadde_bilgisi = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == hammadde_kodu].iloc[0]
                if hammadde_bilgisi.get("Hammadde Tipi", "") == "Oluklu Mukavva":
                    hammadde_agirligi = hammadde.get("Hammadde Agirligi", 0)
                    if pd.notna(hammadde_agirligi):
                        toplam_agirlik += float(hammadde_agirligi)
                        if self.loglayici:
                            self.loglayici.debug(f"Oluklu mukavva hammadde ağırlığı eklendi: {hammadde_kodu} - {hammadde_agirligi:.2f} kg")
        
        if self.loglayici:
            self.loglayici.info(f"Ürün toplam ağırlığı hesaplandı (sadece oluklu mukavva): {urun_kodu} - {toplam_agirlik:.2f} kg")
        
        return toplam_agirlik
    
    @lru_cache(maxsize=128)
    def urun_maliyeti_hesapla(self, urun_kodu: str, data_version: int) -> float:
        """
        Belirli bir ürünün toplam maliyetini hesaplar (önbelleklenmiş).
        """
        if self.urun_bom_df is None or self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Ürün BOM verisi boş, maliyet hesaplanamadı: {urun_kodu}")
            return 0
        
        urun_hammaddeleri = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu].copy()
        if urun_hammaddeleri.empty:
            if self.loglayici:
                self.loglayici.warning(f"Ürün için hammadde bulunamadı, maliyet hesaplanamadı: {urun_kodu}")
            return 0
        
        toplam_maliyet = 0
        for _, hammadde in urun_hammaddeleri.iterrows():
            hammadde_maliyeti = hammadde.get("Toplam Maliyet", 0)
            if pd.notna(hammadde_maliyeti):
                toplam_maliyet += float(hammadde_maliyeti)
                if self.loglayici:
                    self.loglayici.debug(f"Hammadde maliyeti eklendi: {hammadde['Hammadde Kodu']} - {hammadde_maliyeti:.2f}")
        
        if self.loglayici:
            self.loglayici.info(f"Ürün toplam maliyeti hesaplandı: {urun_kodu} - {toplam_maliyet:.2f}")
        
        return toplam_maliyet
    
    @lru_cache(maxsize=128)
    def urun_oluklu_mukavva_m2_hesapla(self, urun_kodu: str, data_version: int) -> float:
        """
        Belirli bir ürünün oluklu mukavva m2 miktarını hesaplar (önbelleklenmiş).
        """
        if self.urun_bom_df is None or self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Ürün BOM verisi boş, oluklu mukavva m2 hesaplanamadı: {urun_kodu}")
            return 0
        
        urun_hammaddeleri = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu].copy()
        if urun_hammaddeleri.empty:
            if self.loglayici:
                self.loglayici.warning(f"Ürün için hammadde bulunamadı, oluklu mukavva m2 hesaplanamadı: {urun_kodu}")
            return 0
        
        toplam_oluklu_m2 = 0
        for _, hammadde in urun_hammaddeleri.iterrows():
            hammadde_kodu = hammadde.get("Hammadde Kodu", "")
            if self.hammadde_df is not None and not self.hammadde_df.empty and hammadde_kodu in self.hammadde_df["Hammadde Kodu"].values:
                hammadde_bilgisi = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == hammadde_kodu].iloc[0]
                if hammadde_bilgisi.get("Hammadde Tipi", "") == "Oluklu Mukavva" and hammadde.get("Birim", "") == "m2":
                    miktar = hammadde.get("Miktar", 0)
                    if pd.notna(miktar):
                        toplam_oluklu_m2 += float(miktar)
                        if self.loglayici:
                            self.loglayici.debug(f"Oluklu mukavva m2 eklendi: {hammadde_kodu} - {miktar:.2f} m2")
        
        if self.loglayici:
            self.loglayici.info(f"Ürün için oluklu mukavva m2 hesaplandı: {urun_kodu} - {toplam_oluklu_m2:.2f} m2")
        
        return toplam_oluklu_m2
    
    def satis_icin_urun_bilgilerini_hesapla(self, satis: Dict) -> Dict:
        """
        Satış kaydı için ürün bilgilerini hesaplar ve ekler.
        Not: Bu metod önbelleklenmiş metodları kullanır, doğrudan önbellekleme uygulanmaz.
        """
        guncellenmis_satis = satis.copy()
        if "Urun Kodu" in satis and self.urun_bom_df is not None and not self.urun_bom_df.empty:
            urun_kodu = satis["Urun Kodu"]
            toplam_oluklu_m2 = self.urun_oluklu_mukavva_m2_hesapla(urun_kodu, self._data_version)
            if "Miktar" in satis and pd.notna(satis["Miktar"]):
                satis_miktari = float(satis["Miktar"])
                toplam_oluklu_m2 *= satis_miktari
            guncellenmis_satis["Oluklu Mukavva m2"] = toplam_oluklu_m2
            
            urun_bilgisi = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu]
            if not urun_bilgisi.empty and "Urun Agirligi" in urun_bilgisi.columns:
                urun_agirligi = urun_bilgisi["Urun Agirligi"].iloc[0]
                if "Miktar" in satis and pd.notna(satis["Miktar"]):
                    satis_miktari = float(satis["Miktar"])
                    guncellenmis_satis["Agirlik (kg)"] = float(urun_agirligi) * satis_miktari
                else:
                    guncellenmis_satis["Agirlik (kg)"] = urun_agirligi
            else:
                guncellenmis_satis["Agirlik (kg)"] = self.urun_agirligi_hesapla(urun_kodu, self._data_version)
            
            if not urun_bilgisi.empty and "Urun Maliyeti" in urun_bilgisi.columns:
                urun_maliyeti = urun_bilgisi["Urun Maliyeti"].iloc[0]
                if "Miktar" in satis and pd.notna(satis["Miktar"]):
                    satis_miktari = float(satis["Miktar"])
                    toplam_maliyet = float(urun_maliyeti) * satis_miktari
                    guncellenmis_satis["Urun Maliyeti"] = toplam_maliyet
                    if "Birim Fiyat" in satis and pd.notna(satis["Birim Fiyat"]):
                        birim_fiyat = float(satis["Birim Fiyat"])
                        toplam_satis_tutari = birim_fiyat * satis_miktari
                        if toplam_maliyet > 0:
                            kar_marji = ((toplam_satis_tutari - toplam_maliyet) / toplam_maliyet) * 100
                            guncellenmis_satis["Kar Marji (%)"] = kar_marji
                            if self.loglayici:
                                self.loglayici.info(f"Kar marjı hesaplandı: {kar_marji:.2f}%")
                else:
                    guncellenmis_satis["Urun Maliyeti"] = urun_maliyeti
            else:
                guncellenmis_satis["Urun Maliyeti"] = self.urun_maliyeti_hesapla(urun_kodu, self._data_version)
        else:
            guncellenmis_satis["Oluklu Mukavva m2"] = 0
            guncellenmis_satis["Agirlik (kg)"] = 0
            guncellenmis_satis["Urun Maliyeti"] = 0
        
        return guncellenmis_satis
    
    @lru_cache(maxsize=128)
    def hammadde_agirligi_hesapla(self, hammadde_kodu: str, miktar: float, birim: str, data_version: int) -> float:
        """
        Hammadde ağırlığını hesaplar (önbelleklenmiş).
        """
        if self.hammadde_df is None or self.hammadde_df.empty:
            if self.loglayici:
                self.loglayici.warning(f"Hammadde verisi boş, ağırlık hesaplanamadı: {hammadde_kodu}")
            return 0
        
        hammadde_bilgisi = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == hammadde_kodu]
        if hammadde_bilgisi.empty:
            if self.loglayici:
                self.loglayici.warning(f"Hammadde bilgisi bulunamadı, ağırlık hesaplanamadı: {hammadde_kodu}")
            return 0
        
        hammadde_tipi = hammadde_bilgisi.iloc[0].get("Hammadde Tipi", "")
        if hammadde_tipi == "Oluklu Mukavva" and birim == "m2":
            m2_agirlik = hammadde_bilgisi.iloc[0].get("m2 Agirlik", 0)
            if pd.notna(m2_agirlik) and pd.notna(miktar):
                hammadde_agirligi = float(m2_agirlik) * float(miktar)
                if self.loglayici:
                    self.loglayici.info(f"Hammadde ağırlığı hesaplandı: {hammadde_kodu} - {hammadde_agirligi:.2f} kg")
                return hammadde_agirligi
        
        return 0
    
    def tum_urun_agirliklarini_guncelle(self, urun_bom_df: pd.DataFrame) -> pd.DataFrame:
        """
        Tüm ürünlerin ağırlıklarını hesaplar ve günceller.
        Not: Önbelleklenmiş urun_agirligi_hesapla metodunu kullanır.
        """
        if urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Ürün BOM verisi boş, ağırlık hesaplanamadı")
            return urun_bom_df
        
        urun_kodlari = urun_bom_df["Urun Kodu"].unique()
        for urun_kodu in urun_kodlari:
            toplam_agirlik = self.urun_agirligi_hesapla(urun_kodu, self._data_version)
            urun_bom_df.loc[urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Agirligi"] = toplam_agirlik
        
        if self.loglayici:
            self.loglayici.info(f"Tüm ürün ağırlıkları güncellendi ({len(urun_kodlari)} ürün)")
        
        return urun_bom_df
    
    def tum_urun_maliyetlerini_guncelle(self, urun_bom_df: pd.DataFrame) -> pd.DataFrame:
        """
        Tüm ürünlerin maliyetlerini hesaplar ve günceller.
        Not: Önbelleklenmiş urun_maliyeti_hesapla metodunu kullanır.
        """
        if urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Ürün BOM verisi boş, maliyet hesaplanamadı")
            return urun_bom_df
        
        urun_kodlari = urun_bom_df["Urun Kodu"].unique()
        for urun_kodu in urun_kodlari:
            toplam_maliyet = self.urun_maliyeti_hesapla(urun_kodu, self._data_version)
            urun_bom_df.loc[urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Maliyeti"] = toplam_maliyet
        
        if self.loglayici:
            self.loglayici.info(f"Toplam {len(urun_kodlari)} ürünün maliyeti güncellendi")
        
        return urun_bom_df