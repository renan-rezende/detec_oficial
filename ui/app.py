"""
Aplicação principal com CustomTkinter
"""
import customtkinter as ctk
import logging
from core.camera_manager import CameraManager


logger = logging.getLogger('PelletDetector.app')


class PelletDetectorApp(ctk.CTk):
    """Aplicação principal"""

    def __init__(self):
        super().__init__()

        # Configurações da janela
        self.title("Pellet Detector - Sistema de Medição de Pelotas")
        self.geometry("1200x700")

        # Tema
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Inicializar componentes core
        # Cada câmera terá seu próprio CSV criado automaticamente
        self.camera_manager = CameraManager()

        # Container para telas
        self.current_frame = None

        # Mostrar tela inicial (lista de câmeras)
        self.show_camera_list()

        # Protocolo de fechamento
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        logger.info("Aplicação inicializada")

    def clear_frame(self):
        """Remove frame atual"""
        if self.current_frame is not None:
            self.current_frame.destroy()
            self.current_frame = None

    def show_camera_form(self):
        """Mostra tela de cadastro de câmera"""
        from ui.camera_form import CameraFormFrame

        self.clear_frame()
        self.current_frame = CameraFormFrame(self, self.camera_manager)
        self.current_frame.pack(fill="both", expand=True)

    def show_camera_list(self):
        """Mostra tela de lista de câmeras"""
        from ui.camera_list import CameraListFrame

        self.clear_frame()
        self.current_frame = CameraListFrame(self, self.camera_manager)
        self.current_frame.pack(fill="both", expand=True)

    def show_detection_view(self, camera_id):
        """
        Mostra tela de visualização de detecções

        Args:
            camera_id: ID da câmera
        """
        from ui.detection_view import DetectionViewFrame

        self.clear_frame()
        self.current_frame = DetectionViewFrame(self, self.camera_manager, camera_id)
        self.current_frame.pack(fill="both", expand=True)

    def show_history_view(self):
        """Mostra tela de histórico"""
        from ui.history_view import HistoryViewWindow

        # Abrir em nova janela
        HistoryViewWindow(self, self.camera_manager)

    def on_closing(self):
        """Callback ao fechar aplicação"""
        logger.info("Fechando aplicação...")

        # Parar todas as câmeras (libera VRAM de cada detector)
        self.camera_manager.stop_all()

        # Limpeza final do CUDA
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info("VRAM totalmente liberada")
        except Exception as e:
            logger.warning(f"Erro ao limpar CUDA: {e}")

        # Destruir janela
        self.destroy()

        logger.info("Aplicação fechada")


def run_app():
    """Função para iniciar a aplicação"""
    app = PelletDetectorApp()
    app.mainloop()
