"""
Analisador de pelotas - processa resultados do YOLO e classifica pelotas
Versao otimizada: operacoes vetorizadas em batch (numpy) em vez de loop Python por mascara.
"""
import cv2
import numpy as np
import logging
import time
import os
from config import GRANULOMETRIC_RANGES, RANGE_ORDER


# =========================================================================
#  FUNCOES NUMPY — hot-paths de processamento pixel-a-pixel
# =========================================================================

def _compute_areas_from_masks(masks_data, n_masks, threshold=0.5):
    """
    Binariza mascaras e calcula area (contagem de pixels) via NumPy vetorizado.
    """
    return (masks_data > threshold).reshape(n_masks, -1).sum(axis=1).astype(np.int64)


def _compute_edge_map(any_coverage, mask_indices, h, w):
    """
    Calcula o mapa de bordas entre mascaras usando operacoes NumPy vetorizadas.
    Compara pixels vizinhos (horizontal e vertical) para detectar transicoes.
    """
    # Criar label_map: pixels cobertos recebem (indice + 1), nao cobertos recebem 0
    label_map = np.where(any_coverage, mask_indices + 1, 0).astype(np.int32)

    edge_map = np.zeros((h, w), dtype=np.uint8)

    # Diferencas horizontais (vizinho da direita)
    diff_h = label_map[:, :-1] != label_map[:, 1:]
    edge_map[:, :-1] |= diff_h.astype(np.uint8)
    edge_map[:, 1:] |= diff_h.astype(np.uint8)

    # Diferencas verticais (vizinho de baixo)
    diff_v = label_map[:-1, :] != label_map[1:, :]
    edge_map[:-1, :] |= diff_v.astype(np.uint8)
    edge_map[1:, :] |= diff_v.astype(np.uint8)

    return edge_map


logger = logging.getLogger('PelletDetector.analyzer')


class PelletAnalyzer:
    """Analisa resultados de segmentacao e classifica pelotas"""

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

        Estrategia de resolucao:
        - Quando frame e fornecido E mascaras sao grandes (>= 400px), opera a 1/4
          da resolucao (DS=4): reduz 16x o volume de dados sem perda visual.
        - Quando mascaras sao pequenas (YOLO native ~160px), usa resolucao original.
        - A anotacao faz upsample apenas do label map (muito mais barato que
          redimensionar 73 mascaras individuais).

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
            # --- Caminho COM anotacao ---
            # Determinar fator de downsample: opera a 1/4 quando mascaras sao grandes.
            # Mascaras >= 400px ja estao em alta resolucao (resize=NAO ou semelhante).
            # Mascaras pequenas (~160px, YOLO native) nao precisam de downsample.
            _DS = 4 if (mask_h >= 400 and mask_w >= 400) else 1

            work_data = masks_data[:, ::_DS, ::_DS] if _DS > 1 else masks_data

            # Binarizacao + contagem de area vetorizada
            areas_raw = _compute_areas_from_masks(work_data, n_raw_masks)
            # masks_binary ainda necessario para anotacao (centroide + overlay)
            masks_binary = (work_data > 0.5).astype(np.uint8)
            t_bin_ms = (time.perf_counter() - t_bin_start) * 1000

            t_resize_start = time.perf_counter()
            needs_resize = _DS > 1  # indica que usamos resolucao reduzida
            t_resize_ms = 0.0

            t_area_start = time.perf_counter()
            # Escalar contagem de pixels de volta para resolucao original
            areas = areas_raw.astype(np.float32) * (_DS * _DS)
            t_area_ms = (time.perf_counter() - t_area_start) * 1000
        else:
            # --- Caminho SEM anotacao: downsample 4x ---
            ds = 4
            small_data = masks_data[:, ::ds, ::ds]

            # Binarizacao + contagem de area vetorizada
            areas_raw = _compute_areas_from_masks(small_data, n_raw_masks)
            t_bin_ms = (time.perf_counter() - t_bin_start) * 1000

            t_resize_ms = 0.0
            needs_resize = False

            t_area_start = time.perf_counter()
            areas = areas_raw.astype(np.float32) * (ds * ds)
            t_area_ms = (time.perf_counter() - t_area_start) * 1000

            masks_binary = None  # Nao precisamos do array para anotacao

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

        # --- Centroide ---
        t_centroid_start = time.perf_counter()

        if frame is not None:
            # valid_masks esta no espaco reduzido (_DS x menor que o frame original).
            # Calculamos centroides nesse espaco e escalamos para coordenadas do frame.
            small_h_m, small_w_m = valid_masks.shape[1], valid_masks.shape[2]
            # Fator real de escala (pode nao ser inteiro se mask_h nao divide target_h)
            scale_y = target_h / small_h_m
            scale_x = target_w / small_w_m

            small_masks_float = valid_masks.astype(np.float32)
            col_sums = small_masks_float.sum(axis=1)  # (M, small_W)
            row_sums = small_masks_float.sum(axis=2)  # (M, small_H)

            small_areas_c = small_masks_float.reshape(len(valid_indices), -1).sum(axis=1)
            small_areas_c = np.maximum(small_areas_c, 1.0)

            # Coordenadas em pixels do frame original
            x_coords = np.arange(small_w_m, dtype=np.float32) * scale_x + scale_x * 0.5
            y_coords = np.arange(small_h_m, dtype=np.float32) * scale_y + scale_y * 0.5

            cx = (col_sums @ x_coords) / small_areas_c
            cy = (row_sums @ y_coords) / small_areas_c
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
        Anotacao otimizada: label map calculado na resolucao das mascaras
        (possivelmente 1/4 do frame) e upsampled para o frame — evita operacoes
        de max/argmax em arrays de 150MB.

        - cv2.addWeighted substitui blend float32 manual (SIMD nativo, sem alloc float).
        - Deteccao de bordas no espaco reduzido, upsample por INTER_NEAREST.

        Args:
            frame: Frame original (sera copiado internamente)
            pellets: Lista de dicts com info das pelotas
            masks: Array (M, H_m, W_m) uint8 — pode estar em resolucao reduzida
        """
        n = len(pellets)
        if n == 0:
            return frame.copy()

        result_frame = frame.copy()
        h, w = result_frame.shape[:2]
        mask_h_m, mask_w_m = masks.shape[1], masks.shape[2]

        # Cores deterministicas
        np.random.seed(42)
        colors = np.random.randint(50, 255, size=(n, 3), dtype=np.uint8)

        # --- Label map na resolucao das mascaras (muito menor que o frame) ---
        # max(axis=0) e argmax(axis=0): O(M * H_m * W_m) — 16x mais rapido que full-res
        any_cov_small = masks.max(axis=0).astype(bool)      # (H_m, W_m)
        idx_small = masks.argmax(axis=0).astype(np.int32)   # (H_m, W_m)

        # --- Upsample para resolucao do frame (se necessario) ---
        if mask_h_m != h or mask_w_m != w:
            any_coverage = cv2.resize(
                any_cov_small.view(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST
            ).astype(bool)
            mask_indices = cv2.resize(idx_small, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            any_coverage = any_cov_small
            mask_indices = idx_small

        # --- Colorir mascaras em batch ---
        color_overlay = colors[mask_indices]  # (H, W, 3) via fancy indexing

        # Alpha blend com cv2.addWeighted (uint8 SIMD, sem conversao float32)
        # Pixels nao cobertos: overlay == result_frame → blend resulta no valor original
        covered_3d = any_coverage[:, :, np.newaxis]  # (H, W, 1) broadcast para (H, W, 3)
        overlay = result_frame.copy()
        np.copyto(overlay, color_overlay, where=covered_3d)
        cv2.addWeighted(overlay, 0.4, result_frame, 0.6, 0, result_frame)

        # --- Contornos via deteccao de bordas (NumPy vetorizado) ---
        any_cov_contiguous = np.ascontiguousarray(any_coverage)
        midx_contiguous = np.ascontiguousarray(mask_indices.astype(np.int32))
        edge_map = _compute_edge_map(any_cov_contiguous, midx_contiguous, h, w)

        # Dilatar para espessura ~2px
        edge_map = cv2.dilate(edge_map, np.ones((3, 3), np.uint8))
        result_frame[edge_map > 0] = (0, 255, 0)

        # --- Labels de diametro ---
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
