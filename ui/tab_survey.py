from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QComboBox, QLineEdit, QMessageBox, QFileDialog, QFrame,
    QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from core.models import ProjectConfig, Expert
from core.excel_handler import export_all_experts_results
from core.project_db import ProjectDB
from ui.widgets.z_cell_widget import MatrixCellWidget


class TabSurvey(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ProjectConfig()
        self.row_labels = []
        self.col_labels = []
        self.cell_widgets = {}
        
        # Bộ nhớ lưu bài của các chuyên gia đã xác nhận Save
        self.saved_experts_data = {}
        self.project_db: ProjectDB = None
        self.current_expert: Expert = None
        self.is_authenticated = False

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # =====================================================================
        # 1. EXPERT LOGIN & AUTHENTICATION BAR
        # =====================================================================
        grp_auth = QGroupBox("1. Expert Authentication & Session")
        lay_auth = QHBoxLayout(grp_auth)

        lay_auth.addWidget(QLabel("Expert:"))
        self.cb_experts = QComboBox()
        self.cb_experts.setMinimumWidth(220)
        self.cb_experts.currentIndexChanged.connect(self.on_expert_selected_change)
        lay_auth.addWidget(self.cb_experts)

        self.txt_expert_free = QLineEdit()
        self.txt_expert_free.setPlaceholderText("Enter Expert Name...")
        self.txt_expert_free.setVisible(False)
        lay_auth.addWidget(self.txt_expert_free)

        # Ô nhập Mật khẩu
        self.lbl_pwd = QLabel("Password:")
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Enter password...")
        self.txt_password.setFixedWidth(130)
        lay_auth.addWidget(self.lbl_pwd)
        lay_auth.addWidget(self.txt_password)

        # Nút Đăng nhập / Mở khóa
        self.btn_login = QPushButton("🔑 Login & Unlock")
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b5ed7; }
        """)
        self.btn_login.clicked.connect(self.authenticate_expert)
        lay_auth.addWidget(self.btn_login)

        # Trạng thái đăng nhập & Đã lưu
        self.lbl_auth_status = QLabel("🔒 Locked")
        self.lbl_auth_status.setStyleSheet("font-weight: bold; color: #dc3545; font-size: 12px;")
        lay_auth.addWidget(self.lbl_auth_status)

        # Nút Lưu kết quả của chuyên gia hiện tại
        self.btn_save_expert = QPushButton("💾 Save Evaluation")
        self.btn_save_expert.setEnabled(False)
        self.btn_save_expert.setStyleSheet("""
            QPushButton {
                background-color: #198754; color: white; font-weight: bold; padding: 5px 15px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #157347; }
            QPushButton:disabled { background-color: #adb5bd; }
        """)
        self.btn_save_expert.clicked.connect(self.save_current_expert)
        lay_auth.addWidget(self.btn_save_expert)

        lay_auth.addStretch()

        self.lbl_model_badge = QLabel("DEMATEL")
        self.lbl_model_badge.setStyleSheet("font-weight: bold; color: #0d6efd; padding: 3px 8px; border: 1px solid #0d6efd; border-radius: 4px;")
        lay_auth.addWidget(self.lbl_model_badge)

        self.lbl_z_badge = QLabel("Z-Number: OFF")
        self.lbl_z_badge.setStyleSheet("font-weight: bold; color: #6f42c1; padding: 3px 8px; border: 1px solid #6f42c1; border-radius: 4px;")
        lay_auth.addWidget(self.lbl_z_badge)

        main_layout.addWidget(grp_auth)

        # =====================================================================
        # 2. KHUNG HƯỚNG DẪN ĐỘNG CHI TIẾT TỌA ĐỘ Ô
        # =====================================================================
        frame_guide = QFrame()
        frame_guide.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #0d6efd;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        lay_guide = QVBoxLayout(frame_guide)
        lay_guide.setSpacing(4)

        self.lbl_cell_coords = QLabel("📍 SELECTED COORDINATE: None")
        self.lbl_cell_coords.setStyleSheet("font-size: 13px; font-weight: bold; color: #0d6efd;")
        lay_guide.addWidget(self.lbl_cell_coords)

        self.lbl_dynamic_question = QLabel("👉 Click on any cell in the matrix below to see the detailed evaluation question.")
        self.lbl_dynamic_question.setStyleSheet("font-size: 15px; font-weight: bold; color: #212529;")
        self.lbl_dynamic_question.setWordWrap(True)
        lay_guide.addWidget(self.lbl_dynamic_question)

        main_layout.addWidget(frame_guide)

        # =====================================================================
        # 3. VÙNG TRUNG TÂM: CHIA ĐÔI (MA TRẬN ĐÁNH GIÁ VÀ BẢNG THAM CHIẾU)
        # =====================================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Bên trái (70%): Bảng ma trận khảo sát
        matrix_container = QWidget()
        lay_matrix = QVBoxLayout(matrix_container)
        lay_matrix.setContentsMargins(0, 0, 5, 0)
        
        lbl_mat_title = QLabel("Evaluation Matrix:")
        lbl_mat_title.setStyleSheet("font-weight: bold; color: #333;")
        lay_matrix.addWidget(lbl_mat_title)

        self.table_matrix = QTableWidget()
        self.table_matrix.cellClicked.connect(self.on_cell_clicked)
        lay_matrix.addWidget(self.table_matrix)
        splitter.addWidget(matrix_container)

        # Bên phải (30%): Bảng tham chiếu danh sách Factors & Thang đo Scales
        ref_container = QWidget()
        lay_ref = QVBoxLayout(ref_container)
        lay_ref.setContentsMargins(5, 0, 0, 0)
        lay_ref.setSpacing(6)

        lbl_ref_title = QLabel("📖 Reference Tables:")
        lbl_ref_title.setStyleSheet("font-weight: bold; color: #333;")
        lay_ref.addWidget(lbl_ref_title)

        # Bảng 1: Factors/Solutions Reference
        lay_ref.addWidget(QLabel("1. Items (Factors / Alternatives):"))
        self.table_ref_factors = QTableWidget()
        self.setup_mini_table(self.table_ref_factors)
        lay_ref.addWidget(self.table_ref_factors)

        # Bảng 2: Scale Definition Reference
        lay_ref.addWidget(QLabel("2. Linguistic Scales & Values:"))
        self.table_ref_scales = QTableWidget()
        self.setup_mini_table(self.table_ref_scales)
        lay_ref.addWidget(self.table_ref_scales)

        splitter.addWidget(ref_container)
        splitter.setSizes([750, 350])
        main_layout.addWidget(splitter)

        # =====================================================================
        # 4. THANH FOOTER: TIẾN ĐỘ & XUẤT TOÀN BỘ
        # =====================================================================
        lay_footer = QHBoxLayout()
        self.lbl_progress = QLabel("Experts completed: 0 / 0")
        self.lbl_progress.setStyleSheet("font-weight: bold; font-size: 13px; color: #212529;")
        lay_footer.addWidget(self.lbl_progress)

        lay_footer.addStretch()

        self.btn_export_all = QPushButton("📤 EXPORT ALL EXPERTS (2 Excel Files)")
        self.btn_export_all.setFixedHeight(40)
        self.btn_export_all.setStyleSheet("""
            QPushButton {
                background-color: #198754; color: white; font-weight: bold; font-size: 13px; border-radius: 5px; padding: 0 18px;
            }
            QPushButton:hover { background-color: #157347; }
        """)
        self.btn_export_all.clicked.connect(self.on_export_all_clicked)
        lay_footer.addWidget(self.btn_export_all)

        main_layout.addLayout(lay_footer)

    def setup_mini_table(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(24)

    # =========================================================================
    # KHỞI TẠO VÀ NẠP DỮ LIỆU CẤU HÌNH
    # =========================================================================
    def load_project(self, config: ProjectConfig, project_db: ProjectDB = None):
        self.config = config
        self.project_db = project_db
        self.saved_experts_data.clear()
        self.cell_widgets.clear()
        self.is_authenticated = False

        # Restore already persisted responses. The database identity is based on
        # respondent_id, never expert name, because names may legitimately repeat.
        if self.project_db:
            for row in self.project_db.get_all_responses():
                try:
                    payload = __import__("json").loads(row["response_json"])
                except Exception:
                    continue
                key = str(row["respondent_id"] or row["id"])
                self.saved_experts_data[key] = {
                    "code_matrix": payload.get("code_matrix", []),
                    "value_matrix": payload.get("value_matrix", []),
                    "expert_name": row.get("full_name") or key,
                    "respondent_id": key,
                    "answer_id": f"Ans_{int(row['display_index']):02d}",
                    "submitted_at": row.get("submitted_at", ""),
                    "source_project_id": row.get("source_project_id", ""),
                    "source_project_name": row.get("source_project_name", ""),
                }

        self.lbl_model_badge.setText(config.model_type)
        self.lbl_z_badge.setText(f"Z-Number: {'ON' if config.use_z_number else 'OFF'}")

        # Nạp Chuyên gia vào Dropdown
        self.cb_experts.blockSignals(True)
        self.cb_experts.clear()
        if config.expert_auth_mode == "Account":
            self.cb_experts.setVisible(True)
            self.txt_expert_free.setVisible(False)
            self.lbl_pwd.setVisible(True)
            self.txt_password.setVisible(True)
            self.btn_login.setVisible(True)

            for exp in config.experts:
                self.cb_experts.addItem(f"{exp.name} ({exp.username})", userData=exp)
        else:
            self.cb_experts.setVisible(False)
            self.txt_expert_free.setVisible(True)
            self.txt_expert_free.setText("Expert_01")
            self.lbl_pwd.setVisible(False)
            self.txt_password.setVisible(False)
            self.btn_login.setVisible(False)

        self.cb_experts.blockSignals(False)

        # Nạp các bảng tham chiếu Factors và Scales ở bên phải
        self.populate_reference_tables()

        # Dựng ma trận rỗng
        self.build_matrix()

        # Mặc định khóa ma trận cho đến khi đăng nhập
        if config.expert_auth_mode == "Account":
            self.lock_matrix(True)
        else:
            self.lock_matrix(False)

        self.update_progress_counter()

    def populate_reference_tables(self):
        """Đưa trực tiếp danh sách Factors và Scales vào 2 bảng bên phải."""
        # 1. Bảng Factors & Alternatives
        items = []
        for f in self.config.factors:
            items.append((f.code, f.name))
        for a in self.config.alternatives:
            items.append((a.code, a.name))

        self.table_ref_factors.setRowCount(len(items))
        self.table_ref_factors.setColumnCount(2)
        self.table_ref_factors.setHorizontalHeaderLabels(["Code", "Name"])
        for r, (code, name) in enumerate(items):
            self.table_ref_factors.setItem(r, 0, QTableWidgetItem(code))
            self.table_ref_factors.setItem(r, 1, QTableWidgetItem(name))

        # 2. Bảng Scales
        if self.config.scale_type == "Continuous":
            self.table_ref_scales.setRowCount(1)
            self.table_ref_scales.setColumnCount(2)
            self.table_ref_scales.setHorizontalHeaderLabels(["Type", "Range"])
            self.table_ref_scales.setItem(0, 0, QTableWidgetItem("Continuous"))
            self.table_ref_scales.setItem(0, 1, QTableWidgetItem(f"[{self.config.continuous_min}, {self.config.continuous_max}]"))
        elif not self.config.use_z_number:
            scales = self.config.standard_scales
            self.table_ref_scales.setRowCount(len(scales))
            self.table_ref_scales.setColumnCount(3)
            self.table_ref_scales.setHorizontalHeaderLabels(["Code", "Term", "Value"])
            for r, s in enumerate(scales):
                self.table_ref_scales.setItem(r, 0, QTableWidgetItem(s.code))
                self.table_ref_scales.setItem(r, 1, QTableWidgetItem(s.linguistic))
                self.table_ref_scales.setItem(r, 2, QTableWidgetItem(str(s.value)))
        else:
            # Z-Number
            sa = self.config.z_scales_a
            sb = self.config.z_scales_b
            max_r = max(len(sa), len(sb))
            self.table_ref_scales.setRowCount(max_r)
            self.table_ref_scales.setColumnCount(4)
            self.table_ref_scales.setHorizontalHeaderLabels(["[A] Code", "[A] Value", "[B] Code", "[B] Value"])
            for r in range(max_r):
                if r < len(sa):
                    self.table_ref_scales.setItem(r, 0, QTableWidgetItem(sa[r].code))
                    self.table_ref_scales.setItem(r, 1, QTableWidgetItem(str(sa[r].value)))
                if r < len(sb):
                    self.table_ref_scales.setItem(r, 2, QTableWidgetItem(sb[r].code))
                    self.table_ref_scales.setItem(r, 3, QTableWidgetItem(str(sb[r].value)))

    def build_matrix(self):
        """Sinh cấu trúc ma trận chuẩn."""
        model = self.config.model_type
        factors = [f.code for f in self.config.factors]
        alts = [a.code for a in self.config.alternatives]

        scales_a = self.config.z_scales_a if self.config.use_z_number else self.config.standard_scales
        scales_b = self.config.z_scales_b if self.config.use_z_number else []

        self.cell_widgets.clear()

        if model in ["DEMATEL", "AHP"]:
            self.row_labels = factors
            self.col_labels = factors
            n = len(factors)
            self.table_matrix.setRowCount(n)
            self.table_matrix.setColumnCount(n)
            self.table_matrix.setHorizontalHeaderLabels(factors)
            self.table_matrix.setVerticalHeaderLabels(factors)

            for i in range(n):
                for j in range(n):
                    if model == "DEMATEL" and i == j:
                        item = QTableWidgetItem("0")
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        item.setBackground(QBrush(QColor("#dee2e6")))
                        self.table_matrix.setItem(i, j, item)
                    elif model == "AHP" and i == j:
                        item = QTableWidgetItem("1")
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        item.setBackground(QBrush(QColor("#dee2e6")))
                        self.table_matrix.setItem(i, j, item)
                    elif model == "AHP" and i > j:
                        item = QTableWidgetItem("1/(a_ji)")
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        item.setBackground(QBrush(QColor("#fff3cd")))
                        self.table_matrix.setItem(i, j, item)
                    else:
                        cell = MatrixCellWidget(
                            is_continuous=(self.config.scale_type == "Continuous"),
                            use_z=self.config.use_z_number,
                            scales_a=scales_a, scales_b=scales_b,
                            c_min=self.config.continuous_min, c_max=self.config.continuous_max
                        )
                        self.table_matrix.setCellWidget(i, j, cell)
                        self.cell_widgets[(i, j)] = cell

        elif model == "TOPSIS":
            self.row_labels = alts
            self.col_labels = factors
            r_count = len(alts)
            c_count = len(factors)
            self.table_matrix.setRowCount(r_count)
            self.table_matrix.setColumnCount(c_count)
            self.table_matrix.setHorizontalHeaderLabels(factors)
            self.table_matrix.setVerticalHeaderLabels(alts)

            for i in range(r_count):
                for j in range(c_count):
                    cell = MatrixCellWidget(
                        is_continuous=(self.config.scale_type == "Continuous"),
                        use_z=self.config.use_z_number,
                        scales_a=scales_a, scales_b=scales_b,
                        c_min=self.config.continuous_min, c_max=self.config.continuous_max
                    )
                    self.table_matrix.setCellWidget(i, j, cell)
                    self.cell_widgets[(i, j)] = cell

        elif model == "DELPHI":
            self.row_labels = factors
            self.col_labels = ["Rating"]
            n = len(factors)
            self.table_matrix.setRowCount(n)
            self.table_matrix.setColumnCount(1)
            self.table_matrix.setHorizontalHeaderLabels(["Rating"])
            self.table_matrix.setVerticalHeaderLabels([f"{f.code}: {f.name}" for f in self.config.factors])

            for i in range(n):
                cell = MatrixCellWidget(
                    is_continuous=(self.config.scale_type == "Continuous"),
                    use_z=self.config.use_z_number,
                    scales_a=scales_a, scales_b=scales_b,
                    c_min=self.config.continuous_min, c_max=self.config.continuous_max
                )
                self.table_matrix.setCellWidget(i, 0, cell)
                self.cell_widgets[(i, 0)] = cell

        self.table_matrix.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_matrix.verticalHeader().setDefaultSectionSize(40)

    # =========================================================================
    # XÁC THỰC MẬT KHẨU & CHUYỂN NGƯỜI (TỰ ĐỘNG REFRESH)
    # =========================================================================
    def lock_matrix(self, locked: bool):
        """Khóa hoặc mở khóa ma trận."""
        self.table_matrix.setEnabled(not locked)
        self.btn_save_expert.setEnabled(not locked)
        if locked:
            self.lbl_auth_status.setText("🔒 Locked (Requires Password)")
            self.lbl_auth_status.setStyleSheet("font-weight: bold; color: #dc3545; font-size: 12px;")
        else:
            self.lbl_auth_status.setText("🔓 Unlocked (Active Session)")
            self.lbl_auth_status.setStyleSheet("font-weight: bold; color: #198754; font-size: 12px;")

    def authenticate_expert(self):
        """Kiểm tra mật khẩu của chuyên gia đang chọn."""
        exp: Expert = self.cb_experts.currentData()
        if not exp:
            return

        input_pwd = self.txt_password.text().strip()
        if str(exp.password).strip() == input_pwd:
            self.is_authenticated = True
            self.lock_matrix(False)
            self.txt_password.clear()
            
            # Nếu người này đã từng lưu bài trước đó -> Nạp lại bài cũ
            response_key = exp.respondent_id or exp.username or exp.name
            if response_key in self.saved_experts_data:
                saved = self.saved_experts_data[response_key]["code_matrix"]
                for (r, c), widget in self.cell_widgets.items():
                    if r < len(saved) and c < len(saved[r]):
                        widget.set_value_by_code(saved[r][c])
                QMessageBox.information(self, "Welcome Back", f"Authenticated successfully! Loaded previously saved data for {exp.name}.")
            else:
                QMessageBox.information(self, "Success", f"Authenticated successfully for {exp.name}. Matrix is unlocked.")
        else:
            QMessageBox.critical(self, "Access Denied", "Incorrect password! Please check the password defined in the Excel template.")

    def on_expert_selected_change(self):
        """Khi chọn chuyên gia khác: Tự động khóa lại & REFRESH trắng ma trận."""
        self.is_authenticated = False
        self.lock_matrix(True)
        self.txt_password.clear()

        # REFRESH TOÀN BỘ MA TRẬN VỀ TRẮNG BAN ĐẦU (Không dính dữ liệu người cũ)
        for widget in self.cell_widgets.values():
            widget.reset_to_default()

        self.lbl_cell_coords.setText("📍 SELECTED COORDINATE: None")
        self.lbl_dynamic_question.setText("👉 Please login and unlock to begin evaluation.")

    # =========================================================================
    # HƯỚNG DẪN ĐỘNG CHI TIẾT TỌA ĐỘ Ô
    # =========================================================================
    def on_cell_clicked(self, row: int, col: int):
        model = self.config.model_type
        r_code = self.row_labels[row] if row < len(self.row_labels) else f"Row {row+1}"
        c_code = self.col_labels[col] if col < len(self.col_labels) else f"Col {col+1}"

        # Tìm tên và mô tả đầy đủ
        r_obj = next((f for f in self.config.factors + self.config.alternatives if f.code == r_code), None)
        c_obj = next((f for f in self.config.factors + self.config.alternatives if f.code == c_code), None)

        r_name = r_obj.name if r_obj else r_code
        c_name = c_obj.name if c_obj else c_code

        r_desc = f" ({r_obj.description})" if r_obj and r_obj.description else ""
        c_desc = f" ({c_obj.description})" if c_obj and c_obj.description else ""

        self.lbl_cell_coords.setText(f"📍 COORDINATE [{r_code} → {c_code}]  |  Row: {r_name}  ×  Col: {c_name}")

        if model == "DEMATEL":
            if row == col:
                self.lbl_dynamic_question.setText(f"⚠️ Cell ({r_code}, {c_code}): A factor cannot exert direct influence on itself (Locked to 0).")
            else:
                self.lbl_dynamic_question.setText(
                    f"❓ Evaluate the direct impact/influence of Factor [{r_code}: {r_name}{r_desc}] onto Factor [{c_code}: {c_name}{c_desc}]."
                )
        elif model == "AHP":
            if row == col:
                self.lbl_dynamic_question.setText(f"⚠️ Cell ({r_code}, {c_code}): Criteria compared to itself (Locked to 1).")
            elif row < col:
                self.lbl_dynamic_question.setText(
                    f"❓ How much more important/preferable is Criterion [{r_code}: {r_name}{r_desc}] compared to Criterion [{c_code}: {c_name}{c_desc}]?"
                )
            else:
                self.lbl_dynamic_question.setText(f"⚠️ Cell ({r_code}, {c_code}): Automatically assigned reciprocal value 1 / ({c_code}, {r_code}).")
        elif model == "TOPSIS":
            self.lbl_dynamic_question.setText(
                f"❓ How well does Alternative [{r_code}: {r_name}{r_desc}] perform against Criterion [{c_code}: {c_name}{c_desc}]?"
            )
        elif model == "DELPHI":
            self.lbl_dynamic_question.setText(
                f"❓ Evaluate the relevance / consensus score for Item [{r_code}: {r_name}{r_desc}]."
            )

    # =========================================================================
    # LƯU VÀ XUẤT KẾT QUẢ
    # =========================================================================
    def save_current_expert(self):
        """Lưu bài đánh giá của chuyên gia hiện tại."""
        exp_name = ""
        respondent_id = ""
        if self.config.expert_auth_mode == "Account":
            exp: Expert = self.cb_experts.currentData()
            if not exp:
                return
            exp_name = exp.name
            respondent_id = exp.respondent_id or exp.username
        else:
            exp_name = self.txt_expert_free.text().strip()
            respondent_id = f"FREE_{exp_name}" if exp_name else ""

        if not exp_name:
            QMessageBox.warning(self, "Warning", "Please provide a valid expert name.")
            return

        r_len = len(self.row_labels)
        c_len = len(self.col_labels)
        code_mat = [["" for _ in range(c_len)] for _ in range(r_len)]
        val_mat = [["" for _ in range(c_len)] for _ in range(r_len)]

        for r in range(r_len):
            for c in range(c_len):
                if (r, c) in self.cell_widgets:
                    widget = self.cell_widgets[(r, c)]
                    code_mat[r][c] = widget.get_code()
                    val_mat[r][c] = widget.get_value()
                else:
                    item = self.table_matrix.item(r, c)
                    txt = item.text() if item else ""
                    code_mat[r][c] = txt
                    val_mat[r][c] = txt

        answer_key = respondent_id or exp_name
        self.saved_experts_data[answer_key] = {
            "code_matrix": code_mat,
            "value_matrix": val_mat,
            "expert_name": exp_name,
            "respondent_id": respondent_id,
            "answer_id": self._answer_id_for_key(answer_key),
        }

        if self.project_db:
            self.project_db.save_response(
                respondent_id=respondent_id,
                response_data={"code_matrix": code_mat, "value_matrix": val_mat},
            )
            # Reload Answer numbering from the persisted database after every save.
            self.reload_from_project_db()

        self.update_progress_counter()
        QMessageBox.information(self, "Saved", f"Data for expert '{exp_name}' has been successfully saved!")

    def _answer_id_for_key(self, respondent_id: str) -> str:
        if self.project_db:
            row = self.project_db.get_response_by_respondent(respondent_id)
            if row:
                return f"Ans_{int(row['display_index']):02d}"
        return "Ans_01"

    def reload_from_project_db(self):
        """Refresh response cache after save/merge without changing immutable config."""
        if not self.project_db:
            return
        selected_id = None
        exp = self.cb_experts.currentData() if self.config.expert_auth_mode == "Account" else None
        if exp:
            selected_id = exp.respondent_id or exp.username
        self.saved_experts_data.clear()
        for row in self.project_db.get_all_responses():
            try:
                payload = __import__("json").loads(row["response_json"])
            except Exception:
                continue
            key = str(row["respondent_id"] or row["id"])
            self.saved_experts_data[key] = {
                "code_matrix": payload.get("code_matrix", []),
                "value_matrix": payload.get("value_matrix", []),
                "expert_name": row.get("full_name") or key,
                "respondent_id": key,
                "answer_id": f"Ans_{int(row['display_index']):02d}",
                "submitted_at": row.get("submitted_at", ""),
                "source_project_id": row.get("source_project_id", ""),
                "source_project_name": row.get("source_project_name", ""),
            }
        self.update_progress_counter()

    def update_progress_counter(self):
        total = len(self.config.experts) if self.config.expert_auth_mode == "Account" else len(self.saved_experts_data)
        completed = len(self.saved_experts_data)
        self.lbl_progress.setText(f"Experts completed: {completed} / {max(total, completed)}")

    def on_export_all_clicked(self):
        if not self.saved_experts_data:
            QMessageBox.warning(self, "No Data", "No expert data has been saved yet to export.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save 2 Result Files")
        if not folder:
            return

        file_code = f"{folder}/ALL_EXPERTS_{self.config.model_type}_RAW_CODES.xlsx"
        file_val = f"{folder}/ALL_EXPERTS_{self.config.model_type}_NUMERICAL_VALUES.xlsx"

        try:
            export_all_experts_results(
                file_code, file_val, self.config,
                self.saved_experts_data, self.row_labels, self.col_labels
            )
            QMessageBox.information(
                self, "Export Successful!",
                f"Successfully exported {len(self.saved_experts_data)} expert sheets to:\n\n"
                f"1. Raw Codes:\n{file_code}\n\n"
                f"2. Numerical / Fuzzy Values:\n{file_val}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred while exporting:\n{e}")