# core/ptz_integration_bridge.py
"""
Bridge de integración PTZ para conectar con enhanced_ptz_multi_object_dialog.py
Este archivo proporciona la capa de conexión entre los sistemas PTZ y la UI
"""

import threading
import time
import json
import os
import queue
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from datetime import datetime

# === CONFIGURACIÓN DE IMPORTS CONDICIONALES ===
# Intentar importar sistemas PTZ con fallbacks

# Sistema multi-objeto principal
try:
    from core.multi_object_ptz_system import (
        MultiObjectPTZTracker, MultiObjectConfig, TrackingMode, ObjectPriority,
        create_multi_object_tracker, get_preset_config, PRESET_CONFIGS
    )
    MULTI_OBJECT_AVAILABLE = True
    print("✅ Sistema multi-objeto PTZ disponible")
except ImportError as e:
    print(f"⚠️ Sistema multi-objeto no disponible: {e}")
    MULTI_OBJECT_AVAILABLE = False
    
    # Crear clases stub si no están disponibles
    class MultiObjectConfig:
        def __init__(self, **kwargs):
            self.alternating_enabled = kwargs.get('alternating_enabled', True)
            self.primary_follow_time = kwargs.get('primary_follow_time', 5.0)
            self.secondary_follow_time = kwargs.get('secondary_follow_time', 3.0)
            self.auto_zoom_enabled = kwargs.get('auto_zoom_enabled', True)
            self.min_confidence_threshold = kwargs.get('min_confidence_threshold', 0.5)
            
    class TrackingMode:
        SINGLE_OBJECT = "single"
        MULTI_OBJECT_ALTERNATING = "alternating"
        
    PRESET_CONFIGS = {
        'maritime_standard': MultiObjectConfig(),
        'maritime_fast': MultiObjectConfig(primary_follow_time=3.0)
    }

# Sistema básico PTZ
try:
    from core.ptz_control import PTZCameraONVIF
    BASIC_PTZ_AVAILABLE = True
    print("✅ Sistema básico PTZ disponible")
except ImportError as e:
    print(f"⚠️ Sistema básico PTZ no disponible: {e}")
    BASIC_PTZ_AVAILABLE = False

# Librería ONVIF
try:
    from onvif import ONVIFCamera
    ONVIF_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Librería ONVIF no disponible: {e}")
    ONVIF_AVAILABLE = False

@dataclass
class PTZSessionInfo:
    """Información de sesión PTZ"""
    camera_id: str
    ip: str
    port: int
    username: str
    password: str
    tracker: Optional[Any] = None
    active: bool = False
    start_time: float = 0.0
    detection_count: int = 0
    error_count: int = 0
    last_status: Dict = None

class PTZIntegrationBridge:
    """Bridge de integración PTZ para enhanced_ptz_multi_object_dialog.py"""
    
    def __init__(self):
        self.sessions: Dict[str, PTZSessionInfo] = {}
        self.active_sessions: List[str] = []
        self.detection_queue = queue.Queue(maxsize=500)
        self.running = True
        
        # Callbacks para el diálogo
        self.on_status_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_detection_processed: Optional[Callable] = None
        
        print("🔗 PTZ Integration Bridge inicializado")
    
    def create_ptz_session(self, camera_data: Dict) -> bool:
        """Crear nueva sesión PTZ"""
        try:
            camera_id = camera_data.get('nombre', 'unknown')
            ip = camera_data.get('ip', '')
            port = int(camera_data.get('puerto', 80))
            username = camera_data.get('usuario', '')
            password = camera_data.get('password', '')
            
            if not ip or not username:
                raise ValueError("IP y usuario son requeridos")
            
            session = PTZSessionInfo(
                camera_id=camera_id,
                ip=ip,
                port=port,
                username=username,
                password=password,
                start_time=time.time()
            )
            
            # Intentar crear tracker multi-objeto si está disponible
            if MULTI_OBJECT_AVAILABLE:
                try:
                    # Usar configuración predefinida marítima
                    config = PRESET_CONFIGS.get('maritime_standard', MultiObjectConfig())
                    tracker = create_multi_object_tracker(ip, port, username, password, config)
                    session.tracker = tracker
                    print(f"✅ Tracker multi-objeto creado para {camera_id}")
                except Exception as e:
                    print(f"⚠️ Error creando tracker multi-objeto: {e}")
                    session.tracker = None
            
            # Si no hay tracker multi-objeto, intentar básico
            if not session.tracker and BASIC_PTZ_AVAILABLE:
                try:
                    tracker = PTZCameraONVIF(ip, port, username, password)
                    if tracker.test_connection():
                        session.tracker = tracker
                        print(f"✅ Tracker básico creado para {camera_id}")
                    else:
                        print(f"❌ Conexión PTZ falló para {camera_id}")
                except Exception as e:
                    print(f"❌ Error creando tracker básico: {e}")
            
            self.sessions[camera_id] = session
            
            if session.tracker:
                self.active_sessions.append(camera_id)
                return True
            else:
                print(f"❌ No se pudo crear tracker para {camera_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error creando sesión PTZ: {e}")
            if self.on_error:
                self.on_error(f"Error creando sesión: {e}")
            return False
    
    def start_tracking(self, camera_id: str) -> bool:
        """Iniciar seguimiento para una cámara"""
        if camera_id not in self.sessions:
            print(f"❌ Sesión {camera_id} no encontrada")
            return False
        
        session = self.sessions[camera_id]
        
        try:
            if session.tracker:
                # Iniciar tracking según el tipo de tracker
                if hasattr(session.tracker, 'start_tracking'):
                    # Tracker multi-objeto
                    success = session.tracker.start_tracking()
                    if success:
                        session.active = True
                        print(f"✅ Seguimiento iniciado para {camera_id}")
                        return True
                else:
                    # Tracker básico - asumir que está listo
                    session.active = True
                    print(f"✅ Tracker básico activado para {camera_id}")
                    return True
            
            print(f"❌ No hay tracker disponible para {camera_id}")
            return False
            
        except Exception as e:
            print(f"❌ Error iniciando tracking: {e}")
            if self.on_error:
                self.on_error(f"Error iniciando tracking: {e}")
            return False
    
    def stop_tracking(self, camera_id: str) -> bool:
        """Detener seguimiento para una cámara"""
        if camera_id not in self.sessions:
            return False
        
        session = self.sessions[camera_id]
        
        try:
            if session.tracker and hasattr(session.tracker, 'stop_tracking'):
                session.tracker.stop_tracking()
            
            session.active = False
            if camera_id in self.active_sessions:
                self.active_sessions.remove(camera_id)
            
            print(f"✅ Seguimiento detenido para {camera_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error deteniendo tracking: {e}")
            return False
    
    def update_detections(self, camera_id: str, detections: List[Dict], frame_size: tuple = (1920, 1080)):
        """Actualizar detecciones para una cámara"""
        if camera_id not in self.sessions or not self.sessions[camera_id].active:
            return
        
        session = self.sessions[camera_id]
        
        try:
            # Procesar detecciones según el tipo de tracker
            if session.tracker:
                if hasattr(session.tracker, 'update_detections'):
                    # Tracker multi-objeto
                    session.tracker.update_detections(detections, frame_size)
                    session.detection_count += len(detections)
                elif hasattr(session.tracker, 'track_object_continuous'):
                    # Tracker básico - usar la primera detección
                    if detections:
                        best_detection = max(detections, key=lambda x: x.get('confidence', 0))
                        # Convertir a formato esperado por tracker básico
                        x1 = int(best_detection['x1'])
                        y1 = int(best_detection['y1'])
                        x2 = int(best_detection['x2'])
                        y2 = int(best_detection['y2'])
                        
                        # Ejecutar tracking en hilo separado para no bloquear
                        def track_async():
                            try:
                                session.tracker.track_object_continuous((x1, y1, x2, y2), frame_size)
                            except Exception as e:
                                print(f"Error en tracking básico: {e}")
                        
                        thread = threading.Thread(target=track_async, daemon=True)
                        thread.start()
                        
                        session.detection_count += 1
            
            # Notificar al diálogo si hay callback
            if self.on_detection_processed:
                self.on_detection_processed(camera_id, len(detections))
                
        except Exception as e:
            session.error_count += 1
            print(f"❌ Error procesando detecciones: {e}")
            if self.on_error:
                self.on_error(f"Error procesando detecciones: {e}")
    
    def get_session_status(self, camera_id: str) -> Dict:
        """Obtener estado de una sesión"""
        if camera_id not in self.sessions:
            return {
                'exists': False,
                'active': False,
                'error': 'Sesión no encontrada'
            }
        
        session = self.sessions[camera_id]
        
        status = {
            'exists': True,
            'active': session.active,
            'ip': session.ip,
            'port': session.port,
            'uptime': time.time() - session.start_time,
            'detection_count': session.detection_count,
            'error_count': session.error_count,
            'tracker_type': 'none'
        }
        
        # Determinar tipo de tracker
        if session.tracker:
            if hasattr(session.tracker, 'get_status'):
                status['tracker_type'] = 'multi_object'
                try:
                    tracker_status = session.tracker.get_status()
                    status.update(tracker_status)
                except:
                    pass
            else:
                status['tracker_type'] = 'basic'
        
        session.last_status = status
        return status
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Obtener estado de todas las sesiones"""
        return {cam_id: self.get_session_status(cam_id) for cam_id in self.sessions}
    
    def cleanup(self):
        """Limpiar recursos"""
        print("🧹 Limpiando PTZ Integration Bridge...")
        
        # Detener todas las sesiones
        for camera_id in list(self.sessions.keys()):
            self.stop_tracking(camera_id)
        
        self.sessions.clear()
        self.active_sessions.clear()
        self.running = False
        
        print("✅ PTZ Integration Bridge limpiado")

# === FUNCIONES DE INTEGRACIÓN PARA EL DIÁLOGO ===

def create_ptz_bridge() -> PTZIntegrationBridge:
    """Crear bridge de integración PTZ"""
    return PTZIntegrationBridge()

def create_multi_object_ptz_system(camera_list: List[Dict], parent=None):
    """Función de compatibilidad para enhanced_ptz_multi_object_dialog.py"""
    try:
        # Importar el diálogo principal
        from ui.enhanced_ptz_multi_object_dialog import EnhancedMultiObjectPTZDialog
        
        # Crear diálogo
        dialog = EnhancedMultiObjectPTZDialog(parent, camera_list)
        
        # Crear bridge y conectarlo al diálogo
        bridge = PTZIntegrationBridge()
        
        # Conectar callbacks
        if hasattr(dialog, '_log'):
            bridge.on_status_update = lambda status: dialog._log(f"📊 Status: {status}")
            bridge.on_error = lambda error: dialog._log(f"❌ Error: {error}")
            bridge.on_detection_processed = lambda cam, count: dialog._log(f"🎯 {cam}: {count} detecciones")
        
        # Agregar bridge al diálogo
        dialog.integration_bridge = bridge
        
        return dialog, bridge
        
    except ImportError as e:
        print(f"❌ Error importando diálogo PTZ: {e}")
        return None, None
    except Exception as e:
        print(f"❌ Error creando sistema PTZ: {e}")
        return None, None

# === FUNCIONES DE DIAGNÓSTICO ===

def diagnose_ptz_system(camera_data: Dict = None) -> Dict[str, Any]:
    """Diagnosticar sistema PTZ"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'modules': {},
        'camera': {},
        'recommendations': []
    }
    
    # Verificar módulos
    results['modules']['multi_object'] = MULTI_OBJECT_AVAILABLE
    results['modules']['basic_ptz'] = BASIC_PTZ_AVAILABLE
    results['modules']['onvif'] = ONVIF_AVAILABLE
    
    # Verificar cámara si se proporciona
    if camera_data:
        ip = camera_data.get('ip', '')
        port = camera_data.get('puerto', 80)
        username = camera_data.get('usuario', '')
        password = camera_data.get('password', '')
        
        results['camera']['has_ip'] = bool(ip)
        results['camera']['has_credentials'] = bool(username and password)
        results['camera']['config_complete'] = bool(ip and username and password)
        
        # Intentar conexión si está configurada
        if results['camera']['config_complete'] and ONVIF_AVAILABLE:
            try:
                test_camera = ONVIFCamera(ip, port, username, password)
                results['camera']['connection_test'] = True
            except:
                results['camera']['connection_test'] = False
        else:
            results['camera']['connection_test'] = None
    
    # Generar recomendaciones
    if not ONVIF_AVAILABLE:
        results['recommendations'].append("Instalar librería ONVIF: pip install onvif-zeep")
    
    if not MULTI_OBJECT_AVAILABLE:
        results['recommendations'].append("Verificar archivo core/multi_object_ptz_system.py")
    
    if camera_data and not results['camera']['config_complete']:
        results['recommendations'].append("Completar configuración de cámara PTZ (IP, usuario, contraseña)")
    
    return results

if __name__ == "__main__":
    # Prueba del sistema
    print("🧪 Probando PTZ Integration Bridge...")
    
    bridge = create_ptz_bridge()
    
    # Datos de prueba
    test_camera = {
        'nombre': 'test_camera',
        'ip': '192.168.1.100',
        'puerto': 80,
        'usuario': 'admin',
        'password': 'admin123'
    }
    
    # Diagnóstico
    diagnosis = diagnose_ptz_system(test_camera)
    print(f"📋 Diagnóstico: {json.dumps(diagnosis, indent=2)}")
    
    print("✅ Prueba completada")