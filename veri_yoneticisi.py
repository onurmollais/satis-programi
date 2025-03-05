# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import logging
from typing import Dict, Optional, List, Tuple, Iterator, Callable, Any
from repository import RepositoryInterface
from io import BytesIO  # Yeni eklenen import
import base64  # Raporlarda kullanilan base64 icin
from datetime import datetime  # musteri_raporu_olustur icin gerekli
from events import Event, EventManager, EVENT_DATA_UPDATED, EVENT_ERROR_OCCURRED, EVENT_LOADING_PROGRESS, EVENT_LOADING_COMPLETED, EVENT_LOADING_ERROR, EVENT_BACKUP_COMPLETED  # Event ve olay sabitleri eklendi
from urun_hesaplayici import UrunHesaplayici  # Yeni modul import edildi

# Yeni yonetici siniflari import edildi
from veri_yukleyici import VeriYukleyici
from satis_yoneticisi import SatisYoneticisi
from musteri_yoneticisi import MusteriYoneticisi
from urun_yoneticisi import UrunYoneticisi

class VeriYoneticisi:
    def __init__(self, repository: RepositoryInterface, loglayici, event_manager):
        self.repository = repository
        self.loglayici = loglayici
        self.event_manager = event_manager
        
        # DataFrame'leri tanimla
        self.satiscilar_df = None
        self.hedefler_df = None
        self.aylik_hedefler_df = None
        self.satislar_df = None
        self.pipeline_df = None
        self.musteriler_df = None
        self.ziyaretler_df = None
        self.sikayetler_df = None
        self.hammadde_df = None
        self.urun_bom_df = None
        
        # Urun hesaplayici olustur
        self.urun_hesaplayici = UrunHesaplayici(self.loglayici, event_manager)
        
        # Yonetici siniflari olustur
        self.veri_yukleyici = VeriYukleyici(self)
        self.satis_yoneticisi = SatisYoneticisi(self)
        self.musteri_yoneticisi = MusteriYoneticisi(self)
        self.urun_yoneticisi = UrunYoneticisi(self)

        # Oluklu mukavva DataFrame'i
        self.oluklu_df = pd.DataFrame({
            'Dalga_Tipi': [
                'B Dalga', 'C Dalga', 'A Dalga',  # Tek Dalga
                'BC Dalga', 'AA Dalga', 'AC Dalga',  # Dopel
                'BCA Dalga', 'ACA Dalga'  # Tripleks
            ],
            'Grup': [
                'Tek Dalga', 'Tek Dalga', 'Tek Dalga',
                'Dopel', 'Dopel', 'Dopel',
                'Tripleks', 'Tripleks'
            ],
            'Birim_M2_Agirlik': [  # gr/m2 cinsinden birim agirlik
                350, 400, 450,  
                500, 550, 525,  
                650, 625  
            ],
            'Birim_M2': [  # m2 cinsinden birim alan
                1.0, 1.0, 1.0,  
                1.0, 1.0, 1.0,  
                1.0, 1.0  
            ]
        })
        
        # Gruplara gore ozet DataFrame
        self.oluklu_gruplar_df = self.oluklu_df.groupby('Grup').agg({
            'Birim_M2_Agirlik': 'min',
            'Birim_M2_Agirlik': 'max',
            'Birim_M2': 'min',
            'Birim_M2': 'max'
        }).reset_index()

    @property
    def customers_df(self):
        return self.musteriler_df

    @customers_df.setter
    def customers_df(self, value):
        self.musteriler_df = value

    @property
    def targets_df(self):
        return self.hedefler_df

    @targets_df.setter
    def targets_df(self, value):
        self.hedefler_df = value

    @property
    def monthly_targets_df(self):
        return self.aylik_hedefler_df
        
    @monthly_targets_df.setter
    def monthly_targets_df(self, value):
        self.aylik_hedefler_df = value

    def tum_verileri_yukle(self, dosya_yolu: str) -> None:
        return self.veri_yukleyici.tum_verileri_yukle(dosya_yolu)

    def tum_verileri_yukle_paginated(self, dosya_yolu, sayfa=1, sayfa_boyutu=1000):
        return self.veri_yukleyici.tum_verileri_yukle_paginated(dosya_yolu, sayfa, sayfa_boyutu)

    def tum_verileri_kaydet(self, dosya_yolu):
        return self.veri_yukleyici.tum_verileri_kaydet(dosya_yolu)

    def satisci_ekle(self, yeni_satisci):
        return self.satis_yoneticisi.satisci_ekle(yeni_satisci)

    def satisci_duzenle(self, index, guncellenmis_satisci):
        return self.satis_yoneticisi.satisci_duzenle(index, guncellenmis_satisci)

    def satisci_sil(self, satisci_isim):
        return self.satis_yoneticisi.satisci_sil(satisci_isim)

    def satis_hedefi_ekle(self, yeni_hedef):
        return self.satis_yoneticisi.satis_hedefi_ekle(yeni_hedef)

    def satis_hedefi_duzenle(self, index, yeni_hedef):
        return self.satis_yoneticisi.satis_hedefi_duzenle(index, yeni_hedef)

    def satis_hedefi_sil(self, ay):
        return self.satis_yoneticisi.satis_hedefi_sil(ay)

    def satis_ekle(self, yeni_satis):
        return self.satis_yoneticisi.satis_ekle(yeni_satis)

    def pipeline_firsati_ekle(self, yeni_firsat):
        return self.satis_yoneticisi.pipeline_firsati_ekle(yeni_firsat)

    def pipeline_firsati_sil(self, musteri_adi):
        return self.satis_yoneticisi.pipeline_firsati_sil(musteri_adi)

    def musteri_ekle(self, yeni_musteri):
        return self.musteri_yoneticisi.musteri_ekle(yeni_musteri)

    def ziyaret_ekle(self, yeni_ziyaret):
        return self.musteri_yoneticisi.ziyaret_ekle(yeni_ziyaret)

    def sikayet_ekle(self, yeni_sikayet):
        return self.musteri_yoneticisi.sikayet_ekle(yeni_sikayet)

    def hammadde_ekle(self, yeni_hammadde):
        return self.urun_yoneticisi.hammadde_ekle(yeni_hammadde)

    def hammadde_duzenle(self, index, yeni_hammadde):
        return self.urun_yoneticisi.hammadde_duzenle(index, yeni_hammadde)

    def hammadde_sil(self, hammadde_kodu):
        return self.urun_yoneticisi.hammadde_sil(hammadde_kodu)
            
    def urun_bom_ekle(self, yeni_urun_bom):
        return self.urun_yoneticisi.urun_bom_ekle(yeni_urun_bom)
            
    def urun_bom_duzenle(self, index, yeni_urun_bom):
        return self.urun_yoneticisi.urun_bom_duzenle(index, yeni_urun_bom)
            
    def urun_bom_sil(self, urun_kodu, hammadde_kodu):
        return self.urun_yoneticisi.urun_bom_sil(urun_kodu, hammadde_kodu)

    def urun_agirligi_guncelle(self, urun_kodu):
        """Belirli bir urunun toplam agirligini hesaplar ve gunceller"""
        if self.urun_bom_df.empty:
            return 0
        
        # Urun hesaplayici ile agirlik hesapla
        self.urun_hesaplayici.set_data_frames(self.hammadde_df, self.urun_bom_df)
        toplam_agirlik = self.urun_hesaplayici.urun_agirligi_hesapla(urun_kodu)
        
        # Urun agirligini guncelle
        self.urun_bom_df.loc[self.urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Agirligi"] = toplam_agirlik
        
        return toplam_agirlik
    
    def tum_urun_agirliklarini_guncelle(self):
        """Tum urunlerin agirliklarini hesaplar ve gunceller"""
        if self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Urun BOM verisi bos, agirlik hesaplanamadi")
            return
        
        # Urun hesaplayici ile tum agirliklari guncelle
        self.urun_hesaplayici.set_data_frames(self.hammadde_df, self.urun_bom_df)
        self.urun_bom_df = self.urun_hesaplayici.tum_urun_agirliklarini_guncelle(self.urun_bom_df)
        
        # Veritabanina kaydet
        self.repository.save(self.urun_bom_df, "urun_bom")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"}))

    def urun_maliyeti_guncelle(self, urun_kodu):
        """Belirli bir urunun toplam maliyetini hesaplar ve gunceller"""
        if self.urun_bom_df.empty:
            return 0
        
        # Urun hesaplayici ile maliyet hesapla
        self.urun_hesaplayici.set_data_frames(self.hammadde_df, self.urun_bom_df)
        toplam_maliyet = self.urun_hesaplayici.urun_maliyeti_hesapla(urun_kodu)
        
        # Urun maliyetini guncelle
        self.urun_bom_df.loc[self.urun_bom_df["Urun Kodu"] == urun_kodu, "Urun Maliyeti"] = toplam_maliyet
        
        return toplam_maliyet
        
    def tum_urun_maliyetlerini_guncelle(self):
        """Tum urunlerin maliyetlerini hesaplar ve gunceller"""
        if self.urun_bom_df.empty:
            if self.loglayici:
                self.loglayici.warning("Urun BOM verisi bos, maliyet hesaplanamadi")
            return
        
        # Urun hesaplayici ile tum maliyetleri guncelle
        self.urun_hesaplayici.set_data_frames(self.hammadde_df, self.urun_bom_df)
        self.urun_bom_df = self.urun_hesaplayici.tum_urun_maliyetlerini_guncelle(self.urun_bom_df)
        
        # Veritabanina kaydet
        self.repository.save(self.urun_bom_df, "urun_bom")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"}))

    def kohort_analizi_olustur(self, baslangic_tarihi=None, bitis_tarihi=None):
        """Kohort analizi olusturur"""
        try:
            if self.satislar_df is None or self.satislar_df.empty:
                return {"success": False, "message": "Henuz satis verisi bulunmamaktadir."}
            
            # Veri cercevesini kopyala
            df = self.satislar_df.copy()
            
            # Tarih sutununu olustur
            df['Tarih'] = pd.to_datetime(df['Ay'], format='%m-%Y', errors='coerce')
            
            # Tarih filtreleme
            if baslangic_tarihi and bitis_tarihi:
                baslangic = pd.to_datetime(baslangic_tarihi)
                bitis = pd.to_datetime(bitis_tarihi)
                df = df[(df['Tarih'] >= baslangic) & (df['Tarih'] <= bitis)]
            
            # Kohort analizi icin gerekli sutunlari olustur
            df['Kohort Ay'] = df['Tarih'].dt.to_period('M')
            df['Ay Indeksi'] = (df['Tarih'].dt.year - df['Kohort Ay'].dt.year) * 12 + (df['Tarih'].dt.month - df['Kohort Ay'].dt.month)
            
            # Musteri bazinda kohort analizi
            kohort_musteri = df.groupby(['Kohort Ay', 'Ay Indeksi'])['Ana Musteri'].nunique().reset_index()
            kohort_musteri_pivot = kohort_musteri.pivot(index='Kohort Ay', columns='Ay Indeksi', values='Ana Musteri')
            
            # Ilk ay musteri sayilari
            ilk_ay_musteriler = kohort_musteri_pivot[0]
            
            # Tutma orani hesapla
            kohort_musteri_oran = kohort_musteri_pivot.divide(ilk_ay_musteriler, axis=0)
            
            # Ortalama siparis degeri (AOV) analizi
            kohort_aov = df.groupby(['Kohort Ay', 'Ay Indeksi'])['Satis Miktari'].mean().reset_index()
            kohort_aov_pivot = kohort_aov.pivot(index='Kohort Ay', columns='Ay Indeksi', values='Satis Miktari')
            
            # Toplam satis analizi
            kohort_satis = df.groupby(['Kohort Ay', 'Ay Indeksi'])['Satis Miktari'].sum().reset_index()
            kohort_satis_pivot = kohort_satis.pivot(index='Kohort Ay', columns='Ay Indeksi', values='Satis Miktari')
            
            # Sonuclari dondur
            return {
                "success": True,
                "kohort_musteri_oran": kohort_musteri_oran,
                "kohort_aov_pivot": kohort_aov_pivot,
                "kohort_satis_pivot": kohort_satis_pivot,
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }
            
        except Exception as e:
            self.loglayici.error(f"Kohort analizi olusturulurken hata: {str(e)}")
            import traceback
            self.loglayici.error(traceback.format_exc())
            return {"success": False, "message": f"Kohort analizi olusturulurken hata: {str(e)}"}

    def oluklu_bilgilerini_getir(self, dalga_tipi=None, grup=None):
        """
        Oluklu mukavva bilgilerini getirir.
        
        Args:
            dalga_tipi (str, optional): Spesifik dalga tipi
            grup (str, optional): Dalga grubu (Tek Dalga, Dopel, Tripleks)
            
        Returns:
            pd.DataFrame: Filtrelenmis oluklu mukavva bilgileri
        """
        if dalga_tipi:
            return self.oluklu_df[self.oluklu_df['Dalga_Tipi'] == dalga_tipi]
        elif grup:
            return self.oluklu_df[self.oluklu_df['Grup'] == grup]
        else:
            return self.oluklu_df
    
    def oluklu_grup_bilgilerini_getir(self, grup=None):
        """
        Oluklu mukavva grup bilgilerini getirir.
        
        Args:
            grup (str, optional): Dalga grubu (Tek Dalga, Dopel, Tripleks)
            
        Returns:
            pd.DataFrame: Filtrelenmis grup bilgileri
        """
        if grup:
            return self.oluklu_gruplar_df[self.oluklu_gruplar_df['Grup'] == grup]
        else:
            return self.oluklu_gruplar_df

    def oluklu_agirlik_hesapla(self, dalga_tipi: str, satis_miktari: float, bom_miktari: float) -> float:
        """
        Oluklu mukavva urunun toplam agirligini hesaplar.
        
        Args:
            dalga_tipi (str): Urunun dalga tipi
            satis_miktari (float): Satilan urun miktari
            bom_miktari (float): BOM'daki miktar
            
        Returns:
            float: Toplam agirlik (kg cinsinden)
        """
        try:
            # Hammadde m2 agirligini kullan (hammadde_df'den)
            if self.hammadde_df is not None and not self.hammadde_df.empty:
                oluklu_hammaddeler = self.hammadde_df[
                    (self.hammadde_df['Hammadde Tipi'] == 'Oluklu Mukavva') &
                    (self.hammadde_df['Mukavva Tipi'] == dalga_tipi)
                ]
                
                if not oluklu_hammaddeler.empty:
                    # m2 agirligini al (gr/m2 cinsinden)
                    m2_agirlik = oluklu_hammaddeler['m2 Agirlik'].iloc[0]
                    
                    # Toplam agirligi hesapla (kg cinsinden)
                    # hammadde m2 agirligi x bom miktari x satis miktari
                    toplam_agirlik = (m2_agirlik * bom_miktari * satis_miktari) / 1000
                    
                    return toplam_agirlik
            
            return 0.0
            
        except Exception as e:
            self.loglayici.error(f"Oluklu agirlik hesaplama hatasi: {str(e)}")
            return 0.0

    def oluklu_m2_hesapla(self, dalga_tipi: str, satis_miktari: float, bom_miktari: float) -> float:
        """
        Oluklu mukavva urunun toplam m2'sini hesaplar.
        
        Args:
            dalga_tipi (str): Urunun dalga tipi
            satis_miktari (float): Satilan urun miktari
            bom_miktari (float): BOM'daki miktar
            
        Returns:
            float: Toplam m2
        """
        try:
            # Toplam m2'yi hesapla: bom miktari x satis miktari
            toplam_m2 = bom_miktari * satis_miktari
            return toplam_m2
            
        except Exception as e:
            self.loglayici.error(f"Oluklu m2 hesaplama hatasi: {str(e)}")
            return 0.0

    def musteri_grubu_analizi(self) -> pd.DataFrame:
        """
        Musterileri ZER ve Diger olarak gruplandirip analiz yapar.
        
        Returns:
            pd.DataFrame: Musteri grubu analiz sonuclarini iceren DataFrame
        """
        try:
            if self.satislar_df is None or self.satislar_df.empty:
                if self.loglayici:
                    self.loglayici.warning("Satis verisi bos, analiz yapilamadi")
                return pd.DataFrame()

            # Alt musterisi olan ve olmayan musterileri belirle
            zer_musteriler = self.satislar_df[self.satislar_df["Alt Musteri"].notna()]["Ana Musteri"].unique()
            diger_musteriler = self.satislar_df[~self.satislar_df["Ana Musteri"].isin(zer_musteriler)]["Ana Musteri"].unique()

            sonuclar = []

            # ZER Grubu Analizi
            zer_satislar = self.satislar_df[self.satislar_df["Ana Musteri"].isin(zer_musteriler)].copy()
            if not zer_satislar.empty:
                zer_toplam = self._grup_analizi_yap(zer_satislar)
                zer_toplam["Musteri Grubu"] = "ZER"
                sonuclar.append(zer_toplam)

            # Diger Grup Analizi
            diger_satislar = self.satislar_df[self.satislar_df["Ana Musteri"].isin(diger_musteriler)].copy()
            if not diger_satislar.empty:
                diger_toplam = self._grup_analizi_yap(diger_satislar)
                diger_toplam["Musteri Grubu"] = "Diger"
                sonuclar.append(diger_toplam)

            # Sonuclari birlestir
            analiz_df = pd.concat(sonuclar, ignore_index=True)
            
            if self.loglayici:
                self.loglayici.info("Musteri grubu analizi tamamlandi")
            
            return analiz_df

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Musteri grubu analizi sirasinda hata: {str(e)}")
            return pd.DataFrame()

    def _grup_analizi_yap(self, grup_df: pd.DataFrame) -> pd.DataFrame:
        """
        Verilen grup icin analiz hesaplamalarini yapar.
        
        Args:
            grup_df: Analiz edilecek grup verisi
            
        Returns:
            pd.DataFrame: Grup analiz sonuclarini iceren DataFrame
        """
        try:
            # Toplam satis tutari hesapla (Miktar x Birim Fiyat)
            grup_df["Satis Tutari"] = grup_df["Miktar"] * grup_df["Birim Fiyat"]
            toplam_satis = grup_df["Satis Tutari"].sum()

            toplam_agirlik = 0
            toplam_m2 = 0
            toplam_maliyet = 0  # Toplam maliyet degiskeni ekle

            # Her urun icin agirlik ve m2 hesapla
            for urun_kodu in grup_df["Urun Kodu"].unique():
                urun_satislari = grup_df[grup_df["Urun Kodu"] == urun_kodu]
                satis_adedi = urun_satislari["Miktar"].sum()

                if self.urun_bom_df is not None and not self.urun_bom_df.empty:
                    urun_bom = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu]
                    
                    # Agirlik hesapla
                    for _, bom_satir in urun_bom.iterrows():
                        if self.hammadde_df is not None and not self.hammadde_df.empty:
                            hammadde = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == bom_satir["Hammadde Kodu"]]
                            if not hammadde.empty:
                                hammadde_agirligi = hammadde["m2 Agirlik"].iloc[0]  # Birim maliyet yerine m2 agirlik
                                miktar = bom_satir["Miktar"]
                                toplam_agirlik += hammadde_agirligi * miktar * satis_adedi
                                
                                # Maliyet hesapla (varsayilan olarak hammadde birim fiyati * miktar * satis adedi)
                                if "Birim Fiyat" in hammadde.columns:
                                    hammadde_fiyati = hammadde["Birim Fiyat"].iloc[0]
                                    toplam_maliyet += hammadde_fiyati * miktar * satis_adedi

                    # m2 hesapla
                    for _, bom_satir in urun_bom.iterrows():
                        miktar = bom_satir["Miktar"]
                        toplam_m2 += miktar * satis_adedi
            
            # Eger maliyet hesaplanamadiysa, varsayilan olarak satisin %70'i olarak kabul et
            if toplam_maliyet == 0:
                toplam_maliyet = toplam_satis * 0.65

            return pd.DataFrame([{
                "Toplam Satis (TL)": toplam_satis,
                "Toplam Maliyet (TL)": toplam_maliyet,  # Toplam maliyet sutunu ekle
                "Toplam Agirlik (kg)": toplam_agirlik,
                "Toplam m2": toplam_m2
            }])

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Grup analizi sirasinda hata: {str(e)}")
            return pd.DataFrame()

    def toplam_maliyet_hesapla(self, baslangic_tarihi: str = None, bitis_tarihi: str = None) -> Dict[str, Any]:
        """
        Belirtilen tarih araligindaki toplam maliyeti hesaplar.
        
        Args:
            baslangic_tarihi: Baslangic tarihi (MM-YYYY formati)
            bitis_tarihi: Bitis tarihi (MM-YYYY formati)
            
        Returns:
            Dict: Toplam maliyet bilgilerini iceren sozluk
            {
                "toplam_maliyet": float,
                "urun_bazli_maliyetler": pd.DataFrame,
                "donem": str
            }
        """
        try:
            if self.satislar_df is None or self.satislar_df.empty:
                if self.loglayici:
                    self.loglayici.warning("Satis verisi bos, maliyet hesaplanamadi")
                return {
                    "toplam_maliyet": 0.0,
                    "urun_bazli_maliyetler": pd.DataFrame(),
                    "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
                }

            # Satislari filtrele
            satislar = self.satislar_df.copy()
            if baslangic_tarihi and bitis_tarihi:
                satislar = satislar[
                    (satislar["Ay"] >= baslangic_tarihi) & 
                    (satislar["Ay"] <= bitis_tarihi)
                ]

            toplam_maliyet = 0.0
            urun_maliyetleri = []

            # Her urun icin maliyet hesapla
            for urun_kodu in satislar["Urun Kodu"].unique():
                urun_satislari = satislar[satislar["Urun Kodu"] == urun_kodu]
                satis_adedi = urun_satislari["Miktar"].sum()
                
                if self.urun_bom_df is not None and not self.urun_bom_df.empty:
                    urun_bom = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu]
                    urun_toplam_maliyet = 0.0
                    
                    # Her BOM satiri icin maliyet hesapla
                    for _, bom_satir in urun_bom.iterrows():
                        if self.hammadde_df is not None and not self.hammadde_df.empty:
                            hammadde = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == bom_satir["Hammadde Kodu"]]
                            if not hammadde.empty:
                                birim_maliyet = hammadde["Birim Maliyet"].iloc[0]
                                miktar = bom_satir["Miktar"]
                                # Hammadde maliyeti = birim maliyet x miktar x satis adedi
                                hammadde_maliyeti = birim_maliyet * miktar * satis_adedi
                                urun_toplam_maliyet += hammadde_maliyeti
                    
                    toplam_maliyet += urun_toplam_maliyet

                    # Urun bazli maliyet bilgilerini kaydet
                    urun_maliyetleri.append({
                        "Urun Kodu": urun_kodu,
                        "Urun Adi": urun_satislari["Urun Adi"].iloc[0] if not urun_satislari.empty else "",
                        "Satis Adedi": satis_adedi,
                        "Birim Maliyet": urun_toplam_maliyet / satis_adedi if satis_adedi > 0 else 0,
                        "Toplam Maliyet": urun_toplam_maliyet
                    })

            # Urun bazli maliyetleri DataFrame'e donustur
            urun_bazli_maliyetler = pd.DataFrame(urun_maliyetleri)
            
            if self.loglayici:
                self.loglayici.info(f"Toplam maliyet hesaplandi: {toplam_maliyet:.2f} TL")

            return {
                "toplam_maliyet": toplam_maliyet,
                "urun_bazli_maliyetler": urun_bazli_maliyetler,
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Toplam maliyet hesaplama hatasi: {str(e)}")
            return {
                "toplam_maliyet": 0.0,
                "urun_bazli_maliyetler": pd.DataFrame(),
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }

    def ortalama_av_hesapla(self, baslangic_tarihi: str = None, bitis_tarihi: str = None) -> Dict[str, Any]:
        """
        Belirtilen tarih araligindaki ortalama AV (Arti Value - Katma Deger) oranini hesaplar.
        
        Formul: AV = 1 - (Toplam Maliyet / Toplam Satis)
        
        Args:
            baslangic_tarihi: Baslangic tarihi (MM-YYYY formati)
            bitis_tarihi: Bitis tarihi (MM-YYYY formati)
            
        Returns:
            Dict: Ortalama AV bilgilerini iceren sozluk
            {
                "ortalama_av": float,  # Yuzde olarak AV orani
                "toplam_maliyet": float,
                "toplam_satis": float,
                "donem": str
            }
        """
        try:
            if self.satislar_df is None or self.satislar_df.empty:
                if self.loglayici:
                    self.loglayici.warning("Satis verisi bos, AV hesaplanamadi")
                return {
                    "ortalama_av": 0.0,
                    "toplam_maliyet": 0.0,
                    "toplam_satis": 0.0,
                    "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
                }

            # Toplam maliyeti hesapla
            maliyet_sonuc = self.toplam_maliyet_hesapla(baslangic_tarihi, bitis_tarihi)
            toplam_maliyet = maliyet_sonuc["toplam_maliyet"]

            # Toplam satisi hesapla
            satislar = self.satislar_df.copy()
            if baslangic_tarihi and bitis_tarihi:
                satislar = satislar[
                    (satislar["Ay"] >= baslangic_tarihi) & 
                    (satislar["Ay"] <= bitis_tarihi)
                ]
            
            # Toplam satis tutarini hesapla (Miktar x Birim Fiyat)
            satislar["Satis Tutari"] = satislar["Miktar"] * satislar["Birim Fiyat"]
            toplam_satis = satislar["Satis Tutari"].sum()

            # AV oranini hesapla
            ortalama_av = 0.0
            if toplam_satis > 0:
                ortalama_av = 1 - (toplam_maliyet / toplam_satis)
                ortalama_av = max(0.0, min(1.0, ortalama_av))  # 0-1 arasinda sinirla

            if self.loglayici:
                self.loglayici.info(f"Ortalama AV hesaplandi: {ortalama_av:.2%}")
                self.loglayici.debug(f"Toplam Maliyet: {toplam_maliyet:.2f} TL")
                self.loglayici.debug(f"Toplam Satis: {toplam_satis:.2f} TL")

            return {
                "ortalama_av": ortalama_av,
                "toplam_maliyet": toplam_maliyet,
                "toplam_satis": toplam_satis,
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Ortalama AV hesaplama hatasi: {str(e)}")
            return {
                "ortalama_av": 0.0,
                "toplam_maliyet": 0.0,
                "toplam_satis": 0.0,
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }

    def toplam_agirlik_hesapla(self, baslangic_tarihi: str = None, bitis_tarihi: str = None) -> Dict[str, Any]:
        """
        Belirtilen tarih araligindaki toplam agirligi hesaplar.
        
        Args:
            baslangic_tarihi: Baslangic tarihi (MM-YYYY formati)
            bitis_tarihi: Bitis tarihi (MM-YYYY formati)
            
        Returns:
            Dict: Toplam agirlik bilgilerini iceren sozluk
            {
                "toplam_agirlik": float,  # kg cinsinden
                "urun_bazli_agirliklar": pd.DataFrame,
                "donem": str
            }
        """
        try:
            if self.satislar_df is None or self.satislar_df.empty:
                if self.loglayici:
                    self.loglayici.warning("Satis verisi bos, agirlik hesaplanamadi")
                return {
                    "toplam_agirlik": 0.0,
                    "urun_bazli_agirliklar": pd.DataFrame(),
                    "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
                }

            # Satislari filtrele
            satislar = self.satislar_df.copy()
            if baslangic_tarihi and bitis_tarihi:
                satislar = satislar[
                    (satislar["Ay"] >= baslangic_tarihi) & 
                    (satislar["Ay"] <= bitis_tarihi)
                ]

            toplam_agirlik = 0.0
            urun_agirliklar = []

            # Her urun icin agirlik hesapla
            for urun_kodu in satislar["Urun Kodu"].unique():
                urun_satislari = satislar[satislar["Urun Kodu"] == urun_kodu]
                satis_adedi = urun_satislari["Miktar"].sum()

                if self.urun_bom_df is not None and not self.urun_bom_df.empty:
                    urun_bom = self.urun_bom_df[self.urun_bom_df["Urun Kodu"] == urun_kodu]
                    
                    urun_toplam_agirlik = 0.0
                    
                    # Her BOM satiri icin agirlik hesapla
                    for _, bom_satir in urun_bom.iterrows():
                        if self.hammadde_df is not None and not self.hammadde_df.empty:
                            hammadde = self.hammadde_df[self.hammadde_df["Hammadde Kodu"] == bom_satir["Hammadde Kodu"]]
                            if not hammadde.empty:
                                hammadde_tipi = hammadde["Hammadde Tipi"].iloc[0]
                                
                                if hammadde_tipi == "Oluklu Mukavva":
                                    # Oluklu mukavva icin ozel hesaplama
                                    mukavva_tipi = hammadde["Mukavva Tipi"].iloc[0]
                                    agirlik = self.oluklu_agirlik_hesapla(
                                        mukavva_tipi,
                                        satis_adedi,
                                        bom_satir["Miktar"]
                                    )
                                    urun_toplam_agirlik += agirlik
                                else:
                                    # Diger hammaddeler icin normal hesaplama
                                    hammadde_agirligi = hammadde["m2 Agirlik"].iloc[0]
                                    miktar = bom_satir["Miktar"]
                                    agirlik = (hammadde_agirligi * miktar * satis_adedi) / 1000  # gr'dan kg'a cevir
                                    urun_toplam_agirlik += agirlik

                    toplam_agirlik += urun_toplam_agirlik

                    # Urun bazli agirlik bilgilerini kaydet
                    urun_agirliklar.append({
                        "Urun Kodu": urun_kodu,
                        "Urun Adi": urun_satislari["Urun Adi"].iloc[0] if not urun_satislari.empty else "",
                        "Satis Adedi": satis_adedi,
                        "Toplam Agirlik (kg)": urun_toplam_agirlik
                    })

            # Urun bazli agirlik bilgilerini DataFrame'e donustur
            urun_bazli_agirliklar = pd.DataFrame(urun_agirliklar)
            
            if self.loglayici:
                self.loglayici.info(f"Toplam agirlik hesaplandi: {toplam_agirlik:.2f} kg")

            return {
                "toplam_agirlik": toplam_agirlik,
                "urun_bazli_agirliklar": urun_bazli_agirliklar,
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Toplam agirlik hesaplama hatasi: {str(e)}")
            return {
                "toplam_agirlik": 0.0,
                "urun_bazli_agirliklar": pd.DataFrame(),
                "donem": f"{baslangic_tarihi} - {bitis_tarihi}" if baslangic_tarihi and bitis_tarihi else "Tum Zamanlar"
            }