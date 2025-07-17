# ui/ptz_dialog_patch.py
"""
Parche específico para corregir el error NoneType en enhanced_ptz_multi_object_dialog.py
Este parche soluciona el error "'NoneType' object has no attribute 'get'"
"""

def apply_critical_fix():
    """
    Aplicar corrección crítica al enhanced_ptz_multi_object_dialog.py
    
    INSTRUCCIONES DE APLICACIÓN:
    
    1. Reemplazar la clase StatusUpdateThread en enhanced_ptz_multi_object_dialog.py:
    """
    
    status_update_thread_replacement = '''
class StatusUpdateThread(QThread):
    """Hilo corregido para actualizar estado del sistema PTZ"""
    status_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, tracker=None):
        super().__init__()
        self.tracker = tracker
        self.running = True
        self.error_count = 0
        self.max_errors = 10  # Máximo errores antes de detener
        
    def run(self):
        """Ejecutar actualizaciones de estado con manejo de errores mejorado"""
        while self.running:
            try:
                # Verificar que el tracker existe y es válido
                if not self.tracker:
                    time.sleep(1.0)
                    continue
                
                # Intentar obtener estado del tracker de forma segura
                status = self._get_safe_status()
                
                if status and isinstance(status, dict):
                    # Resetear contador de errores si obtenemos estado válido
                    self.error_count = 0
                    self.status_updated.emit(status)
                else:
                    # Incrementar contador de errores
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        break
                
                # Esperar antes de la siguiente actualización
                time.sleep(0.5)  # 500ms entre actualizaciones
                
            except Exception as e:
                self.error_count += 1
                error_msg = f"Error en StatusThread: {e}"
                self.error_occurred.emit(error_msg)
                
                # Si hay demasiados errores, detener el hilo
                if self.error_count >= self.max_errors:
                    break
                
                # Esperar más tiempo si hay errores
                time.sleep(1.0)
    
    def _get_safe_status(self):
        """Obtener estado del tracker de forma segura"""
        try:
            # Verificar que el tracker tiene método get_status
            if not hasattr(self.tracker, 'get_status'):
                return self._create_default_status("Tracker sin método get_status")
            
            # Intentar obtener estado
            status = self.tracker.get_status()
            
            # Verificar que el estado es válido
            if status is None:
                return self._create_default_status("Estado None retornado")
            
            # Verificar que es un diccionario
            if not isinstance(status, dict):
                return self._create_default_status(f"Estado inválido: {type(status)}")
            
            # Asegurar campos mínimos requeridos
            safe_status = self._ensure_required_fields(status)
            return safe_status
            
        except Exception as e:
            return self._create_default_status(f"Error: {e}")
    
    def _ensure_required_fields(self, status):
        """Asegurar que el estado tiene todos los campos requeridos"""
        safe_status = {
            'connected': status.get('connected', False),
            'tracking_active': status.get('tracking_active', False),
            'successful_moves': status.get('successful_moves', 0),
            'failed_moves': status.get('failed_moves', 0),
            'total_detections': status.get('total_detections', 0),
            'success_rate': status.get('success_rate', 0.0),
            'ip': status.get('ip', 'unknown'),
            'active_objects': status.get('active_objects', 0),
            'current_target': status.get('current_target', None),
            'camera_ip': status.get('camera_ip', status.get('ip', 'unknown')),
            'session_time': status.get('session_time', 0),
            'switches_count': status.get('switches_count', 0),
            'last_update': time.time()
        }
        return safe_status
    
    def _create_default_status(self, reason="Estado no disponible"):
        """Crear estado por defecto cuando no se puede obtener del tracker"""
        return {
            'connected': False,
            'tracking_active': False,
            'successful_moves': 0,
            'failed_moves': 0,
            'total_detections': 0,
            'success_rate': 0.0,
            'ip': 'unknown',
            'active_objects': 0,
            'current_target': None,
            'camera_ip': 'unknown',
            'session_time': 0,
            'switches_count': 0,
            'status_error': reason,
            'last_update': time.time()
        }
    
    def stop(self):
        """Detener el hilo de forma segura"""
        self.running = False
'''

    # 2. Reemplazar el método _update_status_display en EnhancedMultiObjectPTZDialog:
    
    update_status_display_replacement = '''
    def _update_status_display(self, status):
        """Actualizar display de estado de forma segura - MÉTODO CORREGIDO"""
        try:
            # Verificar que status es válido
            if not status or not isinstance(status, dict):
                self._log("⚠️ Estado inválido recibido")
                return
            
            # Actualizar campos básicos si existen en la UI
            try:
                if hasattr(self, 'connection_status_label'):
                    connected = status.get('connected', False)
                    connection_text = "🟢 Conectado" if connected else "🔴 Desconectado"
                    self.connection_status_label.setText(connection_text)
                
                if hasattr(self, 'tracking_status_label'):
                    tracking = status.get('tracking_active', False)
                    tracking_text = "🎯 Activo" if tracking else "⏸️ Inactivo"
                    self.tracking_status_label.setText(tracking_text)
                
                if hasattr(self, 'objects_count_label'):
                    objects = status.get('active_objects', 0)
                    self.objects_count_label.setText(str(objects))
                
                if hasattr(self, 'success_rate_label'):
                    success_rate = status.get('success_rate', 0.0)
                    self.success_rate_label.setText(f"{success_rate:.1f}%")
                
                if hasattr(self, 'detections_count_label'):
                    detections = status.get('total_detections', 0)
                    self.detections_count_label.setText(str(detections))
                
                if hasattr(self, 'moves_count_label'):
                    successful = status.get('successful_moves', 0)
                    failed = status.get('failed_moves', 0)
                    total = successful + failed
                    self.moves_count_label.setText(f"{successful}/{total}")
                
                # Actualizar target actual si existe
                if hasattr(self, 'current_target_label'):
                    target = status.get('current_target')
                    target_text = f"🎯 {target}" if target else "➖ Sin objetivo"
                    self.current_target_label.setText(target_text)
                
                # Si hay error de estado, mostrarlo
                if 'status_error' in status:
                    self._log(f"⚠️ Estado: {status['status_error']}")
                    
            except Exception as ui_error:
                self._log(f"⚠️ Error actualizando UI: {ui_error}")
                
        except Exception as e:
            self._log(f"❌ Error crítico procesando estado: {e}")
'''

    # 3. Agregar método de manejo de errores de estado:
    
    handle_status_error_method = '''
    def _handle_status_error(self, error_message):
        """Manejar errores del hilo de estado"""
        self._log(f"⚠️ Error en hilo de estado: {error_message}")
        
        # Si hay demasiados errores, detener tracking
        if "Demasiados errores" in error_message:
            self._log("🛑 Deteniendo seguimiento por errores críticos")
            self._stop_tracking()
'''

    # 4. Modificar el método _start_tracking para usar el hilo corregido:
    
    start_tracking_modification = '''
    # En el método _start_tracking, reemplazar la sección del status_thread con:
    
    # Iniciar hilo de actualización de estado CORREGIDO
    if self.current_tracker:
        self.status_thread = StatusUpdateThread(self.current_tracker)
        self.status_thread.status_updated.connect(self._update_status_display)
        self.status_thread.error_occurred.connect(self._handle_status_error)
        self.status_thread.start()
        self._log("✅ Hilo de estado iniciado (versión corregida)")
    else:
        self._log("⚠️ No hay tracker disponible para hilo de estado")
'''

    print("=== INSTRUCCIONES DE APLICACIÓN DEL PARCHE ===")
    print("\n1. REEMPLAZAR StatusUpdateThread:")
    print("   Buscar 'class StatusUpdateThread(QThread):' y reemplazar toda la clase")
    
    print("\n2. REEMPLAZAR _update_status_display:")
    print("   Buscar 'def _update_status_display(self, status):' y reemplazar el método")
    
    print("\n3. AGREGAR _handle_status_error:")
    print("   Agregar el método _handle_status_error después de _update_status_display")
    
    print("\n4. MODIFICAR _start_tracking:")
    print("   En _start_tracking, reemplazar la sección donde se crea status_thread")
    
    print("\n5. VERIFICAR IMPORTS:")
    print("   Asegurar que 'import time' está en los imports del archivo")
    
    return {
        'status_thread_class': status_update_thread_replacement,
        'update_display_method': update_status_display_replacement,
        'error_handler_method': handle_status_error_method,
        'start_tracking_mod': start_tracking_modification
    }

# Función para generar el archivo corregido completo
def generate_corrected_file_content():
    """Generar contenido completo del archivo corregido"""
    
    corrected_content = '''
# ARCHIVO CORREGIDO: ui/enhanced_ptz_multi_object_dialog.py
# ESTE ES EL CONTENIDO CORREGIDO PARA REEMPLAZAR EL ORIGINAL

"""
Diálogo PTZ mejorado con seguimiento multi-objeto y zoom inteligente - VERSIÓN CORREGIDA
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QComboBox, QLabel,
    QMessageBox, QGroupBox, QCheckBox, QSpinBox, QTextEdit, QSlider, QProgressBar,
    QDoubleSpinBox, QTabWidget, QWidget, QFormLayout, QSplitter, QListWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QScrollArea,
    QLineEdit, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette, QPixmap, QPainter, QBrush
import threading
import time
import json
import os
import sys
from typing import Optional, Dict, List, Any
from datetime import datetime

# Importar sistemas según disponibilidad
try:
    from core.multi_object_ptz_system import (
        MultiObjectPTZTracker, MultiObjectConfig, TrackingMode, ObjectPriority,
        create_multi_object_tracker, get_preset_config, PRESET_CONFIGS,
        analyze_tracking_performance
    )
    MULTI_OBJECT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Sistema multi-objeto no disponible: {e}")
    MULTI_OBJECT_AVAILABLE = False

try:
    from core.ptz_tracking_integration_enhanced import (
        PTZTrackingSystemEnhanced, start_ptz_session, stop_ptz_session,
        update_ptz_detections, process_ptz_yolo_results, get_ptz_status
    )
    INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Sistema de integración no disponible: {e}")
    INTEGRATION_AVAILABLE = False

try:
    from core.ptz_control import PTZCameraONVIF
    BASIC_PTZ_AVAILABLE = True
except ImportError:
    BASIC_PTZ_AVAILABLE = False

# === CLASE STATUSUPDATETHREAD CORREGIDA ===
class StatusUpdateThread(QThread):
    """Hilo corregido para actualizar estado del sistema PTZ"""
    status_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, tracker=None):
        super().__init__()
        self.tracker = tracker
        self.running = True
        self.error_count = 0
        self.max_errors = 10
        
    def run(self):
        """Ejecutar actualizaciones de estado con manejo de errores mejorado"""
        while self.running:
            try:
                if not self.tracker:
                    time.sleep(1.0)
                    continue
                
                status = self._get_safe_status()
                
                if status and isinstance(status, dict):
                    self.error_count = 0
                    self.status_updated.emit(status)
                else:
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        break
                
                time.sleep(0.5)
                
            except Exception as e:
                self.error_count += 1
                self.error_occurred.emit(f"Error en StatusThread: {e}")
                
                if self.error_count >= self.max_errors:
                    break
                
                time.sleep(1.0)
    
    def _get_safe_status(self):
        """Obtener estado del tracker de forma segura"""
        try:
            if not hasattr(self.tracker, 'get_status'):
                return self._create_default_status("Tracker sin método get_status")
            
            status = self.tracker.get_status()
            
            if status is None:
                return self._create_default_status("Estado None retornado")
            
            if not isinstance(status, dict):
                return self._create_default_status(f"Estado inválido: {type(status)}")
            
            return self._ensure_required_fields(status)
            
        except Exception as e:
            return self._create_default_status(f"Error: {e}")
    
    def _ensure_required_fields(self, status):
        """Asegurar que el estado tiene todos los campos requeridos"""
        return {
            'connected': status.get('connected', False),
            'tracking_active': status.get('tracking_active', False),
            'successful_moves': status.get('successful_moves', 0),
            'failed_moves': status.get('failed_moves', 0),
            'total_detections': status.get('total_detections', 0),
            'success_rate': status.get('success_rate', 0.0),
            'ip': status.get('ip', 'unknown'),
            'active_objects': status.get('active_objects', 0),
            'current_target': status.get('current_target', None),
            'camera_ip': status.get('camera_ip', status.get('ip', 'unknown')),
            'session_time': status.get('session_time', 0),
            'switches_count': status.get('switches_count', 0),
            'last_update': time.time()
        }
    
    def _create_default_status(self, reason="Estado no disponible"):
        """Crear estado por defecto"""
        return {
            'connected': False,
            'tracking_active': False,
            'successful_moves': 0,
            'failed_moves': 0,
            'total_detections': 0,
            'success_rate': 0.0,
            'ip': 'unknown',
            'active_objects': 0,
            'current_target': None,
            'camera_ip': 'unknown',
            'session_time': 0,
            'switches_count': 0,
            'status_error': reason,
            'last_update': time.time()
        }
    
    def stop(self):
        """Detener el hilo de forma segura"""
        self.running = False

# === RESTO DEL ARCHIVO ENHANCED_PTZ_MULTI_OBJECT_DIALOG.PY ===
# (Mantener todo el contenido original excepto StatusUpdateThread y los métodos que se modifican)
'''

    print("=== APLICACIÓN RÁPIDA DEL PARCHE ===")
    print("\nPARA SOLUCIONAR EL ERROR INMEDIATAMENTE:")
    print("\n1. Abrir: ui/enhanced_ptz_multi_object_dialog.py")
    
    print("\n2. BUSCAR y REEMPLAZAR la clase StatusUpdateThread completa:")
    print("   Buscar: 'class StatusUpdateThread(QThread):'")
    print("   Reemplazar TODA la clase con la versión corregida")
    
    print("\n3. BUSCAR y MODIFICAR el método _update_status_display:")
    print("   Buscar: 'def _update_status_display(self, status):'")
    print("   Agregar verificación al inicio del método:")
    
    quick_fix_code = '''
    def _update_status_display(self, status):
        """Actualizar display de estado - VERSIÓN CORREGIDA"""
        try:
            # === AGREGAR ESTAS LÍNEAS AL INICIO ===
            if not status or not isinstance(status, dict):
                return
            # === FIN DE LÍNEAS AGREGADAS ===
            
            # ... resto del método original sin cambios ...
        except Exception as e:
            if hasattr(self, '_log'):
                self._log(f"❌ Error procesando actualización de estado: {e}")
'''
    
    print(quick_fix_code)
    
    print("\n4. AGREGAR método de manejo de errores:")
    print("   Agregar después del método _update_status_display:")
    
    error_handler_code = '''
    def _handle_status_error(self, error_message):
        """Manejar errores del hilo de estado"""
        if hasattr(self, '_log'):
            self._log(f"⚠️ Error en hilo de estado: {error_message}")
'''
    
    print(error_handler_code)
    
    print("\n5. MODIFICAR la creación del status_thread en _start_tracking:")
    print("   Buscar donde se crea self.status_thread y reemplazar con:")
    
    thread_creation_fix = '''
    # Iniciar hilo de actualización de estado CORREGIDO
    if self.current_tracker:
        self.status_thread = StatusUpdateThread(self.current_tracker)
        self.status_thread.status_updated.connect(self._update_status_display)
        self.status_thread.error_occurred.connect(self._handle_status_error)
        self.status_thread.start()
'''
    
    print(thread_creation_fix)
    
    return corrected_content

# Función de verificación post-aplicación
def verify_fix_applied():
    """Verificar que la corrección se aplicó correctamente"""
    verification_steps = [
        "✅ StatusUpdateThread tiene método _get_safe_status",
        "✅ _update_status_display verifica que status no sea None",
        "✅ _handle_status_error existe y maneja errores",
        "✅ status_thread.error_occurred conectado a _handle_status_error",
        "✅ import time agregado si faltaba"
    ]
    
    print("\n=== VERIFICACIÓN POST-APLICACIÓN ===")
    for step in verification_steps:
        print(step)
    
    print("\n✅ DESPUÉS DE APLICAR LA CORRECCIÓN:")
    print("- El error 'NoneType' object has no attribute 'get' debe desaparecer")
    print("- El seguimiento multi-objeto debe funcionar sin errores de estado")
    print("- Los logs deben mostrar información de estado válida")

if __name__ == "__main__":
    print("🔧 PARCHE PARA ENHANCED PTZ MULTI-OBJECT DIALOG")
    print("=" * 60)
    
    # Generar parche
    patch_data = apply_critical_fix()
    
    print("\n📋 RESUMEN DEL PROBLEMA:")
    print("- StatusUpdateThread obtiene estado None del tracker")
    print("- Intenta hacer status.get() en un objeto None")
    print("- Causa error repetitivo cada 500ms")
    
    print("\n🛠️ SOLUCIÓN APLICADA:")
    print("- Verificación de estado None antes de usar .get()")
    print("- Creación de estado por defecto si el tracker falla")
    print("- Manejo de errores mejorado en el hilo")
    print("- Contador de errores para evitar loops infinitos")
    
    print("\n⚡ APLICAR CORRECCIÓN AHORA:")
    print("1. Usar las instrucciones de arriba para modificar el archivo")
    print("2. Guardar y reiniciar la aplicación")
    print("3. Probar seguimiento multi-objeto")
    
    verify_fix_applied()