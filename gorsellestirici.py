# -*- coding: utf-8 -*-
import plotly.graph_objects as go
import plotly.express as px
from PyQt6.QtCore import QUrl
import pandas as pd
import calendar
from PyQt6.QtWidgets import QSizePolicy
from io import StringIO
import base64
from PyQt6.QtWebEngineWidgets import QWebEngineView
from typing import Optional, Union
from events import Event, EventManager, EVENT_DATA_UPDATED, EVENT_UI_UPDATED, EVENT_ERROR_OCCURRED
import os
import folium
import folium.plugins
import json
from asset_manager import AssetManager
from plotly.subplots import make_subplots

HATA_KODLARI = {
    "GRAFIK_001": "Veri çerçevesi boş veya gerekli sütunlar eksik",
    "GRAFIK_002": "Grafik oluşturma hatası"
}

class VisualizerInterface:
    def satis_performansi_grafigi_olustur(self, targets_df: pd.DataFrame, sales_df: pd.DataFrame, filtreler=None, chart_type='bar', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        raise NotImplementedError("Bu yöntem alt sınıflar tarafından uygulanmalıdır.")

    def musteri_sektor_grafigi_olustur(self, customers_df: pd.DataFrame, chart_type: str, theme: str, html_only: bool = False) -> Optional[Union[QWebEngineView, str]]:
        raise NotImplementedError("Bu yöntem alt sınıflar tarafından uygulanmalıdır.")

class Gorsellestirici(VisualizerInterface):
    def __init__(self, loglayici=None, event_manager=None, services=None):
        self.plotly_colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880']
        self.loglayici = loglayici
        self.event_manager = event_manager
        self.services = services
        self.cache = {}
        
        # Plotly renk paleti
        self.plotly_colors = px.colors.qualitative.Plotly
        
        # Asset Manager oluştur
        self.asset_manager = AssetManager(loglayici, event_manager)
        # Asset'leri kontrol et ve gerekirse indir
        self.asset_manager.check_and_download_assets()

        # UI güncellemeleri için abone ol
        if self.event_manager:
            self.event_manager.subscribe(EVENT_DATA_UPDATED, self._on_data_updated)

    def _on_data_updated(self, event: Event) -> None:
        """Veri güncellendiğinde grafiklerin yenilenmesi için olay dinleyicisi"""
        if self.loglayici:
            self.loglayici.info(f"Veri güncellendi, grafikler yenileniyor: {event.data}")
        
        # Veri güncellendiğinde UI_UPDATED olayını tetikle
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_UI_UPDATED, {"source": "gorsellestirici", "action": "refresh_charts"}))

    def customize_plotly_fig(self, fig, title, x_title=None, y_title=None, theme='plotly'):
        fig.update_layout(
            title=title,
            xaxis_title=x_title,
            yaxis_title=y_title,
            template=theme,
            font=dict(size=8),  # Yazı boyutunu 8'e küçülttük (daha küçük ve okunabilir)
            margin=dict(l=50, r=50, t=80, b=50),
            hovermode='x unified'
        )
        return fig
    
    def satis_performansi_grafigi_olustur(self, targets_df: pd.DataFrame, sales_df: pd.DataFrame, filtreler=None, chart_type='bar', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        try:
            # Veri kontrolü
            if targets_df.empty and sales_df.empty:
                hata_mesaji = f"Satış performansı grafiği oluşturulamadı. Targets_df satır: {len(targets_df)}, Sales_df satır: {len(sales_df)}, Sebep: Her iki veri çerçevesi de boş, Hata Kodu: GRAFIK_001"
                self.loglayici.warning(hata_mesaji)
                return self._create_empty_web_view(html_only)

            # Ay formatını kontrol et ve MM-YYYY formatına dönüştür
            if 'Ay' in sales_df.columns:
                sales_df['Ay'] = sales_df['Ay'].astype(str)
                
                for i, ay in enumerate(sales_df['Ay']):
                    try:
                        if len(ay) == 6:  # YYYYMM formati
                            yil = ay[:4]
                            ay_no = ay[4:]
                            yeni_ay = f"{ay_no}-{yil}"
                            sales_df.at[i, 'Ay'] = yeni_ay
                    except Exception as e:
                        self.loglayici.error(f"Ay formatı dönüştürme hatası: {str(e)}")
                
                if any('-' in str(ay) for ay in sales_df['Ay']):
                    if not sales_df.empty:
                        ay_parcalari = sales_df['Ay'].iloc[0].split('-')
                        if len(ay_parcalari) == 2:
                            try:
                                sales_df['Ay'] = sales_df['Ay'].apply(
                                    lambda x: f"{int(x.split('-')[0]):02d}-{x.split('-')[1]}"
                                )
                            except Exception as e:
                                self.loglayici.error(f"Ay formatı dönüştürme hatası: {str(e)}")
                            else:
                                self.loglayici.warning(f"Satışlar için ay formatı tanınamadı: {sales_df['Ay'].iloc[0]}")
                    
            # Grafik oluştur
            fig = go.Figure()
            if chart_type == 'line':
                fig.add_trace(go.Scatter(x=sales_df['Ay'], y=sales_df['Satis Miktari'], mode='lines+markers', marker_color=self.plotly_colors[0]))
            elif chart_type == 'bar':
                fig.add_trace(go.Bar(x=sales_df['Ay'], y=sales_df['Satis Miktari'], marker_color=self.plotly_colors[0]))
            elif chart_type == 'area':
                fig.add_trace(go.Scatter(x=sales_df['Ay'], y=sales_df['Satis Miktari'], fill='tozeroy', marker_color=self.plotly_colors[0]))

            fig = self.customize_plotly_fig(fig, 'Satış Performansı', 'Ay', 'Satış Miktarı', theme)
            return self._create_plotly_widget(fig, html_only=html_only)
            
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Satış performansı grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def musteri_grubu_maliyet_satis_grafigi_olustur(self, sales_df: pd.DataFrame, chart_type='pie', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        """Müşteri gruplarına (ZER ve Diğer) göre maliyet/satış oranlarını gösteren pasta grafik."""
        try:
            # Oncelikle data_manager'in musteri_grubu_analizi metoduna sahip olup olmadigini kontrol et
            if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'musteri_grubu_analizi'):
                self.loglayici.error("data_manager veya musteri_grubu_analizi metodu bulunamadi")
                return self._create_empty_web_view(html_only)
                
            if sales_df.empty:
                self.loglayici.warning("Müşteri grubu analizi için veri bulunamadı.")
                return self._create_empty_web_view(html_only)

            # Müşteri grubu analizi yap
            analiz_df = self.services.data_manager.musteri_grubu_analizi()

            if analiz_df.empty:
                self.loglayici.warning("Müşteri grubu analizi DataFrame'i boş.")
                return self._create_empty_web_view(html_only)

            # ZER ve Diğer grupları için maliyet ve satış oranlarını hesapla
            zer_row = analiz_df[analiz_df['Musteri Grubu'] == 'ZER']
            diger_row = analiz_df[analiz_df['Musteri Grubu'] == 'Diger']
            
            # Sutun adlarini kontrol et
            if 'Toplam Maliyet (TL)' not in analiz_df.columns:
                self.loglayici.warning("'Toplam Maliyet (TL)' sutunu bulunamadi. Varsayilan degerler kullaniliyor.")
                # Varsayilan degerler
                zer_satis = zer_row['Toplam Satis (TL)'].iloc[0] if not zer_row.empty and 'Toplam Satis (TL)' in zer_row.columns else 0
                zer_maliyet = zer_satis * 0.7  # Varsayilan olarak satisin %70'i maliyet
                diger_satis = diger_row['Toplam Satis (TL)'].iloc[0] if not diger_row.empty and 'Toplam Satis (TL)' in diger_row.columns else 0
                diger_maliyet = diger_satis * 0.7  # Varsayilan olarak satisin %70'i maliyet
            else:
                # ZER için oranlar
                zer_satis = zer_row['Toplam Satis (TL)'].iloc[0] if not zer_row.empty else 0
                zer_maliyet = zer_row['Toplam Maliyet (TL)'].iloc[0] if not zer_row.empty else 0
                
                # Diğer için oranlar
                diger_satis = diger_row['Toplam Satis (TL)'].iloc[0] if not diger_row.empty else 0
                diger_maliyet = diger_row['Toplam Maliyet (TL)'].iloc[0] if not diger_row.empty else 0
            
            zer_toplam = zer_satis + zer_maliyet
            zer_satis_oran = (zer_satis / zer_toplam) * 100 if zer_toplam > 0 else 0
            zer_maliyet_oran = (zer_maliyet / zer_toplam) * 100 if zer_toplam > 0 else 0

            diger_toplam = diger_satis + diger_maliyet
            diger_satis_oran = (diger_satis / diger_toplam) * 100 if diger_toplam > 0 else 0
            diger_maliyet_oran = (diger_maliyet / diger_toplam) * 100 if diger_toplam > 0 else 0

            # Genel maliyet/satış oranını hesapla
            genel_satis = zer_satis + diger_satis
            genel_maliyet = zer_maliyet + diger_maliyet
            genel_toplam = genel_satis + genel_maliyet
            genel_satis_oran = (genel_satis / genel_toplam) * 100 if genel_toplam > 0 else 0
            genel_maliyet_oran = (genel_maliyet / genel_toplam) * 100 if genel_toplam > 0 else 0

            # Verileri birleştir
            etiketler = ['Maliyet', 'Satış']
            values_zer = [zer_maliyet_oran, zer_satis_oran] if zer_toplam > 0 else [0, 0]
            values_diger = [diger_maliyet_oran, diger_satis_oran] if diger_toplam > 0 else [0, 0]
            values_genel = [genel_maliyet_oran, genel_satis_oran] if genel_toplam > 0 else [0, 0]

            # Genel maliyet/satış oranı için grafik
            fig_genel = go.Figure(data=[go.Pie(labels=etiketler, values=values_genel, hole=0.4, textinfo='percent+label')])
            fig_genel = self.customize_plotly_fig(fig_genel, 'Genel Maliyet/Satış Oranı', theme=theme)

            # ZER için maliyet/satış oranı için grafik
            fig_zer = go.Figure(data=[go.Pie(labels=etiketler, values=values_zer, hole=0.4, textinfo='percent+label')])
            fig_zer = self.customize_plotly_fig(fig_zer, 'ZER Maliyet/Satış Oranı', theme=theme)

            # Diğer için maliyet/satış oranı için grafik
            fig_diger = go.Figure(data=[go.Pie(labels=etiketler, values=values_diger, hole=0.4, textinfo='percent+label')])
            fig_diger = self.customize_plotly_fig(fig_diger, 'Diğer Maliyet/Satış Oranı', theme=theme)

            # HTML çıktısı için birleştir (üç grafiği yan yana göster)
            html_genel = fig_genel.to_html(include_plotlyjs='cdn', full_html=False)
            html_zer = fig_zer.to_html(include_plotlyjs='cdn', full_html=False)
            html_diger = fig_diger.to_html(include_plotlyjs='cdn', full_html=False)

            combined_html = f"""
            <div style="display: flex; justify-content: space-around; padding: 20px;">
                <div style="width: 30%;">{html_genel}</div>
                <div style="width: 30%;">{html_zer}</div>
                <div style="width: 30%;">{html_diger}</div>
            </div>
            """

            if html_only:
                return combined_html

            # QWebEngineView olarak döndür
            web_view = QWebEngineView()
            web_view.setHtml(combined_html)
            web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            return web_view

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Müşteri grubu maliyet/satış grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def oluklu_agirlik_dagilim_grafigi_olustur(self, sales_df: pd.DataFrame, chart_type='pie', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        """Oluklu mukavva türlerine göre ağırlık dağılımını gösteren pasta grafik."""
        try:
            # Oncelikle data_manager'in toplam_agirlik_hesapla metoduna sahip olup olmadigini kontrol et
            if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'toplam_agirlik_hesapla'):
                self.loglayici.error("data_manager veya toplam_agirlik_hesapla metodu bulunamadi")
                return self._create_empty_web_view(html_only)
                
            if sales_df.empty:
                self.loglayici.warning("Ağırlık dağılımı grafiği için veri bulunamadı.")
                return self._create_empty_web_view(html_only)

            # Toplam ağırlığı hesapla
            agirlik_sonuc = self.services.data_manager.toplam_agirlik_hesapla()
            urun_bazli_agirliklar = agirlik_sonuc['urun_bazli_agirliklar']

            if urun_bazli_agirliklar.empty:
                self.loglayici.warning("Ürün bazlı ağırlık verisi boş.")
                return self._create_empty_web_view(html_only)

            # Oluklu gruplar (Tripleks, Dopel, Tek Dalga) için ağırlıkları topla
            oluklu_df = self.services.data_manager.oluklu_df
            if oluklu_df is None or oluklu_df.empty:
                self.loglayici.warning("Oluklu mukavva verisi bulunamadı.")
                return self._create_empty_web_view(html_only)

            # Ürün gruplarına göre ağırlıkları hesapla
            grup_agirliklar = {}
            for _, row in urun_bazli_agirliklar.iterrows():
                urun_kodu = row['Urun Kodu']
                urun_agirlik = row['Toplam Agirlik (kg)']
                urun_grup = oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])]['Grup'].iloc[0] if not oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])].empty else 'Bilinmeyen'
                grup_agirliklar[urun_grup] = grup_agirliklar.get(urun_grup, 0) + urun_agirlik

            # Grafik için veriyi hazırla
            etiketler = list(grup_agirliklar.keys())
            degerler = list(grup_agirliklar.values())
            toplam = sum(degerler) if degerler else 0

            if toplam == 0:
                self.loglayici.warning("Toplam ağırlık sıfır, grafik oluşturulamadı.")
                return self._create_empty_web_view(html_only)

            # Yüzde oranlarını hesapla
            degerler_percent = [(v / toplam) * 100 for v in degerler]

            fig = go.Figure(data=[go.Pie(labels=etiketler, values=degerler_percent, hole=0.4, textinfo='percent+label')])
            fig = self.customize_plotly_fig(fig, 'Toplam Ağırlık Dağılımı (Tripleks, Dopel, Tek Dalga)', theme=theme)

            return self._create_plotly_widget(fig, html_only=html_only)

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Ağırlık dağılımı grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def oluklu_m2_dagilim_grafigi_olustur(self, sales_df: pd.DataFrame, chart_type='pie', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        """Oluklu mukavva türlerine göre m² dağılımını gösteren pasta grafik."""
        try:
            # Oncelikle data_manager'in toplam_agirlik_hesapla metoduna sahip olup olmadigini kontrol et
            if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'toplam_agirlik_hesapla'):
                self.loglayici.error("data_manager veya toplam_agirlik_hesapla metodu bulunamadi")
                return self._create_empty_web_view(html_only)
                
            if sales_df.empty:
                self.loglayici.warning("m² dağılımı grafiği için veri bulunamadı.")
                return self._create_empty_web_view(html_only)

            # Toplam m²'yi hesapla (toplam_agirlik_hesapla'da m² bilgileri de var)
            agirlik_sonuc = self.services.data_manager.toplam_agirlik_hesapla()
            urun_bazli_agirliklar = agirlik_sonuc['urun_bazli_agirliklar']

            if urun_bazli_agirliklar.empty:
                self.loglayici.warning("Ürün bazlı m² verisi boş.")
                return self._create_empty_web_view(html_only)

            # Oluklu gruplar (Tripleks, Dopel, Tek Dalga) için m²'leri topla
            oluklu_df = self.services.data_manager.oluklu_df
            if oluklu_df is None or oluklu_df.empty:
                self.loglayici.warning("Oluklu mukavva verisi bulunamadı.")
                return self._create_empty_web_view(html_only)

            # Ürün gruplarına göre m²'leri hesapla
            grup_m2 = {}
            for _, row in urun_bazli_agirliklar.iterrows():
                urun_kodu = row['Urun Kodu']
                urun_m2 = row.get('Toplam m2', 0)  # VeriYoneticisi'nde m² hesaplanıyor
                urun_grup = oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])]['Grup'].iloc[0] if not oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])].empty else 'Bilinmeyen'
                grup_m2[urun_grup] = grup_m2.get(urun_grup, 0) + urun_m2

            # Grafik için veriyi hazırla
            etiketler = list(grup_m2.keys())
            degerler = list(grup_m2.values())
            toplam = sum(degerler) if degerler else 0

            if toplam == 0:
                self.loglayici.warning("Toplam m² sıfır, grafik oluşturulamadı.")
                return self._create_empty_web_view(html_only)

            # Yüzde oranlarını hesapla
            degerler_percent = [(v / toplam) * 100 for v in degerler]

            fig = go.Figure(data=[go.Pie(labels=etiketler, values=degerler_percent, hole=0.4, textinfo='percent+label')])
            fig = self.customize_plotly_fig(fig, 'Toplam m² Dağılımı (Tripleks, Dopel, Tek Dalga)', theme=theme)

            return self._create_plotly_widget(fig, html_only=html_only)

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"m² dağılımı grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def zer_satis_dagilim_grafigi_olustur(self, sales_df: pd.DataFrame, chart_type='pie', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        """ZER grubu satışlarının Tripleks, Dopel, Tek Dalga dağılımını gösteren pasta grafik."""
        try:
            # Oncelikle data_manager'in musteri_grubu_analizi metoduna sahip olup olmadigini kontrol et
            if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'musteri_grubu_analizi'):
                self.loglayici.error("data_manager veya musteri_grubu_analizi metodu bulunamadi")
                return self._create_empty_web_view(html_only)
                
            if sales_df.empty:
                self.loglayici.warning("ZER satış dağılımı grafiği için veri bulunamadı.")
                return self._create_empty_web_view(html_only)

            # ZER grubu satışlarını al
            analiz_df = self.services.data_manager.musteri_grubu_analizi()
            zer_row = analiz_df[analiz_df['Musteri Grubu'] == 'ZER']

            if zer_row.empty:
                self.loglayici.warning("ZER grubu verisi boş.")
                return self._create_empty_web_view(html_only)

            # Oluklu mukavva türlerine göre satışları hesapla
            oluklu_df = self.services.data_manager.oluklu_df
            if oluklu_df is None or oluklu_df.empty:
                self.loglayici.warning("Oluklu mukavva verisi bulunamadı.")
                return self._create_empty_web_view(html_only)

            # ZER musterilerini dogrudan VeriYoneticisi'nden al
            if not hasattr(self.services.data_manager, 'satislar_df') or self.services.data_manager.satislar_df is None or self.services.data_manager.satislar_df.empty:
                self.loglayici.warning("Satislar verisi bulunamadi.")
                return self._create_empty_web_view(html_only)
                
            # Sutun kontrolu yap
            if 'Ana Musteri' not in self.services.data_manager.satislar_df.columns or 'Alt Musteri' not in self.services.data_manager.satislar_df.columns:
                self.loglayici.warning("Satislar verisinde 'Ana Musteri' veya 'Alt Musteri' sutunu bulunamadi.")
                return self._create_empty_web_view(html_only)
                
            # ZER musterilerini belirle (Alt musterisi olan musteriler)
            zer_musteriler = self.services.data_manager.satislar_df[self.services.data_manager.satislar_df["Alt Musteri"].notna()]["Ana Musteri"].unique()
            
            if len(zer_musteriler) == 0:
                self.loglayici.warning("ZER musteri bulunamadi.")
                return self._create_empty_web_view(html_only)

            # ZER satışlarını Tripleks, Dopel, Tek Dalga gruplarına ayır
            grup_satislar = {}
            
            # Sutun kontrolu yap
            if 'Urun Kodu' not in sales_df.columns:
                self.loglayici.warning("Satislar verisinde 'Urun Kodu' sutunu bulunamadi.")
                return self._create_empty_web_view(html_only)
                
            # Satis Tutari sutunu yoksa hesapla
            if 'Satis Tutari' not in sales_df.columns:
                if 'Miktar' in sales_df.columns and 'Birim Fiyat' in sales_df.columns:
                    sales_df['Satis Tutari'] = sales_df['Miktar'] * sales_df['Birim Fiyat']
                else:
                    self.loglayici.warning("Satislar verisinde 'Satis Tutari' hesaplanamadi.")
                    return self._create_empty_web_view(html_only)
            
            for urun_kodu in sales_df[sales_df['Ana Musteri'].isin(zer_musteriler)]['Urun Kodu'].unique():
                urun_satis = sales_df[sales_df['Urun Kodu'] == urun_kodu]['Satis Tutari'].sum()
                urun_grup = oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])]['Grup'].iloc[0] if not oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])].empty else 'Bilinmeyen'
                grup_satislar[urun_grup] = grup_satislar.get(urun_grup, 0) + urun_satis

            # Grafik için veriyi hazırla
            etiketler = list(grup_satislar.keys())
            degerler = list(grup_satislar.values())
            toplam = sum(degerler) if degerler else 0

            if toplam == 0:
                self.loglayici.warning("Toplam ZER satışı sıfır, grafik oluşturulamadı.")
                return self._create_empty_web_view(html_only)

            # Yüzde oranlarını hesapla
            degerler_percent = [(v / toplam) * 100 for v in degerler]

            fig = go.Figure(data=[go.Pie(labels=etiketler, values=degerler_percent, hole=0.4, textinfo='percent+label')])
            fig = self.customize_plotly_fig(fig, 'ZER Satış Dağılımı (Tripleks, Dopel, Tek Dalga)', theme=theme)

            return self._create_plotly_widget(fig, html_only=html_only)

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"ZER satış dağılımı grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def birlesik_genel_rapor_grafigi_olustur(self, sales_df: pd.DataFrame, chart_type='pie', theme='plotly', html_only=False) -> Optional[Union[QWebEngineView, str]]:
        """Tüm genel rapor grafiklerini tek bir plotly grafiğinde birleştirir.
        
        Bu fonksiyon, aşağıdaki grafikleri tek bir plotly grafiğinde birleştirir:
        - Müşteri grubu maliyet/satış oranları
        - Oluklu mukavva ağırlık dağılımı
        - Oluklu mukavva m² dağılımı
        - ZER satış dağılımı
        
        Args:
            sales_df (pd.DataFrame): Satış verileri
            chart_type (str): Grafik tipi (varsayılan: 'pie')
            theme (str): Grafik teması (varsayılan: 'plotly')
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView döndürür
            
        Returns:
            QWebEngineView veya HTML string: Oluşturulan grafik
        """
        try:
            # Subplot için satır ve sütun sayısını belirle
            rows = 2
            cols = 2
            
            # Subplot oluştur
            fig = make_subplots(
                rows=rows, 
                cols=cols,
                specs=[[{'type': 'pie'}, {'type': 'pie'}], [{'type': 'pie'}, {'type': 'pie'}]],
                subplot_titles=[
                    'Maliyet/Satış Oranları', 
                    'Ağırlık Dağılımı (Tripleks, Dopel, Tek Dalga)',
                    'm² Dağılımı (Tripleks, Dopel, Tek Dalga)', 
                    'ZER Satış Dağılımı (Tripleks, Dopel, Tek Dalga)'
                ]
            )
            
            # 1. Maliyet/Satış Oranları Grafiği
            try:
                # Oncelikle data_manager'in musteri_grubu_analizi metoduna sahip olup olmadigini kontrol et
                if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'musteri_grubu_analizi'):
                    self.loglayici.error("data_manager veya musteri_grubu_analizi metodu bulunamadi")
                else:
                    if not sales_df.empty:
                        # Müşteri grubu analizi yap
                        analiz_df = self.services.data_manager.musteri_grubu_analizi()

                        if not analiz_df.empty:
                            # ZER ve Diğer grupları için maliyet ve satış oranlarını hesapla
                            zer_row = analiz_df[analiz_df['Musteri Grubu'] == 'ZER']
                            diger_row = analiz_df[analiz_df['Musteri Grubu'] == 'Diger']
                            
                            # Sutun adlarini kontrol et
                            if 'Toplam Maliyet (TL)' not in analiz_df.columns:
                                self.loglayici.warning("'Toplam Maliyet (TL)' sutunu bulunamadi. Varsayilan degerler kullaniliyor.")
                                # Varsayilan degerler
                                zer_satis = zer_row['Toplam Satis (TL)'].iloc[0] if not zer_row.empty and 'Toplam Satis (TL)' in zer_row.columns else 0
                                zer_maliyet = zer_satis * 0.7  # Varsayilan olarak satisin %70'i maliyet
                                diger_satis = diger_row['Toplam Satis (TL)'].iloc[0] if not diger_row.empty and 'Toplam Satis (TL)' in diger_row.columns else 0
                                diger_maliyet = diger_satis * 0.7  # Varsayilan olarak satisin %70'i maliyet
                            else:
                                # ZER için oranlar
                                zer_satis = zer_row['Toplam Satis (TL)'].iloc[0] if not zer_row.empty else 0
                                zer_maliyet = zer_row['Toplam Maliyet (TL)'].iloc[0] if not zer_row.empty else 0
                                
                                # Diğer için oranlar
                                diger_satis = diger_row['Toplam Satis (TL)'].iloc[0] if not diger_row.empty else 0
                                diger_maliyet = diger_row['Toplam Maliyet (TL)'].iloc[0] if not diger_row.empty else 0
                            
                            # Genel maliyet/satış oranını hesapla
                            genel_satis = zer_satis + diger_satis
                            genel_maliyet = zer_maliyet + diger_maliyet
                            genel_toplam = genel_satis + genel_maliyet
                            genel_satis_oran = (genel_satis / genel_toplam) * 100 if genel_toplam > 0 else 0
                            genel_maliyet_oran = (genel_maliyet / genel_toplam) * 100 if genel_toplam > 0 else 0

                            # Verileri birleştir
                            etiketler = ['Maliyet', 'Satış']
                            values_genel = [genel_maliyet_oran, genel_satis_oran] if genel_toplam > 0 else [0, 0]

                            # Genel maliyet/satış oranı için grafik
                            fig.add_trace(
                                go.Pie(
                                    labels=etiketler, 
                                    values=values_genel, 
                                    hole=0.4, 
                                    textinfo='percent+label',
                                    name='Maliyet/Satış'
                                ),
                                row=1, col=1
                            )
            except Exception as e:
                self.loglayici.error(f"Maliyet/Satış grafiği oluşturulurken hata: {str(e)}")
                # Hata durumunda boş bir grafik ekle
                fig.add_trace(
                    go.Pie(
                        labels=['Veri Yok'], 
                        values=[100], 
                        hole=0.4, 
                        textinfo='label',
                        name='Maliyet/Satış'
                    ),
                    row=1, col=1
                )
            
            # 2. Ağırlık Dağılımı Grafiği
            try:
                # Oncelikle data_manager'in toplam_agirlik_hesapla metoduna sahip olup olmadigini kontrol et
                if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'toplam_agirlik_hesapla'):
                    self.loglayici.error("data_manager veya toplam_agirlik_hesapla metodu bulunamadi")
                else:
                    if not sales_df.empty:
                        # Toplam ağırlığı hesapla
                        agirlik_sonuc = self.services.data_manager.toplam_agirlik_hesapla()
                        urun_bazli_agirliklar = agirlik_sonuc['urun_bazli_agirliklar']

                        if not urun_bazli_agirliklar.empty:
                            # Oluklu gruplar (Tripleks, Dopel, Tek Dalga) için ağırlıkları topla
                            oluklu_df = self.services.data_manager.oluklu_df
                            if oluklu_df is not None and not oluklu_df.empty:
                                # Ürün gruplarına göre ağırlıkları hesapla
                                grup_agirliklar = {}
                                for _, row in urun_bazli_agirliklar.iterrows():
                                    urun_kodu = row['Urun Kodu']
                                    urun_agirlik = row['Toplam Agirlik (kg)']
                                    urun_grup = oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])]['Grup'].iloc[0] if not oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])].empty else 'Bilinmeyen'
                                    grup_agirliklar[urun_grup] = grup_agirliklar.get(urun_grup, 0) + urun_agirlik

                                # Grafik için veriyi hazırla
                                etiketler = list(grup_agirliklar.keys())
                                degerler = list(grup_agirliklar.values())
                                toplam = sum(degerler) if degerler else 0

                                if toplam > 0:
                                    # Yüzde oranlarını hesapla
                                    degerler_percent = [(v / toplam) * 100 for v in degerler]

                                    fig.add_trace(
                                        go.Pie(
                                            labels=etiketler, 
                                            values=degerler_percent, 
                                            hole=0.4, 
                                            textinfo='percent+label',
                                            name='Ağırlık Dağılımı'
                                        ),
                                        row=1, col=2
                                    )
            except Exception as e:
                self.loglayici.error(f"Ağırlık dağılımı grafiği oluşturulurken hata: {str(e)}")
                # Hata durumunda boş bir grafik ekle
                fig.add_trace(
                    go.Pie(
                        labels=['Veri Yok'], 
                        values=[100], 
                        hole=0.4, 
                        textinfo='label',
                        name='Ağırlık Dağılımı'
                    ),
                    row=1, col=2
                )
            
            # 3. m² Dağılımı Grafiği
            try:
                # Oncelikle data_manager'in toplam_agirlik_hesapla metoduna sahip olup olmadigini kontrol et
                if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'toplam_agirlik_hesapla'):
                    self.loglayici.error("data_manager veya toplam_agirlik_hesapla metodu bulunamadi")
                else:
                    if not sales_df.empty:
                        # Toplam m²'yi hesapla (toplam_agirlik_hesapla'da m² bilgileri de var)
                        agirlik_sonuc = self.services.data_manager.toplam_agirlik_hesapla()
                        urun_bazli_agirliklar = agirlik_sonuc['urun_bazli_agirliklar']

                        if not urun_bazli_agirliklar.empty:
                            # Oluklu gruplar (Tripleks, Dopel, Tek Dalga) için m²'leri topla
                            oluklu_df = self.services.data_manager.oluklu_df
                            if oluklu_df is not None and not oluklu_df.empty:
                                # Ürün gruplarına göre m²'leri hesapla
                                grup_m2 = {}
                                for _, row in urun_bazli_agirliklar.iterrows():
                                    urun_kodu = row['Urun Kodu']
                                    urun_m2 = row.get('Toplam m2', 0)  # VeriYoneticisi'nde m² hesaplanıyor
                                    urun_grup = oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])]['Grup'].iloc[0] if not oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])].empty else 'Bilinmeyen'
                                    grup_m2[urun_grup] = grup_m2.get(urun_grup, 0) + urun_m2

                                # Grafik için veriyi hazırla
                                etiketler = list(grup_m2.keys())
                                degerler = list(grup_m2.values())
                                toplam = sum(degerler) if degerler else 0

                                if toplam > 0:
                                    # Yüzde oranlarını hesapla
                                    degerler_percent = [(v / toplam) * 100 for v in degerler]

                                    fig.add_trace(
                                        go.Pie(
                                            labels=etiketler, 
                                            values=degerler_percent, 
                                            hole=0.4, 
                                            textinfo='percent+label',
                                            name='m² Dağılımı'
                                        ),
                                        row=2, col=1
                                    )
            except Exception as e:
                self.loglayici.error(f"m² dağılımı grafiği oluşturulurken hata: {str(e)}")
                # Hata durumunda boş bir grafik ekle
                fig.add_trace(
                    go.Pie(
                        labels=['Veri Yok'], 
                        values=[100], 
                        hole=0.4, 
                        textinfo='label',
                        name='m² Dağılımı'
                    ),
                    row=2, col=1
                )
            
            # 4. ZER Satış Dağılımı Grafiği
            try:
                # Oncelikle data_manager'in musteri_grubu_analizi metoduna sahip olup olmadigini kontrol et
                if not hasattr(self.services, 'data_manager') or not hasattr(self.services.data_manager, 'musteri_grubu_analizi'):
                    self.loglayici.error("data_manager veya musteri_grubu_analizi metodu bulunamadi")
                else:
                    if not sales_df.empty:
                        # ZER grubu satışlarını al
                        analiz_df = self.services.data_manager.musteri_grubu_analizi()
                        zer_row = analiz_df[analiz_df['Musteri Grubu'] == 'ZER']

                        if not zer_row.empty:
                            # Oluklu mukavva türlerine göre satışları hesapla
                            oluklu_df = self.services.data_manager.oluklu_df
                            if oluklu_df is not None and not oluklu_df.empty:
                                # ZER musterilerini dogrudan VeriYoneticisi'nden al
                                if hasattr(self.services.data_manager, 'satislar_df') and self.services.data_manager.satislar_df is not None and not self.services.data_manager.satislar_df.empty:
                                    # Sutun kontrolu yap
                                    if 'Ana Musteri' in self.services.data_manager.satislar_df.columns and 'Alt Musteri' in self.services.data_manager.satislar_df.columns:
                                        # ZER musterilerini belirle (Alt musterisi olan musteriler)
                                        zer_musteriler = self.services.data_manager.satislar_df[self.services.data_manager.satislar_df["Alt Musteri"].notna()]["Ana Musteri"].unique()
                                        
                                        if len(zer_musteriler) > 0:
                                            # ZER satışlarını Tripleks, Dopel, Tek Dalga gruplarına ayır
                                            grup_satislar = {}
                                            
                                            # Sutun kontrolu yap
                                            if 'Urun Kodu' in sales_df.columns:
                                                # Satis Tutari sutunu yoksa hesapla
                                                if 'Satis Tutari' not in sales_df.columns:
                                                    if 'Miktar' in sales_df.columns and 'Birim Fiyat' in sales_df.columns:
                                                        sales_df['Satis Tutari'] = sales_df['Miktar'] * sales_df['Birim Fiyat']
                                                
                                                if 'Satis Tutari' in sales_df.columns:
                                                    for urun_kodu in sales_df[sales_df['Ana Musteri'].isin(zer_musteriler)]['Urun Kodu'].unique():
                                                        urun_satis = sales_df[sales_df['Urun Kodu'] == urun_kodu]['Satis Tutari'].sum()
                                                        urun_grup = oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])]['Grup'].iloc[0] if not oluklu_df[oluklu_df['Dalga_Tipi'].isin([urun_kodu])].empty else 'Bilinmeyen'
                                                        grup_satislar[urun_grup] = grup_satislar.get(urun_grup, 0) + urun_satis

                                                    # Grafik için veriyi hazırla
                                                    etiketler = list(grup_satislar.keys())
                                                    degerler = list(grup_satislar.values())
                                                    toplam = sum(degerler) if degerler else 0

                                                    if toplam > 0:
                                                        # Yüzde oranlarını hesapla
                                                        degerler_percent = [(v / toplam) * 100 for v in degerler]

                                                        fig.add_trace(
                                                            go.Pie(
                                                                labels=etiketler, 
                                                                values=degerler_percent, 
                                                                hole=0.4, 
                                                                textinfo='percent+label',
                                                                name='ZER Satış Dağılımı'
                                                            ),
                                                            row=2, col=2
                                                        )
            except Exception as e:
                self.loglayici.error(f"ZER satış dağılımı grafiği oluşturulurken hata: {str(e)}")
                # Hata durumunda boş bir grafik ekle
                fig.add_trace(
                    go.Pie(
                        labels=['Veri Yok'], 
                        values=[100], 
                        hole=0.4, 
                        textinfo='label',
                        name='ZER Satış Dağılımı'
                    ),
                    row=2, col=2
                )
            
            # Grafik düzenlemeleri
            fig.update_layout(
                title_text='Genel Rapor Grafikleri',
                showlegend=False,  # Her alt grafiğin kendi legendı var
                margin=dict(t=50, b=20, l=20, r=20),  # Kenar boşlukları
                paper_bgcolor='#333',  # Arka plan rengi
                plot_bgcolor='#333',  # Grafik arka plan rengi
                font=dict(color='white'),  # Yazı rengi
                title_font=dict(size=24, color='white'),  # Başlık yazı stili
                autosize=True  # Otomatik boyutlandırma
            )
            
            # Subplot başlıklarını güncelle
            for i in fig['layout']['annotations']:
                i['font'] = dict(size=14, color='white')
            
            # Tema ayarları
            if theme == 'dark':
                fig.update_layout(
                    paper_bgcolor='#1e1e1e',
                    plot_bgcolor='#1e1e1e',
                    font=dict(color='white')
                )
            elif theme == 'light':
                fig.update_layout(
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    font=dict(color='black')
                )
            
            return self._create_plotly_widget(fig, html_only=html_only)

        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Birleşik genel rapor grafiği oluşturulurken hata: {str(e)}")
                import traceback
                self.loglayici.debug(f"Hata ayrıntıları:\n{traceback.format_exc()}")
            return self._create_empty_web_view(html_only)

    def _create_empty_web_view(self, html_only=False):
        """Boş grafik için varsayılan görünüm oluşturur.
        
        Veri olmadığı veya hata durumlarında kullanılacak boş bir görünüm oluşturur.
        html_only=True ise HTML string, html_only=False ise QWebEngineView/QLabel döndürür.
        
        Args:
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView/QLabel döndürür
            
        Returns:
            str, QWebEngineView veya QLabel: html_only=True ise HTML string, 
            html_only=False ise QWebEngineView veya QLabel nesnesi döndürür
        """
        empty_html = """
        <div style='text-align:center; padding:20px; background-color:#f0f0f0; 
                    border-radius:5px; box-shadow:0 1px 3px rgba(0,0,0,0.1);
                    font-family:Arial, sans-serif;'>
            <p style='margin:0; padding:10px; font-size:14px; color:#666;'>
                Veri bulunamadı veya görüntülenemiyor.
            </p>
        </div>
        """
        
        if html_only:
            return empty_html
            
        try:
            # QWebEngineView oluştur
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWidgets import QSizePolicy
            
            web_view = QWebEngineView()
            web_view.setHtml(empty_html)
            web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            return web_view
        except Exception as e:
            # Herhangi bir hata durumunda QLabel döndür
            if self.loglayici:
                self.loglayici.error(f"Boş web view oluşturulurken hata: {str(e)}")
                import traceback
                self.loglayici.debug(f"Hata ayrıntıları:\n{traceback.format_exc()}")
            
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import Qt
            label = QLabel("Veri bulunamadı.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; padding: 10px; border-radius: 5px;")
            return label

    def _create_plotly_widget(self, fig, html_only=False):
        """Plotly grafiğini QWebEngineView veya HTML olarak döndürür.
        
        Args:
            fig: Plotly Figure nesnesi
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView döndürür
            
        Returns:
            QWebEngineView veya HTML string
        """
        try:
            # Responsive ayarlarini ekle
            fig.update_layout(
                autosize=True,
                margin=dict(l=20, r=20, t=50, b=20),
            )
            
            # Plotly grafiğini HTML'e dönüştür - responsive config ekle
            config = {
                'responsive': True,
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d']
            }
            
            html = fig.to_html(
                include_plotlyjs='cdn', 
                full_html=False,
                config=config
            )
            
            # Responsive davranisi icin HTML wrapper ekle
            responsive_html = f"""
            <div style="width:100%; height:100%;">
                <style>
                    .plotly-graph-div {{
                        width: 100% !important;
                        height: 100% !important;
                    }}
                </style>
                {html}
            </div>
            """
            
            if html_only:
                return responsive_html
                
            # QWebEngineView oluştur
            web_view = QWebEngineView()
            web_view.setHtml(responsive_html)
            web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Resize event'i icin JavaScript ekle
            resize_script = """
            <script>
                window.addEventListener('resize', function() {
                    var graphDivs = document.getElementsByClassName('plotly-graph-div');
                    for (var i = 0; i < graphDivs.length; i++) {
                        Plotly.Plots.resize(graphDivs[i]);
                    }
                });
            </script>
            """
            web_view.page().runJavaScript(resize_script)
            
            return web_view
            
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Plotly widget oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def _create_plotly_widget_from_html(self, html_content):
        """HTML içeriğinden QWebEngineView oluşturur.
        
        Args:
            html_content (str): HTML içeriği
            
        Returns:
            QWebEngineView: Oluşturulan QWebEngineView nesnesi
        """
        try:
            # Responsive davranisi icin HTML wrapper ekle
            responsive_html = f"""
            <div style="width:100%; height:100%;">
                <style>
                    .plotly-graph-div {{
                        width: 100% !important;
                        height: 100% !important;
                    }}
                </style>
                {html_content}
            </div>
            """
            
            # QWebEngineView oluştur
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWidgets import QSizePolicy
            
            web_view = QWebEngineView()
            web_view.setHtml(responsive_html)
            web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Resize event'i icin JavaScript ekle
            resize_script = """
            <script>
                window.addEventListener('resize', function() {
                    var graphDivs = document.getElementsByClassName('plotly-graph-div');
                    for (var i = 0; i < graphDivs.length; i++) {
                        Plotly.Plots.resize(graphDivs[i]);
                    }
                });
            </script>
            """
            web_view.page().runJavaScript(resize_script)
            
            return web_view
        except Exception as e:
            # Herhangi bir hata durumunda boş web view döndür
            if self.loglayici:
                self.loglayici.error(f"HTML'den web view oluşturulurken hata: {str(e)}")
                import traceback
                self.loglayici.debug(f"Hata ayrıntıları:\n{traceback.format_exc()}")
            
            return self._create_empty_web_view()
    def aylik_potansiyel_gelir_grafigi_olustur(self, pipeline_df, filtreler=None, chart_type='line', theme='plotly', html_only=False):
        """Aylık potansiyel gelir grafiği"""
        try:
            if pipeline_df is None or pipeline_df.empty:
                self.loglayici.warning("Potansiyel gelir grafiği için veri bulunamadı.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Veri bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)

            # Tarihi aylık gruplara ayır
            pipeline_df['Ay'] = pd.to_datetime(pipeline_df['Tahmini Kapanis Tarihi']).dt.strftime('%Y-%m')
            aylik_potansiyel = pipeline_df.groupby('Ay')['Potansiyel Ciro'].sum().sort_index()

            fig = go.Figure()
            if chart_type == 'line':
                fig.add_trace(go.Scatter(x=aylik_potansiyel.index, y=aylik_potansiyel.values, mode='lines+markers', marker_color=self.plotly_colors[0]))
            elif chart_type == 'bar':
                fig.add_trace(go.Bar(x=aylik_potansiyel.index, y=aylik_potansiyel.values, marker_color=self.plotly_colors[0]))
            elif chart_type == 'area':
                fig.add_trace(go.Scatter(x=aylik_potansiyel.index, y=aylik_potansiyel.values, fill='tozeroy', marker_color=self.plotly_colors[0]))

            fig = self.customize_plotly_fig(fig, 'Aylık Potansiyel Gelir', 'Ay', 'Potansiyel Ciro', theme)
            return self._create_plotly_widget(fig, html_only=html_only)
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Aylık potansiyel gelir grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)
            
    def pipeline_grafigi_olustur(self, pipeline_df, chart_type='pie', theme='plotly', html_only=False):
        """Pipeline analizi grafiği
        
        Args:
            pipeline_df (pd.DataFrame): Pipeline verileri
            chart_type (str): Grafik türü ('pie', 'bar', 'funnel')
            theme (str): Grafik teması
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView döndürür
            
        Returns:
            QWebEngineView veya str: Oluşturulan grafik
        """
        try:
            if pipeline_df is None or pipeline_df.empty:
                self.loglayici.warning("Pipeline grafiği için veri bulunamadı.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Veri bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)
                
            # Sutun kontrolu yap
            gerekli_sutunlar = ['Musteri Adi', 'Potansiyel Ciro', 'Olasilik', 'Asamasi']
            for sutun in gerekli_sutunlar:
                if sutun not in pipeline_df.columns:
                    self.loglayici.warning(f"Pipeline verisinde '{sutun}' sutunu bulunamadi.")
                    if html_only:
                        return f"<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Pipeline verisinde '{sutun}' sutunu bulunamadi.</p></div>"
                    return self._create_empty_web_view(html_only)
            
            # Aşamalara göre grupla
            asama_gruplari = pipeline_df.groupby('Asamasi')['Potansiyel Ciro'].sum().sort_values(ascending=False)
            
            # Grafik oluştur
            fig = go.Figure()
            
            if chart_type == 'pie':
                fig.add_trace(go.Pie(
                    labels=asama_gruplari.index,
                    values=asama_gruplari.values,
                    hole=0.4,
                    textinfo='percent+label',
                    marker_colors=self.plotly_colors[:len(asama_gruplari)]
                ))
                
            elif chart_type == 'bar':
                fig.add_trace(go.Bar(
                    x=asama_gruplari.index,
                    y=asama_gruplari.values,
                    marker_color=self.plotly_colors[0]
                ))
                
            elif chart_type == 'funnel':
                # Funnel grafik için verileri hazırla
                # Aşamaları satış sürecine göre sırala
                asama_sirasi = ['İlk Temas', 'Teklif Hazırlama', 'Teklif Verildi', 'Müzakere', 'Kazanıldı', 'Kaybedildi']
                
                # Tüm aşamaları içeren bir DataFrame oluştur
                tum_asamalar = pd.DataFrame(index=asama_sirasi)
                # Mevcut aşamaları ekle
                tum_asamalar['Potansiyel Ciro'] = asama_gruplari
                # NaN değerleri 0 ile doldur
                tum_asamalar = tum_asamalar.fillna(0)
                
                fig.add_trace(go.Funnel(
                    y=tum_asamalar.index,
                    x=tum_asamalar['Potansiyel Ciro'],
                    textinfo='value+percent initial',
                    marker_color=self.plotly_colors[:len(tum_asamalar)]
                ))
            
            # Grafik başlığı ve düzeni
            fig = self.customize_plotly_fig(fig, 'Pipeline Analizi', 'Aşama', 'Potansiyel Ciro (TL)', theme)
            
            return self._create_plotly_widget(fig, html_only=html_only)
            
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Pipeline grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def satis_temsilcisi_performansi_grafigi_olustur(self, sales_df, chart_type='bar', theme='plotly', html_only=False):
        """Satış temsilcisi performans grafiği
        
        Args:
            sales_df (pd.DataFrame): Satış verileri
            chart_type (str): Grafik türü ('bar', 'pie', 'line')
            theme (str): Grafik teması
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView döndürür
            
        Returns:
            QWebEngineView veya str: Oluşturulan grafik
        """
        try:
            if sales_df is None or sales_df.empty:
                self.loglayici.warning("Satış temsilcisi performans grafiği için veri bulunamadı.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Veri bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)
                
            # Sutun kontrolu yap
            gerekli_sutunlar = ['Satisci', 'Satis Tutari']
            
            # Satis Tutari sutunu yoksa hesapla
            if 'Satis Tutari' not in sales_df.columns:
                if 'Miktar' in sales_df.columns and 'Birim Fiyat' in sales_df.columns:
                    sales_df['Satis Tutari'] = sales_df['Miktar'] * sales_df['Birim Fiyat']
                else:
                    self.loglayici.warning("Satislar verisinde 'Satis Tutari' hesaplanamadi.")
                    if html_only:
                        return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Satış tutarı hesaplanamadı.</p></div>"
                    return self._create_empty_web_view(html_only)
            
            # Satisci sutunu yoksa alternatif sutunlari kontrol et
            satisci_sutunu = 'Satisci'
            if 'Satisci' not in sales_df.columns:
                # Alternatif sutunlari kontrol et
                alternatif_sutunlar = ['Satis Temsilcisi', 'Temsilci', 'Sorumlu', 'Personel']
                for sutun in alternatif_sutunlar:
                    if sutun in sales_df.columns:
                        satisci_sutunu = sutun
                        self.loglayici.info(f"'Satisci' sutunu yerine '{sutun}' sutunu kullaniliyor.")
                        break
                else:
                    # Eger hic bir alternatif sutun bulunamazsa, varsayilan bir sutun olustur
                    self.loglayici.warning("Satislar verisinde 'Satisci' sutunu bulunamadi ve alternatif sutun da yok.")
                    sales_df['Satisci'] = 'Bilinmeyen'
                    satisci_sutunu = 'Satisci'
            
            # Satış temsilcilerine göre grupla
            satisci_performans = sales_df.groupby(satisci_sutunu)['Satis Tutari'].sum().sort_values(ascending=False)
            
            # Grafik oluştur
            fig = go.Figure()
            
            if chart_type == 'bar':
                fig.add_trace(go.Bar(
                    x=satisci_performans.index,
                    y=satisci_performans.values,
                    marker_color=self.plotly_colors[0]
                ))
                
            elif chart_type == 'pie':
                fig.add_trace(go.Pie(
                    labels=satisci_performans.index,
                    values=satisci_performans.values,
                    hole=0.4,
                    textinfo='percent+label',
                    marker_colors=self.plotly_colors[:len(satisci_performans)]
                ))
                
            elif chart_type == 'line':
                # Satış temsilcisi performansını aylara göre grupla
                if 'Tarih' in sales_df.columns:
                    sales_df['Ay'] = pd.to_datetime(sales_df['Tarih']).dt.strftime('%Y-%m')
                    satisci_aylik = sales_df.pivot_table(
                        index='Ay', 
                        columns=satisci_sutunu, 
                        values='Satis Tutari', 
                        aggfunc='sum'
                    ).fillna(0)
                    
                    for i, satisci in enumerate(satisci_aylik.columns):
                        fig.add_trace(go.Scatter(
                            x=satisci_aylik.index,
                            y=satisci_aylik[satisci],
                            mode='lines+markers',
                            name=satisci,
                            marker_color=self.plotly_colors[i % len(self.plotly_colors)]
                        ))
                elif 'Ay' in sales_df.columns:
                    # Tarih sutunu yoksa Ay sutununu kullan
                    satisci_aylik = sales_df.pivot_table(
                        index='Ay', 
                        columns=satisci_sutunu, 
                        values='Satis Tutari', 
                        aggfunc='sum'
                    ).fillna(0)
                    
                    for i, satisci in enumerate(satisci_aylik.columns):
                        fig.add_trace(go.Scatter(
                            x=satisci_aylik.index,
                            y=satisci_aylik[satisci],
                            mode='lines+markers',
                            name=satisci,
                            marker_color=self.plotly_colors[i % len(self.plotly_colors)]
                        ))
                else:
                    # Tarih ve Ay sutunu yoksa bar grafik göster
                    fig.add_trace(go.Bar(
                        x=satisci_performans.index,
                        y=satisci_performans.values,
                        marker_color=self.plotly_colors[0]
                    ))
            
            # Grafik başlığı ve düzeni
            baslik = f'Satış Temsilcisi Performansı ({satisci_sutunu})' if satisci_sutunu != 'Satisci' else 'Satış Temsilcisi Performansı'
            fig = self.customize_plotly_fig(fig, baslik, satisci_sutunu, 'Satış Tutarı (TL)', theme)
            
            return self._create_plotly_widget(fig, html_only=html_only)
            
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Satış temsilcisi performans grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)
            
    def musteri_bolge_dagilimi_grafigi_olustur(self, customers_df, chart_type='choropleth', theme='plotly', html_only=False):
        """Müşteri bölge dağılımı grafiği (Türkiye haritası)
        
        Args:
            customers_df (pd.DataFrame): Müşteri verileri
            chart_type (str): Grafik türü ('choropleth', 'bar', 'pie')
            theme (str): Grafik teması
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView döndürür
            
        Returns:
            QWebEngineView veya str: Oluşturulan grafik
        """
        try:
            if customers_df is None or customers_df.empty:
                self.loglayici.warning("Müşteri bölge dağılımı grafiği için veri bulunamadı.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Veri bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)
                
            # Sutun kontrolu yap
            if 'Il' not in customers_df.columns:
                self.loglayici.warning("Müşteri verisinde 'Il' sutunu bulunamadi.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>İl bilgisi bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)
            
            # İllere göre müşteri sayısını hesapla
            il_dagilimi = customers_df['Il'].value_counts().reset_index()
            il_dagilimi.columns = ['Il', 'Musteri_Sayisi']
            
            # Grafik türüne göre uygun grafiği oluştur
            if chart_type == 'choropleth':
                # Türkiye haritası için GeoJSON dosyası
                try:
                    # Türkiye il sınırları GeoJSON dosyasını yükle
                    import json
                    import os
                    
                    # GeoJSON dosyasının yolu
                    geojson_path = os.path.join(os.path.dirname(__file__), 'assets', 'turkiye-iller.geojson')
                    
                    # Dosya varsa yükle, yoksa hata mesajı göster
                    if os.path.exists(geojson_path):
                        with open(geojson_path, 'r', encoding='utf-8') as f:
                            turkiye_geo = json.load(f)
                            
                        # Choropleth harita oluştur
                        fig = px.choropleth(
                            il_dagilimi,
                            geojson=turkiye_geo,
                            locations='Il',
                            featureidkey='properties.name',
                            color='Musteri_Sayisi',
                            color_continuous_scale='Viridis',
                            scope='europe',
                            labels={'Musteri_Sayisi': 'Müşteri Sayısı'}
                        )
                        
                        # Harita merkezini Türkiye'ye ayarla
                        fig.update_geos(
                            fitbounds='locations',
                            visible=False,
                            showcountries=True,
                            showcoastlines=True,
                            showland=True,
                            landcolor='lightgray'
                        )
                    else:
                        # GeoJSON dosyası yoksa bar grafik göster
                        self.loglayici.warning("Türkiye il sınırları GeoJSON dosyası bulunamadı. Bar grafik gösteriliyor.")
                        fig = px.bar(
                            il_dagilimi.sort_values('Musteri_Sayisi', ascending=False).head(15),
                            x='Il',
                            y='Musteri_Sayisi',
                            color='Musteri_Sayisi',
                            color_continuous_scale='Viridis',
                            labels={'Musteri_Sayisi': 'Müşteri Sayısı', 'Il': 'İl'}
                        )
                except Exception as e:
                    # Herhangi bir hata durumunda bar grafik göster
                    self.loglayici.error(f"Choropleth harita oluşturulurken hata: {str(e)}. Bar grafik gösteriliyor.")
                    fig = px.bar(
                        il_dagilimi.sort_values('Musteri_Sayisi', ascending=False).head(15),
                        x='Il',
                        y='Musteri_Sayisi',
                        color='Musteri_Sayisi',
                        color_continuous_scale='Viridis',
                        labels={'Musteri_Sayisi': 'Müşteri Sayısı', 'Il': 'İl'}
                    )
                    
            elif chart_type == 'bar':
                # Bar grafik
                fig = px.bar(
                    il_dagilimi.sort_values('Musteri_Sayisi', ascending=False).head(15),
                    x='Il',
                    y='Musteri_Sayisi',
                    color='Musteri_Sayisi',
                    color_continuous_scale='Viridis',
                    labels={'Musteri_Sayisi': 'Müşteri Sayısı', 'Il': 'İl'}
                )
                
            elif chart_type == 'pie':
                # Pasta grafik (en çok müşterisi olan 10 il)
                top_10 = il_dagilimi.sort_values('Musteri_Sayisi', ascending=False).head(10)
                fig = px.pie(
                    top_10,
                    names='Il',
                    values='Musteri_Sayisi',
                    hole=0.4,
                    labels={'Musteri_Sayisi': 'Müşteri Sayısı', 'Il': 'İl'}
                )
            
            # Grafik başlığı ve düzeni
            fig = self.customize_plotly_fig(fig, 'Müşteri Bölge Dağılımı', 'İl', 'Müşteri Sayısı', theme)
            
            return self._create_plotly_widget(fig, html_only=html_only)
            
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Müşteri bölge dağılımı grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

    def musteri_sektor_grafigi_olustur(self, customers_df: pd.DataFrame, chart_type: str, theme: str, html_only: bool = False) -> Optional[Union[QWebEngineView, str]]:
        """Müşteri sektör dağılımı grafiği
        
        Args:
            customers_df (pd.DataFrame): Müşteri verileri
            chart_type (str): Grafik türü ('pie', 'bar', 'treemap')
            theme (str): Grafik teması
            html_only (bool): True ise HTML string döndürür, False ise QWebEngineView döndürür
            
        Returns:
            QWebEngineView veya str: Oluşturulan grafik
        """
        try:
            if customers_df is None or customers_df.empty:
                self.loglayici.warning("Müşteri sektör grafiği için veri bulunamadı.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Veri bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)
                
            # Sutun kontrolu yap
            if 'Sektor' not in customers_df.columns:
                self.loglayici.warning("Müşteri verisinde 'Sektor' sutunu bulunamadi.")
                if html_only:
                    return "<div style='text-align:center; padding:20px; background-color:#f0f0f0;'><p>Sektör bilgisi bulunamadı.</p></div>"
                return self._create_empty_web_view(html_only)
            
            # Sektörlere göre müşteri sayısını hesapla
            sektor_dagilimi = customers_df['Sektor'].value_counts().reset_index()
            sektor_dagilimi.columns = ['Sektor', 'Musteri_Sayisi']
            
            # Grafik oluştur
            fig = go.Figure()
            
            if chart_type == 'pie':
                fig.add_trace(go.Pie(
                    labels=sektor_dagilimi['Sektor'],
                    values=sektor_dagilimi['Musteri_Sayisi'],
                    hole=0.4,
                    textinfo='percent+label',
                    marker_colors=self.plotly_colors[:len(sektor_dagilimi)]
                ))
                
            elif chart_type == 'bar':
                fig.add_trace(go.Bar(
                    x=sektor_dagilimi['Sektor'],
                    y=sektor_dagilimi['Musteri_Sayisi'],
                    marker_color=self.plotly_colors[0]
                ))
                
            elif chart_type == 'treemap':
                fig = px.treemap(
                    sektor_dagilimi,
                    path=['Sektor'],
                    values='Musteri_Sayisi',
                    color='Musteri_Sayisi',
                    color_continuous_scale='Viridis',
                    title='Müşteri Sektör Dağılımı'
                )
            
            # Grafik başlığı ve düzeni
            fig = self.customize_plotly_fig(fig, 'Müşteri Sektör Dağılımı', 'Sektör', 'Müşteri Sayısı', theme)
            
            return self._create_plotly_widget(fig, html_only=html_only)
            
        except Exception as e:
            if self.loglayici:
                self.loglayici.error(f"Müşteri sektör grafiği oluşturulurken hata: {str(e)}")
            return self._create_empty_web_view(html_only)

