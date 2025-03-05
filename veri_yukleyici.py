# -*- coding: utf-8 -*-
import pandas as pd
from typing import Dict, Optional, List, Tuple, Any
from events import Event, EVENT_DATA_UPDATED, EVENT_LOADING_PROGRESS, EVENT_LOADING_ERROR, EVENT_LOADING_COMPLETED, EVENT_ERROR_OCCURRED

class VeriYukleyici:
    """
    Veri yukleme ve kaydetme islemlerini yoneten sinif.
    """
    
    def __init__(self, veri_yoneticisi):
        """
        VeriYukleyici sinifinin kurucu metodu.
        
        Args:
            veri_yoneticisi: Veri yoneticisi nesnesi
        """
        self.veri_yoneticisi = veri_yoneticisi
        self.repository = veri_yoneticisi.repository
        self.loglayici = veri_yoneticisi.loglayici
        self.event_manager = veri_yoneticisi.event_manager

    def tum_verileri_yukle(self, dosya_yolu: str) -> None:
        """
        Excel dosyasindan tum verileri yukler.
        
        Args:
            dosya_yolu: Excel dosyasinin yolu
        """
        try:
            excel = pd.ExcelFile(dosya_yolu)
            self.loglayici.info(f"Excel dosyasi acildi: {dosya_yolu}")
            yukleme_hatalari = []
            toplam_tablo = 11  # Toplam tablo sayisi
            yuklenen_tablo = 0
            
            for sheet, attr, table in [
                ('Satiscilar', 'satiscilar_df', 'sales_reps'),
                ('Aylik Hedefler', 'hedefler_df', 'monthly_targets'),
                ('Pipeline', 'pipeline_df', 'pipeline'),
                ('Musteriler', 'musteriler_df', 'customers'),
                ('Ziyaretler', 'ziyaretler_df', 'visits'),
                ('Sikayetler', 'sikayetler_df', 'complaints'),
                ('Aylik Satislar Takibi', 'satislar_df', 'sales'),
                ('Hammadde Maliyetleri', 'hammadde_df', 'hammadde'),
                ('Urun BOM', 'urun_bom_df', 'urun_bom')
            ]:
                try:
                    df = pd.read_excel(excel, sheet)
                    setattr(self.veri_yoneticisi, attr, df)
                    self.repository.save(df, table)
                    self.loglayici.info(f"{sheet} tablosu yuklendi ve kaydedildi.")
                    
                    # Aylik Hedefler tablosunu aylik_hedefler_df'e de kopyala
                    if sheet == 'Aylik Hedefler' and df is not None and not df.empty:
                        self.veri_yoneticisi.aylik_hedefler_df = df.copy()
                        self.loglayici.info("Aylik hedefler kopyalandi.")
                        
                        # Ay sutununu kontrol et ve duzelt
                        if 'Ay' in df.columns:
                            try:
                                # Her bir ay degerini kontrol et ve duzelt
                                for i, ay in enumerate(df['Ay']):
                                    try:
                                        ay_str = str(ay)
                                        if '-' in ay_str:
                                            # MM-YYYY formatini kontrol et
                                            ay_parcalari = ay_str.split('-')
                                            if len(ay_parcalari) == 2:
                                                ay_no = ay_parcalari[0].strip()
                                                yil = ay_parcalari[1].strip()
                                                # Ay numarasini 2 haneli, yili 4 haneli yap
                                                yeni_ay = f"{int(ay_no):02d}-{yil}"
                                                df.at[i, 'Ay'] = yeni_ay
                                                self.veri_yoneticisi.aylik_hedefler_df.at[i, 'Ay'] = yeni_ay
                                        elif len(ay_str) == 6:  # YYYYMM formati
                                            yil = ay_str[:4]
                                            ay_no = ay_str[4:]
                                            yeni_ay = f"{int(ay_no):02d}-{yil}"
                                            df.at[i, 'Ay'] = yeni_ay
                                            self.veri_yoneticisi.aylik_hedefler_df.at[i, 'Ay'] = yeni_ay
                                    except Exception as e:
                                        self.loglayici.error(f"Hedefler icin ay formati donusturme hatasi: {str(e)}")
                                
                                # Degisiklikleri kaydet
                                self.veri_yoneticisi.hedefler_df = df
                                self.repository.save(df, table)
                                self.loglayici.info("Aylik hedefler formati duzeltildi ve kaydedildi.")
                            except Exception as e:
                                self.loglayici.error(f"Hedefler icin ay formati donusturme hatasi: {str(e)}")
                    
                    yuklenen_tablo += 1
                    ilerleme = (yuklenen_tablo / toplam_tablo) * 100
                    
                    # Progress event'ini gonder
                    if self.event_manager:
                        self.event_manager.emit(Event(EVENT_LOADING_PROGRESS, {
                            "progress": ilerleme,
                            "current_table": sheet,
                            "total_tables": toplam_tablo,
                            "loaded_tables": yuklenen_tablo
                        }))
                        
                except Exception as e:
                    hata_mesaji = f"{sheet} tablosu yuklenemedi: {str(e)}"
                    self.loglayici.error(hata_mesaji)
                    yukleme_hatalari.append(hata_mesaji)
                    if self.event_manager:
                        self.event_manager.emit(Event(EVENT_LOADING_ERROR, {"message": hata_mesaji}))
            
            # satislar_df'e gerekli ozellikleri ekle
            if self.veri_yoneticisi.satislar_df is not None:
                # Alt Musteri kolonu ekle
                if 'Alt Musteri' not in self.veri_yoneticisi.satislar_df.columns:
                    self.veri_yoneticisi.satislar_df['Alt Musteri'] = ''

                # Ay formatini kontrol et ve MM-YYYY formatina donustur
                if 'Ay' in self.veri_yoneticisi.satislar_df.columns:
                    self.veri_yoneticisi.satislar_df['Ay'] = self.veri_yoneticisi.satislar_df['Ay'].astype(str)
                    
                    self.loglayici.info(f"Satislar veri cercevesi Ay sutunu: {self.veri_yoneticisi.satislar_df['Ay'].tolist()}")
                    
                    for i, ay in enumerate(self.veri_yoneticisi.satislar_df['Ay']):
                        try:
                            if len(ay) == 6:  # YYYYMM formati
                                yil = ay[:4]
                                ay_no = ay[4:]
                                yeni_ay = f"{ay_no}-{yil}"
                                self.veri_yoneticisi.satislar_df.at[i, 'Ay'] = yeni_ay
                        except Exception as e:
                            self.loglayici.error(f"Ay formati donusturme hatasi: {str(e)}")

                    if any('-' in str(ay) for ay in self.veri_yoneticisi.satislar_df['Ay']):
                        # MM-YYYY formatina donustur
                        if not self.veri_yoneticisi.satislar_df.empty:
                            try:
                                # Her bir ay degerini kontrol et ve duzelt
                                for i, ay in enumerate(self.veri_yoneticisi.satislar_df['Ay']):
                                    try:
                                        ay_parcalari = ay.split('-')
                                        if len(ay_parcalari) == 2:
                                            # Formati MM-YYYY olarak duzenle
                                            ay_no = ay_parcalari[0].strip()
                                            yil = ay_parcalari[1].strip()
                                            # Ay numarasini 2 haneli, yili 4 haneli yap
                                            yeni_ay = f"{int(ay_no):02d}-{yil}"
                                            self.veri_yoneticisi.satislar_df.at[i, 'Ay'] = yeni_ay
                                        else:
                                            self.loglayici.warning(f"Satislar icin ay formati taninamadi: {ay}")
                                    except Exception as e:
                                        self.loglayici.error(f"Ay formati donusturme hatasi: {str(e)}")
                            except Exception as e:
                                self.loglayici.error(f"Ay formati donusturme hatasi: {str(e)}")

                self.repository.save(self.veri_yoneticisi.satislar_df, "sales")
                self.loglayici.info(f"Satislar tablosu guncellendi ve kaydedildi. Satır sayısı: {len(self.veri_yoneticisi.satislar_df)}")
            else:
                self.loglayici.warning("satislar_df boş olduğu için güncellenemedi")
            
            if len(yukleme_hatalari) > 0:
                self.loglayici.warning(f"Bazi tablolar yuklenemedi: {yukleme_hatalari}")
            else:
                self.loglayici.info("Tum tablolar basariyla yuklendi.")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_LOADING_COMPLETED, {"message": "Tum veriler yuklendi"}))
                    self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "tum_verileri_yukle"}))
                    
        except Exception as e:
            hata_mesaji = f"Veri yukleme hatasi: {str(e)}"
            self.loglayici.error(hata_mesaji)
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_LOADING_ERROR, {"message": hata_mesaji}))

    def tum_verileri_yukle_paginated(self, dosya_yolu, sayfa=1, sayfa_boyutu=1000):
        """
        Excel dosyasindan sayfalandirilmis sekilde veri yukler.
        
        Args:
            dosya_yolu: Excel dosyasinin yolu
            sayfa: Sayfa numarasi
            sayfa_boyutu: Sayfa boyutu
        """
        try:
            excel = pd.ExcelFile(dosya_yolu)
            self.veri_yoneticisi.satiscilar_df = pd.read_excel(excel, 'Satiscilar', nrows=sayfa_boyutu, skiprows=(sayfa-1)*sayfa_boyutu)
            self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
            self.loglayici.info(f"Satiscilar tablosu yuklendi: Sayfa {sayfa}, Boyut {sayfa_boyutu}")
        except Exception as e:
            self.loglayici.error(f"Satiscilar tablosu yuklenemedi: {str(e)}")
            
        try:
            # Aylik Hedefler tablosunu yukle
            hedefler_df = pd.read_excel(excel, 'Aylik Hedefler', nrows=sayfa_boyutu, skiprows=(sayfa-1)*sayfa_boyutu)
            self.veri_yoneticisi.hedefler_df = hedefler_df
            
            # aylik_hedefler_df'e de kopyala
            self.veri_yoneticisi.aylik_hedefler_df = hedefler_df.copy()
            
            # Ay sutununu kontrol et ve duzelt
            if 'Ay' in hedefler_df.columns:
                try:
                    # Her bir ay degerini kontrol et ve duzelt
                    for i, ay in enumerate(hedefler_df['Ay']):
                        try:
                            ay_str = str(ay)
                            if '-' in ay_str:
                                # MM-YYYY formatini kontrol et
                                ay_parcalari = ay_str.split('-')
                                if len(ay_parcalari) == 2:
                                    ay_no = ay_parcalari[0].strip()
                                    yil = ay_parcalari[1].strip()
                                    # Ay numarasini 2 haneli, yili 4 haneli yap
                                    yeni_ay = f"{int(ay_no):02d}-{yil}"
                                    hedefler_df.at[i, 'Ay'] = yeni_ay
                                    self.veri_yoneticisi.aylik_hedefler_df.at[i, 'Ay'] = yeni_ay
                                elif len(ay_str) == 6:  # YYYYMM formati
                                    yil = ay_str[:4]
                                    ay_no = ay_str[4:]
                                    yeni_ay = f"{int(ay_no):02d}-{yil}"
                                    hedefler_df.at[i, 'Ay'] = yeni_ay
                                    self.veri_yoneticisi.aylik_hedefler_df.at[i, 'Ay'] = yeni_ay
                        except Exception as e:
                            self.loglayici.error(f"Hedefler icin ay formati donusturme hatasi: {str(e)}")
                    
                    # Degisiklikleri kaydet
                    self.veri_yoneticisi.hedefler_df = hedefler_df
                except Exception as e:
                    self.loglayici.error(f"Hedefler icin ay formati donusturme hatasi: {str(e)}")
            
            self.repository.save(hedefler_df, "monthly_targets")
            self.loglayici.info(f"Aylik Hedefler tablosu yuklendi ve kopyalandi: Sayfa {sayfa}, Boyut {sayfa_boyutu}")
        except Exception as e:
            self.loglayici.error(f"Aylik Hedefler tablosu yuklenemedi: {str(e)}")

    def tum_verileri_kaydet(self, dosya_yolu):
        """
        Tum verileri Excel dosyasina kaydeder.
        
        Args:
            dosya_yolu: Excel dosyasinin yolu
        """
        try:
            with pd.ExcelWriter(dosya_yolu) as writer:
                # Her DataFrame icin None kontrolu yap
                if self.veri_yoneticisi.satiscilar_df is not None:
                    self.veri_yoneticisi.satiscilar_df.to_excel(writer, sheet_name='Satiscilar', index=False)
                
                if self.veri_yoneticisi.hedefler_df is not None:
                    self.veri_yoneticisi.hedefler_df.to_excel(writer, sheet_name='Aylik Hedefler', index=False)
                
                if self.veri_yoneticisi.satislar_df is not None:
                    self.veri_yoneticisi.satislar_df.to_excel(writer, sheet_name='Aylik Satislar Takibi', index=False)
                
                if self.veri_yoneticisi.pipeline_df is not None:
                    self.veri_yoneticisi.pipeline_df.to_excel(writer, sheet_name='Pipeline', index=False)
                
                if self.veri_yoneticisi.musteriler_df is not None:
                    self.veri_yoneticisi.musteriler_df.to_excel(writer, sheet_name='Musteriler', index=False)
                
                if self.veri_yoneticisi.ziyaretler_df is not None:
                    self.veri_yoneticisi.ziyaretler_df.to_excel(writer, sheet_name='Ziyaretler', index=False)
                
                if self.veri_yoneticisi.sikayetler_df is not None:
                    self.veri_yoneticisi.sikayetler_df.to_excel(writer, sheet_name='Sikayetler', index=False)
                
                if self.veri_yoneticisi.hammadde_df is not None:
                    self.veri_yoneticisi.hammadde_df.to_excel(writer, sheet_name='Hammadde Maliyetleri', index=False)
                
                if self.veri_yoneticisi.urun_bom_df is not None:
                    self.veri_yoneticisi.urun_bom_df.to_excel(writer, sheet_name='Urun BOM', index=False)
                
            self.loglayici.info("Tum veriler basariyla Excel dosyasina kaydedildi.")
            
        except Exception as e:
            hata_mesaji = f"Veri kaydetme hatasi: {str(e)}"
            self.loglayici.error(hata_mesaji)
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": hata_mesaji}))
            raise 