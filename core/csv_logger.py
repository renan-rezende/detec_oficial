"""
Logger para gravacao de deteccoes em CSV.
Escrita sincrona com buffer: log() acumula linhas em memoria e grava em batch
a cada 0.5s (uma abertura de arquivo por lote em vez de uma por linha).
Nao usa threads — projetado para rodar dentro de um processo dedicado
(Pipeline worker) onde nao ha contencao de GIL.
"""
import csv
import os
import logging
import time
import pandas as pd
from datetime import datetime
from config import CSV_PATH, CSV_COLUMNS, DATA_DIR, RANGE_ORDER


logger = logging.getLogger('PelletDetector.csv_logger')

# Intervalo maximo entre flushes (segundos)
_FLUSH_INTERVAL = 0.5


class CSVLogger:
    """Gerencia gravacao de estatisticas em CSV com buffer em memoria."""

    def __init__(self, csv_path=CSV_PATH):
        self.csv_path = csv_path
        self._buffer = []
        self._last_flush = time.monotonic()

        # Criar diretorio se nao existir
        os.makedirs(DATA_DIR, exist_ok=True)

        # Criar CSV com cabecalho se nao existir
        if not os.path.exists(csv_path):
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(CSV_COLUMNS)
            logger.info(f"CSV criado: {csv_path}")
        else:
            logger.info(f"CSV existente encontrado: {csv_path}")

    # =========================================================================
    #  ESCRITA COM BUFFER
    # =========================================================================

    def log(self, camera_name, analysis_result):
        """
        Acumula um registro no buffer. Grava em disco automaticamente
        quando o intervalo de flush e atingido.
        """
        try:
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                camera_name,
                analysis_result['total_pellets'],
                round(analysis_result['media'], 2),
            ]
            row.extend(
                round(analysis_result['range_relations'][r], 4) for r in RANGE_ORDER
            )
            self._buffer.append(row)

            # Auto-flush baseado em tempo
            now = time.monotonic()
            if (now - self._last_flush) >= _FLUSH_INTERVAL:
                self.flush()

        except Exception as e:
            logger.error(f"Erro ao enfileirar CSV: {e}")

    def flush(self):
        """Grava todas as linhas acumuladas no buffer de uma so vez."""
        if not self._buffer:
            self._last_flush = time.monotonic()
            return
        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(self._buffer)
            logger.debug(f"Batch gravado: {len(self._buffer)} linha(s)")
        except Exception as e:
            logger.error(f"Erro no flush CSV: {e}")
        finally:
            self._buffer.clear()
            self._last_flush = time.monotonic()

    # =========================================================================
    #  LEITURA / MANUTENCAO
    # =========================================================================

    def read_csv(self):
        """Le o CSV completo (sincrono, uso esporadico)."""
        try:
            return pd.read_csv(self.csv_path) if os.path.exists(self.csv_path) else pd.DataFrame(columns=CSV_COLUMNS)
        except Exception as e:
            logger.error(f"Erro ao ler CSV: {e}")
            return pd.DataFrame(columns=CSV_COLUMNS)

    def get_history_for_camera(self, camera_name, limit=None):
        """Retorna historico de uma camera especifica."""
        df = self.read_csv()
        if df.empty:
            return df
        df_camera = df[df['camera_name'] == camera_name]
        if limit is not None:
            df_camera = df_camera.tail(limit)
        return df_camera

    def get_latest_stats(self, camera_name):
        """Retorna ultimo registro de uma camera, ou None."""
        df = self.get_history_for_camera(camera_name, limit=1)
        return None if df.empty else df.iloc[-1].to_dict()

    def clear(self):
        """
        Limpa todo o conteudo do CSV (mantem cabecalho).
        Descarta linhas pendentes no buffer antes de limpar o arquivo.
        """
        discarded = len(self._buffer)
        self._buffer.clear()
        if discarded:
            logger.debug(f"Clear: {discarded} linha(s) descartada(s) do buffer")

        try:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(CSV_COLUMNS)
            logger.info("CSV limpo")
        except Exception as e:
            logger.error(f"Erro ao limpar CSV: {e}")
