"""
Logger para gravação de detecções em CSV.
Escrita assíncrona via fila: log() retorna imediatamente sem tocar o disco,
liberando a thread PostProc para o próximo frame.
Um único thread daemon drena a fila e grava em batch (uma abertura de arquivo
por lote em vez de uma por linha).
"""
import csv
import os
import logging
import queue
import threading
import pandas as pd
from datetime import datetime
from config import CSV_PATH, CSV_COLUMNS, DATA_DIR, RANGE_ORDER


logger = logging.getLogger('PelletDetector.csv_logger')

# Sentinela para encerrar o writer thread
_STOP = object()


class CSVLogger:
    """Gerencia gravação assíncrona de estatísticas em CSV."""

    def __init__(self, csv_path=CSV_PATH):
        self.csv_path = csv_path
        self._write_queue = queue.Queue()
        self._lock = threading.Lock()   # Protege operações de leitura/clear

        # Criar diretório se não existir
        os.makedirs(DATA_DIR, exist_ok=True)

        # Criar CSV com cabeçalho se não existir
        if not os.path.exists(csv_path):
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(CSV_COLUMNS)
            logger.info(f"CSV criado: {csv_path}")
        else:
            logger.info(f"CSV existente encontrado: {csv_path}")

        # Thread daemon que grava linhas acumuladas em batch
        self._writer_thread = threading.Thread(
            target=self._background_writer,
            daemon=True,
            name=f"CSVWriter-{os.path.basename(csv_path)}"
        )
        self._writer_thread.start()

    # =========================================================================
    #  ESCRITA ASSÍNCRONA
    # =========================================================================

    def _background_writer(self):
        """
        Drena a fila em batch: espera a primeira linha, depois coleta todas
        as que chegaram enquanto aguardava (burst draining).
        Uma abertura de arquivo por lote é muito mais eficiente que
        uma abertura por linha no Xeon E5-2603 v3.
        """
        while True:
            rows = []
            try:
                # Bloqueia até a primeira linha (ou sentinela de parada)
                item = self._write_queue.get(timeout=0.5)
                if item is _STOP:
                    break
                rows.append(item)

                # Coleta linhas adicionais sem bloquear (burst draining)
                while True:
                    try:
                        item = self._write_queue.get_nowait()
                        if item is _STOP:
                            self._flush_rows(rows)
                            return
                        rows.append(item)
                    except queue.Empty:
                        break

            except queue.Empty:
                continue

            self._flush_rows(rows)

    def _flush_rows(self, rows):
        """Grava uma lista de linhas de uma só vez (uma abertura de arquivo)."""
        if not rows:
            return
        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(rows)
            logger.debug(f"Batch gravado: {len(rows)} linha(s)")
        except Exception as e:
            logger.error(f"Erro no background writer: {e}")

    def log(self, camera_name, analysis_result):
        """
        Enfileira um registro para gravação assíncrona.
        Retorna imediatamente — não toca o disco.
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
            self._write_queue.put(row)
        except Exception as e:
            logger.error(f"Erro ao enfileirar CSV: {e}")

    # =========================================================================
    #  LEITURA / MANUTENÇÃO
    # =========================================================================

    def read_csv(self):
        """Lê o CSV completo (síncrono, uso esporádico)."""
        try:
            return pd.read_csv(self.csv_path) if os.path.exists(self.csv_path) else pd.DataFrame(columns=CSV_COLUMNS)
        except Exception as e:
            logger.error(f"Erro ao ler CSV: {e}")
            return pd.DataFrame(columns=CSV_COLUMNS)

    def get_history_for_camera(self, camera_name, limit=None):
        """Retorna histórico de uma câmera específica."""
        df = self.read_csv()
        if df.empty:
            return df
        df_camera = df[df['camera_name'] == camera_name]
        if limit is not None:
            df_camera = df_camera.tail(limit)
        return df_camera

    def get_latest_stats(self, camera_name):
        """Retorna último registro de uma câmera, ou None."""
        df = self.get_history_for_camera(camera_name, limit=1)
        return None if df.empty else df.iloc[-1].to_dict()

    def clear(self):
        """
        Limpa todo o conteúdo do CSV (mantém cabeçalho).
        Descarta escritas pendentes na fila antes de limpar o arquivo.
        """
        # Descartar escritas pendentes na fila
        discarded = 0
        while not self._write_queue.empty():
            try:
                self._write_queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break
        if discarded:
            logger.debug(f"Clear: {discarded} linha(s) descartada(s) da fila")

        with self._lock:
            try:
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(CSV_COLUMNS)
                logger.info("CSV limpo")
            except Exception as e:
                logger.error(f"Erro ao limpar CSV: {e}")
