# ui/ptz_status_thread_fix.py
"""
Corrección para el StatusUpdateThread que causa errores NoneType
El problema ocurre cuando el tracker no retorna un estado válido
"""

from PyQt6.QtCore import QThread, pyqtSignal
import time
from typing import Optional, Dict, Any

class FixedStatusUpdateThread(QThread):
    """Hilo corregido para actualizar estado del sistema PTZ"""
    status_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, tracker=None):
        super().__init__()
        self.tracker = tracker
        self.running = True
        self.error_count = 0
        self.max_errors = 5  # Máximo errores antes de detener
        
    def run(self):
        """Ejecutar actualizaciones de estado con manejo de errores mejorado"""
        while self.running:
            try:
                # Verificar que el tracker existe y es válido
                if not self.tracker:
                    self._log_error("Tracker no disponible")
                    break
                
                # Intentar obtener estado del tracker
                status = self._get_safe_status()
                
                if status:
                    # Resetear contador de errores si obtenemos estado válido
                    self.error_count = 0
                    self.status_updated.emit(status)
                else:
                    # Incrementar contador de errores
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        self._log_error(f"Demasiados errores ({self.error_count}), deteniendo")
                        break
                
                # Esperar antes de la siguiente actualización
                time.sleep(0.5)  # 500ms entre actualizaciones
                
            except Exception as e:
                self.error_count += 1
                error_msg = f"Error en StatusThread: {e}"
                self._log_error(error_msg)
                
                # Si hay demasiados errores, detener el hilo
                if self.error_count >= self.max_errors:
                    self._log_error("Demasiados errores consecutivos, deteniendo hilo")
                    break
                
                # Esperar más tiempo si hay errores
                time.sleep(1.0)
        
        self._log_error("StatusUpdateThread terminado")
    
    def _get_safe_status(self) -> Optional[Dict[str, Any]]:
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
            self._log_error(f"Error obteniendo estado: {e}")
            return self._create_default_status(f"Error: {e}")
    
    def _ensure_required_fields(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Asegurar que el estado tiene todos los campos requeridos"""
        safe_status = {
            # Campos básicos con valores por defecto
            'connected': status.get('connected', False),
            'tracking_active': status.get('tracking_active', False),
            'successful_moves': status.get('successful_moves', 0),
            'failed_moves': status.get('failed_moves', 0),
            'total_detections': status.get('total_detections', 0),
            'success_rate': status.get('success_rate', 0.0),
            'ip': status.get('ip', 'unknown'),
            
            # Campos adicionales si existen
            'active_objects': status.get('active_objects', 0),
            'current_target': status.get('current_target', None),
            'camera_ip': status.get('camera_ip', status.get('ip', 'unknown')),
            'session_time': status.get('session_time', 0),
            'switches_count': status.get('switches_count', 0),
            
            # Timestamp de actualización
            'last_update': time.time()
        }
        
        return safe_status
    
    def _create_default_status(self, reason: str = "Estado no disponible") -> Dict[str, Any]:
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
    
    def _log_error(self, message: str):
        """Log de errores"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] StatusThread ERROR: {message}")
        self.error_occurred.emit(message)
    
    def stop(self):
        """Detener el hilo de forma segura"""
        self.running = False
        self._log_error("Solicitud de detención recibida")

# Corrección para el método de actualización de estado en el diálogo principal
class PTZDialogStatusFix:
    """Clase con métodos corregidos para el diálogo PTZ"""
    
    @staticmethod
    def create_fixed_status_thread(tracker):
        """Crear hilo de estado corregido"""
        return FixedStatusUpdateThread(tracker)
    
    @staticmethod
    def safe_update_status_display(dialog, status: Dict[str, Any]):
        """Actualizar display de estado de forma segura"""
        try:
            if not status or not isinstance(status, dict):
                return
            
            # Actualizar campos básicos si existen en la UI
            if hasattr(dialog, 'connection_status_label'):
                connected = status.get('connected', False)
                connection_text = "🟢 Conectado" if connected else "🔴 Desconectado"
                dialog.connection_status_label.setText(connection_text)
            
            if hasattr(dialog, 'tracking_status_label'):
                tracking = status.get('tracking_active', False)
                tracking_text = "🎯 Activo" if tracking else "⏸️ Inactivo"
                dialog.tracking_status_label.setText(tracking_text)
            
            if hasattr(dialog, 'objects_count_label'):
                objects = status.get('active_objects', 0)
                dialog.objects_count_label.setText(str(objects))
            
            if hasattr(dialog, 'success_rate_label'):
                success_rate = status.get('success_rate', 0.0)
                dialog.success_rate_label.setText(f"{success_rate:.1f}%")
            
            if hasattr(dialog, 'detections_count_label'):
                detections = status.get('total_detections', 0)
                dialog.detections_count_label.setText(str(detections))
            
            if hasattr(dialog, 'moves_count_label'):
                successful = status.get('successful_moves', 0)
                failed = status.get('failed_moves', 0)
                dialog.moves_count_label.setText(f"{successful}/{successful + failed}")
            
            # Actualizar target actual si existe
            if hasattr(dialog, 'current_target_label'):
                target = status.get('current_target')
                target_text = f"🎯 {target}" if target else "➖ Sin objetivo"
                dialog.current_target_label.setText(target_text)
            
            # Si hay error de estado, mostrarlo
            if 'status_error' in status and hasattr(dialog, '_log'):
                dialog._log(f"⚠️ Estado: {status['status_error']}")
                
        except Exception as e:
            print(f"Error actualizando display de estado: {e}")

# Parche para aplicar a enhanced_ptz_multi_object_dialog.py
def apply_status_thread_fix(dialog_class):
    """Aplicar corrección al diálogo PTZ existente"""
    
    def _create_fixed_status_thread(self):
        """Método corregido para crear hilo de estado"""
        if hasattr(self, 'current_tracker') and self.current_tracker:
            self.status_thread = FixedStatusUpdateThread(self.current_tracker)
            self.status_thread.status_updated.connect(self._safe_update_status_display)
            self.status_thread.error_occurred.connect(self._handle_status_error)
            return self.status_thread
        return None
    
    def _safe_update_status_display(self, status):
        """Método corregido para actualizar display"""
        try:
            PTZDialogStatusFix.safe_update_status_display(self, status)
        except Exception as e:
            if hasattr(self, '_log'):
                self._log(f"❌ Error procesando actualización de estado: {e}")
    
    def _handle_status_error(self, error_message):
        """Manejar errores del hilo de estado"""
        if hasattr(self, '_log'):
            self._log(f"⚠️ Error en hilo de estado: {error_message}")
    
    def _start_tracking_fixed(self):
        """Método de inicio de tracking corregido"""
        try:
            # ... código de inicio existente ...
            
            # Crear hilo de estado corregido
            if hasattr(self, 'current_tracker') and self.current_tracker:
                self.status_thread = self._create_fixed_status_thread()
                if self.status_thread:
                    self.status_thread.start()
                    if hasattr(self, '_log'):
                        self._log("✅ Hilo de estado iniciado correctamente")
                else:
                    if hasattr(self, '_log'):
                        self._log("⚠️ No se pudo crear hilo de estado")
            
            return True
            
        except Exception as e:
            if hasattr(self, '_log'):
                self._log(f"❌ Error en inicio de tracking: {e}")
            return False
    
    def _stop_tracking_fixed(self):
        """Método de detención corregido"""
        try:
            # Detener hilo de estado primero
            if hasattr(self, 'status_thread') and self.status_thread:
                self.status_thread.stop()
                self.status_thread.wait(2000)  # Esperar máximo 2 segundos
                self.status_thread = None
                if hasattr(self, '_log'):
                    self._log("✅ Hilo de estado detenido")
            
            # ... resto del código de detención ...
            
        except Exception as e:
            if hasattr(self, '_log'):
                self._log(f"❌ Error deteniendo tracking: {e}")
    
    # Aplicar métodos corregidos a la clase
    dialog_class._create_fixed_status_thread = _create_fixed_status_thread
    dialog_class._safe_update_status_display = _safe_update_status_display
    dialog_class._handle_status_error = _handle_status_error
    dialog_class._start_tracking_fixed = _start_tracking_fixed
    dialog_class._stop_tracking_fixed = _stop_tracking_fixed
    
    return dialog_class

if __name__ == "__main__":
    # Ejemplo de uso
    print("🔧 Corrección StatusUpdateThread PTZ")
    
    # Simular tracker problemático
    class ProblematicTracker:
        def get_status(self):
            return None  # Esto causa el error
    
    # Probar hilo corregido
    tracker = ProblematicTracker()
    thread = FixedStatusUpdateThread(tracker)
    
    def on_status(status):
        print(f"Estado recibido: {status}")
    
    def on_error(error):
        print(f"Error: {error}")
    
    thread.status_updated.connect(on_status)
    thread.error_occurred.connect(on_error)
    
    print("Iniciando hilo de prueba...")
    thread.start()
    
    # Simular ejecución
    import time
    time.sleep(3)
    
    thread.stop()
    thread.wait()
    
    print("Prueba completada")