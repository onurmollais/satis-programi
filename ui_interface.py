# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QPushButton, QMessageBox, QLabel, QScrollArea, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLineEdit, QFormLayout, QDateEdit,
                             QComboBox, QTextEdit, QDialog, QProgressBar, QFileDialog, QListWidget,
                             QGroupBox, QSizePolicy, QGridLayout, QScrollArea, QPushButton, QDialog,
                             QDialogButtonBox, QAbstractItemView, QFrame)
from PyQt6.QtCore import Qt, QDate, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

class UIInterface:
    """
    Kullanici arayuzu icin temel arayuz sinifi.
    
    Bu sinif, tum kullanici arayuzu siniflarinin uygulamasi gereken
    temel metodlari tanimlar.
    """
    
    def tum_verileri_yukle(self) -> None:
        """
        Verileri yuklemek icin kullanilan metod.
        
        Bu metod, kullanici arayuzu siniflarinin uygulamasi gereken
        temel bir islevdir.
        """
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.") 
        
    def create_action(self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False):
        """
        Yeni bir QAction olusturur ve yapilandirir.
        
        Args:
            text (str): Aksiyon metni
            slot: Tetiklendiginde calisacak fonksiyon
            shortcut: Klavye kisayolu
            icon: Ikon dosyasi
            tip: Ipucu metni
            checkable (bool): Isaretlenebilir olup olmadigi
            
        Returns:
            QAction: Olusturulan aksiyon nesnesi
        """
        raise NotImplementedError("Bu metod alt siniflar tarafindan uygulanmalidir.") 
