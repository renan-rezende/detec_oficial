"""
Logger para gravação de detecções em CSV
"""
import pandas as pd
import os
import logging
import threading
from datetime import datetime
from config import CSV_PATH, CSV_COLUMNS, DATA_DIR, RANGE_ORDER


logger = logging.getLogger('PelletDetector.csv_logger')


class CSVLogger:
    """Gerencia gravação de estatísticas em CSV"""

    def __init__(self, csv_path=CSV_PATH):
        """
        Inicializa o logger CSV

        Args:
            csv_path: Caminho para o arquivo CSV
        """
        self.csv_path = csv_path
        self.lock = threading.Lock()  # Lock para escrita thread-safe

        # Criar diretório se não existir
        os.makedirs(DATA_DIR, exist_ok=True)

        # Criar CSV com cabeçalho se não existir
        if not os.path.exists(csv_path):
            df = pd.DataFrame(columns=CSV_COLUMNS)
            df.to_csv(csv_path, index=False)
            logger.info(f"CSV criado: {csv_path}")
        else:
            logger.info(f"CSV existente encontrado: {csv_path}")

    def log(self, camera_name, analysis_result):
        """
        Registra resultado de análise no CSV

        Args:
            camera_name: Nome da câmera
            analysis_result: Resultado do PelletAnalyzer.analyze()
        """
        try:
            with self.lock:
                # Preparar dados
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                row_data = {
                    'Data': timestamp,
                    'camera_name': camera_name,
                    'total_pellets': analysis_result['total_pellets'],
                    'media': round(analysis_result['media'], 2)
                }

                # Adicionar relações das faixas
                for range_name in RANGE_ORDER:
                    row_data[range_name] = round(analysis_result['range_relations'][range_name], 4)

                # Criar DataFrame com uma linha
                df_new = pd.DataFrame([row_data])

                # Append no CSV
                df_new.to_csv(self.csv_path, mode='a', header=False, index=False)

                logger.debug(f"Registro salvo: {camera_name}, {row_data['total_pellets']} pelotas")

        except Exception as e:
            logger.error(f"Erro ao gravar CSV: {e}")

    def read_csv(self):
        """
        Lê o CSV completo

        Returns:
            pandas.DataFrame: Dados do CSV
        """
        try:
            if os.path.exists(self.csv_path):
                df = pd.read_csv(self.csv_path)
                return df
            else:
                return pd.DataFrame(columns=CSV_COLUMNS)
        except Exception as e:
            logger.error(f"Erro ao ler CSV: {e}")
            return pd.DataFrame(columns=CSV_COLUMNS)

    def get_history_for_camera(self, camera_name, limit=None):
        """
        Obtém histórico de uma câmera específica

        Args:
            camera_name: Nome da câmera
            limit: Número máximo de registros (None = todos)

        Returns:
            pandas.DataFrame: Histórico filtrado
        """
        df = self.read_csv()

        if df.empty:
            return df

        # Filtrar por câmera
        df_camera = df[df['camera_name'] == camera_name]

        # Aplicar limite
        if limit is not None:
            df_camera = df_camera.tail(limit)

        return df_camera

    def get_latest_stats(self, camera_name):
        """
        Obtém últimas estatísticas de uma câmera

        Args:
            camera_name: Nome da câmera

        Returns:
            dict or None: Último registro ou None se não existir
        """
        df = self.get_history_for_camera(camera_name, limit=1)

        if df.empty:
            return None

        return df.iloc[-1].to_dict()

    def clear(self):
        """Limpa todo o conteúdo do CSV (mantém cabeçalho)"""
        try:
            with self.lock:
                df = pd.DataFrame(columns=CSV_COLUMNS)
                df.to_csv(self.csv_path, index=False)
                logger.info("CSV limpo")
        except Exception as e:
            logger.error(f"Erro ao limpar CSV: {e}")
