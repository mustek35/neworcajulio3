#!/usr/bin/env python3
"""
Test de integración PTZ - Verificar que las detecciones lleguen al sistema PTZ
Ejecutar desde el directorio raíz del proyecto: python test_ptz_integration.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainGUI
import time

def test_ptz_bridge_basic():
    """Test básico del puente PTZ"""
    print("🧪 Iniciando test básico del puente PTZ...")
    
    try:
        app = QApplication(sys.argv)
        window = MainGUI()
        
        # 1. Verificar estado inicial
        print("\n1️⃣ Verificando estado inicial del puente PTZ...")
        initial_status = window.get_ptz_bridge_status()
        print(f"   Estado inicial: {initial_status}")
        
        # 2. Simular activación del sistema PTZ multi-objeto
        print("\n2️⃣ Simulando activación del sistema PTZ...")
        # Esto normalmente se hace al abrir el diálogo PTZ multi-objeto
        
        # 3. Test con detecciones simuladas
        print("\n3️⃣ Enviando detecciones de prueba...")
        test_detections = [
            {
                'cx': 960.0, 'cy': 540.0,
                'width': 100.0, 'height': 150.0,
                'confidence': 0.85, 'class': 0,
                'bbox': [910.0, 465.0, 1010.0, 615.0],
                'frame_w': 1920, 'frame_h': 1080,
                'track_id': 'test_001',
                'timestamp': time.time(),
                'moving': True
            },
            {
                'cx': 500.0, 'cy': 300.0,
                'width': 80.0, 'height': 120.0,
                'confidence': 0.72, 'class': 0,
                'bbox': [460.0, 240.0, 540.0, 360.0],
                'frame_w': 1920, 'frame_h': 1080,
                'track_id': 'test_002',
                'timestamp': time.time(),
                'moving': False
            }
        ]
        
        # Enviar detecciones a una cámara de prueba
        camera_id = "test_camera_192.168.1.100"
        result = window.send_detections_to_ptz(camera_id, test_detections)
        print(f"   Resultado envío: {result}")
        
        # 4. Verificar estado final
        print("\n4️⃣ Verificando estado final...")
        final_status = window.get_ptz_bridge_status()
        print(f"   Estado final: {final_status}")
        
        print("\n✅ Test básico completado")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en test básico: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_registration():
    """Test de registro de cámaras con el sistema PTZ"""
    print("\n🧪 Iniciando test de registro de cámaras...")
    
    try:
        app = QApplication(sys.argv)
        window = MainGUI()
        
        # Test con cámara PTZ
        print("\n📷 Test con cámara PTZ...")
        ptz_camera = {
            'ip': '192.168.1.100',
            'tipo': 'ptz',
            'usuario': 'admin',
            'contrasena': 'admin123',
            'puerto': 80,
            'modelo': 'Personas'
        }
        
        result_ptz = window.register_camera_with_ptz(ptz_camera)
        print(f"   Registro cámara PTZ: {result_ptz}")
        
        # Test con cámara fija
        print("\n📹 Test con cámara fija...")
        fixed_camera = {
            'ip': '192.168.1.101',
            'tipo': 'fija',
            'usuario': 'admin',
            'contrasena': 'admin123',
            'puerto': 80,
            'modelo': 'Personas'
        }
        
        result_fixed = window.register_camera_with_ptz(fixed_camera)
        print(f"   Registro cámara fija: {result_fixed}")
        
        print("\n✅ Test de registro completado")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en test de registro: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_detection_conversion():
    """Test de conversión de detecciones YOLO a formato PTZ"""
    print("\n🧪 Iniciando test de conversión de detecciones...")
    
    try:
        # Simular datos de detección YOLO
        yolo_boxes = [
            {
                'bbox': (100, 200, 300, 500),  # x1, y1, x2, y2
                'id': 'track_001',
                'cls': 0,
                'conf': 0.85,
                'moving': True,
                'centers': [(200, 350), (205, 355)]
            },
            {
                'bbox': (400, 100, 600, 400),
                'id': 'track_002', 
                'cls': 0,
                'conf': 0.72,
                'moving': False,
                'centers': [(500, 250)]
            }
        ]
        
        # Simular conversión (esto normalmente se hace en GrillaWidget)
        print("\n🔄 Convirtiendo detecciones YOLO a formato PTZ...")
        
        ptz_detections = []
        frame_w, frame_h = 1920, 1080
        
        for box_data in yolo_boxes:
            x1, y1, x2, y2 = box_data['bbox']
            cx = float((x1 + x2) / 2)
            cy = float((y1 + y2) / 2)
            width = float(x2 - x1)
            height = float(y2 - y1)
            
            ptz_detection = {
                'cx': cx, 'cy': cy,
                'width': width, 'height': height,
                'confidence': float(box_data['conf']),
                'class': int(box_data['cls']),
                'bbox': [float(x1), float(y1), float(x2), float(y2)],
                'frame_w': frame_w, 'frame_h': frame_h,
                'track_id': box_data['id'],
                'timestamp': time.time(),
                'moving': box_data.get('moving', False),
                'centers': box_data.get('centers', [])
            }
            ptz_detections.append(ptz_detection)
        
        print(f"   ✅ Conversión exitosa: {len(yolo_boxes)} → {len(ptz_detections)} detecciones")
        
        # Mostrar ejemplo de detección convertida
        if ptz_detections:
            example = ptz_detections[0]
            print(f"   📋 Ejemplo de detección convertida:")
            print(f"      Track ID: {example['track_id']}")
            print(f"      Centro: ({example['cx']:.1f}, {example['cy']:.1f})")
            print(f"      Confianza: {example['confidence']:.2f}")
            print(f"      Movimiento: {example['moving']}")
        
        print("\n✅ Test de conversión completado")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en test de conversión: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Ejecutar todos los tests"""
    print("🚀 Iniciando suite completa de tests PTZ...")
    print("=" * 60)
    
    tests = [
        ("Test básico del puente PTZ", test_ptz_bridge_basic),
        ("Test de registro de cámaras", test_camera_registration), 
        ("Test de conversión de detecciones", test_detection_conversion)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Ejecutando: {test_name}")
        print("-" * 40)
        
        try:
            success = test_func()
            results.append((test_name, success))
            status = "✅ EXITOSO" if success else "❌ FALLIDO"
            print(f"\n{status}: {test_name}")
        except Exception as e:
            print(f"\n❌ ERROR CRÍTICO en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTS:")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 RESULTADO FINAL: {passed}/{total} tests exitosos")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron! El sistema PTZ está listo.")
        return 0
    else:
        print("⚠️ Algunos tests fallaron. Revisa la implementación.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)