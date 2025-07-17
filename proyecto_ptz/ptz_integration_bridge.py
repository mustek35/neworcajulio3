#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Puente de Integración PTZ con Sistema Existente
Archivo: ptz_integration_bridge.py

Puente de integración entre el sistema PTZ profesional y sistemas existentes:
- Convierte detecciones del formato actual al formato profesional
- Maneja múltiples cámaras PTZ
- Integración transparente con grilla_widget
- Sistema de gestión centralizada
- Monitoreo y estadísticas

Autor: Sistema PTZ Profesional
Versión: 1.0.0
Fecha: 2024
"""

import time
import threading
import json
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging
from collections import defaultdict

# Importar sistema PTZ profesional
try:
    from professional_ptz_system import ProfessionalPTZSystem, PTZConfig, Detection
    PTZ_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Sistema PTZ profesional no disponible: {e}")
    PTZ_SYSTEM_AVAILABLE = False

# =====================================================================
# CLASES DE GESTIÓN Y CONFIGURACIÓN
# =====================================================================

class PTZCameraManager:
    """Gestor de una cámara PTZ individual"""
    
    def __init__(self, camera_id: str, camera_config: Dict, ptz_config: PTZConfig = None):
        self.camera_id = camera_id
        self.camera_config = camera_config
        self.ptz_config = ptz_config or PTZConfig()
        
        # Sistema PTZ
        self.ptz_system: Optional[ProfessionalPTZSystem] = None
        self.is_active = False
        self.connection_attempts = 0
        self.last_connection_attempt = 0.0
        
        # Estadísticas
        self.stats = {
            'detections_received': 0,
            'detections_processed': 0,
            'detections_filtered': 0,
            'last_detection_time': 0.0,
            'session_start': time.time(),
            'uptime': 0.0
        }
        
        # Configuración de logging
        self.logger = logging.getLogger(f"PTZCamera_{camera_id}")
        self._setup_logging()
        
        # Callbacks para eventos
        self.on_target_acquired: Optional[Callable] = None
        self.on_target_lost: Optional[Callable] = None
        self.on_movement_executed: Optional[Callable] = None
        
    def _setup_logging(self):
        """Configurar logging específico para esta cámara"""
        self.logger.setLevel(logging.INFO)
        
        # Handler para archivo específico de cámara
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        log_file = f"logs/ptz_camera_{self.camera_id.replace('.', '_')}.log"
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def initialize(self) -> bool:
        """Inicializar el sistema PTZ para esta cámara"""
        if not PTZ_SYSTEM_AVAILABLE:
            self.logger.error("❌ Sistema PTZ no disponible")
            return False
        
        try:
            self.logger.info(f"🚀 Inicializando PTZ para {self.camera_id}")
            
            # Crear sistema PTZ
            self.ptz_system = ProfessionalPTZSystem(
                camera_ip=self.camera_config['ip'],
                port=self.camera_config.get('puerto', 80),
                username=self.camera_config['usuario'],
                password=self.camera_config['contrasena'],
                config=self.ptz_config
            )
            
            self.logger.info(f"✅ Sistema PTZ creado para {self.camera_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando PTZ: {e}")
            return False
    
    def connect(self) -> bool:
        """Conectar al sistema PTZ"""
        if not self.ptz_system:
            if not self.initialize():
                return False
        
        self.connection_attempts += 1
        self.last_connection_attempt = time.time()
        
        try:
            if self.ptz_system.connect():
                self.is_active = True
                self.logger.info(f"✅ PTZ conectado para {self.camera_id}")
                return True
            else:
                self.logger.error(f"❌ Conexión PTZ fallida para {self.camera_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error conectando PTZ {self.camera_id}: {e}")
            return False
    
    def start_tracking(self) -> bool:
        """Iniciar seguimiento PTZ"""
        if not self.is_active:
            if not self.connect():
                return False
        
        try:
            if self.ptz_system.start_tracking():
                self.stats['session_start'] = time.time()
                self.logger.info(f"🎯 Seguimiento iniciado para {self.camera_id}")
                return True
            else:
                self.logger.error(f"❌ No se pudo iniciar seguimiento para {self.camera_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error iniciando seguimiento {self.camera_id}: {e}")
            return False
    
    def stop_tracking(self):
        """Detener seguimiento PTZ"""
        try:
            if self.ptz_system and self.ptz_system.is_tracking:
                self.ptz_system.stop_tracking()
                self.logger.info(f"⏹️ Seguimiento detenido para {self.camera_id}")
        except Exception as e:
            self.logger.error(f"❌ Error deteniendo seguimiento {self.camera_id}: {e}")
    
    def process_detection(self, detection_data: Dict, frame_size: tuple = (1920, 1080)) -> bool:
        """Procesar una detección"""
        if not self.is_active or not self.ptz_system or not self.ptz_system.is_tracking:
            return False
        
        try:
            self.stats['detections_received'] += 1
            
            # Convertir formato de detección
            x, y, width, height = self._parse_detection_format(detection_data)
            
            if x is None:  # Formato inválido
                self.stats['detections_filtered'] += 1
                return False
            
            # Extraer otros campos
            confidence = detection_data.get('confidence', detection_data.get('conf', 0.0))
            class_name = self._parse_class_name(detection_data)
            track_id = detection_data.get('track_id', detection_data.get('id'))
            
            # Filtro básico de confianza
            if confidence < self.ptz_config.min_confidence:
                self.stats['detections_filtered'] += 1
                return False
            
            # Enviar al sistema PTZ
            self.ptz_system.add_detection(
                x=x, y=y, width=width, height=height,
                confidence=confidence,
                frame_width=frame_size[0],
                frame_height=frame_size[1],
                class_name=class_name,
                track_id=str(track_id) if track_id else None
            )
            
            self.stats['detections_processed'] += 1
            self.stats['last_detection_time'] = time.time()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando detección: {e}")
            return False
    
    def _parse_detection_format(self, detection: Dict) -> tuple:
        """Parsear diferentes formatos de detección"""
        try:
            # Formato 1: bbox = [x1, y1, x2, y2]
            if 'bbox' in detection:
                bbox = detection['bbox']
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                    return float(x1), float(y1), float(x2-x1), float(y2-y1)
            
            # Formato 2: x, y, width, height separados
            if all(k in detection for k in ['x', 'y', 'width', 'height']):
                return (
                    float(detection['x']),
                    float(detection['y']),
                    float(detection['width']),
                    float(detection['height'])
                )
            
            # Formato 3: cx, cy (centro) + width, height
            if all(k in detection for k in ['cx', 'cy', 'width', 'height']):
                cx, cy = float(detection['cx']), float(detection['cy'])
                w, h = float(detection['width']), float(detection['height'])
                return cx - w/2, cy - h/2, w, h
            
            return None, None, None, None
            
        except (ValueError, TypeError, KeyError):
            return None, None, None, None
    
    def _parse_class_name(self, detection: Dict) -> str:
        """Parsear nombre de clase"""
        # Mapeo de clases numéricas a nombres
        class_map = {
            0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
            4: 'airplane', 5: 'bus', 6: 'train', 7: 'truck', 8: 'boat',
            9: 'traffic_light', 10: 'fire_hydrant', 11: 'stop_sign'
        }
        
        # Prioridad: 'class' string, luego 'cls' numérico
        if 'class' in detection:
            return str(detection['class'])
        elif 'cls' in detection:
            cls_id = detection['cls']
            return class_map.get(cls_id, f'class_{cls_id}')
        else:
            return 'object'
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas de esta cámara"""
        current_time = time.time()
        uptime = current_time - self.stats['session_start']
        
        base_stats = {
            **self.stats,
            'uptime': uptime,
            'detection_rate': self.stats['detections_received'] / max(uptime, 1),
            'processing_rate': self.stats['detections_processed'] / max(self.stats['detections_received'], 1),
            'filtering_rate': self.stats['detections_filtered'] / max(self.stats['detections_received'], 1),
            'is_active': self.is_active,
            'connection_attempts': self.connection_attempts,
            'camera_info': {
                'id': self.camera_id,
                'ip': self.camera_config['ip'],
                'name': self.camera_config.get('nombre', self.camera_id)
            }
        }
        
        # Agregar estadísticas del sistema PTZ si está disponible
        if self.ptz_system:
            try:
                ptz_stats = self.ptz_system.get_stats()
                base_stats['ptz_stats'] = ptz_stats
            except Exception as e:
                base_stats['ptz_stats'] = {'error': str(e)}
        
        return base_stats
    
    def disconnect(self):
        """Desconectar la cámara PTZ"""
        try:
            self.stop_tracking()
            if self.ptz_system:
                self.ptz_system.disconnect()
            self.is_active = False
            self.logger.info(f"🔌 PTZ desconectado para {self.camera_id}")
        except Exception as e:
            self.logger.error(f"❌ Error desconectando PTZ {self.camera_id}: {e}")

# =====================================================================
# GESTOR PRINCIPAL DE MÚLTIPLES CÁMARAS PTZ
# =====================================================================

class PTZManager:
    """Gestor principal de múltiples cámaras PTZ"""
    
    def __init__(self, config_file: str = "ptz_cameras_config.json"):
        self.config_file = config_file
        self.cameras: Dict[str, PTZCameraManager] = {}
        self.global_stats = {
            'total_cameras': 0,
            'active_cameras': 0,
            'total_detections': 0,
            'session_start': time.time()
        }
        
        # Threading
        self.running = True
        self.monitor_thread = None
        
        # Configuración de logging
        self.logger = logging.getLogger("PTZManager")
        self._setup_logging()
        
        # Callbacks globales
        self.on_camera_connected: Optional[Callable] = None
        self.on_camera_disconnected: Optional[Callable] = None
        self.on_detection_processed: Optional[Callable] = None
        
        # Cargar configuración
        self._load_configuration()
        
        # Iniciar monitor
        self._start_monitor()
    
    def _setup_logging(self):
        """Configurar logging del gestor principal"""
        self.logger.setLevel(logging.INFO)
        
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # Handler para archivo
        file_handler = logging.FileHandler('logs/ptz_manager.log')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - PTZManager - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def _load_configuration(self):
        """Cargar configuración de cámaras"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                cameras_config = config_data.get('cameras', [])
                self.global_settings = config_data.get('global_settings', {})
                
                self.logger.info(f"📋 Configuración cargada: {len(cameras_config)} cámaras")
                
                # Registrar cámaras automáticamente
                for camera_config in cameras_config:
                    self.register_ptz_camera(camera_config)
                    
            else:
                self.logger.warning(f"⚠️ Archivo de configuración {self.config_file} no encontrado")
                self.global_settings = {}
                
        except Exception as e:
            self.logger.error(f"❌ Error cargando configuración: {e}")
            self.global_settings = {}
    
    def register_ptz_camera(self, camera_data: Dict) -> bool:
        """
        Registrar una cámara PTZ
        
        Args:
            camera_data: {
                'id': 'ptz_main',
                'ip': '19.10.10.217',
                'puerto': 80,
                'usuario': 'admin', 
                'contrasena': 'admin123',
                'nombre': 'PTZ Principal',
                'config_personalizada': {...}
            }
        """
        try:
            camera_id = camera_data.get('id', camera_data['ip'])
            
            if camera_id in self.cameras:
                self.logger.warning(f"📷 Cámara {camera_id} ya registrada")
                return True
            
            # Crear configuración PTZ personalizada
            ptz_config_data = camera_data.get('config_personalizada', {})
            ptz_config = PTZConfig(**ptz_config_data)
            
            # Crear gestor de cámara
            camera_manager = PTZCameraManager(camera_id, camera_data, ptz_config)
            
            # Registrar cámara
            self.cameras[camera_id] = camera_manager
            self.global_stats['total_cameras'] += 1
            
            self.logger.info(f"📷 Cámara PTZ registrada: {camera_id} ({camera_data.get('nombre', 'Sin nombre')})")
            
            # Callback de registro
            if self.on_camera_connected:
                self.on_camera_connected(camera_id, camera_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error registrando cámara PTZ: {e}")
            return False
    
    def connect_camera(self, camera_id: str) -> bool:
        """Conectar una cámara PTZ específica"""
        if camera_id not in self.cameras:
            self.logger.error(f"❌ Cámara {camera_id} no registrada")
            return False
        
        try:
            camera_manager = self.cameras[camera_id]
            
            if camera_manager.connect():
                self.global_stats['active_cameras'] += 1
                self.logger.info(f"✅ Cámara PTZ {camera_id} conectada")
                return True
            else:
                self.logger.error(f"❌ No se pudo conectar a cámara PTZ {camera_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error conectando cámara PTZ {camera_id}: {e}")
            return False
    
    def connect_all_cameras(self) -> Dict[str, bool]:
        """Conectar todas las cámaras registradas"""
        results = {}
        
        self.logger.info(f"🔗 Conectando {len(self.cameras)} cámaras PTZ...")
        
        for camera_id in self.cameras:
            results[camera_id] = self.connect_camera(camera_id)
        
        successful = sum(1 for success in results.values() if success)
        self.logger.info(f"✅ Conectadas {successful}/{len(self.cameras)} cámaras PTZ")
        
        return results
    
    def start_tracking(self, camera_id: str) -> bool:
        """Iniciar seguimiento para una cámara específica"""
        if camera_id not in self.cameras:
            self.logger.error(f"❌ Cámara {camera_id} no registrada")
            return False
        
        camera_manager = self.cameras[camera_id]
        
        if not camera_manager.is_active:
            # Intentar conectar primero
            if not self.connect_camera(camera_id):
                return False
        
        try:
            success = camera_manager.start_tracking()
            
            if success:
                self.logger.info(f"🚀 Seguimiento PTZ iniciado para {camera_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Error iniciando seguimiento PTZ {camera_id}: {e}")
            return False
    
    def start_all_tracking(self) -> Dict[str, bool]:
        """Iniciar seguimiento para todas las cámaras conectadas"""
        results = {}
        
        active_cameras = [cid for cid, cam in self.cameras.items() if cam.is_active]
        self.logger.info(f"🚀 Iniciando seguimiento en {len(active_cameras)} cámaras...")
        
        for camera_id in active_cameras:
            results[camera_id] = self.start_tracking(camera_id)
        
        successful = sum(1 for success in results.values() if success)
        self.logger.info(f"✅ Seguimiento iniciado en {successful}/{len(active_cameras)} cámaras")
        
        return results
    
    def stop_tracking(self, camera_id: str):
        """Detener seguimiento para una cámara específica"""
        if camera_id in self.cameras:
            try:
                self.cameras[camera_id].stop_tracking()
                self.logger.info(f"⏹️ Seguimiento PTZ detenido para {camera_id}")
            except Exception as e:
                self.logger.error(f"❌ Error deteniendo seguimiento PTZ {camera_id}: {e}")
    
    def stop_all_tracking(self):
        """Detener seguimiento para todas las cámaras"""
        tracking_cameras = [cid for cid, cam in self.cameras.items() 
                           if cam.is_active and cam.ptz_system and cam.ptz_system.is_tracking]
        
        self.logger.info(f"⏹️ Deteniendo seguimiento en {len(tracking_cameras)} cámaras...")
        
        for camera_id in tracking_cameras:
            self.stop_tracking(camera_id)
    
    def add_detection(self, camera_id: str, detection_data: Dict, frame_size: tuple = (1920, 1080)) -> bool:
        """
        Agregar detección para procesamiento PTZ
        
        Args:
            camera_id: ID de la cámara
            detection_data: Datos de la detección en cualquier formato soportado
            frame_size: Tamaño del frame (width, height)
        """
        if camera_id not in self.cameras:
            return False
        
        try:
            camera_manager = self.cameras[camera_id]
            success = camera_manager.process_detection(detection_data, frame_size)
            
            if success:
                self.global_stats['total_detections'] += 1
                
                # Callback global
                if self.on_detection_processed:
                    self.on_detection_processed(camera_id, detection_data)
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando detección para {camera_id}: {e}")
            return False
    
    def get_camera_stats(self, camera_id: str) -> Optional[Dict]:
        """Obtener estadísticas de una cámara específica"""
        if camera_id in self.cameras:
            return self.cameras[camera_id].get_stats()
        return None
    
    def get_all_stats(self) -> Dict:
        """Obtener estadísticas de todas las cámaras"""
        stats = {
            'manager_stats': {
                **self.global_stats,
                'uptime': time.time() - self.global_stats['session_start'],
                'registered_cameras': len(self.cameras),
                'active_cameras': sum(1 for cam in self.cameras.values() if cam.is_active),
                'tracking_cameras': sum(1 for cam in self.cameras.values() 
                                      if cam.is_active and cam.ptz_system and cam.ptz_system.is_tracking)
            },
            'cameras': {}
        }
        
        for camera_id, camera_manager in self.cameras.items():
            stats['cameras'][camera_id] = {
                'camera_name': camera_manager.camera_config.get('nombre', camera_id),
                'ip': camera_manager.camera_config['ip'],
                'active': camera_manager.is_active,
                'tracking': (camera_manager.ptz_system.is_tracking 
                           if camera_manager.ptz_system else False),
                'stats': camera_manager.get_stats()
            }
        
        return stats
    
    def get_system_health(self) -> Dict:
        """Obtener estado de salud del sistema"""
        health = {
            'overall_status': 'healthy',
            'issues': [],
            'cameras_status': {},
            'recommendations': []
        }
        
        for camera_id, camera_manager in self.cameras.items():
            camera_health = {
                'status': 'healthy',
                'issues': []
            }
            
            # Verificar conexión
            if not camera_manager.is_active:
                camera_health['status'] = 'disconnected'
                camera_health['issues'].append('Camera not connected')
            
            # Verificar actividad reciente
            elif camera_manager.stats['last_detection_time'] > 0:
                time_since_last = time.time() - camera_manager.stats['last_detection_time']
                if time_since_last > 300:  # 5 minutos sin detecciones
                    camera_health['status'] = 'inactive'
                    camera_health['issues'].append(f'No detections for {time_since_last/60:.1f} minutes')
            
            # Verificar errores de conexión
            if camera_manager.connection_attempts > 3:
                camera_health['issues'].append(f'Multiple connection attempts: {camera_manager.connection_attempts}')
            
            health['cameras_status'][camera_id] = camera_health
            
            # Agregar a issues globales si hay problemas
            if camera_health['status'] != 'healthy':
                health['issues'].extend([f"{camera_id}: {issue}" for issue in camera_health['issues']])
        
        # Determinar estado general
        unhealthy_cameras = sum(1 for status in health['cameras_status'].values() 
                              if status['status'] != 'healthy')
        
        if unhealthy_cameras == 0:
            health['overall_status'] = 'healthy'
        elif unhealthy_cameras < len(self.cameras) / 2:
            health['overall_status'] = 'degraded'
        else:
            health['overall_status'] = 'critical'
        
        # Generar recomendaciones
        if unhealthy_cameras > 0:
            health['recommendations'].append('Check camera connectivity and credentials')
        
        inactive_cameras = sum(1 for status in health['cameras_status'].values() 
                             if status['status'] == 'inactive')
        if inactive_cameras > 0:
            health['recommendations'].append('Verify detection system is sending data to PTZ')
        
        return health
    
    def _start_monitor(self):
        """Iniciar hilo de monitoreo"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.logger.info("📊 Monitor del sistema iniciado")
    
    def _monitor_loop(self):
        """Bucle de monitoreo del sistema"""
        last_health_check = 0
        health_check_interval = 60  # Check cada minuto
        
        while self.running:
            try:
                current_time = time.time()
                
                # Health check periódico
                if current_time - last_health_check > health_check_interval:
                    health = self.get_system_health()
                    
                    if health['overall_status'] != 'healthy':
                        self.logger.warning(f"⚠️ Sistema PTZ: {health['overall_status']}")
                        for issue in health['issues'][:3]:  # Solo primeros 3 issues
                            self.logger.warning(f"   - {issue}")
                    
                    last_health_check = current_time
                
                time.sleep(10)  # Check cada 10 segundos
                
            except Exception as e:
                self.logger.error(f"❌ Error en monitor: {e}")
                time.sleep(30)
    
    def disconnect_camera(self, camera_id: str):
        """Desconectar una cámara específica"""
        if camera_id in self.cameras:
            try:
                camera_manager = self.cameras[camera_id]
                camera_manager.disconnect()
                
                if camera_manager.is_active:
                    self.global_stats['active_cameras'] -= 1
                
                self.logger.info(f"🔌 Cámara PTZ {camera_id} desconectada")
                
                # Callback de desconexión
                if self.on_camera_disconnected:
                    self.on_camera_disconnected(camera_id)
                    
            except Exception as e:
                self.logger.error(f"❌ Error desconectando cámara {camera_id}: {e}")
    
    def disconnect_all_cameras(self):
        """Desconectar todas las cámaras"""
        self.logger.info("🔌 Desconectando todas las cámaras PTZ...")
        
        for camera_id in list(self.cameras.keys()):
            self.disconnect_camera(camera_id)
    
    def shutdown(self):
        """Cerrar el sistema PTZ completo"""
        self.logger.info("🔄 Cerrando sistema PTZ...")
        
        # Detener monitoreo
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        # Detener seguimiento y desconectar cámaras
        self.stop_all_tracking()
        self.disconnect_all_cameras()
        
        self.logger.info("✅ Sistema PTZ cerrado completamente")
    
    def export_configuration(self, filename: str = None) -> str:
        """Exportar configuración actual del sistema"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ptz_config_export_{timestamp}.json"
        
        try:
            export_data = {
                'export_info': {
                    'timestamp': datetime.now().isoformat(),
                    'version': '1.0.0',
                    'total_cameras': len(self.cameras)
                },
                'global_settings': self.global_settings,
                'cameras': []
            }
            
            for camera_id, camera_manager in self.cameras.items():
                camera_export = {
                    **camera_manager.camera_config,
                    'id': camera_id,
                    'config_personalizada': camera_manager.ptz_config.__dict__,
                    'stats_snapshot': camera_manager.get_stats()
                }
                export_data['cameras'].append(camera_export)
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            self.logger.info(f"📤 Configuración exportada a {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"❌ Error exportando configuración: {e}")
            return ""

# =====================================================================
# FUNCIONES DE UTILIDAD E INTEGRACIÓN
# =====================================================================

def create_ptz_manager_from_config(config_file: str = "ptz_cameras_config.json") -> PTZManager:
    """Crear gestor PTZ desde archivo de configuración"""
    return PTZManager(config_file)

def test_camera_connection(camera_ip: str, port: int = 80, username: str = "admin", 
                          password: str = "admin123") -> Dict[str, Any]:
    """Función rápida para probar conexión de una cámara"""
    try:
        from professional_ptz_system import test_ptz_connection
        return test_ptz_connection(camera_ip, port, username, password)
    except ImportError:
        return {
            'success': False,
            'error': 'Sistema PTZ profesional no disponible'
        }

# =====================================================================
# INTEGRACIÓN CON SISTEMA EXISTENTE
# =====================================================================

class GrillaWidgetPTZIntegration:
    """Clase helper para integrar con grilla_widget"""
    
    def __init__(self, ptz_manager: PTZManager):
        self.ptz_manager = ptz_manager
        self.camera_mappings = {}  # Mapeo de grillas a cámaras PTZ
        
    def register_grilla(self, grilla_widget, camera_data: Dict):
        """Registrar una grilla con el sistema PTZ"""
        try:
            camera_ip = camera_data.get('ip')
            if not camera_ip:
                return False
            
            # Verificar si es cámara PTZ
            if camera_data.get('tipo') == 'ptz':
                # Registrar en el gestor PTZ
                self.ptz_manager.register_ptz_camera(camera_data)
                self.camera_mappings[id(grilla_widget)] = camera_ip
                
                # Agregar método al grilla_widget
                grilla_widget.send_detection_to_ptz = lambda detection, frame_size=(1920, 1080): \
                    self.ptz_manager.add_detection(camera_ip, detection, frame_size)
                
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Error registrando grilla PTZ: {e}")
            return False
    
    def start_ptz_for_grilla(self, grilla_widget) -> bool:
        """Iniciar PTZ para una grilla específica"""
        grilla_id = id(grilla_widget)
        if grilla_id in self.camera_mappings:
            camera_ip = self.camera_mappings[grilla_id]
            return self.ptz_manager.start_tracking(camera_ip)
        return False
    
    def stop_ptz_for_grilla(self, grilla_widget):
        """Detener PTZ para una grilla específica"""
        grilla_id = id(grilla_widget)
        if grilla_id in self.camera_mappings:
            camera_ip = self.camera_mappings[grilla_id]
            self.ptz_manager.stop_tracking(camera_ip)

# =====================================================================
# FUNCIÓN PRINCIPAL PARA PRUEBAS
# =====================================================================

def main():
    """Función principal para pruebas del bridge"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PTZ Integration Bridge')
    parser.add_argument('--config', default='ptz_cameras_config.json', help='Archivo de configuración')
    parser.add_argument('--test', action='store_true', help='Ejecutar pruebas')
    parser.add_argument('--monitor', action='store_true', help='Modo monitor')
    
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Probando bridge de integración PTZ...")
        
        # Crear gestor
        manager = PTZManager(args.config)
        
        # Mostrar cámaras registradas
        print(f"📷 Cámaras registradas: {len(manager.cameras)}")
        for camera_id, camera_manager in manager.cameras.items():
            print(f"   - {camera_id}: {camera_manager.camera_config['ip']}")
        
        # Intentar conectar todas
        results = manager.connect_all_cameras()
        print(f"✅ Conexiones exitosas: {sum(results.values())}/{len(results)}")
        
        # Mostrar estadísticas
        stats = manager.get_all_stats()
        print(f"📊 Estadísticas: {stats['manager_stats']}")
        
        manager.shutdown()
        return
    
    if args.monitor:
        print("📊 Iniciando monitor PTZ...")
        
        manager = PTZManager(args.config)
        
        try:
            while True:
                health = manager.get_system_health()
                stats = manager.get_all_stats()
                
                print(f"\n📊 Estado del Sistema PTZ - {datetime.now().strftime('%H:%M:%S')}")
                print(f"   Estado general: {health['overall_status']}")
                print(f"   Cámaras activas: {stats['manager_stats']['active_cameras']}")
                print(f"   Detecciones totales: {stats['manager_stats']['total_detections']}")
                
                if health['issues']:
                    print("⚠️ Problemas detectados:")
                    for issue in health['issues'][:3]:
                        print(f"   - {issue}")
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n⏹️ Monitor detenido")
        finally:
            manager.shutdown()

if __name__ == "__main__":
    main()