#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema PTZ Profesional con AbsoluteMove
Archivo: professional_ptz_system.py

Sistema completo de seguimiento PTZ con características avanzadas:
- Confirmación de detecciones antes de mover
- Compensación de delay de cámara
- Filtrado de falsos positivos
- Movimientos suaves y controlados
- Sistema de calibración automática
- Logging profesional y métricas

Autor: Sistema PTZ Profesional
Versión: 1.0.0
Fecha: 2024
"""

import time
import json
import threading
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
import logging
import os
import socket

# =====================================================================
# CONFIGURACIÓN Y ESTRUCTURAS DE DATOS
# =====================================================================

@dataclass
class PTZConfig:
    """Configuración del sistema PTZ"""
    # Confirmación de detecciones
    confirmation_frames: int = 3              # Frames consecutivos para confirmar
    confirmation_timeout: float = 2.0        # Timeout máximo para confirmación
    
    # Control de movimiento
    min_movement_threshold: float = 50        # Píxeles mínimos para mover
    movement_cooldown: float = 1.5           # Tiempo mínimo entre movimientos
    position_tolerance: float = 30           # Tolerancia para considerar centrado
    
    # Compensación de delay
    camera_delay: float = 0.8               # Delay estimado de la cámara
    movement_prediction: bool = True         # Predecir posición futura
    
    # Filtrado de detecciones
    min_confidence: float = 0.6             # Confianza mínima
    max_position_jump: float = 200          # Máximo salto entre frames
    stability_frames: int = 2               # Frames de estabilidad requeridos
    
    # Velocidades PTZ
    fast_speed: float = 0.8                 # Velocidad para movimientos grandes
    normal_speed: float = 0.4               # Velocidad normal
    precise_speed: float = 0.2              # Velocidad para ajustes finos
    
    # Zoom inteligente
    auto_zoom: bool = True                  # Activar zoom automático
    min_zoom: float = 0.1                   # Zoom mínimo
    max_zoom: float = 0.9                   # Zoom máximo
    target_object_ratio: float = 0.25       # Ratio objetivo del objeto en frame
    
    # Configuración avanzada
    movement_smoothing: bool = True          # Suavizar movimientos
    return_to_center_timeout: float = 30.0  # Tiempo para volver al centro
    max_tracking_distance: float = 500      # Distancia máxima de seguimiento

@dataclass
class Detection:
    """Estructura de una detección"""
    x: float
    y: float
    width: float
    height: float
    confidence: float
    timestamp: float
    class_name: str = "object"
    track_id: Optional[str] = None
    
    @property
    def center_x(self) -> float:
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        return self.y + self.height / 2
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def distance_to(self, other: 'Detection') -> float:
        """Calcular distancia a otra detección"""
        return np.sqrt(
            (self.center_x - other.center_x)**2 + 
            (self.center_y - other.center_y)**2
        )

@dataclass
class PTZPosition:
    """Posición PTZ"""
    pan: float
    tilt: float
    zoom: float
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def distance_to(self, other: 'PTZPosition') -> float:
        """Calcular distancia a otra posición PTZ"""
        return np.sqrt(
            (self.pan - other.pan)**2 + 
            (self.tilt - other.tilt)**2 +
            (self.zoom - other.zoom)**2 * 0.1  # Zoom tiene menos peso
        )

class DetectionTracker:
    """Rastreador de detecciones para confirmación"""
    
    def __init__(self, config: PTZConfig):
        self.config = config
        self.detection_history: deque = deque(maxlen=10)
        self.confirmed_target: Optional[Detection] = None
        self.confirmation_start: Optional[float] = None
        self.stable_count = 0
        self.last_confirmed_time = 0.0
        
    def add_detection(self, detection: Detection) -> bool:
        """
        Agregar detección y verificar si está confirmada
        
        Returns:
            bool: True si la detección está confirmada para seguimiento
        """
        current_time = time.time()
        
        # Agregar a historial
        self.detection_history.append(detection)
        
        # Verificar si tenemos suficientes detecciones
        if len(self.detection_history) < self.config.confirmation_frames:
            return False
        
        # Verificar estabilidad de las últimas detecciones
        recent_detections = list(self.detection_history)[-self.config.confirmation_frames:]
        
        if self._are_detections_stable(recent_detections):
            self.stable_count += 1
            
            # Confirmar si hemos tenido detecciones estables suficientes
            if self.stable_count >= self.config.stability_frames:
                self.confirmed_target = detection
                self.last_confirmed_time = current_time
                return True
        else:
            self.stable_count = 0
            
        return False
    
    def _are_detections_stable(self, detections: List[Detection]) -> bool:
        """Verificar si las detecciones son estables"""
        if len(detections) < 2:
            return False
        
        # Verificar confianza mínima
        for det in detections:
            if det.confidence < self.config.min_confidence:
                return False
        
        # Verificar que no hay saltos grandes de posición
        for i in range(1, len(detections)):
            prev_det = detections[i-1]
            curr_det = detections[i]
            
            distance = curr_det.distance_to(prev_det)
            
            if distance > self.config.max_position_jump:
                return False
        
        # Verificar consistencia temporal
        time_span = detections[-1].timestamp - detections[0].timestamp
        if time_span > self.config.confirmation_timeout:
            return False
        
        return True
    
    def get_predicted_position(self) -> Optional[Detection]:
        """Predecir posición futura basada en movimiento"""
        if not self.config.movement_prediction or len(self.detection_history) < 2:
            return self.confirmed_target
        
        # Calcular velocidad promedio
        recent = list(self.detection_history)[-3:]  # Últimas 3 detecciones
        if len(recent) < 2:
            return self.confirmed_target
        
        # Calcular velocidad en x, y
        dt = recent[-1].timestamp - recent[0].timestamp
        if dt <= 0:
            return self.confirmed_target
        
        dx = (recent[-1].center_x - recent[0].center_x) / dt
        dy = (recent[-1].center_y - recent[0].center_y) / dt
        
        # Predecir posición futura considerando el delay de la cámara
        future_time = self.config.camera_delay
        
        predicted = Detection(
            x=recent[-1].x + dx * future_time,
            y=recent[-1].y + dy * future_time,
            width=recent[-1].width,
            height=recent[-1].height,
            confidence=recent[-1].confidence,
            timestamp=recent[-1].timestamp + future_time,
            class_name=recent[-1].class_name,
            track_id=recent[-1].track_id
        )
        
        return predicted
    
    def is_target_lost(self, timeout: float = 5.0) -> bool:
        """Verificar si el objetivo se perdió"""
        if not self.confirmed_target:
            return True
        
        return (time.time() - self.last_confirmed_time) > timeout

class PTZCoordinateConverter:
    """Conversor avanzado de coordenadas píxel a PTZ"""
    
    def __init__(self, camera_ip: str):
        self.camera_ip = camera_ip
        self.calibration = self._load_calibration()
        self.movement_history = deque(maxlen=20)
        
    def _load_calibration(self) -> Dict:
        """Cargar calibración de la cámara"""
        default_calibration = {
            'pan_range': {'min': -1.0, 'max': 1.0},
            'tilt_range': {'min': -1.0, 'max': 1.0},
            'zoom_range': {'min': 0.0, 'max': 1.0},
            'field_of_view': {
                'horizontal_degrees': 60.0,
                'vertical_degrees': 45.0
            },
            'center_offset': {'pan': 0.0, 'tilt': 0.0},
            'movement_scaling': {
                'pan_factor': 1.0,
                'tilt_factor': 1.0,
                'zoom_factor': 1.0
            },
            'limits': {
                'max_pan_speed': 0.8,
                'max_tilt_speed': 0.8,
                'max_zoom_speed': 0.5
            }
        }
        
        try:
            calibration_file = f"calibration_{self.camera_ip.replace('.', '_')}.json"
            if os.path.exists(calibration_file):
                with open(calibration_file, 'r') as f:
                    saved_cal = json.load(f)
                    default_calibration.update(saved_cal)
                    logging.info(f"📏 Calibración cargada para {self.camera_ip}")
            else:
                logging.info(f"📏 Usando calibración por defecto para {self.camera_ip}")
        except Exception as e:
            logging.warning(f"⚠️ Error cargando calibración: {e}")
        
        return default_calibration
    
    def pixel_to_ptz(self, detection: Detection, frame_width: int, frame_height: int,
                    current_position: PTZPosition) -> PTZPosition:
        """Convertir detección a coordenadas PTZ absolutas"""
        
        # Centro del frame
        frame_center_x = frame_width / 2
        frame_center_y = frame_height / 2
        
        # Offset del objeto respecto al centro
        offset_x = detection.center_x - frame_center_x
        offset_y = detection.center_y - frame_center_y
        
        # Normalizar a rango -1.0 a 1.0
        normalized_x = offset_x / frame_center_x
        normalized_y = offset_y / frame_center_y
        
        # Aplicar campo de visión
        fov_h = self.calibration['field_of_view']['horizontal_degrees']
        fov_v = self.calibration['field_of_view']['vertical_degrees']
        
        # Convertir a incrementos PTZ
        pan_increment = normalized_x * (fov_h / 360.0)  # Proporción del rango total
        tilt_increment = -normalized_y * (fov_v / 360.0)  # Invertir Y
        
        # Aplicar factores de escalamiento
        scaling = self.calibration['movement_scaling']
        pan_increment *= scaling['pan_factor']
        tilt_increment *= scaling['tilt_factor']
        
        # Aplicar zoom factor (a mayor zoom, menor movimiento necesario)
        zoom_factor = 1.0 - (current_position.zoom * 0.7)
        pan_increment *= zoom_factor
        tilt_increment *= zoom_factor
        
        # Aplicar offset de centro si existe
        center_offset = self.calibration['center_offset']
        
        # Calcular nuevas coordenadas absolutas
        new_pan = current_position.pan + pan_increment + center_offset['pan']
        new_tilt = current_position.tilt + tilt_increment + center_offset['tilt']
        
        # Aplicar límites
        pan_range = self.calibration['pan_range']
        tilt_range = self.calibration['tilt_range']
        
        new_pan = max(pan_range['min'], min(pan_range['max'], new_pan))
        new_tilt = max(tilt_range['min'], min(tilt_range['max'], new_tilt))
        
        # Calcular zoom óptimo
        new_zoom = self._calculate_optimal_zoom(detection, frame_width, frame_height, current_position.zoom)
        
        # Registrar movimiento en historial
        movement = {
            'timestamp': time.time(),
            'offset_pixels': (offset_x, offset_y),
            'ptz_increment': (pan_increment, tilt_increment),
            'final_position': (new_pan, new_tilt, new_zoom)
        }
        self.movement_history.append(movement)
        
        return PTZPosition(pan=new_pan, tilt=new_tilt, zoom=new_zoom)
    
    def _calculate_optimal_zoom(self, detection: Detection, frame_w: int, frame_h: int, current_zoom: float) -> float:
        """Calcular zoom óptimo basado en el tamaño del objeto"""
        # Ratio actual del objeto en el frame
        object_ratio_w = detection.width / frame_w
        object_ratio_h = detection.height / frame_h
        current_ratio = max(object_ratio_w, object_ratio_h)
        
        # Ratio objetivo
        target_ratio = self.calibration.get('target_object_ratio', 0.25)
        
        # Calcular zoom necesario
        if current_ratio > 0:
            zoom_factor = target_ratio / current_ratio
            # Suavizar cambio de zoom
            zoom_change = (zoom_factor - 1.0) * 0.3  # Factor de suavizado
            new_zoom = current_zoom * (1.0 + zoom_change)
            
            # Aplicar límites de zoom
            zoom_range = self.calibration['zoom_range']
            new_zoom = max(zoom_range['min'], min(zoom_range['max'], new_zoom))
        else:
            new_zoom = current_zoom
        
        return new_zoom
    
    def get_movement_statistics(self) -> Dict:
        """Obtener estadísticas de movimiento"""
        if not self.movement_history:
            return {}
        
        recent_movements = list(self.movement_history)[-10:]  # Últimos 10 movimientos
        
        # Calcular estadísticas
        pan_increments = [mov['ptz_increment'][0] for mov in recent_movements]
        tilt_increments = [mov['ptz_increment'][1] for mov in recent_movements]
        
        return {
            'total_movements': len(self.movement_history),
            'recent_movements': len(recent_movements),
            'avg_pan_increment': np.mean(pan_increments) if pan_increments else 0,
            'avg_tilt_increment': np.mean(tilt_increments) if tilt_increments else 0,
            'max_pan_increment': np.max(np.abs(pan_increments)) if pan_increments else 0,
            'max_tilt_increment': np.max(np.abs(tilt_increments)) if tilt_increments else 0
        }

# =====================================================================
# CLASE PRINCIPAL DEL SISTEMA PTZ
# =====================================================================

class ProfessionalPTZSystem:
    """Sistema PTZ Profesional con todas las características avanzadas"""
    
    def __init__(self, camera_ip: str, port: int, username: str, password: str,
                 config: Optional[PTZConfig] = None):
        
        # Configuración
        self.camera_ip = camera_ip
        self.port = port
        self.username = username
        self.password = password
        self.config = config or PTZConfig()
        
        # Componentes del sistema
        self.detection_tracker = DetectionTracker(self.config)
        self.coordinate_converter = PTZCoordinateConverter(camera_ip)
        
        # Estado del sistema
        self.is_connected = False
        self.is_tracking = False
        self.current_position = PTZPosition(0.0, 0.0, 0.5)
        self.last_movement_time = 0.0
        self.target_detection: Optional[Detection] = None
        self.home_position = PTZPosition(0.0, 0.0, 0.5)
        
        # Conexión ONVIF
        self.camera = None
        self.ptz_service = None
        self.profile_token = None
        
        # Estadísticas
        self.stats = {
            'total_detections': 0,
            'confirmed_detections': 0,
            'movements_executed': 0,
            'movements_skipped': 0,
            'average_response_time': 0.0,
            'session_start': time.time(),
            'last_target_time': 0.0,
            'connection_attempts': 0,
            'successful_connections': 0
        }
        
        # Logging
        self._setup_logging()
        
        # Hilo de control
        self.control_thread = None
        self.running = False
        
        # Sistema de alertas
        self.error_count = 0
        self.max_errors = 10
        
    def _setup_logging(self):
        """Configurar logging profesional"""
        logger_name = f"PTZ_{self.camera_ip.replace('.', '_')}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Crear directorio de logs si no existe
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # Handler para archivo
        log_file = f"logs/ptz_log_{self.camera_ip.replace('.', '_')}.log"
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - PTZ - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"🚀 Sistema PTZ inicializado para {self.camera_ip}")
    
    def connect(self) -> bool:
        """Conectar al sistema PTZ"""
        try:
            self.stats['connection_attempts'] += 1
            self.logger.info(f"🔗 Conectando a PTZ {self.camera_ip}:{self.port}")
            
            # Verificar conectividad de red
            if not self._test_network_connectivity():
                self.logger.error(f"❌ No hay conectividad de red a {self.camera_ip}:{self.port}")
                return False
            
            # Crear cámara ONVIF
            try:
                from onvif import ONVIFCamera
                
                self.camera = ONVIFCamera(
                    self.camera_ip, self.port, self.username, self.password,
                    wsdl_dir='wsdl/'
                )
                
                # Servicios
                self.ptz_service = self.camera.create_ptz_service()
                media_service = self.camera.create_media_service()
                
                # Perfiles
                profiles = media_service.GetProfiles()
                if not profiles:
                    self.logger.error("❌ No se encontraron perfiles")
                    return False
                
                self.profile_token = profiles[0].token
                self.logger.info(f"📋 Perfil obtenido: {self.profile_token}")
                
            except ImportError:
                self.logger.error("❌ Librería ONVIF no disponible. Instalar: pip install onvif-zeep")
                return False
            except Exception as e:
                self.logger.error(f"❌ Error creando servicios ONVIF: {e}")
                return False
            
            # Obtener posición actual
            try:
                status = self.ptz_service.GetStatus(self.profile_token)
                if status and status.Position:
                    self.current_position = PTZPosition(
                        pan=float(status.Position.PanTilt.x),
                        tilt=float(status.Position.PanTilt.y),
                        zoom=float(status.Position.Zoom.x) if status.Position.Zoom else 0.5
                    )
                    self.home_position = PTZPosition(
                        pan=self.current_position.pan,
                        tilt=self.current_position.tilt,
                        zoom=self.current_position.zoom
                    )
                    self.logger.info(f"📍 Posición actual: {asdict(self.current_position)}")
            except Exception as e:
                self.logger.warning(f"⚠️ No se pudo obtener posición actual: {e}")
                # Usar valores por defecto
                self.current_position = PTZPosition(0.0, 0.0, 0.5)
                self.home_position = PTZPosition(0.0, 0.0, 0.5)
            
            # Test de movimiento
            test_success = self._test_movement()
            if test_success:
                self.is_connected = True
                self.stats['successful_connections'] += 1
                self.logger.info("✅ Conexión PTZ exitosa")
                return True
            else:
                self.logger.error("❌ Test de movimiento falló")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error conectando PTZ: {e}")
            self.error_count += 1
            return False
    
    def _test_network_connectivity(self) -> bool:
        """Probar conectividad de red"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.camera_ip, self.port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _test_movement(self) -> bool:
        """Test básico de movimiento"""
        try:
            self.logger.info("🧪 Probando movimiento PTZ...")
            
            # Movimiento mínimo para verificar funcionalidad
            test_position = PTZPosition(
                pan=self.current_position.pan + 0.02,
                tilt=self.current_position.tilt,
                zoom=self.current_position.zoom
            )
            
            success = self._execute_absolute_move(test_position, speed=0.1)
            
            if success:
                time.sleep(1.0)
                # Volver a posición original
                self._execute_absolute_move(self.current_position, speed=0.1)
                time.sleep(0.5)
                self.logger.info("✅ Test de movimiento exitoso")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error en test de movimiento: {e}")
            return False
    
    def start_tracking(self) -> bool:
        """Iniciar sistema de seguimiento"""
        if not self.is_connected:
            self.logger.error("❌ PTZ no conectado")
            return False
        
        if self.is_tracking:
            self.logger.warning("⚠️ Seguimiento ya activo")
            return True
        
        self.logger.info("🚀 Iniciando seguimiento PTZ profesional")
        self.is_tracking = True
        self.running = True
        self.stats['session_start'] = time.time()
        
        # Resetear estadísticas de sesión
        self.stats.update({
            'total_detections': 0,
            'confirmed_detections': 0,
            'movements_executed': 0,
            'movements_skipped': 0
        })
        
        # Iniciar hilo de control
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        
        self.logger.info("✅ Sistema de seguimiento iniciado")
        return True
    
    def stop_tracking(self):
        """Detener seguimiento"""
        self.logger.info("⏹️ Deteniendo seguimiento PTZ")
        self.is_tracking = False
        self.running = False
        
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=2.0)
        
        # Volver a posición home si está configurado
        if self.config.return_to_center_timeout > 0:
            try:
                self._execute_absolute_move(self.home_position, speed=0.3)
                self.logger.info("🏠 Volviendo a posición home")
            except Exception as e:
                self.logger.warning(f"⚠️ Error volviendo a home: {e}")
    
    def add_detection(self, x: float, y: float, width: float, height: float,
                     confidence: float, frame_width: int, frame_height: int,
                     class_name: str = "object", track_id: Optional[str] = None):
        """
        Agregar una nueva detección al sistema
        
        Args:
            x, y, width, height: Bounding box del objeto
            confidence: Confianza de la detección
            frame_width, frame_height: Dimensiones del frame
            class_name: Clase del objeto
            track_id: ID de tracking si está disponible
        """
        
        detection = Detection(
            x=x, y=y, width=width, height=height,
            confidence=confidence, timestamp=time.time(),
            class_name=class_name, track_id=track_id
        )
        
        self.stats['total_detections'] += 1
        
        # Agregar al tracker para confirmación
        is_confirmed = self.detection_tracker.add_detection(detection)
        
        if is_confirmed:
            self.stats['confirmed_detections'] += 1
            self.stats['last_target_time'] = time.time()
            self.target_detection = detection
            self.logger.info(
                f"🎯 Objetivo confirmado: {class_name} en ({detection.center_x:.1f}, {detection.center_y:.1f}) "
                f"conf={confidence:.3f}"
            )
    
    def _control_loop(self):
        """Bucle principal de control PTZ"""
        self.logger.info("🔄 Iniciando bucle de control PTZ")
        
        last_heartbeat = time.time()
        heartbeat_interval = 30.0  # Heartbeat cada 30 segundos
        
        while self.running:
            try:
                current_time = time.time()
                
                # Heartbeat y estadísticas periódicas
                if current_time - last_heartbeat > heartbeat_interval:
                    self._log_heartbeat()
                    last_heartbeat = current_time
                
                # Procesar seguimiento si hay objetivo
                if self.target_detection and self.is_tracking:
                    self._process_tracking()
                
                # Verificar si el objetivo se perdió
                elif self.detection_tracker.is_target_lost():
                    if self.target_detection:
                        self.logger.info("👻 Objetivo perdido")
                        self.target_detection = None
                
                time.sleep(0.1)  # 10 FPS de control
                
            except Exception as e:
                self.logger.error(f"❌ Error en bucle de control: {e}")
                self.error_count += 1
                if self.error_count > self.max_errors:
                    self.logger.critical("🚨 Demasiados errores, deteniendo sistema")
                    break
                time.sleep(0.5)
        
        self.logger.info("🛑 Bucle de control terminado")
    
    def _log_heartbeat(self):
        """Log de heartbeat con estadísticas"""
        uptime = time.time() - self.stats['session_start']
        self.logger.info(
            f"💓 Heartbeat - Uptime: {uptime:.1f}s, "
            f"Detecciones: {self.stats['total_detections']}, "
            f"Confirmadas: {self.stats['confirmed_detections']}, "
            f"Movimientos: {self.stats['movements_executed']}"
        )
    
    def _process_tracking(self):
        """Procesar seguimiento del objetivo actual"""
        current_time = time.time()
        
        # Verificar cooldown de movimiento
        if current_time - self.last_movement_time < self.config.movement_cooldown:
            return
        
        # Obtener posición predicha si está habilitada la predicción
        if self.config.movement_prediction:
            target = self.detection_tracker.get_predicted_position()
        else:
            target = self.target_detection
        
        if not target:
            return
        
        # Calcular distancia al centro del frame (asumiendo 1920x1080 por defecto)
        frame_center_x = 960
        frame_center_y = 540
        
        distance_to_center = np.sqrt(
            (target.center_x - frame_center_x)**2 + 
            (target.center_y - frame_center_y)**2
        )
        
        # Solo mover si está suficientemente descentrado
        if distance_to_center < self.config.position_tolerance:
            self.logger.debug(f"🎯 Objetivo centrado (dist: {distance_to_center:.1f}px)")
            return
        
        if distance_to_center < self.config.min_movement_threshold:
            self.stats['movements_skipped'] += 1
            return
        
        # Ejecutar movimiento
        success = self._execute_tracking_movement(target, frame_center_x * 2, frame_center_y * 2)
        
        if success:
            self.last_movement_time = current_time
            self.stats['movements_executed'] += 1
            self.logger.info(f"✅ PTZ movido hacia objetivo (dist: {distance_to_center:.1f}px)")
        else:
            self.logger.warning("❌ Falló movimiento PTZ")
    
    def _execute_tracking_movement(self, target: Detection, frame_width: int, frame_height: int) -> bool:
        """Ejecutar movimiento de seguimiento"""
        try:
            # Convertir a coordenadas PTZ
            target_position = self.coordinate_converter.pixel_to_ptz(
                target, frame_width, frame_height, self.current_position
            )
            
            # Calcular distancia de movimiento para determinar velocidad
            pan_diff = abs(target_position.pan - self.current_position.pan)
            tilt_diff = abs(target_position.tilt - self.current_position.tilt)
            max_diff = max(pan_diff, tilt_diff)
            
            # Seleccionar velocidad basada en distancia
            if max_diff > 0.3:
                speed = self.config.fast_speed
                speed_desc = "rápida"
            elif max_diff > 0.1:
                speed = self.config.normal_speed
                speed_desc = "normal"
            else:
                speed = self.config.precise_speed
                speed_desc = "precisa"
            
            self.logger.info(
                f"🎯 Moviendo PTZ: "
                f"({self.current_position.pan:.3f}, {self.current_position.tilt:.3f}) → "
                f"({target_position.pan:.3f}, {target_position.tilt:.3f}) "
                f"velocidad {speed_desc} ({speed})"
            )
            
            # Ejecutar movimiento
            success = self._execute_absolute_move(target_position, speed)
            
            if success:
                self.current_position = target_position
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Error en movimiento de seguimiento: {e}")
            return False
    
    def _execute_absolute_move(self, position: PTZPosition, speed: float = 0.3) -> bool:
        """Ejecutar AbsoluteMove"""
        try:
            if not self.ptz_service or not self.profile_token:
                self.logger.error("❌ Servicio PTZ no disponible")
                return False
            
            # Aplicar límites de velocidad
            limits = self.coordinate_converter.calibration.get('limits', {})
            max_pan_speed = limits.get('max_pan_speed', 0.8)
            max_tilt_speed = limits.get('max_tilt_speed', 0.8)
            max_zoom_speed = limits.get('max_zoom_speed', 0.5)
            
            pan_speed = min(speed, max_pan_speed)
            tilt_speed = min(speed, max_tilt_speed)
            zoom_speed = min(speed * 0.5, max_zoom_speed)
            
            # Crear request
            req = self.ptz_service.create_type('AbsoluteMove')
            req.ProfileToken = self.profile_token
            
            # Posición objetivo
            req.Position = {
                'PanTilt': {'x': float(position.pan), 'y': float(position.tilt)},
                'Zoom': {'x': float(position.zoom)}
            }
            
            # Velocidad
            req.Speed = {
                'PanTilt': {'x': float(pan_speed), 'y': float(tilt_speed)},
                'Zoom': {'x': float(zoom_speed)}
            }
            
            # Ejecutar AbsoluteMove
            self.ptz_service.AbsoluteMove(req)
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error en AbsoluteMove: {e}")
            return False
    
    def return_to_home(self) -> bool:
        """Volver a posición home"""
        try:
            self.logger.info("🏠 Volviendo a posición home")
            success = self._execute_absolute_move(self.home_position, speed=0.3)
            if success:
                self.current_position = self.home_position
                self.logger.info("✅ Posición home alcanzada")
            return success
        except Exception as e:
            self.logger.error(f"❌ Error volviendo a home: {e}")
            return False
    
    def set_home_position(self, pan: float = None, tilt: float = None, zoom: float = None):
        """Establecer nueva posición home"""
        if pan is not None:
            self.home_position.pan = pan
        if tilt is not None:
            self.home_position.tilt = tilt
        if zoom is not None:
            self.home_position.zoom = zoom
        
        self.logger.info(f"🏠 Nueva posición home establecida: {asdict(self.home_position)}")
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas del sistema"""
        uptime = time.time() - self.stats['session_start']
        
        # Estadísticas de movimiento
        movement_stats = self.coordinate_converter.get_movement_statistics()
        
        base_stats = {
            **self.stats,
            'uptime_seconds': uptime,
            'detection_rate': self.stats['total_detections'] / max(uptime, 1),
            'confirmation_rate': (self.stats['confirmed_detections'] / 
                                max(self.stats['total_detections'], 1)) * 100,
            'movement_rate': self.stats['movements_executed'] / max(uptime, 1),
            'current_position': asdict(self.current_position),
            'home_position': asdict(self.home_position),
            'is_connected': self.is_connected,
            'is_tracking': self.is_tracking,
            'has_target': self.target_detection is not None,
            'error_count': self.error_count,
            'movement_statistics': movement_stats
        }
        
        # Agregar estadísticas del tracker de detecciones
        if hasattr(self.detection_tracker, 'stable_count'):
            base_stats['tracker_stats'] = {
                'stable_count': self.detection_tracker.stable_count,
                'detection_history_length': len(self.detection_tracker.detection_history),
                'has_confirmed_target': self.detection_tracker.confirmed_target is not None
            }
        
        return base_stats
    
    def get_detailed_status(self) -> Dict:
        """Obtener estado detallado del sistema"""
        try:
            # Obtener estado actual de la cámara PTZ
            if self.ptz_service and self.profile_token:
                try:
                    status = self.ptz_service.GetStatus(self.profile_token)
                    if status and status.Position:
                        actual_position = {
                            'pan': float(status.Position.PanTilt.x),
                            'tilt': float(status.Position.PanTilt.y),
                            'zoom': float(status.Position.Zoom.x) if status.Position.Zoom else 0.5
                        }
                    else:
                        actual_position = None
                except Exception as e:
                    actual_position = f"Error: {e}"
            else:
                actual_position = None
            
            return {
                'system_info': {
                    'camera_ip': self.camera_ip,
                    'port': self.port,
                    'username': self.username,
                    'profile_token': self.profile_token
                },
                'connection_status': {
                    'is_connected': self.is_connected,
                    'connection_attempts': self.stats['connection_attempts'],
                    'successful_connections': self.stats['successful_connections']
                },
                'tracking_status': {
                    'is_tracking': self.is_tracking,
                    'has_target': self.target_detection is not None,
                    'target_info': asdict(self.target_detection) if self.target_detection else None
                },
                'position_info': {
                    'expected_position': asdict(self.current_position),
                    'actual_position': actual_position,
                    'home_position': asdict(self.home_position)
                },
                'configuration': asdict(self.config),
                'calibration': self.coordinate_converter.calibration,
                'statistics': self.get_stats()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo estado detallado: {e}")
            return {'error': str(e)}
    
    def update_config(self, new_config: PTZConfig):
        """Actualizar configuración del sistema"""
        old_config = self.config
        self.config = new_config
        
        # Actualizar componentes que dependen de la configuración
        self.detection_tracker.config = new_config
        
        self.logger.info("⚙️ Configuración actualizada")
        self.logger.debug(f"Cambios: {asdict(new_config)}")
    
    def calibrate_field_of_view(self, horizontal_degrees: float, vertical_degrees: float):
        """Calibrar campo de visión de la cámara"""
        self.coordinate_converter.calibration['field_of_view'] = {
            'horizontal_degrees': horizontal_degrees,
            'vertical_degrees': vertical_degrees
        }
        
        # Guardar calibración
        self._save_calibration()
        
        self.logger.info(f"📏 Campo de visión calibrado: {horizontal_degrees}° x {vertical_degrees}°")
    
    def _save_calibration(self):
        """Guardar calibración actual"""
        try:
            calibration_file = f"calibration_{self.camera_ip.replace('.', '_')}.json"
            with open(calibration_file, 'w') as f:
                json.dump(self.coordinate_converter.calibration, f, indent=2)
            self.logger.info(f"💾 Calibración guardada en {calibration_file}")
        except Exception as e:
            self.logger.error(f"❌ Error guardando calibración: {e}")
    
    def disconnect(self):
        """Desconectar del sistema PTZ"""
        try:
            if self.is_tracking:
                self.stop_tracking()
            
            self.is_connected = False
            self.camera = None
            self.ptz_service = None
            self.profile_token = None
            
            self.logger.info("🔌 Desconectado del sistema PTZ")
            
        except Exception as e:
            self.logger.error(f"❌ Error desconectando: {e}")
    
    def __del__(self):
        """Destructor del sistema"""
        try:
            if hasattr(self, 'is_connected') and self.is_connected:
                self.disconnect()
        except:
            pass

# =====================================================================
# FUNCIONES DE UTILIDAD
# =====================================================================

def create_ptz_system_from_config(config_file: str = "ptz_cameras_config.json", 
                                 camera_id: str = None) -> Optional[ProfessionalPTZSystem]:
    """
    Crear sistema PTZ desde archivo de configuración
    
    Args:
        config_file: Archivo de configuración de cámaras
        camera_id: ID específico de cámara (si None, usa la primera)
        
    Returns:
        ProfessionalPTZSystem o None si hay error
    """
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        cameras = config_data.get('cameras', [])
        if not cameras:
            logging.error("❌ No hay cámaras en la configuración")
            return None
        
        # Seleccionar cámara
        if camera_id:
            camera_config = next((cam for cam in cameras if cam.get('id') == camera_id), None)
            if not camera_config:
                logging.error(f"❌ Cámara {camera_id} no encontrada")
                return None
        else:
            camera_config = cameras[0]  # Primera cámara
        
        # Crear configuración PTZ
        ptz_config_data = camera_config.get('config_personalizada', {})
        ptz_config = PTZConfig(**ptz_config_data)
        
        # Crear sistema PTZ
        ptz_system = ProfessionalPTZSystem(
            camera_ip=camera_config['ip'],
            port=camera_config.get('puerto', 80),
            username=camera_config['usuario'],
            password=camera_config['contrasena'],
            config=ptz_config
        )
        
        logging.info(f"✅ Sistema PTZ creado para {camera_config['nombre']}")
        return ptz_system
        
    except Exception as e:
        logging.error(f"❌ Error creando sistema PTZ: {e}")
        return None

def test_ptz_connection(camera_ip: str, port: int = 80, username: str = "admin", 
                       password: str = "admin123") -> Dict[str, Any]:
    """
    Función rápida para probar conexión PTZ
    
    Returns:
        Dict con resultado de la prueba
    """
    result = {
        'success': False,
        'connection_time': 0.0,
        'can_move': False,
        'position': None,
        'error': None
    }
    
    try:
        config = PTZConfig(confirmation_frames=1, movement_cooldown=0.1)
        ptz = ProfessionalPTZSystem(camera_ip, port, username, password, config)
        
        start_time = time.time()
        connected = ptz.connect()
        result['connection_time'] = time.time() - start_time
        
        if connected:
            result['success'] = True
            result['position'] = asdict(ptz.current_position)
            
            # Probar movimiento mínimo
            test_pos = PTZPosition(
                pan=ptz.current_position.pan + 0.01,
                tilt=ptz.current_position.tilt,
                zoom=ptz.current_position.zoom
            )
            
            move_success = ptz._execute_absolute_move(test_pos, speed=0.1)
            if move_success:
                time.sleep(0.5)
                ptz._execute_absolute_move(ptz.current_position, speed=0.1)
                result['can_move'] = True
        
        ptz.disconnect()
        
    except Exception as e:
        result['error'] = str(e)
    
    return result

# =====================================================================
# FUNCIÓN PRINCIPAL PARA PRUEBAS
# =====================================================================

def main():
    """Función principal para pruebas rápidas"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sistema PTZ Profesional')
    parser.add_argument('--ip', default='19.10.10.217', help='IP de la cámara PTZ')
    parser.add_argument('--port', type=int, default=80, help='Puerto de la cámara')
    parser.add_argument('--username', default='admin', help='Usuario')
    parser.add_argument('--password', default='admin123', help='Contraseña')
    parser.add_argument('--test', action='store_true', help='Ejecutar prueba de conexión')
    parser.add_argument('--demo', action='store_true', help='Ejecutar demo de seguimiento')
    
    args = parser.parse_args()
    
    if args.test:
        print(f"🧪 Probando conexión a {args.ip}:{args.port}")
        result = test_ptz_connection(args.ip, args.port, args.username, args.password)
        
        if result['success']:
            print(f"✅ Conexión exitosa en {result['connection_time']:.2f}s")
            print(f"📍 Posición: {result['position']}")
            print(f"🎯 Puede mover: {'Sí' if result['can_move'] else 'No'}")
        else:
            print(f"❌ Conexión fallida: {result.get('error', 'Error desconocido')}")
        
        return
    
    if args.demo:
        print(f"🚀 Iniciando demo de seguimiento en {args.ip}")
        
        # Crear sistema PTZ
        config = PTZConfig(
            confirmation_frames=2,
            movement_cooldown=1.0,
            movement_prediction=True
        )
        
        ptz = ProfessionalPTZSystem(args.ip, args.port, args.username, args.password, config)
        
        if ptz.connect():
            print("✅ Conectado")
            
            if ptz.start_tracking():
                print("🎯 Seguimiento iniciado")
                
                try:
                    # Simular detecciones
                    detections = [
                        (600, 400, 80, 60, 0.85),
                        (620, 410, 80, 60, 0.87),
                        (640, 420, 80, 60, 0.88),
                        (660, 430, 80, 60, 0.90)
                    ]
                    
                    for i, (x, y, w, h, conf) in enumerate(detections):
                        print(f"📍 Enviando detección {i+1}: ({x}, {y}) conf={conf}")
                        ptz.add_detection(x, y, w, h, conf, 1920, 1080, "demo_object")
                        time.sleep(2.0)
                    
                    # Esperar y mostrar estadísticas
                    time.sleep(5.0)
                    stats = ptz.get_stats()
                    print(f"\n📊 Estadísticas finales:")
                    print(f"   Detecciones totales: {stats['total_detections']}")
                    print(f"   Detecciones confirmadas: {stats['confirmed_detections']}")
                    print(f"   Movimientos ejecutados: {stats['movements_executed']}")
                    
                except KeyboardInterrupt:
                    print("\n⏹️ Demo interrumpido")
                
                finally:
                    ptz.stop_tracking()
            
            ptz.disconnect()
        else:
            print("❌ No se pudo conectar")

if __name__ == "__main__":
    main()