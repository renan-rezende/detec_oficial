"""
Gerenciador de câmeras - Otimizado com Threading (CUDA Context Compartilhado)
"""
import cv2
import threading
import queue
import logging
import uuid
import time
import os
from core.detector import Detector
from core.pellet_analyzer import PelletAnalyzer
from core.csv_logger import CSVLogger
from config import MAX_QUEUE_SIZE, DATA_DIR

logger = logging.getLogger('PelletDetector.camera_manager')

class CameraConfig:
    def __init__(self, name, source, model_path, detection_rate, scale_mm_pixel, confidence, device):
        self.name = name
        self.source = source
        self.model_path = model_path
        self.detection_rate = detection_rate
        self.scale_mm_pixel = scale_mm_pixel
        self.confidence = confidence
        self.device = device
        self.id = str(uuid.uuid4())[:8]

class CameraManager:
    """Gerencia múltiplas câmeras processando simultaneamente num único contexto GPU"""

    def __init__(self):
        self.cameras = {}
        self.threads = {}
        self.queues = {}
        self.stop_flags = {}
        self.csv_loggers = {}
        self.detectors = {}      # Referências aos detectores para update em tempo real
        self.analyzers = {}      # Referências aos analyzers para update em tempo real

        # Otimização OpenCV para não competir com as threads do Python
        cv2.setNumThreads(1)

        logger.info("CameraManager inicializado (Threading Otimizado)")

    def add_camera(self, config):
        try:
            camera_id = config.id
            logger.info(f"Adicionando câmera: {config.name} (ID: {camera_id})")

            self.cameras[camera_id] = config

            csv_filename = f"{config.name.replace(' ', '_')}.csv"
            csv_path = os.path.join(DATA_DIR, csv_filename)
            os.makedirs(DATA_DIR, exist_ok=True)
            self.csv_loggers[camera_id] = CSVLogger(csv_path)

            self.queues[camera_id] = queue.Queue(maxsize=MAX_QUEUE_SIZE)
            self.stop_flags[camera_id] = threading.Event()

            thread = threading.Thread(
                target=self._process_camera,
                args=(camera_id,),
                daemon=True,
                name=f"Camera-{config.name}"
            )
            self.threads[camera_id] = thread
            thread.start()

            return camera_id

        except Exception as e:
            logger.error(f"Erro ao adicionar câmera: {e}")
            raise

    def _open_capture(self, source):
        """Abre e configura um VideoCapture. Retorna o objeto ou None."""
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _process_camera(self, camera_id):
        config = self.cameras[camera_id]
        stop_flag = self.stop_flags[camera_id]
        output_queue = self.queues[camera_id]

        # Captura referência local do csv_logger para evitar race condition no stop_camera
        csv_logger = self.csv_loggers[camera_id]

        logger.info(f"[{config.name}] Thread iniciada")
        cap = None

        try:
            detector = Detector(config.model_path, config.device, config.confidence)
            analyzer = PelletAnalyzer(config.scale_mm_pixel)

            # Guardar referências para update em tempo real
            self.detectors[camera_id] = detector
            self.analyzers[camera_id] = analyzer

            try:
                source = int(config.source)
            except ValueError:
                source = config.source

            is_file = isinstance(source, str) and source.endswith(('.mp4', '.avi', '.mov', '.mkv'))

            # Intervalo de reconexão para câmeras de rede (RTSP/IP)
            RECONNECT_DELAY = 5.0   # segundos entre tentativas

            cap = self._open_capture(source)
            if cap is None:
                raise RuntimeError(f"Não foi possível abrir source: {config.source}")

            last_inference_time = 0
            fps_start_time = time.time()
            fps_inference_count = 0

            while not stop_flag.is_set():
                ret, frame = cap.read()

                if not ret:
                    if is_file:
                        # Arquivo de vídeo terminou — reinicia do começo
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        # Câmera de rede perdeu conexão — tenta reconectar
                        logger.warning(f"[{config.name}] Conexão perdida. Tentando reconectar em {RECONNECT_DELAY}s...")
                        cap.release()
                        cap = None

                        reconnect_count = 0
                        while not stop_flag.is_set():
                            stop_flag.wait(timeout=RECONNECT_DELAY)
                            if stop_flag.is_set():
                                break
                            reconnect_count += 1
                            logger.info(f"[{config.name}] Tentativa de reconexão #{reconnect_count}...")
                            cap = self._open_capture(source)
                            if cap is not None:
                                logger.info(f"[{config.name}] Reconectado com sucesso!")
                                break
                            logger.warning(f"[{config.name}] Reconexão #{reconnect_count} falhou.")
                        continue

                # Ler detection_rate do config a cada iteração (permite update em tempo real)
                target_fps = float(config.detection_rate)
                min_interval = 1.0 / target_fps if target_fps > 0 else 0

                current_time = time.time()
                if (current_time - last_inference_time) < min_interval:
                    continue

                last_inference_time = current_time

                try:
                    mask, inference_time = detector.infer(frame)
                    analysis = analyzer.analyze(mask, frame)

                    # Usa referência local — seguro mesmo se stop_camera já executou
                    csv_logger.log(config.name, analysis)

                    data_packet = {
                        'frame': analysis['annotated_frame'],
                        'analysis': analysis,
                        'inference_time': inference_time
                    }

                    try:
                        output_queue.put_nowait(data_packet)
                    except queue.Full:
                        try:
                            output_queue.get_nowait()
                            output_queue.put_nowait(data_packet)
                        except queue.Empty:
                            pass

                    fps_inference_count += 1
                    fps_elapsed = time.time() - fps_start_time
                    if fps_elapsed >= 5.0:
                        fps = fps_inference_count / fps_elapsed
                        logger.info(f"[{config.name}] FPS Real: {fps:.1f} (Alvo: {target_fps}), "
                                   f"Inferência: {inference_time:.1f}ms")
                        fps_start_time = time.time()
                        fps_inference_count = 0

                except Exception as e:
                    logger.error(f"[{config.name}] Erro na inferência: {e}")
                    continue

        except Exception as e:
            logger.error(f"[{config.name}] Erro fatal na thread: {e}")
        finally:
            if cap is not None:
                cap.release()
            logger.info(f"[{config.name}] Thread finalizada")

    def update_camera_config(self, camera_id, detection_rate=None, confidence=None, scale_mm_pixel=None):
        """
        Atualiza configurações de uma câmera em tempo real

        Args:
            camera_id: ID da câmera
            detection_rate: Nova taxa de inferências por segundo (opcional)
            confidence: Novo nível de confiança 0.0-1.0 (opcional)
            scale_mm_pixel: Nova escala mm/pixel (opcional)

        Returns:
            bool: True se atualização bem-sucedida
        """
        if camera_id not in self.cameras:
            logger.error(f"Câmera {camera_id} não encontrada")
            return False

        config = self.cameras[camera_id]
        updated = []

        try:
            # Atualizar detection_rate (lido pelo loop da thread)
            if detection_rate is not None:
                config.detection_rate = detection_rate
                updated.append(f"detection_rate={detection_rate}")

            # Atualizar confidence no detector
            if confidence is not None:
                config.confidence = confidence
                if camera_id in self.detectors:
                    self.detectors[camera_id].confidence = confidence
                updated.append(f"confidence={confidence:.2f}")

            # Atualizar scale no analyzer
            if scale_mm_pixel is not None:
                config.scale_mm_pixel = scale_mm_pixel
                if camera_id in self.analyzers:
                    self.analyzers[camera_id].scale = scale_mm_pixel
                updated.append(f"scale={scale_mm_pixel}")

            logger.info(f"[{config.name}] Config atualizado: {', '.join(updated)}")
            return True

        except Exception as e:
            logger.error(f"Erro ao atualizar config da câmera {camera_id}: {e}")
            return False

    def stop_camera(self, camera_id):
        if camera_id not in self.cameras:
            return

        config = self.cameras[camera_id]
        logger.info(f"Parando câmera: {config.name}")

        self.stop_flags[camera_id].set()

        thread = self.threads.get(camera_id)
        if thread and thread.is_alive():
            thread.join(timeout=5.0)
            if thread.is_alive():
                logger.warning(f"[{config.name}] Thread não encerrou em 5s — recursos serão liberados mesmo assim")

        # Liberar recursos do detector (VRAM)
        detector = self.detectors.pop(camera_id, None)
        if detector is not None:
            detector.cleanup()
            logger.info(f"[{config.name}] VRAM liberada")

        self.cameras.pop(camera_id, None)
        self.threads.pop(camera_id, None)
        self.queues.pop(camera_id, None)
        self.stop_flags.pop(camera_id, None)
        self.csv_loggers.pop(camera_id, None)
        self.analyzers.pop(camera_id, None)

    def get_frame(self, camera_id, timeout=0.01):
        if camera_id not in self.queues:
            return None
        try:
            return self.queues[camera_id].get(timeout=timeout)
        except queue.Empty:
            return None

    def is_running(self, camera_id):
        return camera_id in self.threads and self.threads[camera_id].is_alive()

    def list_cameras(self):
        return [(cid, config) for cid, config in self.cameras.items()]

    def stop_all(self):
        for camera_id in list(self.cameras.keys()):
            self.stop_camera(camera_id)