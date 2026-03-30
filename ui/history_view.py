"""
Visualizacao de historico temporal
Carregamento de dados via multiprocessing.Process para nao travar a UI.
"""
import customtkinter as ctk
import logging
import multiprocessing as mp
import queue as _queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
import pandas as pd
import os
import glob
from datetime import datetime
from config import HISTORY_UPDATE_INTERVAL, DATA_DIR


logger = logging.getLogger('PelletDetector.history_view')


def _load_history_data(data_dir, result_queue):
    """
    Funcao top-level para carregar CSVs em processo separado.
    Necessario ser top-level para multiprocessing no Windows (spawn).
    """
    try:
        csv_files = glob.glob(os.path.join(data_dir, '*.csv'))
        if not csv_files:
            result_queue.put(None)
            return

        dfs = []
        for csv_file in csv_files:
            try:
                df_temp = pd.read_csv(csv_file)
                if not df_temp.empty:
                    dfs.append(df_temp)
            except Exception:
                pass

        if not dfs:
            result_queue.put(None)
            return

        df = pd.concat(dfs, ignore_index=True)
        if df.empty:
            result_queue.put(None)
            return

        # Enviar DataFrame serializado para o processo principal
        result_queue.put(df)

    except Exception as e:
        result_queue.put(('error', str(e)))


class HistoryViewWindow(ctk.CTkToplevel):
    """Janela de visualizacao de historico"""

    def __init__(self, parent, camera_manager):
        super().__init__(parent)

        self.camera_manager = camera_manager

        # Configurar janela
        self.title("Historico - Tamanho Medio das Pelotas")
        self.geometry("1000x600")

        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=20, pady=15)

        title = ctk.CTkLabel(header_frame, text="Historico Temporal",
                            font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(side="left", padx=10)

        # Botoes
        btn_frame = ctk.CTkFrame(header_frame)
        btn_frame.pack(side="right", padx=10)

        refresh_btn = ctk.CTkButton(btn_frame, text="Atualizar", width=120,
                                   command=self.refresh_data)
        refresh_btn.pack(side="left", padx=5)

        close_btn = ctk.CTkButton(btn_frame, text="Fechar", width=100,
                                 command=self.destroy,
                                 fg_color="gray", hover_color="darkgray")
        close_btn.pack(side="left", padx=5)

        # Filtro de camera
        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(filter_frame, text="Camera:", font=ctk.CTkFont(size=12)).pack(side="left", padx=10)

        self.camera_filter = ctk.CTkOptionMenu(filter_frame, values=["Todas"],
                                              command=self.on_camera_changed)
        self.camera_filter.pack(side="left", padx=5)

        # Container do grafico
        graph_frame = ctk.CTkFrame(self)
        graph_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Criar grafico matplotlib
        self.fig = Figure(figsize=(12, 6), dpi=100, facecolor='#2b2b2b')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white', labelsize=10)
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True, padx=10, pady=10)

        self._refresh_running = False   # Guard contra refreshes concorrentes
        self._result_queue = None       # Fila para receber dados do processo

        # Carregar dados (em background para nao travar a abertura da janela)
        self.refresh_data()

        # Auto-refresh
        self.after(HISTORY_UPDATE_INTERVAL, self.auto_refresh)

        logger.info("Janela de historico aberta")

    def refresh_data(self):
        """
        Dispara leitura de CSVs em processo separado.
        Retorna imediatamente — a UI nao trava durante pd.read_csv().
        """
        if self._refresh_running:
            return
        self._refresh_running = True

        self._result_queue = mp.Queue()
        p = mp.Process(
            target=_load_history_data,
            args=(DATA_DIR, self._result_queue),
            daemon=True,
            name="HistoryRefresh"
        )
        p.start()

        # Iniciar polling da fila de resultado
        self.after(100, self._check_result)

    def _check_result(self):
        """Verifica se o processo de carregamento retornou dados."""
        if not self.winfo_exists():
            self._refresh_running = False
            return

        if self._result_queue is None:
            self._refresh_running = False
            return

        try:
            result = self._result_queue.get_nowait()

            if result is None:
                self.show_empty_message()
            elif isinstance(result, tuple) and result[0] == 'error':
                self.show_error_message(result[1])
            else:
                self._apply_data(result)

            self._refresh_running = False

        except _queue.Empty:
            # Ainda processando — verificar novamente em 100ms
            self.after(100, self._check_result)

    def _apply_data(self, df):
        """Atualiza widgets e redesenha grafico — chamado sempre na thread principal."""
        if not self.winfo_exists():
            return
        cameras = ["Todas"] + sorted(df['camera_name'].unique().tolist())
        self.camera_filter.configure(values=cameras)
        self.plot_history(df)

    def on_camera_changed(self, camera_name):
        """Callback quando camera e alterada"""
        self.refresh_data()

    def plot_history(self, df):
        """
        Plota grafico de historico

        Args:
            df: DataFrame com historico
        """
        # Limpar grafico
        self.ax.clear()

        # Filtrar por camera se necessario
        selected_camera = self.camera_filter.get()
        if selected_camera != "Todas":
            df = df[df['camera_name'] == selected_camera]

        if df.empty:
            self.show_empty_message()
            return

        # Converter coluna Data para datetime
        df['Data'] = pd.to_datetime(df['Data'])

        # Ordenar por data
        df = df.sort_values('Data')

        # Agrupar por camera e plotar
        cameras = df['camera_name'].unique()

        for camera in cameras:
            df_camera = df[df['camera_name'] == camera]

            # Plotar linha
            self.ax.plot(df_camera['Data'], df_camera['media'],
                       marker='o', markersize=4, linewidth=2,
                       label=camera, alpha=0.8)

        # Configurar eixos
        self.ax.set_xlabel('Tempo', color='white', fontsize=12, fontweight='bold')
        self.ax.set_ylabel('Tamanho Medio (mm)', color='white', fontsize=12, fontweight='bold')
        self.ax.set_title('Evolucao Temporal do Tamanho Medio das Pelotas',
                         color='white', fontsize=14, fontweight='bold', pad=20)

        # Formatar datas no eixo X — adapta ao span real dos dados
        time_span = df['Data'].max() - df['Data'].min()
        if time_span.total_seconds() < 86400:  # menos de 1 dia
            date_format = DateFormatter("%H:%M:%S")
        else:
            date_format = DateFormatter("%d/%m %H:%M")
        self.ax.xaxis.set_major_formatter(date_format)
        self.fig.autofmt_xdate()

        # Grid
        self.ax.grid(True, alpha=0.3, linestyle='--', color='gray')

        # Legenda
        if len(cameras) > 1:
            self.ax.legend(loc='best', facecolor='#2b2b2b', edgecolor='white',
                          labelcolor='white', fontsize=10)

        # Ajustar layout
        self.fig.tight_layout()

        # draw_idle() agenda o redraw no proximo evento idle do Tk (nao bloqueia)
        self.canvas.draw_idle()

    def show_empty_message(self):
        """Mostra mensagem de dados vazios"""
        self.ax.clear()
        self.ax.text(0.5, 0.5, 'Nenhum dado disponivel',
                    ha='center', va='center', fontsize=16, color='white',
                    transform=self.ax.transAxes)
        self.ax.axis('off')
        self.canvas.draw_idle()

    def show_error_message(self, error):
        """Mostra mensagem de erro"""
        self.ax.clear()
        self.ax.text(0.5, 0.5, f'Erro ao carregar dados:\n{error}',
                    ha='center', va='center', fontsize=14, color='red',
                    transform=self.ax.transAxes)
        self.ax.axis('off')
        self.canvas.draw_idle()

    def auto_refresh(self):
        """Auto-refresh periodico"""
        if self.winfo_exists():
            self.refresh_data()
            self.after(HISTORY_UPDATE_INTERVAL, self.auto_refresh)
