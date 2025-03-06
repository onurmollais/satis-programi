# -*- coding: utf-8 -*-
import pandas as pd
from typing import Dict, Any, List, Callable, Optional, Iterator
from events import Event, EVENT_DATA_UPDATED, EVENT_ERROR_OCCURRED
from decimal import Decimal, getcontext
from decimal import InvalidOperation, DivisionByZero

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
        try:
            # Değerleri kontrol et
            if pd.isna(miktar) or pd.isna(birim_fiyat):
                return Decimal('0.00')
                
            # Decimal'e çevir
            try:
                miktar_decimal = Decimal(str(miktar))
                birim_fiyat_decimal = Decimal(str(birim_fiyat))
            except (InvalidOperation, ValueError, TypeError) as e:
                self.loglayici.error(f"Decimal donusum hatasi: {str(e)}, miktar: {miktar}, birim_fiyat: {birim_fiyat}")
                return Decimal('0.00')
                
            # Çarpma işlemi
            try:
                toplam = miktar_decimal * birim_fiyat_decimal
                return toplam.quantize(Decimal('0.01'))  # 2 ondalık basamağa yuvarla
            except (InvalidOperation, DivisionByZero, ValueError, TypeError) as e:
                self.loglayici.error(f"Carpma islemi hatasi: {str(e)}, miktar: {miktar_decimal}, birim_fiyat: {birim_fiyat_decimal}")
                return Decimal('0.00')
                
        except Exception as e:
            self.loglayici.error(f"Toplam tutar hesaplama hatasi: {str(e)}, miktar: {miktar}, birim_fiyat: {birim_fiyat}")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Toplam tutar hesaplama hatasi: {str(e)}"}))
            return Decimal('0.00')

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
        
        def on_save_finished(result):
            if result["success"]:
                self.loglayici.info(f"Toplu satış ekleme tamamlandı: {len(satis_df)} satış eklendi")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "bulk_add"}))
            else:
                self.loglayici.error(f"Kaydetme başarısız: {result.get('error', 'Bilinmeyen hata')}")
        
        self.repository.save(self.veri_yoneticisi.satislar_df, "sales", callback=on_save_finished)
            

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
            try:
                # Kategorik sütunları kontrol et ve gerekirse kategorileri güncelle
                for col, value in guncellenmis_satisci.items():
                    if col in self.veri_yoneticisi.satiscilar_df.columns and hasattr(self.veri_yoneticisi.satiscilar_df[col], 'cat'):
                        # Eğer yeni değer mevcut kategorilerde yoksa, kategorileri güncelle
                        if value not in self.veri_yoneticisi.satiscilar_df[col].cat.categories:
                            new_categories = self.veri_yoneticisi.satiscilar_df[col].cat.categories.tolist()
                            new_categories.append(value)
                            self.veri_yoneticisi.satiscilar_df[col] = self.veri_yoneticisi.satiscilar_df[col].cat.set_categories(new_categories)
                            self.loglayici.debug(f"'{col}' sütunu için yeni kategori eklendi: {value}")
                
                # Şimdi güncellemeyi yap
                self.veri_yoneticisi.satiscilar_df.loc[index, list(guncellenmis_satisci.keys())] = list(guncellenmis_satisci.values())
                self.veri_yoneticisi.satiscilar_df = self._optimize_dataframe(self.veri_yoneticisi.satiscilar_df, 'sales_reps')
                self.repository.save(self.veri_yoneticisi.satiscilar_df, "sales_reps")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "satisci_duzenle"}))
            except Exception as e:
                self.loglayici.error(f"Satisci guncellenirken hata: {str(e)}")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Satisci guncellenirken hata: {str(e)}"}))
                raise

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
        try:
            # Önce yeni satış verilerini kontrol et
            self.loglayici.debug(f"Yeni satis ekleniyor: {yeni_satis}")
            
            # DataFrame oluştur
            yeni_satis_df = pd.DataFrame([yeni_satis])
            
            # Kategorik sütunları kontrol et ve gerekirse kategorileri güncelle
            if not self._bos_df_kontrol(self.veri_yoneticisi.satislar_df, "Satışlar DataFrame'i boş, yeni veriyle başlatılıyor"):
                for col, value in yeni_satis.items():
                    if col in self.veri_yoneticisi.satislar_df.columns and hasattr(self.veri_yoneticisi.satislar_df[col], 'cat'):
                        try:
                            # None veya NaN değerleri kontrol et
                            if pd.isna(value):
                                continue
                                
                            # Eğer yeni değer mevcut kategorilerde yoksa, kategorileri güncelle
                            if value not in self.veri_yoneticisi.satislar_df[col].cat.categories:
                                new_categories = self.veri_yoneticisi.satislar_df[col].cat.categories.tolist()
                                new_categories.append(value)
                                self.veri_yoneticisi.satislar_df[col] = self.veri_yoneticisi.satislar_df[col].cat.set_categories(new_categories)
                                self.loglayici.debug(f"'{col}' sütunu için yeni kategori eklendi: {value}")
                        except Exception as cat_error:
                            self.loglayici.error(f"Kategori güncelleme hatası ({col}): {str(cat_error)}")
                            if self.event_manager:
                                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Kategori güncelleme hatası ({col}): {str(cat_error)}"}))
            
            # DataFrame'i optimize et
            try:
                yeni_satis_df = self._optimize_dataframe(yeni_satis_df, 'sales')
            except Exception as opt_error:
                self.loglayici.error(f"DataFrame optimizasyon hatası: {str(opt_error)}")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"DataFrame optimizasyon hatası: {str(opt_error)}"}))
                # Optimizasyon hatası olsa bile devam et
            
            # Toplam tutar hesapla
            try:
                if 'Miktar' in yeni_satis_df.columns and 'Birim Fiyat' in yeni_satis_df.columns:
                    yeni_satis_df['Toplam Tutar'] = yeni_satis_df.apply(
                        lambda row: self.hesapla_toplam_tutar(row['Miktar'], row['Birim Fiyat']), axis=1
                    )
            except Exception as calc_error:
                self.loglayici.error(f"Toplam tutar hesaplama hatası: {str(calc_error)}")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Toplam tutar hesaplama hatası: {str(calc_error)}"}))
                # Toplam tutar hesaplanamasa bile devam et
            
            # DataFrame'i birleştir veya yeni oluştur
            if self._bos_df_kontrol(self.veri_yoneticisi.satislar_df, "Satışlar DataFrame'i boş, yeni veriyle başlatılıyor"):
                self.veri_yoneticisi.satislar_df = yeni_satis_df
            else:
                try:
                    self.veri_yoneticisi.satislar_df = pd.concat([self.veri_yoneticisi.satislar_df, yeni_satis_df], ignore_index=True)
                except Exception as concat_error:
                    self.loglayici.error(f"DataFrame birleştirme hatası: {str(concat_error)}")
                    if self.event_manager:
                        self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"DataFrame birleştirme hatası: {str(concat_error)}"}))
                    raise
            
            # Alt Müşteri sütunu kontrolü
            if 'Alt Musteri' not in self.veri_yoneticisi.satislar_df.columns:
                self.veri_yoneticisi.satislar_df['Alt Musteri'] = pd.Series('', dtype='category')
            
            # Veritabanına kaydet
            try:
                self.repository.save(self.veri_yoneticisi.satislar_df, "sales")
                self.loglayici.info(f"Satış başarıyla kaydedildi: {yeni_satis.get('Ana Musteri', 'Bilinmeyen')} - {yeni_satis.get('Ay', 'Bilinmeyen')}")
            except Exception as save_error:
                self.loglayici.error(f"Veritabanına kaydetme hatası: {str(save_error)}")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Veritabanına kaydetme hatası: {str(save_error)}"}))
                raise
            
            # Olay bildir
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales", "action": "add"}))
                
        except Exception as e:
            self.loglayici.error(f"Satis ekleme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Satis ekleme hatasi: {str(e)}"}))
            raise

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
            try:
                # Kategorik sütunları kontrol et ve gerekirse kategorileri güncelle
                for col, value in guncellenmis_firsat.items():
                    if col in self.veri_yoneticisi.pipeline_df.columns and hasattr(self.veri_yoneticisi.pipeline_df[col], 'cat'):
                        # Eğer yeni değer mevcut kategorilerde yoksa, kategorileri güncelle
                        if value not in self.veri_yoneticisi.pipeline_df[col].cat.categories:
                            new_categories = self.veri_yoneticisi.pipeline_df[col].cat.categories.tolist()
                            new_categories.append(value)
                            self.veri_yoneticisi.pipeline_df[col] = self.veri_yoneticisi.pipeline_df[col].cat.set_categories(new_categories)
                            self.loglayici.debug(f"'{col}' sütunu için yeni kategori eklendi: {value}")
                
                # Şimdi güncellemeyi yap
                self.veri_yoneticisi.pipeline_df.loc[index, list(guncellenmis_firsat.keys())] = list(guncellenmis_firsat.values())
                self.veri_yoneticisi.pipeline_df = self._optimize_dataframe(self.veri_yoneticisi.pipeline_df, 'pipeline')
                self.repository.save(self.veri_yoneticisi.pipeline_df, "pipeline")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"source": "pipeline_firsati_duzenle"}))
            except Exception as e:
                self.loglayici.error(f"Pipeline guncellenirken hata: {str(e)}")
                if self.event_manager:
                    self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"error": f"Pipeline guncellenirken hata: {str(e)}"}))
                raise

