# -*- coding: utf-8 -*-
# thread_worker.py
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot
import traceback
import sys

class WorkerSignals(QObject):
    """Worker sinyalleri"""
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    """Worker thread"""
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        """Worker thread'inin çalıştırılması"""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()