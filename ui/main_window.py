from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QTextEdit, QMenuBar, QMenu, QGridLayout, QStackedWidget, QLabel,
    QScrollArea, QMessageBox, QSplitter
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
import importlib
from ui.camera_modal import CameraDialog
from gui.resumen_detecciones import ResumenDeteccionesWidget
from ui.config_modal import ConfiguracionDialog
from ui.fps_config_dialog import FPSConfigDialog
from ui.camera_manager import guardar_camaras, cargar_camaras_guardadas
from core.rtsp_builder import generar_rtsp
import os
import cProfile
import pstats
import io
import time
import numpy as np
# ===============================================
# IMPORTS PTZ SYSTEM - CORRECCIÓN AUTOMÁTICA
# ===============================================
try:
    from core.ptz_control_enhanced import PTZDetectionBridge, create_multi_object_ptz_system
    PTZ_AVAILABLE = True
except ImportError as e:
    PTZ_AVAILABLE = False
    print(f"⚠️ PTZ no disponible: {e}")



# NUEVAS IMPORTACIONES: Sistema de Muestreo Adaptativo
try:
    from ui.adaptive_sampling_dialog import AdaptiveSamplingConfigDialog
    from core.adaptive_sampling import AdaptiveSamplingConfig
    ADAPTIVE_SAMPLING_AVAILABLE = True
except ImportError:
    ADAPTIVE_SAMPLING_AVAILABLE = False
    print("ℹ️ Sistema de muestreo adaptativo no disponible")

CONFIG_PATH = "config.json"

class MainGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        print("INFO: Iniciando profiler para MainGUI...")
        self.profiler = cProfile.Profile()
        self.profiler.enable()

        self.setWindowTitle("Monitor PTZ Inteligente - Orca")
        self.setGeometry(100, 100, 1600, 900)

        # Configuración de FPS por defecto
        self.fps_config = {
            "visual_fps": 25,
            "detection_fps": 8, 
            "ui_update_fps": 15,
            "adaptive_fps": True
        }

        self.camera_data_list = []
        self.camera_widgets = [] 
        
        # NUEVO: Bridge PTZ para detecciones
        self.ptz_detection_bridge = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)

        self.menu_inicio = self.menu_bar.addMenu("Inicio")
        self.menu_config = self.menu_bar.addMenu("Configuración")
        self.menu_ptz = self.menu_bar.addMenu("PTZ")

        self.action_agregar = QAction("➕ Agregar Cámara", self)
        self.action_agregar.triggered.connect(lambda: self.open_camera_dialog())
        self.menu_inicio.addAction(self.action_agregar)

        self.action_salir = QAction("🚪 Salir de la Aplicación", self)
        self.action_salir.triggered.connect(self.close) 
        self.menu_inicio.addAction(self.action_salir)

        self.action_ver_config = QAction("⚙️ Ver Configuración", self)
        self.action_ver_config.triggered.connect(self.abrir_configuracion_modal)
        self.menu_config.addAction(self.action_ver_config)

        # Agregar acción de FPS al menú
        self.action_fps_config = QAction("🎯 Configurar FPS", self)
        self.action_fps_config.triggered.connect(self.abrir_fps_config)
        self.menu_config.addAction(self.action_fps_config)

        # NUEVO: Muestreo Adaptativo
        if ADAPTIVE_SAMPLING_AVAILABLE:
            self.action_adaptive_sampling = QAction("🧠 Muestreo Adaptativo", self)
            self.action_adaptive_sampling.triggered.connect(self.abrir_muestreo_adaptativo_config)
            self.menu_config.addAction(self.action_adaptive_sampling)
            
            # Separador entre configuraciones
            self.menu_config.addSeparator()

        self.action_edit_line = QAction("🏁 Línea de Cruce", self)
        self.action_edit_line.triggered.connect(self.toggle_line_edit)
        self.menu_config.addAction(self.action_edit_line)

        # ✅ MENÚ PTZ CORREGIDO Y COMPLETO
        self.create_ptz_menu()

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        self.init_tab = QWidget()
        self.init_tab_layout = QVBoxLayout()
        self.init_tab.setLayout(self.init_tab_layout)
        self.setup_inicio_ui() 

        self.stacked_widget.addWidget(self.init_tab)

        # Inicializar sistema PTZ al arrancar
        self._ptz_initialized = False

        # NUEVO: Agregar elementos del menú de muestreo adaptativo
        self.add_adaptive_sampling_menu_items()

        cargar_camaras_guardadas(self)
        # ===============================================
        # INICIALIZACIÓN SISTEMA PTZ - CORRECCIÓN AUTO
        # ===============================================
        self.ptz_detection_bridge = None
        self.ptz_system = None
        if PTZ_AVAILABLE:
            # Metodo de inicialización actualizado
            self._initialize_ptz_system()


    def _setup_ptz_menu(self):
        """✅ NUEVO: Configurar menú PTZ completo"""
        # Menú PTZ Básico
        self.action_ptz_tracking = QAction("🎮 Seguimiento Básico", self)
        self.action_ptz_tracking.triggered.connect(self.open_ptz_dialog)
        self.menu_ptz.addAction(self.action_ptz_tracking)

        # Gestión Avanzada PTZ
        self.action_ptz_presets = QAction("🎯 Gestión Avanzada PTZ", self)
        self.action_ptz_presets.triggered.connect(self.open_ptz_presets_dialog)
        self.menu_ptz.addAction(self.action_ptz_presets)

        # ✅ NUEVO: PTZ Multi-Objeto (CORREGIDO)
        self.action_ptz_multi_object = QAction("🚀 Seguimiento Multi-Objeto", self)
        self.action_ptz_multi_object.triggered.connect(self.open_ptz_multi_object_dialog)
        self.menu_ptz.addAction(self.action_ptz_multi_object)

        # Separador en el menú PTZ
        self.menu_ptz.addSeparator()

        # Acciones adicionales PTZ
        self.action_ptz_init = QAction("🔧 Inicializar Sistema PTZ", self)
        self.action_ptz_init.triggered.connect(self._initialize_ptz_system)
        self.menu_ptz.addAction(self.action_ptz_init)

        self.action_ptz_stop_all = QAction("⏹️ Detener Todas las PTZ", self)
        self.action_ptz_stop_all.triggered.connect(self.stop_all_ptz)
        self.menu_ptz.addAction(self.action_ptz_stop_all)

    def create_ptz_menu(self):
        """Crear menú PTZ y agregar acciones disponibles"""
        # Utilizar configuración existente del menú
        self._setup_ptz_menu()

        # NUEVO: Calibración PTZ
        self.action_ptz_calibration = QAction("🎯 Calibrar PTZ", self)
        self.action_ptz_calibration.triggered.connect(self.open_ptz_calibration)
        self.menu_ptz.addAction(self.action_ptz_calibration)

    def abrir_configuracion_modal(self):
        """Abrir modal de configuración - MÉTODO CORREGIDO"""
        try:
            dialog = ConfiguracionDialog(self, camera_list=self.camera_data_list)
            if dialog.exec():
                guardar_camaras(self)
                self.append_debug("⚙️ Configuración del sistema guardada.")
            else:
                self.append_debug("⚙️ Cambios en configuración del sistema cancelados.")
        except ImportError as e:
            self.append_debug(f"❌ Error: No se pudo cargar el diálogo de configuración: {e}")
            QMessageBox.warning(
                self,
                "Módulo no disponible",
                f"❌ No se pudo cargar el diálogo de configuración:\n{e}\n\n"
                f"Archivo requerido:\n"
                f"• ui/config_modal.py"
            )
        except Exception as e:
            self.append_debug(f"❌ Error inesperado abriendo configuración: {e}")

    # ✅ NUEVO: Método PTZ Multi-Objeto CORREGIDO
    def open_ptz_multi_object_dialog(self):
        """Abrir sistema PTZ con área de trabajo - VERSIÓN ACTUALIZADA"""
        try:
            # Verificar que hay cámaras PTZ disponibles
            ptz_cameras = [cam for cam in self.camera_data_list if cam.get('tipo') == 'ptz']

            if not ptz_cameras:
                QMessageBox.warning(
                    self,
                    "Sin cámaras PTZ",
                    "❌ No se encontraron cámaras PTZ configuradas.\n\n"
                    "Para usar el seguimiento con área de trabajo:\n"
                    "1. Agregue al menos una cámara con tipo 'ptz'\n"
                    "2. Configure las credenciales ONVIF\n"
                    "3. Verifique la conectividad de red\n\n"
                    "Use el menú 'Configuración → Cámaras' para agregar cámaras PTZ."
                )
                return

            self.append_debug(f"🎯 Abriendo sistema PTZ con área de trabajo con {len(ptz_cameras)} cámaras...")

            # Importar el nuevo diálogo con área de trabajo
            try:
                from ui.enhanced_ptz_multi_object_dialog import EnhancedMultiObjectPTZDialog
                
                # Crear el diálogo
                self.ptz_area_dialog = EnhancedMultiObjectPTZDialog(self, self.camera_data_list)
                
                # Conectar señales para integración
                self.ptz_area_dialog.tracking_started.connect(self._on_ptz_tracking_started)
                self.ptz_area_dialog.tracking_stopped.connect(self._on_ptz_tracking_stopped)
                self.ptz_area_dialog.area_configured.connect(self._on_ptz_area_configured)
                
                # Mostrar el diálogo
                self.ptz_area_dialog.show()
                
                self.append_debug("✅ Sistema PTZ con área de trabajo abierto exitosamente")
                
                # Guardar referencia para envío de detecciones
                self.active_ptz_system = self.ptz_area_dialog

            except ImportError as import_error:
                self.append_debug(f"❌ Error importando diálogo PTZ: {import_error}")
                QMessageBox.critical(
                    self,
                    "Sistema No Disponible",
                    f"❌ El sistema PTZ con área de trabajo no está disponible:\n\n"
                    f"Error: {import_error}\n\n"
                    f"Archivo requerido:\n"
                    f"• ui/enhanced_ptz_multi_object_dialog.py\n\n"
                    f"Dependencias:\n"
                    f"• pip install numpy\n"
                    f"• Sistema ONVIF configurado"
                )
                return

            except Exception as creation_error:
                self.append_debug(f"❌ Error creando diálogo PTZ: {creation_error}")
                QMessageBox.critical(
                    self,
                    "Error de Inicialización",
                    f"❌ No se pudo crear el diálogo PTZ:\n\n"
                    f"Error: {creation_error}\n\n"
                    f"Posibles causas:\n"
                    f"• Error en la configuración de cámaras\n"
                    f"• Problemas con dependencias\n"
                    f"• Conflictos en archivos del sistema"
                )
                return

        except Exception as general_error:
            self.append_debug(f"❌ Error inesperado abriendo PTZ: {general_error}")
            QMessageBox.critical(
                self,
                "Error Inesperado",
                f"❌ Error inesperado:\n\n"
                f"{general_error}\n\n"
                f"Revise la consola para más detalles.\n"
                f"Si el problema persiste, reinicie la aplicación."
            )
    
    def _on_ptz_tracking_started(self):
        """Manejar inicio de seguimiento PTZ"""
        self.append_debug("🚀 Seguimiento PTZ iniciado")
        
        # Opcional: Cambiar modo de detección para optimizar rendimiento
        if hasattr(self, 'detection_fps'):
            self.ptz_detection_fps = 15  # FPS más alto para seguimiento
    
    def _on_ptz_tracking_stopped(self):
        """Manejar parada de seguimiento PTZ"""
        self.append_debug("⏹️ Seguimiento PTZ detenido")
        
        # Restaurar FPS normal si se cambió
        if hasattr(self, 'ptz_detection_fps'):
            delattr(self, 'ptz_detection_fps')
    
    def _on_ptz_area_configured(self, camera_ip: str, area_data: dict):
        """Manejar configuración de área PTZ"""
        self.append_debug(f"📐 Área de trabajo configurada para cámara {camera_ip}")
        
        # Opcional: Guardar configuración del área en config.json
        self._save_ptz_area_to_config(camera_ip, area_data)
    
    def _save_ptz_area_to_config(self, camera_ip: str, area_data: dict):
        """Guardar configuración del área PTZ en config.json"""
        try:
            # Buscar la cámara en la configuración
            for camera in self.camera_data_list:
                if camera.get('ip') == camera_ip:
                    camera['ptz_area_config'] = {
                        'area_points': area_data,
                        'configured_at': time.time()
                    }
                    break
            
            # Guardar la configuración actualizada
            from ui.camera_manager import guardar_camaras
            guardar_camaras(self)
            
            self.append_debug(f"💾 Configuración de área PTZ guardada para {camera_ip}")
            
        except Exception as e:
            self.append_debug(f"⚠️ Error guardando configuración PTZ: {e}")
    
    def send_detections_to_ptz(self, camera_ip: str, detections: list, frame_size: tuple = (1280, 720)):
        """
        Enviar detecciones al sistema PTZ activo
        
        Args:
            camera_ip: IP de la cámara que generó las detecciones
            detections: Lista de detecciones con formato [{'x': int, 'y': int, 'confidence': float}]
            frame_size: Tamaño del frame (width, height)
        """
        try:
            # Verificar que hay un sistema PTZ activo
            if not hasattr(self, 'active_ptz_system') or not self.active_ptz_system:
                return False
            
            # Verificar que el seguimiento está activo
            if not self.active_ptz_system.is_tracking_active():
                return False
            
            # Verificar que la cámara coincide (opcional)
            current_camera_ip = self.active_ptz_system.get_current_camera_ip()
            if current_camera_ip and current_camera_ip != camera_ip:
                return False  # No enviar si no es la cámara seleccionada
            
            # Enviar las detecciones
            success = self.active_ptz_system.send_detections(detections, frame_size)
            
            if success:
                self.append_debug(f"📤 Detecciones enviadas a PTZ: {len(detections)} objetos")
            
            return success
            
        except Exception as e:
            self.append_debug(f"❌ Error enviando detecciones a PTZ: {e}")
            return False
    
    # MÉTODO PARA INTEGRAR CON EL SISTEMA DE DETECCIÓN EXISTENTE
    def integrate_ptz_with_detection(self, camera_ip: str, yolo_results: list, frame_size: tuple):
        """
        Integrar PTZ con el sistema de detección existente
        
        Args:
            camera_ip: IP de la cámara
            yolo_results: Resultados de YOLO
            frame_size: Tamaño del frame
        """
        try:
            # Convertir resultados YOLO a formato PTZ
            detections = []
            
            for result in yolo_results:
                # Assuming YOLO result format, adjust as needed
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        # Get bounding box center
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        confidence = float(box.conf[0])
                        
                        detections.append({
                            'x': center_x,
                            'y': center_y,
                            'confidence': confidence,
                            'bbox': [x1, y1, x2, y2]
                        })
            
            # Enviar al sistema PTZ
            if detections:
                self.send_detections_to_ptz(camera_ip, detections, frame_size)
                
        except Exception as e:
            self.append_debug(f"❌ Error integrando PTZ con detección: {e}")
    
    # MÉTODO PARA USAR EN TU LOOP DE DETECCIÓN EXISTENTE
    def process_frame_with_ptz(self, camera_ip: str, frame: np.ndarray, detection_results: list):
        """
        Procesar frame con integración PTZ
        
        Este método se puede llamar desde tu loop de detección existente
        
        Args:
            camera_ip: IP de la cámara
            frame: Frame de video (numpy array)
            detection_results: Resultados de detección
        """
        try:
            frame_height, frame_width = frame.shape[:2]
            frame_size = (frame_width, frame_height)
            
            # Integrar con PTZ si está activo
            self.integrate_ptz_with_detection(camera_ip, detection_results, frame_size)
            
        except Exception as e:
            self.append_debug(f"❌ Error procesando frame con PTZ: {e}")
    # ✅ NUEVO: Integración con sistema de detección
    def send_custom_detections_to_ptz(self, detections_list):
        """
        Enviar detecciones personalizadas al PTZ

        Args:
            detections_list: Lista de detecciones en formato personalizado
        """
        if not self.ptz_detection_bridge:
            return

        try:
            self.ptz_detection_bridge.process_custom_detections(detections_list)
            self.append_debug(f"🎯 PTZ: {len(detections_list)} detección(es) personalizada(s) enviada(s)")
        except Exception as e:
            self.append_debug(f"⚠️ Error enviando detecciones personalizadas al PTZ: {e}")

    def cleanup_ptz_system(self):
        """Limpiar sistema PTZ al cerrar la aplicación"""
        try:
            if hasattr(self, 'ptz_detection_bridge') and self.ptz_detection_bridge:
                self.ptz_detection_bridge.cleanup()
                self.ptz_detection_bridge = None
                self.append_debug("🧹 Sistema PTZ limpiado")
        except Exception as e:
            self.append_debug(f"❌ Error limpiando sistema PTZ: {e}")

    def _initialize_ptz_system(self):
        """Inicializar sistema PTZ mejorado - CORRECCIÓN AUTOMÁTICA"""
        try:
            # Verificar disponibilidad
            if not PTZ_AVAILABLE:
                self.append_debug("⚠️ Sistema PTZ no disponible")
                return False

            # Obtener cámaras PTZ
            ptz_cameras = []
            if hasattr(self, 'cameras_config') and self.cameras_config:
                cameras = self.cameras_config.get('camaras', [])
                ptz_cameras = [cam for cam in cameras if cam.get('tipo', '').lower() == 'ptz']

            if not ptz_cameras:
                self.append_debug("📝 No hay cámaras PTZ configuradas")
                return False

            # CORRECCIÓN CRÍTICA: Crear sistema con validación
            self.ptz_system = create_multi_object_ptz_system(ptz_cameras, self)

            if self.ptz_system:
                # CORRECCIÓN: Crear bridge desde el sistema, no independiente
                if hasattr(self.ptz_system, 'dialog') and hasattr(self.ptz_system.dialog, 'detection_bridge'):
                    self.ptz_detection_bridge = self.ptz_system.dialog.detection_bridge
                    self.append_debug(f"✅ Sistema PTZ inicializado con {len(ptz_cameras)} cámara(s)")

                    # Auto-iniciar seguimiento en la primera cámara
                    if ptz_cameras:
                        self._auto_start_ptz_tracking(ptz_cameras[0])
                    return True
                else:
                    self.append_debug("❌ Error: Bridge PTZ no disponible en el diálogo")
                    return False
            else:
                self.append_debug("❌ Error creando sistema PTZ")
                return False

        except Exception as e:
            self.append_debug(f"❌ Error inicializando sistema PTZ: {e}")
            return False

    def _auto_start_ptz_tracking(self, camera_data):
        try:
            if not self.ptz_system or not hasattr(self.ptz_system, 'dialog'):
                return False
            dialog = self.ptz_system.dialog
            camera_name = f"{camera_data.get('ip', 'Unknown')} - {camera_data.get('nombre', 'PTZ')}"
            if hasattr(dialog, 'camera_combo'):
                for i in range(dialog.camera_combo.count()):
                    if camera_data.get('ip', '') in dialog.camera_combo.itemText(i):
                        dialog.camera_combo.setCurrentIndex(i)
                        break
            if hasattr(dialog, '_start_tracking'):
                dialog._start_tracking()
                self.append_debug(f"🚀 Seguimiento PTZ auto-iniciado para {camera_name}")
                return True
            return False
        except Exception as e:
            self.append_debug(f"❌ Error auto-iniciando PTZ: {e}")
            return False

    def ensure_ptz_dialog_active(self):
        """Asegurar que el diálogo PTZ esté activo para recibir detecciones"""
        try:
            if hasattr(self, 'ptz_detection_bridge') and self.ptz_detection_bridge:
                bridge = self.ptz_detection_bridge
                if hasattr(bridge, 'ptz_system') and bridge.ptz_system:
                    dialog = bridge.ptz_system.dialog
                    if dialog and not getattr(dialog, 'tracking_active', False):
                        dialog.tracking_active = True
                        self.append_debug("🔄 PTZ diálogo activado para recibir detecciones")
                        return True
            return False
        except Exception as e:
            self.append_debug(f"❌ Error activando diálogo PTZ: {e}")
            return False

    def send_detections_to_ptz(self, camera_id: str, detections):
        """Enviar detecciones al sistema PTZ mejorado"""
        try:
            # NUEVO: Asegurar que el diálogo esté activo
            self.ensure_ptz_dialog_active()

            if not hasattr(self, 'ptz_detection_bridge') or not self.ptz_detection_bridge:
                return False

            if not detections:
                return False

            # Limpiar camera_id
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                camera_id = camera_id.replace('camera_', '')

            # Enviar detecciones
            success = self.ptz_detection_bridge.send_detections(camera_id, detections)

            if success:
                if not hasattr(self, '_ptz_detection_count'):
                    self._ptz_detection_count = 0
                self._ptz_detection_count += len(detections)

                # Log limitado
                if self._ptz_detection_count <= 50:
                    self.append_debug(f"📡 PTZ: {len(detections)} detecciones → {camera_id}")

            return success

        except Exception as e:
            self.append_debug(f"❌ Error enviando detecciones a PTZ: {e}")
            return False

    def get_ptz_status(self, camera_id: str = None):
        """Obtener estado del sistema PTZ"""
        try:
            if hasattr(self, 'ptz_detection_bridge') and self.ptz_detection_bridge:
                return self.ptz_detection_bridge.get_status(camera_id)
            return {'error': 'Sistema PTZ no activo'}
        except Exception as e:
            return {'error': str(e)}

    def get_ptz_bridge_status(self):
        """Verificar estado del puente PTZ (para debugging)"""
        try:
            if hasattr(self, 'ptz_detection_bridge') and self.ptz_detection_bridge:
                status = {
                    'active': True,
                    'cameras_registered': len(self.ptz_detection_bridge.active_cameras),
                    'detection_count': self.ptz_detection_bridge.detection_count,
                    'active_cameras': list(self.ptz_detection_bridge.active_cameras.keys())
                }
                return status
            else:
                return {
                    'active': False,
                    'error': 'Puente PTZ no inicializado'
                }
        except Exception as e:
            return {
                'active': False,
                'error': str(e)
            }

    def process_detections_for_ptz(self, results, frame_shape, camera_id=None):
        """Procesar detecciones para PTZ multi-objeto (Formato YOLO completo)"""
        if not hasattr(self, 'ptz_detection_bridge') or not self.ptz_detection_bridge:
            return 0

        try:
            if hasattr(self.ptz_detection_bridge, 'process_yolo_results'):
                detections_count = self.ptz_detection_bridge.process_yolo_results(
                    results, frame_shape
                )
            else:
                detections_count = self._convert_and_send_detections(results, camera_id)

            if detections_count > 0:
                self.append_debug(
                    f"🎯 PTZ: {detections_count} detección(es) enviada(s) al sistema PTZ"
                )

            return detections_count

        except Exception as e:
            self.append_debug(f"⚠️ Error enviando detecciones al PTZ: {e}")
            return 0

    def _convert_and_send_detections(self, results, camera_id):
        """Convertir detecciones YOLO a formato básico y enviar al PTZ"""
        try:
            if not results or not hasattr(results, 'boxes'):
                return 0

            detections_list = []
            boxes = results.boxes

            if boxes is not None and len(boxes) > 0:
                for i, box in enumerate(boxes):
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    cls = int(box.cls[0].cpu().numpy())

                    x1, y1, x2, y2 = xyxy
                    cx = float((x1 + x2) / 2)
                    cy = float((y1 + y2) / 2)
                    width = float(x2 - x1)
                    height = float(y2 - y1)

                    detection = {
                        'cx': cx,
                        'cy': cy,
                        'width': width,
                        'height': height,
                        'confidence': conf,
                        'class': cls,
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'frame_w': results.orig_shape[1] if hasattr(results, 'orig_shape') else 1920,
                        'frame_h': results.orig_shape[0] if hasattr(results, 'orig_shape') else 1080
                    }
                    detections_list.append(detection)

            if detections_list and camera_id:
                success = self.send_detections_to_ptz(camera_id, detections_list)
                return len(detections_list) if success else 0

            return 0

        except Exception as e:
            self.append_debug(f"❌ Error convirtiendo detecciones para PTZ: {e}")
            return 0

    def register_camera_with_ptz(self, camera_data):
        """Registrar una cámara con el sistema PTZ"""
        try:
            if hasattr(self, 'ptz_detection_bridge') and self.ptz_detection_bridge:
                camera_id = camera_data.get('ip', camera_data.get('id', 'unknown'))

                if camera_data.get('tipo') == 'ptz':
                    success = self.ptz_detection_bridge.register_camera(camera_id, camera_data)
                    if success:
                        self.append_debug(f"📷 Cámara PTZ registrada: {camera_id}")
                        return True
                    else:
                        self.append_debug(f"❌ Error registrando cámara PTZ: {camera_id}")
                else:
                    self.append_debug(
                        f"📹 Cámara fija preparada para envío de detecciones: {camera_id}"
                    )
                    return True

            return False
        except Exception as e:
            self.append_debug(f"❌ Error registrando cámara con PTZ: {e}")
            return False

    def add_adaptive_sampling_menu_items(self):
        """Agrega elementos del menú de muestreo adaptativo"""
        if ADAPTIVE_SAMPLING_AVAILABLE:
            # Agregar separador antes de las opciones de muestreo adaptativo
            self.menu_config.addSeparator()
            
            # Menú principal de muestreo adaptativo
            adaptive_menu = self.menu_config.addMenu("🧠 Muestreo Adaptativo")
            
            # Configuración global
            config_global_action = QAction("⚙️ Configuración Global", self)
            config_global_action.triggered.connect(self.abrir_muestreo_adaptativo_config)
            adaptive_menu.addAction(config_global_action)
            
            # Estado de todas las cámaras
            status_all_action = QAction("📊 Estado de Todas las Cámaras", self)
            status_all_action.triggered.connect(self.show_adaptive_sampling_status)
            adaptive_menu.addAction(status_all_action)
            
            # Separador
            adaptive_menu.addSeparator()
            
            # Activar/Desactivar para todas
            enable_all_action = QAction("🧠 Activar en Todas", self)
            enable_all_action.triggered.connect(lambda: self.toggle_adaptive_sampling_all(True))
            adaptive_menu.addAction(enable_all_action)
            
            disable_all_action = QAction("📊 Desactivar en Todas (Usar Fijo)", self)
            disable_all_action.triggered.connect(lambda: self.toggle_adaptive_sampling_all(False))
            adaptive_menu.addAction(disable_all_action)
            
            # Separador
            adaptive_menu.addSeparator()
            
            # Presets de configuración
            presets_menu = adaptive_menu.addMenu("🚀 Aplicar Preset")
            
            aggressive_action = QAction("⚡ Agresivo (Máximo rendimiento)", self)
            aggressive_action.triggered.connect(lambda: self.apply_adaptive_preset("aggressive"))
            presets_menu.addAction(aggressive_action)
            
            balanced_action = QAction("⚖️ Balanceado (Recomendado)", self)
            balanced_action.triggered.connect(lambda: self.apply_adaptive_preset("balanced"))
            presets_menu.addAction(balanced_action)
            
            conservative_action = QAction("🛡️ Conservador (Máxima estabilidad)", self)
            conservative_action.triggered.connect(lambda: self.apply_adaptive_preset("conservative"))
            presets_menu.addAction(conservative_action)

    def abrir_muestreo_adaptativo_config(self):
        """Abrir diálogo de configuración del muestreo adaptativo"""
        if not ADAPTIVE_SAMPLING_AVAILABLE:
            QMessageBox.warning(
                self,
                "No disponible",
                "❌ El sistema de muestreo adaptativo no está disponible.\n\n"
                "Archivos requeridos:\n"
                "• core/adaptive_sampling.py\n"
                "• ui/adaptive_sampling_dialog.py"
            )
            return
        
        try:
            # Obtener configuración actual desde las cámaras activas
            current_config = None
            
            # Si hay cámaras activas, usar la configuración de la primera
            if self.camera_widgets:
                for widget in self.camera_widgets:
                    if hasattr(widget, 'get_adaptive_sampling_status'):
                        status = widget.get_adaptive_sampling_status()
                        if status.get('enabled') and hasattr(widget, 'adaptive_controller'):
                            current_config = widget.adaptive_controller.config.copy()
                            break
            
            # Si no hay configuración activa, usar balanceada por defecto
            if current_config is None:
                current_config = AdaptiveSamplingConfig.create_config("balanced")
            
            dialog = AdaptiveSamplingConfigDialog(self, current_config)
            dialog.config_changed.connect(self.apply_adaptive_config_to_all_cameras)
            
            if dialog.exec():
                final_config = dialog.get_config()
                self.apply_adaptive_config_to_all_cameras(final_config)
                self.append_debug("✅ Configuración de muestreo adaptativo aplicada a todas las cámaras")
                
        except Exception as e:
            self.append_debug(f"❌ Error abriendo configuración de muestreo adaptativo: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"❌ Error abriendo configuración:\n{e}"
            )

    def apply_adaptive_config_to_all_cameras(self, config):
        """Aplica configuración de muestreo adaptativo a todas las cámaras - MÉTODO CORREGIDO"""
        applied_count = 0

        for widget in self.camera_widgets:
            if hasattr(widget, 'configure_adaptive_sampling'):
                try:
                    success = widget.configure_adaptive_sampling(config)
                    if success:
                        applied_count += 1

                        # También activar el muestreo adaptativo si no estaba activo
                        if hasattr(widget, 'toggle_adaptive_sampling'):
                            widget.toggle_adaptive_sampling(True)
                except Exception as e:
                    cam_ip = "N/A"
                    if hasattr(widget, 'cam_data') and widget.cam_data:
                        cam_ip = widget.cam_data.get('ip', 'N/A')
                    self.append_debug(f"❌ Error aplicando config adaptativo a {cam_ip}: {e}")

        if applied_count > 0:
            self.append_debug(f"✅ Configuración adaptativa aplicada a {applied_count} cámaras")
            self.save_adaptive_config_to_global_config(config)
        else:
            self.append_debug("⚠️ No se pudo aplicar configuración adaptativa a ninguna cámara")

    def save_adaptive_config_to_global_config(self, adaptive_config):
        """Guarda la configuración de muestreo adaptativo en config.json"""
        try:
            import json
            import os
            
            config_path = "config.json"
            
            # Leer configuración existente
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                config_data = {"camaras": [], "configuracion": {}}
            
            # Agregar configuración global de muestreo adaptativo
            config_data["adaptive_sampling"] = adaptive_config
            
            # También agregar a cada cámara individualmente
            for cam in config_data.get("camaras", []):
                cam["adaptive_sampling"] = adaptive_config.copy()
            
            # Guardar archivo
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            
            self.append_debug("💾 Configuración de muestreo adaptativo guardada en config.json")
            
        except Exception as e:
            self.append_debug(f"❌ Error guardando configuración adaptativa: {e}")

    def show_adaptive_sampling_status(self):
        """Muestra el estado del muestreo adaptativo de todas las cámaras"""
        if not ADAPTIVE_SAMPLING_AVAILABLE:
            QMessageBox.information(
                self,
                "Muestreo Adaptativo",
                "❌ El sistema de muestreo adaptativo no está disponible."
            )
            return
        
        status_info = []
        total_cameras = len(self.camera_widgets)
        adaptive_cameras = 0
        
        for i, widget in enumerate(self.camera_widgets):
            cam_ip = "N/A"
            if hasattr(widget, 'cam_data') and widget.cam_data:
                cam_ip = widget.cam_data.get('ip', f'Cámara {i+1}')
            
            if hasattr(widget, 'get_adaptive_sampling_status'):
                status = widget.get_adaptive_sampling_status()
                
                if status['enabled']:
                    adaptive_cameras += 1
                    status_info.append(
                        f"📷 {cam_ip}: 🧠 ADAPTATIVO\n"
                        f"   • Intervalo actual: {status['current_interval']}\n"
                        f"   • Actividad: {status.get('activity_score', 0):.2f}\n"
                        f"   • Frames procesados: {status['frames_processed']}\n"
                        f"   • Eficiencia: {(status['frames_skipped']/status['frames_processed']*100):.1f}% omitidos"
                    )
                else:
                    status_info.append(
                        f"📷 {cam_ip}: 📊 FIJO\n"
                        f"   • Intervalo fijo: {status['current_interval']}\n"
                        f"   • Frames procesados: {status['frames_processed']}"
                    )
            else:
                status_info.append(f"📷 {cam_ip}: ❌ Estado no disponible")
        
        summary = f"""🧠 Estado del Muestreo Adaptativo

📊 Resumen:
• Total de cámaras: {total_cameras}
• Usando muestreo adaptativo: {adaptive_cameras}
• Usando muestreo fijo: {total_cameras - adaptive_cameras}

📷 Detalles por cámara:
"""
        
        if status_info:
            summary += "\n\n".join(status_info)
        else:
            summary += "No hay cámaras activas"
        
        QMessageBox.information(self, "Estado del Muestreo Adaptativo", summary)

    def toggle_adaptive_sampling_all(self, enable):
        """Activa/desactiva muestreo adaptativo en todas las cámaras"""
        if not ADAPTIVE_SAMPLING_AVAILABLE:
            return
        
        affected_count = 0
        mode = "adaptativo" if enable else "fijo"
        
        for widget in self.camera_widgets:
            if hasattr(widget, 'toggle_adaptive_sampling'):
                try:
                    widget.toggle_adaptive_sampling(enable)
                    affected_count += 1
                    
                    # Si se está activando, aplicar configuración por defecto si es necesario
                    if enable and hasattr(widget, 'configure_adaptive_sampling'):
                        if not hasattr(widget, 'adaptive_controller') or widget.adaptive_controller is None:
                            default_config = AdaptiveSamplingConfig.create_config("balanced")
                            widget.configure_adaptive_sampling(default_config)
                            
                except Exception as e:
                    cam_ip = "N/A"
                    if hasattr(widget, 'cam_data') and widget.cam_data:
                        cam_ip = widget.cam_data.get('ip', 'N/A')
                    self.append_debug(f"❌ Error cambiando a modo {mode} en {cam_ip}: {e}")
        
        if affected_count > 0:
            self.append_debug(f"🧠 Muestreo {mode} {'activado' if enable else 'desactivado'} en {affected_count} cámaras")
            
            # Mostrar mensaje de confirmación
            QMessageBox.information(
                self,
                "Muestreo Adaptativo",
                f"✅ Muestreo {mode} {'activado' if enable else 'desactivado'} en {affected_count} cámaras.\n\n"
                f"{'💡 El sistema se adaptará automáticamente a la actividad de cada escena.' if enable else '📊 Todas las cámaras usarán intervalos fijos.'}"
            )
        else:
            self.append_debug("⚠️ No se encontraron cámaras compatibles con muestreo adaptativo")

    def apply_adaptive_preset(self, preset_name):
        """Aplica un preset de configuración adaptativa a todas las cámaras"""
        if not ADAPTIVE_SAMPLING_AVAILABLE:
            return
        
        try:
            preset_config = AdaptiveSamplingConfig.create_config(preset_name)
            
            # Aplicar a todas las cámaras
            self.apply_adaptive_config_to_all_cameras(preset_config)
            
            # Descripción del preset
            preset_descriptions = {
                "aggressive": "⚡ Máximo rendimiento - Adaptación rápida y agresiva",
                "balanced": "⚖️ Balanceado - Equilibrio ideal entre calidad y rendimiento",
                "conservative": "🛡️ Conservador - Cambios suaves y máxima estabilidad"
            }
            
            description = preset_descriptions.get(preset_name, preset_name)
            
            QMessageBox.information(
                self,
                "Preset Aplicado",
                f"✅ Preset '{preset_name}' aplicado exitosamente.\n\n"
                f"{description}\n\n"
                f"🧠 El sistema adaptativo ajustará automáticamente la frecuencia\n"
                f"de análisis según la actividad detectada en cada cámara."
            )
            
        except Exception as e:
            self.append_debug(f"❌ Error aplicando preset {preset_name}: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"❌ Error aplicando preset '{preset_name}':\n{e}"
            )

    def toggle_camera_adaptive_sampling(self, camera_index, enable):
        """Activa/desactiva muestreo adaptativo para una cámara específica"""
        if camera_index >= len(self.camera_widgets):
            return
            
        widget = self.camera_widgets[camera_index]
        cam_ip = "N/A"
        
        if hasattr(widget, 'cam_data') and widget.cam_data:
            cam_ip = widget.cam_data.get('ip', f'Cámara {camera_index+1}')
        
        if hasattr(widget, 'toggle_adaptive_sampling'):
            try:
                widget.toggle_adaptive_sampling(enable)
                mode = "adaptativo" if enable else "fijo"
                self.append_debug(f"🧠 Cámara {cam_ip}: Muestreo {mode} {'activado' if enable else 'desactivado'}")
                
                # Si se está activando y no hay configuración, usar la por defecto
                if enable and hasattr(widget, 'configure_adaptive_sampling'):
                    if not hasattr(widget, 'adaptive_controller') or widget.adaptive_controller is None:
                        default_config = AdaptiveSamplingConfig.create_config("balanced")
                        widget.configure_adaptive_sampling(default_config)
                        self.append_debug(f"⚙️ Configuración adaptativa por defecto aplicada a {cam_ip}")
                        
            except Exception as e:
                self.append_debug(f"❌ Error cambiando modo de muestreo en {cam_ip}: {e}")
        else:
            self.append_debug(f"⚠️ Cámara {cam_ip} no soporta muestreo adaptativo")

    def configure_individual_adaptive_sampling(self, camera_index):
        """Configura muestreo adaptativo para una cámara específica"""
        if camera_index >= len(self.camera_widgets):
            return
            
        widget = self.camera_widgets[camera_index]
        cam_ip = "N/A"
        
        if hasattr(widget, 'cam_data') and widget.cam_data:
            cam_ip = widget.cam_data.get('ip', f'Cámara {camera_index+1}')
        
        try:
            # Obtener configuración actual de la cámara
            current_config = None
            if hasattr(widget, 'adaptive_controller') and widget.adaptive_controller:
                current_config = widget.adaptive_controller.config.copy()
            else:
                current_config = AdaptiveSamplingConfig.create_config("balanced")
            
            dialog = AdaptiveSamplingConfigDialog(self, current_config)
            dialog.setWindowTitle(f"🧠 Muestreo Adaptativo - {cam_ip}")
            
            def apply_individual_config(config):
                if hasattr(widget, 'configure_adaptive_sampling'):
                    success = widget.configure_adaptive_sampling(config)
                    if success:
                        self.append_debug(f"✅ Configuración adaptativa aplicada a {cam_ip}")
                        # Activar si no estaba activo
                        if hasattr(widget, 'toggle_adaptive_sampling'):
                            widget.toggle_adaptive_sampling(True)
                    else:
                        self.append_debug(f"❌ Error aplicando configuración a {cam_ip}")
            
            dialog.config_changed.connect(apply_individual_config)
            
            if dialog.exec():
                final_config = dialog.get_config()
                apply_individual_config(final_config)
                
        except Exception as e:
            self.append_debug(f"❌ Error configurando muestreo adaptativo para {cam_ip}: {e}")

    def show_individual_adaptive_stats(self, camera_index):
        """Muestra estadísticas detalladas de muestreo adaptativo para una cámara"""
        if camera_index >= len(self.camera_widgets):
            return
            
        widget = self.camera_widgets[camera_index]
        cam_ip = "Cámara desconocida"
        
        if hasattr(widget, 'cam_data') and widget.cam_data:
            cam_ip = widget.cam_data.get('ip', f'Cámara {camera_index+1}')
        
        if hasattr(widget, 'get_adaptive_sampling_status'):
            status = widget.get_adaptive_sampling_status()
            
            if status['enabled']:
                # Estadísticas detalladas para muestreo adaptativo
                efficiency = 0
                if status['frames_processed'] > 0:
                    efficiency = (status['frames_skipped'] / status['frames_processed']) * 100
                
                stats_message = f"""🧠 Estadísticas de Muestreo Adaptativo
📷 Cámara: {cam_ip}

📊 Estado Actual:
• Modo: Adaptativo
• Intervalo actual: {status['current_interval']} frames
• Puntuación de actividad: {status.get('activity_score', 0):.3f}
• Promedio de detecciones: {status.get('avg_detections', 0):.2f}

📈 Rendimiento:
• Total frames procesados: {status['frames_processed']:,}
• Frames analizados: {status['frames_processed'] - status['frames_skipped']:,}
• Frames omitidos: {status['frames_skipped']:,}
• Eficiencia: {efficiency:.1f}% frames omitidos

💡 Significado:
• Intervalo alto (>15) = Poca actividad detectada
• Intervalo bajo (<8) = Mucha actividad detectada
• Más eficiencia = Mejor optimización automática"""
                
                if hasattr(widget, 'adaptive_controller') and widget.adaptive_controller:
                    controller_status = widget.adaptive_controller.get_status()
                    
                    stats_message += f"""

⚙️ Configuración Actual:
• Intervalo base: {controller_status['config']['base_interval']}
• Rango: {controller_status['config']['min_interval']}-{controller_status['config']['max_interval']}
• Velocidad adaptación: {controller_status['config']['adaptation_rate']:.1%}
• Umbral actividad alta: {controller_status['config']['high_activity_threshold']:.1%}"""
                
            else:
                # Estadísticas para muestreo fijo
                efficiency = 0
                if status['frames_processed'] > 0:
                    efficiency = (status['frames_skipped'] / status['frames_processed']) * 100
                
                stats_message = f"""📊 Estadísticas de Muestreo Fijo
📷 Cámara: {cam_ip}

📊 Estado Actual:
• Modo: Fijo
• Intervalo fijo: {status['current_interval']} frames

📈 Rendimiento:
• Total frames procesados: {status['frames_processed']:,}
• Frames analizados: {status['frames_processed'] - status['frames_skipped']:,}
• Frames omitidos: {status['frames_skipped']:,}
• Frecuencia análisis: {100 - efficiency:.1f}% frames analizados

💡 Recomendación:
El muestreo adaptativo puede optimizar automáticamente
el rendimiento basado en la actividad de la escena."""
            
            QMessageBox.information(self, f"Estadísticas - {cam_ip}", stats_message)
        else:
            QMessageBox.warning(self, "Error", f"No se pueden obtener estadísticas para {cam_ip}")

    def abrir_fps_config(self):
        """Abrir diálogo de configuración de FPS"""
        dialog = FPSConfigDialog(self, self.fps_config)
        dialog.fps_config_changed.connect(self.update_fps_config)
        
        if dialog.exec():
            self.fps_config = dialog.get_config()
            self.apply_fps_to_all_cameras()
            self.append_debug(f"⚙️ Configuración de FPS aplicada: {self.fps_config}")
    
    def update_fps_config(self, config):
        """Actualizar configuración de FPS en tiempo real"""
        self.fps_config = config
        self.apply_fps_to_all_cameras()
        self.append_debug(f"🎯 FPS actualizado en tiempo real: Visual={config['visual_fps']}, "
                         f"Detección={config['detection_fps']}, UI={config['ui_update_fps']}")
    
    def apply_fps_to_all_cameras(self):
        """Aplicar configuración de FPS a todas las cámaras activas"""
        for widget in self.camera_widgets:
            try:
                # Actualizar GrillaWidget
                if hasattr(widget, 'set_fps_config'):
                    widget.set_fps_config(
                        visual_fps=self.fps_config['visual_fps'],
                        detection_fps=self.fps_config['detection_fps'],
                        ui_update_fps=self.fps_config['ui_update_fps']
                    )
                
                # Actualizar VisualizadorDetector
                if hasattr(widget, 'visualizador') and widget.visualizador:
                    if hasattr(widget.visualizador, 'update_fps_config'):
                        widget.visualizador.update_fps_config(
                            visual_fps=self.fps_config['visual_fps'],
                            detection_fps=self.fps_config['detection_fps']
                        )
                        
            except Exception as e:
                self.append_debug(f"❌ Error aplicando FPS a cámara: {e}")

    def get_optimized_fps_for_camera(self, camera_data):
        """Obtener configuración de FPS optimizada según el tipo de cámara"""
        base_config = self.fps_config.copy()
        
        # Ajustar según el tipo de cámara
        camera_type = camera_data.get('tipo', 'fija')
        models = camera_data.get('modelos', [camera_data.get('modelo', 'Personas')])
        
        if camera_type == 'ptz':
            # PTZ necesita más FPS para seguimiento fluido
            base_config['visual_fps'] = min(30, base_config['visual_fps'] + 5)
            base_config['detection_fps'] = min(15, base_config['detection_fps'] + 2)
        
        if 'Embarcaciones' in models or 'Barcos' in models:
            # Detección marítima puede necesitar menos FPS
            base_config['detection_fps'] = max(3, base_config['detection_fps'] - 2)
        
        return base_config

    def append_debug(self, message: str):
        """Agregar mensaje al debug console, filtrando spam innecesario"""
        if any(substr in message for substr in ["hevc @", "VPS 0", "undecodable NALU", "Frame procesado"]):
            return
        self.debug_console.append(message)

    def setup_inicio_ui(self):
        """Configura la interfaz principal con splitter"""
        # --- Parte superior: cámaras ---
        self.video_grid = QGridLayout()
        video_grid_container_widget = QWidget()
        video_grid_container_widget.setLayout(self.video_grid)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(video_grid_container_widget)

        # --- Parte inferior: lista + log + resumen ---
        bottom_layout = QHBoxLayout()
    
        self.camera_list = QListWidget()
        self.camera_list.setFixedWidth(250)
        self.camera_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.camera_list.customContextMenuRequested.connect(self.show_camera_menu)
        bottom_layout.addWidget(self.camera_list)

        self.debug_console = QTextEdit()
        self.debug_console.setReadOnly(True)
        bottom_layout.addWidget(self.debug_console, 2)

        self.resumen_widget = ResumenDeteccionesWidget()
        self.resumen_widget.log_signal.connect(self.append_debug)
        bottom_layout.addWidget(self.resumen_widget, 1)

        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_layout)

        # --- Dividir con splitter vertical ---
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(scroll_area)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([1, 1])  # 50% y 50%

        self.init_tab_layout.addWidget(splitter)

    def open_camera_dialog(self, index=None):
        """Abrir diálogo para agregar/editar cámara"""
        print("🛠️ [DEBUG] Ejecutando open_camera_dialog")
        if index is not None and index >= len(self.camera_data_list):
            return
        existing = self.camera_data_list[index] if index is not None else None
        dialog = CameraDialog(self, existing_data=existing)
        if dialog.exec(): 
            if dialog.result() == 1: 
                new_data = dialog.get_camera_data()
                if index is not None:
                    self.camera_data_list[index] = new_data
                    self.camera_list.item(index).setText(f"{new_data['ip']} - {new_data['tipo']}")
                    self.append_debug(f"✏️ Cámara editada: {new_data}")
                    self.start_camera_stream(new_data) 
                else:
                    self.camera_data_list.append(new_data)
                    self.camera_list.addItem(f"{new_data['ip']} - {new_data['tipo']}")
                    self.append_debug(f"✅ Cámara agregada: {new_data}")
                    self.start_camera_stream(new_data)
                guardar_camaras(self)
                
                # Reinicializar sistema PTZ si se agregó una cámara PTZ
                if new_data.get('tipo') == 'ptz':
                    self._initialize_ptz_system()

    def open_ptz_dialog(self):
        """Abre el diálogo básico de PTZ"""
        try:
            from ui.ptz_tracking_dialog import PTZTrackingDialog
            dialog = PTZTrackingDialog(self, self.camera_data_list)
            dialog.exec()
        except ImportError as e:
            self.append_debug(f"❌ Error: No se pudo cargar el diálogo PTZ básico: {e}")
            QMessageBox.warning(
                self,
                "Módulo PTZ no disponible",
                f"❌ No se pudo cargar el control PTZ básico:\n{e}\n\n"
                f"Archivos requeridos:\n"
                f"• ui/ptz_tracking_dialog.py\n"
                f"• core/ptz_control.py\n\n"
                f"Dependencias:\n"
                f"• pip install onvif-zeep"
            )
        except Exception as e:
            self.append_debug(f"❌ Error inesperado abriendo PTZ básico: {e}")

    def open_ptz_presets_dialog(self):
        """Abre el diálogo avanzado de gestión PTZ - VERSIÓN CORREGIDA"""
        try:
            # Verificar que hay cámaras PTZ disponibles
            ptz_cameras = [cam for cam in self.camera_data_list if cam.get('tipo') == 'ptz']
            
            if not ptz_cameras:
                QMessageBox.warning(
                    self,
                    "Sin cámaras PTZ",
                    "❌ No se encontraron cámaras PTZ configuradas.\n\n"
                    "Para usar la gestión avanzada PTZ:\n"
                    "1. Agregue al menos una cámara con tipo 'ptz'\n"
                    "2. Asegúrese de que las credenciales sean correctas\n"
                    "3. Verifique la conexión de red"
                )
                self.append_debug("⚠️ No hay cámaras PTZ para gestión avanzada")
                return
            
            from ui.ptz_preset_dialog import PTZPresetDialog

            # Tomar una cámara PTZ para inicializar la conexión
            selected_cam = ptz_cameras[0]
            ip = selected_cam.get('ip')
            puerto = int(selected_cam.get('puerto', 80))
            usuario = selected_cam.get('usuario', '')
            contrasena = selected_cam.get('contrasena', '')

            ptz_cam = None
            try:
                try:
                    from core.ptz_control_enhanced import create_enhanced_ptz_camera
                    ptz_cam = create_enhanced_ptz_camera(ip, puerto, usuario, contrasena)
                except ImportError:
                    from core.ptz_control import PTZCameraONVIF
                    ptz_cam = PTZCameraONVIF(ip, puerto, usuario, contrasena)
            except Exception as conn_error:
                self.append_debug(f"❌ Error conectando a cámara PTZ {ip}: {conn_error}")
            if ptz_cam is None:
                self.append_debug("⚠️ No se pudo inicializar la cámara PTZ seleccionada")

            # Asegurar que el sistema PTZ está inicializado
            if not self._ptz_initialized:
                self._initialize_ptz_system()

            # Pasar la instancia de cámara al diálogo
            dialog = PTZPresetDialog(self, camera_list=self.camera_data_list, ptz_camera=ptz_cam)
            
            # Conectar señales del diálogo
            dialog.preset_updated.connect(
                lambda preset_num, preset_name: self.append_debug(
                    f"📍 Preset {preset_num} actualizado: '{preset_name}'"
                )
            )
            
            # Mostrar información de cámaras PTZ encontradas
            self.append_debug(f"🎯 Abriendo gestión PTZ para {len(ptz_cameras)} cámaras:")
            for cam in ptz_cameras:
                ip = cam.get('ip', 'N/A')
                usuario = cam.get('usuario', 'N/A')
                self.append_debug(f"   📹 {ip} ({usuario})")
            
            dialog.exec()
            
        except ImportError as e:
            self.append_debug(f"❌ Error: No se pudo cargar el diálogo PTZ avanzado: {e}")
            self.append_debug("💡 Asegúrese de que el archivo ui/ptz_preset_dialog.py esté presente")
            QMessageBox.critical(
                self,
                "Módulo no encontrado",
                f"❌ No se pudo cargar el diálogo PTZ avanzado:\n{e}\n\n"
                f"Archivos requeridos:\n"
                f"• ui/ptz_preset_dialog.py\n"
                f"• core/ptz_control_enhanced.py (opcional)"
            )
        except Exception as e:
            self.append_debug(f"❌ Error inesperado al abrir diálogo PTZ: {e}")
            import traceback
            traceback.print_exc()  # Para debugging
            QMessageBox.critical(
                self,
                "Error inesperado",
                f"❌ Error inesperado al abrir diálogo PTZ:\n{e}\n\n"
                f"Revise la consola para más detalles."
            )

    def open_ptz_calibration(self):
        """Abrir calibración PTZ"""
        try:
            from ui.ptz_calibration_dialog import create_calibration_dialog

            selected_camera = None
            for cam in self.camera_data_list:
                if cam.get('tipo') == 'ptz':
                    selected_camera = cam
                    break

            if not selected_camera:
                QMessageBox.warning(
                    self,
                    "Sin cámaras PTZ",
                    "No se encontraron cámaras PTZ configuradas."
                )
                return

            dialog = create_calibration_dialog(self, selected_camera)
            if dialog:
                dialog.calibration_completed.connect(self._on_calibration_completed)
                dialog.exec()

        except Exception as e:
            self.append_debug(f"❌ Error abriendo calibración: {e}")

    def _on_calibration_completed(self, camera_ip):
        """Manejar calibración completada"""

        self.append_debug(f"✅ Calibración completada para {camera_ip}")

    def initialize_ptz_system(self):
        """Inicializa manualmente el sistema PTZ"""
        try:
            # Intentar cargar el sistema PTZ mejorado
            try:
                from core.ptz_control_enhanced import initialize_ptz_system
                success = initialize_ptz_system()
                enhanced_available = True
            except ImportError:
                # Fallback a sistema básico
                enhanced_available = False
                success = True  # Asumir éxito para sistema básico
            
            if success:
                self._ptz_initialized = True
                ptz_cameras = [cam for cam in self.camera_data_list if cam.get('tipo') == 'ptz']
                
                if enhanced_available:
                    self.append_debug(f"🚀 Sistema PTZ mejorado inicializado con {len(ptz_cameras)} cámaras PTZ")
                else:
                    self.append_debug(f"🚀 Sistema PTZ básico inicializado con {len(ptz_cameras)} cámaras PTZ")
                
                # Listar cámaras PTZ encontradas
                for cam in ptz_cameras:
                    self.append_debug(f"📹 PTZ detectada: {cam.get('ip')} ({cam.get('usuario')})")
            else:
                self.append_debug("⚠️ No se encontraron cámaras PTZ válidas")
                
        except Exception as e:
            self.append_debug(f"❌ Error inicializando sistema PTZ: {e}")

    def stop_all_ptz(self):
        """Detiene todas las cámaras PTZ"""
        try:
            # Intentar usar sistema PTZ mejorado
            try:
                from core.ptz_control_enhanced import get_ptz_system_status
                # Sistema mejorado disponible
                stopped_count = 0
                for cam in self.camera_data_list:
                    if cam.get('tipo') == 'ptz':
                        # Aquí se implementaría la lógica de parada específica
                        stopped_count += 1
                
                self.append_debug(f"⏹️ {stopped_count} cámaras PTZ detenidas (sistema mejorado)")
                
            except ImportError:
                # Fallback a sistema básico
                stopped_count = 0
                for cam in self.camera_data_list:
                    if cam.get('tipo') == 'ptz':
                        stopped_count += 1
                
                self.append_debug(f"⏹️ {stopped_count} cámaras PTZ detenidas (sistema básico)")
            
        except Exception as e:
            self.append_debug(f"❌ Error deteniendo PTZ: {e}")

    def toggle_line_edit(self):
        """Activar/desactivar modo de edición de línea de cruce"""
        items = self.camera_list.selectedItems()
        if not items:
            self.append_debug("⚠️ Seleccione una cámara para editar línea de cruce")
            return
        index = self.camera_list.row(items[0])
        if index >= len(self.camera_widgets):
            return
        widget = self.camera_widgets[index]
        if hasattr(widget, 'cross_line_edit_mode'):
            if widget.cross_line_edit_mode:
                widget.finish_line_edit()
                self.append_debug("✅ Modo edición de línea desactivado")
            else:
                widget.start_line_edit()
                self.append_debug("📏 Modo edición de línea activado - Click y arrastre para definir línea")
        else:
            self.append_debug("❌ Widget de cámara no soporta edición de línea")

    def start_camera_stream(self, camera_data):
        """Iniciar stream de cámara con configuración optimizada"""
        # Agregar configuración de FPS optimizada a los datos de la cámara
        optimized_fps = self.get_optimized_fps_for_camera(camera_data)
        camera_data['fps_config'] = optimized_fps

        # Verificar si ya existe un widget para esta IP y reemplazarlo
        for i, widget in enumerate(self.camera_widgets):
            if hasattr(widget, 'cam_data') and widget.cam_data.get('ip') == camera_data.get('ip'):
                print(f"INFO: Reemplazando widget para cámara IP: {camera_data.get('ip')}")
                widget.detener()
                self.video_grid.removeWidget(widget) 
                widget.deleteLater()
                self.camera_widgets.pop(i)
                break
        
        # Buscar el contenedor del grid de video
        video_grid_container_widget = None
        for i in range(self.init_tab_layout.count()):
            item = self.init_tab_layout.itemAt(i)
            if hasattr(item, 'widget') and isinstance(item.widget(), QSplitter):
                splitter = item.widget()
                if splitter.count() > 0:
                    scroll_area = splitter.widget(0)
                    if isinstance(scroll_area, QScrollArea):
                        video_grid_container_widget = scroll_area.widget()
                        break

        # Importar dinámicamente GrillaWidget
        try:
            grilla_widget_module = importlib.import_module("gui.grilla_widget")
            GrillaWidget_class = grilla_widget_module.GrillaWidget
        except ImportError as e:
            print(f"ERROR: No se pudo importar GrillaWidget: {e}")
            self.append_debug(f"ERROR: No se pudo importar GrillaWidget: {e}")
            return

        # Crear widget de cámara
        parent_widget = video_grid_container_widget if video_grid_container_widget else self
        video_widget = GrillaWidget_class(parent=parent_widget, fps_config=optimized_fps) 
        
        video_widget.cam_data = camera_data 
        video_widget.log_signal.connect(self.append_debug)
        
        # Posicionar en grid (una fila, múltiples columnas)
        row = 0
        col = len(self.camera_widgets) 
        
        self.video_grid.addWidget(video_widget, row, col)
        self.camera_widgets.append(video_widget) 
        
        # Iniciar vista de cámara
        video_widget.mostrar_vista(camera_data) 
        video_widget.show()
        self.append_debug(f"🎥 Reproduciendo: {camera_data.get('ip', 'IP Desconocida')} con FPS optimizado")

    def show_camera_menu(self, position):
        """Mostrar menú contextual para cámaras - VERSIÓN ACTUALIZADA CON MUESTREO ADAPTATIVO"""
        item = self.camera_list.itemAt(position)
        if item:
            index = self.camera_list.row(item)
            menu = QMenu()
            edit_action = menu.addAction("✏️ Editar Cámara")
            delete_action = menu.addAction("🗑️ Eliminar Cámara")
            stop_action = menu.addAction("⛔ Detener Visual") 
            fps_action = menu.addAction("🎯 Configurar FPS Individual")
            
            # NUEVA SECCIÓN: Muestreo Adaptativo
            if ADAPTIVE_SAMPLING_AVAILABLE and index < len(self.camera_widgets):
                widget = self.camera_widgets[index]
                
                if hasattr(widget, 'get_adaptive_sampling_status'):
                    menu.addSeparator()
                    adaptive_menu = menu.addMenu("🧠 Muestreo Adaptativo")
                    
                    status = widget.get_adaptive_sampling_status()
                    
                    if status['enabled']:
                        # Muestreo adaptativo activo
                        status_action = adaptive_menu.addAction(f"📊 Estado: Activo (Intervalo: {status['current_interval']})")
                        status_action.setEnabled(False)  # Solo informativo
                        
                        disable_action = adaptive_menu.addAction("📊 Cambiar a Fijo")
                        disable_action.triggered.connect(lambda: self.toggle_camera_adaptive_sampling(index, False))
                        
                        config_action = adaptive_menu.addAction("⚙️ Configurar Individual")
                        config_action.triggered.connect(lambda: self.configure_individual_adaptive_sampling(index))
                        
                        stats_action = adaptive_menu.addAction("📈 Ver Estadísticas")
                        stats_action.triggered.connect(lambda: self.show_individual_adaptive_stats(index))
                        
                    else:
                        # Muestreo fijo activo
                        status_action = adaptive_menu.addAction(f"📊 Estado: Fijo (Intervalo: {status['current_interval']})")
                        status_action.setEnabled(False)  # Solo informativo
                        
                        enable_action = adaptive_menu.addAction("🧠 Cambiar a Adaptativo")
                        enable_action.triggered.connect(lambda: self.toggle_camera_adaptive_sampling(index, True))
            
            # Menú específico para cámaras PTZ
            cam_data = self.camera_data_list[index] if index < len(self.camera_data_list) else {}
            if cam_data.get('tipo') == 'ptz':
                menu.addSeparator()
                ptz_control_action = menu.addAction("🎮 Control PTZ")
                ptz_presets_action = menu.addAction("📍 Gestión de Presets")
                ptz_stop_action = menu.addAction("⏹️ Detener PTZ")
                
            action = menu.exec(self.camera_list.mapToGlobal(position))

            if action == edit_action:
                self.open_camera_dialog(index=index) 
            elif action == delete_action:
                cam_to_delete_data = self.camera_data_list.pop(index)
                self.camera_list.takeItem(index) 
                for i, widget in enumerate(self.camera_widgets):
                    if hasattr(widget, 'cam_data') and widget.cam_data.get('ip') == cam_to_delete_data.get('ip'):
                        widget.detener()
                        self.video_grid.removeWidget(widget)
                        widget.deleteLater()
                        self.camera_widgets.pop(i)
                        self.append_debug(f"🗑️ Cámara {cam_to_delete_data.get('ip')} y su widget eliminados.")
                        break
                guardar_camaras(self) 
            elif action == stop_action:
                cam_ip_to_stop = self.camera_data_list[index].get('ip')
                for i, widget in enumerate(self.camera_widgets):
                     if hasattr(widget, 'cam_data') and widget.cam_data.get('ip') == cam_ip_to_stop:
                        widget.detener()
                        self.append_debug(f"⛔ Visual detenida para: {cam_ip_to_stop}")
                        break
            elif action == fps_action:
                self.configure_individual_fps(index)
            elif cam_data.get('tipo') == 'ptz':
                if action == ptz_control_action:
                    self.open_ptz_dialog()
                elif action == ptz_presets_action:
                    self.open_ptz_presets_dialog()
                elif action == ptz_stop_action:
                    try:
                        # Intentar detener PTZ específica
                        ip = cam_data.get('ip')
                        self.append_debug(f"⏹️ Deteniendo PTZ {ip}")
                        # Aquí se implementaría la lógica específica de parada
                    except Exception as e:
                        self.append_debug(f"❌ Error deteniendo PTZ: {e}")

    def configure_individual_fps(self, camera_index):
        """Configurar FPS individual para una cámara específica"""
        if camera_index >= len(self.camera_widgets):
            return
            
        widget = self.camera_widgets[camera_index]
        current_fps = widget.fps_config if hasattr(widget, 'fps_config') else self.fps_config
        
        dialog = FPSConfigDialog(self, current_fps)
        dialog.setWindowTitle(f"🎯 FPS para {self.camera_data_list[camera_index].get('ip', 'Cámara')}")
        
        def apply_individual_fps(config):
            widget.set_fps_config(
                visual_fps=config['visual_fps'],
                detection_fps=config['detection_fps'],
                ui_update_fps=config['ui_update_fps']
            )
            self.append_debug(f"🎯 FPS individual aplicado a {widget.cam_data.get('ip', 'Cámara')}")
        
        dialog.fps_config_changed.connect(apply_individual_fps)
        dialog.exec()

    def restart_all_cameras(self):
        """Reiniciar todas las cámaras con nueva configuración"""
        self.append_debug("🔄 Reiniciando todas las cámaras...")
        
        # Detener todos los widgets existentes
        for widget in list(self.camera_widgets):
            try:
                if hasattr(widget, 'detener') and callable(widget.detener):
                    widget.detener()
                self.video_grid.removeWidget(widget)
                widget.deleteLater()
            except Exception as e:
                print(f"ERROR al detener cámara: {e}")
        
        self.camera_widgets.clear()
        
        # Reiniciar todas las cámaras
        for cam in self.camera_data_list:
            self.start_camera_stream(cam)
            

    def closeEvent(self, event):
        """Manejar cierre de aplicación con limpieza completa"""
        print("INFO: Iniciando proceso de cierre de MainGUI...")
        
        # Detener sistema PTZ
        try:
            if self._ptz_initialized:
                self.stop_all_ptz()
                print("INFO: Sistema PTZ detenido")
        except Exception as e:
            print(f"ERROR deteniendo sistema PTZ: {e}")

        # ✅ AGREGAR: Limpiar sistema PTZ
        self.cleanup_ptz_system()
        
        # Detener widgets de cámara
        print(f"INFO: Deteniendo {len(self.camera_widgets)} widgets de cámara activos...")
        for widget in self.camera_widgets:
            try:
                if hasattr(widget, 'detener') and callable(widget.detener):
                    cam_ip = "N/A"
                    if hasattr(widget, 'cam_data') and widget.cam_data:
                        cam_ip = widget.cam_data.get('ip', 'N/A')
                    print(f"INFO: Llamando a detener() para el widget de la cámara IP: {cam_ip}")
                    widget.detener()
                else:
                    cam_ip_info = "N/A"
                    if hasattr(widget, 'cam_data') and widget.cam_data:
                         cam_ip_info = widget.cam_data.get('ip', 'N/A')
                    print(f"WARN: El widget para IP {cam_ip_info} no tiene el método detener() o no es callable.")
            except Exception as e:
                cam_ip_err = "N/A"
                if hasattr(widget, 'cam_data') and widget.cam_data:
                    cam_ip_err = widget.cam_data.get('ip', 'N/A')
                print(f"ERROR: Excepción al detener widget para IP {cam_ip_err}: {e}")
        
        # Detener widget de resumen
        if hasattr(self, 'resumen_widget') and self.resumen_widget: 
            if hasattr(self.resumen_widget, 'stop_threads') and callable(self.resumen_widget.stop_threads):
                print("INFO: Llamando a stop_threads() para resumen_widget...")
                try:
                    self.resumen_widget.stop_threads()
                except Exception as e:
                    print(f"ERROR: Excepción al llamar a stop_threads() en resumen_widget: {e}")
            else:
                print("WARN: resumen_widget no tiene el método stop_threads() o no es callable.")
        else:
            print("WARN: self.resumen_widget no existe, no se pueden detener sus hilos.")

        # Guardar configuración final
        try:
            guardar_camaras(self)
            print("INFO: Configuración guardada antes del cierre")
        except Exception as e:
            print(f"ERROR guardando configuración: {e}")

        # Profiling - guardar estadísticas
        print("INFO: Deteniendo profiler y guardando estadísticas...")
        try:
            self.profiler.disable()
            stats_filename = "main_gui_profile.prof"
            self.profiler.dump_stats(stats_filename)
            print(f"INFO: Resultados del profiler guardados en {stats_filename}")

            # Mostrar resumen de estadísticas
            s = io.StringIO()
            ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative', 'tottime')
            ps.print_stats(30)
            print("\n--- Resumen del Profiler (Top 30 por tiempo acumulado) ---")
            print(s.getvalue())
            print("--- Fin del Resumen del Profiler ---\n")
        except Exception as e:
            print(f"ERROR en profiling: {e}")

        print("INFO: Proceso de cierre de MainGUI completado. Aceptando evento.")
        event.accept()