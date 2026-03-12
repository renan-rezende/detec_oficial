"""
Visualização de histórico temporal
"""
import customtkinter as ctk
import logging
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


class HistoryViewWindow(ctk.CTkToplevel):
    """Janela de visualização de histórico"""

    def __init__(self, parent, camera_manager):
        super().__init__(parent)

        self.camera_manager = camera_manager

        # Configurar janela
        self.title("Histórico - Tamanho Médio das Pelotas")
        self.geometry("1000x600")

        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=20, pady=15)

        title = ctk.CTkLabel(header_frame, text="Histórico Temporal",
                            font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(side="left", padx=10)

        # Botões
        btn_frame = ctk.CTkFrame(header_frame)
        btn_frame.pack(side="right", padx=10)

        refresh_btn = ctk.CTkButton(btn_frame, text="🔄 Atualizar", width=120,
                                   command=self.refresh_data)
        refresh_btn.pack(side="left", padx=5)

        close_btn = ctk.CTkButton(btn_frame, text="Fechar", width=100,
                                 command=self.destroy,
                                 fg_color="gray", hover_color="darkgray")
        close_btn.pack(side="left", padx=5)

        # Filtro de câmera
        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(filter_frame, text="Câmera:", font=ctk.CTkFont(size=12)).pack(side="left", padx=10)

        self.camera_filter = ctk.CTkOptionMenu(filter_frame, values=["Todas"],
                                              command=self.on_camera_changed)
        self.camera_filter.pack(side="left", padx=5)

        # Container do gráfico
        graph_frame = ctk.CTkFrame(self)
        graph_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Criar gráfico matplotlib
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

        # Carregar dados
        self.refresh_data()

        # Auto-refresh
        self.after(HISTORY_UPDATE_INTERVAL, self.auto_refresh)

        logger.info("Janela de histórico aberta")

    def refresh_data(self):
        """Atualiza dados lendo TODOS os CSVs da pasta data/"""
        try:
            # Ler TODOS os CSVs da pasta data/
            csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))

            if not csv_files:
                self.show_empty_message()
                return

            # Combinar todos os CSVs em um único DataFrame
            dfs = []
            for csv_file in csv_files:
                try:
                    df_temp = pd.read_csv(csv_file)
                    if not df_temp.empty:
                        dfs.append(df_temp)
                except Exception as e:
                    logger.warning(f"Erro ao ler {csv_file}: {e}")

            if not dfs:
                self.show_empty_message()
                return

            # Concatenar todos os DataFrames
            df = pd.concat(dfs, ignore_index=True)

            if df.empty:
                self.show_empty_message()
                return

            # Atualizar opções de câmera
            cameras = ["Todas"] + sorted(df['camera_name'].unique().tolist())
            self.camera_filter.configure(values=cameras)

            # Plotar
            self.plot_history(df)

        except Exception as e:
            logger.error(f"Erro ao carregar histórico: {e}")
            self.show_error_message(str(e))

    def on_camera_changed(self, camera_name):
        """Callback quando câmera é alterada"""
        self.refresh_data()

    def plot_history(self, df):
        """
        Plota gráfico de histórico

        Args:
            df: DataFrame com histórico
        """
        # Limpar gráfico
        self.ax.clear()

        # Filtrar por câmera se necessário
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

        # Agrupar por câmera e plotar
        cameras = df['camera_name'].unique()

        for camera in cameras:
            df_camera = df[df['camera_name'] == camera]

            # Plotar linha
            self.ax.plot(df_camera['Data'], df_camera['media'],
                       marker='o', markersize=4, linewidth=2,
                       label=camera, alpha=0.8)

        # Configurar eixos
        self.ax.set_xlabel('Tempo', color='white', fontsize=12, fontweight='bold')
        self.ax.set_ylabel('Tamanho Médio (mm)', color='white', fontsize=12, fontweight='bold')
        self.ax.set_title('Evolução Temporal do Tamanho Médio das Pelotas',
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

        # Redesenhar
        self.canvas.draw()

    def show_empty_message(self):
        """Mostra mensagem de dados vazios"""
        self.ax.clear()
        self.ax.text(0.5, 0.5, 'Nenhum dado disponível',
                    ha='center', va='center', fontsize=16, color='white',
                    transform=self.ax.transAxes)
        self.ax.axis('off')
        self.canvas.draw()

    def show_error_message(self, error):
        """Mostra mensagem de erro"""
        self.ax.clear()
        self.ax.text(0.5, 0.5, f'Erro ao carregar dados:\n{error}',
                    ha='center', va='center', fontsize=14, color='red',
                    transform=self.ax.transAxes)
        self.ax.axis('off')
        self.canvas.draw()

    def auto_refresh(self):
        """Auto-refresh periódico"""
        if self.winfo_exists():
            self.refresh_data()
            self.after(HISTORY_UPDATE_INTERVAL, self.auto_refresh)
