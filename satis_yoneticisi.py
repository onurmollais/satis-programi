# -*- coding: utf-8 -*-
import pandas as pd
from typing import Dict, Any
from events import Event, EVENT_DATA_UPDATED

class SatisYoneticisi:
    """
    Satis, satisci ve hedeflerle ilgili islemleri gerceklestiren sinif.
    
    Bu sinif, satisci, hedef, satis ve pipeline ile ilgili islemleri gerceklestirir.
    """
    
    def __init__(self, veri_yoneticisi):
        """
        SatisYoneticisi sinifinin kurucu metodu.
        
        Args:
            veri_yoneticisi: Veri yoneticisi nesnesi
        """
        self.veri_yoneticisi = veri_yoneticisi
        self.repository = veri_yoneticisi.repository
        self.loglayici = veri_yoneticisi.loglayici
        self.event_manager = veri_yoneticisi.event_manager
    
    def satisci_ekle(self, yeni_satisci: Dict[str, Any]) -> None:
        """
        Yeni bir satisci ekler.
        
        Args:
            yeni_satisci: Yeni satisci bilgilerini iceren sozluk
        """
        yeni_satisci_df = pd.DataFrame([yeni_satisci])
        if self.veri_yoneticisi.satiscilar_df is None or self.veri_yoneticisi.satiscilar_df.empty:
            self.veri_yoneticisi.satiscilar_df = yeni_satisci_df
        else:
            self.veri_yoneticisi.satiscilar_df = pd.concat([self.veri_yoneticisi.satiscilar_df, yeni_satisci_df], ignore_index=True)
        self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_ekle"}))
    
    def satisci_duzenle(self, index: int, guncellenmis_satisci: Dict[str, Any]) -> None:
        """
        Bir satisciyi gunceller.
        
        Args:
            index: Guncellenecek satiscinin indeksi
            guncellenmis_satisci: Guncel satisci bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.satiscilar_df):
            for key, value in guncellenmis_satisci.items():
                self.veri_yoneticisi.satiscilar_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_duzenle"}))
    
    def satisci_sil(self, satisci_isim: str) -> None:
        """
        Bir satisciyi siler.
        
        Args:
            satisci_isim: Silinecek satiscinin ismi
        """
        if self.veri_yoneticisi.satiscilar_df is not None and not self.veri_yoneticisi.satiscilar_df.empty:
            self.veri_yoneticisi.satiscilar_df = self.veri_yoneticisi.satiscilar_df[self.veri_yoneticisi.satiscilar_df["Isim"] != satisci_isim]
            self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_sil"}))
    
    def satis_hedefi_ekle(self, yeni_hedef: Dict[str, Any]) -> None:
        """
        Yeni bir satis hedefi ekler.
        
        Args:
            yeni_hedef: Yeni hedef bilgilerini iceren sozluk
        """
        yeni_hedef_df = pd.DataFrame([yeni_hedef])
        if self.veri_yoneticisi.hedefler_df is None or self.veri_yoneticisi.hedefler_df.empty:
            self.veri_yoneticisi.hedefler_df = yeni_hedef_df
        else:
            self.veri_yoneticisi.hedefler_df = pd.concat([self.veri_yoneticisi.hedefler_df, yeni_hedef_df], ignore_index=True)
        
        # aylik_hedefler_df'i de guncelle
        self.veri_yoneticisi.aylik_hedefler_df = self.veri_yoneticisi.hedefler_df.copy()
        
        self.repository.save(self.veri_yoneticisi.hedefler_df, "monthly_targets")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_ekle", "table": "monthly_targets"}))
    
    def satis_hedefi_duzenle(self, index: int, yeni_hedef: Dict[str, Any]) -> None:
        """
        Bir satis hedefini gunceller.
        
        Args:
            index: Guncellenecek hedefin indeksi
            yeni_hedef: Guncel hedef bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.hedefler_df):
            for key, value in yeni_hedef.items():
                self.veri_yoneticisi.hedefler_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.hedefler_df, "monthly_targets")
            
            # aylik_hedefler_df'i de guncelle
            self.veri_yoneticisi.aylik_hedefler_df = self.veri_yoneticisi.hedefler_df.copy()
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_duzenle", "table": "monthly_targets"}))
    
    def satis_hedefi_sil(self, ay: str) -> None:
        """
        Bir satis hedefini siler.
        
        Args:
            ay: Silinecek hedefin ayi
        """
        if self.veri_yoneticisi.hedefler_df is not None and not self.veri_yoneticisi.hedefler_df.empty:
            # Ay formatini kontrol et ve duzelt
            try:
                ay_str = str(ay)
                if '-' in ay_str:
                    # MM-YYYY formatini kontrol et
                    ay_parcalari = ay_str.split('-')
                    if len(ay_parcalari) == 2:
                        ay_no = ay_parcalari[0].strip()
                        yil = ay_parcalari[1].strip()
                        # Ay numarasini 2 haneli, yili 4 haneli yap
                        ay = f"{int(ay_no):02d}-{yil}"
            except Exception as e:
                self.loglayici.error(f"Hedef silme icin ay formati donusturme hatasi: {str(e)}")
            
            # Hedefi sil
            self.veri_yoneticisi.hedefler_df = self.veri_yoneticisi.hedefler_df[self.veri_yoneticisi.hedefler_df["Ay"] != ay]
            self.repository.save(self.veri_yoneticisi.hedefler_df, "monthly_targets")
            
            # aylik_hedefler_df'i de guncelle
            self.veri_yoneticisi.aylik_hedefler_df = self.veri_yoneticisi.aylik_hedefler_df[self.veri_yoneticisi.aylik_hedefler_df["Ay"] != ay]
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_sil", "table": "monthly_targets"}))
    
    def satis_ekle(self, yeni_satis: Dict[str, Any]) -> None:
        """
        Yeni bir satis ekler.
        
        Args:
            yeni_satis: Yeni satis bilgilerini iceren sozluk
        """
        yeni_satis_df = pd.DataFrame([yeni_satis])
        
        if self.veri_yoneticisi.satislar_df is None or self.veri_yoneticisi.satislar_df.empty:
            self.veri_yoneticisi.satislar_df = yeni_satis_df
        else:
            self.veri_yoneticisi.satislar_df.loc[len(self.veri_yoneticisi.satislar_df)] = yeni_satis
        
        # Alt Musteri kolonu ekle
        if 'Alt Musteri' not in self.veri_yoneticisi.satislar_df.columns:
            self.veri_yoneticisi.satislar_df['Alt Musteri'] = ''
        
        self.repository.save(self.veri_yoneticisi.satislar_df, "sales")
        
        # Event'i tetikle
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "add"}))
    
    def pipeline_firsati_ekle(self, yeni_firsat: Dict[str, Any]) -> None:
        """
        Yeni bir pipeline firsati ekler.
        
        Args:
            yeni_firsat: Yeni firsat bilgilerini iceren sozluk
        """
        yeni_firsat_df = pd.DataFrame([yeni_firsat])
        if self.veri_yoneticisi.pipeline_df is None or self.veri_yoneticisi.pipeline_df.empty:
            self.veri_yoneticisi.pipeline_df = yeni_firsat_df
        else:
            self.veri_yoneticisi.pipeline_df = pd.concat([self.veri_yoneticisi.pipeline_df, yeni_firsat_df], ignore_index=True)
        self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_ekle"}))
    
    def pipeline_firsati_sil(self, musteri_adi: str) -> None:
        """
        Bir pipeline firsatini siler.
        
        Args:
            musteri_adi: Silinecek firsatin musteri adi
        """
        if self.veri_yoneticisi.pipeline_df is not None and not self.veri_yoneticisi.pipeline_df.empty:
            self.veri_yoneticisi.pipeline_df = self.veri_yoneticisi.pipeline_df[self.veri_yoneticisi.pipeline_df["Musteri Adi"] != musteri_adi]
            self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_sil"}))
    
    def pipeline_firsati_duzenle(self, index: int, guncellenmis_firsat: Dict[str, Any]) -> None:
        """
        Bir pipeline firsatini gunceller.
        
        Args:
            index: Guncellenecek firsatin indeksi
            guncellenmis_firsat: Guncel firsat bilgilerini iceren sozluk
        """
        if index >= 0 and index < len(self.veri_yoneticisi.pipeline_df):
            for key, value in guncellenmis_firsat.items():
                self.veri_yoneticisi.pipeline_df.at[index, key] = value
            self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_duzenle"})) 