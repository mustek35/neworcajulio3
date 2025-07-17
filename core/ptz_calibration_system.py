# core/ptz_calibration_system.py
"""
Sistema de calibración PTZ para corregir problemas de seguimiento
Permite calibrar el centro de imagen y direcciones de movimiento
"""

import time
import json
import os
import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from core.ptz_control import PTZCameraONVIF
    PTZ_AVAILABLE = True
except ImportError:
    PTZ_AVAILABLE = False
    print("⚠️ Sistema PTZ no disponible para calibración")

@dataclass
class CalibrationData:
    """Datos de calibración para una cámara PTZ"""
    camera_ip: str
    center_offset_x: float = 0.0  # Offset del centro en X
    center_offset_y: float = 0.0  # Offset del centro en Y
    pan_direction: int = 1        # 1 = normal, -1 = invertido
    tilt_direction: int = 1       # 1 = normal, -1 = invertido
    pan_sensitivity: float = 0.005
    tilt_sensitivity: float = 0.005
    deadzone_x: float = 0.03
    deadzone_y: float = 0.03
    calibration_date: str = ""
    
    def save_to_file(self, filename: str = None):
        """Guardar calibración a archivo"""
        if not filename:
            filename = f"calibration_{self.camera_ip.replace('.', '_')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(asdict(self), f, indent=4)
            return True
        except Exception as e:
            print(f"❌ Error guardando calibración: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, camera_ip: str, filename: str = None):
        """Cargar calibración desde archivo"""
        if not filename:
            filename = f"calibration_{camera_ip.replace('.', '_')}.json"
        
        if not os.path.exists(filename):
            return cls(camera_ip=camera_ip)
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            print(f"⚠️ Error cargando calibración: {e}")
            return cls(camera_ip=camera_ip)

class PTZCalibrationSystem:
    """Sistema de calibración PTZ para corregir seguimiento"""
    
    def __init__(self):
        self.calibrations: Dict[str, CalibrationData] = {}
        self.current_camera: Optional[PTZCameraONVIF] = None
        self.current_calibration: Optional[CalibrationData] = None
        self.calibration_points: List[Tuple[float, float]] = []
        
    def start_calibration(self, ip: str, port: int, username: str, password: str) -> bool:
        """Iniciar proceso de calibración para una cámara"""
        if not PTZ_AVAILABLE:
            print("❌ Sistema PTZ no disponible")
            return False
        
        try:
            print(f"🔧 Iniciando calibración para cámara {ip}")
            
            # Conectar a la cámara
            self.current_camera = PTZCameraONVIF(ip, port, username, password)
            
            # Cargar calibración existente o crear nueva
            self.current_calibration = CalibrationData.load_from_file(ip)
            self.calibrations[ip] = self.current_calibration
            
            print("✅ Calibración iniciada correctamente")
            return True
            
        except Exception as e:
            print(f"❌ Error iniciando calibración: {e}")
            return False
    
    def test_movement_directions(self) -> Dict[str, str]:
        """Probar direcciones de movimiento para detectar inversiones"""
        if not self.current_camera:
            return {"error": "No hay cámara conectada"}
        
        results = {}
        test_speed = 0.3
        test_duration = 1.0
        
        try:
            print("🧪 Probando direcciones de movimiento...")
            
            # Probar PAN derecha
            print("→ Probando movimiento PAN derecha")
            self.current_camera.continuous_move(test_speed, 0, 0)
            time.sleep(test_duration)
            self.current_camera.stop()
            results["pan_right"] = "Movió hacia la derecha" 
            
            time.sleep(0.5)
            
            # Probar PAN izquierda
            print("← Probando movimiento PAN izquierda")
            self.current_camera.continuous_move(-test_speed, 0, 0)
            time.sleep(test_duration)
            self.current_camera.stop()
            results["pan_left"] = "Movió hacia la izquierda"
            
            time.sleep(0.5)
            
            # Probar TILT arriba
            print("↑ Probando movimiento TILT arriba")
            self.current_camera.continuous_move(0, test_speed, 0)
            time.sleep(test_duration)
            self.current_camera.stop()
            results["tilt_up"] = "Movió hacia arriba"
            
            time.sleep(0.5)
            
            # Probar TILT abajo
            print("↓ Probando movimiento TILT abajo")
            self.current_camera.continuous_move(0, -test_speed, 0)
            time.sleep(test_duration)
            self.current_camera.stop()
            results["tilt_down"] = "Movió hacia abajo"
            
            print("✅ Prueba de direcciones completada")
            return results
            
        except Exception as e:
            print(f"❌ Error probando direcciones: {e}")
            return {"error": str(e)}
    
    def calibrate_center_point(self, detected_box_center: Tuple[float, float], 
                             frame_size: Tuple[int, int]) -> bool:
        """Calibrar punto central basado en detección"""
        if not self.current_calibration:
            return False
        
        frame_w, frame_h = frame_size
        detected_x, detected_y = detected_box_center
        
        # Centro teórico del frame
        theoretical_center_x = frame_w / 2
        theoretical_center_y = frame_h / 2
        
        # Calcular offset
        offset_x = (detected_x - theoretical_center_x) / frame_w
        offset_y = (detected_y - theoretical_center_y) / frame_h
        
        # Actualizar calibración
        self.current_calibration.center_offset_x = offset_x
        self.current_calibration.center_offset_y = offset_y
        self.current_calibration.calibration_date = datetime.now().isoformat()
        
        print(f"🎯 Centro calibrado - Offset: X={offset_x:.4f}, Y={offset_y:.4f}")
        
        # Guardar calibración
        return self.current_calibration.save_to_file()
    
    def add_calibration_point(self, box_center: Tuple[float, float], 
                            frame_size: Tuple[int, int]):
        """Agregar punto de calibración para promedio"""
        frame_w, frame_h = frame_size
        center_x, center_y = box_center
        
        # Normalizar coordenadas
        norm_x = center_x / frame_w
        norm_y = center_y / frame_h
        
        self.calibration_points.append((norm_x, norm_y))
        print(f"📍 Punto agregado: ({norm_x:.3f}, {norm_y:.3f}) - Total: {len(self.calibration_points)}")
    
    def finalize_calibration(self, frame_size: Tuple[int, int]) -> bool:
        """Finalizar calibración usando promedio de puntos"""
        if not self.calibration_points or not self.current_calibration:
            return False
        
        # Calcular centro promedio
        avg_x = sum(p[0] for p in self.calibration_points) / len(self.calibration_points)
        avg_y = sum(p[1] for p in self.calibration_points) / len(self.calibration_points)
        
        # Centro teórico (0.5, 0.5)
        offset_x = avg_x - 0.5
        offset_y = avg_y - 0.5
        
        # Actualizar calibración
        self.current_calibration.center_offset_x = offset_x
        self.current_calibration.center_offset_y = offset_y
        self.current_calibration.calibration_date = datetime.now().isoformat()
        
        print(f"🎯 Calibración finalizada:")
        print(f"   Promedio de {len(self.calibration_points)} puntos")
        print(f"   Centro corregido: X={0.5 + offset_x:.3f}, Y={0.5 + offset_y:.3f}")
        print(f"   Offset: X={offset_x:.4f}, Y={offset_y:.4f}")
        
        # Limpiar puntos
        self.calibration_points.clear()
        
        # Guardar calibración
        return self.current_calibration.save_to_file()
    
    def set_direction_inversion(self, pan_inverted: bool = False, 
                              tilt_inverted: bool = False):
        """Configurar inversión de direcciones"""
        if not self.current_calibration:
            return False
        
        self.current_calibration.pan_direction = -1 if pan_inverted else 1
        self.current_calibration.tilt_direction = -1 if tilt_inverted else 1
        
        print(f"🔄 Direcciones configuradas:")
        print(f"   PAN: {'Invertido' if pan_inverted else 'Normal'}")
        print(f"   TILT: {'Invertido' if tilt_inverted else 'Normal'}")
        
        return self.current_calibration.save_to_file()
    
    def adjust_sensitivity(self, pan_sensitivity: float = None, 
                         tilt_sensitivity: float = None):
        """Ajustar sensibilidad de movimiento"""
        if not self.current_calibration:
            return False
        
        if pan_sensitivity is not None:
            self.current_calibration.pan_sensitivity = pan_sensitivity
        
        if tilt_sensitivity is not None:
            self.current_calibration.tilt_sensitivity = tilt_sensitivity
        
        print(f"🎛️ Sensibilidad ajustada:")
        print(f"   PAN: {self.current_calibration.pan_sensitivity}")
        print(f"   TILT: {self.current_calibration.tilt_sensitivity}")
        
        return self.current_calibration.save_to_file()
    
    def get_calibrated_movement(self, object_center: Tuple[float, float], 
                              frame_size: Tuple[int, int]) -> Tuple[float, float]:
        """Calcular movimiento calibrado para centrar objeto"""
        if not self.current_calibration:
            return (0.0, 0.0)
        
        frame_w, frame_h = frame_size
        obj_x, obj_y = object_center
        
        # Centro corregido del frame
        corrected_center_x = frame_w * (0.5 + self.current_calibration.center_offset_x)
        corrected_center_y = frame_h * (0.5 + self.current_calibration.center_offset_y)
        
        # Calcular diferencia
        dx = obj_x - corrected_center_x
        dy = obj_y - corrected_center_y
        
        # Aplicar deadzone
        if abs(dx) < frame_w * self.current_calibration.deadzone_x:
            dx = 0
        if abs(dy) < frame_h * self.current_calibration.deadzone_y:
            dy = 0
        
        # Calcular velocidades con direcciones y sensibilidad calibradas
        pan_speed = float(np.clip(
            dx * self.current_calibration.pan_sensitivity * self.current_calibration.pan_direction,
            -0.5, 0.5
        ))
        
        tilt_speed = float(np.clip(
            -dy * self.current_calibration.tilt_sensitivity * self.current_calibration.tilt_direction,
            -0.5, 0.5
        ))
        
        return (pan_speed, tilt_speed)

def create_calibration_system() -> PTZCalibrationSystem:
    """Crear nueva instancia del sistema de calibración"""
    return PTZCalibrationSystem()

def get_calibration_for_camera(ip: str) -> Optional[CalibrationData]:
    """Obtener calibración para una cámara específica"""
    return CalibrationData.load_from_file(ip)

# Función mejorada para el seguimiento con calibración
def track_object_calibrated(ip: str, port: int, username: str, password: str, 
                          object_center: Tuple[float, float], 
                          frame_size: Tuple[int, int]) -> bool:
    """Seguimiento de objeto usando calibración"""
    try:
        # Cargar calibración
        calibration = get_calibration_for_camera(ip)
        if not calibration:
            print("⚠️ No hay calibración, usando valores por defecto")
            calibration = CalibrationData(camera_ip=ip)
        
        # Conectar cámara
        cam = PTZCameraONVIF(ip, port, username, password)
        
        # Crear sistema de calibración temporal
        calib_system = PTZCalibrationSystem()
        calib_system.current_calibration = calibration
        
        # Calcular movimiento calibrado
        pan_speed, tilt_speed = calib_system.get_calibrated_movement(
            object_center, frame_size
        )
        
        if pan_speed == 0 and tilt_speed == 0:
            print("📍 Objeto centrado correctamente")
            cam.stop()
            return True
        
        print(f"🎯 Movimiento calibrado: PAN={pan_speed:.3f}, TILT={tilt_speed:.3f}")
        
        # Ejecutar movimiento
        cam.continuous_move(pan_speed, tilt_speed, 0)
        time.sleep(0.3)
        cam.stop()
        
        return True
        
    except Exception as e:
        print(f"❌ Error en seguimiento calibrado: {e}")
        return False

if __name__ == "__main__":
    # Ejemplo de uso
    print("🧪 Sistema de calibración PTZ")
    print("=" * 40)
    
    # Crear sistema
    calib = create_calibration_system()
    
    # Ejemplo de calibración
    print("1. Conectar a cámara")
    print("2. Probar direcciones")
    print("3. Calibrar centro con detecciones")
    print("4. Ajustar sensibilidad")
    print("5. Guardar configuración")