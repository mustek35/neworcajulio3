# ui/ptz_calibration_dialog.py
"""
Interfaz gráfica para calibración PTZ
Permite calibrar el centro de imagen y corregir direcciones de movimiento
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QDoubleSpinBox, QSpinBox, QGroupBox, QTextEdit, QCheckBox, QProgressBar,
    QComboBox, QFormLayout, QMessageBox, QTabWidget, QWidget, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor
import time
import threading
from typing import Optional, Dict, Tuple

try:
    from core.ptz_calibration_system import (
        PTZCalibrationSystem, CalibrationData, track_object_calibrated
    )
    CALIBRATION_AVAILABLE = True
except ImportError:
    CALIBRATION_AVAILABLE = False

class CalibrationTestThread(QThread):
    """Hilo para pruebas de calibración"""
    test_completed = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    
    def __init__(self, calibration_system: PTZCalibrationSystem):
        super().__init__()
        self.calibration_system = calibration_system
        self.test_type = ""
    
    def set_test(self, test_type: str):
        self.test_type = test_type
    
    def run(self):
        try:
            if self.test_type == "directions":
                self.log_message.emit("🧪 Iniciando prueba de direcciones...")
                results = self.calibration_system.test_movement_directions()
                self.test_completed.emit(results)
            
        except Exception as e:
            self.log_message.emit(f"❌ Error en prueba: {e}")

class PTZCalibrationDialog(QDialog):
    """Diálogo para calibración PTZ completa"""
    
    calibration_completed = pyqtSignal(str)  # IP de cámara calibrada
    
    def __init__(self, parent=None, camera_data=None):
        super().__init__(parent)
        self.setWindowTitle("🎯 Calibración PTZ Avanzada")
        self.setFixedSize(800, 700)
        
        self.camera_data = camera_data or {}
        self.calibration_system = None
        self.calibration_points = []
        self.test_thread = None
        
        if CALIBRATION_AVAILABLE:
            self.calibration_system = PTZCalibrationSystem()
        
        self._setup_ui()
        self._connect_signals()
        
        if self.camera_data:
            self._load_camera_data()
    
    def _setup_ui(self):
        """Configurar interfaz de usuario"""
        layout = QVBoxLayout(self)
        
        # === TÍTULO ===
        title_label = QLabel("🎯 Calibración PTZ Avanzada")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # === TABS ===
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: Conexión
        self._create_connection_tab()
        
        # Tab 2: Prueba de Direcciones
        self._create_direction_test_tab()
        
        # Tab 3: Calibración de Centro
        self._create_center_calibration_tab()
        
        # Tab 4: Ajustes Avanzados
        self._create_advanced_tab()
        
        # === LOG ===
        log_group = QGroupBox("📝 Registro de Calibración")
        log_layout = QVBoxLayout(log_group)
        
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(150)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Consolas', monospace;
                font-size: 10pt;
            }
        """)
        log_layout.addWidget(self.log_display)
        layout.addWidget(log_group)
        
        # === BOTONES PRINCIPALES ===
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Guardar Calibración")
        self.save_btn.clicked.connect(self._save_calibration)
        self.save_btn.setEnabled(False)
        
        self.load_btn = QPushButton("📂 Cargar Calibración")
        self.load_btn.clicked.connect(self._load_calibration)
        
        self.close_btn = QPushButton("❌ Cerrar")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.load_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
    
    def _create_connection_tab(self):
        """Tab de conexión a cámara"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Información de cámara
        info_group = QGroupBox("📷 Información de Cámara")
        info_layout = QFormLayout(info_group)
        
        self.ip_label = QLabel("No conectado")
        self.status_label = QLabel("❌ Desconectado")
        self.type_label = QLabel("Desconocido")
        
        info_layout.addRow("IP:", self.ip_label)
        info_layout.addRow("Estado:", self.status_label)
        info_layout.addRow("Tipo:", self.type_label)
        
        layout.addWidget(info_group)
        
        # Botones de conexión
        connection_group = QGroupBox("🔌 Control de Conexión")
        connection_layout = QVBoxLayout(connection_group)
        
        self.connect_btn = QPushButton("🔗 Conectar PTZ")
        self.connect_btn.clicked.connect(self._connect_camera)
        
        self.disconnect_btn = QPushButton("🔌 Desconectar")
        self.disconnect_btn.clicked.connect(self._disconnect_camera)
        self.disconnect_btn.setEnabled(False)
        
        connection_layout.addWidget(self.connect_btn)
        connection_layout.addWidget(self.disconnect_btn)
        
        layout.addWidget(connection_group)
        
        # Estado de calibración existente
        existing_group = QGroupBox("📋 Calibración Existente")
        existing_layout = QVBoxLayout(existing_group)
        
        self.existing_info = QLabel("No hay calibración guardada")
        existing_layout.addWidget(self.existing_info)
        
        layout.addWidget(existing_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "🔌 Conexión")
    
    def _create_direction_test_tab(self):
        """Tab para probar direcciones de movimiento"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Instrucciones
        instructions = QLabel("""
🧪 <b>Prueba de Direcciones</b><br>
Esta prueba mueve la cámara en cada dirección para verificar que los movimientos 
sean correctos. Observe la cámara y confirme si los movimientos coinciden con 
las direcciones indicadas.
        """)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Controles de prueba
        test_group = QGroupBox("🎮 Controles de Prueba")
        test_layout = QGridLayout(test_group)
        
        # Botones direccionales
        self.test_up_btn = QPushButton("↑ Probar ARRIBA")
        self.test_down_btn = QPushButton("↓ Probar ABAJO")
        self.test_left_btn = QPushButton("← Probar IZQUIERDA")
        self.test_right_btn = QPushButton("→ Probar DERECHA")
        
        self.test_up_btn.clicked.connect(lambda: self._test_single_direction("up"))
        self.test_down_btn.clicked.connect(lambda: self._test_single_direction("down"))
        self.test_left_btn.clicked.connect(lambda: self._test_single_direction("left"))
        self.test_right_btn.clicked.connect(lambda: self._test_single_direction("right"))
        
        test_layout.addWidget(self.test_up_btn, 0, 1)
        test_layout.addWidget(self.test_left_btn, 1, 0)
        test_layout.addWidget(self.test_right_btn, 1, 2)
        test_layout.addWidget(self.test_down_btn, 2, 1)
        
        layout.addWidget(test_group)
        
        # Configuración de inversión
        inversion_group = QGroupBox("🔄 Configuración de Direcciones")
        inversion_layout = QFormLayout(inversion_group)
        
        self.pan_inverted_cb = QCheckBox("Invertir movimiento PAN (izq/der)")
        self.tilt_inverted_cb = QCheckBox("Invertir movimiento TILT (arr/abj)")
        
        inversion_layout.addRow(self.pan_inverted_cb)
        inversion_layout.addRow(self.tilt_inverted_cb)
        
        self.apply_inversion_btn = QPushButton("✅ Aplicar Inversiones")
        self.apply_inversion_btn.clicked.connect(self._apply_direction_inversion)
        inversion_layout.addRow(self.apply_inversion_btn)
        
        layout.addWidget(inversion_group)
        
        # Prueba automática completa
        auto_test_group = QGroupBox("🤖 Prueba Automática")
        auto_test_layout = QVBoxLayout(auto_test_group)
        
        self.auto_test_btn = QPushButton("🔄 Ejecutar Prueba Completa")
        self.auto_test_btn.clicked.connect(self._run_automatic_test)
        
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        
        auto_test_layout.addWidget(self.auto_test_btn)
        auto_test_layout.addWidget(self.test_progress)
        
        layout.addWidget(auto_test_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "🧪 Direcciones")
    
    def _create_center_calibration_tab(self):
        """Tab para calibración del centro"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Instrucciones
        instructions = QLabel("""
🎯 <b>Calibración del Centro</b><br>
Para calibrar el centro de imagen:
1. Active la detección de objetos
2. Cuando aparezca un objeto detectado, haga clic en "Agregar Punto"
3. Repita con el objeto en diferentes posiciones
4. Finalice la calibración para calcular el centro corregido
        """)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Estado de calibración
        status_group = QGroupBox("📊 Estado de Calibración")
        status_layout = QFormLayout(status_group)
        
        self.points_count_label = QLabel("0")
        self.current_offset_label = QLabel("No calibrado")
        
        status_layout.addRow("Puntos recolectados:", self.points_count_label)
        status_layout.addRow("Offset actual:", self.current_offset_label)
        
        layout.addWidget(status_group)
        
        # Controles de calibración
        calibration_group = QGroupBox("🎯 Controles de Calibración")
        calibration_layout = QVBoxLayout(calibration_group)
        
        point_controls = QHBoxLayout()
        
        self.add_point_btn = QPushButton("📍 Agregar Punto Actual")
        self.add_point_btn.clicked.connect(self._add_calibration_point)
        self.add_point_btn.setEnabled(False)
        
        self.clear_points_btn = QPushButton("🗑️ Limpiar Puntos")
        self.clear_points_btn.clicked.connect(self._clear_calibration_points)
        
        point_controls.addWidget(self.add_point_btn)
        point_controls.addWidget(self.clear_points_btn)
        
        calibration_layout.addLayout(point_controls)
        
        self.finalize_calibration_btn = QPushButton("✅ Finalizar Calibración de Centro")
        self.finalize_calibration_btn.clicked.connect(self._finalize_center_calibration)
        self.finalize_calibration_btn.setEnabled(False)
        
        calibration_layout.addWidget(self.finalize_calibration_btn)
        
        layout.addWidget(calibration_group)
        
        # Calibración manual
        manual_group = QGroupBox("✋ Calibración Manual")
        manual_layout = QFormLayout(manual_group)
        
        self.manual_offset_x = QDoubleSpinBox()
        self.manual_offset_x.setRange(-0.5, 0.5)
        self.manual_offset_x.setDecimals(4)
        self.manual_offset_x.setSingleStep(0.001)
        
        self.manual_offset_y = QDoubleSpinBox()
        self.manual_offset_y.setRange(-0.5, 0.5)
        self.manual_offset_y.setDecimals(4)
        self.manual_offset_y.setSingleStep(0.001)
        
        manual_layout.addRow("Offset X:", self.manual_offset_x)
        manual_layout.addRow("Offset Y:", self.manual_offset_y)
        
        self.apply_manual_btn = QPushButton("✅ Aplicar Offset Manual")
        self.apply_manual_btn.clicked.connect(self._apply_manual_offset)
        manual_layout.addRow(self.apply_manual_btn)
        
        layout.addWidget(manual_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "🎯 Centro")
    
    def _create_advanced_tab(self):
        """Tab para ajustes avanzados"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Sensibilidad
        sensitivity_group = QGroupBox("🎛️ Sensibilidad de Movimiento")
        sensitivity_layout = QFormLayout(sensitivity_group)
        
        self.pan_sensitivity = QDoubleSpinBox()
        self.pan_sensitivity.setRange(0.001, 0.1)
        self.pan_sensitivity.setDecimals(4)
        self.pan_sensitivity.setValue(0.005)
        self.pan_sensitivity.setSingleStep(0.001)
        
        self.tilt_sensitivity = QDoubleSpinBox()
        self.tilt_sensitivity.setRange(0.001, 0.1)
        self.tilt_sensitivity.setDecimals(4)
        self.tilt_sensitivity.setValue(0.005)
        self.tilt_sensitivity.setSingleStep(0.001)
        
        sensitivity_layout.addRow("Sensibilidad PAN:", self.pan_sensitivity)
        sensitivity_layout.addRow("Sensibilidad TILT:", self.tilt_sensitivity)
        
        self.apply_sensitivity_btn = QPushButton("✅ Aplicar Sensibilidad")
        self.apply_sensitivity_btn.clicked.connect(self._apply_sensitivity)
        sensitivity_layout.addRow(self.apply_sensitivity_btn)
        
        layout.addWidget(sensitivity_group)
        
        # Zona muerta
        deadzone_group = QGroupBox("🎯 Zona Muerta (Deadzone)")
        deadzone_layout = QFormLayout(deadzone_group)
        
        self.deadzone_x = QDoubleSpinBox()
        self.deadzone_x.setRange(0.01, 0.2)
        self.deadzone_x.setDecimals(3)
        self.deadzone_x.setValue(0.03)
        self.deadzone_x.setSingleStep(0.01)
        
        self.deadzone_y = QDoubleSpinBox()
        self.deadzone_y.setRange(0.01, 0.2)
        self.deadzone_y.setDecimals(3)
        self.deadzone_y.setValue(0.03)
        self.deadzone_y.setSingleStep(0.01)
        
        deadzone_layout.addRow("Deadzone X:", self.deadzone_x)
        deadzone_layout.addRow("Deadzone Y:", self.deadzone_y)
        
        self.apply_deadzone_btn = QPushButton("✅ Aplicar Zona Muerta")
        self.apply_deadzone_btn.clicked.connect(self._apply_deadzone)
        deadzone_layout.addRow(self.apply_deadzone_btn)
        
        layout.addWidget(deadzone_group)
        
        # Prueba de seguimiento
        test_tracking_group = QGroupBox("🧪 Prueba de Seguimiento")
        test_tracking_layout = QVBoxLayout(test_tracking_group)
        
        # Coordenadas de prueba
        test_coords_layout = QHBoxLayout()
        
        self.test_x = QSpinBox()
        self.test_x.setRange(0, 1920)
        self.test_x.setValue(960)
        
        self.test_y = QSpinBox()
        self.test_y.setRange(0, 1080)
        self.test_y.setValue(540)
        
        test_coords_layout.addWidget(QLabel("X:"))
        test_coords_layout.addWidget(self.test_x)
        test_coords_layout.addWidget(QLabel("Y:"))
        test_coords_layout.addWidget(self.test_y)
        
        test_tracking_layout.addLayout(test_coords_layout)
        
        self.test_tracking_btn = QPushButton("🎯 Probar Seguimiento a Punto")
        self.test_tracking_btn.clicked.connect(self._test_tracking)
        test_tracking_layout.addWidget(self.test_tracking_btn)
        
        layout.addWidget(test_tracking_group)
        
        # Reset completo
        reset_group = QGroupBox("🔄 Reset de Calibración")
        reset_layout = QVBoxLayout(reset_group)
        
        self.reset_btn = QPushButton("⚠️ Reset Completo de Calibración")
        self.reset_btn.setStyleSheet("QPushButton { background-color: #ff6b6b; color: white; font-weight: bold; }")
        self.reset_btn.clicked.connect(self._reset_calibration)
        reset_layout.addWidget(self.reset_btn)
        
        layout.addWidget(reset_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "⚙️ Avanzado")
    
    def _connect_signals(self):
        """Conectar señales"""
        pass
    
    def _load_camera_data(self):
        """Cargar datos de la cámara"""
        ip = self.camera_data.get('ip', 'Desconocido')
        tipo = self.camera_data.get('tipo', 'Desconocido')
        
        self.ip_label.setText(ip)
        self.type_label.setText(tipo.upper())
        
        self._log(f"📷 Cámara cargada: {ip} ({tipo})")
        
        # Cargar calibración existente si existe
        self._load_existing_calibration()
    
    def _load_existing_calibration(self):
        """Cargar calibración existente"""
        if not CALIBRATION_AVAILABLE or not self.camera_data.get('ip'):
            return
        
        try:
            from core.ptz_calibration_system import CalibrationData
            
            ip = self.camera_data.get('ip')
            calibration = CalibrationData.load_from_file(ip)
            
            if calibration.calibration_date:
                info_text = f"""
📅 Fecha: {calibration.calibration_date[:10]}
🎯 Offset X: {calibration.center_offset_x:.4f}
🎯 Offset Y: {calibration.center_offset_y:.4f}
🎛️ Pan Sens: {calibration.pan_sensitivity:.4f}
🎛️ Tilt Sens: {calibration.tilt_sensitivity:.4f}
🔄 Pan Dir: {'Invertido' if calibration.pan_direction == -1 else 'Normal'}
🔄 Tilt Dir: {'Invertido' if calibration.tilt_direction == -1 else 'Normal'}
                """
                self.existing_info.setText(info_text.strip())
                
                # Cargar valores en la UI
                self.manual_offset_x.setValue(calibration.center_offset_x)
                self.manual_offset_y.setValue(calibration.center_offset_y)
                self.pan_sensitivity.setValue(calibration.pan_sensitivity)
                self.tilt_sensitivity.setValue(calibration.tilt_sensitivity)
                self.deadzone_x.setValue(calibration.deadzone_x)
                self.deadzone_y.setValue(calibration.deadzone_y)
                self.pan_inverted_cb.setChecked(calibration.pan_direction == -1)
                self.tilt_inverted_cb.setChecked(calibration.tilt_direction == -1)
                
                self._log(f"✅ Calibración existente cargada para {ip}")
            else:
                self.existing_info.setText("No hay calibración guardada")
                self._log(f"ℹ️ No hay calibración para {ip}")
                
        except Exception as e:
            self._log(f"❌ Error cargando calibración: {e}")
    
    def _connect_camera(self):
        """Conectar a la cámara PTZ"""
        if not CALIBRATION_AVAILABLE:
            self._log("❌ Sistema de calibración no disponible")
            return
        
        if not self.camera_data:
            self._log("❌ No hay datos de cámara")
            return
        
        try:
            ip = self.camera_data.get('ip')
            port = self.camera_data.get('puerto', 80)
            username = self.camera_data.get('usuario', 'admin')
            password = self.camera_data.get('contrasena', 'admin123')
            
            self._log(f"🔗 Conectando a {ip}:{port}...")
            
            success = self.calibration_system.start_calibration(ip, port, username, password)
            
            if success:
                self.status_label.setText("✅ Conectado")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                self._enable_calibration_controls(True)
                self._log(f"✅ Conectado exitosamente a {ip}")
            else:
                self.status_label.setText("❌ Error de conexión")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                self._log(f"❌ Error conectando a {ip}")
                
        except Exception as e:
            self._log(f"❌ Error en conexión: {e}")
            self.status_label.setText("❌ Error de conexión")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _disconnect_camera(self):
        """Desconectar de la cámara"""
        self.calibration_system = None
        if CALIBRATION_AVAILABLE:
            from core.ptz_calibration_system import PTZCalibrationSystem
            self.calibration_system = PTZCalibrationSystem()
        
        self.status_label.setText("❌ Desconectado")
        self.status_label.setStyleSheet("color: gray;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self._enable_calibration_controls(False)
        self._log("🔌 Desconectado de la cámara")
    
    def _enable_calibration_controls(self, enabled: bool):
        """Habilitar/deshabilitar controles de calibración"""
        # Tab direcciones
        self.test_up_btn.setEnabled(enabled)
        self.test_down_btn.setEnabled(enabled)
        self.test_left_btn.setEnabled(enabled)
        self.test_right_btn.setEnabled(enabled)
        self.auto_test_btn.setEnabled(enabled)
        self.apply_inversion_btn.setEnabled(enabled)
        
        # Tab avanzado
        self.apply_sensitivity_btn.setEnabled(enabled)
        self.apply_deadzone_btn.setEnabled(enabled)
        self.test_tracking_btn.setEnabled(enabled)
        
        # Botón guardar
        self.save_btn.setEnabled(enabled)
    
    def _test_single_direction(self, direction: str):
        """Probar una dirección específica"""
        if not self.calibration_system or not self.calibration_system.current_camera:
            self._log("❌ No hay cámara conectada")
            return
        
        self._log(f"🧪 Probando movimiento: {direction.upper()}")
        
        try:
            speed = 0.3
            duration = 1.0
            
            if direction == "up":
                self.calibration_system.current_camera.continuous_move(0, speed, 0)
            elif direction == "down":
                self.calibration_system.current_camera.continuous_move(0, -speed, 0)
            elif direction == "left":
                self.calibration_system.current_camera.continuous_move(-speed, 0, 0)
            elif direction == "right":
                self.calibration_system.current_camera.continuous_move(speed, 0, 0)
            
            # Crear timer para detener el movimiento
            self.stop_timer = QTimer()
            self.stop_timer.timeout.connect(self._stop_movement)
            self.stop_timer.setSingleShot(True)
            self.stop_timer.start(int(duration * 1000))
            
        except Exception as e:
            self._log(f"❌ Error en prueba de dirección: {e}")
    
    def _stop_movement(self):
        """Detener movimiento de la cámara"""
        if self.calibration_system and self.calibration_system.current_camera:
            self.calibration_system.current_camera.stop()
            self._log("⏹️ Movimiento detenido")
    
    def _run_automatic_test(self):
        """Ejecutar prueba automática de direcciones"""
        if not self.calibration_system:
            self._log("❌ No hay sistema de calibración")
            return
        
        self._log("🤖 Iniciando prueba automática...")
        self.test_progress.setVisible(True)
        self.test_progress.setValue(0)
        self.auto_test_btn.setEnabled(False)
        
        # Crear y configurar hilo de prueba
        self.test_thread = CalibrationTestThread(self.calibration_system)
        self.test_thread.test_completed.connect(self._on_test_completed)
        self.test_thread.log_message.connect(self._log)
        self.test_thread.set_test("directions")
        self.test_thread.start()
    
    def _on_test_completed(self, results: dict):
        """Manejar finalización de prueba"""
        self.test_progress.setVisible(False)
        self.auto_test_btn.setEnabled(True)
        
        if "error" in results:
            self._log(f"❌ Error en prueba: {results['error']}")
        else:
            self._log("✅ Prueba de direcciones completada:")
            for direction, result in results.items():
                self._log(f"   {direction}: {result}")
    
    def _apply_direction_inversion(self):
        """Aplicar configuración de inversión de direcciones"""
        if not self.calibration_system:
            self._log("❌ No hay sistema de calibración")
            return
        
        pan_inverted = self.pan_inverted_cb.isChecked()
        tilt_inverted = self.tilt_inverted_cb.isChecked()
        
        success = self.calibration_system.set_direction_inversion(pan_inverted, tilt_inverted)
        
        if success:
            self._log(f"✅ Direcciones configuradas: PAN={'Inv' if pan_inverted else 'Norm'}, TILT={'Inv' if tilt_inverted else 'Norm'}")
        else:
            self._log("❌ Error aplicando inversión de direcciones")
    
    def _add_calibration_point(self):
        """Agregar punto de calibración actual"""
        # Esta función sería llamada desde el sistema principal cuando hay una detección
        self._log("📍 Para agregar puntos, active la detección y presione este botón cuando vea objetos detectados")
    
    def add_detection_point(self, center_x: float, center_y: float, frame_w: int, frame_h: int):
        """Método público para agregar punto desde detección externa"""
        if not self.calibration_system:
            return
        
        self.calibration_system.add_calibration_point((center_x, center_y), (frame_w, frame_h))
        
        point_count = len(self.calibration_system.calibration_points)
        self.points_count_label.setText(str(point_count))
        
        if point_count >= 3:
            self.finalize_calibration_btn.setEnabled(True)
            self.add_point_btn.setEnabled(True)
        
        self._log(f"📍 Punto agregado: ({center_x:.1f}, {center_y:.1f}) - Total: {point_count}")
    
    def _clear_calibration_points(self):
        """Limpiar puntos de calibración"""
        if self.calibration_system:
            self.calibration_system.calibration_points.clear()
        
        self.points_count_label.setText("0")
        self.finalize_calibration_btn.setEnabled(False)
        self._log("🗑️ Puntos de calibración limpiados")
    
    def _finalize_center_calibration(self):
        """Finalizar calibración del centro"""
        if not self.calibration_system:
            self._log("❌ No hay sistema de calibración")
            return
        
        # Usar tamaño de frame típico si no se especifica
        frame_size = (1920, 1080)  # Se puede actualizar según la cámara
        
        success = self.calibration_system.finalize_calibration(frame_size)
        
        if success:
            calibration = self.calibration_system.current_calibration
            self.current_offset_label.setText(f"X: {calibration.center_offset_x:.4f}, Y: {calibration.center_offset_y:.4f}")
            self.manual_offset_x.setValue(calibration.center_offset_x)
            self.manual_offset_y.setValue(calibration.center_offset_y)
            self._log("✅ Calibración de centro finalizada exitosamente")
        else:
            self._log("❌ Error finalizando calibración de centro")
    
    def _apply_manual_offset(self):
        """Aplicar offset manual"""
        if not self.calibration_system or not self.calibration_system.current_calibration:
            self._log("❌ No hay calibración activa")
            return
        
        offset_x = self.manual_offset_x.value()
        offset_y = self.manual_offset_y.value()
        
        self.calibration_system.current_calibration.center_offset_x = offset_x
        self.calibration_system.current_calibration.center_offset_y = offset_y
        
        self.current_offset_label.setText(f"X: {offset_x:.4f}, Y: {offset_y:.4f}")
        self._log(f"✅ Offset manual aplicado: X={offset_x:.4f}, Y={offset_y:.4f}")
    
    def _apply_sensitivity(self):
        """Aplicar configuración de sensibilidad"""
        if not self.calibration_system:
            self._log("❌ No hay sistema de calibración")
            return
        
        pan_sens = self.pan_sensitivity.value()
        tilt_sens = self.tilt_sensitivity.value()
        
        success = self.calibration_system.adjust_sensitivity(pan_sens, tilt_sens)
        
        if success:
            self._log(f"✅ Sensibilidad aplicada: PAN={pan_sens:.4f}, TILT={tilt_sens:.4f}")
        else:
            self._log("❌ Error aplicando sensibilidad")
    
    def _apply_deadzone(self):
        """Aplicar configuración de zona muerta"""
        if not self.calibration_system or not self.calibration_system.current_calibration:
            self._log("❌ No hay calibración activa")
            return
        
        deadzone_x = self.deadzone_x.value()
        deadzone_y = self.deadzone_y.value()
        
        self.calibration_system.current_calibration.deadzone_x = deadzone_x
        self.calibration_system.current_calibration.deadzone_y = deadzone_y
        
        self._log(f"✅ Zona muerta aplicada: X={deadzone_x:.3f}, Y={deadzone_y:.3f}")
    
    def _test_tracking(self):
        """Probar seguimiento a punto específico"""
        if not self.calibration_system:
            self._log("❌ No hay sistema de calibración")
            return
        
        test_x = self.test_x.value()
        test_y = self.test_y.value()
        frame_size = (1920, 1080)  # Tamaño típico
        
        self._log(f"🎯 Probando seguimiento a punto ({test_x}, {test_y})")
        
        try:
            from core.ptz_calibration_system import track_object_calibrated
            
            ip = self.camera_data.get('ip')
            port = self.camera_data.get('puerto', 80)
            username = self.camera_data.get('usuario', 'admin')
            password = self.camera_data.get('contrasena', 'admin123')
            
            success = track_object_calibrated(
                ip, port, username, password,
                (test_x, test_y), frame_size
            )
            
            if success:
                self._log("✅ Prueba de seguimiento exitosa")
            else:
                self._log("❌ Error en prueba de seguimiento")
                
        except Exception as e:
            self._log(f"❌ Error en prueba: {e}")
    
    def _save_calibration(self):
        """Guardar calibración actual"""
        if not self.calibration_system or not self.calibration_system.current_calibration:
            self._log("❌ No hay calibración para guardar")
            return
        
        success = self.calibration_system.current_calibration.save_to_file()
        
        if success:
            self._log("💾 Calibración guardada exitosamente")
            QMessageBox.information(self, "Calibración Guardada", 
                                   "✅ La calibración se ha guardado correctamente.")
            self.calibration_completed.emit(self.camera_data.get('ip', ''))
        else:
            self._log("❌ Error guardando calibración")
            QMessageBox.critical(self, "Error", "❌ Error guardando la calibración.")
    
    def _load_calibration(self):
        """Cargar calibración desde archivo"""
        self._load_existing_calibration()
        self._log("📂 Calibración recargada desde archivo")
    
    def _reset_calibration(self):
        """Reset completo de calibración"""
        reply = QMessageBox.question(
            self, "Reset Calibración",
            "⚠️ ¿Está seguro de que desea resetear toda la calibración?\n\n"
            "Esto eliminará todos los valores calibrados y volverá a los valores por defecto.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.calibration_system and self.camera_data.get('ip'):
                from core.ptz_calibration_system import CalibrationData
                
                # Crear nueva calibración con valores por defecto
                ip = self.camera_data.get('ip')
                self.calibration_system.current_calibration = CalibrationData(camera_ip=ip)
                
                # Resetear UI
                self.manual_offset_x.setValue(0.0)
                self.manual_offset_y.setValue(0.0)
                self.pan_sensitivity.setValue(0.005)
                self.tilt_sensitivity.setValue(0.005)
                self.deadzone_x.setValue(0.03)
                self.deadzone_y.setValue(0.03)
                self.pan_inverted_cb.setChecked(False)
                self.tilt_inverted_cb.setChecked(False)
                self.current_offset_label.setText("No calibrado")
                self.points_count_label.setText("0")
                
                self._log("🔄 Calibración reseteada a valores por defecto")
    
    def _log(self, message: str):
        """Agregar mensaje al log"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_display.append(formatted_message)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

def create_calibration_dialog(parent=None, camera_data=None):
    """Crear diálogo de calibración PTZ"""
    if not CALIBRATION_AVAILABLE:
        QMessageBox.critical(
            parent, "Error",
            "❌ Sistema de calibración PTZ no disponible.\n\n"
            "Módulos requeridos:\n"
            "• core/ptz_calibration_system.py\n"
            "• core/ptz_control.py"
        )
        return None
    
    return PTZCalibrationDialog(parent, camera_data)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Datos de cámara de ejemplo
    camera_data = {
        'ip': '192.168.1.100',
        'puerto': 80,
        'usuario': 'admin',
        'contrasena': 'admin123',
        'tipo': 'ptz'
    }
    
    dialog = create_calibration_dialog(camera_data=camera_data)
    if dialog:
        dialog.show()
        sys.exit(app.exec())