"""
Analisador de pelotas - processa resultados do YOLO e classifica pelotas
Versao otimizada: operacoes vetorizadas em batch (numpy) em vez de loop Python por mascara.
"""
import cv2
import numpy as np
import logging
import time
import os as _os
from concurrent.futures import ThreadPoolExecutor
from config import GRANULOMETRIC_RANGES, RANGE_ORDER


def _resize_mask(args):
    """Função de nível de módulo para uso no ThreadPoolExecutor."""
    mask, target_w, target_h = args
    return cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)


logger = logging.getLogger('PelletDetector.analyzer')


class PelletAnalyzer:
    """Analisa resultados de segmentacao e classifica pelotas"""

    # Pool compartilhado entre todas as instâncias — criado uma única vez.
    # cv2.resize() libera o GIL, então threads realmente rodam em paralelo.
    # Usa no máximo metade dos núcleos disponíveis (deixa cores para o pipeline).
    _resize_pool = ThreadPoolExecutor(
        max_workers=max(1, min((_os.cpu_count() or 2) // 2, 4)),
        thread_name_prefix="MaskResize"
    )
    # Número mínimo de máscaras para compensar o overhead do pool (~1-2ms)
    _PARALLEL_RESIZE_THRESHOLD = 8

    def __init__(self, scale_mm_per_pixel, min_area=50):
        self.scale = scale_mm_per_pixel
        self.min_area = min_area
        self.ranges = GRANULOMETRIC_RANGES
        # Limites pre-computados para classificacao vetorizada via np.searchsorted
        self._boundaries = np.array([self.ranges[r][0] for r in RANGE_ORDER[1:]])

        logger.info(f"Analisador inicializado")
        logger.info(f"  Escala: {scale_mm_per_pixel} mm/pixel")
        logger.info(f"  Area minima: {min_area} pixels")

    def classify_pellet(self, diameter_mm):
        for range_name in RANGE_ORDER:
            min_val, max_val = self.ranges[range_name]
            if min_val <= diameter_mm < max_val:
                return range_name
        return 'range_above_19'

    def analyze(self, result, frame=None, max_det=None):
        """
        Analisa resultado do YOLO extraindo informacoes de cada pelota individual.
        Versao otimizada com operacoes vetorizadas em batch.

        Args:
            result: Objeto ultralytics Results (saida direta do modelo)
            frame: Frame original (opcional, para anotacao)
            max_det: Maximo de deteccoes a processar (opcional)

        Returns:
            dict com total_pellets, media, pellets, range_counts,
                 range_relations, annotated_frame
        """
        t_analyze_start = time.perf_counter()

        original_shape = result.orig_shape  # (H, W)

        # --- Transferencia GPU->CPU das mascaras ---
        t_cpu_start = time.perf_counter()
        if result.masks is not None:
            masks_data = result.masks.data.cpu().numpy()  # (N, H_mask, W_mask)
        else:
            masks_data = None
        cpu_transfer_ms = (time.perf_counter() - t_cpu_start) * 1000

        # Limitar numero de mascaras ao max_det (YOLO/TensorRT pode ignorar max_det em runtime)
        if masks_data is not None and max_det is not None and len(masks_data) > max_det:
            masks_data = masks_data[:max_det]

        n_raw_masks = len(masks_data) if masks_data is not None else 0
        mask_tensor_shape = result.masks.data.shape if result.masks is not None else None
        logger.debug(f"[analyze] masks GPU->CPU: {cpu_transfer_ms:.2f}ms | "
                     f"masks tensor={mask_tensor_shape} | orig_shape={original_shape}")

        # Early return se nao ha deteccoes
        if masks_data is None or n_raw_masks == 0:
            t_total = (time.perf_counter() - t_analyze_start) * 1000
            logger.debug(f"[analyze] Sem deteccoes ({t_total:.1f}ms)")
            empty_result = {
                'total_pellets': 0, 'media': 0.0, 'pellets': [],
                'range_counts': {r: 0 for r in RANGE_ORDER},
                'range_relations': {r: 0.0 for r in RANGE_ORDER},
                'annotated_frame': frame.copy() if frame is not None else None
            }
            return empty_result

        # === PROCESSAMENTO VETORIZADO EM BATCH ===
        t_loop_start = time.perf_counter()

        target_h, target_w = original_shape
        mask_h, mask_w = masks_data.shape[1], masks_data.shape[2]

        t_bin_start = time.perf_counter()

        if frame is not None:
            # --- Caminho COM anotacao: resolucao cheia para overlay/contornos ---
            masks_binary = (masks_data > 0.5).astype(np.uint8)  # (N, H, W)
            t_bin_ms = (time.perf_counter() - t_bin_start) * 1000

            t_resize_start = time.perf_counter()
            needs_resize = (mask_h != target_h or mask_w != target_w)
            if needs_resize:
                resized = np.empty((n_raw_masks, target_h, target_w), dtype=np.uint8)
                if n_raw_masks >= self._PARALLEL_RESIZE_THRESHOLD:
                    # Resize paralelo: cv2.resize libera o GIL → threads realmente
                    # rodam em paralelo, reduzindo ~4x o tempo com 4 workers.
                    args = [(masks_binary[i], target_w, target_h) for i in range(n_raw_masks)]
                    for i, result in enumerate(self._resize_pool.map(_resize_mask, args)):
                        resized[i] = result
                else:
                    for i in range(n_raw_masks):
                        resized[i] = cv2.resize(
                            masks_binary[i], (target_w, target_h),
                            interpolation=cv2.INTER_NEAREST
                        )
                masks_binary = resized
                logger.debug(f"[analyze] Resize necessario: ({mask_h},{mask_w}) -> ({target_h},{target_w})")
            t_resize_ms = (time.perf_counter() - t_resize_start) * 1000

            t_area_start = time.perf_counter()
            areas = masks_binary.reshape(n_raw_masks, -1).sum(axis=1)  # (N,)
            t_area_ms = (time.perf_counter() - t_area_start) * 1000
        else:
            # --- Caminho SEM anotacao: downsample 4x (112M -> 7M elementos) ---
            ds = 4
            small_data = masks_data[:, ::ds, ::ds]
            masks_binary_small = (small_data > 0.5).astype(np.uint8)
            t_bin_ms = (time.perf_counter() - t_bin_start) * 1000

            t_resize_ms = 0.0
            needs_resize = False

            t_area_start = time.perf_counter()
            areas = masks_binary_small.reshape(n_raw_masks, -1).sum(axis=1) * (ds * ds)
            t_area_ms = (time.perf_counter() - t_area_start) * 1000

            masks_binary = None  # Nao precisamos do array full-res

        # --- Filtrar por area minima ---
        valid_mask = areas >= self.min_area
        valid_indices = np.where(valid_mask)[0]
        skipped_small = int(n_raw_masks - len(valid_indices))

        if len(valid_indices) == 0:
            t_total = (time.perf_counter() - t_analyze_start) * 1000
            logger.debug(f"[analyze] Todas mascaras abaixo de min_area ({t_total:.1f}ms)")
            empty_result = {
                'total_pellets': 0, 'media': 0.0, 'pellets': [],
                'range_counts': {r: 0 for r in RANGE_ORDER},
                'range_relations': {r: 0.0 for r in RANGE_ORDER},
                'annotated_frame': None
            }
            return empty_result

        valid_areas = areas[valid_indices].astype(np.float32)  # (M,)
        valid_masks = masks_binary[valid_indices] if masks_binary is not None else None

        # --- Diametro vetorizado ---
        t_diam_start = time.perf_counter()
        diameters_px = 2.0 * np.sqrt(valid_areas / np.pi)
        diameters_mm = diameters_px * self.scale
        t_diam_ms = (time.perf_counter() - t_diam_start) * 1000

        # --- Centroide (apenas quando frame e fornecido para anotacao) ---
        t_centroid_start = time.perf_counter()

        if frame is not None:
            # Downsampling 4x: reduz volume de dados de ~112M para ~7M elementos
            ds = 4
            small_masks = valid_masks[:, ::ds, ::ds].astype(np.float32)
            small_h, small_w = small_masks.shape[1], small_masks.shape[2]

            col_sums = small_masks.sum(axis=1)  # (M, small_W)
            row_sums = small_masks.sum(axis=2)  # (M, small_H)

            small_areas = small_masks.reshape(len(valid_indices), -1).sum(axis=1)
            small_areas = np.maximum(small_areas, 1.0)  # evitar divisao por zero

            x_coords = np.arange(small_w, dtype=np.float32) * ds + ds * 0.5
            y_coords = np.arange(small_h, dtype=np.float32) * ds + ds * 0.5

            cx = (col_sums @ x_coords) / small_areas
            cy = (row_sums @ y_coords) / small_areas
        else:
            # Sem anotacao: centroides nao sao necessarios
            n_valid = len(valid_indices)
            cx = np.zeros(n_valid, dtype=np.float32)
            cy = np.zeros(n_valid, dtype=np.float32)

        t_centroid_ms = (time.perf_counter() - t_centroid_start) * 1000

        # --- Classificacao vetorizada via np.searchsorted ---
        t_classify_start = time.perf_counter()
        range_indices = np.searchsorted(self._boundaries, diameters_mm, side='right')

        # Converter arrays numpy para listas de dicts
        cx_int = cx.astype(np.int32)
        cy_int = cy.astype(np.int32)
        areas_int = valid_areas.astype(np.int32)
        scale_sq = self.scale ** 2

        pellets = []
        for i in range(len(valid_indices)):
            pellets.append({
                'center': (int(cx_int[i]), int(cy_int[i])),
                'area_pixels': int(areas_int[i]),
                'area_mm2': float(valid_areas[i]) * scale_sq,
                'diameter_px': float(diameters_px[i]),
                'diameter_mm': float(diameters_mm[i]),
                'range': RANGE_ORDER[int(range_indices[i])],
            })
        t_classify_ms = (time.perf_counter() - t_classify_start) * 1000

        t_loop_ms = (time.perf_counter() - t_loop_start) * 1000

        total_pellets = len(pellets)
        media = float(np.mean(diameters_mm)) if total_pellets > 0 else 0.0

        # Contagem por faixa (vetorizada)
        range_counts = {r: 0 for r in RANGE_ORDER}
        unique_vals, counts = np.unique(range_indices, return_counts=True)
        for idx_val, count in zip(unique_vals, counts):
            range_counts[RANGE_ORDER[int(idx_val)]] = int(count)

        # Proporcoes
        range_relations = {}
        for r in RANGE_ORDER:
            range_relations[r] = range_counts[r] / total_pellets if total_pellets > 0 else 0.0

        # --- Anotacao do frame (otimizada) ---
        t_annotate_start = time.perf_counter()
        annotated_frame = None
        if frame is not None:
            annotated_frame = self._annotate_frame_batch(frame, pellets, valid_masks)
        t_annotate_ms = (time.perf_counter() - t_annotate_start) * 1000

        t_analyze_total_ms = (time.perf_counter() - t_analyze_start) * 1000

        # Log detalhado
        logger.debug(
            f"[analyze] total={t_analyze_total_ms:.1f}ms | "
            f"gpu_cpu={cpu_transfer_ms:.2f}ms | batch={t_loop_ms:.1f}ms "
            f"(bin={t_bin_ms:.1f}ms, resize={t_resize_ms:.1f}ms, "
            f"area={t_area_ms:.1f}ms, diam={t_diam_ms:.1f}ms, "
            f"centroid={t_centroid_ms:.1f}ms, classify={t_classify_ms:.1f}ms) | "
            f"annotate={t_annotate_ms:.1f}ms | "
            f"masks_raw={n_raw_masks} | pellets={total_pellets} | "
            f"skipped_small={skipped_small} | needs_resize={needs_resize} | "
            f"media={media:.2f}mm"
        )

        if t_analyze_total_ms > 100:
            logger.warning(
                f"[analyze] LENTO: {t_analyze_total_ms:.1f}ms total | "
                f"gpu_cpu={cpu_transfer_ms:.2f}ms | batch={t_loop_ms:.1f}ms | "
                f"annotate={t_annotate_ms:.1f}ms | masks={n_raw_masks} | "
                f"resize={'SIM' if needs_resize else 'NAO'}"
            )

        return {
            'total_pellets': total_pellets,
            'media': media,
            'pellets': pellets,
            'range_counts': range_counts,
            'range_relations': range_relations,
            'annotated_frame': annotated_frame
        }

    def _annotate_frame_batch(self, frame, pellets, masks):
        """
        Anotacao otimizada: colore mascaras em batch e desenha contornos.
        Evita overlay[mask_bool] = color em loop Python.

        Args:
            frame: Frame original (sera copiado internamente)
            pellets: Lista de dicts com info das pelotas
            masks: Array (M, H, W) uint8 com mascaras binarias
        """
        n = len(pellets)
        if n == 0:
            return frame.copy()

        result_frame = frame.copy()

        # Cores deterministicas
        np.random.seed(42)
        colors = np.random.randint(50, 255, size=(n, 3), dtype=np.uint8)

        # --- Colorir mascaras em batch ---
        # Encontrar cobertura e indice da mascara por pixel usando argmax
        # Para pixels sem cobertura, argmax retorna 0, mas usamos any_coverage para filtrar
        any_coverage = masks.max(axis=0).astype(bool)  # (H, W)
        mask_indices = masks.argmax(axis=0)  # (H, W) - indice da primeira mascara ativa

        # Mapear indices para cores: (H, W) -> (H, W, 3)
        color_overlay = colors[mask_indices]  # fancy indexing broadcast

        # Blend apenas nos pixels cobertos por mascaras
        alpha = 0.4
        covered = any_coverage[:, :, np.newaxis]  # (H, W, 1)
        blended = np.where(
            covered,
            (alpha * color_overlay.astype(np.float32) +
             (1 - alpha) * result_frame.astype(np.float32)).astype(np.uint8),
            result_frame
        )
        result_frame = blended

        # --- Contornos vetorizados via deteccao de bordas no label map ---
        # Em vez de cv2.findContours por mascara (N chamadas OpenCV lentas),
        # detectamos bordas comparando labels de pixels vizinhos: O(H*W) em vez de O(N*H*W)
        h, w = result_frame.shape[:2]
        label_map = np.where(any_coverage, mask_indices.astype(np.int16) + 1, np.int16(0))

        # Bordas: pixels onde vizinhos tem labels diferentes (4-connected)
        diff_v = label_map[:-1, :] != label_map[1:, :]
        diff_h = label_map[:, :-1] != label_map[:, 1:]

        edge_map = np.zeros((h, w), dtype=np.uint8)
        edge_map[:-1, :] |= diff_v
        edge_map[1:, :] |= diff_v
        edge_map[:, :-1] |= diff_h
        edge_map[:, 1:] |= diff_h

        # Dilatar para espessura ~2px (equivalente ao thickness=2 original)
        edge_map = cv2.dilate(edge_map, np.ones((3, 3), np.uint8))
        result_frame[edge_map > 0] = (0, 255, 0)

        # --- Labels de diametro (outline em vez de getTextSize+rectangle) ---
        for idx in range(n):
            pellet = pellets[idx]
            px, py = pellet['center']
            text = f"{pellet['diameter_mm']:.1f}mm"
            pos = (px - 30, py - 15)
            cv2.putText(result_frame, text, pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
            cv2.putText(result_frame, text, pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Info geral
        info_text = f"Pelotas: {n}"
        cv2.rectangle(result_frame, (5, 5), (220, 35), (0, 0, 0), -1)
        cv2.putText(result_frame, info_text, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return result_frame
