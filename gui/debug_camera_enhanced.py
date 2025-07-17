# ========================================================================================
# ARCHIVO: debug_camera_enhanced.py
# Parche para agregar debug detallado a cámaras que muestran "sin señal"
# ========================================================================================

import os
import shutil
from datetime import datetime

def aplicar_debug_camara():
    """
    Aplica parches de debug a los archivos principales para diagnosticar problemas de cámaras
    """
    print("🔧 Aplicando debug mejorado para diagnóstico de cámaras...")
    
    # ================================
    # 1. PARCHE PARA VisualizadorDetector
    # ================================
    
    archivo_visualizador = "gui/visualizador_detector.py"
    if os.path.exists(archivo_visualizador):
        # Hacer backup
        backup_file = f"{archivo_visualizador}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(archivo_visualizador, backup_file)
        print(f"💾 Backup creado: {backup_file}")
        
        # Leer contenido actual
        with open(archivo_visualizador, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Parche 1: Mejorar el método iniciar()
        parche_iniciar = '''
    def iniciar(self):
        rtsp_url = self.cam_data.get("rtsp")
        if rtsp_url:
            logger.info("%s: Reproduciendo RTSP %s", self.objectName(), rtsp_url)
            self.log_signal.emit(f"🎥 [{self.objectName()}] Streaming iniciado: {rtsp_url}")
            
            # ✅ DEBUG MEJORADO: Verificar URL y estado de conexión
            self.log_signal.emit(f"🔍 [{self.objectName()}] Verificando conexión...")
            self.log_signal.emit(f"📊 [{self.objectName()}] Datos de cámara: IP={self.cam_data.get('ip')}, Usuario={self.cam_data.get('usuario')}, Canal={self.cam_data.get('canal')}")
            
            # Configurar callback de estado del media player
            self.video_player.playbackStateChanged.connect(self._on_playback_state_changed)
            self.video_player.mediaStatusChanged.connect(self._on_media_status_changed)
            
            self.video_player.setSource(QUrl(rtsp_url))
            self.video_player.play()
        else:
            logger.warning("%s: No se encontró URL RTSP para iniciar", self.objectName())
            self.log_signal.emit(f"⚠️ [{self.objectName()}] No se encontró URL RTSP.")
            
    def _on_playback_state_changed(self, state):
        """Callback para cambios en el estado de reproducción"""
        state_names = {
            0: "StoppedState",
            1: "PlayingState", 
            2: "PausedState"
        }
        state_name = state_names.get(state, f"Unknown({state})")
        self.log_signal.emit(f"🎬 [{self.objectName()}] Estado reproducción: {state_name}")
        
        if state == 0:  # Stopped
            self.log_signal.emit(f"⛔ [{self.objectName()}] STREAM DETENIDO - Verificar conexión")
            
    def _on_media_status_changed(self, status):
        """Callback para cambios en el estado del media"""
        status_names = {
            0: "NoMedia",
            1: "LoadingMedia",
            2: "LoadedMedia", 
            3: "StalledMedia",
            4: "BufferingMedia",
            5: "BufferedMedia",
            6: "EndOfMedia",
            7: "InvalidMedia"
        }
        status_name = status_names.get(status, f"Unknown({status})")
        self.log_signal.emit(f"📺 [{self.objectName()}] Estado media: {status_name}")
        
        if status == 7:  # InvalidMedia
            self.log_signal.emit(f"❌ [{self.objectName()}] MEDIA INVÁLIDO - URL incorrecta o stream no disponible")
        elif status == 3:  # StalledMedia  
            self.log_signal.emit(f"⚠️ [{self.objectName()}] STREAM INTERRUMPIDO - Problemas de red")
        elif status == 5:  # BufferedMedia
            self.log_signal.emit(f"✅ [{self.objectName()}] STREAM ACTIVO - Recibiendo datos")'''
        
        # Buscar y reemplazar el método iniciar
        inicio_metodo = contenido.find("    def iniciar(self):")
        if inicio_metodo != -1:
            # Encontrar el final del método
            lineas = contenido[inicio_metodo:].split('\n')
            fin_metodo = inicio_metodo
            nivel_indentacion = 0
            for i, linea in enumerate(lineas[1:], 1):
                if linea.strip() == "":
                    continue
                if linea.startswith("    def ") and not linea.startswith("        "):
                    break
                fin_metodo = inicio_metodo + len('\n'.join(lineas[:i+1]))
            
            # Reemplazar el método
            contenido_nuevo = contenido[:inicio_metodo] + parche_iniciar + contenido[fin_metodo:]
        else:
            # Si no encuentra el método, agregarlo antes del método detener
            parche_iniciar_completo = parche_iniciar + "\n"
            contenido_nuevo = contenido.replace("    def detener(self):", parche_iniciar_completo + "    def detener(self):")
        
        # Parche 2: Mejorar el callback on_frame
        parche_on_frame = '''
    def on_frame(self, frame): # frame es QVideoFrame
        logger.debug(
            "%s: on_frame called %d (interval %d)",
            self.objectName(),
            self.frame_counter,
            self.detector_frame_interval,
        )
        
        # ✅ DEBUG MEJORADO: Verificar validez del frame
        if not frame.isValid():
            self.log_signal.emit(f"❌ [{self.objectName()}] Frame inválido recibido")
            return

        # ✅ DEBUG: Información del frame cada 100 frames para evitar spam
        if self.frame_counter % 100 == 0:
            self.log_signal.emit(f"📷 [{self.objectName()}] Frame #{self.frame_counter}: {frame.width()}x{frame.height()}, Formato: {frame.pixelFormat()}")
        
        handle_type = frame.handleType()
        logger.debug("%s: frame handle type %s", self.objectName(), handle_type)

        self.frame_counter += 1
        
        # Procesar frames para detección según la configuración de FPS
        if self.frame_counter % self.detector_frame_interval == 0:
            try:
                qimg = self._qimage_from_frame(frame)
                if qimg is None:
                    if self.frame_counter % 50 == 0:  # Log cada 50 frames fallidos
                        self.log_signal.emit(f"⚠️ [{self.objectName()}] No se pudo convertir frame a QImage")
                    return
                    
                if qimg.format() != QImage.Format.Format_RGB888:
                    img_converted = qimg.convertToFormat(QImage.Format.Format_RGB888)
                else:
                    img_converted = qimg

                buffer = img_converted.constBits()
                bytes_per_pixel = img_converted.depth() // 8
                buffer.setsize(img_converted.height() * img_converted.width() * bytes_per_pixel)

                arr = (
                    np.frombuffer(buffer, dtype=np.uint8)
                    .reshape((img_converted.height(), img_converted.width(), bytes_per_pixel))
                    .copy()
                )

                self._last_frame = arr
                self._pending_detections = {}
                self._current_frame_id += 1

                # ✅ DEBUG: Confirmar que hay detectores activos
                if hasattr(self, 'detectors'):
                    detectores_activos = sum(1 for det in self.detectors if det and det.isRunning())
                    if self.frame_counter % 200 == 0:  # Log cada 200 frames
                        self.log_signal.emit(f"🤖 [{self.objectName()}] Detectores activos: {detectores_activos}/{len(self.detectors)}")
                    
                    for det in self.detectors:
                        if det and det.isRunning():
                            det.set_frame(arr, self._current_frame_id)
                else:
                    if self.frame_counter % 100 == 0:
                        self.log_signal.emit(f"⚠️ [{self.objectName()}] No hay detectores configurados")

            except Exception as e:
                logger.error("%s: error procesando frame en on_frame: %s", self.objectName(), e)
                self.log_signal.emit(f"❌ [{self.objectName()}] Error procesando frame: {e}")'''
        
        # Reemplazar el método on_frame existente
        inicio_on_frame = contenido_nuevo.find("    def on_frame(self, frame):")
        if inicio_on_frame != -1:
            # Encontrar el final del método on_frame
            lineas = contenido_nuevo[inicio_on_frame:].split('\n')
            fin_on_frame = inicio_on_frame
            for i, linea in enumerate(lineas[1:], 1):
                if linea.strip() == "":
                    continue
                if linea.startswith("    def ") and not linea.startswith("        "):
                    break
                fin_on_frame = inicio_on_frame + len('\n'.join(lineas[:i+1]))
            
            contenido_nuevo = contenido_nuevo[:inicio_on_frame] + parche_on_frame + contenido_nuevo[fin_on_frame:]
        
        # Agregar imports necesarios al inicio del archivo
        if "from PyQt6.QtMultimedia import" in contenido_nuevo:
            contenido_nuevo = contenido_nuevo.replace(
                "from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink, QVideoFrameFormat, QVideoFrame",
                "from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink, QVideoFrameFormat, QVideoFrame"
            )
        
        # Escribir el archivo modificado
        with open(archivo_visualizador, 'w', encoding='utf-8') as f:
            f.write(contenido_nuevo)
        
        print(f"✅ VisualizadorDetector actualizado con debug mejorado")
    
    # ================================
    # 2. PARCHE PARA GrillaWidget
    # ================================
    
    archivo_grilla = "gui/grilla_widget.py"
    if os.path.exists(archivo_grilla):
        backup_grilla = f"{archivo_grilla}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(archivo_grilla, backup_grilla)
        print(f"💾 Backup creado: {backup_grilla}")
        
        with open(archivo_grilla, 'r', encoding='utf-8') as f:
            contenido_grilla = f.read()
        
        # Agregar debug al método iniciar_stream
        parche_grilla = '''
        # ✅ DEBUG MEJORADO: Información detallada de inicialización
        ip = self.cam_data.get('ip', 'N/A')
        rtsp_url = self.cam_data.get('rtsp', 'N/A')
        usuario = self.cam_data.get('usuario', 'N/A')
        canal = self.cam_data.get('canal', 'N/A')
        
        self.append_debug(f"🚀 [{ip}] Iniciando stream...")
        self.append_debug(f"📝 [{ip}] URL: {rtsp_url}")
        self.append_debug(f"👤 [{ip}] Usuario: {usuario}")
        self.append_debug(f"📺 [{ip}] Canal: {canal}")
        
        if not rtsp_url or rtsp_url == 'N/A':
            self.append_debug(f"❌ [{ip}] URL RTSP no configurada correctamente")
            return
        
        # Verificar formato de URL
        if not rtsp_url.startswith('rtsp://'):
            self.append_debug(f"⚠️ [{ip}] URL no parece ser RTSP válida: {rtsp_url}")'''
        
        # Buscar el método iniciar_stream y agregar el debug al inicio
        if "def iniciar_stream(self):" in contenido_grilla:
            contenido_grilla = contenido_grilla.replace(
                "def iniciar_stream(self):",
                f"def iniciar_stream(self):{parche_grilla}"
            )
        
        with open(archivo_grilla, 'w', encoding='utf-8') as f:
            f.write(contenido_grilla)
        
        print(f"✅ GrillaWidget actualizado con debug mejorado")
    
    # ================================
    # 3. CREAR UTILIDAD DE DIAGNÓSTICO
    # ================================
    
    utilidad_diagnostico = '''
# ========================================================================================
# UTILIDAD DE DIAGNÓSTICO DE CÁMARAS
# ========================================================================================

import cv2
import requests
from urllib.parse import urlparse
import socket
import threading
import time

def diagnosticar_camara(cam_data):
    """
    Ejecuta un diagnóstico completo de una cámara
    """
    print(f"\\n🔍 DIAGNÓSTICO PARA CÁMARA: {cam_data.get('ip', 'N/A')}")
    print("=" * 60)
    
    ip = cam_data.get('ip')
    puerto = cam_data.get('puerto', 554)
    usuario = cam_data.get('usuario')
    contrasena = cam_data.get('contrasena')
    rtsp_url = cam_data.get('rtsp')
    
    # 1. Verificar conectividad de red
    print(f"📡 1. Verificando conectividad de red...")
    if verificar_ping(ip):
        print(f"   ✅ Ping exitoso a {ip}")
    else:
        print(f"   ❌ No se puede hacer ping a {ip}")
    
    # 2. Verificar puerto RTSP
    print(f"🔌 2. Verificando puerto RTSP {puerto}...")
    if verificar_puerto(ip, puerto):
        print(f"   ✅ Puerto {puerto} abierto en {ip}")
    else:
        print(f"   ❌ Puerto {puerto} cerrado o inaccesible en {ip}")
    
    # 3. Verificar autenticación HTTP (si disponible)
    print(f"🔐 3. Verificando autenticación...")
    verificar_auth_http(ip, usuario, contrasena)
    
    # 4. Probar conexión RTSP con OpenCV
    print(f"📹 4. Probando conexión RTSP con OpenCV...")
    if rtsp_url:
        probar_rtsp_opencv(rtsp_url)
    else:
        print(f"   ⚠️ URL RTSP no configurada")
    
    # 5. Verificar formato de URL
    print(f"🔗 5. Verificando formato de URL...")
    if rtsp_url:
        verificar_formato_url(rtsp_url)
    
    print("\\n" + "=" * 60)

def verificar_ping(host, timeout=3):
    """Verificar si el host responde a ping"""
    try:
        import subprocess
        import platform
        
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        result = subprocess.run(['ping', param, '1', host], 
                              capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0
    except:
        return False

def verificar_puerto(host, puerto, timeout=5):
    """Verificar si un puerto está abierto"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, puerto))
        sock.close()
        return result == 0
    except:
        return False

def verificar_auth_http(ip, usuario, contrasena):
    """Verificar autenticación HTTP básica"""
    try:
        url = f"http://{ip}/"
        response = requests.get(url, auth=(usuario, contrasena), timeout=5)
        print(f"   🌐 HTTP Status: {response.status_code}")
        if response.status_code == 401:
            print(f"   ⚠️ Credenciales incorrectas o no autorizadas")
        elif response.status_code == 200:
            print(f"   ✅ Autenticación HTTP exitosa")
    except requests.exceptions.Timeout:
        print(f"   ⏱️ Timeout en conexión HTTP")
    except Exception as e:
        print(f"   ❓ Error HTTP: {e}")

def probar_rtsp_opencv(rtsp_url, timeout=10):
    """Probar conexión RTSP usando OpenCV"""
    print(f"   🎥 Intentando conectar: {rtsp_url}")
    
    cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print(f"   ❌ OpenCV no pudo abrir el stream RTSP")
        return False
    
    print(f"   ✅ Conexión RTSP establecida")
    
    # Intentar leer frames
    frames_leidos = 0
    inicio = time.time()
    
    while time.time() - inicio < timeout and frames_leidos < 5:
        ret, frame = cap.read()
        if ret:
            frames_leidos += 1
            print(f"   📷 Frame {frames_leidos}: {frame.shape if frame is not None else 'None'}")
        else:
            print(f"   ⚠️ Error leyendo frame")
            break
        time.sleep(0.1)
    
    cap.release()
    
    if frames_leidos > 0:
        print(f"   ✅ Se leyeron {frames_leidos} frames exitosamente")
        return True
    else:
        print(f"   ❌ No se pudieron leer frames del stream")
        return False

def verificar_formato_url(url):
    """Verificar el formato de la URL RTSP"""
    try:
        parsed = urlparse(url)
        print(f"   📝 Esquema: {parsed.scheme}")
        print(f"   🌐 Host: {parsed.hostname}")
        print(f"   🔌 Puerto: {parsed.port}")
        print(f"   📂 Ruta: {parsed.path}")
        print(f"   👤 Usuario: {parsed.username}")
        print(f"   🔐 Contraseña: {'***' if parsed.password else 'No configurada'}")
        
        if parsed.scheme != 'rtsp':
            print(f"   ⚠️ Esquema debería ser 'rtsp', encontrado: '{parsed.scheme}'")
        
        if not parsed.hostname:
            print(f"   ❌ No se detectó hostname en la URL")
            
        if not parsed.port:
            print(f"   ℹ️ Puerto no especificado, usando 554 por defecto")
    except Exception as e:
        print(f"   ❌ Error analizando URL: {e}")

# Función para ejecutar diagnóstico en todas las cámaras
def diagnosticar_todas_camaras():
    """Ejecutar diagnóstico en todas las cámaras configuradas"""
    try:
        from config_manager import cargar_camaras
        camaras = cargar_camaras()
        
        if not camaras:
            print("❌ No se encontraron cámaras configuradas")
            return
        
        print(f"🔍 DIAGNÓSTICO MASIVO - {len(camaras)} cámaras encontradas")
        
        for i, cam in enumerate(camaras, 1):
            print(f"\\n{'='*20} CÁMARA {i}/{len(camaras)} {'='*20}")
            diagnosticar_camara(cam)
            
    except Exception as e:
        print(f"❌ Error en diagnóstico masivo: {e}")

if __name__ == "__main__":
    diagnosticar_todas_camaras()
'''
    
    with open("diagnostico_camaras.py", 'w', encoding='utf-8') as f:
        f.write(utilidad_diagnostico)
    
    print("✅ Utilidad de diagnóstico creada: diagnostico_camaras.py")
    
    print("\n🎯 DEBUG APLICADO EXITOSAMENTE")
    print("📋 Próximos pasos:")
    print("   1. Reinicia la aplicación")
    print("   2. Observa los nuevos mensajes de debug en la consola")
    print("   3. Ejecuta 'python diagnostico_camaras.py' para diagnóstico completo")
    print("   4. Comparte los logs para análisis detallado")

if __name__ == "__main__":
    aplicar_debug_camara()