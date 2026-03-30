"""
Gerenciador de cameras — Pipeline 2-stage por camera (Multiprocessing)
Arquitetura: [Processo Reader] -> Queue -> [Processo Pipeline (Infer+PostProc)] -> Queue -> [Main GUI]
Otimizado para Xeon E5-2603 v3 (6 nucleos, 1.6 GHz) + RTX 4000 Quadro

Ganho principal: processos separados eliminam a GIL — a CPU do Reader nao
compete com o PostProc, e a GPU opera com paralelismo real.
"""
import cv2
import multiprocessing as mp
import queue as _queue  # apenas para a exceção Empty
import logging
import uuid
import time
import os
from config import DATA_DIR

logger = logging.getLogger('PelletDetector.camera_manager')


class CameraConfig:
    def __init__(self, name, source, model_path, detection_rate, scale_mm_pixel, confidence, device, max_det=100, roi=None, frame_display_interval=0):
        self.name = name
        self.source = source
        self.model_path = model_path
        self.detection_rate = detection_rate
        self.scale_mm_pixel = scale_mm_pixel
        self.confidence = confidence
        self.device = device
        self.max_det = max_det
        self.roi = roi  # (x, y, w, h) ou None para frame inteiro
        self.frame_display_interval = frame_display_interval  # segundos entre frames anotados (0 = todos)
        self.id = str(uuid.uuid4())[:8]


# =========================================================================
#  FUNCOES TOP-LEVEL DOS PROCESSOS WORKER
#  (obrigatório para multiprocessing no Windows — método spawn)
# =========================================================================

def _setup_worker_logging(log_level=logging.INFO):
    """Configura logging no processo worker (necessario para Windows spawn)."""
    from utils.logger import setup_logger
    setup_logger('PelletDetector', level=log_level)


def _open_capture(source):
    """Abre e configura um VideoCapture. Retorna o objeto ou None."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def _reader_worker(config, stop_event, frame_queue, roi_queue, log_level):
    """
    Processo Reader: le frames da camera continuamente, aplica recorte ROI
    e coloca o frame mais recente na fila do pipeline (latest-wins).
    """
    _setup_worker_logging(log_level)
    log = logging.getLogger('PelletDetector.reader')

    cv2.setNumThreads(1)

    name = config.name
    roi = config.roi

    log.info(f"[{name}] Reader processo iniciado (PID={os.getpid()})")
    cap = None

    try:
        try:
            source = int(config.source)
        except (ValueError, TypeError):
            source = config.source

        is_file = isinstance(source, str) and source.endswith(('.mp4', '.avi', '.mov', '.mkv'))
        RECONNECT_DELAY = 5.0

        cap = _open_capture(source)
        if cap is None:
            raise RuntimeError(f"Nao foi possivel abrir source: {config.source}")

        while not stop_event.is_set():
            # Verificar atualizacoes de ROI (non-blocking)
            try:
                while True:
                    update = roi_queue.get_nowait()
                    roi = update.get('roi', roi)
            except _queue.Empty:
                pass

            ret, frame = cap.read()

            if not ret:
                if is_file:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    log.warning(f"[{name}] Conexao perdida. Reconectando...")
                    cap.release()
                    cap = None
                    reconnect_count = 0
                    while not stop_event.is_set():
                        stop_event.wait(timeout=RECONNECT_DELAY)
                        if stop_event.is_set():
                            break
                        reconnect_count += 1
                        log.info(f"[{name}] Tentativa #{reconnect_count}...")
                        cap = _open_capture(source)
                        if cap is not None:
                            log.info(f"[{name}] Reconectado com sucesso!")
                            break
                        log.warning(f"[{name}] Tentativa #{reconnect_count} falhou.")
                    continue

            # Aplicar ROI (lido a cada frame — suporta update em tempo real)
            full_frame = frame
            inference_frame = frame  # default: frame completo

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
                    roi = None  # ROI invalida, usa frame completo

            # Politica "latest-wins": se a fila esta cheia, descarta o frame
            # antigo e coloca o mais recente (evita latencia acumulada)
            try:
                frame_queue.put_nowait((full_frame, inference_frame, roi))
            except _queue.Full:
                try:
                    frame_queue.get_nowait()
                except _queue.Empty:
                    pass
                try:
                    frame_queue.put_nowait((full_frame, inference_frame, roi))
                except _queue.Full:
                    pass

    except Exception as e:
        log.error(f"[{name}] Reader fatal: {e}")
    finally:
        if cap is not None:
            cap.release()
        # Sinaliza fim de stream para o estagio seguinte
        try:
            frame_queue.put(None, timeout=2.0)
        except Exception:
            pass
        log.info(f"[{name}] Reader finalizado")


def _pipeline_worker(config, stop_event, frame_queue, data_queue, csv_path, config_queue, log_level):
    """
    Processo Pipeline: Inference (GPU) + PostProc (CPU) + CSV logging.
    Cria Detector e PelletAnalyzer internamente (objetos GPU nao cruzam processos).
    """
    _setup_worker_logging(log_level)
    log = logging.getLogger('PelletDetector.pipeline')

    from core.detector import Detector
    from core.pellet_analyzer import PelletAnalyzer
    from core.csv_logger import CSVLogger

    name = config.name
    log.info(f"[{name}] Pipeline processo iniciado (PID={os.getpid()}, device={config.device})")

    detector = None
    csv_logger = None

    try:
        detector = Detector(config.model_path, config.device, config.confidence, config.max_det)
        analyzer = PelletAnalyzer(config.scale_mm_pixel)
        csv_logger = CSVLogger(csv_path)

        detection_rate = float(config.detection_rate)
        frame_display_interval = config.frame_display_interval
        max_det = config.max_det

        last_inference_time = 0.0
        last_annotated_time = 0.0
        fps_start = time.time()
        fps_count = 0
        acc_infer_ms = 0.0
        acc_analyze_ms = 0.0

        while not stop_event.is_set():
            # Verificar atualizacoes de config (non-blocking)
            try:
                while True:
                    update = config_queue.get_nowait()
                    if 'detection_rate' in update:
                        detection_rate = float(update['detection_rate'])
                        log.info(f"[{name}] detection_rate atualizado: {detection_rate}")
                    if 'confidence' in update:
                        detector.confidence = update['confidence']
                        log.info(f"[{name}] confidence atualizado: {update['confidence']}")
                    if 'scale_mm_pixel' in update:
                        analyzer.scale = update['scale_mm_pixel']
                        log.info(f"[{name}] scale atualizado: {update['scale_mm_pixel']}")
                    if 'max_det' in update:
                        max_det = update['max_det']
                        detector.max_det = max_det
                        detector.model.overrides['max_det'] = max_det
                        detector.model.predictor = None
                        log.info(f"[{name}] max_det atualizado: {max_det}")
                    if 'frame_display_interval' in update:
                        frame_display_interval = update['frame_display_interval']
                        log.info(f"[{name}] frame_display_interval atualizado: {frame_display_interval}")
            except _queue.Empty:
                pass

            # Obter frame do Reader
            try:
                item = frame_queue.get(timeout=1.0)
            except _queue.Empty:
                continue

            if item is None:  # Sinal de fim do Reader
                break

            full_frame, inference_frame, roi = item

            # Rate limiting
            target_fps = detection_rate
            min_interval = 1.0 / target_fps if target_fps > 0 else 0.0
            current_time = time.time()
            if (current_time - last_inference_time) < min_interval:
                continue
            last_inference_time = current_time

            try:
                # === INFERENCE (GPU) ===
                result, inference_time = detector.infer(inference_frame)

                # === POSTPROC (CPU) ===
                now_mono = time.time()
                needs_annotation = (now_mono - last_annotated_time) >= frame_display_interval
                frame_for_analysis = inference_frame if needs_annotation else None

                t_analyze_start = time.perf_counter()
                analysis = analyzer.analyze(result, frame_for_analysis, max_det=max_det)
                t_analyze_ms = (time.perf_counter() - t_analyze_start) * 1000

                if needs_annotation:
                    last_annotated_time = now_mono

                # Remapear coordenadas ROI para o frame completo
                if roi is not None and analysis['annotated_frame'] is not None:
                    rx, ry, rw, rh = roi
                    for pellet in analysis['pellets']:
                        cx, cy = pellet['center']
                        pellet['center'] = (cx + rx, cy + ry)
                    display_frame = full_frame.copy()
                    display_frame[ry:ry+rh, rx:rx+rw] = analysis['annotated_frame']
                    cv2.rectangle(display_frame, (rx, ry), (rx+rw-1, ry+rh-1), (0, 255, 255), 2)
                    analysis['annotated_frame'] = display_frame

                # CSV logging
                csv_logger.log(name, analysis)

                # Enviar para o processo principal (UI)
                data_packet = {
                    'frame': analysis['annotated_frame'],
                    'analysis': analysis,
                    'inference_time': inference_time
                }
                try:
                    data_queue.put_nowait(data_packet)
                except _queue.Full:
                    try:
                        data_queue.get_nowait()
                    except _queue.Empty:
                        pass
                    try:
                        data_queue.put_nowait(data_packet)
                    except _queue.Full:
                        pass

                # Metricas FPS
                fps_count += 1
                acc_infer_ms += inference_time
                acc_analyze_ms += t_analyze_ms
                fps_elapsed = time.time() - fps_start

                if fps_elapsed >= 5.0:
                    fps = fps_count / fps_elapsed
                    avg_infer = acc_infer_ms / fps_count
                    avg_analyze = acc_analyze_ms / fps_count
                    log.info(
                        f"[{name}] --- RESUMO 5s --- "
                        f"FPS={fps:.1f} | avg_infer={avg_infer:.1f}ms | "
                        f"avg_analyze={avg_analyze:.1f}ms | "
                        f"pellets={analysis['total_pellets']}"
                    )
                    fps_start = time.time()
                    fps_count = 0
                    acc_infer_ms = acc_analyze_ms = 0.0

                if t_analyze_ms > 100:
                    log.warning(f"[{name}] GARGALO ANALISE: {t_analyze_ms:.1f}ms "
                               f"(pellets={analysis['total_pellets']})")

            except Exception as e:
                log.error(f"[{name}] Erro no pipeline: {e}")

    except Exception as e:
        log.error(f"[{name}] Pipeline fatal: {e}")
    finally:
        if csv_logger is not None:
            csv_logger.flush()
        if detector is not None:
            detector.cleanup()
        log.info(f"[{name}] Pipeline finalizado")


class CameraManager:
    """
    Gerencia multiplas cameras com pipeline paralelo de 2 processos por camera.

    Por camera sao criados 2 processos:
      Reader   — cap.read() + recorte ROI               -> frame_queue
      Pipeline — inference GPU + analise + CSV + store   -> data_queue -> Main GUI

    As filas tem maxsize=1 com politica "latest-wins": frames velhos sao
    descartados automaticamente, garantindo que a GPU sempre processe o
    frame mais recente disponivel.
    """

    def __init__(self):
        self.cameras = {}
        self.processes = {}          # camera_id -> [p_reader, p_pipeline]
        self.stop_flags = {}
        self._frame_queues = {}      # camera_id -> mp.Queue (Reader -> Pipeline)
        self._data_queues = {}       # camera_id -> mp.Queue (Pipeline -> Main)
        self._config_queues = {}     # camera_id -> mp.Queue (Main -> Pipeline)
        self._roi_queues = {}        # camera_id -> mp.Queue (Main -> Reader)

        self._log_level = logging.getLogger('PelletDetector').level or logging.INFO

        cv2.setNumThreads(1)
        logger.info("CameraManager inicializado (Pipeline 2-stage Multiprocessing)")

    # =========================================================================
    #  GERENCIAMENTO DE CAMERAS
    # =========================================================================

    def add_camera(self, config):
        try:
            camera_id = config.id
            logger.info(f"Adicionando camera: {config.name} (ID: {camera_id})")

            self.cameras[camera_id] = config

            csv_filename = f"{config.name.replace(' ', '_')}.csv"
            csv_path = os.path.join(DATA_DIR, csv_filename)
            os.makedirs(DATA_DIR, exist_ok=True)

            self.stop_flags[camera_id] = mp.Event()

            # Filas do pipeline: maxsize=1 -> politica "latest-wins"
            self._frame_queues[camera_id] = mp.Queue(maxsize=1)
            self._data_queues[camera_id] = mp.Queue(maxsize=2)
            self._config_queues[camera_id] = mp.Queue()
            self._roi_queues[camera_id] = mp.Queue()

            p_reader = mp.Process(
                target=_reader_worker,
                args=(config, self.stop_flags[camera_id],
                      self._frame_queues[camera_id],
                      self._roi_queues[camera_id],
                      self._log_level),
                daemon=True,
                name=f"Reader-{config.name}"
            )
            p_pipeline = mp.Process(
                target=_pipeline_worker,
                args=(config, self.stop_flags[camera_id],
                      self._frame_queues[camera_id],
                      self._data_queues[camera_id],
                      csv_path,
                      self._config_queues[camera_id],
                      self._log_level),
                daemon=True,
                name=f"Pipeline-{config.name}"
            )

            self.processes[camera_id] = [p_reader, p_pipeline]
            p_reader.start()
            p_pipeline.start()

            return camera_id

        except Exception as e:
            logger.error(f"Erro ao adicionar camera: {e}")
            raise

    # =========================================================================
    #  UPDATE EM TEMPO REAL
    # =========================================================================

    def update_camera_config(self, camera_id, detection_rate=None, confidence=None, scale_mm_pixel=None, max_det=None, roi='_unchanged', frame_display_interval=None):
        """
        Atualiza configuracoes de uma camera em tempo real sem reiniciar processos.
        Envia atualizacoes via filas IPC para os processos worker.
        """
        if camera_id not in self.cameras:
            logger.error(f"Camera {camera_id} nao encontrada")
            return False

        config = self.cameras[camera_id]
        updated = []
        pipeline_update = {}

        try:
            if detection_rate is not None:
                config.detection_rate = detection_rate
                pipeline_update['detection_rate'] = detection_rate
                updated.append(f"detection_rate={detection_rate}")

            if confidence is not None:
                config.confidence = confidence
                pipeline_update['confidence'] = confidence
                updated.append(f"confidence={confidence:.2f}")

            if scale_mm_pixel is not None:
                config.scale_mm_pixel = scale_mm_pixel
                pipeline_update['scale_mm_pixel'] = scale_mm_pixel
                updated.append(f"scale={scale_mm_pixel}")

            if max_det is not None:
                config.max_det = max_det
                pipeline_update['max_det'] = max_det
                updated.append(f"max_det={max_det}")

            if frame_display_interval is not None:
                config.frame_display_interval = frame_display_interval
                pipeline_update['frame_display_interval'] = frame_display_interval
                updated.append(f"frame_display_interval={frame_display_interval}s")

            if roi != '_unchanged':
                config.roi = roi
                # Enviar atualizacao de ROI para o processo Reader
                if camera_id in self._roi_queues:
                    self._roi_queues[camera_id].put({'roi': roi})
                updated.append("roi=cleared" if roi is None else f"roi={roi}")

            # Enviar atualizacoes para o processo Pipeline
            if pipeline_update and camera_id in self._config_queues:
                self._config_queues[camera_id].put(pipeline_update)

            logger.info(f"[{config.name}] Config atualizado: {', '.join(updated)}")
            return True

        except Exception as e:
            logger.error(f"Erro ao atualizar config da camera {camera_id}: {e}")
            return False

    # =========================================================================
    #  CONTROLE DE CAMERAS
    # =========================================================================

    def stop_camera(self, camera_id):
        if camera_id not in self.cameras:
            return

        config = self.cameras[camera_id]
        logger.info(f"Parando camera: {config.name}")

        # Sinalizar parada para todos os processos
        self.stop_flags[camera_id].set()

        # Aguardar todos os processos do pipeline
        for proc in self.processes.get(camera_id, []):
            if proc.is_alive():
                proc.join(timeout=5.0)
                if proc.is_alive():
                    logger.warning(f"[{config.name}] Processo {proc.name} nao encerrou em 5s, terminando...")
                    proc.terminate()
                    proc.join(timeout=2.0)

        # Fechar filas para liberar recursos
        for q in [self._frame_queues.get(camera_id),
                   self._data_queues.get(camera_id),
                   self._config_queues.get(camera_id),
                   self._roi_queues.get(camera_id)]:
            if q is not None:
                try:
                    q.close()
                    q.join_thread()
                except Exception:
                    pass

        # Limpar todos os recursos desta camera
        self.cameras.pop(camera_id, None)
        self.processes.pop(camera_id, None)
        self.stop_flags.pop(camera_id, None)
        self._frame_queues.pop(camera_id, None)
        self._data_queues.pop(camera_id, None)
        self._config_queues.pop(camera_id, None)
        self._roi_queues.pop(camera_id, None)

    def get_frame(self, camera_id):
        """
        Obtem o data_packet mais recente do processo Pipeline.
        Drena a fila e retorna o ultimo item (latest-wins no consumidor).
        """
        dq = self._data_queues.get(camera_id)
        if dq is None:
            return None
        data = None
        try:
            while True:
                data = dq.get_nowait()
        except _queue.Empty:
            pass
        return data

    def is_running(self, camera_id):
        procs = self.processes.get(camera_id, [])
        return bool(procs) and any(p.is_alive() for p in procs)

    def list_cameras(self):
        return list(self.cameras.items())

    def stop_all(self):
        for camera_id in list(self.cameras.keys()):
            self.stop_camera(camera_id)
