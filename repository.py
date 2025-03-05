# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any, Tuple, Iterator
import pandas as pd
from enum import Enum
import sqlite3  # Örnek olarak SQLite kullanıyoruz, başka bir DB ile değiştirilebilir
import threading
import time
from repository_interface import RepositoryInterface  # Yeni eklenen satır

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
    """Sorgu sonuçlarını önbelleğe alan sınıf"""
    def __init__(self, max_size: int = 100, ttl: int = 300):  # ttl saniye cinsinden
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
        self._lock = threading.Lock()
    
    def get(self, query: str, params: Optional[tuple] = None) -> Optional[Any]:
        """Önbellekten sorgu sonucunu alır"""
        key = (query, str(params))
        with self._lock:
            if key in self.cache:
                timestamp, result = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return result
                else:
                    del self.cache[key]  # TTL süresi dolmuşsa sil
        return None
    
    def set(self, query: str, params: Optional[tuple], result: Any) -> None:
        """Sorgu sonucunu önbelleğe kaydeder"""
        key = (query, str(params))
        with self._lock:
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.items(), key=lambda x: x[1][0])[0]
                del self.cache[oldest_key]
            self.cache[key] = (time.time(), result)
    
    def clear(self) -> None:
        """Önbelleği temizler"""
        with self._lock:
            self.cache.clear()

class SqlRepository(RepositoryInterface):
    """SQL tabanlı Repository implementasyonu"""
    
    def __init__(self, db_path: str, logger: Optional[Any] = None):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.logger = logger
        self.cache = QueryCache(max_size=100, ttl=300)  # Önbellek: 100 sorgu, 5 dakika TTL
        self._data_version = 0  # Veri değişimini izlemek için
    
    def initialize(self) -> None:
        """Veritabanını başlatır ve gerekli tabloları oluşturur"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            if self.logger:
                self.logger.info(f"Veritabanı bağlantısı başlatıldı: {self.db_path}")
        except sqlite3.Error as e:
            raise RepositoryError(
                message=f"Veritabanı bağlantısı başarısız: {str(e)}",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value,
                details={"exception": str(e)}
            )
    
    def close(self) -> None:
        """Veritabani bağlantısını kapatır"""
        if self.conn:
            self.conn.close()
            if self.logger:
                self.logger.info("Veritabanı bağlantısı kapatıldı.")
            self.conn = None
    
    def save(self, df: pd.DataFrame, table_name: str, batch_size: int = 1000) -> None:
        if self.conn is None:
            raise RepositoryError(
                message="Veritabanı bağlantısı yok",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value
            )
        
        is_valid, errors = self.validate_data(df, table_name)
        if not is_valid:
            raise RepositoryError(
                message="Geçersiz veri",
                error_code=ErrorCode.INVALID_DATA.value,
                details={"errors": errors}
            )
        
        try:
            # Veri tiplerini SQLite uyumlu hale getir
            df = df.astype(object).where(pd.notnull(df), None)  # NaN -> None
            if self.logger:
                self.logger.debug(f"Veritabanına kaydedilecek veri: {df.to_dict(orient='records')[:5]}")  # İlk 5 kaydı logla
            
            df.to_sql(table_name, self.conn, if_exists="append", index=False, chunksize=batch_size)
            self._data_version += 1
            self.cache.clear()
            if self.logger:
                self.logger.info(f"Veri kaydedildi: {table_name}, satır sayısı: {len(df)}")
        except sqlite3.Error as e:
            if self.logger:
                self.logger.error(f"Veri kaydetme hatası - Tablo: {table_name}, Veri: {df.to_dict(orient='records')[:5]}, Hata: {str(e)}")
            raise RepositoryError(
                message=f"Veri kaydetme hatası: {str(e)}",
                error_code=ErrorCode.QUERY_ERROR.value,
                details={"exception": str(e), "table": table_name, "sample_data": df.to_dict(orient='records')[:5]}
            )
    
    def load(self, table_name: str, page: int = 1, page_size: int = 1000) -> pd.DataFrame:
        """Belirtilen tablodan veriyi yükler (önbelleklenmiş)"""
        if self.conn is None:
            raise RepositoryError(
                message="Veritabanı bağlantısı yok",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value
            )
        
        offset = (page - 1) * page_size
        query = f"SELECT * FROM {table_name} LIMIT ? OFFSET ?"
        params = (page_size, offset)
        
        # Önbellekten kontrol et
        cached_result = self.cache.get(query, params)
        if cached_result is not None:
            if self.logger:
                self.logger.debug(f"Önbellekten veri alındı: {table_name}, sayfa: {page}")
            return pd.DataFrame(cached_result)
        
        try:
            df = pd.read_sql_query(query, self.conn, params=params)
            if df.empty:
                if self.logger:
                    self.logger.warning(f"Tablo boş veya bulunamadı: {table_name}")
            else:
                self.cache.set(query, params, df.to_dict("records"))  # Önbelleğe kaydet
                if self.logger:
                    self.logger.info(f"Veri yüklendi: {table_name}, satır sayısı: {len(df)}")
            return df
        except sqlite3.Error as e:
            raise RepositoryError(
                message=f"Sorgu hatası: {str(e)}",
                error_code=ErrorCode.QUERY_ERROR.value,
                details={"table": table_name, "exception": str(e)}
            )
    
    def batch_update(self, table_name: str, updates: List[Dict[str, Any]], condition: str, params: List[tuple]) -> None:
        """Toplu güncelleme işlemi yapar"""
        if self.conn is None:
            raise RepositoryError(
                message="Veritabanı bağlantısı yok",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value
            )
        
        try:
            cursor = self.conn.cursor()
            query = f"UPDATE {table_name} SET {{}} WHERE {condition}"
            for update_dict, param in zip(updates, params):
                set_clause = ", ".join([f"{k} = ?" for k in update_dict.keys()])
                full_query = query.format(set_clause)
                cursor.execute(full_query, tuple(update_dict.values()) + param)
            
            self.conn.commit()
            self._data_version += 1  # Veri değişti
            self.cache.clear()  # Önbelleği temizle
            if self.logger:
                self.logger.info(f"Toplu güncelleme tamamlandı: {table_name}, güncellenen satır: {len(updates)}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RepositoryError(
                message=f"Toplu güncelleme hatası: {str(e)}",
                error_code=ErrorCode.BATCH_UPDATE_ERROR.value,
                details={"exception": str(e)}
            )
    
    def optimize(self) -> None:
        """Veritabanını optimize eder (indeksler ve temizlik)"""
        if self.conn is None:
            raise RepositoryError(
                message="Veritabanı bağlantısı yok",
                error_code=ErrorCode.DB_CONNECTION_ERROR.value
            )
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("VACUUM")  # SQLite için temizlik
            cursor.execute("ANALYZE")  # İstatistikleri güncelle
            self.conn.commit()
            if self.logger:
                self.logger.info("Veritabanı optimize edildi.")
        except sqlite3.Error as e:
            raise RepositoryError(
                message=f"Optimizasyon hatası: {str(e)}",
                error_code=ErrorCode.OPTIMIZATION_ERROR.value,
                details={"exception": str(e)}
            )
    
    def get_error_details(self, error_code: str) -> Dict[str, Any]:
        """Hata kodu ile ilgili detaylı bilgi döndürür"""
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
        """Hatayı loglama sistemi için kayıt eder"""
        if self.logger:
            self.logger.error(f"Hata: {error.message}, Kod: {error.error_code}, Detaylar: {error.details}")
    
    def validate_data(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, Optional[List[str]]]:
        """Veri doğrulaması yapar ve hataları döndürür"""
        errors = []
        if df.empty:
            errors.append("DataFrame boş")
        if not table_name:
            errors.append("Tablo adı belirtilmemiş")
        if not all(col.replace(" ", "_").isalnum() for col in df.columns):
            errors.append("Geçersiz sütun isimleri")
        
        return (len(errors) == 0, errors if errors else None)
    
    def health_check(self) -> Dict[str, Any]:
        """Veritabani sağlık kontrolü yapar"""
        if self.conn is None:
            return {"status": "unhealthy", "details": "Bağlantı yok"}
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            return {"status": "healthy", "details": "Bağlantı aktif"}
        except sqlite3.Error as e:
            return {"status": "unhealthy", "details": str(e)}

# Örnek kullanım
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("SqlRepository")
    
    repo = SqlRepository(db_path=":memory:", logger=logger)
    repo.initialize()
    
    # Örnek veri
    df = pd.DataFrame({"id": [1, 2], "name": ["A", "B"]})
    repo.save(df, "test_table")
    
    # Aynı sorguyu iki kez çalıştır
    result1 = repo.load("test_table", page=1, page_size=10)
    result2 = repo.load("test_table", page=1, page_size=10)
    print(result1.equals(result2))  # True, önbellekten döner
    
    repo.close()