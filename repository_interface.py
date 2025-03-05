from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Iterator
import pandas as pd

class RepositoryInterface(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def save(self, df: pd.DataFrame, table_name: str, batch_size: int = 1000) -> None:
        pass

    @abstractmethod
    def load(self, table_name: str, page: int = 1, page_size: int = 1000) -> pd.DataFrame:
        pass

    @abstractmethod
    def batch_update(self, table_name: str, updates: List[Dict[str, Any]], condition: str, params: List[tuple]) -> None:
        pass

    @abstractmethod
    def optimize(self) -> None:
        pass

    @abstractmethod
    def get_error_details(self, error_code: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def log_error(self, error: Any) -> None:
        pass

    @abstractmethod
    def validate_data(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, Optional[List[str]]]:
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def lazy_load_iterator(self, table_name: str, chunk_size: int = 1000) -> Iterator[pd.DataFrame]:
        pass 