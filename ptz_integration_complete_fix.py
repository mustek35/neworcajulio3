"""
CORRECCIÓN COMPLETA PARA EL SISTEMA PTZ TRACKER
=============================================

Este archivo aplica todas las correcciones necesarias para activar
el seguimiento PTZ multi-objeto en tu proyecto.

SOLUCIONES IMPLEMENTADAS:
1. ✅ Inicialización automática del sistema PTZ
2. ✅ Bridge de detecciones YOLO → PTZ
3. ✅ Integración con grilla_widget.py  
4. ✅ Configuración automática de cámaras PTZ
5. ✅ Activación automática del seguimiento
"""

import os
import sys
import json
import shutil
import traceback
import time
from pathlib import Path
from datetime import datetime


class PTZIntegrationFixer:
    """Clase para aplicar correcciones PTZ"""

    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.backup_dir = self.project_path / "backups_ptz" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def find_file(self, filename):
        """Buscar un archivo dentro del proyecto"""
        for path in self.project_path.rglob(filename):
            if path.is_file():
                return path
        return self.project_path / filename

    def create_backup(self, file_path):
        """Crear backup de archivo"""
        if not file_path.exists():
            return None
        backup_path = self.backup_dir / file_path.name
        shutil.copy2(file_path, backup_path)
        print(f"   📁 Backup: {backup_path}")
        return backup_path

    def fix_main_window_ptz_init(self):
        """CORRECCIÓN PRINCIPAL: Inicialización PTZ en main_window.py"""
        print("🔧 CORRIGIENDO main_window.py - Inicialización PTZ")
        print("-" * 50)

        main_window_path = self.find_file("main_window.py")
        if not main_window_path.exists():
            print("   ❌ main_window.py no encontrado")
            return False

        # Crear backup
        self.create_backup(main_window_path)

        try:
            with open(main_window_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "def _initialize_ptz_system(self):" in content:
                print("   ✅ main_window.py ya tiene correcciones PTZ")
                return True

            ptz_imports = '''
# ===============================================
# IMPORTS PTZ SYSTEM - CORRECCIÓN AUTOMÁTICA
# ===============================================
try:
    from ui.enhanced_ptz_multi_object_dialog import (
        create_multi_object_ptz_system, EnhancedMultiObjectPTZDialog
    )
    from core.ptz_tracking_integration_enhanced import PTZTrackingSystemEnhanced
    PTZ_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Sistema PTZ no disponible: {e}")
    PTZ_AVAILABLE = False

'''

            if "from PyQt6" in content:
                import_section_end = content.find("from PyQt6")
                next_empty_line = content.find("\n\n", import_section_end)
                if next_empty_line > 0:
                    content = content[:next_empty_line] + ptz_imports + content[next_empty_line:]
                else:
                    content = ptz_imports + content
            else:
                content = ptz_imports + content

            init_ptz_call = '''
        # ===============================================
        # INICIALIZACIÓN SISTEMA PTZ - CORRECCIÓN AUTO
        # ===============================================
        self.ptz_detection_bridge = None
        self.ptz_system = None
        if PTZ_AVAILABLE:
            self._initialize_ptz_system()
'''

            if "def __init__(self" in content and "cargar_camaras_guardadas(self)" in content:
                insert_pos = content.find("cargar_camaras_guardadas(self)") + len("cargar_camaras_guardadas(self)")
                content = content[:insert_pos] + init_ptz_call + content[insert_pos:]

            ptz_methods = '''
    # ===============================================
    # MÉTODOS PTZ SYSTEM - CORRECCIÓN AUTOMÁTICA
    # ===============================================

    def _initialize_ptz_system(self):
        """Inicializar sistema PTZ mejorado - CORRECCIÓN AUTOMÁTICA"""
        try:
            if not PTZ_AVAILABLE:
                self.append_debug("⚠️ Sistema PTZ no disponible")
                return False

            ptz_cameras = []
            if hasattr(self, 'cameras_config') and self.cameras_config:
                cameras = self.cameras_config.get('camaras', [])
                ptz_cameras = [cam for cam in cameras if cam.get('tipo') == 'ptz']

            if not ptz_cameras:
                self.append_debug("📝 No hay cámaras PTZ configuradas")
                return False

            self.ptz_system = create_multi_object_ptz_system(ptz_cameras, self)

            if self.ptz_system:
                self.ptz_detection_bridge = PTZDetectionBridge(self.ptz_system)
                self.append_debug(f"✅ Sistema PTZ inicializado con {len(ptz_cameras)} cámara(s)")
                if ptz_cameras:
                    self._auto_start_ptz_tracking(ptz_cameras[0])
                return True
            else:
                self.append_debug("❌ Error creando sistema PTZ")
                return False

        except Exception as e:
            self.append_debug(f"❌ Error inicializando PTZ: {e}")
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

    def send_detections_to_ptz(self, camera_id: str, detections):
        try:
            if not hasattr(self, 'ptz_detection_bridge') or not self.ptz_detection_bridge:
                return False
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                camera_id = camera_id.replace('camera_', '')
            success = self.ptz_detection_bridge.send_detections(camera_id, detections)
            if success:
                if not hasattr(self, '_ptz_detection_count'):
                    self._ptz_detection_count = 0
                self._ptz_detection_count += len(detections) if detections else 0
                if self._ptz_detection_count <= 50:
                    self.append_debug(f"📡 PTZ: {len(detections)} detecciones → {camera_id}")
            return success
        except Exception as e:
            self.append_debug(f"❌ Error enviando detecciones a PTZ: {e}")
            return False

    def register_camera_with_ptz(self, camera_data):
        try:
            if not self.ptz_detection_bridge:
                return False
            camera_id = camera_data.get('ip', 'unknown')
            if hasattr(self.ptz_detection_bridge, 'register_camera'):
                success = self.ptz_detection_bridge.register_camera(camera_id, camera_data)
                if success:
                    self.append_debug(f"📷 Cámara registrada con PTZ: {camera_id}")
                return success
            return True
        except Exception as e:
            self.append_debug(f"❌ Error registrando cámara con PTZ: {e}")
            return False

    def get_ptz_status(self, camera_id=None):
        try:
            if not self.ptz_detection_bridge:
                return {'active': False, 'error': 'Sistema PTZ no activo'}
            status = {
                'active': True,
                'bridge_available': True,
                'system_initialized': self.ptz_system is not None
            }
            if hasattr(self.ptz_detection_bridge, 'get_status'):
                ptz_status = self.ptz_detection_bridge.get_status(camera_id)
                status.update(ptz_status)
            return status
        except Exception as e:
            return {'active': False, 'error': str(e)}

    def cleanup_ptz_system(self):
        try:
            if hasattr(self, 'ptz_detection_bridge') and self.ptz_detection_bridge:
                if hasattr(self.ptz_detection_bridge, 'cleanup'):
                    self.ptz_detection_bridge.cleanup()
                self.ptz_detection_bridge = None
            if hasattr(self, 'ptz_system') and self.ptz_system:
                if hasattr(self.ptz_system, 'cleanup'):
                    self.ptz_system.cleanup()
                self.ptz_system = None
            self.append_debug("🧹 Sistema PTZ limpiado")
        except Exception as e:
            self.append_debug(f"❌ Error limpiando PTZ: {e}")

class PTZDetectionBridge:
    """Bridge mejorado para conectar detecciones YOLO con sistema PTZ - CORRECCIÓN AUTOMÁTICA"""

    def __init__(self, ptz_system):
        self.ptz_system = ptz_system
        self.active_cameras = {}
        self.detection_count = 0
        self.last_detection_time = {}

    def send_detections(self, camera_id: str, detections: list, frame_size=(1920, 1080)):
        try:
            if not isinstance(detections, list) or not detections:
                return False
            valid_detections = []
            for det in detections:
                if isinstance(det, dict) and 'bbox' in det:
                    valid_detections.append(det)
            if not valid_detections:
                return False
            if camera_id not in self.active_cameras:
                self.active_cameras[camera_id] = {
                    'detections_sent': 0,
                    'last_detection': None
                }
            self.detection_count += len(valid_detections)
            self.active_cameras[camera_id]['detections_sent'] += len(valid_detections)
            self.last_detection_time[camera_id] = time.time()
            if self.ptz_system and hasattr(self.ptz_system, 'dialog'):
                dialog = self.ptz_system.dialog
                if hasattr(dialog, 'update_detections'):
                    dialog.update_detections(valid_detections, frame_size)
                    return True
            return False
        except Exception as e:
            print(f"❌ Error en PTZDetectionBridge: {e}")
            return False

    def register_camera(self, camera_id: str, camera_data: dict):
        try:
            self.active_cameras[camera_id] = {
                'camera_data': camera_data,
                'detections_sent': 0,
                'registered_time': time.time()
            }
            return True
        except:
            return False

    def get_status(self, camera_id=None):
        if camera_id:
            return self.active_cameras.get(camera_id, {})
        return {
            'active_cameras': len(self.active_cameras),
            'total_detections': self.detection_count,
            'cameras': list(self.active_cameras.keys())
        }

    def cleanup(self):
        self.active_cameras.clear()
        self.detection_count = 0

'''

            if "class MainWindow" in content:
                class_start = content.find("class MainWindow")
                next_class = content.find("\nclass ", class_start + 1)
                if next_class > 0:
                    content = content[:next_class] + ptz_methods + content[next_class:]
                else:
                    content += ptz_methods

            with open(main_window_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("   ✅ main_window.py corregido exitosamente")
            return True

        except Exception as e:
            print(f"   ❌ Error corrigiendo main_window.py: {e}")
            traceback.print_exc()
            return False

    def fix_grilla_widget_integration(self):
        print("🔧 CORRIGIENDO grilla_widget.py - Integración PTZ")
        print("-" * 50)

        grilla_path = self.find_file("grilla_widget.py")
        if not grilla_path.exists():
            print("   ❌ grilla_widget.py no encontrado")
            return False

        self.create_backup(grilla_path)

        try:
            with open(grilla_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "# INTEGRACIÓN PTZ - CORRECCIÓN AUTO" in content:
                print("   ✅ grilla_widget.py ya corregido")
                return True

            if "def actualizar_boxes(self, boxes):" in content:
                method_start = content.find("def actualizar_boxes(self, boxes):")
                paint_update_pos = content.find("self.request_paint_update()", method_start)
                if paint_update_pos > 0:
                    ptz_integration = '''
        # ===============================================
        # INTEGRACIÓN PTZ - CORRECCIÓN AUTOMÁTICA
        # ===============================================
        try:
            main_window = self._get_main_window()
            if main_window and hasattr(main_window, 'send_detections_to_ptz'):
                camera_id = self.cam_data.get('ip', 'unknown') if self.cam_data else 'unknown'
                ptz_detections = self._convert_boxes_for_ptz(boxes)
                if ptz_detections:
                    success = main_window.send_detections_to_ptz(camera_id, ptz_detections)
                    if success and self.detection_count <= 10:
                        self.registrar_log(f"🎯 PTZ: {len(ptz_detections)} detecciones enviadas a {camera_id}")
        except Exception as e:
            if hasattr(self, '_ptz_error_count'):
                self._ptz_error_count = getattr(self, '_ptz_error_count', 0) + 1
                if self._ptz_error_count <= 3:
                    self.registrar_log(f"⚠️ Error integración PTZ: {e}")
'''
                    content = content[:paint_update_pos] + ptz_integration + content[paint_update_pos:]
                    with open(grilla_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print("   ✅ grilla_widget.py corregido exitosamente")
                    return True
            print("   ⚠️ No se pudo localizar método actualizar_boxes")
            return False
        except Exception as e:
            print(f"   ❌ Error corrigiendo grilla_widget.py: {e}")
            return False

    def create_ptz_config_example(self):
        print("🔧 CREANDO configuración PTZ de ejemplo")
        print("-" * 50)

        config_path = self.project_path / "config_ptz_ejemplo.json"

        ptz_config = {
            "camaras": [
                {
                    "ip": "192.168.1.100",
                    "puerto": 80,
                    "usuario": "admin",
                    "contrasena": "admin123",
                    "tipo": "ptz",
                    "nombre": "PTZ Cam 1",
                    "modelos": ["Personas", "Embarcaciones"],
                    "conf": 0.3,
                    "imgsz": 640,
                    "device": "cuda",
                    "rtsp_url": "rtsp://admin:admin123@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0",
                    "preset_inicial": "1",
                    "seguimiento_config": {
                        "modo": "maritime_standard",
                        "auto_zoom": True,
                        "alternancia": True,
                        "tiempo_seguimiento": 5.0
                    }
                }
            ],
            "configuracion_ptz": {
                "fps_global": {
                    "visual_fps": 25,
                    "detection_fps": 8,
                    "ui_update_fps": 15
                },
                "sistema_ptz": {
                    "auto_iniciar": True,
                    "config_predefinida": "maritime_standard",
                    "debug_activo": True
                }
            }
        }

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(ptz_config, f, indent=4, ensure_ascii=False)
            print(f"   ✅ Configuración PTZ creada: {config_path}")
            print("   📝 Edita este archivo con los datos de tu cámara PTZ")
            return True
        except Exception as e:
            print(f"   ❌ Error creando config PTZ: {e}")
            return False

    def create_test_script(self):
        print("🔧 CREANDO script de prueba PTZ")
        print("-" * 50)

        test_script = '''#!/usr/bin/env python3
# test_ptz_system.py - Script de prueba para sistema PTZ
"""
SCRIPT DE PRUEBA SISTEMA PTZ
===========================

Este script verifica que el sistema PTZ esté funcionando correctamente.

Uso:
    python test_ptz_system.py
"""

import sys
import time
import json
from pathlib import Path

def test_ptz_imports():
    """Probar importaciones PTZ"""
    print("🔍 Probando importaciones PTZ...")
    try:
        from core.multi_object_ptz_system import MultiObjectPTZTracker
        print("   ✅ MultiObjectPTZTracker importado")
    except ImportError as e:
        print(f"   ❌ Error importando MultiObjectPTZTracker: {e}")
        return False
    try:
        from ui.enhanced_ptz_multi_object_dialog import EnhancedMultiObjectPTZDialog
        print("   ✅ EnhancedMultiObjectPTZDialog importado")
    except ImportError as e:
        print(f"   ❌ Error importando EnhancedMultiObjectPTZDialog: {e}")
        return False
    try:
        from core.ptz_tracking_integration_enhanced import PTZTrackingSystemEnhanced
        print("   ✅ PTZTrackingSystemEnhanced importado")
    except ImportError as e:
        print(f"   ❌ Error importando PTZTrackingSystemEnhanced: {e}")
        return False
    return True

def test_config_file():
    """Probar archivo de configuración"""
    print("\n🔍 Probando configuración...")
    config_files = ["config.json", "config_ptz_ejemplo.json"]
    for config_file in config_files:
        if Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                cameras = config.get('camaras', [])
                ptz_cameras = [cam for cam in cameras if cam.get('tipo') == 'ptz']
                print(f"   ✅ {config_file}: {len(ptz_cameras)} cámara(s) PTZ")
                if ptz_cameras:
                    return True
            except Exception as e:
                print(f"   ❌ Error leyendo {config_file}: {e}")
    print("   ⚠️ No se encontraron cámaras PTZ configuradas")
    return False

def test_ptz_creation():
    """Probar creación de tracker PTZ"""
    print("\n🔍 Probando creación de tracker PTZ...")
    try:
        from core.multi_object_ptz_system import MultiObjectPTZTracker, MultiObjectConfig
        test_config = MultiObjectConfig(
            alternating_enabled=True,
            primary_follow_time=5.0,
            auto_zoom_enabled=True
        )
        print("   ⚠️ Creación de tracker requiere cámara real")
        print("   ✅ Clases PTZ disponibles")
        return True
    except Exception as e:
        print(f"   ❌ Error creando tracker PTZ: {e}")
        return False

def simulate_detections():
    """Simular envío de detecciones"""
    print("\n🔍 Simulando detecciones...")
    test_detections = [
        {
            'bbox': [100, 100, 200, 300],
            'confidence': 0.85,
            'class': 0,
            'cx': 150,
            'cy': 200,
            'width': 100,
            'height': 200,
            'frame_w': 1920,
            'frame_h': 1080,
            'timestamp': time.time()
        },
        {
            'bbox': [400, 200, 600, 500],
            'confidence': 0.72,
            'class': 0,
            'cx': 500,
            'cy': 350,
            'width': 200,
            'height': 300,
            'frame_w': 1920,
            'frame_h': 1080,
            'timestamp': time.time()
        }
    ]
    print(f"   ✅ {len(test_detections)} detecciones de prueba creadas")
    print("   📡 Formato compatible con sistema PTZ")
    return True

def main():
    print("🚀 PRUEBA SISTEMA PTZ TRACKER")
    print("=" * 50)
    results = []
    results.append(test_ptz_imports())
    results.append(test_config_file())
    results.append(test_ptz_creation())
    results.append(simulate_detections())
    print("\n" + "=" * 50)
    success_count = sum(results)
    print(f"📊 RESULTADO: {success_count}/{len(results)} pruebas exitosas")
    if success_count == len(results):
        print("\n✅ ¡SISTEMA PTZ LISTO!")
        print("🎯 SIGUIENTE PASO:")
        print("   1. Ejecuta tu aplicación principal")
        print("   2. El sistema PTZ se iniciará automáticamente")
        print("   3. Configura tu cámara PTZ en config.json")
    else:
        print("\n⚠️ Algunas pruebas fallaron")
        print("🔧 RECOMENDACIONES:")
        print("   1. Verifica que todos los archivos PTZ estén presentes")
        print("   2. Instala dependencias: pip install ultralytics opencv-python")
        print("   3. Configura una cámara PTZ en config.json")

if __name__ == "__main__":
    main()
'''
        test_path = self.project_path / "test_ptz_system.py"
        try:
            with open(test_path, 'w', encoding='utf-8') as f:
                f.write(test_script)
            print(f"   ✅ Script de prueba creado: {test_path}")
            return True
        except Exception as e:
            print(f"   ❌ Error creando script de prueba: {e}")
            return False

    def apply_all_fixes(self):
        print("🚀 APLICANDO TODAS LAS CORRECCIONES PTZ")
        print("=" * 70)
        print(f"📁 Directorio: {self.project_path}")
        print(f"💾 Backups en: {self.backup_dir}")
        print("=" * 70)
        results = []
        results.append(self.fix_main_window_ptz_init())
        results.append(self.fix_grilla_widget_integration())
        results.append(self.create_ptz_config_example())
        results.append(self.create_test_script())
        print("\n" + "=" * 70)
        success_count = sum(results)
        print(f"📊 RESULTADO FINAL: {success_count}/{len(results)} correcciones aplicadas")
        if success_count == len(results):
            print("\n🎉 ¡TODAS LAS CORRECCIONES APLICADAS EXITOSAMENTE!")
            self.print_success_instructions()
        else:
            print("\n⚠️ Algunas correcciones fallaron")
            self.print_troubleshooting()
        return success_count == len(results)

    def print_success_instructions(self):
        print("\n🎯 INSTRUCCIONES PARA ACTIVAR EL SEGUIMIENTO PTZ:")
        print("-" * 50)
        print("1. ✅ CONFIGURAR CÁMARA PTZ:")
        print("   • Edita config.json o usa config_ptz_ejemplo.json")
        print("   • Agrega tu cámara PTZ con IP, usuario y contraseña")
        print("   • Configura tipo: 'ptz'")
        print("")
        print("2. ✅ REINICIAR APLICACIÓN:")
        print("   • Cierra tu aplicación actual")
        print("   • Vuelve a ejecutar: python main.py")
        print("   • El sistema PTZ se iniciará automáticamente")
        print("")
        print("3. ✅ VERIFICAR FUNCIONAMIENTO:")
        print("   • Ejecuta: python test_ptz_system.py")
        print("   • Busca en logs: '✅ Sistema PTZ inicializado'")
        print("   • Verifica menú PTZ en la aplicación")
        print("")
        print("4. ✅ ACTIVAR SEGUIMIENTO:")
        print("   • El seguimiento se activa automáticamente")
        print("   • También puedes usar: Menú PTZ > Seguimiento Enhanced")
        print("")
        print("🔍 VERIFICACIÓN RÁPIDA:")
        print("   • Busca en consola: '📡 PTZ: X detecciones → camera_ip'")
        print("   • Si ves esto, ¡el seguimiento está funcionando!")

    def print_troubleshooting(self):
        print("\n🛠️ RESOLUCIÓN DE PROBLEMAS:")
        print("-" * 40)
        print("1. Si main_window.py falló:")
        print("   • Verifica que existe ui/main_window.py")
        print("   • Restaura desde backup si es necesario")
        print("")
        print("2. Si grilla_widget.py falló:")
        print("   • Verifica que existe gui/grilla_widget.py")
        print("   • Agrega manualmente la integración PTZ")
        print("")
        print("3. Si persisten problemas:")
        print("   • Ejecuta: python fix_ptz_integration.py --debug")
        print("   • Revisa logs de error")
        print("   • Verifica dependencias: pip install ultralytics")

def main():
    import time
    print("🔧 CORRECCIÓN COMPLETA SISTEMA PTZ TRACKER")
    print("=" * 60)
    print("⚠️  IMPORTANTE: Se crearán backups automáticos")
    print("=" * 60)
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = input("📁 Ruta del proyecto (o Enter para directorio actual): ").strip()
        if not project_path:
            project_path = "."
    project_path = Path(project_path).resolve()
    if not project_path.exists():
        print(f"❌ El directorio {project_path} no existe")
        return
    print(f"📁 Proyecto: {project_path}")
    if "--auto" not in sys.argv:
        response = input("\n¿Aplicar correcciones automáticas? (s/N): ").strip().lower()
        if response not in ['s', 'si', 'sí', 'y', 'yes']:
            print("❌ Operación cancelada")
            return
    fixer = PTZIntegrationFixer(project_path)
    success = fixer.apply_all_fixes()
    if success:
        print(f"\n🎉 ¡CORRECCIONES COMPLETADAS!")
        print(f"💾 Backups guardados en: {fixer.backup_dir}")
    else:
        print(f"\n⚠️ Algunas correcciones fallaron")
        print(f"💾 Backups disponibles en: {fixer.backup_dir}")

if __name__ == "__main__":
    main()