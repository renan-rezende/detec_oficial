"""
Lista de câmeras ativas
"""
import customtkinter as ctk
import logging
from tkinter import messagebox


logger = logging.getLogger('PelletDetector.camera_list')


class EditCameraDialog(ctk.CTkToplevel):
    """Diálogo para editar configurações de uma câmera em tempo real"""

    def __init__(self, parent, camera_manager, camera_id, config):
        super().__init__(parent)

        self.camera_manager = camera_manager
        self.camera_id = camera_id
        self.config = config

        # Configurar janela
        self.title(f"Editar Câmera: {config.name}")
        self.geometry("450x450")
        self.resizable(False, False)

        # Centralizar na tela
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 450) // 2
        y = (self.winfo_screenheight() - 450) // 2
        self.geometry(f"+{x}+{y}")

        # Tornar modal
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        self.lift()

        # Frame principal
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Título
        title = ctk.CTkLabel(main_frame, text=f"Editando: {config.name}",
                            font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(pady=(0, 20))

        # Inferências por segundo
        rate_frame = ctk.CTkFrame(main_frame)
        rate_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(rate_frame, text="Inferências por Segundo:",
                    font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        rate_control = ctk.CTkFrame(rate_frame)
        rate_control.pack(fill="x", pady=5)

        self.rate_slider = ctk.CTkSlider(rate_control, from_=1, to=10, number_of_steps=9, width=250)
        self.rate_slider.set(config.detection_rate)
        self.rate_slider.pack(side="left", padx=(0, 10))

        self.rate_label = ctk.CTkLabel(rate_control, text=f"{int(config.detection_rate)} inf/s")
        self.rate_label.pack(side="left")

        self.rate_slider.configure(command=lambda v: self.rate_label.configure(text=f"{int(v)} inf/s"))

        # Nível de confiança
        conf_frame = ctk.CTkFrame(main_frame)
        conf_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(conf_frame, text="Nível de Confiança (%):",
                    font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        conf_control = ctk.CTkFrame(conf_frame)
        conf_control.pack(fill="x", pady=5)

        self.conf_slider = ctk.CTkSlider(conf_control, from_=0, to=100, number_of_steps=20, width=250)
        self.conf_slider.set(config.confidence * 100)
        self.conf_slider.pack(side="left", padx=(0, 10))

        self.conf_label = ctk.CTkLabel(conf_control, text=f"{int(config.confidence * 100)}%")
        self.conf_label.pack(side="left")

        self.conf_slider.configure(command=lambda v: self.conf_label.configure(text=f"{int(v)}%"))

        # Escala mm/pixel
        scale_frame = ctk.CTkFrame(main_frame)
        scale_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(scale_frame, text="Escala (mm/pixel):",
                    font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        self.scale_entry = ctk.CTkEntry(scale_frame, width=150)
        self.scale_entry.insert(0, str(config.scale_mm_pixel))
        self.scale_entry.pack(anchor="w", pady=5)

        # Status label
        self.status_label = ctk.CTkLabel(main_frame, text="", text_color="green")
        self.status_label.pack(pady=5)

        # Botões
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        apply_btn = ctk.CTkButton(btn_frame, text="Aplicar", width=150, height=40,
                                 command=self.apply_changes,
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 fg_color="#2d8f2d", hover_color="#1f6b1f")
        apply_btn.pack(side="left", padx=10)

        close_btn = ctk.CTkButton(btn_frame, text="Fechar", width=150, height=40,
                                  command=self.destroy,
                                  fg_color="#555555", hover_color="#333333")
        close_btn.pack(side="left", padx=10)

    def apply_changes(self):
        """Aplica as alterações sem fechar o diálogo"""
        try:
            # Validar escala
            scale = float(self.scale_entry.get())
            if scale <= 0:
                messagebox.showerror("Erro", "Escala deve ser maior que zero")
                return

            # Obter valores
            detection_rate = int(self.rate_slider.get())
            confidence = self.conf_slider.get() / 100.0

            # Aplicar alterações
            success = self.camera_manager.update_camera_config(
                self.camera_id,
                detection_rate=detection_rate,
                confidence=confidence,
                scale_mm_pixel=scale
            )

            if success:
                logger.info(f"Configurações da câmera {self.config.name} atualizadas")
                self.status_label.configure(text="Alterações aplicadas!", text_color="green")
                # Limpar mensagem após 2 segundos
                self.after(2000, lambda: self.status_label.configure(text=""))
            else:
                self.status_label.configure(text="Erro ao aplicar", text_color="red")

        except ValueError:
            messagebox.showerror("Erro", "Escala inválida (use número decimal)")
        except Exception as e:
            logger.error(f"Erro ao aplicar configurações: {e}")
            messagebox.showerror("Erro", f"Erro ao aplicar:\n{str(e)}")


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

        # Auto-refresh a cada 3 segundos para atualizar status das câmeras
        self.after(3000, self.auto_refresh)

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

        # Botão Editar
        if is_running:
            edit_btn = ctk.CTkButton(btn_frame, text="Editar", width=120, height=35,
                                    fg_color="#1f6aa5", hover_color="#144870",
                                    command=lambda: self.edit_camera(camera_id))
            edit_btn.pack(pady=3)

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

    def edit_camera(self, camera_id):
        """
        Abre diálogo de edição de uma câmera

        Args:
            camera_id: ID da câmera
        """
        config = self.camera_manager.cameras.get(camera_id)
        if config is None:
            messagebox.showerror("Erro", "Câmera não encontrada")
            return

        logger.info(f"Abrindo edição da câmera {camera_id}")
        EditCameraDialog(self, self.camera_manager, camera_id, config)

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
        """Auto-refresh periódico — atualiza status (Ativo/Parado) das câmeras"""
        if self.winfo_exists():
            self.refresh_list()
            self.after(3000, self.auto_refresh)