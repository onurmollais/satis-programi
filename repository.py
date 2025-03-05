# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
from enum import Enum

class RepositoryError(Exception):
    """Repository islemleri icin temel hata sinifi"""
    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ErrorCode(Enum):
    """Repository hata kodlari"""
    DB_CONNECTION_ERROR = "DB001"
    TABLE_NOT_FOUND = "DB002"
    INVALID_DATA = "DB003"
    QUERY_ERROR = "DB004"
    BATCH_UPDATE_ERROR = "DB005"
    OPTIMIZATION_ERROR = "DB006"

class RepositoryInterface:
    """Veri erisimi icin genel Repository arayuzu"""
    
    def save(self, df: pd.DataFrame, table_name: str, batch_size: int = 1000) -> None:
        """Veriyi bir tabloya kaydeder"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def load(self, table_name: str, page: int = 1, page_size: int = 1000) -> pd.DataFrame:
        """Belirtilen tablodan veriyi yukler"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def batch_update(self, table_name: str, updates: List[Dict[str, Any]], condition: str, params: List[tuple]) -> None:
        """Toplu guncelleme islemi yapar"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def initialize(self) -> None:
        """Veritabanini baslatir ve gerekli tablolari olusturur"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def close(self) -> None:
        """Veritabani baglantisini kapatir"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def optimize(self) -> None:
        """Veritabanini optimize eder (indeksler ve temizlik)"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def get_error_details(self, error_code: str) -> Dict[str, Any]:
        """Hata kodu ile ilgili detayli bilgi dondurur"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def log_error(self, error: RepositoryError) -> None:
        """Hatayi loglama sistemi icin kayit eder"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def validate_data(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, Optional[List[str]]]:
        """Veri dogrulamasi yapar ve hatalari dondurur"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")

    def health_check(self) -> Dict[str, Any]:
        """Veritabani saglik kontrolu yapar"""
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.")
