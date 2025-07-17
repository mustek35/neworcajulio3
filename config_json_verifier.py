# test_real_credentials.py - Probar credenciales reales con carácter especial @
"""
Probar las credenciales reales encontradas en config.json:
- root/@Remoto753524
- orca/@Remoto753524

El problema puede ser la codificación del carácter @ en ONVIF.
"""

import time
import threading
from urllib.parse import quote, quote_plus

def patch_ptz_camera_onvif():
    """Agregar método connect() a PTZCameraONVIF si no existe"""
    
    try:
        from core.ptz_control import PTZCameraONVIF
        
        if not hasattr(PTZCameraONVIF, 'connect'):
            def connect(self):
                """Método connect() agregado dinámicamente"""
                try:
                    self.media = self.cam.create_media_service()
                    self.ptz = self.cam.create_ptz_service()
                    profiles = self.media.GetProfiles()
                    if not profiles:
                        return False
                    self.profile_token = profiles[0].token
                    return True
                except Exception as e:
                    print(f"Error en connect(): {e}")
                    return False
            
            PTZCameraONVIF.connect = connect
            print("✅ Método connect() agregado exitosamente")
            
        return True
        
    except ImportError:
        print("⚠️ PTZCameraONVIF no disponible")
        return False
    except Exception as e:
        print(f"❌ Error parchando PTZCameraONVIF: {e}")
        return False

def test_real_credentials_with_encoding():
    """Probar credenciales reales con diferentes codificaciones del carácter @"""
    
    print("🔑 PROBANDO CREDENCIALES REALES CON CODIFICACIÓN ESPECIAL")
    print("=" * 60)
    
    # Parchear PTZCameraONVIF primero
    if not patch_ptz_camera_onvif():
        return
    
    from core.ptz_control import PTZCameraONVIF
    
    # Datos de las cámaras reales
    cameras = [
        {
            'ip': '19.10.10.217',
            'puerto': 80,
            'usuario': 'root',
            'password_original': '@Remoto753524',
            'descripcion': 'Cámara PTZ 1 (root)'
        },
        {
            'ip': '19.10.10.220', 
            'puerto': 80,
            'usuario': 'orca',
            'password_original': '@Remoto753524',
            'descripcion': 'Cámara PTZ 2 (orca)'
        }
    ]
    
    # Diferentes formas de codificar la contraseña con @
    password_variants = [
        '@Remoto753524',                    # Original
        '%40Remoto753524',                  # URL encoded (@)
        quote('@Remoto753524'),             # urllib.parse.quote
        quote_plus('@Remoto753524'),        # urllib.parse.quote_plus
        'Remoto753524',                     # Sin @
        '@remoto753524',                    # Lowercase
        '@REMOTO753524',                    # Uppercase
    ]
    
    successful_connections = []
    
    for camera in cameras:
        ip = camera['ip']
        port = camera['puerto']
        username = camera['usuario']
        description = camera['descripcion']
        
        print(f"\n🎯 PROBANDO {description} ({ip})")
        print("-" * 50)
        
        success = False
        
        for i, password in enumerate(password_variants, 1):
            print(f"   {i}. Probando {username}/{password}")
            
            try:
                # Crear instancia PTZ
                camera_ptz = PTZCameraONVIF(ip, port, username, password)
                
                # Intentar crear servicios directamente
                start_time = time.time()
                
                def test_connection():
                    try:
                        media_service = camera_ptz.cam.create_media_service()
                        ptz_service = camera_ptz.cam.create_ptz_service()
                        profiles = media_service.GetProfiles()
                        
                        if profiles:
                            connection_time = time.time() - start_time
                            print(f"      ✅ ¡ÉXITO! Tiempo: {connection_time:.1f}s")
                            print(f"      📋 Perfiles encontrados: {len(profiles)}")
                            
                            # Intentar obtener estado PTZ
                            try:
                                profile_token = profiles[0].token
                                status = ptz_service.GetStatus({'ProfileToken': profile_token})
                                if status:
                                    print(f"      📊 Estado PTZ obtenido")
                                    if hasattr(status, 'Position'):
                                        pos = status.Position
                                        if hasattr(pos, 'PanTilt'):
                                            pan = getattr(pos.PanTilt, 'x', 'N/A')
                                            tilt = getattr(pos.PanTilt, 'y', 'N/A')
                                            print(f"      🎯 Posición actual: Pan={pan}, Tilt={tilt}")
                            except Exception as e:
                                print(f"      ⚠️ No se pudo obtener estado: {e}")
                            
                            return True
                        else:
                            print(f"      ❌ No se encontraron perfiles")
                            return False
                            
                    except Exception as e:
                        error_msg = str(e)
                        if 'sender not authorized' in error_msg.lower():
                            print(f"      ❌ Credenciales incorrectas")
                        elif 'timeout' in error_msg.lower():
                            print(f"      ❌ Timeout de conexión")
                        else:
                            print(f"      ❌ Error: {e}")
                        return False
                
                # Ejecutar con timeout
                connection_thread = threading.Thread(target=test_connection)
                connection_thread.daemon = True
                connection_thread.start()
                connection_thread.join(8.0)  # 8 segundos timeout
                
                if connection_thread.is_alive():
                    print(f"      ⏱️ Timeout después de 8 segundos")
                    continue
                
                # Si llegamos aquí y no hubo error, fue exitoso
                if not hasattr(test_connection, 'result'):
                    # Verificar si la conexión fue exitosa probando los servicios otra vez
                    try:
                        test_media = camera_ptz.cam.create_media_service()
                        test_profiles = test_media.GetProfiles()
                        if test_profiles:
                            print(f"      ✅ Conexión verificada exitosamente!")
                            successful_connections.append({
                                'ip': ip,
                                'username': username,
                                'password': password,
                                'description': description,
                                'profiles_count': len(test_profiles)
                            })
                            success = True
                            break
                    except:
                        pass
                        
            except Exception as e:
                error_msg = str(e)
                if 'sender not authorized' in error_msg.lower():
                    print(f"      ❌ Credenciales incorrectas")
                elif 'timeout' in error_msg.lower():
                    print(f"      ❌ Timeout de conexión")
                else:
                    print(f"      ❌ Error: {e}")
        
        if not success:
            print(f"   ❌ No se pudo conectar a {ip} con ninguna variante de contraseña")
    
    # Mostrar resumen final
    print(f"\n📊 RESUMEN FINAL:")
    print("=" * 40)
    
    if successful_connections:
        print(f"✅ Cámaras conectadas exitosamente: {len(successful_connections)}")
        
        for conn in successful_connections:
            print(f"\n🎯 {conn['description']}")
            print(f"   📡 IP: {conn['ip']}")
            print(f"   👤 Usuario: {conn['username']}")
            print(f"   🔑 Contraseña: {conn['password']}")
            print(f"   📋 Perfiles: {conn['profiles_count']}")
        
        # Generar configuración corregida
        print(f"\n📁 GENERANDO CONFIGURACIÓN CORREGIDA...")
        create_corrected_config_real(successful_connections)
        
        print(f"\n✅ ¡PROBLEMA RESUELTO!")
        print("🎉 Las credenciales PTZ funcionan correctamente")
        print("\n📋 Próximos pasos:")
        print("1. Aplicar configuración corregida:")
        print("   cp config.json.working_credentials config.json")
        print("2. Usar el diálogo PTZ optimizado")
        print("3. Verificar conexión en el diálogo")
        print("4. Iniciar seguimiento")
        
    else:
        print("❌ No se pudo conectar a ninguna cámara")
        print("\n🔍 DIAGNÓSTICO ADICIONAL REQUERIDO:")
        print("1. Verificar ping a las cámaras:")
        print("   ping 19.10.10.217")
        print("   ping 19.10.10.220")
        print("2. Verificar acceso web:")
        print("   http://19.10.10.217")
        print("   http://19.10.10.220")
        print("3. Verificar que ONVIF esté habilitado")
        print("4. Probar puertos alternativos: 554, 8080, 8000")
        
        # Probar puertos alternativos
        print(f"\n🔄 PROBANDO PUERTOS ALTERNATIVOS...")
        test_alternative_ports(cameras)

def create_corrected_config_real(successful_connections):
    """Crear config.json con credenciales que funcionan"""
    
    import json
    
    try:
        # Cargar config actual
        with open('config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # Actualizar con credenciales que funcionan
        cameras = config_data.get('camaras', [])
        updated = False
        
        for camera in cameras:
            camera_ip = camera.get('ip')
            
            # Buscar credenciales exitosas para esta IP
            for conn in successful_connections:
                if conn['ip'] == camera_ip:
                    # Actualizar credenciales
                    camera['usuario'] = conn['username']
                    camera['contrasena'] = conn['password']
                    camera['puerto'] = 80
                    updated = True
                    print(f"   ✅ Credenciales actualizadas para {camera_ip}")
                    break
        
        if updated:
            # Guardar configuración corregida
            corrected_file = 'config.json.working_credentials'
            with open(corrected_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            print(f"   💾 Configuración guardada: {corrected_file}")
            return corrected_file
        else:
            print("   ⚠️ No se encontraron credenciales válidas para actualizar")
            return None
            
    except Exception as e:
        print(f"   ❌ Error creando configuración: {e}")
        return None

def test_alternative_ports(cameras):
    """Probar puertos alternativos para ONVIF"""
    
    alternative_ports = [554, 8080, 8000, 8888, 8181]
    
    for camera in cameras:
        ip = camera['ip']
        username = camera['usuario']
        password = camera['password_original']
        
        print(f"\n🔍 Probando puertos alternativos para {ip}:")
        
        for port in alternative_ports:
            print(f"   Puerto {port}... ", end='')
            
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                print("✅ Abierto")
                # Podríamos probar ONVIF en este puerto también
            else:
                print("❌ Cerrado")

def main():
    """Función principal"""
    
    print("🔑 PRUEBA DE CREDENCIALES REALES PTZ")
    print("Credenciales encontradas en config.json:")
    print("   • 19.10.10.217: root/@Remoto753524")  
    print("   • 19.10.10.220: orca/@Remoto753524")
    print("=" * 60)
    
    test_real_credentials_with_encoding()

if __name__ == "__main__":
    main()