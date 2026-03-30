"""
Gerenciador de câmeras — Pipeline 3-stage por câmera
Arquitetura: Reader → Inference → PostProc (threads independentes)
Otimizado para Xeon E5-2603 v3 (6 núcleos, 1.6 GHz) + RTX 4000 Quadro

Ganho principal: enquanto a GPU processa frame N, a CPU já lê o frame N+1.
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


class CameraManager:
    """
    Gerencia múltiplas câmeras com pipeline paralelo de 3 estágios por câmera.

    Por câmera são criadas 3 threads daemon:
      Reader    — cap.read() + recorte ROI → _frame_queues[id]
      Inference — detector.infer() na GPU  → _result_queues[id]
      PostProc  — analyzer + CSV + store   → latest_data[id]

    As filas têm maxsize=1 com política "latest-wins": frames velhos são
    descartados automaticamente, garantindo que a GPU sempre processe o
    frame mais recente disponível — importante em hardware de clock baixo.
    """

    def __init__(self):
        self.cameras = {}
        self.threads = {}           # camera_id -> [t_reader, t_infer, t_postproc]
        self.latest_data = {}
        self.data_locks = {}
        self.stop_flags = {}
        self.csv_loggers = {}
        self.detectors = {}         # Referências para update em tempo real
        self.analyzers = {}         # Referências para update em tempo real
        self._frame_queues = {}     # camera_id -> Queue(maxsize=1)
        self._result_queues = {}    # camera_id -> Queue(maxsize=1)

        cv2.setNumThreads(1)
        logger.info("CameraManager inicializado (Pipeline 3-stage Threading)")

    # =========================================================================
    #  GERENCIAMENTO DE CÂMERAS
    # =========================================================================

    def add_camera(self, config):
        try:
            camera_id = config.id
            logger.info(f"Adicionando câmera: {config.name} (ID: {camera_id})")

            self.cameras[camera_id] = config

            csv_filename = f"{config.name.replace(' ', '_')}.csv"
            csv_path = os.path.join(DATA_DIR, csv_filename)
            os.makedirs(DATA_DIR, exist_ok=True)
            self.csv_loggers[camera_id] = CSVLogger(csv_path)

            self.latest_data[camera_id] = None
            self.data_locks[camera_id] = threading.Lock()
            self.stop_flags[camera_id] = threading.Event()

            # Filas do pipeline: maxsize=1 → política "latest-wins"
            self._frame_queues[camera_id] = queue.Queue(maxsize=1)
            self._result_queues[camera_id] = queue.Queue(maxsize=1)

            t_reader = threading.Thread(
                target=self._stage_reader,
                args=(camera_id,),
                daemon=True,
                name=f"Reader-{config.name}"
            )
            t_infer = threading.Thread(
                target=self._stage_inference,
                args=(camera_id,),
                daemon=True,
                name=f"Infer-{config.name}"
            )
            t_postproc = threading.Thread(
                target=self._stage_postproc,
                args=(camera_id,),
                daemon=True,
                name=f"PostProc-{config.name}"
            )

            self.threads[camera_id] = [t_reader, t_infer, t_postproc]
            t_reader.start()
            t_infer.start()
            t_postproc.start()

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

    # =========================================================================
    #  ESTÁGIO 1 — READER: lê frames e aplica ROI
    # =========================================================================

    def _stage_reader(self, camera_id):
        """
        Lê frames da câmera continuamente, aplica recorte ROI e coloca o
        frame mais recente na fila do pipeline (latest-wins, sem bloqueio).
        """
        config = self.cameras[camera_id]
        stop_flag = self.stop_flags[camera_id]
        frame_queue = self._frame_queues[camera_id]

        logger.info(f"[{config.name}] Reader iniciado")
        cap = None

        try:
            try:
                source = int(config.source)
            except (ValueError, TypeError):
                source = config.source

            is_file = isinstance(source, str) and source.endswith(('.mp4', '.avi', '.mov', '.mkv'))
            RECONNECT_DELAY = 5.0

            cap = self._open_capture(source)
            if cap is None:
                raise RuntimeError(f"Não foi possível abrir source: {config.source}")

            while not stop_flag.is_set():
                ret, frame = cap.read()

                if not ret:
                    if is_file:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        logger.warning(f"[{config.name}] Conexão perdida. Reconectando...")
                        cap.release()
                        cap = None
                        reconnect_count = 0
                        while not stop_flag.is_set():
                            stop_flag.wait(timeout=RECONNECT_DELAY)
                            if stop_flag.is_set():
                                break
                            reconnect_count += 1
                            logger.info(f"[{config.name}] Tentativa #{reconnect_count}...")
                            cap = self._open_capture(source)
                            if cap is not None:
                                logger.info(f"[{config.name}] Reconectado com sucesso!")
                                break
                            logger.warning(f"[{config.name}] Tentativa #{reconnect_count} falhou.")
                        continue

                # Aplicar ROI (lido a cada frame — suporta update em tempo real)
                roi = config.roi
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
                        roi = None  # ROI inválida, usa frame completo

                # Política "latest-wins": se a fila está cheia, descarta o frame
                # antigo e coloca o mais recente (evita latência acumulada)
                try:
                    frame_queue.put_nowait((full_frame, inference_frame, roi))
                except queue.Full:
                    try:
                        frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        frame_queue.put_nowait((full_frame, inference_frame, roi))
                    except queue.Full:
                        pass

        except Exception as e:
            logger.error(f"[{config.name}] Reader fatal: {e}")
        finally:
            if cap is not None:
                cap.release()
            # Sinaliza fim de stream para o estágio seguinte
            try:
                frame_queue.put(None)
            except Exception:
                pass
            logger.info(f"[{config.name}] Reader finalizado")

    # =========================================================================
    #  ESTÁGIO 2 — INFERENCE: executa inferência na GPU
    # =========================================================================

    def _stage_inference(self, camera_id):
        """
        Carrega o modelo e executa inferência GPU nos frames recebidos do
        Reader. Aplica o rate limiting configurado (detection_rate).
        Enquanto aguarda o resultado da GPU, o Reader continua lendo frames.
        """
        config = self.cameras[camera_id]
        stop_flag = self.stop_flags[camera_id]
        frame_queue = self._frame_queues[camera_id]
        result_queue = self._result_queues[camera_id]

        logger.info(f"[{config.name}] Inference iniciado (device={config.device})")

        try:
            detector = Detector(config.model_path, config.device, config.confidence, config.max_det)
            self.detectors[camera_id] = detector

            last_inference_time = 0.0
            fps_start = time.time()
            fps_count = 0

            while not stop_flag.is_set():
                try:
                    item = frame_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if item is None:  # Sinal de fim do Reader
                    break

                full_frame, inference_frame, roi = item

                # Rate limiting lido a cada iteração — suporta update em tempo real
                target_fps = float(config.detection_rate)
                min_interval = 1.0 / target_fps if target_fps > 0 else 0.0
                current_time = time.time()
                if (current_time - last_inference_time) < min_interval:
                    continue
                last_inference_time = current_time

                try:
                    result, inference_time = detector.infer(inference_frame)

                    payload = (full_frame, inference_frame, roi, result, inference_time)
                    try:
                        result_queue.put_nowait(payload)
                    except queue.Full:
                        try:
                            result_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            result_queue.put_nowait(payload)
                        except queue.Full:
                            pass

                    fps_count += 1
                    fps_elapsed = time.time() - fps_start
                    if fps_elapsed >= 5.0:
                        fps = fps_count / fps_elapsed
                        logger.info(f"[{config.name}] Inference FPS: {fps:.1f} (alvo={config.detection_rate})")
                        fps_start = time.time()
                        fps_count = 0

                except Exception as e:
                    logger.error(f"[{config.name}] Erro na inferência: {e}")

        except Exception as e:
            logger.error(f"[{config.name}] Inference fatal: {e}")
        finally:
            # Sinaliza fim para o PostProc
            try:
                result_queue.put(None)
            except Exception:
                pass
            logger.info(f"[{config.name}] Inference finalizado")

    # =========================================================================
    #  ESTÁGIO 3 — POSTPROC: analisa, loga CSV e armazena para UI
    # =========================================================================

    def _stage_postproc(self, camera_id):
        """
        Recebe resultados brutos da GPU, executa o PelletAnalyzer (CPU),
        grava CSV de forma assíncrona e publica o data_packet para a UI.
        Roda enquanto o Inference processa o próximo frame.
        """
        config = self.cameras[camera_id]
        stop_flag = self.stop_flags[camera_id]
        result_queue = self._result_queues[camera_id]
        data_lock = self.data_locks[camera_id]
        csv_logger = self.csv_loggers[camera_id]

        logger.info(f"[{config.name}] PostProc iniciado")

        try:
            analyzer = PelletAnalyzer(config.scale_mm_pixel)
            self.analyzers[camera_id] = analyzer

            last_annotated_time = 0.0
            fps_start = time.time()
            fps_count = 0

            acc_infer_ms = 0.0
            acc_analyze_ms = 0.0

            while not stop_flag.is_set():
                try:
                    item = result_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if item is None:  # Sinal de fim do Inference
                    break

                full_frame, inference_frame, roi, result, inference_time = item

                now_mono = time.time()
                needs_annotation = (now_mono - last_annotated_time) >= config.frame_display_interval
                frame_for_analysis = inference_frame if needs_annotation else None

                try:
                    t_analyze_start = time.perf_counter()
                    analysis = analyzer.analyze(result, frame_for_analysis, max_det=config.max_det)
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

                    csv_logger.log(config.name, analysis)

                    data_packet = {
                        'frame': analysis['annotated_frame'],
                        'analysis': analysis,
                        'inference_time': inference_time
                    }
                    with data_lock:
                        self.latest_data[camera_id] = data_packet

                    fps_count += 1
                    acc_infer_ms += inference_time
                    acc_analyze_ms += t_analyze_ms
                    fps_elapsed = time.time() - fps_start

                    if fps_elapsed >= 5.0:
                        fps = fps_count / fps_elapsed
                        avg_infer = acc_infer_ms / fps_count
                        avg_analyze = acc_analyze_ms / fps_count
                        logger.info(
                            f"[{config.name}] --- RESUMO 5s --- "
                            f"FPS={fps:.1f} | avg_infer={avg_infer:.1f}ms | "
                            f"avg_analyze={avg_analyze:.1f}ms | "
                            f"pellets={analysis['total_pellets']}"
                        )
                        fps_start = time.time()
                        fps_count = 0
                        acc_infer_ms = acc_analyze_ms = 0.0

                    if t_analyze_ms > 100:
                        logger.warning(f"[{config.name}] GARGALO ANALISE: {t_analyze_ms:.1f}ms "
                                       f"(pellets={analysis['total_pellets']})")

                except Exception as e:
                    logger.error(f"[{config.name}] Erro no PostProc: {e}")

        except Exception as e:
            logger.error(f"[{config.name}] PostProc fatal: {e}")
        finally:
            logger.info(f"[{config.name}] PostProc finalizado")

    # =========================================================================
    #  UPDATE EM TEMPO REAL
    # =========================================================================

    def update_camera_config(self, camera_id, detection_rate=None, confidence=None, scale_mm_pixel=None, max_det=None, roi='_unchanged', frame_display_interval=None):
        """
        Atualiza configurações de uma câmera em tempo real sem reiniciar threads.
        Os estágios do pipeline leem os atributos de config a cada iteração.
        """
        if camera_id not in self.cameras:
            logger.error(f"Câmera {camera_id} não encontrada")
            return False

        config = self.cameras[camera_id]
        updated = []

        try:
            if detection_rate is not None:
                config.detection_rate = detection_rate
                updated.append(f"detection_rate={detection_rate}")

            if confidence is not None:
                config.confidence = confidence
                if camera_id in self.detectors:
                    self.detectors[camera_id].confidence = confidence
                updated.append(f"confidence={confidence:.2f}")

            if scale_mm_pixel is not None:
                config.scale_mm_pixel = scale_mm_pixel
                if camera_id in self.analyzers:
                    self.analyzers[camera_id].scale = scale_mm_pixel
                updated.append(f"scale={scale_mm_pixel}")

            if max_det is not None:
                config.max_det = max_det
                if camera_id in self.detectors:
                    detector = self.detectors[camera_id]
                    detector.max_det = max_det
                    detector.model.overrides['max_det'] = max_det
                    detector.model.predictor = None
                updated.append(f"max_det={max_det}")

            if frame_display_interval is not None:
                config.frame_display_interval = frame_display_interval
                updated.append(f"frame_display_interval={frame_display_interval}s")

            if roi != '_unchanged':
                config.roi = roi
                updated.append("roi=cleared" if roi is None else f"roi={roi}")

            logger.info(f"[{config.name}] Config atualizado: {', '.join(updated)}")
            return True

        except Exception as e:
            logger.error(f"Erro ao atualizar config da câmera {camera_id}: {e}")
            return False

    # =========================================================================
    #  CONTROLE DE CÂMERAS
    # =========================================================================

    def stop_camera(self, camera_id):
        if camera_id not in self.cameras:
            return

        config = self.cameras[camera_id]
        logger.info(f"Parando câmera: {config.name}")

        # Sinalizar parada para todas as threads
        self.stop_flags[camera_id].set()

        # Aguardar todas as threads do pipeline
        for thread in self.threads.get(camera_id, []):
            if thread.is_alive():
                thread.join(timeout=5.0)
                if thread.is_alive():
                    logger.warning(f"[{config.name}] Thread {thread.name} não encerrou em 5s")

        # Liberar VRAM
        detector = self.detectors.pop(camera_id, None)
        if detector is not None:
            detector.cleanup()
            logger.info(f"[{config.name}] VRAM liberada")

        # Limpar todos os recursos desta câmera
        self.cameras.pop(camera_id, None)
        self.threads.pop(camera_id, None)
        self.latest_data.pop(camera_id, None)
        self.data_locks.pop(camera_id, None)
        self.stop_flags.pop(camera_id, None)
        self.csv_loggers.pop(camera_id, None)
        self.analyzers.pop(camera_id, None)
        self._frame_queues.pop(camera_id, None)
        self._result_queues.pop(camera_id, None)

    def get_frame(self, camera_id):
        lock = self.data_locks.get(camera_id)
        if lock is None:
            return None
        with lock:
            data = self.latest_data.get(camera_id)
            self.latest_data[camera_id] = None
            return data

    def is_running(self, camera_id):
        threads = self.threads.get(camera_id, [])
        return bool(threads) and any(t.is_alive() for t in threads)

    def list_cameras(self):
        return list(self.cameras.items())

    def stop_all(self):
        for camera_id in list(self.cameras.keys()):
            self.stop_camera(camera_id)
