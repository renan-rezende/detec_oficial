"""
Analisador de pelotas - processa resultados do YOLO e classifica pelotas
Versao otimizada: operacoes vetorizadas em batch (numpy) em vez de loop Python por mascara.
"""
import cv2
import numpy as np
import logging
import time
from config import GRANULOMETRIC_RANGES, RANGE_ORDER


logger = logging.getLogger('PelletDetector.analyzer')


class PelletAnalyzer:
    """Analisa resultados de segmentacao e classifica pelotas"""

    def __init__(self, scale_mm_per_pixel, min_area=50):
        self.scale = scale_mm_per_pixel
        self.min_area = min_area
        self.ranges = GRANULOMETRIC_RANGES

        logger.info(f"Analisador inicializado")
        logger.info(f"  Escala: {scale_mm_per_pixel} mm/pixel")
        logger.info(f"  Area minima: {min_area} pixels")

    def classify_pellet(self, diameter_mm):
        for range_name in RANGE_ORDER:
            min_val, max_val = self.ranges[range_name]
            if min_val <= diameter_mm < max_val:
                return range_name
        return 'range_above_19'

    def analyze(self, result, frame=None):
        """
        Analisa resultado do YOLO extraindo informacoes de cada pelota individual.
        Versao otimizada com operacoes vetorizadas em batch.

        Args:
            result: Objeto ultralytics Results (saida direta do modelo)
            frame: Frame original (opcional, para anotacao)

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

        # Binarizar todas as mascaras de uma vez
        t_bin_start = time.perf_counter()
        masks_binary = (masks_data > 0.5).astype(np.uint8)  # (N, H, W)
        t_bin_ms = (time.perf_counter() - t_bin_start) * 1000

        # Resize apenas se resolucao da mascara difere do frame original
        # Com retina_masks=True, as mascaras ja estao na resolucao original -> pula resize
        t_resize_start = time.perf_counter()
        needs_resize = (mask_h != target_h or mask_w != target_w)
        if needs_resize:
            resized = np.empty((n_raw_masks, target_h, target_w), dtype=np.uint8)
            for i in range(n_raw_masks):
                resized[i] = cv2.resize(
                    masks_binary[i], (target_w, target_h),
                    interpolation=cv2.INTER_NEAREST
                )
            masks_binary = resized
            logger.debug(f"[analyze] Resize necessario: ({mask_h},{mask_w}) -> ({target_h},{target_w})")
        t_resize_ms = (time.perf_counter() - t_resize_start) * 1000

        # --- Area vetorizada: soma de todos os pixels de cada mascara de uma vez ---
        t_area_start = time.perf_counter()
        # reshape (N, H*W) para sum mais eficiente em memoria contigua
        areas = masks_binary.reshape(n_raw_masks, -1).sum(axis=1)  # (N,)
        t_area_ms = (time.perf_counter() - t_area_start) * 1000

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
                'annotated_frame': frame.copy() if frame is not None else None
            }
            return empty_result

        valid_masks = masks_binary[valid_indices]  # (M, H, W)
        valid_areas = areas[valid_indices].astype(np.float32)  # (M,)

        # --- Diametro vetorizado ---
        t_diam_start = time.perf_counter()
        diameters_px = 2.0 * np.sqrt(valid_areas / np.pi)
        diameters_mm = diameters_px * self.scale
        t_diam_ms = (time.perf_counter() - t_diam_start) * 1000

        # --- Centroide vetorizado via projecao matricial ---
        # Em vez de np.where() por mascara (lento), usamos:
        #   col_sums = sum across height -> (M, W), depois dot com x_coords -> cx
        #   row_sums = sum across width  -> (M, H), depois dot com y_coords -> cy
        t_centroid_start = time.perf_counter()

        col_sums = valid_masks.sum(axis=1, dtype=np.float32)  # (M, W)
        row_sums = valid_masks.sum(axis=2, dtype=np.float32)  # (M, H)

        x_coords = np.arange(target_w, dtype=np.float32)  # (W,)
        y_coords = np.arange(target_h, dtype=np.float32)  # (H,)

        # (M, W) @ (W,) -> (M,) / (M,) -> (M,)
        cx = (col_sums @ x_coords) / valid_areas
        cy = (row_sums @ y_coords) / valid_areas

        t_centroid_ms = (time.perf_counter() - t_centroid_start) * 1000

        # --- Classificar e montar lista de pellets ---
        t_classify_start = time.perf_counter()
        pellets = []
        for i in range(len(valid_indices)):
            range_name = self.classify_pellet(float(diameters_mm[i]))
            pellets.append({
                'center': (int(cx[i]), int(cy[i])),
                'area_pixels': int(valid_areas[i]),
                'area_mm2': float(valid_areas[i]) * (self.scale ** 2),
                'diameter_px': float(diameters_px[i]),
                'diameter_mm': float(diameters_mm[i]),
                'range': range_name,
            })
        t_classify_ms = (time.perf_counter() - t_classify_start) * 1000

        t_loop_ms = (time.perf_counter() - t_loop_start) * 1000

        total_pellets = len(pellets)
        media = float(np.mean(diameters_mm)) if total_pellets > 0 else 0.0

        # Contagem por faixa
        range_counts = {r: 0 for r in RANGE_ORDER}
        for p in pellets:
            range_counts[p['range']] += 1

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

        # --- Contornos e labels por pelota ---
        for idx in range(n):
            pellet = pellets[idx]

            # Contorno verde (findContours nao e vetorizavel)
            contours, _ = cv2.findContours(
                masks[idx], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for cnt in contours:
                cv2.drawContours(result_frame, [cnt], -1, (0, 255, 0), 2)

            # Label de diametro
            cx, cy = pellet['center']
            text = f"{pellet['diameter_mm']:.1f}mm"
            text_pos = (cx - 30, cy - 15)

            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(result_frame,
                         (text_pos[0] - 2, text_pos[1] - text_size[1] - 4),
                         (text_pos[0] + text_size[0] + 2, text_pos[1] + 4),
                         (0, 0, 0), -1)
            cv2.putText(result_frame, text, text_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Info geral
        info_text = f"Pelotas: {n}"
        cv2.rectangle(result_frame, (5, 5), (220, 35), (0, 0, 0), -1)
        cv2.putText(result_frame, info_text, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return result_frame
