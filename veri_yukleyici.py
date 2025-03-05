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

    def parcali_veri_yukle(self, dosya_yolu, tablo_adi, parca_boyutu=1000, islem_fonksiyonu=None):
        """
        Excel dosyasindan belirli bir tabloyu parcalar halinde yukler ve isler.
        
        Bu fonksiyon, buyuk veri setlerini belirtilen boyutta parcalara ayirarak
        her parcayi ayri ayri yukler ve isler. Bu sayede bellek kullanimi optimize edilir
        ve buyuk veri setleri daha verimli sekilde islenir.
        
        Args:
            dosya_yolu: Excel dosyasinin yolu
            tablo_adi: Yuklenecek tablonun adi
            parca_boyutu: Her parcada yuklenecek satir sayisi
            islem_fonksiyonu: Her parca icin uygulanacak islem fonksiyonu
            
        Returns:
            Islenmis veri cercevesi
        """
        try:
            # Excel dosyasini ac
            excel = pd.ExcelFile(dosya_yolu)
            
            # Tablonun toplam satir sayisini bul
            toplam_satir = pd.read_excel(excel, tablo_adi, nrows=0).shape[0]
            parca_sayisi = (toplam_satir + parca_boyutu - 1) // parca_boyutu  # Yukarı yuvarlama
            
            self.loglayici.info(f"Parcali veri yukleme basladi: {tablo_adi}, Toplam {toplam_satir} satir, {parca_sayisi} parca")
            
            # Ilerleme bilgisi
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_LOADING_PROGRESS, {
                    "progress": 0,
                    "current_table": tablo_adi,
                    "total_chunks": parca_sayisi,
                    "loaded_chunks": 0
                }))
            
            # Sonuc DataFrame'i olustur
            sonuc_df_list = []
            
            # Parcalar halinde yukle
            for i in range(parca_sayisi):
                baslangic_satir = i * parca_boyutu
                
                try:
                    # Parcayi yukle
                    parca_df = pd.read_excel(excel, tablo_adi, skiprows=baslangic_satir, nrows=parca_boyutu)
                    
                    # Islem fonksiyonu varsa uygula
                    if islem_fonksiyonu:
                        try:
                            islenmis_parca = islem_fonksiyonu(parca_df)
                            sonuc_df_list.append(islenmis_parca)
                        except Exception as e:
                            self.loglayici.error(f"Parca isleme hatasi: {str(e)}")
                            sonuc_df_list.append(parca_df)  # Hata durumunda orijinal parcayi ekle
                    else:
                        sonuc_df_list.append(parca_df)
                    
                    # Ilerleme bilgisi
                    if self.event_manager:
                        ilerleme = ((i + 1) / parca_sayisi) * 100
                        self.event_manager.emit(Event(EVENT_LOADING_PROGRESS, {
                            "progress": ilerleme,
                            "current_table": tablo_adi,
                            "total_chunks": parca_sayisi,
                            "loaded_chunks": i + 1
                        }))
                    
                    self.loglayici.debug(f"Parca {i+1}/{parca_sayisi} yuklendi ve islendi.")
                    
                except Exception as e:
                    self.loglayici.error(f"Parca {i+1} yukleme hatasi: {str(e)}")
                    if self.event_manager:
                        self.event_manager.emit(Event(EVENT_LOADING_ERROR, {
                            "message": f"Parca {i+1} yukleme hatasi: {str(e)}",
                            "table": tablo_adi
                        }))
            
            # Tum parcalari birlestir
            if sonuc_df_list:
                sonuc_df = pd.concat(sonuc_df_list, ignore_index=True)
                self.loglayici.info(f"Parcali veri yukleme tamamlandi: {tablo_adi}, {len(sonuc_df)} satir yuklendi.")
                
                # Veri yoneticisine kaydet
                self._veri_yoneticisine_kaydet(tablo_adi, sonuc_df)
                
                # Yukleme tamamlandi bilgisi
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_LOADING_COMPLETED, {
                        "message": f"{tablo_adi} tablosu yuklendi",
                        "table": tablo_adi
                    }))
                    self.event_manager.emit(Event(EVENT_DATA_UPDATED, {
                        "source": "parcali_veri_yukle",
                        "table": tablo_adi
                    }))
                
                return sonuc_df
            else:
                self.loglayici.warning(f"Parcali veri yukleme basarisiz: {tablo_adi}, hicbir parca yuklenemedi.")
                return None
                
        except Exception as e:
            hata_mesaji = f"Parcali veri yukleme hatasi: {str(e)}"
            self.loglayici.error(hata_mesaji)
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_LOADING_ERROR, {
                    "message": hata_mesaji,
                    "table": tablo_adi
                }))
            return None
    
    def _veri_yoneticisine_kaydet(self, tablo_adi, df):
        """
        Yuklenen veriyi veri yoneticisine kaydeder.
        
        Args:
            tablo_adi: Tablo adi
            df: Veri cercevesi
        """
        # Tablo adina gore veri yoneticisindeki ilgili DataFrame'e kaydet
        if tablo_adi == 'Satiscilar':
            self.veri_yoneticisi.satiscilar_df = df
            self.repository.save(df, "sales_reps")
        elif tablo_adi == 'Aylik Hedefler':
            self.veri_yoneticisi.hedefler_df = df
            self.veri_yoneticisi.aylik_hedefler_df = df.copy()
            self.repository.save(df, "monthly_targets")
            
            # Ay sutununu kontrol et ve duzelt
            if 'Ay' in df.columns:
                self._ay_formatini_duzenle(df, "hedefler_df")
                
        elif tablo_adi == 'Pipeline':
            self.veri_yoneticisi.pipeline_df = df
            self.repository.save(df, "pipeline")
        elif tablo_adi == 'Musteriler':
            self.veri_yoneticisi.musteriler_df = df
            self.repository.save(df, "customers")
        elif tablo_adi == 'Ziyaretler':
            self.veri_yoneticisi.ziyaretler_df = df
            self.repository.save(df, "visits")
        elif tablo_adi == 'Sikayetler':
            self.veri_yoneticisi.sikayetler_df = df
            self.repository.save(df, "complaints")
        elif tablo_adi == 'Aylik Satislar Takibi':
            self.veri_yoneticisi.satislar_df = df
            
            # Alt Musteri kolonu ekle
            if 'Alt Musteri' not in df.columns:
                self.veri_yoneticisi.satislar_df['Alt Musteri'] = ''
                
            # Ay formatini kontrol et ve duzelt
            if 'Ay' in df.columns:
                self._ay_formatini_duzenle(df, "satislar_df")
                
            self.repository.save(self.veri_yoneticisi.satislar_df, "sales")
        elif tablo_adi == 'Hammadde Maliyetleri':
            self.veri_yoneticisi.hammadde_df = df
            self.repository.save(df, "hammadde")
        elif tablo_adi == 'Urun BOM':
            self.veri_yoneticisi.urun_bom_df = df
            self.repository.save(df, "urun_bom")
        else:
            self.loglayici.warning(f"Bilinmeyen tablo adi: {tablo_adi}")
    
    def _ay_formatini_duzenle(self, df, df_adi):
        """
        Ay sutununu MM-YYYY formatina donusturur.
        
        Args:
            df: Veri cercevesi
            df_adi: Veri cercevesinin adi
        """
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
                            
                            # Hedefler icin aylik_hedefler_df'i de guncelle
                            if df_adi == "hedefler_df":
                                self.veri_yoneticisi.aylik_hedefler_df.at[i, 'Ay'] = yeni_ay
                    elif len(ay_str) == 6:  # YYYYMM formati
                        yil = ay_str[:4]
                        ay_no = ay_str[4:]
                        yeni_ay = f"{int(ay_no):02d}-{yil}"
                        df.at[i, 'Ay'] = yeni_ay
                        
                        # Hedefler icin aylik_hedefler_df'i de guncelle
                        if df_adi == "hedefler_df":
                            self.veri_yoneticisi.aylik_hedefler_df.at[i, 'Ay'] = yeni_ay
                except Exception as e:
                    self.loglayici.error(f"{df_adi} icin ay formati donusturme hatasi: {str(e)}")
        except Exception as e:
            self.loglayici.error(f"{df_adi} icin ay formati donusturme hatasi: {str(e)}") 