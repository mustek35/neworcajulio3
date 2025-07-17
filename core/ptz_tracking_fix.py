# core/ptz_tracking_fix.py
"""
Correcciones y mejoras para el sistema PTZ multi-objeto
Soluciona problemas comunes de seguimiento y calibración
"""

import time
import json
import threading
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# Importar calibración
try:
    from core.ptz_calibration_system import get_calibration_for_camera, track_object_calibrated
    CALIBRATION_AVAILABLE = True
except ImportError:
    CALIBRATION_AVAILABLE = False

# Importar PTZ básico
try:
    from core.ptz_control import PTZCameraONVIF
    PTZ_BASIC_AVAILABLE = True
except ImportError:
    PTZ_BASIC_AVAILABLE = False

class FixedPTZTracker:
    """Tracker PTZ corregido con mejor manejo de errores"""
    
    def __init__(self, ip: str, port: int, username: str, password: str):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.camera = None
        self.is_connected = False
        self.tracking_active = False
        self.last_movement_time = 0
        self.movement_lock = threading.Lock()
        
        # Estadísticas
        self.successful_moves = 0
        self.failed_moves = 0
        self.total_detections = 0
        
        # Configuración mejorada
        self.config = {
            'min_movement_interval': 0.1,  # Mínimo tiempo entre movimientos
            'max_speed': 0.5,              # Velocidad máxima
            'center_tolerance': 50,        # Tolerancia para considerar centrado
            'use_calibration': True,       # Usar calibración si está disponible
            'debug_mode': True,            # Mostrar información de debug
            'movement_timeout': 5.0,       # Timeout para movimientos
        }
    
    def connect(self) -> bool:
        """Conectar a la cámara PTZ con verificación mejorada"""
        if not PTZ_BASIC_AVAILABLE:
            self._log("❌ Sistema PTZ básico no disponible")
            return False
        
        try:
            self._log(f"🔗 Conectando a {self.ip}:{self.port}...")
            
            # Crear conexión
            self.camera = PTZCameraONVIF(self.ip, self.port, self.username, self.password)
            
            # Verificar conexión con prueba básica
            profiles = self.camera.media.GetProfiles()
            if not profiles:
                self._log("❌ No se encontraron perfiles PTZ")
                return False
            
            # Verificar servicio PTZ
            ptz_service = self.camera.ptz
            if not ptz_service:
                self._log("❌ Servicio PTZ no disponible")
                return False
            
            self.is_connected = True
            self._log(f"✅ Conectado exitosamente ({len(profiles)} perfiles)")
            return True
            
        except Exception as e:
            self._log(f"❌ Error de conexión: {e}")
            self.camera = None
            self.is_connected = False
            return False
    
    def start_tracking(self) -> bool:
        """Iniciar seguimiento con verificaciones"""
        if not self.is_connected:
            if not self.connect():
                return False
        
        self.tracking_active = True
        self.successful_moves = 0
        self.failed_moves = 0
        self.total_detections = 0
        
        self._log("🎯 Seguimiento iniciado")
        return True
    
    def stop_tracking(self):
        """Detener seguimiento"""
        self.tracking_active = False
        
        # Detener movimiento actual
        if self.camera:
            try:
                self.camera.stop()
                self._log("⏹️ Movimiento detenido")
            except:
                pass
        
        self._log("🛑 Seguimiento detenido")
        self._log(f"📊 Estadísticas: {self.successful_moves} exitosos, {self.failed_moves} fallidos")
    
    def track_object(self, detection: Dict, frame_size: Tuple[int, int]) -> bool:
        """Seguir un objeto detectado con mejoras"""
        if not self.tracking_active or not self.is_connected:
            return False
        
        self.total_detections += 1
        
        try:
            # Extraer información de la detección
            bbox = detection.get('bbox', [])
            confidence = detection.get('confidence', 0.0)
            class_name = detection.get('class', 'unknown')
            
            if len(bbox) != 4:
                self._log(f"❌ Bbox inválido: {bbox}")
                return False
            
            x1, y1, x2, y2 = bbox
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            frame_w, frame_h = frame_size
            
            self._log(f"🎯 Rastreando {class_name} (conf: {confidence:.2f}) en ({center_x:.0f}, {center_y:.0f})")
            
            # Verificar si necesita movimiento
            if self._is_centered(center_x, center_y, frame_w, frame_h):
                self._log("📍 Objeto ya está centrado")
                return True
            
            # Verificar intervalo mínimo entre movimientos
            current_time = time.time()
            if current_time - self.last_movement_time < self.config['min_movement_interval']:
                return False
            
            # Ejecutar movimiento
            success = self._execute_movement(center_x, center_y, frame_w, frame_h)
            
            if success:
                self.successful_moves += 1
                self.last_movement_time = current_time
            else:
                self.failed_moves += 1
            
            return success
            
        except Exception as e:
            self._log(f"❌ Error en seguimiento: {e}")
            self.failed_moves += 1
            return False
    
    def _execute_movement(self, center_x: float, center_y: float, 
                         frame_w: int, frame_h: int) -> bool:
        """Ejecutar movimiento PTZ con diferentes métodos"""
        
        # Método 1: Usar calibración si está disponible
        if self.config['use_calibration'] and CALIBRATION_AVAILABLE:
            try:
                success = track_object_calibrated(
                    self.ip, self.port, self.username, self.password,
                    (center_x, center_y), (frame_w, frame_h)
                )
                if success:
                    self._log("✅ Movimiento calibrado exitoso")
                    return True
                else:
                    self._log("⚠️ Movimiento calibrado falló, probando método básico")
            except Exception as e:
                self._log(f"⚠️ Error en calibración: {e}, usando método básico")
        
        # Método 2: Cálculo básico mejorado
        return self._basic_movement(center_x, center_y, frame_w, frame_h)
    
    def _basic_movement(self, center_x: float, center_y: float, 
                       frame_w: int, frame_h: int) -> bool:
        """Movimiento PTZ básico mejorado"""
        
        with self.movement_lock:
            try:
                # Calcular centro del frame
                frame_center_x = frame_w / 2
                frame_center_y = frame_h / 2
                
                # Calcular diferencias
                dx = center_x - frame_center_x
                dy = center_y - frame_center_y
                
                # Normalizar a rango -1 a 1
                norm_dx = dx / (frame_w / 2)
                norm_dy = dy / (frame_h / 2)
                
                # Aplicar zona muerta
                deadzone = 0.1
                if abs(norm_dx) < deadzone:
                    norm_dx = 0
                if abs(norm_dy) < deadzone:
                    norm_dy = 0
                
                # Calcular velocidades
                max_speed = self.config['max_speed']
                pan_speed = float(np.clip(norm_dx * 0.5, -max_speed, max_speed))
                tilt_speed = float(np.clip(-norm_dy * 0.5, -max_speed, max_speed))  # Negativo para arriba
                
                if pan_speed == 0 and tilt_speed == 0:
                    self._log("📍 Objeto centrado (zona muerta)")
                    return True
                
                self._log(f"🎯 Movimiento: PAN={pan_speed:.3f}, TILT={tilt_speed:.3f}")
                
                # Ejecutar movimiento
                self.camera.continuous_move(pan_speed, tilt_speed, 0)
                
                # Movimiento por tiempo corto
                time.sleep(0.2)
                self.camera.stop()
                
                return True
                
            except Exception as e:
                self._log(f"❌ Error en movimiento básico: {e}")
                return False
    
    def _is_centered(self, obj_x: float, obj_y: float, frame_w: int, frame_h: int) -> bool:
        """Verificar si el objeto está centrado"""
        center_x = frame_w / 2
        center_y = frame_h / 2
        
        tolerance = self.config['center_tolerance']
        
        dx = abs(obj_x - center_x)
        dy = abs(obj_y - center_y)
        
        return dx < tolerance and dy < tolerance
    
    def _log(self, message: str):
        """Log con timestamp"""
        if self.config['debug_mode']:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] PTZ {self.ip}: {message}")
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado del tracker"""
        return {
            'connected': self.is_connected,
            'tracking_active': self.tracking_active,
            'successful_moves': self.successful_moves,
            'failed_moves': self.failed_moves,
            'total_detections': self.total_detections,
            'success_rate': (self.successful_moves / max(1, self.total_detections)) * 100,
            'ip': self.ip
        }

class FixedMultiObjectTracker:
    """Tracker multi-objeto corregido"""
    
    def __init__(self, camera_data: Dict):
        self.camera_data = camera_data
        self.tracker = None
        self.active_objects = {}
        self.current_target = None
        self.last_switch_time = 0
        self.switch_interval = 5.0  # Cambiar objetivo cada 5 segundos
        
        # Configuración
        self.config = {
            'min_confidence': 0.5,
            'max_objects': 3,
            'switch_interval': 5.0,
            'priority_weights': {
                'confidence': 0.4,
                'size': 0.3,
                'movement': 0.2,
                'center_proximity': 0.1
            }
        }
    
    def initialize(self) -> bool:
        """Inicializar tracker multi-objeto"""
        try:
            ip = self.camera_data.get('ip')
            port = self.camera_data.get('puerto', 80)
            username = self.camera_data.get('usuario')
            password = self.camera_data.get('contrasena')
            
            # Crear tracker corregido
            self.tracker = FixedPTZTracker(ip, port, username, password)
            
            # Conectar
            if self.tracker.connect():
                self._log("✅ Tracker multi-objeto inicializado")
                return True
            else:
                self._log("❌ Error inicializando tracker")
                return False
                
        except Exception as e:
            self._log(f"❌ Error en inicialización: {e}")
            return False
    
    def start_tracking(self) -> bool:
        """Iniciar seguimiento multi-objeto"""
        if not self.tracker:
            if not self.initialize():
                return False
        
        success = self.tracker.start_tracking()
        if success:
            self.active_objects.clear()
            self.current_target = None
            self.last_switch_time = time.time()
            self._log("🚀 Seguimiento multi-objeto iniciado")
        
        return success
    
    def stop_tracking(self):
        """Detener seguimiento multi-objeto"""
        if self.tracker:
            self.tracker.stop_tracking()
        
        self.active_objects.clear()
        self.current_target = None
        self._log("🛑 Seguimiento multi-objeto detenido")
    
    def update_tracking(self, detections: List[Dict], frame_size: Tuple[int, int]) -> bool:
        """Actualizar seguimiento con múltiples detecciones"""
        if not self.tracker or not self.tracker.tracking_active:
            return False
        
        try:
            # Filtrar detecciones válidas
            valid_detections = self._filter_detections(detections)
            
            if not valid_detections:
                self._log("⚠️ No hay detecciones válidas")
                return False
            
            # Actualizar objetos activos
            self._update_active_objects(valid_detections)
            
            # Seleccionar objetivo actual
            target_detection = self._select_target()
            
            if target_detection:
                # Ejecutar seguimiento
                success = self.tracker.track_object(target_detection, frame_size)
                
                if success:
                    self._log(f"✅ Siguiendo {target_detection.get('class', 'objeto')} "
                             f"(conf: {target_detection.get('confidence', 0):.2f})")
                else:
                    self._log("❌ Error en seguimiento")
                
                return success
            else:
                self._log("⚠️ No hay objetivo válido")
                return False
                
        except Exception as e:
            self._log(f"❌ Error en actualización: {e}")
            return False
    
    def _filter_detections(self, detections: List[Dict]) -> List[Dict]:
        """Filtrar detecciones válidas"""
        filtered = []
        
        for detection in detections:
            # Verificar confianza mínima
            confidence = detection.get('confidence', 0)
            if confidence < self.config['min_confidence']:
                continue
            
            # Verificar bbox válido
            bbox = detection.get('bbox', [])
            if len(bbox) != 4:
                continue
            
            x1, y1, x2, y2 = bbox
            if x2 <= x1 or y2 <= y1:
                continue
            
            # Verificar tamaño mínimo
            width = x2 - x1
            height = y2 - y1
            if width < 10 or height < 10:
                continue
            
            filtered.append(detection)
        
        return filtered[:self.config['max_objects']]
    
    def _update_active_objects(self, detections: List[Dict]):
        """Actualizar lista de objetos activos"""
        current_time = time.time()
        
        # Limpiar objetos antiguos
        self.active_objects = {k: v for k, v in self.active_objects.items() 
                              if current_time - v.get('last_seen', 0) < 3.0}
        
        # Agregar/actualizar objetos actuales
        for i, detection in enumerate(detections):
            obj_id = f"obj_{i}"
            
            bbox = detection['bbox']
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            
            self.active_objects[obj_id] = {
                'detection': detection,
                'center': (center_x, center_y),
                'last_seen': current_time,
                'confidence': detection.get('confidence', 0),
                'class': detection.get('class', 'unknown')
            }
    
    def _select_target(self) -> Optional[Dict]:
        """Seleccionar objetivo basado en prioridades"""
        if not self.active_objects:
            return None
        
        current_time = time.time()
        
        # Verificar si es tiempo de cambiar objetivo
        should_switch = (
            self.current_target is None or
            self.current_target not in self.active_objects or
            current_time - self.last_switch_time > self.config['switch_interval']
        )
        
        if should_switch:
            # Calcular prioridades
            priorities = {}
            for obj_id, obj_data in self.active_objects.items():
                priority = self._calculate_priority(obj_data)
                priorities[obj_id] = priority
            
            # Seleccionar el de mayor prioridad
            if priorities:
                self.current_target = max(priorities, key=priorities.get)
                self.last_switch_time = current_time
                
                target_class = self.active_objects[self.current_target]['class']
                self._log(f"🎯 Nuevo objetivo: {target_class} (prioridad: {priorities[self.current_target]:.2f})")
        
        # Retornar detección del objetivo actual
        if self.current_target and self.current_target in self.active_objects:
            return self.active_objects[self.current_target]['detection']
        
        return None
    
    def _calculate_priority(self, obj_data: Dict) -> float:
        """Calcular prioridad de un objeto"""
        weights = self.config['priority_weights']
        
        # Factor confianza
        confidence_factor = obj_data['confidence']
        
        # Factor tamaño (objetos más grandes tienen mayor prioridad)
        bbox = obj_data['detection']['bbox']
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        size_factor = min(area / 50000, 1.0)  # Normalizar
        
        # Factor movimiento (simplificado - usar confianza como proxy)
        movement_factor = confidence_factor
        
        # Factor proximidad al centro (objetos cerca del centro tienen menor prioridad)
        center_x, center_y = obj_data['center']
        frame_center_dist = ((center_x - 960)**2 + (center_y - 540)**2)**0.5
        proximity_factor = 1.0 - min(frame_center_dist / 1000, 1.0)
        
        # Calcular prioridad total
        priority = (
            weights['confidence'] * confidence_factor +
            weights['size'] * size_factor +
            weights['movement'] * movement_factor +
            weights['center_proximity'] * proximity_factor
        )
        
        return priority
    
    def _log(self, message: str):
        """Log con identificación"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        ip = self.camera_data.get('ip', 'unknown')
        print(f"[{timestamp}] MultiTracker {ip}: {message}")
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado del sistema"""
        status = {
            'active_objects': len(self.active_objects),
            'current_target': self.current_target,
            'camera_ip': self.camera_data.get('ip'),
        }
        
        if self.tracker:
            status.update(self.tracker.get_status())
        
        return status

# Funciones de utilidad para integración
def create_fixed_tracker(camera_data: Dict) -> FixedMultiObjectTracker:
    """Crear tracker multi-objeto corregido"""
    return FixedMultiObjectTracker(camera_data)

def test_ptz_connection(camera_data: Dict) -> Dict[str, Any]:
    """Probar conexión PTZ básica"""
    result = {
        'success': False,
        'message': '',
        'details': {}
    }
    
    try:
        tracker = FixedPTZTracker(
            camera_data.get('ip'),
            camera_data.get('puerto', 80),
            camera_data.get('usuario'),
            camera_data.get('contrasena')
        )
        
        if tracker.connect():
            result['success'] = True
            result['message'] = 'Conexión PTZ exitosa'
            result['details'] = tracker.get_status()
        else:
            result['message'] = 'Error conectando a PTZ'
        
        tracker.stop_tracking()
        
    except Exception as e:
        result['message'] = f'Error de conexión: {e}'
    
    return result

def run_movement_test(camera_data: Dict) -> bool:
    """Ejecutar prueba básica de movimiento"""
    try:
        tracker = FixedPTZTracker(
            camera_data.get('ip'),
            camera_data.get('puerto', 80),
            camera_data.get('usuario'),
            camera_data.get('contrasena')
        )
        
        if not tracker.connect():
            print("❌ No se pudo conectar para prueba")
            return False
        
        print("🧪 Ejecutando prueba de movimiento...")
        
        # Simular detección en esquina
        fake_detection = {
            'bbox': [100, 100, 200, 200],
            'confidence': 0.8,
            'class': 'test_object'
        }
        
        frame_size = (1920, 1080)
        
        # Probar seguimiento
        success = tracker.track_object(fake_detection, frame_size)
        
        # Limpiar
        tracker.stop_tracking()
        
        if success:
            print("✅ Prueba de movimiento exitosa")
        else:
            print("❌ Prueba de movimiento falló")
        
        return success
        
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
        return False

# Función principal de reparación
def apply_tracking_fixes(camera_data: Dict) -> Dict[str, Any]:
    """Aplicar todas las correcciones disponibles"""
    fixes_applied = {
        'connection_test': False,
        'movement_test': False,
        'calibration_check': False,
        'config_validation': False
    }
    
    print("🔧 Aplicando correcciones PTZ...")
    
    # 1. Probar conexión básica
    print("\n1. Probando conexión PTZ...")
    connection_result = test_ptz_connection(camera_data)
    fixes_applied['connection_test'] = connection_result['success']
    
    if connection_result['success']:
        print("✅ Conexión PTZ OK")
        
        # 2. Probar movimiento básico
        print("\n2. Probando movimiento básico...")
        movement_ok = run_movement_test(camera_data)
        fixes_applied['movement_test'] = movement_ok
        
        # 3. Verificar calibración
        print("\n3. Verificando calibración...")
        if CALIBRATION_AVAILABLE:
            calibration = get_calibration_for_camera(camera_data.get('ip'))
            if calibration and calibration.calibration_date:
                print(f"✅ Calibración disponible: {calibration.calibration_date[:10]}")
                fixes_applied['calibration_check'] = True
            else:
                print("⚠️ Sin calibración - se recomienda calibrar")
        
        # 4. Validar configuración
        print("\n4. Validando configuración...")
        required_fields = ['ip', 'tipo', 'usuario', 'contrasena']
        missing = [f for f in required_fields if not camera_data.get(f)]
        
        if not missing and camera_data.get('tipo', '').lower() == 'ptz':
            print("✅ Configuración válida")
            fixes_applied['config_validation'] = True
        else:
            print(f"❌ Configuración incompleta: {missing}")
    
    else:
        print(f"❌ Conexión falló: {connection_result['message']}")
    
    return fixes_applied

if __name__ == "__main__":
    # Ejemplo de uso
    print("🧪 Sistema de Corrección PTZ Multi-Objeto")
    print("=" * 50)
    
    # Datos de prueba
    test_camera = {
        'ip': '192.168.1.100',
        'puerto': 80,
        'usuario': 'admin',
        'contrasena': 'admin123',
        'tipo': 'ptz'
    }
    
    # Aplicar correcciones
    fixes = apply_tracking_fixes(test_camera)
    
    print(f"\n📊 Resumen de correcciones:")
    for fix, status in fixes.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {fix}")
    
    # Probar tracker corregido
    if fixes['connection_test']:
        print(f"\n🚀 Probando tracker multi-objeto corregido...")
        tracker = create_fixed_tracker(test_camera)
        
        if tracker.initialize():
            print("✅ Tracker inicializado correctamente")
            
            # Simular detecciones múltiples
            detections = [
                {
                    'bbox': [400, 300, 500, 400],
                    'confidence': 0.85,
                    'class': 'person'
                },
                {
                    'bbox': [800, 200, 900, 350],
                    'confidence': 0.75,
                    'class': 'vehicle'
                }
            ]
            
            if tracker.start_tracking():
                print("✅ Seguimiento iniciado")
                
                # Simular actualización
                success = tracker.update_tracking(detections, (1920, 1080))
                print(f"Resultado seguimiento: {'✅' if success else '❌'}")
                
                # Mostrar estado
                status = tracker.get_status()
                print(f"Estado: {status}")
                
                tracker.stop_tracking()
            else:
                print("❌ No se pudo iniciar seguimiento")
        else:
            print("❌ No se pudo inicializar tracker")