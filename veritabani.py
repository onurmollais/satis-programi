# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
from functools import lru_cache
import shutil
from datetime import datetime, timedelta
import os
import logging
from sqlite3 import Connection, Cursor
from typing import List, Optional, Tuple, Dict, Any, Iterator
from repository import RepositoryInterface, RepositoryError, ErrorCode
from events import Event, EVENT_DATA_UPDATED, EVENT_ERROR_OCCURRED, EVENT_BACKUP_COMPLETED
import json
import threading
from sifreleme import SifrelemeYoneticisi  # Yeni import


HATA_KODLARI = {
    "VERI_KAYDET_001": "Veri cercevesi bos veya None",
    "VERI_KAYDET_002": "Gecersiz tablo adi",
    "VERI_KAYDET_003": "Veritabani butunluk hatasi",
    "VERI_KAYDET_004": "Genel veritabani hatasi",
    "VERI_YUKLE_001": "Gecersiz tablo adi",
    "VERI_YUKLE_002": "Veritabani sorgu hatasi",
    "BACKUP_001": "Yedekleme sirasinda hata",
    "RESTORE_001": "Yedek geri yukleme hatasi"
}

logging.basicConfig(filename='crm_database.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseInterface:
    def veri_kaydet(self, df: pd.DataFrame, tablo_adi: str, batch_size: int) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def veri_yukle(self, tablo_adi: str, sayfa: int, sayfa_boyutu: int) -> pd.DataFrame:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def batch_update(self, tablo_adi: str, updates: List[Dict[str, Any]], condition: str, params: List[tuple]) -> None:
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

class BackupManager:
    def __init__(self, backup_dir: str = "backups", event_manager=None, sifreleme_yoneticisi=None):
        self.backup_dir = backup_dir
        self.event_manager = event_manager
        self.sifreleme = sifreleme_yoneticisi
        self.loglayici = logging.getLogger(__name__)
        
        # Yedekleme dizinini olustur
        os.makedirs(backup_dir, exist_ok=True)
        
    def create_backup(self, database_path: str) -> Tuple[bool, str]:
        """Veritabani yedegi olusturur ve sifreler"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"backup_{timestamp}.db")
            
            # Veritabanini yedekle
            with sqlite3.connect(database_path) as src, sqlite3.connect(backup_path) as dst:
                src.backup(dst)
            
            # Yedegi sifrele
            if self.sifreleme:
                backup_path = self.sifreleme.yedekleme_sifrele(backup_path)
                self.loglayici.info(f"Yedekleme sifrelendi: {backup_path}")
            
            if self.event_manager:
                self.event_manager.emit(Event("backup_created", {
                    "path": backup_path,
                    "encrypted": bool(self.sifreleme)
                }))
            
            return True, backup_path
            
        except Exception as e:
            error_msg = f"Yedekleme olusturma hatasi: {str(e)}"
            self.loglayici.error(error_msg)
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "BACKUP_001",
                    "message": error_msg
                }))
            return False, error_msg
    
    def restore_backup(self, backup_path: str, database_path: str) -> Tuple[bool, str]:
        """Yedekten geri yukleme yapar"""
        try:
            # Eger sifrelenmis yedek ise once sifresini coz
            if backup_path.endswith('.encrypted') and self.sifreleme:
                backup_path = self.sifreleme.yedekleme_sifre_coz(backup_path)
                self.loglayici.info(f"Yedekleme sifresi cozuldu: {backup_path}")
            
            # Yedegi geri yukle
            with sqlite3.connect(backup_path) as src, sqlite3.connect(database_path) as dst:
                src.backup(dst)
            
            if self.event_manager:
                self.event_manager.emit(Event("backup_restored", {
                    "path": database_path
                }))
            
            return True, "Yedek basariyla geri yuklendi"
            
        except Exception as e:
            error_msg = f"Yedek geri yukleme hatasi: {str(e)}"
            self.loglayici.error(error_msg)
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "BACKUP_002",
                    "message": error_msg
                }))
            return False, error_msg


class SQLiteRepository(RepositoryInterface):
    def __init__(self, db_path: str = "crm_database.db", event_manager=None, max_connections: int = 5, min_connections: int = 2):
        self.db_path = db_path
        self.event_manager = event_manager
        self.max_connections = max_connections
        self.min_connections = min_connections  # Minimum bağlantı sayısı eklendi
        self._lock = threading.Lock()
        self.loglayici = logging.getLogger(__name__)
        
        # Thread-local veri yapısı
        self._thread_local = threading.local()
        self._initialize_pool_for_thread()  # İlk başlatma
        
    def _create_connection(self) -> sqlite3.Connection:
        """Yeni bir SQLite bağlantısı oluşturur ve optimize eder."""
        conn = sqlite3.connect(self.db_path, timeout=10)  # Zaman aşımı eklendi
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-2000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=2147483648")
        return conn

    def _initialize_pool_for_thread(self) -> None:
        """Thread için bağlantı havuzunu başlatır."""
        if not hasattr(self._thread_local, 'connection_pool'):
            self._thread_local.connection_pool = []
            self._thread_local.available_connections = []
            self._thread_local.active_connections = 0  # Aktif bağlantı sayısını takip et
            
        # Minimum bağlantı sayısına ulaşana kadar doldur
        while len(self._thread_local.connection_pool) < self.min_connections:
            conn = self._create_connection()
            self._thread_local.connection_pool.append(conn)
            self._thread_local.available_connections.append(conn)
        self.loglayici.debug(f"Thread {threading.get_ident()} için bağlantı havuzu başlatıldı.")

    def _get_connection(self) -> sqlite3.Connection:
        """Havuzdan bağlantı alır veya gerekirse yeni bir tane oluşturur."""
        self._initialize_pool_for_thread()
        
        with self._lock:
            # Müsait bağlantı varsa kullan
            if self._thread_local.available_connections:
                conn = self._thread_local.available_connections.pop()
                if self._is_connection_healthy(conn):
                    self._thread_local.active_connections += 1
                    return conn
                else:
                    self._thread_local.connection_pool.remove(conn)
                    conn.close()

            # Havuzda yer varsa yeni bağlantı oluştur
            if len(self._thread_local.connection_pool) < self.max_connections:
                conn = self._create_connection()
                self._thread_local.connection_pool.append(conn)
                self._thread_local.active_connections += 1
                return conn

            # Havuz doluysa hata fırlat
            raise RepositoryError(
                "Maksimum bağlantı sayısına ulaşıldı",
                ErrorCode.DB_CONNECTION_ERROR.value,
                {"max_connections": self.max_connections}
            )

    def _release_connection(self, conn: sqlite3.Connection) -> None:
        """Bağlantıyı havuza geri döndürür."""
        with self._lock:
            if conn in self._thread_local.connection_pool:
                if self._is_connection_healthy(conn):
                    self._thread_local.available_connections.append(conn)
                else:
                    self._thread_local.connection_pool.remove(conn)
                    conn.close()
                    self._replace_dead_connection()
                self._thread_local.active_connections -= 1

            # Havuzda fazla bağlantı varsa küçült
            self._shrink_pool_if_needed()

    def _is_connection_healthy(self, conn: sqlite3.Connection) -> bool:
        """Bağlantının sağlıklı olup olmadığını kontrol eder."""
        try:
            conn.execute("SELECT 1")
            return True
        except sqlite3.Error as e:
            self.loglayici.warning(f"Bağlantı sağlıksız: {str(e)}")
            return False

    def _replace_dead_connection(self) -> None:
        """Bozuk bağlantıyı yenisiyle değiştirir."""
        if len(self._thread_local.connection_pool) < self.max_connections:
            new_conn = self._create_connection()
            self._thread_local.connection_pool.append(new_conn)
            self._thread_local.available_connections.append(new_conn)
            self.loglayici.info("Bozuk bağlantı yenisiyle değiştirildi.")

    def _shrink_pool_if_needed(self) -> None:
        """Havuzda fazla bağlantı varsa küçültür."""
        if (len(self._thread_local.connection_pool) > self.min_connections and 
            len(self._thread_local.available_connections) > self.min_connections):
            excess = len(self._thread_local.available_connections) - self.min_connections
            for _ in range(excess):
                conn = self._thread_local.available_connections.pop()
                self._thread_local.connection_pool.remove(conn)
                conn.close()
            self.loglayici.debug(f"Havuz küçültüldü, mevcut bağlantı: {len(self._thread_local.connection_pool)}")

    def close(self) -> None:
        """Tüm bağlantıları kapatır."""
        with self._lock:
            if hasattr(self._thread_local, 'connection_pool'):
                for conn in self._thread_local.connection_pool:
                    conn.close()
                self._thread_local.connection_pool.clear()
                self._thread_local.available_connections.clear()
                self._thread_local.active_connections = 0
                self.loglayici.debug(f"Thread {threading.get_ident()} için bağlantı havuzu kapatıldı.")

    # Diğer metodlar (save, load, vb.) aynı kalabilir, sadece _get_connection ve _release_connection kullanılır.
    def __init__(self, db_path: str = "crm_database.db", event_manager=None, max_connections: int = 5):  # Baglanti havuzu icin max_connections eklendi
        self.db_path = db_path
        self.event_manager = event_manager
        self.max_connections = max_connections
        self._lock = threading.Lock()  # Thread guvenli erisim icin
        self.loglayici = logging.getLogger(__name__)
        
        # Thread-local baglanti havuzu olustur
        self._thread_local = threading.local()
        self._thread_local.connection_pool = []  # Her thread icin ayri baglanti havuzu
        self._thread_local.available_connections = []  # Her thread icin ayri musait baglantilar
        
        # Sifreleme yoneticisini olustur
        self.sifreleme = SifrelemeYoneticisi(self.loglayici, self.event_manager)
        
        self.initialize()
        
    def _initialize_pool_for_thread(self) -> None:
        """Mevcut thread icin baglanti havuzunu baslat"""
        # Thread icin baglanti havuzu yoksa olustur
        if not hasattr(self._thread_local, 'connection_pool'):
            self._thread_local.connection_pool = []
            self._thread_local.available_connections = []
            
        # Havuz bossa doldur
        if not self._thread_local.connection_pool:
            for _ in range(self.max_connections):
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                
                # Performans optimizasyonlari
                conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
                conn.execute("PRAGMA synchronous=NORMAL")  # Daha hizli yazma
                conn.execute("PRAGMA cache_size=-2000")  # Cache boyutunu 2MB yap
                conn.execute("PRAGMA temp_store=MEMORY")  # Gecici tablolari RAM'de tut
                conn.execute("PRAGMA mmap_size=2147483648")  # Memory-mapped I/O icin 2GB ayir
                
                self._thread_local.connection_pool.append(conn)
                self._thread_local.available_connections.append(conn)
            
            self.loglayici.debug(f"Thread {threading.get_ident()} icin baglanti havuzu olusturuldu")

    def _get_connection(self) -> sqlite3.Connection:
        """Mevcut thread icin musait bir baglanti alir veya yeni baglanti olusturur"""
        # Thread icin baglanti havuzu yoksa olustur
        self._initialize_pool_for_thread()
        
        with self._lock:
            # Oncelikle havuzdaki musait baglantilari kontrol et
            if self._thread_local.available_connections:
                conn = self._thread_local.available_connections.pop()
                try:
                    # Baglanti sagligini kontrol et
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    # Baglanti bozuksa yenisini olustur
                    self._thread_local.connection_pool.remove(conn)
                    conn.close()
            
            # Tum baglantilar kullaniliyorsa ve havuz limitine ulasilmadiysa
            if len(self._thread_local.connection_pool) < self.max_connections:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                
                # Yeni baglanti icin performans ayarlari
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-2000")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA mmap_size=2147483648")
                
                self._thread_local.connection_pool.append(conn)
                return conn
            
            # Havuz dolu ve tum baglantilar kullaniliyor
            raise RepositoryError(
                "Maksimum baglanti sayisina ulasildi",
                ErrorCode.DB_CONNECTION_ERROR.value,
                {"max_connections": self.max_connections}
            )

    def _release_connection(self, conn: sqlite3.Connection) -> None:
        """Kullanilan baglantiyi thread'in havuzuna geri dondurur"""
        # Thread icin baglanti havuzu yoksa olustur
        self._initialize_pool_for_thread()
        
        with self._lock:
            if conn in self._thread_local.connection_pool and conn not in self._thread_local.available_connections:
                try:
                    # Baglanti sagligini kontrol et
                    conn.execute("SELECT 1")
                    self._thread_local.available_connections.append(conn)
                except sqlite3.Error:
                    # Baglanti bozuksa havuzdan cikar ve yenisini olustur
                    self._thread_local.connection_pool.remove(conn)
                    conn.close()
                    new_conn = sqlite3.connect(self.db_path)
                    new_conn.row_factory = sqlite3.Row
                    self._thread_local.connection_pool.append(new_conn)
                    self._thread_local.available_connections.append(new_conn)

    def close(self) -> None:
        """Tum baglantilarÄ± kapatir"""
        with self._lock:
            # Thread-local baglanti havuzu varsa temizle
            if hasattr(self._thread_local, 'connection_pool'):
                for conn in self._thread_local.connection_pool:
                    try:
                        conn.close()
                    except Exception as e:
                        if self.event_manager:
                            self.event_manager.emit(Event(
                                EVENT_ERROR_OCCURRED,
                                {"error": f"Baglanti kapatma hatasi: {str(e)}"}
                            ))
                self._thread_local.connection_pool.clear()
                self._thread_local.available_connections.clear()
                
                self.loglayici.debug(f"Thread {threading.get_ident()} icin baglanti havuzu kapatildi")

    def _execute_in_main_thread(self, func, *args, **kwargs):
        """
        Fonksiyonu ana thread'de calistirir.
        
        Args:
            func: Calistirilacak fonksiyon
            *args: Fonksiyona gecilecek argümanlar
            **kwargs: Fonksiyona gecilecek anahtar kelime argümanlari
            
        Returns:
            Fonksiyonun donüs degeri
        """
        # Ana thread ID'sini kontrol et (UI thread genellikle ana thread'dir)
        from PyQt6.QtCore import QThread, QCoreApplication
        
        # Mevcut thread'in ID'sini al
        current_thread_id = threading.get_ident()
        
        # Ana thread'in ID'sini al (QApplication'in thread'i)
        main_thread_id = QCoreApplication.instance().thread().currentThreadId()
        
        # Eger zaten ana thread'deyse, dogrudan calistir
        if QThread.currentThread() == QCoreApplication.instance().thread():
            return func(*args, **kwargs)
        
        # Ana thread'de degilse, QTimer.singleShot ile ana thread'de calistir
        from PyQt6.QtCore import QTimer, QEventLoop
        
        result = None
        error = None
        completed = False
        
        def run_in_main_thread():
            nonlocal result, error, completed
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                error = e
            finally:
                completed = True
                
        # Ana thread'de calistir ve tamamlanmasini bekle
        QTimer.singleShot(0, run_in_main_thread)
        
        # Tamamlanana kadar bekle
        loop = QEventLoop()
        
        def check_completed():
            if completed:
                loop.quit()
                
        timer = QTimer()
        timer.timeout.connect(check_completed)
        timer.start(10)  # 10 ms'de bir kontrol et
        
        loop.exec()
        
        if error:
            raise error
            
        return result

    def save(self, df: pd.DataFrame, table_name: str, batch_size: int = 1000) -> None:
        """Veri cercevesini veritabanina kaydeder"""
        try:
            # Hassas verileri sifrele
            df = self.sifreleme.veri_cercevesi_sifrele(df.copy(), table_name)
            
            # Thread-local baglanti al ve verileri kaydet
            conn = self._get_connection()
            try:
                df.to_sql(table_name, conn, if_exists='replace', index=False, chunksize=batch_size)
            finally:
                self._release_connection(conn)
            
            if self.event_manager:
                self.event_manager.emit(Event("data_saved", {
                    "table": table_name,
                    "rows": len(df)
                }))
                
        except Exception as e:
            self.loglayici.error(f"Veri kaydetme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "DB_SAVE_ERROR",
                    "message": f"Veri kaydetme hatasi: {str(e)}"
                }))
            raise

    def load(self, table_name: str, page: int = 1, page_size: int = 1000) -> pd.DataFrame:
        """Veritabanindan veri yukler"""
        try:
            offset = (page - 1) * page_size
            
            # Thread-local baglanti al ve verileri yukle
            conn = self._get_connection()
            try:
                query = f"SELECT * FROM {table_name} LIMIT {page_size} OFFSET {offset}"
                df = pd.read_sql_query(query, conn)
            finally:
                self._release_connection(conn)
            
            # Sifreli verileri coz
            df = self.sifreleme.veri_cercevesi_sifre_coz(df, table_name)
            
            return df
            
        except Exception as e:
            self.loglayici.error(f"Veri yukleme hatasi: {str(e)}")
            if self.event_manager:
                self.event_manager.emit(Event("error_occurred", {
                    "error": "DB_LOAD_ERROR",
                    "message": f"Veri yukleme hatasi: {str(e)}"
                }))
            raise

    def batch_update(self, table_name: str, updates: List[Dict[str, Any]], condition: str, params: List[tuple]) -> None:
        """Toplu guncelleme islemi yapar"""
        try:
            # Thread-local baglanti al ve guncelleme yap
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                for update_dict, param_tuple in zip(updates, params):
                    set_clause = ", ".join([f"{k} = ?" for k in update_dict.keys()])
                    query = f"UPDATE {table_name} SET {set_clause} WHERE {condition}"
                    values = list(update_dict.values()) + list(param_tuple)
                    cursor.execute(query, values)
                
                conn.commit()
            finally:
                self._release_connection(conn)
            
            if self.event_manager:
                self.event_manager.emit(Event(
                    EVENT_DATA_UPDATED,
                    {"operation": "batch_update", "updates": len(updates)}
                ))

        except Exception as e:
            error_msg = f"Toplu guncelleme hatasi: {str(e)}"
            if self.event_manager:
                self.event_manager.emit(Event(
                    EVENT_ERROR_OCCURRED,
                    {"error": error_msg}
                ))
            raise RepositoryError(error_msg, ErrorCode.BATCH_UPDATE_ERROR.value)

    def initialize(self) -> None:
        """Veritabanini baslatir ve gerekli tablolari olusturur"""
        # Thread-local baglanti al
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            tables = {
                'sales_reps': '''
                    CREATE TABLE IF NOT EXISTS sales_reps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Isim" TEXT NOT NULL,
                        "Bolge" TEXT,
                        "E-posta" TEXT,
                        "Telefon" TEXT,
                        "Durum" TEXT CHECK("Durum" IN ('Aktif', 'Pasif'))
                    )''',
                'monthly_targets': '''
                    CREATE TABLE IF NOT EXISTS monthly_targets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Ay" TEXT NOT NULL,
                        "Hedef" REAL,
                        "Para Birimi" TEXT
                    )''',
                'monthly_sales': '''
                    CREATE TABLE IF NOT EXISTS monthly_sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Ay" TEXT NOT NULL,
                        "Satis" REAL
                    )''',
                'pipeline': '''
                    CREATE TABLE IF NOT EXISTS pipeline (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Musteri Adi" TEXT NOT NULL,
                        "Satis Temsilcisi" TEXT,
                        "Sektor" TEXT,
                        "Potansiyel Ciro" REAL,
                        "Pipeline Asamasi" TEXT,
                        "Tahmini Kapanis Tarihi" TEXT
                    )''',
                'customers': '''
                    CREATE TABLE IF NOT EXISTS customers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Musteri Adi" TEXT NOT NULL,
                        "Sektor" TEXT,
                        "Bolge" TEXT,
                        "Global/Lokal" TEXT,
                        "Son Satin Alma Tarihi" TEXT,
                        "Musteri Turu" TEXT CHECK("Musteri Turu" IN ('Ana Musteri', 'Alt Musteri')),
                        "Ana Musteri" TEXT
                    )''',
                'interactions': '''
                    CREATE TABLE IF NOT EXISTS interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Musteri Adi" TEXT NOT NULL,
                        "Tarih" TEXT,
                        "Tur" TEXT,
                        "Notlar" TEXT
                    )''',
                'visits': '''
                    CREATE TABLE IF NOT EXISTS visits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Musteri Adi" TEXT NOT NULL,
                        "Satis Temsilcisi" TEXT,
                        "Ziyaret Tarihi" TEXT,
                        "Ziyaret Konusu" TEXT
                    )''',
                'complaints': '''
                    CREATE TABLE IF NOT EXISTS complaints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Musteri Adi" TEXT NOT NULL,
                        "Siparis No" TEXT,
                        "Sikayet Turu" TEXT,
                        "Sikayet Detayi" TEXT,
                        "Tarih" TEXT,
                        "Durum" TEXT
                    )''',
                'sales': '''
                    CREATE TABLE IF NOT EXISTS sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Ana Musteri" TEXT NOT NULL,
                        "Alt Musteri" TEXT,
                        "Satis Temsilcisi" TEXT,
                        "Ay" TEXT NOT NULL,
                        "Urun Kodu" TEXT,
                        "Urun Adi" TEXT,
                        "Miktar" REAL,
                        "Birim Fiyat" REAL,
                        "Satis Miktari" REAL,
                        "Para Birimi" TEXT
                    )''',
                'hammadde': '''
                    CREATE TABLE IF NOT EXISTS hammadde (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Hammadde Kodu" TEXT NOT NULL,
                        "Hammadde Adi" TEXT NOT NULL,
                        "Hammadde Tipi" TEXT NOT NULL,
                        "Mukavva Tipi" TEXT,
                        "Birim Agirlik" REAL,
                        "Birim m2" REAL,
                        "Uzunluk" REAL,
                        "Birim Maliyet" REAL,
                        "Ay" TEXT NOT NULL,
                        "Para Birimi" TEXT
                    )''',
                'urun_bom': '''
                    CREATE TABLE IF NOT EXISTS urun_bom (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "Urun Kodu" TEXT NOT NULL,
                        "Urun Adi" TEXT NOT NULL,
                        "Hammadde Kodu" TEXT NOT NULL,
                        "Hammadde Adi" TEXT NOT NULL,
                        "Miktar" REAL NOT NULL,
                        "Birim" TEXT NOT NULL,
                        "Aciklama" TEXT,
                        FOREIGN KEY ("Urun Kodu") REFERENCES sales("Urun Kodu"),
                        FOREIGN KEY ("Hammadde Kodu") REFERENCES hammadde("Hammadde Kodu")
                    )'''
            }
            for table_name, create_query in tables.items():
                cursor.execute(create_query)
                logger.info(f"Tablo olusturuldu: {table_name}")

            # Mevcut tablolari guncelle
            cursor.execute("PRAGMA table_info(customers)")
            columns = {col[1] for col in cursor.fetchall()}
            alterations = [
                ("Musteri Turu", 'ALTER TABLE customers ADD COLUMN "Musteri Turu" TEXT CHECK("Musteri Turu" IN (\'Ana Musteri\', \'Alt Musteri\'))'),
                ("Ana Musteri", 'ALTER TABLE customers ADD COLUMN "Ana Musteri" TEXT')
            ]
            for col_name, alter_query in alterations:
                if col_name not in columns:
                    cursor.execute(alter_query)
                    logger.info(f"customers tablosuna '{col_name}' sutunu eklendi")

            cursor.execute("PRAGMA table_info(sales)")
            columns = {col[1] for col in cursor.fetchall()}
            sales_columns_to_add = [
                ("Ana Musteri", 'ALTER TABLE sales ADD COLUMN "Ana Musteri" TEXT'),
                ("Alt Musteri", 'ALTER TABLE sales ADD COLUMN "Alt Musteri" TEXT'),
                ("Urun Kodu", 'ALTER TABLE sales ADD COLUMN "Urun Kodu" TEXT'),
                ("Urun Adi", 'ALTER TABLE sales ADD COLUMN "Urun Adi" TEXT'),
                ("Miktar", 'ALTER TABLE sales ADD COLUMN "Miktar" REAL'),
                ("Birim Fiyat", 'ALTER TABLE sales ADD COLUMN "Birim Fiyat" REAL')
            ]
            for col_name, alter_query in sales_columns_to_add:
                if col_name not in columns:
                    cursor.execute(alter_query)
                    logger.info(f"sales tablosuna '{col_name}' sutunu eklendi")
            
            if "Ana Musteri" not in columns:
                cursor.execute('UPDATE sales SET "Ana Musteri" = "Musteri Adi" WHERE "Ana Musteri" IS NULL')
                logger.info("sales tablosuna 'Ana Musteri' ve 'Alt Musteri' sutunlari eklendi")

            conn.commit()
        finally:
            self._release_connection(conn)

    def optimize(self) -> None:
        """Veritabanini optimize eder (indeksler ve temizlik)"""
        # Thread-local baglanti al
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            index_queries = [
                # Mevcut indeksler
                "CREATE INDEX IF NOT EXISTS idx_customers_name ON customers([Musteri Adi])",
                "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales([Ay])",
                "CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline([Pipeline Asamasi])",
                "CREATE INDEX IF NOT EXISTS idx_visits_date ON visits([Ziyaret Tarihi])",
                "CREATE INDEX IF NOT EXISTS idx_sales_rep ON sales([Satis Temsilcisi])",
                "CREATE INDEX IF NOT EXISTS idx_pipeline_date ON pipeline([Tahmini Kapanis Tarihi])",
                "CREATE INDEX IF NOT EXISTS idx_customers_region ON customers([Bolge])",
                
                # Yeni eklenen indeksler
                "CREATE INDEX IF NOT EXISTS idx_customers_sector ON customers([Sektor])",
                "CREATE INDEX IF NOT EXISTS idx_customers_size ON customers([Global/Lokal])",
                "CREATE INDEX IF NOT EXISTS idx_customers_type ON customers([Musteri Turu])",
                "CREATE INDEX IF NOT EXISTS idx_sales_amount ON sales([Satis Miktari])",
                "CREATE INDEX IF NOT EXISTS idx_pipeline_revenue ON pipeline([Potansiyel Ciro])",
                "CREATE INDEX IF NOT EXISTS idx_complaints_type ON complaints([Sikayet Turu])",
                "CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints([Durum])",
                
                # BileÅŸik indeksler
                "CREATE INDEX IF NOT EXISTS idx_sales_rep_date ON sales([Satis Temsilcisi], [Ay])",
                "CREATE INDEX IF NOT EXISTS idx_customer_region_sector ON customers([Bolge], [Sektor])",
                "CREATE INDEX IF NOT EXISTS idx_pipeline_stage_date ON pipeline([Pipeline Asamasi], [Tahmini Kapanis Tarihi])"
            ]
            for query in index_queries:
                cursor.execute(query)
                logger.info(f"Indeks olusturuldu: {query}")
                
            # VACUUM ile veritabani boyutunu optimize et
            cursor.execute("VACUUM")
            
            # Istatistikleri guncelle
            cursor.execute("ANALYZE")
            
            conn.commit()
            logger.info("Veritabani optimize edildi ve indeksler guncellendi.")
        finally:
            self._release_connection(conn)

    def lazy_load_iterator(self, table_name: str, chunk_size: int = 1000) -> Iterator[pd.DataFrame]:
        """Veriyi chunk_size buyuklugunde parcalar halinde lazy olarak yukler"""
        try:
            # Thread-local baglanti al
            conn = self._get_connection()
            try:
                offset = 0
                while True:
                    query = f"SELECT * FROM {table_name} LIMIT {chunk_size} OFFSET {offset}"
                    chunk = pd.read_sql_query(query, conn)
                    
                    if chunk.empty:
                        break
                        
                    # Sifreli verileri coz
                    chunk = self.sifreleme.veri_cercevesi_sifre_coz(chunk, table_name)
                    
                    yield chunk
                    offset += chunk_size
                    
                    if self.event_manager:
                        self.event_manager.emit(Event("DataLoadProgress", {"table": table_name, "offset": offset}))
            finally:
                self._release_connection(conn)
                    
        except Exception as e:
            if self.event_manager:
                self.event_manager.emit(Event("ErrorOccurred", {"error": str(e)}))
            raise e

    def get_error_details(self, error_code: str) -> Dict[str, Any]:
        """Hata kodu ile ilgili detayli bilgi dondurur"""
        error_details = {
            "DB001": {
                "description": "Veritabani baglanti hatasi",
                "possible_causes": ["Veritabani dosyasi bulunamadi", "Yetersiz izinler", "Dosya kilitli"],
                "suggested_actions": ["Veritabani dosyasinin varligini kontrol et", "Izinleri kontrol et", "Kilitleyen islemleri sonlandir"]
            },
            "DB002": {
                "description": "Tablo bulunamadi",
                "possible_causes": ["Tablo mevcut degil", "Tablo adi yanlis yazilmis"],
                "suggested_actions": ["Tablo adini kontrol et", "Tabloyu olustur"]
            },
            "DB003": {
                "description": "Gecersiz veri",
                "possible_causes": ["Veri tipleri uyumsuz", "Zorunlu alanlar bos"],
                "suggested_actions": ["Veri tiplerini kontrol et", "Zorunlu alanlari doldur"]
            },
            "DB004": {
                "description": "Sorgu hatasi",
                "possible_causes": ["SQL syntax hatasi", "Gecersiz sutun adi"],
                "suggested_actions": ["SQL sorgusunu kontrol et", "Sutun adlarini dogrula"]
            },
            "DB005": {
                "description": "Toplu guncelleme hatasi",
                "possible_causes": ["Veri butunlugu ihlali", "Kilit catismasi"],
                "suggested_actions": ["Veri bÃ¼tÃ¼nlÃ¼gÃ¼nÃ¼ kontrol et", "Islemleri siraya koy"]
            },
            "DB006": {
                "description": "Optimizasyon hatasi",
                "possible_causes": ["Yetersiz disk alani", "Indeks olusturma hatasi"],
                "suggested_actions": ["Disk alanini kontrol et", "Indeksleri yeniden olustur"]
            }
        }
        return error_details.get(error_code, {"description": "Bilinmeyen hata kodu"})

    def log_error(self, error: RepositoryError) -> None:
        """Hatayi loglama sistemi icin kayit eder"""
        error_details = self.get_error_details(error.error_code)
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details,
            "error_info": error_details
        }
        
        if self.event_manager:
            self.event_manager.emit(Event(EVENT_ERROR_OCCURRED, error_log))
        
        # Thread-local baglanti al
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    error_code TEXT,
                    message TEXT,
                    details TEXT,
                    error_info TEXT
                )
            """)
            cursor.execute(
                "INSERT INTO error_logs (timestamp, error_code, message, details, error_info) VALUES (?, ?, ?, ?, ?)",
                (error_log["timestamp"], error_log["error_code"], error_log["message"],
                 json.dumps(error_log["details"]), json.dumps(error_log["error_info"]))
            )
            conn.commit()
        finally:
            self._release_connection(conn)

    def validate_data(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, Optional[List[str]]]:
        """Veri dogrulamasi yapar ve hatalari dondurur"""
        errors = []
        
        if df is None or df.empty:
            errors.append("Veri cercevesi bos veya None")
            return False, errors
            
        required_columns = {
            'sales_reps': ['Isim'],
            'monthly_targets': ['Ay', 'Hedef'],
            'monthly_sales': ['Ay', 'Satis'],
            'pipeline': ['Musteri Adi', 'Pipeline Asamasi'],
            'customers': ['Musteri Adi'],
            'interactions': ['Musteri Adi', 'Tarih'],
            'visits': ['Musteri Adi', 'Ziyaret Tarihi'],
            'complaints': ['Musteri Adi', 'Sikayet Turu'],
            'sales': ['Ana Musteri', 'Ay', 'Satis Miktari'],
            'hammadde': ['Hammadde Kodu', 'Hammadde Adi', 'Hammadde Tipi', 'Birim Maliyet', 'Ay', 'Para Birimi']
        }
        
        if table_name not in required_columns:
            errors.append(f"Gecersiz tablo adi: {table_name}")
            return False, errors
            
        missing_columns = [col for col in required_columns[table_name] if col not in df.columns]
        if missing_columns:
            errors.append(f"Eksik zorunlu sutunlar: {', '.join(missing_columns)}")
            
        if table_name == 'sales_reps':
            if df['Isim'].duplicated().any():
                errors.append("Tekrar eden satisci isimleri mevcut")
                
        elif table_name == 'monthly_targets':
            if not pd.to_numeric(df['Hedef'], errors='coerce').notnull().all():
                errors.append("Hedef sutununda gecersiz sayisal degerler")
                
        elif table_name == 'sales':
            if not pd.to_numeric(df['Satis Miktari'], errors='coerce').notnull().all():
                errors.append("Satis Miktari sutununda gecersiz sayisal degerler")
        
        return len(errors) == 0, errors if errors else None

    def health_check(self) -> Dict[str, Any]:
        """Veritabani saglik kontrolu yapar"""
        health_status = {
            "status": "healthy",
            "connection": True,
            "tables": {},
            "disk_space": {},
            "indexes": {},
            "last_backup": None,
            "errors": []
        }
        
        try:
            # Thread-local baglanti al
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # Tablo durumlarini kontrol et
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    
                    health_status["tables"][table_name] = {
                        "row_count": row_count,
                        "column_count": len(columns),
                        "status": "ok"
                    }
                
                # Indeksleri kontrol et
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
                indexes = cursor.fetchall()
                for index in indexes:
                    index_name = index[0]
                    health_status["indexes"][index_name] = "ok"
                
                # Disk alani kontrolu
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                total_size = page_size * page_count / (1024 * 1024)  # MB cinsinden
                
                health_status["disk_space"] = {
                    "total_size_mb": round(total_size, 2),
                    "status": "ok" if total_size < 1000 else "warning"  # 1GB'dan buyukse uyari ver
                }
                
                # Son yedekleme zamanini kontrol et
                if os.path.exists("backups"):
                    backup_files = os.listdir("backups")
                    if backup_files:
                        latest_backup = max(backup_files, key=lambda x: os.path.getctime(os.path.join("backups", x)))
                        health_status["last_backup"] = datetime.fromtimestamp(
                            os.path.getctime(os.path.join("backups", latest_backup))
                        ).strftime("%Y-%m-%d %H:%M:%S")
            finally:
                self._release_connection(conn)
            
            return health_status
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["errors"].append(str(e))
            return health_status

    def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """Sorgu performansini analiz eder ve aciklama plani dondurur"""
        try:
            # Thread-local baglanti al
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(f"EXPLAIN QUERY PLAN {query}")
                plan = cursor.fetchall()
                
                analysis = {
                    "query": query,
                    "plan": [],
                    "suggestions": []
                }
                
                for step in plan:
                    analysis["plan"].append({
                        "id": step[0],
                        "parent": step[1],
                        "detail": step[3]
                    })
                    
                # Indeks kullanimi kontrolu
                if "SCAN TABLE" in str(plan) and "USING INDEX" not in str(plan):
                    analysis["suggestions"].append("Bu sorgu icin indeks kullanilmiyor. Ilgili sutunlar icin indeks olusturmayi dusunun.")
                    
                # TEMP B-TREE kontrolu
                if "TEMP B-TREE" in str(plan):
                    analysis["suggestions"].append("Gecici B-Tree kullaniliyor. Sorgu optimizasyonu gerekebilir.")
                
                return analysis
            finally:
                self._release_connection(conn)
                
        except Exception as e:
            return {"error": str(e)}

    def optimize_query(self, query: str) -> str:
        """Verilen sorguyu optimize eder"""
        # Basit optimizasyonlar
        optimized = query.strip()
        
        # DISTINCT yerine GROUP BY kullan
        if "DISTINCT" in optimized.upper():
            optimized = optimized.replace("DISTINCT", "")
            if "ORDER BY" in optimized.upper():
                group_by = optimized[optimized.upper().find("ORDER BY"):]
                optimized = optimized[:optimized.upper().find("ORDER BY")]
                optimized += " GROUP BY " + ", ".join([col.strip() for col in group_by.split(",")]) + " " + group_by
                
        # IN yerine EXISTS kullan (buyuk listeler icin)
        if " IN (SELECT" in optimized.upper():
            optimized = optimized.replace(" IN (SELECT", " EXISTS (SELECT")
            
        # LIKE %...% yerine full-text search kullan
        if "LIKE '%'" in optimized.upper():
            self.loglayici.warning("LIKE %...% kullanimi yerine FTS (Full-Text Search) kullanmayi dusunun")
            
        return optimized

    def get_slow_queries(self, threshold_ms: int = 100) -> List[Dict[str, Any]]:
        """Yavas calisabilecek sorgulari tespit eder"""
        slow_queries = []
        
        try:
            # Thread-local baglanti al
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # Ornek sorgular uzerinde EXPLAIN QUERY PLAN calistir
                test_queries = [
                    "SELECT * FROM sales WHERE Ay BETWEEN ? AND ?",
                    "SELECT * FROM customers WHERE Bolge = ? AND Sektor = ?",
                    "SELECT * FROM pipeline WHERE Pipeline_Asamasi = ? ORDER BY Tahmini_Kapanis_Tarihi"
                ]
                
                for query in test_queries:
                    cursor.execute(f"EXPLAIN QUERY PLAN {query}")
                    plan = cursor.fetchall()
                    
                    # Plan analizi
                    if "SCAN TABLE" in str(plan):
                        slow_queries.append({
                            "query": query,
                            "reason": "Table scan detected",
                            "suggestion": "Consider adding appropriate indexes"
                        })
            finally:
                self._release_connection(conn)
                        
        except Exception as e:
            self.loglayici.error(f"Yavas sorgu analizi sirasinda hata: {str(e)}")
            
        return slow_queries
