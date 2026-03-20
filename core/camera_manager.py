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
from datetime import datetime
from config import MAX_QUEUE_SIZE, DATA_DIR

FRAMES_DIR = os.path.join(DATA_DIR, 'frames_segmentados')

logger = logging.getLogger('PelletDetector.camera_manager')

class CameraConfig:
    def __init__(self, name, source, model_path, detection_rate, scale_mm_pixel, confidence, device, max_det=100, roi=None):
        self.name = name
        self.source = source
        self.model_path = model_path
        self.detection_rate = detection_rate
        self.scale_mm_pixel = scale_mm_pixel
        self.confidence = confidence
        self.device = device
        self.max_det = max_det
        self.roi = roi  # (x, y, w, h) ou None para frame inteiro
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
            detector = Detector(config.model_path, config.device, config.confidence, config.max_det)
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

            # Acumuladores para relatório de desempenho por etapa
            acc_frame_read_ms = 0.0
            acc_infer_ms = 0.0
            acc_analyze_ms = 0.0
            acc_csv_ms = 0.0
            acc_disk_ms = 0.0
            acc_queue_ms = 0.0
            acc_total_pipeline_ms = 0.0

            while not stop_flag.is_set():
                t_read_start = time.perf_counter()
                ret, frame = cap.read()
                t_read_ms = (time.perf_counter() - t_read_start) * 1000

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
                t_pipeline_start = time.perf_counter()

                try:
                    # --- ROI: recortar frame para inferência ---
                    roi = config.roi  # (x, y, w, h) ou None
                    full_frame = frame

                    if roi is not None:
                        rx, ry, rw, rh = roi
                        fh, fw = frame.shape[:2]
                        rx = max(0, min(rx, fw - 1))
                        ry = max(0, min(ry, fh - 1))
                        rw = min(rw, fw - rx)
                        rh = min(rh, fh - ry)
                        if rw > 10 and rh > 10:
                            inference_frame = frame[ry:ry+rh, rx:rx+rw]
                        else:
                            roi = None
                            inference_frame = frame
                    else:
                        inference_frame = frame

                    # --- Inferência ---
                    t_infer_start = time.perf_counter()
                    result, inference_time = detector.infer(inference_frame)
                    t_infer_ms = (time.perf_counter() - t_infer_start) * 1000

                    # --- Análise (pós-processamento) ---
                    t_analyze_start = time.perf_counter()
                    analysis = analyzer.analyze(result, inference_frame)
                    t_analyze_ms = (time.perf_counter() - t_analyze_start) * 1000

                    # --- ROI: remapear coordenadas e compor no frame completo ---
                    if roi is not None:
                        rx, ry, rw, rh = roi
                        for pellet in analysis['pellets']:
                            cx, cy = pellet['center']
                            pellet['center'] = (cx + rx, cy + ry)

                        display_frame = full_frame.copy()
                        if analysis['annotated_frame'] is not None:
                            display_frame[ry:ry+rh, rx:rx+rw] = analysis['annotated_frame']
                        cv2.rectangle(display_frame, (rx, ry), (rx+rw-1, ry+rh-1), (0, 255, 255), 2)
                        analysis['annotated_frame'] = display_frame

                    # --- Log CSV ---
                    t_csv_start = time.perf_counter()
                    csv_logger.log(config.name, analysis)
                    t_csv_ms = (time.perf_counter() - t_csv_start) * 1000

                    # --- Salvar frame segmentado em disco ---
                    t_disk_start = time.perf_counter()
                    try:
                        cam_frames_dir = os.path.join(FRAMES_DIR, config.name)
                        os.makedirs(cam_frames_dir, exist_ok=True)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                        frame_path = os.path.join(cam_frames_dir, f'{timestamp}.jpg')
                        cv2.imwrite(frame_path, analysis['annotated_frame'])
                    except Exception as e:
                        logger.warning(f"[{config.name}] Erro ao salvar frame segmentado: {e}")
                    t_disk_ms = (time.perf_counter() - t_disk_start) * 1000

                    # --- Enviar para fila UI ---
                    t_queue_start = time.perf_counter()
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
                    t_queue_ms = (time.perf_counter() - t_queue_start) * 1000

                    t_pipeline_ms = (time.perf_counter() - t_pipeline_start) * 1000

                    # Log detalhado por frame (DEBUG)
                    logger.debug(
                        f"[{config.name}] PIPELINE: "
                        f"read={t_read_ms:.1f}ms | "
                        f"infer={t_infer_ms:.1f}ms | "
                        f"analyze={t_analyze_ms:.1f}ms | "
                        f"csv={t_csv_ms:.1f}ms | "
                        f"disk={t_disk_ms:.1f}ms | "
                        f"queue={t_queue_ms:.1f}ms | "
                        f"total={t_pipeline_ms:.1f}ms | "
                        f"pellets={analysis['total_pellets']}"
                    )

                    # Alerta se alguma etapa for incomumente lenta
                    if t_disk_ms > 50:
                        logger.warning(f"[{config.name}] GARGALO DISCO: {t_disk_ms:.1f}ms (frame={frame_path})")
                    if t_analyze_ms > 100:
                        logger.warning(f"[{config.name}] GARGALO ANALISE: {t_analyze_ms:.1f}ms "
                                       f"(pellets={analysis['total_pellets']})")
                    if t_infer_ms > 300:
                        logger.warning(f"[{config.name}] GARGALO INFERENCIA: {t_infer_ms:.1f}ms")

                    # Acumular para relatório periódico
                    acc_frame_read_ms += t_read_ms
                    acc_infer_ms += t_infer_ms
                    acc_analyze_ms += t_analyze_ms
                    acc_csv_ms += t_csv_ms
                    acc_disk_ms += t_disk_ms
                    acc_queue_ms += t_queue_ms
                    acc_total_pipeline_ms += t_pipeline_ms

                    fps_inference_count += 1
                    fps_elapsed = time.time() - fps_start_time
                    if fps_elapsed >= 5.0:
                        fps = fps_inference_count / fps_elapsed
                        avg_read = acc_frame_read_ms / fps_inference_count
                        avg_infer = acc_infer_ms / fps_inference_count
                        avg_analyze = acc_analyze_ms / fps_inference_count
                        avg_csv = acc_csv_ms / fps_inference_count
                        avg_disk = acc_disk_ms / fps_inference_count
                        avg_queue = acc_queue_ms / fps_inference_count
                        avg_total = acc_total_pipeline_ms / fps_inference_count

                        logger.info(
                            f"[{config.name}] --- RESUMO 5s --- "
                            f"FPS={fps:.1f} (alvo={target_fps}) | "
                            f"avg_total={avg_total:.1f}ms | "
                            f"avg_infer={avg_infer:.1f}ms | "
                            f"avg_analyze={avg_analyze:.1f}ms | "
                            f"avg_disk={avg_disk:.1f}ms | "
                            f"avg_csv={avg_csv:.1f}ms | "
                            f"avg_read={avg_read:.1f}ms | "
                            f"avg_queue={avg_queue:.1f}ms"
                        )

                        fps_start_time = time.time()
                        fps_inference_count = 0
                        acc_frame_read_ms = acc_infer_ms = acc_analyze_ms = 0.0
                        acc_csv_ms = acc_disk_ms = acc_queue_ms = acc_total_pipeline_ms = 0.0

                except Exception as e:
                    logger.error(f"[{config.name}] Erro na inferência: {e}")
                    continue

        except Exception as e:
            logger.error(f"[{config.name}] Erro fatal na thread: {e}")
        finally:
            if cap is not None:
                cap.release()
            logger.info(f"[{config.name}] Thread finalizada")

    def update_camera_config(self, camera_id, detection_rate=None, confidence=None, scale_mm_pixel=None, max_det=None, roi='_unchanged'):
        """
        Atualiza configurações de uma câmera em tempo real

        Args:
            camera_id: ID da câmera
            detection_rate: Nova taxa de inferências por segundo (opcional)
            confidence: Novo nível de confiança 0.0-1.0 (opcional)
            scale_mm_pixel: Nova escala mm/pixel (opcional)
            max_det: Máximo de detecções por frame (opcional)
            roi: (x,y,w,h) para definir ROI, None para limpar, '_unchanged' para não alterar

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

            # Atualizar max_det no detector
            if max_det is not None:
                config.max_det = max_det
                if camera_id in self.detectors:
                    self.detectors[camera_id].max_det = max_det
                updated.append(f"max_det={max_det}")

            # Atualizar ROI (lido pelo loop da thread)
            if roi != '_unchanged':
                config.roi = roi
                if roi is None:
                    updated.append("roi=cleared")
                else:
                    updated.append(f"roi={roi}")

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