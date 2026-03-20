"""
Detector de pelotas usando modelo de segmentação
Suporta TensorRT (.engine) e PyTorch (.pt) via Ultralytics
Retorna o resultado puro do modelo, sem pós-processamento
"""
import cv2
import numpy as np
import logging
import time
import os
import torch
from ultralytics import YOLO
from config import DEFAULT_CONFIDENCE

logger = logging.getLogger('PelletDetector.detector')


class Detector:
    """Detector de pelotas usando modelo de segmentação"""

    def __init__(self, model_path, device='cuda:0', confidence=DEFAULT_CONFIDENCE, max_det=100):
        self.model_path = model_path
        self.device = device
        self.confidence = confidence
        self.max_det = max_det

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo não encontrado: {model_path}")

        try:
            self._load_model()
            logger.info(f"Detector inicializado com sucesso")
            logger.info(f"  Modelo: {model_path}")
            logger.info(f"  Device: {device}")
            logger.info(f"  Confiança: {confidence}")
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            raise

    def _load_model(self):
        """Carrega o modelo (TensorRT ou PyTorch)"""
        model_ext = os.path.splitext(self.model_path)[1].lower()

        if model_ext == '.engine':
            self._load_tensorrt()
        elif model_ext == '.pt':
            self._load_pytorch()
        else:
            raise ValueError(f"Formato de modelo não suportado: {model_ext}")

        # Detectar imgsz do modelo (TensorRT engines têm shape fixa)
        self.imgsz = self._detect_imgsz()
        logger.info(f"  imgsz detectado: {self.imgsz}")

        # Debug: logar atributos disponíveis para diagnóstico
        model_inner = getattr(self.model, 'model', None)
        if model_inner is not None:
            bindings = getattr(model_inner, 'bindings', None)
            if bindings is not None:
                for name, b in bindings.items():
                    shape = b.get('shape') if isinstance(b, dict) else getattr(b, 'shape', None)
                    logger.debug(f"  binding '{name}': shape={shape}")
            metadata = getattr(model_inner, 'metadata', {})
            if metadata:
                logger.debug(f"  metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else type(metadata)}")

    def _detect_imgsz(self):
        """Detecta o tamanho de entrada do modelo"""
        model_inner = getattr(self.model, 'model', None)

        if model_inner is not None:
            # 1. Tentar via input shape do TensorRT engine (mais confiável)
            #    AutoBackend armazena bindings com shape do tensor de entrada
            bindings = getattr(model_inner, 'bindings', None)
            if bindings is not None:
                for name, binding in bindings.items():
                    shape = binding.get('shape') if isinstance(binding, dict) else getattr(binding, 'shape', None)
                    if shape is not None and len(shape) == 4:
                        # shape = (batch, channels, H, W)
                        h, w = shape[2], shape[3]
                        logger.debug(f"imgsz via TensorRT binding '{name}': {h}x{w}")
                        return max(h, w)

            # 2. Tentar via metadata do modelo
            metadata = getattr(model_inner, 'metadata', {})
            if isinstance(metadata, dict) and 'imgsz' in metadata:
                imgsz = metadata['imgsz']
                if isinstance(imgsz, (list, tuple)):
                    return max(imgsz)
                return int(imgsz)

            # 3. Tentar via atributo imgsz direto
            if hasattr(model_inner, 'imgsz'):
                imgsz = model_inner.imgsz
                if isinstance(imgsz, (list, tuple)):
                    return max(imgsz)
                return int(imgsz)

        # 4. Tentar via overrides do YOLO
        overrides = getattr(self.model, 'overrides', {})
        if 'imgsz' in overrides:
            imgsz = overrides['imgsz']
            if isinstance(imgsz, (list, tuple)):
                return max(imgsz)
            return int(imgsz)

        # Fallback: 640 (padrão YOLO)
        logger.warning("Não foi possível detectar imgsz do modelo, usando 640")
        return 640

    def _load_tensorrt(self):
        """Carrega modelo TensorRT usando Ultralytics"""
        try:
            logger.info("Limpando cache do CUDA...")
            torch.cuda.empty_cache()

            logger.info(f"Carregando modelo TensorRT via Ultralytics: {self.model_path}")
            self.model = YOLO(self.model_path, task='segment')
            self.model_type = 'tensorrt'

            model_type_info = getattr(self.model, 'type', 'unknown')
            logger.info(f"  Ultralytics model type: {model_type_info}")
            logger.info("  TensorRT inicializado com sucesso (GPU CUDA Compute)")

        except Exception as e:
            logger.error(f"Erro ao carregar modelo TensorRT via Ultralytics: {e}")
            raise

    def _load_pytorch(self):
        """Carrega modelo PyTorch (.pt) usando Ultralytics"""
        try:
            if self.device.startswith('cuda'):
                logger.info("Limpando cache do CUDA...")
                torch.cuda.empty_cache()

            logger.info(f"Carregando modelo PyTorch via Ultralytics: {self.model_path}")
            logger.info(f"  Device: {self.device}")

            self.model = YOLO(self.model_path, task='segment')
            self.model_type = 'pytorch'

            if self.device == 'cpu':
                logger.info("  PyTorch inicializado com sucesso (CPU)")
            else:
                logger.info("  PyTorch inicializado com sucesso (GPU acelerada via Ultralytics)")

        except Exception as e:
            logger.error(f"Erro ao carregar modelo PyTorch via Ultralytics: {e}")
            raise

    def infer(self, frame):
        """
        Executa inferência pura no frame, sem pós-processamento.

        Returns:
            tuple: (result, inference_time_ms)
                - result: objeto ultralytics Results com masks e boxes individuais
                - inference_time_ms: tempo de inferência em milissegundos
        """
        try:
            t_total_start = time.perf_counter()

            # --- Informações do frame de entrada ---
            frame_h, frame_w = frame.shape[:2]
            logger.debug(f"[infer] Frame entrada: {frame_w}x{frame_h}, dtype={frame.dtype}, "
                         f"model_type={self.model_type}, conf={self.confidence}")

            # --- Tempo real do predict ---
            t_predict_start = time.perf_counter()

            if self.model_type == 'tensorrt':
                results = self.model.predict(
                    source=frame,
                    half=True,
                    conf=self.confidence,
                    verbose=False,
                    max_det=self.max_det,
                    retina_masks=True,
                    imgsz=self.imgsz
                )
            else:
                use_half = self.device.startswith('cuda')
                results = self.model.predict(
                    source=frame,
                    device=self.device,
                    half=use_half,
                    conf=self.confidence,
                    verbose=False,
                    max_det=self.max_det,
                    retina_masks=True,
                    imgsz=self.imgsz
                )

            t_predict_end = time.perf_counter()
            predict_ms = (t_predict_end - t_predict_start) * 1000

            # --- Informações do resultado ---
            result = results[0]
            n_detections = len(result.boxes) if result.boxes is not None else 0
            has_masks = result.masks is not None
            mask_shape = result.masks.data.shape if has_masks else None

            t_total_end = time.perf_counter()
            total_infer_ms = (t_total_end - t_total_start) * 1000
            overhead_ms = total_infer_ms - predict_ms

            logger.debug(
                f"[infer] predict={predict_ms:.1f}ms | overhead={overhead_ms:.1f}ms | "
                f"total={total_infer_ms:.1f}ms | dets={n_detections} | "
                f"masks={mask_shape}"
            )

            if predict_ms > 200:
                logger.warning(f"[infer] LENTO: predict demorou {predict_ms:.1f}ms "
                               f"(frame {frame_w}x{frame_h})")

            return result, total_infer_ms

        except Exception as e:
            logger.error(f"Erro durante inferência: {e}")
            raise

    def cleanup(self):
        """Libera recursos da GPU explicitamente"""
        try:
            if hasattr(self, 'model') and self.model is not None:
                del self.model
                self.model = None
                logger.debug("Modelo YOLO/TensorRT liberado")

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("Cache CUDA liberado")

        except Exception as e:
            logger.warning(f"Erro ao liberar recursos: {e}")

    def __del__(self):
        self.cleanup()
