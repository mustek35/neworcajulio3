# core/ptz_diagnostic_system.py
"""
Sistema de diagnóstico para PTZ Multi-Objeto
Identifica y resuelve problemas comunes en el seguimiento multi-objeto
"""

import time
import json
import os
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DiagnosticResult:
    """Resultado de diagnóstico"""
    component: str
    status: str  # "OK", "WARNING", "ERROR"
    message: str
    details: Dict[str, Any] = None
    solution: str = ""

class PTZMultiObjectDiagnostic:
    """Sistema de diagnóstico para PTZ Multi-Objeto"""
    
    def __init__(self):
        self.results: List[DiagnosticResult] = []
        self.camera_data = None
        self.detection_data = None
        
    def run_full_diagnostic(self, camera_data: Dict, detection_data: Dict = None) -> List[DiagnosticResult]:
        """Ejecutar diagnóstico completo"""
        self.camera_data = camera_data
        self.detection_data = detection_data or {}
        self.results.clear()
        
        print("🔍 Iniciando diagnóstico PTZ Multi-Objeto...")
        print("=" * 50)
        
        # 1. Verificar disponibilidad de módulos
        self._check_module_availability()
        
        # 2. Verificar configuración de cámara
        self._check_camera_configuration()
        
        # 3. Verificar conexión PTZ
        self._check_ptz_connection()
        
        # 4. Verificar sistema multi-objeto
        self._check_multi_object_system()
        
        # 5. Verificar integración con detecciones
        self._check_detection_integration()
        
        # 6. Verificar configuración de seguimiento
        self._check_tracking_configuration()
        
        # 7. Generar reporte y soluciones
        self._generate_solutions()
        
        return self.results
    
    def _check_module_availability(self):
        """Verificar disponibilidad de módulos requeridos"""
        print("📦 Verificando módulos...")
        
        # Módulos básicos PTZ
        try:
            from core.ptz_control import PTZCameraONVIF
            self._add_result("ptz_basic", "OK", "✅ Módulo PTZ básico disponible")
        except ImportError as e:
            self._add_result("ptz_basic", "ERROR", 
                           f"❌ Módulo PTZ básico no disponible: {e}",
                           solution="Verificar que existe core/ptz_control.py")
        
        # Sistema multi-objeto
        try:
            from core.multi_object_ptz_system import MultiObjectPTZTracker, MultiObjectConfig
            self._add_result("multi_object", "OK", "✅ Sistema multi-objeto disponible")
        except ImportError as e:
            self._add_result("multi_object", "ERROR", 
                           f"❌ Sistema multi-objeto no disponible: {e}",
                           solution="Verificar que existe core/multi_object_ptz_system.py")
        
        # Sistema de integración
        try:
            from core.ptz_tracking_integration_enhanced import PTZTrackingSystemEnhanced
            self._add_result("integration", "OK", "✅ Sistema de integración disponible")
        except ImportError as e:
            self._add_result("integration", "WARNING", 
                           f"⚠️ Sistema de integración no disponible: {e}",
                           solution="Verificar core/ptz_tracking_integration_enhanced.py")
        
        # Librería ONVIF
        try:
            from onvif import ONVIFCamera
            self._add_result("onvif", "OK", "✅ Librería ONVIF disponible")
        except ImportError as e:
            self._add_result("onvif", "ERROR", 
                           f"❌ Librería ONVIF no disponible: {e}",
                           solution="Instalar con: pip install onvif-zeep")
    
    def _check_camera_configuration(self):
        """Verificar configuración de cámara"""
        print("📷 Verificando configuración de cámara...")
        
        if not self.camera_data:
            self._add_result("camera_data", "ERROR", "❌ No hay datos de cámara",
                           solution="Proporcionar datos de cámara válidos")
            return
        
        # Verificar campos requeridos
        required_fields = ['ip', 'tipo', 'usuario', 'contrasena']
        missing_fields = []
        
        for field in required_fields:
            if not self.camera_data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            self._add_result("camera_fields", "ERROR", 
                           f"❌ Campos faltantes: {', '.join(missing_fields)}",
                           solution="Completar configuración de cámara")
        else:
            self._add_result("camera_fields", "OK", "✅ Campos de cámara completos")
        
        # Verificar tipo PTZ
        tipo = self.camera_data.get('tipo', '').lower()
        if tipo != 'ptz':
            self._add_result("camera_type", "ERROR", 
                           f"❌ Tipo de cámara es '{tipo}', debe ser 'ptz'",
                           solution="Cambiar tipo de cámara a 'ptz'")
        else:
            self._add_result("camera_type", "OK", "✅ Cámara configurada como PTZ")
        
        # Verificar IP válida
        ip = self.camera_data.get('ip', '')
        if not self._is_valid_ip(ip):
            self._add_result("camera_ip", "ERROR", 
                           f"❌ IP inválida: {ip}",
                           solution="Verificar IP de la cámara")
        else:
            self._add_result("camera_ip", "OK", f"✅ IP válida: {ip}")
    
    def _check_ptz_connection(self):
        """Verificar conexión PTZ"""
        print("🔗 Verificando conexión PTZ...")
        
        if not self.camera_data:
            return
        
        try:
            from core.ptz_control import PTZCameraONVIF
            
            ip = self.camera_data.get('ip')
            port = self.camera_data.get('puerto', 80)
            username = self.camera_data.get('usuario')
            password = self.camera_data.get('contrasena')
            
            print(f"   Probando conexión a {ip}:{port}...")
            
            # Intentar conexión básica
            ptz_cam = PTZCameraONVIF(ip, port, username, password)
            
            # Probar obtener perfiles
            profiles = ptz_cam.media.GetProfiles()
            if profiles:
                self._add_result("ptz_connection", "OK", 
                               f"✅ Conexión PTZ exitosa ({len(profiles)} perfiles)",
                               details={"profiles": len(profiles)})
            else:
                self._add_result("ptz_connection", "WARNING", 
                               "⚠️ Conexión PTZ sin perfiles",
                               solution="Verificar configuración de perfiles en cámara")
            
            # Probar servicio PTZ
            try:
                ptz_service = ptz_cam.ptz
                if ptz_service:
                    self._add_result("ptz_service", "OK", "✅ Servicio PTZ disponible")
                else:
                    self._add_result("ptz_service", "ERROR", "❌ Servicio PTZ no disponible",
                                   solution="Verificar que la cámara soporta PTZ")
            except Exception as e:
                self._add_result("ptz_service", "ERROR", 
                               f"❌ Error accediendo servicio PTZ: {e}",
                               solution="Verificar configuración ONVIF de la cámara")
            
        except Exception as e:
            self._add_result("ptz_connection", "ERROR", 
                           f"❌ Error de conexión PTZ: {e}",
                           solution="Verificar IP, puerto, usuario y contraseña")
    
    def _check_multi_object_system(self):
        """Verificar sistema multi-objeto"""
        print("🎯 Verificando sistema multi-objeto...")
        
        try:
            from core.multi_object_ptz_system import (
                MultiObjectPTZTracker, MultiObjectConfig, 
                create_multi_object_tracker
            )
            
            # Verificar creación de configuración
            try:
                config = MultiObjectConfig()
                is_valid = config.validate()
                if is_valid:
                    self._add_result("multi_config", "OK", "✅ Configuración multi-objeto válida")
                else:
                    self._add_result("multi_config", "ERROR", "❌ Configuración multi-objeto inválida",
                                   solution="Revisar parámetros de MultiObjectConfig")
            except Exception as e:
                self._add_result("multi_config", "ERROR", 
                               f"❌ Error en configuración: {e}",
                               solution="Verificar MultiObjectConfig")
            
            # Verificar creación de tracker
            if self.camera_data:
                try:
                    ip = self.camera_data.get('ip')
                    port = self.camera_data.get('puerto', 80)
                    username = self.camera_data.get('usuario')
                    password = self.camera_data.get('contrasena')
                    
                    # Solo probar creación, no inicialización completa
                    tracker = MultiObjectPTZTracker(ip, port, username, password)
                    if tracker:
                        self._add_result("multi_tracker", "OK", "✅ Tracker multi-objeto creado")
                    else:
                        self._add_result("multi_tracker", "ERROR", "❌ No se pudo crear tracker",
                                       solution="Verificar parámetros de conexión")
                        
                except Exception as e:
                    self._add_result("multi_tracker", "ERROR", 
                                   f"❌ Error creando tracker: {e}",
                                   solution="Verificar inicialización de MultiObjectPTZTracker")
            
        except ImportError:
            self._add_result("multi_system", "ERROR", "❌ Sistema multi-objeto no importable",
                           solution="Verificar core/multi_object_ptz_system.py")
    
    def _check_detection_integration(self):
        """Verificar integración con sistema de detección"""
        print("🔍 Verificando integración de detecciones...")
        
        # Verificar que hay detecciones
        if not self.detection_data:
            self._add_result("detection_data", "WARNING", 
                           "⚠️ No hay datos de detección para probar",
                           solution="Activar sistema de detección")
            return
        
        # Verificar formato de detecciones
        try:
            detections = self.detection_data.get('detections', [])
            if not detections:
                self._add_result("detection_format", "WARNING", 
                               "⚠️ No hay detecciones activas",
                               solution="Verificar que YOLO está detectando objetos")
            else:
                # Verificar formato de detección
                sample_detection = detections[0]
                required_fields = ['bbox', 'confidence', 'class']
                
                missing_fields = [f for f in required_fields if f not in sample_detection]
                if missing_fields:
                    self._add_result("detection_format", "ERROR", 
                                   f"❌ Formato de detección incompleto: falta {missing_fields}",
                                   solution="Verificar formato de salida de YOLO")
                else:
                    self._add_result("detection_format", "OK", 
                                   f"✅ Formato de detección correcto ({len(detections)} detecciones)")
        
        except Exception as e:
            self._add_result("detection_format", "ERROR", 
                           f"❌ Error verificando detecciones: {e}",
                           solution="Verificar estructura de datos de detección")
    
    def _check_tracking_configuration(self):
        """Verificar configuración de seguimiento"""
        print("⚙️ Verificando configuración de seguimiento...")
        
        # Verificar archivos de configuración
        config_files = [
            'camaras_config.json',
            'ptz_enhanced_config.json'
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    self._add_result(f"config_{config_file}", "OK", 
                                   f"✅ Archivo {config_file} válido")
                except json.JSONDecodeError:
                    self._add_result(f"config_{config_file}", "ERROR", 
                                   f"❌ Archivo {config_file} corrupto",
                                   solution=f"Reparar o eliminar {config_file}")
            else:
                self._add_result(f"config_{config_file}", "WARNING", 
                               f"⚠️ Archivo {config_file} no existe",
                               solution=f"Crear configuración inicial")
        
        # Verificar calibración PTZ
        if self.camera_data:
            ip = self.camera_data.get('ip', '').replace('.', '_')
            calib_file = f"calibration_{ip}.json"
            
            if os.path.exists(calib_file):
                self._add_result("ptz_calibration", "OK", 
                               f"✅ Calibración PTZ disponible")
            else:
                self._add_result("ptz_calibration", "WARNING", 
                               "⚠️ No hay calibración PTZ",
                               solution="Ejecutar calibración PTZ")
    
    def _generate_solutions(self):
        """Generar soluciones y recomendaciones"""
        print("\n📋 Generando reporte de diagnóstico...")
        
        errors = [r for r in self.results if r.status == "ERROR"]
        warnings = [r for r in self.results if r.status == "WARNING"]
        successes = [r for r in self.results if r.status == "OK"]
        
        print(f"\n✅ Exitosos: {len(successes)}")
        print(f"⚠️  Advertencias: {len(warnings)}")
        print(f"❌ Errores: {len(errors)}")
        
        # Generar soluciones prioritarias
        if errors:
            print("\n🔧 SOLUCIONES PRIORITARIAS:")
            for i, error in enumerate(errors, 1):
                print(f"{i}. {error.component}: {error.message}")
                if error.solution:
                    print(f"   💡 Solución: {error.solution}")
        
        if warnings:
            print("\n⚠️ RECOMENDACIONES:")
            for i, warning in enumerate(warnings, 1):
                print(f"{i}. {warning.component}: {warning.message}")
                if warning.solution:
                    print(f"   💡 Recomendación: {warning.solution}")
    
    def _add_result(self, component: str, status: str, message: str, 
                   details: Dict = None, solution: str = ""):
        """Agregar resultado de diagnóstico"""
        result = DiagnosticResult(
            component=component,
            status=status,
            message=message,
            details=details or {},
            solution=solution
        )
        self.results.append(result)
        print(f"   {message}")
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Verificar si IP es válida"""
        try:
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except:
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """Obtener resumen del diagnóstico"""
        errors = [r for r in self.results if r.status == "ERROR"]
        warnings = [r for r in self.results if r.status == "WARNING"]
        successes = [r for r in self.results if r.status == "OK"]
        
        return {
            "total_checks": len(self.results),
            "errors": len(errors),
            "warnings": len(warnings),
            "successes": len(successes),
            "error_components": [e.component for e in errors],
            "warning_components": [w.component for w in warnings],
            "critical_issues": [e for e in errors if e.component in [
                "ptz_basic", "multi_object", "ptz_connection", "camera_type"
            ]],
            "ready_for_tracking": len(errors) == 0
        }

def create_diagnostic_system() -> PTZMultiObjectDiagnostic:
    """Crear nueva instancia del sistema de diagnóstico"""
    return PTZMultiObjectDiagnostic()

def run_quick_diagnostic(camera_data: Dict) -> Dict[str, Any]:
    """Ejecutar diagnóstico rápido"""
    diagnostic = create_diagnostic_system()
    results = diagnostic.run_full_diagnostic(camera_data)
    return diagnostic.get_summary()

def diagnose_tracking_issue(camera_data: Dict, detection_data: Dict = None) -> List[str]:
    """Diagnosticar problema específico de seguimiento"""
    diagnostic = create_diagnostic_system()
    results = diagnostic.run_full_diagnostic(camera_data, detection_data)
    
    # Generar lista de soluciones prioritarias
    solutions = []
    
    errors = [r for r in results if r.status == "ERROR"]
    for error in errors:
        if error.solution:
            solutions.append(error.solution)
    
    # Agregar soluciones comunes basadas en problemas típicos
    if any("multi_object" in e.component for e in errors):
        solutions.append("Verificar instalación completa del sistema multi-objeto")
    
    if any("ptz_connection" in e.component for e in errors):
        solutions.append("Probar conexión manual PTZ antes de usar multi-objeto")
    
    if any("detection" in e.component for e in errors):
        solutions.append("Verificar que el sistema de detección está enviando datos")
    
    return solutions

# Funciones específicas para problemas comunes
def fix_multi_object_not_moving(camera_data: Dict) -> Dict[str, str]:
    """Diagnosticar por qué el multi-objeto no mueve la cámara"""
    print("🔍 Diagnosticando: Cámara no se mueve en multi-objeto...")
    
    issues = {}
    
    # 1. Verificar que la cámara es PTZ
    if camera_data.get('tipo', '').lower() != 'ptz':
        issues['camera_type'] = f"Tipo '{camera_data.get('tipo')}' debe ser 'ptz'"
    
    # 2. Verificar credenciales
    if not camera_data.get('usuario') or not camera_data.get('contrasena'):
        issues['credentials'] = "Faltan credenciales de usuario/contraseña"
    
    # 3. Verificar conexión básica
    try:
        from core.ptz_control import PTZCameraONVIF
        ip = camera_data.get('ip')
        port = camera_data.get('puerto', 80)
        username = camera_data.get('usuario')
        password = camera_data.get('contrasena')
        
        ptz_cam = PTZCameraONVIF(ip, port, username, password)
        profiles = ptz_cam.media.GetProfiles()
        
        if not profiles:
            issues['ptz_profiles'] = "No hay perfiles PTZ disponibles"
        
    except Exception as e:
        issues['ptz_connection'] = f"Error de conexión PTZ: {e}"
    
    # 4. Verificar sistema multi-objeto
    try:
        from core.multi_object_ptz_system import MultiObjectPTZTracker
    except ImportError:
        issues['multi_object_import'] = "Sistema multi-objeto no disponible"
    
    return issues

def fix_tracking_goes_up(camera_data: Dict) -> List[str]:
    """Generar soluciones para cámara que se va hacia arriba"""
    solutions = [
        "1. Usar sistema de calibración PTZ para corregir direcciones",
        "2. Verificar configuración 'tilt_direction' en calibración",
        "3. Reducir sensibilidad de TILT en configuración",
        "4. Ajustar valores de 'deadzone_y' para mayor tolerancia",
        "5. Probar movimientos manuales antes del seguimiento automático"
    ]
    
    return solutions

if __name__ == "__main__":
    # Ejemplo de uso del diagnóstico
    print("🧪 Sistema de Diagnóstico PTZ Multi-Objeto")
    print("=" * 50)
    
    # Datos de cámara de ejemplo
    camera_test_data = {
        'ip': '192.168.1.100',
        'puerto': 80,
        'usuario': 'admin',
        'contrasena': 'admin123',
        'tipo': 'ptz'
    }
    
    # Ejecutar diagnóstico
    diagnostic = create_diagnostic_system()
    results = diagnostic.run_full_diagnostic(camera_test_data)
    
    # Mostrar resumen
    summary = diagnostic.get_summary()
    print(f"\n📊 RESUMEN:")
    print(f"Total verificaciones: {summary['total_checks']}")
    print(f"Errores: {summary['errors']}")
    print(f"Advertencias: {summary['warnings']}")
    print(f"Exitosos: {summary['successes']}")
    print(f"Listo para seguimiento: {summary['ready_for_tracking']}")
    
    # Diagnóstico específico
    print(f"\n🔍 DIAGNÓSTICO ESPECÍFICO:")
    multi_object_issues = fix_multi_object_not_moving(camera_test_data)
    if multi_object_issues:
        print("Problemas encontrados:")
        for issue, description in multi_object_issues.items():
            print(f"  • {issue}: {description}")
    else:
        print("No se encontraron problemas en multi-objeto")
    
    tracking_solutions = fix_tracking_goes_up(camera_test_data)
    print(f"\nSoluciones para cámara que se va hacia arriba:")
    for solution in tracking_solutions:
        print(f"  {solution}")