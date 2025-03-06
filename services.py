# -*- coding: utf-8 -*-
from typing import Dict, Optional, List
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from veri_yoneticisi import VeriYoneticisi
from events import Event, EVENT_DATA_UPDATED, EVENT_ERROR_OCCURRED
import os
from urun_hesaplayici import UrunHesaplayici

class ServiceInterface:
    """Servis katmani arayuzu"""
    
    def add_sales_rep(self, sales_rep: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def update_sales_rep(self, index: int, sales_rep: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def delete_sales_rep(self, sales_rep_name: str) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_sales_target(self, target: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def update_sales_target(self, index: int, target: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def delete_sales_target(self, month: str) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_sale(self, sale: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_pipeline_opportunity(self, opportunity: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def delete_pipeline_opportunity(self, customer_name: str) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_customer(self, customer: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_visit(self, visit: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_complaint(self, complaint: Dict) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def generate_sales_report(self) -> str:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def generate_customer_report(self) -> str:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def generate_visit_report(self) -> str:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def generate_complaint_report(self) -> str:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def generate_pipeline_report(self) -> str:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_hammadde(self, hammadde: Dict) -> None:
        """Yeni hammadde ekler"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")
        
    def update_hammadde(self, index: int, hammadde: Dict) -> None:
        """Hammadde bilgilerini gunceller"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")
        
    def delete_hammadde(self, hammadde_kodu: str) -> None:
        """Hammadde siler"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def add_urun_bom(self, urun_bom: Dict) -> None:
        """Yeni urun BOM ekler"""
        self.data_manager.urun_bom_ekle(urun_bom)
        self.logger.info(f"Yeni urun BOM eklendi: {urun_bom['Urun Kodu']}")
        
        # Urun agirligini hesapla
        self.data_manager.urun_agirligi_guncelle(urun_bom['Urun Kodu'])

    def update_urun_bom(self, index: int, urun_bom: Dict) -> None:
        """Urun BOM bilgilerini gunceller"""
        self.data_manager.urun_bom_duzenle(index, urun_bom)
        self.logger.info(f"Urun BOM guncellendi: {urun_bom['Urun Adi']}")
        
        # Urun agirligini hesapla
        self.data_manager.urun_agirligi_guncelle(urun_bom['Urun Kodu'])

    def delete_urun_bom(self, urun_kodu: str, hammadde_kodu: str) -> None:
        """Urun BOM siler"""
        self.data_manager.urun_bom_sil(urun_kodu, hammadde_kodu)
        self.logger.info(f"Urun BOM silindi: {urun_kodu} - {hammadde_kodu}")
        
        # Urun agirligini guncelle
        self.data_manager.urun_agirligi_guncelle(urun_kodu)

    def generate_urun_bom_report(self) -> str:
        """Urun BOM raporu olusturur"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def generate_urun_performans_report(self) -> str:
        """Urun performans raporu olusturur"""
        return "Urun Performans Raporu"

    def generate_kohort_report(self, baslangic_tarihi=None, bitis_tarihi=None):
        """
        Musterilerin ilk satin alma tarihlerine gore kohort analizi raporu olusturur.
        
        Args:
            baslangic_tarihi (str, optional): 'YYYY-MM-DD' formatinda baslangic tarihi
            bitis_tarihi (str, optional): 'YYYY-MM-DD' formatinda bitis tarihi
            
        Returns:
            dict: Kohort analizi sonuclari, HTML rapor ve grafikler
        """
        try:
            # Veri yoneticisinden kohort analizi olustur
            kohort_analizi = self.data_manager.kohort_analizi_olustur(
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi
            )
            
            if not kohort_analizi.get("success", False):
                self.logger.error(f"Kohort analizi olusturulamadi: {kohort_analizi.get('message', 'Bilinmeyen hata')}")
                return {"success": False, "message": kohort_analizi.get("message", "Kohort analizi olusturulamadi.")}
            
            # HTML raporunu kaydet
            html_rapor = kohort_analizi["html_rapor"]
            rapor_dosyasi = os.path.join(self.reports_dir, f"kohort_analizi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            
            with open(rapor_dosyasi, "w", encoding="utf-8") as f:
                f.write(html_rapor)
            
            self.logger.info(f"Kohort analizi raporu olusturuldu: {rapor_dosyasi}")
            
            # Sonuclari dondur
            return {
                "success": True,
                "rapor_dosyasi": rapor_dosyasi,
                "html_rapor": html_rapor,
                "kohort_musteri_oran": kohort_analizi["kohort_musteri_oran"],
                "kohort_aov_pivot": kohort_analizi["kohort_aov_pivot"],
                "kohort_satis_pivot": kohort_analizi["kohort_satis_pivot"]
            }
            
        except Exception as e:
            self.logger.error(f"Kohort raporu olusturulurken hata: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {"success": False, "message": f"Kohort raporu olusturulurken hata: {str(e)}"}

    def calculate_all_product_weights(self) -> None:
        """Tum urunlerin agirliklarini hesaplar (sadece oluklu mukavva hammaddeler)"""
        self.data_manager.tum_urun_agirliklarini_guncelle()
        self.logger.info("Tum urun agirliklari hesaplandi (sadece oluklu mukavva hammaddeler)")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"}))

    def calculate_all_product_costs(self) -> None:
        """Tum urunlerin maliyetlerini hesaplar"""
        self.data_manager.tum_urun_maliyetlerini_guncelle()
        self.logger.info("Tum urun maliyetleri hesaplandi")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"}))

    def update_sale(self, row: int, sale: Dict) -> None:
        """Bir satışı günceller"""
        errors = []
        required_fields = ["Ana Musteri", "Satis Temsilcisi", "Ay", "Satis Miktari", "Para Birimi"]
        for field in required_fields:
            if field not in sale or not sale[field]:
                errors.append(f"{field} alani bos birakilamaz")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        self.data_manager.update_sale(row, sale)
        self.logger.info(f"Satis guncellendi: {sale['Ana Musteri']} - {sale.get('Ay', 'Bilinmiyor')}")
    
    def update_visit(self, row: int, visit: Dict) -> None:
        """Bir ziyareti günceller"""
        errors = []
        required_fields = ["Musteri Adi", "Satis Temsilcisi", "Tarih", "Ziyaret Konusu"]
        for field in required_fields:
            if field not in visit or not visit[field]:
                errors.append(f"{field} alani bos birakilamaz")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        self.data_manager.update_visit(row, visit)
        self.logger.info(f"Ziyaret guncellendi: {visit['Musteri Adi']} - {visit.get('Tarih', 'Bilinmiyor')}")

class CRMServices(ServiceInterface):
    """CRM servis katmani implementasyonu"""
    
    def __init__(self, data_manager: VeriYoneticisi, logger, event_manager):  # EventManager eklendi
        self.data_manager = data_manager
        self.logger = logger
        self.event_manager = event_manager  # Olay yoneticisi eklendi
        
        # Urun hesaplayici olustur
        self.urun_hesaplayici = UrunHesaplayici(logger, event_manager)  # Yeni modul ornegi olusturuldu

    def add_sales_rep(self, sales_rep: Dict) -> None:
        if not sales_rep.get("Isim") or not isinstance(sales_rep["Isim"], str):
            hata_mesaji = "Satisci ismi bos olamaz ve string olmali"
            self.logger.error(hata_mesaji)
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": hata_mesaji}))
            raise ValueError(hata_mesaji)
        sales_rep["Isim"] = str(sales_rep["Isim"])
        self.data_manager.satisci_ekle(sales_rep)
        self.logger.info(f"Yeni satisci eklendi: {sales_rep['Isim']}")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales_rep", "data": sales_rep}))

    def update_sales_rep(self, index: int, sales_rep: Dict) -> None:
        """Bir satisciyi gunceller"""
        if not sales_rep.get("Isim") or not isinstance(sales_rep["Isim"], str):
            hata_mesaji = "Satisci ismi bos olamaz ve string olmali"
            self.logger.error(hata_mesaji)
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, {"message": hata_mesaji}))
            raise ValueError(hata_mesaji)
        
        sales_rep["Isim"] = str(sales_rep["Isim"])
        self.data_manager.satisci_duzenle(index, sales_rep)
        self.logger.info(f"Satisci guncellendi: {sales_rep['Isim']}")
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales_rep", "data": sales_rep}))

    def delete_sales_rep(self, sales_rep_name: str) -> None:
        """Bir satisciyi siler"""
        if self.data_manager.satiscilar_df is not None and not self.data_manager.satiscilar_df.empty:
            self.data_manager.satisci_sil(sales_rep_name)
            self.logger.info(f"Satisci silindi: {sales_rep_name}")
        else:
            self.logger.warning(f"Silinecek satisci bulunamadi: {sales_rep_name}")

    def add_sales_target(self, target: Dict) -> None:
        """Yeni bir satis hedefi ekler"""
        errors = []
        if not isinstance(target["Ay"], str) or not target["Ay"]:
            errors.append("Ay bos olamaz ve string olmali")
        if errors:
            hata_mesaji = f"Gecersiz hedef verisi: {'; '.join(errors)} Hata Kodu: HEDEF_EKLE_001"
            raise ValueError(hata_mesaji)
        else:
            self.logger.debug(f"Hedef ekleme - Alinan Ay degeri: '{target['Ay']}'")
            if "-" not in target["Ay"]:
                errors.append("Ay 'MM-YYYY' formatinda olmali (orn: 03-2025)")
            else:
                try:
                    ay, yil = target["Ay"].split("-")
                    ay_num = int(ay)
                    if not (1 <= ay_num <= 12):
                        errors.append("Ay 01-12 araliginda olmali")
                    yil_num = int(yil)
                    if len(yil) != 4 or not (1900 <= yil_num <= 2100):
                        errors.append("Yil 4 haneli ve 1900-2100 araliginda olmali")
                except ValueError as e:
                    self.logger.debug(f"Ay ayrim hatasi: {str(e)}")
                    errors.append("Ay 'MM-YYYY' formatinda olmali (orn: 03-2025)")

        if "Hedef" not in target or not isinstance(target["Hedef"], (int, float)) or target["Hedef"] <= 0:
            errors.append("Hedef pozitif bir sayi olmali")
        if "Para Birimi" not in target or target["Para Birimi"] not in ["TL", "USD", "EUR"]:
            errors.append("Para Birimi 'TL', 'USD' veya 'EUR' olmali")

        if errors:
            raise ValueError("; ".join(errors))

        self.data_manager.satis_hedefi_ekle(target)
        self.logger.info(f"Hedef eklendi: {target['Ay']} - {target['Hedef']} {target['Para Birimi']}")
        # Olay yayinla
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales_target", "data": target}))

    def update_sales_target(self, index: int, target: Dict) -> None:
        """Bir satis hedefini gunceller"""
        if self.data_manager.aylik_hedefler_df is not None and not self.data_manager.aylik_hedefler_df.empty:
            self.data_manager.satis_hedefi_duzenle(index, target)
            self.logger.info(f"Hedef guncellendi: {target['Ay']}")
            # Olay yayinla
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales_target", "data": target}))

    def delete_sales_target(self, month: str) -> None:
        """Bir satis hedefini siler"""
        if self.data_manager.aylik_hedefler_df is not None and not self.data_manager.aylik_hedefler_df.empty:
            self.data_manager.satis_hedefi_sil(month)
            self.logger.info(f"Hedef silindi: {month}")
            # Olay yayinla
            if self.event_manager:
                self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"type": "sales_target", "action": "delete", "month": month}))

    def add_sale(self, sale: Dict) -> None:
        """Yeni bir satis ekler"""
        errors = []
        required_fields = ["Ana Musteri", "Satis Temsilcisi", "Ay", "Satis Miktari", "Para Birimi"]
        for field in required_fields:
            if field not in sale or not sale[field]:
                errors.append(f"{field} alani bos birakilamaz")
        if errors:
            hata_mesaji = f"Gecersiz satis verisi: {'; '.join(errors)} Hata Kodu: SATIS_EKLE_001"
            raise ValueError(hata_mesaji)
        
        if "Ay" in sale:
            self.logger.debug(f"Satis ekleme - Alinan Ay degeri: '{sale['Ay']}'")
            if not isinstance(sale["Ay"], str) or "-" not in sale["Ay"]:
                errors.append("Ay 'MM-YYYY' formatinda olmali (orn: 03-2025)")
            else:
                try:
                    ay, yil = sale["Ay"].split("-")
                    ay_num = int(ay)
                    if not (1 <= ay_num <= 12):
                        errors.append("Ay 01-12 araliginda olmali")
                    yil_num = int(yil)
                    if len(yil) != 4 or not (1900 <= yil_num <= 2100):
                        errors.append("Yil 4 haneli ve 1900-2100 araliginda olmali")
                except ValueError as e:
                    self.logger.debug(f"Ay ayrim hatasi: {str(e)}")
                    errors.append("Ay 'MM-YYYY' formatinda olmali (orn: 03-2025)")
        
        # Satis Miktari kontrolÃ¼
        if "Satis Miktari" in sale:
            try:
                sale["Satis Miktari"] = float(sale["Satis Miktari"])
                if sale["Satis Miktari"] <= 0:
                    errors.append("Satis miktari pozitif bir sayi olmalidir")
            except (ValueError, TypeError):
                errors.append("Satis miktari sayisal bir deger olmalidir")
        
        # Miktar ve Birim Fiyat kontrolÃ¼
        if "Miktar" in sale:
            try:
                sale["Miktar"] = float(sale["Miktar"])
                if sale["Miktar"] <= 0:
                    errors.append("Miktar pozitif bir sayi olmalidir")
            except (ValueError, TypeError):
                errors.append("Miktar sayisal bir deger olmalidir")
                
        if "Birim Fiyat" in sale:
            try:
                sale["Birim Fiyat"] = float(sale["Birim Fiyat"])
                if sale["Birim Fiyat"] <= 0:
                    errors.append("Birim fiyat pozitif bir sayi olmalidir")
            except (ValueError, TypeError):
                errors.append("Birim fiyat sayisal bir deger olmalidir")
                
        # Miktar ve Birim Fiyat ile Satis Miktari tutarlÄ±lÄ±k kontrolÃ¼
        if "Miktar" in sale and "Birim Fiyat" in sale and "Satis Miktari" in sale:
            beklenen_satis_miktari = sale["Miktar"] * sale["Birim Fiyat"]
            if abs(beklenen_satis_miktari - sale["Satis Miktari"]) > 0.01:  # KÃ¼Ã§Ã¼k yuvarlama hatalarÄ±na izin ver
                self.logger.warning(f"Satis miktari tutarsiz: Miktar * Birim Fiyat = {beklenen_satis_miktari}, Satis Miktari = {sale['Satis Miktari']}")
                # Otomatik dÃ¼zeltme yapÄ±labilir
                # sale["Satis Miktari"] = beklenen_satis_miktari

        if "Ana Musteri" in sale:
            try:
                if self.data_manager.musteriler_df is None or self.data_manager.musteriler_df.empty or "Musteri Adi" not in self.data_manager.musteriler_df.columns:
                    errors.append("Musteri listesi bos veya yuklenmemis")
                else:
                    # Büyük/küçük harf duyarlılığını kaldırarak müşteri adlarını karşılaştır
                    musteri_adlari = [str(ad).lower() for ad in self.data_manager.musteriler_df["Musteri Adi"].values]
                    if str(sale["Ana Musteri"]).lower() not in musteri_adlari:
                        self.logger.warning(f"Ana Musteri '{sale['Ana Musteri']}' bulunamadi. Mevcut musteriler: {self.data_manager.musteriler_df['Musteri Adi'].tolist()}")
                        errors.append("Ana Musteri mevcut musteriler arasinda bulunmali")
            except Exception as e:
                self.logger.error(f"Ana Musteri kontrol hatasi: {str(e)}")
                errors.append("Ana Musteri kontrolu sirasinda hata olustu")
        if "Para Birimi" in sale and sale["Para Birimi"] not in ["TL", "USD", "EUR"]:
            errors.append("Para Birimi 'TL', 'USD' veya 'EUR' olmali")
        
        if "Alt Musteri" in sale and sale["Alt Musteri"]:
            try:
                if self.data_manager.musteriler_df is None or self.data_manager.musteriler_df.empty:
                    errors.append("Musteri listesi bos veya yuklenmemis")
                else:
                    # Büyük/küçük harf duyarlılığını kaldırarak müşteri adlarını karşılaştır
                    musteri_adlari = [str(ad).lower() for ad in self.data_manager.musteriler_df["Musteri Adi"].values]
                    if str(sale["Alt Musteri"]).lower() not in musteri_adlari:
                        self.logger.warning(f"Alt Musteri '{sale['Alt Musteri']}' bulunamadi. Mevcut musteriler: {self.data_manager.musteriler_df['Musteri Adi'].tolist()}")
                        errors.append("Secilen Alt Musteri mevcut degil")
            except Exception as e:
                self.logger.error(f"Alt Musteri kontrol hatasi: {str(e)}")
                errors.append("Alt Musteri kontrolu sirasinda hata olustu")

        if errors:
            raise ValueError("; ".join(errors))

        self.data_manager.satis_ekle(sale)
        self.logger.info(f"Yeni satis eklendi: {sale['Ana Musteri']} - {sale.get('Alt Musteri', 'Yok')} - {sale['Satis Miktari']} {sale['Para Birimi']}")

    def add_pipeline_opportunity(self, opportunity: Dict) -> None:
        """Yeni bir pipeline firsati ekler"""
        self.data_manager.pipeline_firsati_ekle(opportunity)
        self.logger.info(f"Yeni pipeline firsati eklendi: {opportunity['Musteri Adi']}")

    def delete_pipeline_opportunity(self, customer_name: str) -> None:
        """Bir pipeline firsatini siler"""
        if self.data_manager.pipeline_df is not None and not self.data_manager.pipeline_df.empty:
            self.data_manager.pipeline_firsati_sil(customer_name)
            self.logger.info(f"Pipeline firsati silindi: {customer_name}")

    def add_customer(self, customer: Dict) -> None:
        """Yeni bir musteri ekler"""
        errors = self.validate_customer(customer)
        if errors:
            raise ValueError("; ".join(errors))

        customer["Musteri Adi"] = str(customer["Musteri Adi"])
        if "Son Satin Alma Tarihi" not in customer:
            customer["Son Satin Alma Tarihi"] = None
        self.data_manager.musteri_ekle(customer)
        self.logger.info(f"Yeni musteri eklendi: {customer['Musteri Adi']} ({customer['Musteri Turu']})")

    def validate_customer(self, customer: Dict) -> List[str]:
        """Musteri verilerini dogrular"""
        errors = []
        
        # Zorunlu alanlar
        required_fields = ["Musteri Adi", "Bolge", "Sektor", "Musteri Turu"]
        for field in required_fields:
            if field not in customer or not customer[field]:
                errors.append(f"{field} alani zorunludur")
        
        # Global/Lokal kontrolu
        if "Global/Lokal" in customer:
            if customer["Global/Lokal"] not in ["Global", "Lokal"]:
                errors.append("Global/Lokal alani 'Global' veya 'Lokal' olmali")
        
        # Musteri turu kontrolu
        if "Musteri Turu" in customer:
            if customer["Musteri Turu"] not in ["Ana Musteri", "Alt Musteri"]:
                errors.append("Musteri Turu 'Ana Musteri' veya 'Alt Musteri' olmali")
            if customer["Musteri Turu"] == "Alt Musteri" and customer["Ana Musteri"] and self.data_manager.musteriler_df is not None and not self.data_manager.musteriler_df.empty:
                try:
                    # Büyük/küçük harf duyarlılığını kaldırarak müşteri adlarını karşılaştır
                    musteri_adlari = [str(ad).lower() for ad in self.data_manager.musteriler_df["Musteri Adi"].values]
                    if str(customer["Ana Musteri"]).lower() not in musteri_adlari:
                        self.logger.warning(f"Ana Musteri '{customer['Ana Musteri']}' bulunamadi. Mevcut musteriler: {self.data_manager.musteriler_df['Musteri Adi'].tolist()}")
                        errors.append("Secilen Ana Musteri mevcut degil")
                except Exception as e:
                    self.logger.error(f"Ana Musteri kontrol hatasi: {str(e)}")
                    errors.append("Ana Musteri kontrolu sirasinda hata olustu")
        
        return errors

    def add_visit(self, visit: Dict) -> None:
        """Yeni bir ziyaret ekler"""
        errors = []
        required_fields = ["Musteri Adi", "Satis Temsilcisi", "Ziyaret Tarihi", "Ziyaret Konusu"]
        for field in required_fields:
            if field not in visit or not visit[field]:
                errors.append(f"{field} alani bos birakilamaz")

        visit["Musteri Adi"] = str(visit.get("Musteri Adi", ""))
        visit["Satis Temsilcisi"] = str(visit.get("Satis Temsilcisi", ""))
    
        if 'Ziyaret Tarihi' in visit:
            try:
                pd.to_datetime(visit['Ziyaret Tarihi'], format='%Y-%m-%d')
            except ValueError:
                errors.append("Ziyaret Tarihi YYYY-MM-DD formatinda olmalidir")

        if errors:
            raise ValueError("; ".join(errors))

        self.data_manager.ziyaret_ekle(visit)
        self.logger.info(f"Yeni ziyaret eklendi: {visit['Musteri Adi']} - {visit['Ziyaret Tarihi']}")

    def update_pipeline_opportunity(self, index: int, opportunity: Dict) -> None:
        """Bir pipeline firsatini gunceller"""
        try:
            if self.data_manager.pipeline_df is not None and not self.data_manager.pipeline_df.empty and index < len(self.data_manager.pipeline_df):
                self.data_manager.pipeline_df.iloc[index] = pd.Series(opportunity)
                self.data_manager.repository.save(self.data_manager.pipeline_df, "pipeline")
                self.logger.info(f"Pipeline firsati guncellendi: {opportunity['Musteri Adi']}")
            else:
                raise ValueError("Pipeline verisi bos veya indeks gecersiz")
        except Exception as e:
            self.logger.error(f"Pipeline guncelleme hatasi: {str(e)}")
            raise

    def add_complaint(self, complaint: Dict) -> None:
        """Yeni bir sikayet ekler"""
        self.data_manager.sikayet_ekle(complaint)
        self.logger.info(f"Yeni sikayet eklendi: {complaint['Musteri Adi']} - {complaint['Sikayet Turu']}")

    def generate_sales_report(self) -> str:
        """Satis raporu olusturur"""
        return self.data_manager.satis_raporu_olustur()

    def generate_customer_report(self) -> str:
        """Musteri raporu olusturur"""
        return self.data_manager.musteri_raporu_olustur()

    def generate_visit_report(self) -> str:
        """Ziyaret raporu olusturur"""
        return self.data_manager.ziyaret_raporu_olustur()

    def generate_complaint_report(self) -> str:
        """Sikayet raporu olusturur"""
        return self.data_manager.sikayet_raporu_olustur()

    def generate_pipeline_report(self) -> str:
        """Pipeline raporu olusturur"""
        return self.data_manager.pipeline_raporu_olustur()

    def add_hammadde(self, hammadde: Dict) -> None:
        """Yeni hammadde ekler"""
        self.data_manager.hammadde_ekle(hammadde)
        self.logger.info(f"Yeni hammadde eklendi: {hammadde['Hammadde Adi']}")

    def update_hammadde(self, index: int, hammadde: Dict) -> None:
        """Hammadde bilgilerini gunceller"""
        self.data_manager.hammadde_duzenle(index, hammadde)
        self.logger.info(f"Hammadde guncellendi: {hammadde['Hammadde Adi']}")

    def delete_hammadde(self, hammadde_kodu: str) -> None:
        """Hammadde siler"""
        self.data_manager.hammadde_sil(hammadde_kodu)
        self.logger.info(f"Hammadde silindi: {hammadde_kodu}")

    def add_urun_bom(self, urun_bom: Dict) -> None:
        """Yeni urun BOM ekler"""
        self.data_manager.urun_bom_ekle(urun_bom)
        self.logger.info(f"Yeni urun BOM eklendi: {urun_bom['Urun Kodu']}")
        
        # Urun agirligini hesapla
        self.data_manager.urun_agirligi_guncelle(urun_bom['Urun Kodu'])

    def update_urun_bom(self, index: int, urun_bom: Dict) -> None:
        """Urun BOM bilgilerini gunceller"""
        self.data_manager.urun_bom_duzenle(index, urun_bom)
        self.logger.info(f"Urun BOM guncellendi: {urun_bom['Urun Adi']}")
        
        # Urun agirligini hesapla
        self.data_manager.urun_agirligi_guncelle(urun_bom['Urun Kodu'])

    def delete_urun_bom(self, urun_kodu: str, hammadde_kodu: str) -> None:
        """Urun BOM siler"""
        self.data_manager.urun_bom_sil(urun_kodu, hammadde_kodu)
        self.logger.info(f"Urun BOM silindi: {urun_kodu} - {hammadde_kodu}")
        
        # Urun agirligini guncelle
        self.data_manager.urun_agirligi_guncelle(urun_kodu)
        
    def calculate_all_product_weights(self) -> None:
        """Tum urunlerin agirliklarini hesaplar (sadece oluklu mukavva hammaddeler)"""
        self.data_manager.tum_urun_agirliklarini_guncelle()
        self.logger.info("Tum urun agirliklari hesaplandi (sadece oluklu mukavva hammaddeler)")
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_DATA_UPDATED, {"table": "urun_bom"}))

    def generate_urun_bom_report(self) -> str:
        """Urun BOM raporu olusturur"""
        return self.data_manager.urun_bom_raporu_olustur()

    def generate_urun_performans_report(self) -> str:
        """Urun performans raporu olusturur"""
        return "Urun Performans Raporu"
