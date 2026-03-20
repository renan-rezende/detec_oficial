"""
Lista de câmeras ativas
"""
import customtkinter as ctk
import logging
from tkinter import messagebox
from ui.roi_dialog import ROIDialog


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
        self.geometry("450x620")
        self.resizable(False, False)

        # Centralizar na tela
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 450) // 2
        y = (self.winfo_screenheight() - 620) // 2
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

        # Máximo de detecções por frame
        max_det_frame = ctk.CTkFrame(main_frame)
        max_det_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(max_det_frame, text="Máx. Detecções por Frame:",
                    font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        self.max_det_entry = ctk.CTkEntry(max_det_frame, width=150)
        self.max_det_entry.insert(0, str(getattr(config, 'max_det', 100)))
        self.max_det_entry.pack(anchor="w", pady=5)

        # Região de Interesse (ROI)
        roi_section = ctk.CTkFrame(main_frame)
        roi_section.pack(fill="x", pady=10)

        ctk.CTkLabel(roi_section, text="Região de Interesse (ROI):",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        roi_control = ctk.CTkFrame(roi_section)
        roi_control.pack(fill="x", pady=5)

        current_roi = getattr(config, 'roi', None)
        roi_text = f"ROI: ({current_roi[0]}, {current_roi[1]}) {current_roi[2]}x{current_roi[3]}" if current_roi else "Não definida (frame inteiro)"
        self.roi_status = ctk.CTkLabel(roi_control, text=roi_text)
        self.roi_status.pack(side="left", padx=(0, 10))

        ctk.CTkButton(roi_control, text="Definir ROI", width=110,
                       command=self._open_roi_dialog).pack(side="left", padx=3)

        ctk.CTkButton(roi_control, text="Limpar ROI", width=100,
                       command=self._clear_roi,
                       fg_color="gray", hover_color="darkgray").pack(side="left", padx=3)

        self._pending_roi = '_unchanged'  # Sentinela: não alterar ROI por padrão

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

    def _open_roi_dialog(self):
        """Abre diálogo de seleção de ROI usando frame da câmera ativa"""
        data = self.camera_manager.get_frame(self.camera_id, timeout=0.5)
        if data is not None:
            frame = data['frame']
        else:
            # Fallback: abrir source diretamente
            from ui.roi_dialog import grab_sample_frame
            frame = grab_sample_frame(self.config.source)

        if frame is None:
            messagebox.showerror("Erro", "Não foi possível capturar frame da câmera.")
            return

        current = getattr(self.config, 'roi', None)
        ROIDialog(self, frame, current_roi=current, on_apply=self._on_roi_applied)

    def _on_roi_applied(self, roi):
        """Callback quando ROI é definida ou limpa pelo diálogo"""
        self._pending_roi = roi
        if roi is not None:
            x, y, w, h = roi
            self.roi_status.configure(text=f"ROI: ({x}, {y}) {w}x{h}")
        else:
            self.roi_status.configure(text="Não definida (frame inteiro)")

    def _clear_roi(self):
        """Limpa ROI"""
        self._pending_roi = None
        self.roi_status.configure(text="Não definida (frame inteiro)")

    def apply_changes(self):
        """Aplica as alterações sem fechar o diálogo"""
        try:
            # Validar escala
            scale = float(self.scale_entry.get())
            if scale <= 0:
                messagebox.showerror("Erro", "Escala deve ser maior que zero")
                return

            # Validar max_det
            try:
                max_det = int(self.max_det_entry.get())
                if max_det <= 0:
                    messagebox.showerror("Erro", "Máx. detecções deve ser maior que zero")
                    return
            except ValueError:
                messagebox.showerror("Erro", "Máx. detecções inválido (use número inteiro)")
                return

            # Obter valores
            detection_rate = int(self.rate_slider.get())
            confidence = self.conf_slider.get() / 100.0

            # Aplicar alterações
            success = self.camera_manager.update_camera_config(
                self.camera_id,
                detection_rate=detection_rate,
                confidence=confidence,
                scale_mm_pixel=scale,
                max_det=max_det,
                roi=self._pending_roi
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

        # Referências aos labels de status para atualização sem reconstruir a lista
        self._status_labels = {}   # camera_id -> CTkLabel
        self._displayed_ids = set()  # IDs atualmente exibidos

        # Atualizar lista
        self.refresh_list()

        # Auto-refresh a cada 3 segundos para atualizar status das câmeras
        self.after(3000, self.auto_refresh)

    def refresh_list(self):
        """Reconstrói toda a lista de câmeras (scroll é resetado)."""
        self._status_labels.clear()
        self._displayed_ids.clear()

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if cameras := self.camera_manager.list_cameras():
            for camera_id, config in cameras:
                self.create_camera_item(camera_id, config)
                self._displayed_ids.add(camera_id)
        else:
            empty_label = ctk.CTkLabel(self.scrollable_frame,
                                      text="Nenhuma câmera adicionada\n\nClique em 'Adicionar Câmera' para começar",
                                      font=ctk.CTkFont(size=16),
                                      text_color="gray")
            empty_label.pack(pady=100)

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

        # Guardar referência para atualização sem reconstruir a lista
        self._status_labels[camera_id] = status_label

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
        """Auto-refresh periódico — atualiza apenas os status sem resetar o scroll."""
        if not self.winfo_exists():
            return

        current_ids = {cid for cid, _ in self.camera_manager.list_cameras()}

        if current_ids != self._displayed_ids:
            # Lista mudou (câmera adicionada ou removida) — reconstrói tudo
            self.refresh_list()
        else:
            # Só atualiza os labels de status — scroll não é alterado
            for camera_id, status_label in list(self._status_labels.items()):
                if not status_label.winfo_exists():
                    continue
                is_running = self.camera_manager.is_running(camera_id)
                status_label.configure(
                    text="🟢 Ativo" if is_running else "🔴 Parado",
                    text_color="green" if is_running else "red"
                )

        self.after(3000, self.auto_refresh)