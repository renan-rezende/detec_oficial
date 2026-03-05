"""
Lista de câmeras ativas
"""
import customtkinter as ctk
import logging
from tkinter import messagebox


logger = logging.getLogger('PelletDetector.camera_list')


class CameraListFrame(ctk.CTkFrame):
    """Frame de lista de câmeras"""

    def __init__(self, parent, camera_manager):
        super().__init__(parent)

        self.parent = parent
        self.camera_manager = camera_manager

        # Título
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=20, pady=20)

        title = ctk.CTkLabel(header_frame, text="Câmeras Ativas",
                            font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", padx=10)

        # Botões no header
        btn_frame = ctk.CTkFrame(header_frame)
        btn_frame.pack(side="right", padx=10)

        add_btn = ctk.CTkButton(btn_frame, text="+ Adicionar Câmera", width=180, height=35,
                               command=self.parent.show_camera_form,
                               font=ctk.CTkFont(size=13, weight="bold"))
        add_btn.pack(side="left", padx=5)

        history_btn = ctk.CTkButton(btn_frame, text="Histórico", width=120, height=35,
                                   command=self.parent.show_history_view,
                                   fg_color="gray", hover_color="darkgray")
        history_btn.pack(side="left", padx=5)

        # Lista scrollable
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scrollable_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Atualizar lista
        self.refresh_list()

        # Auto-refresh a cada 2 segundos
        self.after(2000, self.auto_refresh)

    def refresh_list(self):
        """Atualiza lista de câmeras"""
        # Limpar widgets existentes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Obter lista de câmeras
        cameras = self.camera_manager.list_cameras()

        if not cameras:
            # Nenhuma câmera
            empty_label = ctk.CTkLabel(self.scrollable_frame,
                                      text="Nenhuma câmera adicionada\n\nClique em 'Adicionar Câmera' para começar",
                                      font=ctk.CTkFont(size=16),
                                      text_color="gray")
            empty_label.pack(pady=100)
        else:
            # Mostrar câmeras
            for camera_id, config in cameras:
                self.create_camera_item(camera_id, config)

    def create_camera_item(self, camera_id, config):
        """
        Cria item da câmera na lista

        Args:
            camera_id: ID da câmera
            config: CameraConfig
        """
        # Frame do item
        item_frame = ctk.CTkFrame(self.scrollable_frame, height=80)
        item_frame.pack(fill="x", padx=10, pady=10)

        # Info da câmera
        info_frame = ctk.CTkFrame(item_frame)
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)

        # Nome
        name_label = ctk.CTkLabel(info_frame, text=config.name,
                                  font=ctk.CTkFont(size=18, weight="bold"))
        name_label.pack(anchor="w")

        # Detalhes
        details_text = f"Source: {config.source} | Device: {config.device} | Escala: {config.scale_mm_pixel} mm/px"
        details_label = ctk.CTkLabel(info_frame, text=details_text,
                                     font=ctk.CTkFont(size=12),
                                     text_color="gray")
        details_label.pack(anchor="w")

        # Status
        is_running = self.camera_manager.is_running(camera_id)
        status_text = "🟢 Ativo" if is_running else "🔴 Parado"
        status_color = "green" if is_running else "red"

        status_label = ctk.CTkLabel(info_frame, text=status_text,
                                   font=ctk.CTkFont(size=13),
                                   text_color=status_color)
        status_label.pack(anchor="w")

        # Botões
        btn_frame = ctk.CTkFrame(item_frame)
        btn_frame.pack(side="right", padx=15, pady=10)

        # Botão Visualizar
        if is_running:
            view_btn = ctk.CTkButton(btn_frame, text="Visualizar", width=120, height=35,
                                    command=lambda: self.view_camera(camera_id))
            view_btn.pack(pady=3)

        # Botão Parar
        stop_btn = ctk.CTkButton(btn_frame, text="Parar", width=120, height=35,
                                fg_color="red", hover_color="darkred",
                                command=lambda: self.stop_camera(camera_id))
        stop_btn.pack(pady=3)

    def view_camera(self, camera_id):
        """
        Abre visualização de uma câmera

        Args:
            camera_id: ID da câmera
        """
        logger.info(f"Abrindo visualização da câmera {camera_id}")
        self.parent.show_detection_view(camera_id)

    def stop_camera(self, camera_id):
        """
        Para uma câmera

        Args:
            camera_id: ID da câmera
        """
        config = self.camera_manager.cameras.get(camera_id)
        if config is None:
            return

        # Confirmar
        result = messagebox.askyesno("Confirmar",
                                     f"Deseja parar a câmera '{config.name}'?")

        if result:
            try:
                self.camera_manager.stop_camera(camera_id)
                logger.info(f"Câmera {camera_id} parada pelo usuário")
                messagebox.showinfo("Sucesso", f"Câmera '{config.name}' parada")
                self.refresh_list()
            except Exception as e:
                logger.error(f"Erro ao parar câmera: {e}")
                messagebox.showerror("Erro", f"Erro ao parar câmera:\n{str(e)}")

    def auto_refresh(self):
        """Auto-refresh periódico"""
        self.refresh_list()
        self.after(2000, self.auto_refresh)
