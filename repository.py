# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any, Tuple, Callable
import pandas as pd
from enum import Enum
import sqlite3
import threading
import time
import queue
import json
from datetime import datetime
from PyQt6.QtCore import QThreadPool
from thread_worker import Worker, WorkerSignals
from repository_interface import RepositoryInterface

class ConnectionPool:
    """SQLite bağlantı havuzu
    
    SQLite bağlantılarını yönetmek için bir havuz sağlar. Bağlantılar yeniden kullanılabilir ve
    thread-safe bir şekilde dağıtılır.
    """
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = queue.Queue(maxsize=max_connections)
        self.connection_count = 0
        self._lock = threading.Lock()

    def get_connection(self) -> sqlite3.Connection:
        """Havuzdan bir bağlantı alır veya yeni bir bağlantı oluşturur."""
        if self.connections.empty() and self.connection_count < self.max_connections:
            with self._lock:
                if self.connection_count < self.max_connections:
                    # check_same_thread=False ile thread-safe hale getiriyoruz
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    self.connection_count += 1
                    return conn
        
        try:
            return self.connections.get(block=True, timeout=5)
        except queue.Empty:
            raise Exception("Veritabanı bağlantı havuzu dolu, lütfen daha sonra tekrar deneyin.")

    def release_connection(self, conn: sqlite3.Connection) -> None:
        """Bağlantıyı havuza geri verir."""
        if conn:
            self.connections.put(conn)

    def close_all(self) -> None:
        """Havuzdaki tüm bağlantıları kapatır."""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                conn.close()
                self.connection_count -= 1
            except queue.Empty:
                break

class RepositoryError(Exception):
    """Repository işlemleri için temel hata sınıfı"""
    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ErrorCode(Enum):
    """Repository hata kodları"""
    DB_CONNECTION_ERROR = "DB001"
    TABLE_NOT_FOUND = "DB002"
    INVALID_DATA = "DB003"
    QUERY_ERROR = "DB004"
    BATCH_UPDATE_ERROR = "DB005"
    OPTIMIZATION_ERROR = "DB006"

class QueryCache:
    """Sorgu sonuçlarını önbelleğe alan sınıf
    
    Sorgu sonuçlarını belirli bir süre (TTL) boyunca saklar ve tekrarlanan sorguların
    performansını artırır.
    """
    def __init__(self, max_size: int = 100, ttl: int = 300):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
        self._lock = threading.Lock()

    def get(self, query: str, params: Optional[tuple] = None) -> Optional[Any]:
        key = (query, str(params))
        with self._lock:
            if key in self.cache:
                timestamp, result = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return result
                else:
                    del self.cache[key]
        return None

    def set(self, query: str, params: Optional[tuple], result: Any) -> None:
        key = (query, str(params))
        with self._lock:
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.items(), key=lambda x: x[1][0])[0]
                del self.cache[oldest_key]
            self.cache[key] = (time.time(), result)

    def clear(self) -> None:
        with self._lock:
            self.cache.clear()

class SqlRepository(RepositoryInterface):
    """SQL tabanlı Repository implementasyonu
    
    SQLite veritabanı ile çalışır ve ConnectionPool kullanarak bağlantıları yönetir.
    """

    def __init__(self, db_path: str, logger: Optional[Any] = None):
        """SqlRepository constructor.
        
        Args:
            db_path (str): Veritabanı dosya yolu
            logger (Optional[Any]): Hata ve bilgi mesajlarını loglamak için logger nesnesi
        """
        self.db_path = db_path
        self.logger = logger
        self.cache = QueryCache(max_size=100, ttl=300)  # 5 dakikalık TTL
        self._data_version = 0
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)
        self.conn_pool = ConnectionPool(db_path, max_connections=5)

    def initialize(self) -> None:
        """Repository’yi başlatır ve bağlantı havuzunu hazırlar."""
        if self.logger:
            self.logger.info(f"Veritabanı bağlantı havuzu başlatıldı: {self.db_path}")

    def close(self) -> None:
        """Bağlantı havuzunu kapatır ve tüm bağlantıları serbest bırakır."""
        self.conn_pool.close_all()
        if self.logger:
            self.logger.info("Veritabanı bağlantı havuzu kapatıldı.")

    def save(self, df: pd.DataFrame, table_name: str, batch_size: int = 1000, callback: Optional[Callable] = None) -> None:
        """Veriyi thread-safe bir şekilde kaydeder ve kompleks tipleri SQLite uyumlu hale getirir.
        
        Args:
            df (pd.DataFrame): Kaydedilecek veri
            table_name (str): Verinin kaydedileceği tablo adı
            batch_size (int): Veri yazma işlemi için toplu iş boyutu
            callback (Optional[Callable]): İşlem tamamlandığında çağrılacak fonksiyon
        """
        def save_task():
            try:
                conn = self.conn_pool.get_connection()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Bağlantı alınamadı: {str(e)}")
                raise RepositoryError(
                    message="Veritabanı bağlantısı alınamadı: Havuz dolu veya başka bir hata oluştu.",
                    error_code=ErrorCode.DB_CONNECTION_ERROR.value,
                    details={"exception": str(e)}
                )
            try:
                is_valid, errors = self.validate_data(df, table_name)
                if not is_valid:
                    raise RepositoryError(
                        message="Geçersiz veri",
                        error_code=ErrorCode.INVALID_DATA.value,
                        details={"errors": errors}
                    )

                df_clean = df.copy()
                for col in df_clean.columns:
                    if df_clean[col].dtype.name == 'category':
                        df_clean[col] = df_clean[col].astype(str)
                    elif df_clean[col].dtype.name == 'object':
                        df_clean[col] = df_clean[col].apply(
                            lambda x: json.dumps(x) if isinstance(x, (list, dict, set)) and pd.notna(x)
                            else x.isoformat() if isinstance(x, (datetime, pd.Timestamp)) and pd.notna(x)
                            else str(x) if pd.notna(x) else None
                        )
                    elif isinstance(df_clean[col].iloc[0], (float, int)):
                        df_clean[col] = df_clean[col].apply(lambda x: float(x) if pd.notna(x) else None)
                    else:
                        df_clean[col] = df_clean[col].apply(
                            lambda x: json.dumps(x) if isinstance(x, (list, dict, set)) and pd.notna(x)
                            else str(x) if pd.notna(x) else None
                        )

                if self.logger:
                    self.logger.debug(f"Kaydedilecek veri sütunları: {list(df_clean.columns)}")
                    self.logger.debug(f"Veri tipleri: {df_clean.dtypes.to_dict()}")
                    self.logger.debug(f"Örnek veri: {df_clean.to_dict(orient='records')[:5]}")

                df_clean.to_sql(table_name, conn, if_exists="append", index=False, chunksize=batch_size)
                conn.commit()
                self._data_version += 1
                self.cache.clear()
                if self.logger:
                    self.logger.info(f"Veri kaydedildi: {table_name}, satır sayısı: {len(df_clean)}")
                return {"success": True}
            except sqlite3.Error as e:
                conn.rollback()
                if self.logger:
                    self.logger.error(f"Veri kaydetme hatası - Tablo: {table_name}, Hata: {str(e)}")
                raise RepositoryError(
                    message=f"Veri kaydetme hatası: {str(e)}",
                    error_code=ErrorCode.QUERY_ERROR.value,
                    details={"exception": str(e), "table": table_name}
                )
            finally:
                self.conn_pool.release_connection(conn)

        worker = Worker(save_task)
        if callback:
            worker.signals.result.connect(callback)
            worker.signals.error.connect(lambda err: self.logger.error(f"Worker hatası: {err[2]}") if self.logger else None)
            worker.signals.finished.connect(lambda: self.logger.debug("Save işlemi tamamlandı") if self.logger else None)
        self.thread_pool.start(worker)

    def load(self, table_name: str, page: int = 1, page_size: int = 1000) -> pd.DataFrame:
        """Belirtilen tablodan veriyi yükler ve önbellekten kontrol eder.
        
        Args:
            table_name (str): Veri yüklenecek tablo adı
            page (int): Sayfa numarası
            page_size (int): Sayfa başına satır sayısı
        
        Returns:
            pd.DataFrame: Yüklenen veri
        """
        try:
            conn = self.conn_pool.get_connection()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bağlantı alınamadı: {str(e)}")
            raise RepositoryError(
                message="Veritabanı bağlantısı alınamadı: Havuz dolu veya başka bir hata oluştu.",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value,
                details={"exception": str(e)}
            )
        try:
            offset = (page - 1) * page_size
            query = f"SELECT * FROM {table_name} LIMIT ? OFFSET ?"
            params = (page_size, offset)

            cached_result = self.cache.get(query, params)
            if cached_result is not None:
                if self.logger:
                    self.logger.debug(f"Önbellekten veri alındı: {table_name}, sayfa: {page}")
                return pd.DataFrame(cached_result)

            df = pd.read_sql_query(query, conn, params=params)
            if df.empty:
                if self.logger:
                    self.logger.warning(f"Tablo boş veya bulunamadı: {table_name}")
            else:
                self.cache.set(query, params, df.to_dict("records"))
                if self.logger:
                    self.logger.info(f"Veri yüklendi: {table_name}, satır sayısı: {len(df)}")
            return df
        except sqlite3.Error as e:
            if self.logger:
                self.logger.error(f"Sorgu hatası - Tablo: {table_name}, Hata: {str(e)}")
            raise RepositoryError(
                message=f"Sorgu hatası: {str(e)}",
                error_code=ErrorCode.QUERY_ERROR.value,
                details={"table": table_name, "exception": str(e)}
            )
        finally:
            self.conn_pool.release_connection(conn)

    def batch_update(self, table_name: str, updates: List[Dict[str, Any]], condition: str, params: List[tuple]) -> None:
        """Tabloda toplu güncelleme yapar.
        
        Args:
            table_name (str): Güncellenecek tablo adı
            updates (List[Dict]): Güncellenecek veriler
            condition (str): WHERE koşulu
            params (List[tuple]): Parametreler
        """
        try:
            conn = self.conn_pool.get_connection()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bağlantı alınamadı: {str(e)}")
            raise RepositoryError(
                message="Veritabanı bağlantısı alınamadı: Havuz dolu veya başka bir hata oluştu.",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value,
                details={"exception": str(e)}
            )
        try:
            cursor = conn.cursor()
            query = f"UPDATE {table_name} SET {{}} WHERE {condition}"
            for update_dict, param in zip(updates, params):
                set_clause = ", ".join([f"{k} = ?" for k in update_dict.keys()])
                full_query = query.format(set_clause)
                cursor.execute(full_query, tuple(update_dict.values()) + param)

            conn.commit()
            self._data_version += 1
            self.cache.clear()
            if self.logger:
                self.logger.info(f"Toplu güncelleme tamamlandı: {table_name}, güncellenen satır: {len(updates)}")
        except sqlite3.Error as e:
            conn.rollback()
            if self.logger:
                self.logger.error(f"Toplu güncelleme hatası: {str(e)}")
            raise RepositoryError(
                message=f"Toplu güncelleme hatası: {str(e)}",
                error_code=ErrorCode.BATCH_UPDATE_ERROR.value,
                details={"exception": str(e)}
            )
        finally:
            self.conn_pool.release_connection(conn)

    def optimize(self) -> None:
        """Veritabanını optimize eder (VACUUM ve ANALYZE çalıştırır)."""
        try:
            conn = self.conn_pool.get_connection()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bağlantı alınamadı: {str(e)}")
            raise RepositoryError(
                message="Veritabanı bağlantısı alınamadı: Havuz dolu veya başka bir hata oluştu.",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value,
                details={"exception": str(e)}
            )
        try:
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")
            conn.commit()
            if self.logger:
                self.logger.info("Veritabanı optimize edildi.")
        except sqlite3.Error as e:
            if self.logger:
                self.logger.error(f"Optimizasyon hatası: {str(e)}")
            raise RepositoryError(
                message=f"Optimizasyon hatası: {str(e)}",
                error_code=ErrorCode.OPTIMIZATION_ERROR.value,
                details={"exception": str(e)}
            )
        finally:
            self.conn_pool.release_connection(conn)

    def get_error_details(self, error_code: str) -> Dict[str, Any]:
        """Hata koduna göre detaylı bilgi döndürür.
        
        Args:
            error_code (str): Hata kodu
        
        Returns:
            Dict[str, Any]: Hata detayları
        """
        error_map = {
            ErrorCode.DB_CONNECTION_ERROR.value: {"description": "Veritabanı bağlantı hatası"},
            ErrorCode.TABLE_NOT_FOUND.value: {"description": "Tablo bulunamadı"},
            ErrorCode.INVALID_DATA.value: {"description": "Geçersiz veri"},
            ErrorCode.QUERY_ERROR.value: {"description": "Sorgu hatası"},
            ErrorCode.BATCH_UPDATE_ERROR.value: {"description": "Toplu güncelleme hatası"},
            ErrorCode.OPTIMIZATION_ERROR.value: {"description": "Optimizasyon hatası"}
        }
        return error_map.get(error_code, {"description": "Bilinmeyen hata"})

    def log_error(self, error: RepositoryError) -> None:
        """Hata mesajını loglar."""
        if self.logger:
            self.logger.error(f"Hata: {error.message}, Kod: {error.error_code}, Detaylar: {error.details}")

    def validate_data(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, Optional[List[str]]]:
        """Veriyi doğrular ve hataları listeler.
        
        Args:
            df (pd.DataFrame): Doğrulanacak veri
            table_name (str): Tablo adı
        
        Returns:
            Tuple[bool, Optional[List[str]]]: Doğrulama sonucu ve hata listesi
        """
        errors = []
        if df.empty:
            errors.append("DataFrame boş")
        if not table_name:
            errors.append("Tablo adı belirtilmemiş")
        if not all(col.replace(" ", "_").isalnum() for col in df.columns):
            errors.append("Geçersiz sütun isimleri")
        
        return (len(errors) == 0, errors if errors else None)

    def health_check(self) -> Dict[str, Any]:
        """Veritabanı bağlantı durumunu kontrol eder.
        
        Returns:
            Dict[str, Any]: Sağlık durumu ve detaylar
        """
        try:
            conn = self.conn_pool.get_connection()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bağlantı alınamadı: {str(e)}")
            return {"status": "unhealthy", "details": f"Bağlantı alınamadı: {str(e)}"}
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return {
                "status": "healthy",
                "details": f"Bağlantı aktif, havuzda {self.conn_pool.connection_count} bağlantı var"
            }
        except sqlite3.Error as e:
            if self.logger:
                self.logger.error(f"Sağlık kontrolü hatası: {str(e)}")
            return {"status": "unhealthy", "details": str(e)}
        finally:
            self.conn_pool.release_connection(conn)