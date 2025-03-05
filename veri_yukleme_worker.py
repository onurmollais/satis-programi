# -*- coding: utf-8 -*-
from PyQt6.QtCore import QThread, pyqtSignal
from events import Event

class VeriYuklemeWorker(QThread):
    """
    Veri yukleme islemlerini arka planda gerceklestiren worker sinifi.
    
    Bu sinif, Excel dosyalarindan veri yukleme islemlerini arka planda
    gerceklestirerek kullanici arayuzunun donmasini engeller.
    
    Attributes:
        tamamlandi (pyqtSignal): Yukleme tamamlandiginda tetiklenen sinyal
        hata (pyqtSignal): Hata durumunda tetiklenen sinyal
        ilerleme (pyqtSignal): Yukleme ilerlemesini bildiren sinyal
        veri_yuklendi (pyqtSignal): DataFrame ve tablo bilgilerini bildiren sinyal
    """
    tamamlandi = pyqtSignal()
    hata = pyqtSignal(str)
    ilerleme = pyqtSignal(dict)  # Ilerleme sinyali
    veri_yuklendi = pyqtSignal(object, str, str)  # DataFrame, attr_name, table_name

    def __init__(self, veri_yoneticisi, dosya_yolu: str):
        """
        VeriYuklemeWorker sinifinin constructor metodu.
        
        Args:
            veri_yoneticisi: Veri yukleme islemlerini gerceklestirecek veri yoneticisi
            dosya_yolu (str): Yukleme yapilacak Excel dosyasinin yolu
        """
        super().__init__()
        # Thread guvenligini saglamak icin veri_yoneticisi'ni dogrudan kullanmak yerine
        # sadece gerekli ozellikleri saklayalim
        self.repository = veri_yoneticisi.repository
        self.dosya_yolu = dosya_yolu
        # Ana thread'de kullanilacak veri_yoneticisi referansini sakla
        self._veri_yoneticisi = veri_yoneticisi

    def run(self):
        """
        Thread calistiginda yukleme islemini gerceklestirir.
        """
        try:
            # Ozel bir yukleme metodu kullanacagiz
            self._thread_safe_yukle(self.dosya_yolu)
            self.tamamlandi.emit()
        except Exception as e:
            hata_mesaji = f"Arka plan veri yukleme hatasi. Dosya: {self.dosya_yolu}, Hata: {str(e)}, Hata Kodu: VERI_YUKLEME_003"
            self.hata.emit(hata_mesaji)
    
    def _thread_safe_yukle(self, dosya_yolu):
        """
        Thread-safe veri yukleme metodu.
        
        Bu metod, event manager kullanmadan veri yukleme islemini gerceklestirir
        ve ilerleme bilgisini sinyal olarak gonderir.
        """
        import pandas as pd
        
        try:
            excel = pd.ExcelFile(dosya_yolu)
            
            # Tablolari ve hedef bilgilerini tanimla
            tablolar = [
                ('Satiscilar', 'satiscilar_df', 'sales_reps'),
                ('Aylik Hedefler', 'hedefler_df', 'monthly_targets'),
                ('Pipeline', 'pipeline_df', 'pipeline'),
                ('Musteriler', 'musteriler_df', 'customers'),
                ('Ziyaretler', 'ziyaretler_df', 'visits'),
                ('Sikayetler', 'sikayetler_df', 'complaints'),
                ('Aylik Satislar Takibi', 'satislar_df', 'sales'),
                ('Hammadde Maliyetleri', 'hammadde_df', 'hammadde'),
                ('Urun BOM', 'urun_bom_df', 'urun_bom')
            ]
            
            toplam_tablo = len(tablolar)
            yuklenen_tablo = 0
            
            for sheet, attr, table in tablolar:
                try:
                    # Veriyi oku
                    df = pd.read_excel(excel, sheet)
                    
                    # Veriyi repository'ye kaydet
                    self.repository.save(df, table)
                    
                    # DataFrame'i ana thread'e gonder
                    # Ana thread'de veri_yoneticisi'ne atanacak
                    self.veri_yuklendi.emit(df, attr, table)
                    
                    yuklenen_tablo += 1
                    ilerleme = (yuklenen_tablo / toplam_tablo) * 100
                    
                    # Ilerleme bilgisini sinyal olarak gonder
                    self.ilerleme.emit({
                        "progress": ilerleme,
                        "current_table": sheet,
                        "total_tables": toplam_tablo,
                        "loaded_tables": yuklenen_tablo
                    })
                    
                except Exception as e:
                    # Hata durumunda devam et, tum tablolari yuklemeye calis
                    pass
                    
        except Exception as e:
            # Genel bir hata durumunda exception firlat
            raise 
