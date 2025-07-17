# core/ptz_control_enhanced.py
import time
import numpy as np
import json
import os
from datetime import datetime
from onvif import ONVIFCamera
from typing import Optional, Dict, Any, Tuple

class PTZCameraEnhanced:
    """Clase mejorada para control PTZ con funcionalidades avanzadas"""
    
    def __init__(self, ip: str, puerto: int, usuario: str, contrasena: str):
        """
        Inicializa la cámara PTZ con configuración mejorada
        
        Args:
            ip: Dirección IP de la cámara
            puerto: Puerto de conexión
            usuario: Usuario para autenticación
            contrasena: Contraseña para autenticación
        """
        self.ip = ip
        self.puerto = puerto
        self.usuario = usuario
        self.contrasena = contrasena
        
        # Estado interno
        self.last_position = {"pan": 0.0, "tilt": 0.0, "zoom": 0.0}
        self.move_history = []
        self.connection_attempts = 0
        self.max_retries = 3
        self.connected = False
        
        # Configuración
        self.default_speed = 0.5
        self.move_timeout = 30.0
        self.position_tolerance = 0.01
        
        # Inicializar conexión
        self._initialize_connection()
        
    def _initialize_connection(self):
        """Inicializa la conexión ONVIF"""
        try:
            self.cam = ONVIFCamera(self.ip, self.puerto, self.usuario, self.contrasena)
            self.media = self.cam.create_media_service()
            self.ptz = self.cam.create_ptz_service()
            
            # Obtener profiles disponibles
            self.profiles = self.media.GetProfiles()
            if not self.profiles:
                raise Exception("No se encontraron profiles en la cámara")
                
            # Usar el primer profile por defecto
            self.profile_token = self.profiles[0].token
            
            # Verificar capacidades PTZ
            self._check_ptz_capabilities()
            self._check_absolute_move_support()

            self.connection_attempts = 0
            self.connected = True
            print(f"✅ Conexión PTZ establecida: {self.ip}:{self.puerto}")

        except Exception as e:
            self.connection_attempts += 1
            self.connected = False
            raise Exception(f"Error conectando a PTZ {self.ip}: {e}")
    
    def _check_ptz_capabilities(self):
        """Verifica las capacidades PTZ de la cámara"""
        try:
            # Intentar obtener configuración PTZ
            self.ptz_config = self.ptz.GetConfiguration({'ConfigurationToken': self.profile_token})
            
            # Verificar límites de movimiento
            if hasattr(self.ptz_config, 'PanTiltLimits'):
                self.pan_limits = self.ptz_config.PanTiltLimits
            else:
                self.pan_limits = None
                
            if hasattr(self.ptz_config, 'ZoomLimits'):
                self.zoom_limits = self.ptz_config.ZoomLimits
            else:
                self.zoom_limits = None
                
            print(f"✅ Capacidades PTZ verificadas para {self.ip}")
            
        except Exception as e:
            print(f"⚠️ No se pudieron verificar capacidades PTZ: {e}")
            self.ptz_config = None
            self.pan_limits = None
            self.zoom_limits = None

    def _check_absolute_move_support(self) -> bool:
        """Verificar si la cámara soporta AbsoluteMove"""
        try:
            ptz_config = self.ptz.GetConfiguration({'ConfigurationToken': self.profile_token})
            if hasattr(ptz_config, 'PanTiltLimits'):
                print(f"✅ AbsoluteMove soportado para {self.ip}")
                return True
            else:
                print(f"⚠️ AbsoluteMove limitado para {self.ip}")
                return False
        except Exception as e:
            print(f"⚠️ Error verificando AbsoluteMove para {self.ip}: {e}")
            return False

    def goto_preset(self, preset_token: str, speed: Optional[float] = None) -> bool:
        """
        Mueve la cámara a un preset específico
        
        Args:
            preset_token: Token del preset
            speed: Velocidad de movimiento (opcional)
            
        Returns:
            bool: True si el movimiento fue exitoso
        """
        try:
            req = self.ptz.create_type('GotoPreset')
            req.ProfileToken = self.profile_token
            req.PresetToken = str(preset_token)
            
            if speed is not None:
                req.Speed = {
                    'PanTilt': {'x': speed, 'y': speed},
                    'Zoom': {'x': speed}
                }
            
            self.ptz.GotoPreset(req)
            
            # Registrar movimiento
            self._log_movement("goto_preset", {"preset": preset_token, "speed": speed})
            
            print(f"✅ PTZ {self.ip} movido a preset {preset_token}")
            return True
            
        except Exception as e:
            print(f"❌ Error moviendo a preset {preset_token}: {e}")
            return False

    def continuous_move(self, pan_speed: float, tilt_speed: float, zoom_speed: float = 0.0, duration: Optional[float] = None) -> bool:
        """
        Movimiento continuo de la cámara
        
        Args:
            pan_speed: Velocidad de pan (-1.0 a 1.0)
            tilt_speed: Velocidad de tilt (-1.0 a 1.0) 
            zoom_speed: Velocidad de zoom (-1.0 a 1.0)
            duration: Duración en segundos (opcional)
            
        Returns:
            bool: True si el comando fue exitoso
        """
        try:
            # Validar velocidades
            pan_speed = max(-1.0, min(1.0, pan_speed))
            tilt_speed = max(-1.0, min(1.0, tilt_speed))
            zoom_speed = max(-1.0, min(1.0, zoom_speed))
            
            req = self.ptz.create_type('ContinuousMove')
            req.ProfileToken = self.profile_token
            req.Velocity = {
                'PanTilt': {'x': pan_speed, 'y': tilt_speed},
                'Zoom': {'x': zoom_speed}
            }
            
            if duration is not None:
                req.Timeout = f"PT{duration}S"
            
            self.ptz.ContinuousMove(req)
            
            # Registrar movimiento
            self._log_movement("continuous_move", {
                "pan_speed": pan_speed,
                "tilt_speed": tilt_speed, 
                "zoom_speed": zoom_speed,
                "duration": duration
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error en movimiento continuo: {e}")
            return False

    def absolute_move(self, pan: float, tilt: float, zoom: Optional[float] = None, speed: float = 0.5) -> bool:
        """
        Movimiento absoluto a una posición específica

        Args:
            pan: Posición de pan (-1.0 a 1.0)
            tilt: Posición de tilt (-1.0 a 1.0)
            zoom: Posición de zoom (0.0 a 1.0) opcional
            speed: Velocidad de movimiento (0.1 a 1.0)
            
        Returns:
            bool: True si el comando fue exitoso
        """
        if not self.connected or not self.ptz:
            print(f"❌ PTZ no conectado: {self.ip}")
            return False

        try:
            # Validar posiciones
            pan = max(-1.0, min(1.0, pan))
            tilt = max(-1.0, min(1.0, tilt))

            req = self.ptz.create_type('AbsoluteMove')
            req.ProfileToken = self.profile_token
            req.Position = {
                'PanTilt': {'x': pan, 'y': tilt}
            }

            if zoom is not None:
                zoom = max(0.0, min(1.0, zoom))
                req.Position['Zoom'] = {'x': zoom}

            req.Speed = {
                'PanTilt': {
                    'x': max(0.1, min(1.0, speed)),
                    'y': max(0.1, min(1.0, speed))
                }
            }

            if zoom is not None:
                req.Speed['Zoom'] = {'x': max(0.1, min(1.0, speed))}

            self.ptz.AbsoluteMove(req)
            
            # Actualizar posición conocida
            self.last_position = {"pan": pan, "tilt": tilt, "zoom": zoom}
            
            # Registrar movimiento
            self._log_movement("absolute_move", {
                "pan": pan, "tilt": tilt, "zoom": zoom, "speed": speed
            })
            
            print(f"✅ AbsoluteMove ejecutado - Pan: {pan:.3f}, Tilt: {tilt:.3f}")
            if zoom is not None:
                print(f"   Zoom: {zoom:.3f}")

            return True

        except Exception as e:
            print(f"❌ Error en AbsoluteMove para {self.ip}: {e}")
            return False

    def relative_move(self, pan_delta: float, tilt_delta: float, zoom_delta: float, speed: Optional[float] = None) -> bool:
        """
        Movimiento relativo desde la posición actual
        
        Args:
            pan_delta: Cambio en pan
            tilt_delta: Cambio en tilt
            zoom_delta: Cambio en zoom
            speed: Velocidad de movimiento
            
        Returns:
            bool: True si el comando fue exitoso
        """
        try:
            req = self.ptz.create_type('RelativeMove')
            req.ProfileToken = self.profile_token
            req.Translation = {
                'PanTilt': {'x': pan_delta, 'y': tilt_delta},
                'Zoom': {'x': zoom_delta}
            }
            
            if speed is not None:
                req.Speed = {
                    'PanTilt': {'x': speed, 'y': speed},
                    'Zoom': {'x': speed}
                }
            
            self.ptz.RelativeMove(req)
            
            # Registrar movimiento
            self._log_movement("relative_move", {
                "pan_delta": pan_delta,
                "tilt_delta": tilt_delta,
                "zoom_delta": zoom_delta,
                "speed": speed
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error en movimiento relativo: {e}")
            return False

    def stop(self, stop_pan_tilt: bool = True, stop_zoom: bool = True) -> bool:
        """
        Detiene el movimiento PTZ
        
        Args:
            stop_pan_tilt: Detener movimiento pan/tilt
            stop_zoom: Detener movimiento de zoom
            
        Returns:
            bool: True si el comando fue exitoso
        """
        try:
            req = self.ptz.create_type('Stop')
            req.ProfileToken = self.profile_token
            req.PanTilt = stop_pan_tilt
            req.Zoom = stop_zoom
            
            self.ptz.Stop(req)
            
            # Registrar parada
            self._log_movement("stop", {"pan_tilt": stop_pan_tilt, "zoom": stop_zoom})
            
            return True
            
        except Exception as e:
            print(f"❌ Error deteniendo movimiento: {e}")
            return False

    def get_position(self) -> Optional[Dict[str, float]]:
        """
        Obtiene la posición actual de la cámara

        Returns:
            Dict con posición actual o None si hay error
        """
        if not self.connected or not self.ptz:
            return None

        try:
            req = self.ptz.create_type('GetStatus')
            req.ProfileToken = self.profile_token
            
            status = self.ptz.GetStatus(req)
            
            if hasattr(status, 'Position'):
                position = {
                    "pan": status.Position.PanTilt.x,
                    "tilt": status.Position.PanTilt.y,
                    "zoom": status.Position.Zoom.x
                }
                
                # Actualizar posición conocida
                self.last_position = position.copy()
                
                return position
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error obteniendo posición: {e}")
            return None

    def get_presets(self) -> Optional[Dict[str, str]]:
        """
        Obtiene la lista de presets disponibles
        
        Returns:
            Dict con presets {token: name} o None si hay error
        """
        try:
            req = self.ptz.create_type('GetPresets')
            req.ProfileToken = self.profile_token
            
            presets_response = self.ptz.GetPresets(req)
            
            presets = {}
            if hasattr(presets_response, 'Preset'):
                for preset in presets_response.Preset:
                    token = preset.token
                    name = preset.Name if hasattr(preset, 'Name') else f"Preset {token}"
                    presets[token] = name
            
            return presets
            
        except Exception as e:
            print(f"❌ Error obteniendo presets: {e}")
            return None

    def set_preset(self, preset_token: str, preset_name: Optional[str] = None) -> bool:
        """
        Establece un preset en la posición actual
        
        Args:
            preset_token: Token del preset
            preset_name: Nombre del preset (opcional)
            
        Returns:
            bool: True si fue exitoso
        """
        try:
            req = self.ptz.create_type('SetPreset')
            req.ProfileToken = self.profile_token
            req.PresetToken = preset_token
            
            if preset_name:
                req.PresetName = preset_name
            
            self.ptz.SetPreset(req)
            
            # Registrar creación de preset
            self._log_movement("set_preset", {"preset": preset_token, "name": preset_name})
            
            print(f"✅ Preset {preset_token} establecido en {self.ip}")
            return True
            
        except Exception as e:
            print(f"❌ Error estableciendo preset {preset_token}: {e}")
            return False

    def remove_preset(self, preset_token: str) -> bool:
        """
        Elimina un preset
        
        Args:
            preset_token: Token del preset a eliminar
            
        Returns:
            bool: True si fue exitoso
        """
        try:
            req = self.ptz.create_type('RemovePreset')
            req.ProfileToken = self.profile_token
            req.PresetToken = preset_token
            
            self.ptz.RemovePreset(req)
            
            # Registrar eliminación
            self._log_movement("remove_preset", {"preset": preset_token})
            
            print(f"✅ Preset {preset_token} eliminado de {self.ip}")
            return True
            
        except Exception as e:
            print(f"❌ Error eliminando preset {preset_token}: {e}")
            return False

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado completo de la cámara PTZ
        
        Returns:
            Dict con información de estado o None si hay error
        """
        try:
            req = self.ptz.create_type('GetStatus')
            req.ProfileToken = self.profile_token
            
            status = self.ptz.GetStatus(req)
            
            result = {
                "position": None,
                "move_status": None,
                "error": None,
                "utc_time": None
            }
            
            if hasattr(status, 'Position'):
                result["position"] = {
                    "pan": status.Position.PanTilt.x,
                    "tilt": status.Position.PanTilt.y,
                    "zoom": status.Position.Zoom.x
                }
            
            if hasattr(status, 'MoveStatus'):
                result["move_status"] = {
                    "pan_tilt": status.MoveStatus.PanTilt,
                    "zoom": status.MoveStatus.Zoom
                }
            
            if hasattr(status, 'Error'):
                result["error"] = status.Error
                
            if hasattr(status, 'UtcTime'):
                result["utc_time"] = status.UtcTime
            
            return result
            
        except Exception as e:
            print(f"❌ Error obteniendo estado: {e}")
            return None

    def move_to_position_smooth(self, target_pan: float, target_tilt: float, target_zoom: float, 
                               steps: int = 10, delay: float = 0.1) -> bool:
        """
        Movimiento suave a una posición específica mediante pasos intermedios
        
        Args:
            target_pan: Posición objetivo de pan
            target_tilt: Posición objetivo de tilt
            target_zoom: Posición objetivo de zoom
            steps: Número de pasos intermedios
            delay: Retardo entre pasos (segundos)
            
        Returns:
            bool: True si fue exitoso
        """
        try:
            # Obtener posición actual
            current_pos = self.get_position()
            if not current_pos:
                # Si no podemos obtener la posición, usar la última conocida
                current_pos = self.last_position
            
            # Calcular pasos intermedios
            pan_step = (target_pan - current_pos["pan"]) / steps
            tilt_step = (target_tilt - current_pos["tilt"]) / steps
            zoom_step = (target_zoom - current_pos["zoom"]) / steps
            
            # Ejecutar movimiento paso a paso
            for i in range(steps):
                intermediate_pan = current_pos["pan"] + (pan_step * (i + 1))
                intermediate_tilt = current_pos["tilt"] + (tilt_step * (i + 1))
                intermediate_zoom = current_pos["zoom"] + (zoom_step * (i + 1))
                
                success = self.absolute_move(intermediate_pan, intermediate_tilt, intermediate_zoom, 0.3)
                if not success:
                    return False
                    
                time.sleep(delay)
            
            print(f"✅ Movimiento suave completado a ({target_pan:.2f}, {target_tilt:.2f}, {target_zoom:.2f})")
            return True
            
        except Exception as e:
            print(f"❌ Error en movimiento suave: {e}")
            return False

    def patrol_between_presets(self, preset_list: list, hold_time: float = 5.0, cycles: int = 1) -> bool:
        """
        Patrulla entre una lista de presets
        
        Args:
            preset_list: Lista de tokens de presets
            hold_time: Tiempo de espera en cada preset (segundos)
            cycles: Número de ciclos de patrulla
            
        Returns:
            bool: True si fue exitoso
        """
        try:
            if len(preset_list) < 2:
                print("❌ Se necesitan al menos 2 presets para patrullar")
                return False
            
            for cycle in range(cycles):
                print(f"🚶 Iniciando ciclo de patrulla {cycle + 1}/{cycles}")
                
                for preset in preset_list:
                    success = self.goto_preset(preset)
                    if not success:
                        print(f"❌ Error yendo a preset {preset}, deteniendo patrulla")
                        return False
                    
                    print(f"📍 En preset {preset}, esperando {hold_time}s")
                    time.sleep(hold_time)
            
            print(f"✅ Patrulla completada: {cycles} ciclos entre {len(preset_list)} presets")
            return True
            
        except Exception as e:
            print(f"❌ Error en patrulla: {e}")
            return False

    def calibrate_limits(self) -> Dict[str, Any]:
        """
        Calibra los límites de movimiento de la cámara
        
        Returns:
            Dict con información de límites
        """
        try:
            print("🔧 Iniciando calibración de límites PTZ...")
            
            # Obtener posición inicial
            initial_pos = self.get_position()
            if not initial_pos:
                initial_pos = {"pan": 0.0, "tilt": 0.0, "zoom": 0.0}
            
            limits = {
                "pan_min": -1.0, "pan_max": 1.0,
                "tilt_min": -1.0, "tilt_max": 1.0,
                "zoom_min": 0.0, "zoom_max": 1.0,
                "initial_position": initial_pos,
                "calibration_time": datetime.now().isoformat()
            }
            
            # Si tenemos límites del dispositivo, usarlos
            if self.pan_limits:
                limits.update({
                    "pan_min": self.pan_limits.Range.XRange.Min,
                    "pan_max": self.pan_limits.Range.XRange.Max,
                    "tilt_min": self.pan_limits.Range.YRange.Min,
                    "tilt_max": self.pan_limits.Range.YRange.Max
                })
            
            if self.zoom_limits:
                limits.update({
                    "zoom_min": self.zoom_limits.Range.XRange.Min,
                    "zoom_max": self.zoom_limits.Range.XRange.Max
                })
            
            # Guardar límites
            self._save_calibration_data(limits)
            
            print("✅ Calibración de límites completada")
            return limits
            
        except Exception as e:
            print(f"❌ Error en calibración: {e}")
            return {}

    def _log_movement(self, action: str, params: Dict[str, Any]):
        """Registra un movimiento en el historial"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "params": params,
            "camera_ip": self.ip
        }
        
        self.move_history.append(log_entry)
        
        # Mantener solo los últimos 100 movimientos
        if len(self.move_history) > 100:
            self.move_history = self.move_history[-100:]

    def _save_calibration_data(self, limits: Dict[str, Any]):
        """Guarda los datos de calibración"""
        try:
            filename = f"ptz_limits_{self.ip.replace('.', '_')}.json"
            with open(filename, 'w') as f:
                json.dump(limits, f, indent=4)
            print(f"💾 Límites guardados en {filename}")
        except Exception as e:
            print(f"❌ Error guardando calibración: {e}")

    def get_movement_history(self, limit: int = 10) -> list:
        """
        Obtiene el historial de movimientos recientes
        
        Args:
            limit: Número máximo de entradas a retornar
            
        Returns:
            Lista con historial de movimientos
        """
        return self.move_history[-limit:] if self.move_history else []

    def reset_connection(self) -> bool:
        """
        Reinicia la conexión PTZ
        
        Returns:
            bool: True si la reconexión fue exitosa
        """
        try:
            print(f"🔄 Reiniciando conexión PTZ a {self.ip}")
            self._initialize_connection()
            return True
        except Exception as e:
            print(f"❌ Error reiniciando conexión: {e}")
            return False

    def test_all_functions(self) -> Dict[str, bool]:
        """
        Prueba todas las funciones PTZ disponibles
        
        Returns:
            Dict con resultados de las pruebas
        """
        results = {}
        
        # Probar obtener estado
        results["get_status"] = self.get_status() is not None
        
        # Probar obtener posición
        results["get_position"] = self.get_position() is not None
        
        # Probar obtener presets
        results["get_presets"] = self.get_presets() is not None
        
        # Probar movimiento suave
        current_pos = self.get_position()
        if current_pos:
            results["smooth_movement"] = self.move_to_position_smooth(
                current_pos["pan"], current_pos["tilt"], current_pos["zoom"], steps=2
            )
        else:
            results["smooth_movement"] = False
        
        # Probar stop
        results["stop"] = self.stop()
        
        return results


def create_enhanced_ptz_camera(ip: str, puerto: int, usuario: str, contrasena: str) -> Optional[PTZCameraEnhanced]:
    """
    Factory function para crear una instancia de PTZCameraEnhanced
    
    Args:
        ip: Dirección IP
        puerto: Puerto de conexión
        usuario: Usuario
        contrasena: Contraseña
        
    Returns:
        Instancia de PTZCameraEnhanced o None si falla
    """
    try:
        return PTZCameraEnhanced(ip, puerto, usuario, contrasena)
    except Exception as e:
        print(f"❌ Error creando cámara PTZ mejorada: {e}")
        return None


def initialize_ptz_system() -> Dict[str, Any]:
    """
    Inicializa el sistema PTZ y verifica dependencias
    
    Returns:
        Dict con información del sistema PTZ
    """
    system_info = {
        "onvif_available": False,
        "enhanced_features": True,
        "version": "1.0.0",
        "supported_protocols": ["ONVIF"],
        "initialization_time": datetime.now().isoformat(),
        "errors": []
    }
    
    try:
        # Verificar disponibilidad de ONVIF
        from onvif import ONVIFCamera
        system_info["onvif_available"] = True
        print("✅ ONVIF disponible")
        
    except ImportError as e:
        system_info["onvif_available"] = False
        system_info["errors"].append(f"ONVIF no disponible: {e}")
        print(f"❌ ONVIF no disponible: {e}")
    
    try:
        # Verificar otras dependencias
        import json
        import os
        from datetime import datetime
        print("✅ Dependencias básicas verificadas")
        
    except ImportError as e:
        system_info["errors"].append(f"Dependencias faltantes: {e}")
        print(f"❌ Error en dependencias: {e}")
    
    return system_info


def get_ptz_system_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual del sistema PTZ
    
    Returns:
        Dict con estado del sistema
    """
    return {
        "initialized": True,
        "active_connections": 0,  # Esto se actualizaría con conexiones reales
        "last_check": datetime.now().isoformat(),
        "system_ready": True
    }


def validate_ptz_credentials(ip: str, puerto: int, usuario: str, contrasena: str) -> Dict[str, Any]:
    """
    Valida las credenciales PTZ sin crear una conexión permanente
    
    Args:
        ip: Dirección IP
        puerto: Puerto
        usuario: Usuario
        contrasena: Contraseña
        
    Returns:
        Dict con resultado de la validación
    """
    result = {
        "valid": False,
        "error": None,
        "response_time": None,
        "capabilities": []
    }
    
    start_time = time.time()
    
    try:
        # Crear conexión temporal para validar
        test_cam = PTZCameraEnhanced(ip, puerto, usuario, contrasena)
        
        # Si llegamos aquí, las credenciales son válidas
        result["valid"] = True
        result["response_time"] = time.time() - start_time
        
        # Intentar obtener capacidades básicas
        try:
            if hasattr(test_cam, 'get_presets'):
                presets = test_cam.get_presets()
                if presets is not None:
                    result["capabilities"].append("presets")
        except:
            pass
            
        try:
            if hasattr(test_cam, 'get_position'):
                position = test_cam.get_position()
                if position is not None:
                    result["capabilities"].append("position_feedback")
        except:
            pass
            
        print(f"✅ Credenciales válidas para {ip}")
        
    except Exception as e:
        result["valid"] = False
        result["error"] = str(e)
        result["response_time"] = time.time() - start_time
        print(f"❌ Credenciales inválidas para {ip}: {e}")
    
    return result


# Funciones de utilidad adicionales
def format_ptz_position(position: Dict[str, float]) -> str:
    """
    Formatea una posición PTZ para mostrar
    
    Args:
        position: Dict con pan, tilt, zoom
        
    Returns:
        String formateado
    """
    if not position:
        return "Posición no disponible"
        
    pan = position.get("pan", 0)
    tilt = position.get("tilt", 0) 
    zoom = position.get("zoom", 0)
    
    return f"Pan: {pan:.2f}, Tilt: {tilt:.2f}, Zoom: {zoom:.2f}"


def calculate_movement_distance(pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
    """
    Calcula la distancia de movimiento entre dos posiciones
    
    Args:
        pos1: Posición inicial
        pos2: Posición final
        
    Returns:
        Distancia euclidiana
    """
    if not pos1 or not pos2:
        return 0.0
        
    dx = pos2.get("pan", 0) - pos1.get("pan", 0)
    dy = pos2.get("tilt", 0) - pos1.get("tilt", 0)
    dz = pos2.get("zoom", 0) - pos1.get("zoom", 0)
    
    return (dx*dx + dy*dy + dz*dz) ** 0.5


def generate_preset_tour(presets: list, hold_time: float = 3.0) -> list:
    """
    Genera una secuencia optimizada para tour de presets
    
    Args:
        presets: Lista de presets
        hold_time: Tiempo en cada preset
        
    Returns:
        Lista de comandos para el tour
    """
    if len(presets) < 2:
        return []
        
    tour_commands = []
    
    for i, preset in enumerate(presets):
        tour_commands.append({
            "action": "goto_preset",
            "preset": preset,
            "hold_time": hold_time,
            "sequence": i + 1,
            "total": len(presets)
        })
    
    return tour_commands


class PTZDetectionBridge:
    """Bridge CORREGIDO para conectar detecciones YOLO con sistema PTZ"""

    def __init__(self, ptz_system):
        # CORRECCIÓN CRÍTICA: Verificar que ptz_system no sea None
        if ptz_system is None:
            raise ValueError("ptz_system no puede ser None")

        self.ptz_system = ptz_system
        self.active_cameras = {}
        self.detection_count = 0
        self.last_detection_time = {}

        # Verificar que el sistema PTZ tiene los métodos necesarios
        if not hasattr(self.ptz_system, 'dialog'):
            print("⚠️ PTZ System sin atributo 'dialog'")

    def send_detections(self, camera_id: str, detections: list, frame_size=(1920, 1080)):
        """Enviar detecciones al sistema PTZ - MÉTODO CORREGIDO"""
        try:
            # Verificar que tenemos un sistema PTZ válido
            if not self.ptz_system:
                print("❌ Sistema PTZ no disponible")
                return False

            # Verificar que el diálogo existe y está activo
            if not hasattr(self.ptz_system, 'dialog') or not self.ptz_system.dialog:
                print(f"⚠️ PTZ Bridge: no hay diálogo para cámara {camera_id}")
                return False

            dialog = self.ptz_system.dialog

            # Verificar que el tracking está activo
            if not hasattr(dialog, 'tracking_active') or not dialog.tracking_active:
                print(f"⚠️ PTZ Bridge: seguimiento no activo para cámara {camera_id}")
                return False

            # Validar detecciones
            if not isinstance(detections, list) or not detections:
                return False

            valid_detections = []
            for det in detections:
                if isinstance(det, dict) and 'bbox' in det and len(det.get('bbox', [])) == 4:
                    valid_detections.append(det)

            if not valid_detections:
                return False

            # Intentar enviar detecciones al diálogo
            if hasattr(dialog, 'update_detections'):
                success = dialog.update_detections(valid_detections, frame_size)
                if success:
                    self.detection_count += len(valid_detections)
                    if camera_id not in self.active_cameras:
                        self.active_cameras[camera_id] = {'detections_sent': 0}
                    self.active_cameras[camera_id]['detections_sent'] += len(valid_detections)
                return success
            else:
                print("⚠️ Diálogo PTZ sin método 'update_detections'")
                return False

        except Exception as e:
            print(f"❌ Error en PTZ Bridge.send_detections: {e}")
            return False

    def register_camera(self, camera_id: str, camera_data: dict):
        """Registrar una cámara en el bridge - MÉTODO CORREGIDO"""
        try:
            self.active_cameras[camera_id] = {
                'data': camera_data,
                'detections_sent': 0,
                'registered_at': time.time()
            }
            print(f"📷 Cámara registrada en PTZ Bridge: {camera_id}")
            return True
        except Exception as e:
            print(f"❌ Error registrando cámara en PTZ Bridge: {e}")
            return False

    def get_status(self, camera_id=None):
        """Obtener estado del bridge"""
        try:
            status = {
                'active': True,
                'cameras_registered': len(self.active_cameras),
                'total_detections': self.detection_count,
                'system_available': self.ptz_system is not None
            }

            if self.ptz_system and hasattr(self.ptz_system, 'dialog'):
                dialog = self.ptz_system.dialog
                if dialog and hasattr(dialog, 'tracking_active'):
                    status['tracking_active'] = dialog.tracking_active
                else:
                    status['tracking_active'] = False
            else:
                status['tracking_active'] = False

            return status
        except Exception as e:
            return {'active': False, 'error': str(e)}

    def cleanup(self):
        """Limpiar recursos del bridge"""
        try:
            self.active_cameras.clear()
            self.detection_count = 0
            self.last_detection_time.clear()
            print("🧹 PTZ Bridge limpiado")
        except Exception as e:
            print(f"❌ Error limpiando PTZ Bridge: {e}")


class PTZSystemWrapper:
    """Wrapper CORREGIDO para el sistema PTZ con todos los métodos necesarios"""

    def __init__(self, dialog):
        self.dialog = dialog

    def show(self):
        """Mostrar el diálogo PTZ"""
        if self.dialog and hasattr(self.dialog, 'show'):
            self.dialog.show()
            return True
        else:
            print("❌ Error: No se puede mostrar el diálogo PTZ")
            return False

    def hide(self):
        """Ocultar el diálogo PTZ"""
        if self.dialog and hasattr(self.dialog, 'hide'):
            self.dialog.hide()

    def close(self):
        """Cerrar el diálogo PTZ"""
        if self.dialog and hasattr(self.dialog, 'close'):
            self.dialog.close()

    def exec(self):
        """Ejecutar el diálogo de forma modal"""
        if self.dialog and hasattr(self.dialog, 'exec'):
            return self.dialog.exec()
        return False

    def get_status(self):
        """Obtener estado del sistema"""
        if self.dialog and hasattr(self.dialog, 'tracking_active'):
            return {
                'active': self.dialog.tracking_active,
                'dialog_available': True,
                'dialog_visible': self.dialog.isVisible() if hasattr(self.dialog, 'isVisible') else False
            }
        return {'active': False, 'dialog_available': False, 'dialog_visible': False}

    def cleanup(self):
        """Limpiar recursos del sistema"""
        if self.dialog and hasattr(self.dialog, 'close'):
            self.dialog.close()
        self.dialog = None

    def is_visible(self):
        """Verificar si el diálogo está visible"""
        if self.dialog and hasattr(self.dialog, 'isVisible'):
            return self.dialog.isVisible()
        return False

    def raise_(self):
        """Traer al frente el diálogo"""
        if self.dialog and hasattr(self.dialog, 'raise_'):
            self.dialog.raise_()

    def activateWindow(self):
        """Activar la ventana del diálogo"""
        if self.dialog and hasattr(self.dialog, 'activateWindow'):
            self.dialog.activateWindow()

def create_multi_object_ptz_system(camera_list, parent=None):
    """Crear sistema PTZ multi-objeto CORREGIDO - versión que retorna wrapper funcional"""
    try:
        print(f"🎯 Creando sistema PTZ multi-objeto con {len(camera_list)} cámara(s)...")

        # Verificar que tenemos cámaras PTZ
        ptz_cameras = [cam for cam in camera_list if cam.get('tipo', '').lower() == 'ptz']
        if not ptz_cameras:
            print("❌ No hay cámaras PTZ en la lista")
            return None

        # CORRECCIÓN CRÍTICA: Crear el diálogo PTZ correctamente
        try:
            from ui.enhanced_ptz_multi_object_dialog import EnhancedMultiObjectPTZDialog
            dialog = EnhancedMultiObjectPTZDialog(parent, ptz_cameras)

            # Verificar que el diálogo se creó correctamente
            if not dialog:
                print("❌ Error: No se pudo crear el diálogo PTZ")
                return None

            print("✅ Diálogo PTZ creado exitosamente")

        except Exception as e:
            print(f"❌ Error creando diálogo PTZ: {e}")
            return None

        # Crear sistema wrapper con la clase corregida
        ptz_system = PTZSystemWrapper(dialog)

        # Verificar que el wrapper funciona
        if not hasattr(ptz_system, 'show'):
            print("❌ Error: Wrapper PTZ sin método show")
            return None

        # CORRECCIÓN: Crear bridge DESPUÉS del sistema y con validación
        try:
            bridge = PTZDetectionBridge(ptz_system)
            print("🌉 Puente PTZ registrado para integración con detecciones")
        except Exception as e:
            print(f"❌ Error creando bridge PTZ: {e}")
            # Continuar sin bridge si es necesario
            bridge = None

        # Conectar bridge al diálogo si existe
        if bridge:
            if hasattr(dialog, 'set_detection_bridge'):
                dialog.set_detection_bridge(bridge)
            else:
                dialog.detection_bridge = bridge

        print("✅ Sistema PTZ multi-objeto creado exitosamente")
        return ptz_system

    except Exception as e:
        print(f"❌ Error crítico creando sistema PTZ: {e}")
        return None


# Constantes y configuraciones
PTZ_DEFAULTS = {
    "default_speed": 0.5,
    "default_timeout": 30.0,
    "max_retries": 3,
    "position_tolerance": 0.01,
    "move_duration": 0.3,
    "zoom_step": 0.1,
    "pan_step": 0.1,
    "tilt_step": 0.1
}

PTZ_LIMITS = {
    "pan_min": -1.0,
    "pan_max": 1.0, 
    "tilt_min": -1.0,
    "tilt_max": 1.0,
    "zoom_min": 0.0,
    "zoom_max": 1.0,
    "speed_min": 0.1,
    "speed_max": 1.0
}


def test_ptz_system_creation():
    """Probar la creación del sistema PTZ para verificar que funciona"""
    try:
        # Datos de prueba
        test_cameras = [{
            'ip': '192.168.1.100',
            'puerto': 80,
            'usuario': 'admin',
            'contrasena': 'admin123',
            'tipo': 'ptz',
            'nombre': 'Cámara PTZ Test'
        }]

        # Crear sistema
        system = create_multi_object_ptz_system(test_cameras)

        if system:
            print("✅ Test: Sistema PTZ creado exitosamente")

            # Verificar métodos necesarios
            required_methods = ['show', 'hide', 'close', 'get_status']
            for method in required_methods:
                if hasattr(system, method):
                    print(f"✅ Test: Método {method} disponible")
                else:
                    print(f"❌ Test: Método {method} NO disponible")

            # Limpiar
            system.cleanup()
            return True
        else:
            print("❌ Test: No se pudo crear el sistema PTZ")
            return False

    except Exception as e:
        print(f"❌ Test: Error en creación del sistema PTZ: {e}")
        return False


if __name__ == "__main__":
    # Código de prueba para verificar el módulo
    print("🧪 Ejecutando pruebas del módulo PTZ mejorado...")
    
    # Inicializar sistema
    system_info = initialize_ptz_system()
    print(f"Sistema PTZ: {system_info}")
    
    # Verificar estado
    status = get_ptz_system_status()
    print(f"Estado del sistema: {status}")

    # Ejecutar test de creación del sistema PTZ
    test_ptz_system_creation()

    print("✅ Módulo PTZ mejorado cargado correctamente")