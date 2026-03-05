"""
Analisador de pelotas - processa máscaras e classifica pelotas
"""
import cv2
import numpy as np
import logging
from config import GRANULOMETRIC_RANGES, RANGE_ORDER


logger = logging.getLogger('PelletDetector.analyzer')


class PelletAnalyzer:
    """Analisa máscaras de segmentação e classifica pelotas"""

    def __init__(self, scale_mm_per_pixel, min_area=50):
        """
        Inicializa o analisador

        Args:
            scale_mm_per_pixel: Escala de conversão pixel -> mm
            min_area: Área mínima de contorno (pixels) para filtrar ruído
        """
        self.scale = scale_mm_per_pixel
        self.min_area = min_area
        self.ranges = GRANULOMETRIC_RANGES

        logger.info(f"Analisador inicializado")
        logger.info(f"  Escala: {scale_mm_per_pixel} mm/pixel")
        logger.info(f"  Área mínima: {min_area} pixels")

    def classify_pellet(self, diameter_mm):
        """
        Classifica uma pelota em uma faixa granulométrica

        Args:
            diameter_mm: Diâmetro da pelota em mm

        Returns:
            str: Nome da faixa (ex: 'range_9_12')
        """
        for range_name in RANGE_ORDER:
            min_val, max_val = self.ranges[range_name]
            if min_val <= diameter_mm < max_val:
                return range_name

        # Fallback (não deveria acontecer)
        return 'range_above_19'

    def analyze(self, mask, frame=None):
        """
        Analisa máscara e extrai informações das pelotas

        Args:
            mask: Máscara binária (0 ou 1, uint8)
            frame: Frame original (opcional, para anotação)

        Returns:
            dict: {
                'total_pellets': int,
                'media': float,  # Tamanho médio em mm
                'pellets': list[dict],  # Lista de pelotas detectadas
                'range_counts': dict,  # Contagem por faixa
                'range_relations': dict,  # Relações por faixa (0-1)
                'annotated_frame': np.ndarray  # Frame anotado (se fornecido)
            }
        """
        # Garantir que máscara é binária
        if mask.max() <= 1:
            mask = (mask * 255).astype(np.uint8)

        # Encontrar contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos pequenos (ruído)
        valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= self.min_area]

        logger.debug(f"Encontrados {len(contours)} contornos, {len(valid_contours)} válidos")

        # Analisar cada pelota usando ÁREA da máscara de segmentação
        pellets = []
        diameters_mm = []

        for contour in valid_contours:
            # Calcular área REAL da máscara (em pixels)
            area_pixels = cv2.contourArea(contour)

            # Calcular diâmetro equivalente baseado na área
            # Fórmula: area = π * r² → r = sqrt(area / π) → d = 2r
            diameter_px = 2 * np.sqrt(area_pixels / np.pi)

            # Converter para mm usando escala calibrada
            diameter_mm = diameter_px * self.scale

            # Área em mm²
            area_mm2 = area_pixels * (self.scale ** 2)

            # Centro do contorno (para label)
            M = cv2.moments(contour)
            if M['m00'] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
            else:
                cx, cy = contour[0][0]

            # Classificar em faixa granulométrica
            range_name = self.classify_pellet(diameter_mm)

            pellet_info = {
                'center': (cx, cy),
                'area_pixels': area_pixels,
                'area_mm2': area_mm2,
                'diameter_px': diameter_px,
                'diameter_mm': diameter_mm,
                'range': range_name,
                'contour': contour
            }

            pellets.append(pellet_info)
            diameters_mm.append(diameter_mm)

        # Calcular estatísticas
        total_pellets = len(pellets)

        if total_pellets > 0:
            media = np.mean(diameters_mm)
        else:
            media = 0.0

        # Contagem por faixa
        range_counts = {range_name: 0 for range_name in RANGE_ORDER}
        for pellet in pellets:
            range_counts[pellet['range']] += 1

        # Relações (proporções)
        range_relations = {}
        for range_name in RANGE_ORDER:
            if total_pellets > 0:
                range_relations[range_name] = range_counts[range_name] / total_pellets
            else:
                range_relations[range_name] = 0.0

        # Anotar frame com máscaras de segmentação (se fornecido)
        annotated_frame = None
        if frame is not None:
            annotated_frame = self.annotate_frame(frame.copy(), pellets, mask)

        result = {
            'total_pellets': total_pellets,
            'media': media,
            'pellets': pellets,
            'range_counts': range_counts,
            'range_relations': range_relations,
            'annotated_frame': annotated_frame
        }

        logger.debug(f"Análise: {total_pellets} pelotas, média {media:.2f}mm")

        return result

    def annotate_frame(self, frame, pellets, mask=None):
        """
        Desenha máscaras de segmentação coloridas no frame

        Args:
            frame: Frame BGR
            pellets: Lista de pelotas (do analyze())
            mask: Máscara original (opcional, para overlay)

        Returns:
            np.ndarray: Frame com máscaras segmentadas sobrepostas
        """
        # Criar overlay semi-transparente para as máscaras
        overlay = frame.copy()

        # Cores para as máscaras (semi-aleatórias mas visíveis)
        np.random.seed(42)  # Para cores consistentes
        colors = np.random.randint(50, 255, size=(len(pellets), 3), dtype=np.uint8)

        for idx, pellet in enumerate(pellets):
            contour = pellet['contour']
            diameter_mm = pellet['diameter_mm']
            center = pellet['center']

            # Desenhar máscara preenchida (semi-transparente)
            color = tuple(map(int, colors[idx]))
            cv2.drawContours(overlay, [contour], -1, color, -1)  # Preenchido

            # Contorno da máscara (mais visível)
            cv2.drawContours(frame, [contour], -1, (0, 255, 0), 2)

            # Texto com tamanho e área
            text = f"{diameter_mm:.1f}mm"
            text_pos = (center[0] - 30, center[1] - 15)

            # Fundo escuro para texto
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(frame,
                         (text_pos[0] - 2, text_pos[1] - text_size[1] - 4),
                         (text_pos[0] + text_size[0] + 2, text_pos[1] + 4),
                         (0, 0, 0), -1)

            # Texto em branco
            cv2.putText(frame, text, text_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Blend: frame original + máscaras semi-transparentes
        alpha = 0.4  # Transparência das máscaras
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        # Info geral no canto superior esquerdo
        info_text = f"Pelotas: {len(pellets)}"
        cv2.rectangle(frame, (5, 5), (220, 35), (0, 0, 0), -1)
        cv2.putText(frame, info_text, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return frame
