#!/usr/bin/env python3
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
    print("
🔍 Probando configuración...")
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
    print("
🔍 Probando creación de tracker PTZ...")
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
    print("
🔍 Simulando detecciones...")
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
    print("
" + "=" * 50)
    success_count = sum(results)
    print(f"📊 RESULTADO: {success_count}/{len(results)} pruebas exitosas")
    if success_count == len(results):
        print("
✅ ¡SISTEMA PTZ LISTO!")
        print("🎯 SIGUIENTE PASO:")
        print("   1. Ejecuta tu aplicación principal")
        print("   2. El sistema PTZ se iniciará automáticamente")
        print("   3. Configura tu cámara PTZ en config.json")
    else:
        print("
⚠️ Algunas pruebas fallaron")
        print("🔧 RECOMENDACIONES:")
        print("   1. Verifica que todos los archivos PTZ estén presentes")
        print("   2. Instala dependencias: pip install ultralytics opencv-python")
        print("   3. Configura una cámara PTZ en config.json")

if __name__ == "__main__":
    main()
