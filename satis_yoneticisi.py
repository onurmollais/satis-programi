# -*- coding: utf-8 -*-
import pandas as pd
from typing import Dict, Any, List, Callable, Optional, Iterator
from events import Event, EVENT_DATA_UPDATED
from decimal import Decimal, getcontext

# Decimal hassasiyetini ayarla (28 basamak genellikle finansal işlemler için yeterlidir)
getcontext().prec = 28

class SatisYoneticisi:
    """
    Satış, satıcı ve hedeflerle ilgili işlemleri gerçekleştiren optimize edilmiş sınıf.
    Float yerine Decimal kullanılarak hassasiyet sorunları giderilmiştir.
    """

    def __init__(self, veri_yoneticisi):
        """
        Args:
            veri_yoneticisi: Veri yöneticisi nesnesi
        """
        self.veri_yoneticisi = veri_yoneticisi
        self.repository = veri_yoneticisi.repository
        self.loglayici = veri_yoneticisi.loglayici
        self.event_manager = veri_yoneticisi.event_manager
        
        # Veri tiplerini optimize et (Decimal ile)
        self._optimize_all_dataframes()

    def _optimize_dataframe(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """DataFrame'in veri tiplerini tabloya özel olarak optimize eder (Decimal ile)."""
        if df is None or df.empty:
            return df
        
        categorical_columns = {
            'sales': ['Ana Musteri', 'Alt Musteri', 'Satis Temsilcisi', 'Ay', 'Urun Kodu', 'Urun Adi', 'Para Birimi'],
            'sales_reps': ['Isim', 'Bolge', 'Durum'],
            'monthly_targets': ['Ay', 'Para Birimi'],
            'pipeline': ['Musteri Adi', 'Satis Temsilcisi', 'Sektor', 'Pipeline Asamasi']
        }.get(table_name, [])
        
        numeric_columns = {
            'sales': ['Miktar', 'Birim Fiyat', 'Satis Miktari'],
            'sales_reps': [],
            'monthly_targets': ['Hedef'],
            'pipeline': ['Potansiyel Ciro']
        }.get(table_name, [])
        
        # Kategorik dönüşüm
        for col in categorical_columns:
            if col in df.columns:
                df[col] = df[col].astype('category')
                self.loglayici.debug(f"{table_name}.{col} kategorik tipe dönüştürüldü")
        
        # Sayısal dönüşüm (Decimal -> float)
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: float(x) if pd.notna(x) else None)
                self.loglayici.debug(f"{table_name}.{col} float tipe dönüştürüldü")
        
        return df

    def _optimize_all_dataframes(self):
        """Tüm DataFrame'leri optimize eder (Decimal ile)."""
        dfs = [
            ('satislar_df', 'sales'),
            ('satiscilar_df', 'sales_reps'),
            ('hedefler_df', 'monthly_targets'),
            ('pipeline_df', 'pipeline')
        ]
        for attr, table_name in dfs:
            df = getattr(self.veri_yoneticisi, attr, None)
            if df is not None and not df.empty:
                setattr(self.veri_yoneticisi, attr, self._optimize_dataframe(df, table_name))
                self.loglayici.info(f"{attr} optimize edildi (Decimal ile)")

    def _bos_df_kontrol(self, df: pd.DataFrame, mesaj: str) -> bool:
        """Boş DataFrame kontrolü için yardımcı metod."""
        if df is None or df.empty:
            self.loglayici.warning(mesaj)
            return True
        return False

    def hesapla_toplam_tutar(self, miktar: Any, birim_fiyat: Any) -> Decimal:
        """Miktar ve birim fiyat ile toplam tutarı hesaplar."""
        miktar_decimal = Decimal(str(miktar)) if pd.notna(miktar) else Decimal('0')
        birim_fiyat_decimal = Decimal(str(birim_fiyat)) if pd.notna(birim_fiyat) else Decimal('0')
        toplam = miktar_decimal * birim_fiyat_decimal
        return toplam.quantize(Decimal('0.01'))  # 2 ondalık basamağa yuvarla

    def parcali_veri_isle(self, 
                         veri_df: pd.DataFrame, 
                         parca_boyutu: int = 1000, 
                         islem_fonksiyonu: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None,
                         ilerleme_callback: Optional[Callable[[int, int], None]] = None) -> pd.DataFrame:
        """
        Büyük veri setlerini parçalar halinde işler ve optimize eder (Decimal ile).
        """
        if self._bos_df_kontrol(veri_df, "İşlenecek veri bulunamadı"):
            return veri_df
        
        try:
            toplam_satir = len(veri_df)
            parca_sayisi = (toplam_satir + parca_boyutu - 1) // parca_boyutu
            sonuc_df_list = []
            
            self.loglayici.info(f"Parçalı veri işleme başladı: {toplam_satir} satır, {parca_sayisi} parça")
            
            for i in range(parca_sayisi):
                baslangic = i * parca_boyutu
                bitis = min((i + 1) * parca_boyutu, toplam_satir)
                parca_df = veri_df.iloc[baslangic:bitis]
                
                if islem_fonksiyonu:
                    try:
                        sonuc_df_list.append(islem_fonksiyonu(parca_df))
                    except Exception as e:
                        self.loglayici.error(f"Parça işleme hatası: {str(e)}")
                        sonuc_df_list.append(parca_df)
                else:
                    sonuc_df_list.append(parca_df)
                
                if ilerleme_callback:
                    ilerleme_callback(i + 1, parca_sayisi)
                
                self.loglayici.debug(f"Parça {i+1}/{parca_sayisi} işlendi")
            
            sonuc_df = pd.concat(sonuc_df_list, ignore_index=True)
            return self._optimize_dataframe(sonuc_df, 'sales')
            
        except Exception as e:
            self.loglayici.error(f"Parçalı veri işleme hatası: {str(e)}")
            return veri_df

    def parcali_veri_iterator(self, 
                             veri_df: pd.DataFrame, 
                             parca_boyutu: int = 1000) -> Iterator[pd.DataFrame]:
        """
        Büyük veri setlerini parçalar halinde işler ve iterator döner (Decimal ile).
        """
        if self._bos_df_kontrol(veri_df, "İşlenecek veri bulunamadı"):
            return
        
        try:
            toplam_satir = len(veri_df)
            parca_sayisi = (toplam_satir + parca_boyutu - 1) // parca_boyutu
            
            self.loglayici.info(f"Parçalı veri iterator başladı: {toplam_satir} satır, {parca_sayisi} parça")
            
            for i in range(parca_sayisi):
                baslangic = i * parca_boyutu
                bitis = min((i + 1) * parca_boyutu, toplam_satir)
                parca_df = veri_df.iloc[baslangic:bitis]
                yield self._optimize_dataframe(parca_df, 'sales')
                self.loglayici.debug(f"Parça {i+1}/{parca_sayisi} hazırlandı")
                
        except Exception as e:
            self.loglayici.error(f"Parçalı veri iterator hatası: {str(e)}")
            return

    def toplu_satis_ekle(self, satislar_listesi: List[Dict[str, Any]], parca_boyutu: int = 100) -> None:
        if not satislar_listesi:
            self.loglayici.warning("Eklenecek satış bulunamadı")
            return
        
        try:
            satis_df = pd.DataFrame(satislar_listesi)
            satis_df = self._optimize_dataframe(satis_df, 'sales')
            
            if 'Miktar' in satis_df.columns and 'Birim Fiyat' in satis_df.columns:
                satis_df['Toplam Tutar'] = satis_df.apply(
                    lambda row: float(self.hesapla_toplam_tutar(row['Miktar'], row['Birim Fiyat'])), axis=1
                )
            
            if self._bos_df_kontrol(self.veri_yoneticisi.satislar_df, "Satışlar DataFrame'i boş, yeni veriyle başlatılıyor"):
                self.veri_yoneticisi.satislar_df = satis_df
            else:
                self.veri_yoneticisi.satislar_df = pd.concat([self.veri_yoneticisi.satislar_df, satis_df], ignore_index=True)
            
            if 'Alt Musteri' not in self.veri_yoneticisi.satislar_df.columns:
                self.veri_yoneticisi.satislar_df['Alt Musteri'] = pd.Series('', dtype='category')
            
            # SQLite uyumluluğu için veri tiplerini kontrol et ve logla
            for col in self.veri_yoneticisi.satislar_df.columns:
                if self.veri_yoneticisi.satislar_df[col].dtype.name == 'category':
                    self.veri_yoneticisi.satislar_df[col] = self.veri_yoneticisi.satislar_df[col].astype(str)
                elif self.veri_yoneticisi.satislar_df[col].dtype.name == 'object':
                    self.veri_yoneticisi.satislar_df[col] = self.veri_yoneticisi.satislar_df[col].apply(
                        lambda x: str(x) if pd.notna(x) else None
                    )
            
            self.loglayici.debug(f"Kaydedilecek satış verisi sütunları: {list(self.veri_yoneticisi.satislar_df.columns)}")
            self.loglayici.debug(f"Veri tipleri: {self.veri_yoneticisi.satislar_df.dtypes.to_dict()}")
            self.loglayici.debug(f"Örnek veri: {self.veri_yoneticisi.satislar_df.head(5).to_dict(orient='records')}")
            
            self.repository.save(self.veri_yoneticisi.satislar_df, "sales")
            self.loglayici.info(f"Toplu satış ekleme tamamlandı: {len(satis_df)} satış eklendi")
            
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "bulk_add"}))
        
        except Exception as e:
            self.loglayici.error(f"Toplu satış ekleme hatası: {str(e)}")
            raise

    def satisci_ekle(self, yeni_satisci: Dict[str, Any]) -> None:
        """Yeni satıcıyı optimize şekilde ekler."""
        yeni_satisci_df = pd.DataFrame([yeni_satisci])
        yeni_satisci_df = self._optimize_dataframe(yeni_satisci_df, 'sales_reps')
        
        if self._bos_df_kontrol(self.veri_yoneticisi.satiscilar_df, "Satıcılar DataFrame'i boş, yeni veriyle başlatılıyor"):
            self.veri_yoneticisi.satiscilar_df = yeni_satisci_df
        else:
            self.veri_yoneticisi.satiscilar_df = pd.concat([self.veri_yoneticisi.satiscilar_df, yeni_satisci_df], ignore_index=True)
        
        self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_ekle"}))

    def satisci_duzenle(self, index: int, guncellenmis_satisci: Dict[str, Any]) -> None:
        """Satıcıyı vektörel ve optimize şekilde günceller."""
        if 0 <= index < len(self.veri_yoneticisi.satiscilar_df):
            self.veri_yoneticisi.satiscilar_df.loc[index, list(guncellenmis_satisci.keys())] = list(guncellenmis_satisci.values())
            self.veri_yoneticisi.satiscilar_df = self._optimize_dataframe(self.veri_yoneticisi.satiscilar_df, 'sales_reps')
            self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_duzenle"}))

    def satisci_sil(self, satisci_isim: str) -> None:
        """Satıcıyı vektörel şekilde siler."""
        if not self._bos_df_kontrol(self.veri_yoneticisi.satiscilar_df, "Satıcılar DataFrame'i boş"):
            self.veri_yoneticisi.satiscilar_df = self.veri_yoneticisi.satiscilar_df[
                self.veri_yoneticisi.satiscilar_df["Isim"] != satisci_isim
            ]
            self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_sil"}))

    def satis_hedefi_ekle(self, yeni_hedef: Dict[str, Any]) -> None:
        """Satış hedefini optimize şekilde ekler (Decimal ile)."""
        yeni_hedef_df = pd.DataFrame([yeni_hedef])
        yeni_hedef_df = self._optimize_dataframe(yeni_hedef_df, 'monthly_targets')
        
        if self._bos_df_kontrol(self.veri_yoneticisi.hedefler_df, "Hedefler DataFrame'i boş, yeni veriyle başlatılıyor"):
            self.veri_yoneticisi.hedefler_df = yeni_hedef_df
        else:
            self.veri_yoneticisi.hedefler_df = pd.concat([self.veri_yoneticisi.hedefler_df, yeni_hedef_df], ignore_index=True)
        
        self.veri_yoneticisi.aylik_hedefler_df = self.veri_yoneticisi.hedefler_df
        self.repository.save(self.veri_yoneticisi.hedefler_df, "monthly_targets")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_ekle", "table": "monthly_targets"}))

    def satis_hedefi_duzenle(self, index: int, yeni_hedef: Dict[str, Any]) -> None:
        """Satış hedefini vektörel ve optimize şekilde günceller (Decimal ile)."""
        if 0 <= index < len(self.veri_yoneticisi.hedefler_df):
            self.veri_yoneticisi.hedefler_df.loc[index, list(yeni_hedef.keys())] = list(yeni_hedef.values())
            self.veri_yoneticisi.hedefler_df = self._optimize_dataframe(self.veri_yoneticisi.hedefler_df, 'monthly_targets')
            self.veri_yoneticisi.aylik_hedefler_df = self.veri_yoneticisi.hedefler_df
            self.repository.save(self.veri_yoneticisi.hedefler_df, "monthly_targets")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_duzenle", "table": "monthly_targets"}))

    def satis_hedefi_sil(self, ay: str) -> None:
        """Satış hedefini vektörel şekilde siler."""
        if not self._bos_df_kontrol(self.veri_yoneticisi.hedefler_df, "Hedefler DataFrame'i boş"):
            ay = f"{int(ay.split('-')[0]):02d}-{ay.split('-')[1]}" if '-' in ay else ay
            self.veri_yoneticisi.hedefler_df = self.veri_yoneticisi.hedefler_df[
                self.veri_yoneticisi.hedefler_df["Ay"] != ay
            ]
            self.veri_yoneticisi.aylik_hedefler_df = self.veri_yoneticisi.hedefler_df
            self.repository.save(self.veri_yoneticisi.hedefler_df, "monthly_targets")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satis_hedefi_sil", "table": "monthly_targets"}))

    def satis_ekle(self, yeni_satis: Dict[str, Any]) -> None:
        """Satışı optimize şekilde ekler (Decimal ile)."""
        yeni_satis_df = pd.DataFrame([yeni_satis])
        yeni_satis_df = self._optimize_dataframe(yeni_satis_df, 'sales')
        
        # Toplam tutar hesapla (örnek olarak)
        if 'Miktar' in yeni_satis_df.columns and 'Birim Fiyat' in yeni_satis_df.columns:
            yeni_satis_df['Toplam Tutar'] = yeni_satis_df.apply(
                lambda row: self.hesapla_toplam_tutar(row['Miktar'], row['Birim Fiyat']), axis=1
            )
        
        if self._bos_df_kontrol(self.veri_yoneticisi.satislar_df, "Satışlar DataFrame'i boş, yeni veriyle başlatılıyor"):
            self.veri_yoneticisi.satislar_df = yeni_satis_df
        else:
            self.veri_yoneticisi.satislar_df = pd.concat([self.veri_yoneticisi.satislar_df, yeni_satis_df], ignore_index=True)
        
        if 'Alt Musteri' not in self.veri_yoneticisi.satislar_df.columns:
            self.veri_yoneticisi.satislar_df['Alt Musteri'] = pd.Series('', dtype='category')
        
        self.repository.save(self.veri_yoneticisi.satislar_df, "sales")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "add"}))

    def pipeline_firsati_ekle(self, yeni_firsat: Dict[str, Any]) -> None:
        """Pipeline fırsatını optimize şekilde ekler (Decimal ile)."""
        yeni_firsat_df = pd.DataFrame([yeni_firsat])
        yeni_firsat_df = self._optimize_dataframe(yeni_firsat_df, 'pipeline')
        
        if self._bos_df_kontrol(self.veri_yoneticisi.pipeline_df, "Pipeline DataFrame'i boş, yeni veriyle başlatılıyor"):
            self.veri_yoneticisi.pipeline_df = yeni_firsat_df
        else:
            self.veri_yoneticisi.pipeline_df = pd.concat([self.veri_yoneticisi.pipeline_df, yeni_firsat_df], ignore_index=True)
        
        self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_ekle"}))

    def pipeline_firsati_sil(self, musteri_adi: str) -> None:
        """Pipeline fırsatını vektörel şekilde siler."""
        if not self._bos_df_kontrol(self.veri_yoneticisi.pipeline_df, "Pipeline DataFrame'i boş"):
            self.veri_yoneticisi.pipeline_df = self.veri_yoneticisi.pipeline_df[
                self.veri_yoneticisi.pipeline_df["Musteri Adi"] != musteri_adi
            ]
            self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_sil"}))

    def pipeline_firsati_duzenle(self, index: int, guncellenmis_firsat: Dict[str, Any]) -> None:
        """Pipeline fırsatını vektörel ve optimize şekilde günceller (Decimal ile)."""
        if 0 <= index < len(self.veri_yoneticisi.pipeline_df):
            self.veri_yoneticisi.pipeline_df.loc[index, list(guncellenmis_firsat.keys())] = list(guncellenmis_firsat.values())
            self.veri_yoneticisi.pipeline_df = self._optimize_dataframe(self.veri_yoneticisi.pipeline_df, 'pipeline')
            self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_duzenle"}))

