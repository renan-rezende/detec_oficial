"""
Gerenciador de câmeras - coordena threads de processamento
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
from config import MAX_QUEUE_SIZE


logger = logging.getLogger('PelletDetector.camera_manager')


class CameraConfig:
    """Configuração de uma câmera"""

    def __init__(self, name, source, model_path, detection_rate, scale_mm_pixel,
                 confidence, device):
        self.name = name
        self.source = source  # Caminho de arquivo, índice webcam, ou URL RTSP
        self.model_path = model_path
        self.detection_rate = detection_rate  # Processar 1 a cada N frames
        self.scale_mm_pixel = scale_mm_pixel
        self.confidence = confidence
        self.device = device
        self.id = str(uuid.uuid4())[:8]  # ID único


class CameraManager:
    """Gerencia múltiplas câmeras processando simultaneamente"""

    def __init__(self):
        """Inicializa o gerenciador"""
        self.cameras = {}  # {camera_id: CameraConfig}
        self.threads = {}  # {camera_id: Thread}
        self.queues = {}  # {camera_id: Queue}
        self.stop_flags = {}  # {camera_id: Event}
        self.csv_loggers = {}  # {camera_id: CSVLogger} - um por câmera

        logger.info("CameraManager inicializado")

    def add_camera(self, config):
        """
        Adiciona e inicia processamento de uma câmera

        Args:
            config: CameraConfig

        Returns:
            str: ID da câmera

        Raises:
            Exception: Se houver erro ao iniciar câmera
        """
        try:
            camera_id = config.id

            logger.info(f"Adicionando câmera: {config.name} (ID: {camera_id})")

            # Armazenar configuração
            self.cameras[camera_id] = config

            # Criar CSVLogger específico para esta câmera
            # Nome do arquivo: data/<nome_camera>.csv
            csv_filename = f"{config.name.replace(' ', '_')}.csv"
            csv_path = os.path.join('data', csv_filename)
            self.csv_loggers[camera_id] = CSVLogger(csv_path)

            logger.info(f"CSV criado para câmera {config.name}: {csv_path}")

            # Criar Queue para comunicação
            self.queues[camera_id] = queue.Queue(maxsize=MAX_QUEUE_SIZE)

            # Criar Event para stop flag
            self.stop_flags[camera_id] = threading.Event()

            # Criar e iniciar thread
            thread = threading.Thread(
                target=self._process_camera,
                args=(camera_id,),
                daemon=True,
                name=f"Camera-{config.name}"
            )
            self.threads[camera_id] = thread
            thread.start()

            logger.info(f"Câmera {config.name} iniciada com sucesso")

            return camera_id

        except Exception as e:
            logger.error(f"Erro ao adicionar câmera {config.name}: {e}")
            # Limpar recursos em caso de erro
            if camera_id in self.queues:
                del self.queues[camera_id]
            if camera_id in self.stop_flags:
                del self.stop_flags[camera_id]
            if camera_id in self.csv_loggers:
                del self.csv_loggers[camera_id]
            raise

    def _process_camera(self, camera_id):
        """
        Thread de processamento de uma câmera

        Args:
            camera_id: ID da câmera
        """
        config = self.cameras[camera_id]
        stop_flag = self.stop_flags[camera_id]
        output_queue = self.queues[camera_id]

        logger.info(f"[{config.name}] Thread iniciada")

        detector = None
        analyzer = None
        cap = None

        try:
            # Inicializar detector
            logger.info(f"[{config.name}] Carregando modelo...")
            detector = Detector(config.model_path, config.device, config.confidence)

            # Inicializar analyzer
            analyzer = PelletAnalyzer(config.scale_mm_pixel)

            # Abrir source de vídeo
            logger.info(f"[{config.name}] Abrindo source: {config.source}")

            # Tentar converter source para inteiro (webcam)
            try:
                source = int(config.source)
            except ValueError:
                source = config.source

            cap = cv2.VideoCapture(source)

            if not cap.isOpened():
                raise RuntimeError(f"Não foi possível abrir source: {config.source}")

            # Configurar buffer pequeno para reduzir latência
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            logger.info(f"[{config.name}] Iniciando loop de processamento")

            frame_count = 0
            fps_start_time = time.time()
            fps_frame_count = 0
            last_process_time = time.time()

            while not stop_flag.is_set():
                # Ler frame
                ret, frame = cap.read()

                if not ret:
                    # Se for arquivo, voltar ao início ou parar
                    if isinstance(source, str) and source.endswith(('.mp4', '.avi', '.mov')):
                        logger.info(f"[{config.name}] Fim do vídeo, reiniciando...")
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        logger.error(f"[{config.name}] Erro ao ler frame")
                        break

                frame_count += 1

                # Aplicar taxa de detecção (processar 1 a cada N frames)
                if frame_count % config.detection_rate != 0:
                    continue

                # Controle de tempo: adicionar delay para limitar FPS de processamento
                # Se detection_rate = 1, processar ~1 FPS (1 vez por segundo)
                # Se detection_rate = 5, processar ~5 FPS (1 vez a cada 0.2s)
                elapsed = time.time() - last_process_time
                min_interval = 1.0 / config.detection_rate  # Intervalo mínimo entre processamentos

                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)

                last_process_time = time.time()

                try:
                    # Inferência
                    mask, inference_time = detector.infer(frame)

                    # Análise
                    analysis = analyzer.analyze(mask, frame)

                    # Salvar no CSV específico desta câmera
                    csv_logger = self.csv_loggers[camera_id]
                    csv_logger.log(config.name, analysis)

                    # Enviar para Queue (não bloqueante)
                    try:
                        output_queue.put_nowait({
                            'frame': analysis['annotated_frame'],
                            'analysis': analysis,
                            'inference_time': inference_time
                        })
                    except queue.Full:
                        # Queue cheia, descartar frame mais antigo
                        try:
                            output_queue.get_nowait()
                            output_queue.put_nowait({
                                'frame': analysis['annotated_frame'],
                                'analysis': analysis,
                                'inference_time': inference_time
                            })
                        except:
                            pass

                    # Calcular FPS
                    fps_frame_count += 1
                    if time.time() - fps_start_time >= 5.0:  # A cada 5 segundos
                        fps = fps_frame_count / (time.time() - fps_start_time)
                        logger.info(f"[{config.name}] FPS: {fps:.1f}, "
                                   f"Inferência: {inference_time:.1f}ms")
                        fps_start_time = time.time()
                        fps_frame_count = 0

                except Exception as e:
                    logger.error(f"[{config.name}] Erro no processamento: {e}")
                    continue

        except Exception as e:
            logger.error(f"[{config.name}] Erro fatal na thread: {e}")

        finally:
            # Liberar recursos
            if cap is not None:
                cap.release()
            logger.info(f"[{config.name}] Thread finalizada")

    def stop_camera(self, camera_id):
        """
        Para processamento de uma câmera

        Args:
            camera_id: ID da câmera
        """
        if camera_id not in self.cameras:
            logger.warning(f"Câmera {camera_id} não encontrada")
            return

        config = self.cameras[camera_id]
        logger.info(f"Parando câmera: {config.name}")

        # Sinalizar stop
        self.stop_flags[camera_id].set()

        # Aguardar thread terminar (timeout de 5s)
        thread = self.threads.get(camera_id)
        if thread and thread.is_alive():
            thread.join(timeout=5.0)

        # Limpar recursos
        if camera_id in self.cameras:
            del self.cameras[camera_id]
        if camera_id in self.threads:
            del self.threads[camera_id]
        if camera_id in self.queues:
            del self.queues[camera_id]
        if camera_id in self.stop_flags:
            del self.stop_flags[camera_id]
        if camera_id in self.csv_loggers:
            del self.csv_loggers[camera_id]

        logger.info(f"Câmera {config.name} parada")

    def get_frame(self, camera_id, timeout=0.1):
        """
        Obtém último frame processado de uma câmera

        Args:
            camera_id: ID da câmera
            timeout: Timeout em segundos

        Returns:
            dict or None: {'frame': np.ndarray, 'analysis': dict} ou None
        """
        if camera_id not in self.queues:
            return None

        try:
            return self.queues[camera_id].get(timeout=timeout)
        except queue.Empty:
            return None

    def is_running(self, camera_id):
        """
        Verifica se câmera está rodando

        Args:
            camera_id: ID da câmera

        Returns:
            bool: True se rodando
        """
        return camera_id in self.threads and self.threads[camera_id].is_alive()

    def list_cameras(self):
        """
        Lista todas as câmeras

        Returns:
            list: Lista de (camera_id, CameraConfig)
        """
        return [(cid, config) for cid, config in self.cameras.items()]

    def stop_all(self):
        """Para todas as câmeras"""
        logger.info("Parando todas as câmeras...")

        camera_ids = list(self.cameras.keys())
        for camera_id in camera_ids:
            self.stop_camera(camera_id)

        logger.info("Todas as câmeras paradas")
