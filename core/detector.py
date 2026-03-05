"""
Detector de pelotas usando modelo de segmentação
Suporta TensorRT (.engine) via Ultralytics e ONNX (.onnx) via ONNXRuntime
"""
import cv2
import numpy as np
import logging
import time
import os
import torch
from ultralytics import YOLO
from config import DEFAULT_MODEL_INPUT_SIZE, DEFAULT_CONFIDENCE

logger = logging.getLogger('PelletDetector.detector')

class Detector:
    """Detector de pelotas usando modelo de segmentação"""

    def __init__(self, model_path, device='cuda:0', confidence=DEFAULT_CONFIDENCE):
        """
        Inicializa o detector

        Args:
            model_path: Caminho para o modelo (.engine ou .onnx)
            device: Device para inferência ('cuda:0', 'cuda:1', 'cpu')
            confidence: Threshold de confiança (0.0 a 1.0)
        """
        self.model_path = model_path
        self.device = device
        self.confidence = confidence
        self.session = None
        self.input_size = DEFAULT_MODEL_INPUT_SIZE

        # Verificar se arquivo existe
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo não encontrado: {model_path}")

        # Carregar modelo
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
        """Carrega o modelo (TensorRT ou ONNX Runtime)"""
        model_ext = os.path.splitext(self.model_path)[1].lower()

        if model_ext == '.engine':
            self._load_tensorrt()

        elif model_ext == '.onnx':
            self._load_onnx()

        else:
            raise ValueError(f"Formato de modelo não suportado: {model_ext}")

    def _load_onnx(self):
        """Carrega modelo ONNX"""
        try:
            import onnxruntime as ort

            # Configurar providers (GPU ou CPU)
            providers = []
            if self.device.startswith('cuda'):
                providers.append('CUDAExecutionProvider')
            providers.append('CPUExecutionProvider')

            logger.info(f"Tentando carregar modelo ONNX com providers: {providers}")

            # Criar sessão ONNX
            self.session = ort.InferenceSession(
                self.model_path,
                providers=providers
            )

            # Informações do modelo
            input_info = self.session.get_inputs()[0]
            logger.info(f"  Input: {input_info.name}, shape: {input_info.shape}, tipo: {input_info.type}")

            # Verificar provider ativo
            active_provider = self.session.get_providers()[0]
            logger.info(f"  Provider ativo: {active_provider}")

            if 'CUDA' in active_provider:
                logger.info("  Inferência rodará na GPU")
            else:
                logger.warning("  Inferência rodará na CPU (pode ser lento)")

            self.model_type = 'onnx'

        except ImportError:
            logger.error("onnxruntime não instalado. Execute: pip install onnxruntime-gpu")
            raise
        except Exception as e:
            logger.error(f"Erro ao carregar modelo ONNX: {e}")
            raise

    def _load_tensorrt(self):
        """Carrega modelo TensorRT usando Ultralytics (YOLO)"""
        try:
            logger.info("Limpando cache do CUDA...")
            torch.cuda.empty_cache()

            logger.info(f"Carregando modelo TensorRT via Ultralytics: {self.model_path}")

            # O YOLO gerencia toda a memória e ponteiros automaticamente
            self.model = YOLO(self.model_path, task='segment')
            
            self.model_type = 'tensorrt'

            logger.info("  TensorRT inicializado com sucesso (GPU acelerada via Ultralytics)")

        except Exception as e:
            logger.error(f"Erro ao carregar modelo TensorRT via Ultralytics: {e}")
            raise

    def preprocess(self, frame):
        """Pré-processa frame para inferência (Usado apenas no fluxo ONNX)"""
        input_frame = cv2.resize(frame, self.input_size)
        input_frame = cv2.cvtColor(input_frame, cv2.COLOR_BGR2RGB)
        input_frame = input_frame.astype(np.float32) / 255.0
        input_frame = np.transpose(input_frame, (2, 0, 1))
        input_frame = np.expand_dims(input_frame, axis=0)
        return input_frame

    def postprocess(self, output, original_shape):
        """Pós-processa saída do modelo (Usado apenas no fluxo ONNX)"""
        if len(output.shape) == 4:
            mask = output[0, 0]
        elif len(output.shape) == 3:
            mask = output[0]
        else:
            mask = output

        mask = (mask > self.confidence).astype(np.uint8)
        mask_resized = cv2.resize(mask, (original_shape[1], original_shape[0]),
                                  interpolation=cv2.INTER_NEAREST)
        return mask_resized

    def infer(self, frame):
        """Executa inferência em um frame"""
        try:
            start_time = time.time()
            original_shape = frame.shape[:2]

            # Inferência baseada no tipo de modelo
            if hasattr(self, 'model_type') and self.model_type == 'tensorrt':
                # Ultralytics faz pre e pós processamento nativamente
                mask = self._infer_tensorrt(frame, original_shape)
            else:
                # Fluxo antigo de matrizes manuais para ONNX
                input_tensor = self.preprocess(frame)
                output = self._infer_onnx(input_tensor)
                mask = self.postprocess(output, original_shape)

            inference_time = (time.time() - start_time) * 1000  # ms
            logger.debug(f"Inferência completada em {inference_time:.1f}ms")

            return mask, inference_time

        except Exception as e:
            logger.error(f"Erro durante inferência: {e}")
            raise

    def _infer_onnx(self, input_tensor):
        """Inferência usando ONNX Runtime"""
        if self.session is None:
            raise RuntimeError("Modelo ONNX não carregado")
        input_name = self.session.get_inputs()[0].name
        output_name = self.session.get_outputs()[0].name
        outputs = self.session.run([output_name], {input_name: input_tensor})
        return outputs[0]

    def _infer_tensorrt(self, frame, original_shape):
        """Inferência usando YOLO com separação de instâncias para granulometria"""
        
        # DICA: Aumentei o max_det para 500! Como é uma esteira de pelotização, 
        # 100 pelotas por frame (o padrão do YOLO) pode ser pouco.
        results = self.model.predict(
            source=frame,
            device=self.device,  
            half=True,           
            conf=self.confidence,
            max_det=100,         
            verbose=False,
            retina_masks=True
        )

        result = results[0]
        # Cria uma tela preta vazia do tamanho da imagem da câmera
        final_mask = np.zeros((original_shape[0], original_shape[1]), dtype=np.uint8)

        if result.masks is not None:
            # Pega as matrizes individuais (cada pelota separada)
            masks = result.masks.data.cpu().numpy()
            
            for m in masks:
                # Redimensiona a máscara individual para o tamanho da tela
                m_resized = cv2.resize(m, (original_shape[1], original_shape[0]), interpolation=cv2.INTER_NEAREST)
                m_binary = (m_resized > 0.5).astype(np.uint8)
                
                # 1. Adiciona a pelota na tela final
                final_mask = np.bitwise_or(final_mask, m_binary)
                
                # 2. O SEGREDO: Desenha um contorno preto (0) de 1 pixel ao redor 
                # da pelota recém-adicionada para garantir a separação física.
                contours, _ = cv2.findContours(m_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(final_mask, contours, -1, 0, 1)
                
            return final_mask
        else:
            return final_mask

    def __del__(self):
        """Libera recursos"""
        if self.session is not None:
            self.session = None
            logger.debug("Recursos do detector ONNX liberados")
        # O YOLO/PyTorch lida com a própria coleta de lixo, então não precisamos forçar a limpeza aqui