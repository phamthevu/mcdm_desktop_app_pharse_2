from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QComboBox, QCheckBox, QRadioButton, QButtonGroup,
    QLineEdit, QPushButton, QFileDialog, QMessageBox, QDoubleSpinBox,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QDoubleValidator
from core.models import ProjectConfig, config_to_dict
from core.excel_handler import parse_config_excel, generate_default_template


class TabConfig(QWidget):
    started = pyqtSignal(ProjectConfig)
    project_created = pyqtSignal(ProjectConfig, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ProjectConfig()
        self.is_locked = False
        self.init_ui()
        self.load_and_preview_default()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # =====================================================================
        # LEFT PANEL: CONFIGURATION CONTROLS
        # =====================================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(5, 5, 10, 5)

        # 1. Model & Z-Number
        grp_model = QGroupBox("1. MCDM Model & Z-Number Configuration")
        lay_model = QGridLayout(grp_model)

        lay_model.addWidget(QLabel("Target Model:"), 0, 0)
        self.cb_model = QComboBox()
        self.cb_model.addItems(["DEMATEL", "TOPSIS", "AHP", "DELPHI"])
        self.cb_model.currentTextChanged.connect(self.on_config_changed)
        lay_model.addWidget(self.cb_model, 0, 1)

        self.chk_z_number = QCheckBox("Enable Z-Number (Restriction + Reliability)")
        self.chk_z_number.toggled.connect(self.on_z_number_toggled)
        lay_model.addWidget(self.chk_z_number, 1, 0, 1, 2)
        left_layout.addWidget(grp_model)

        # 2. Scale Configuration
        grp_scale = QGroupBox("2. Scale Configuration")
        lay_scale = QGridLayout(grp_scale)

        self.rb_category = QRadioButton("Categorical (Linguistic: VL, L, M, H, VH)")
        self.rb_continuous = QRadioButton("Continuous (Numerical: Slider / Direct input)")
        self.rb_category.setChecked(True)

        self.btn_group_scale = QButtonGroup(self)
        self.btn_group_scale.addButton(self.rb_category)
        self.btn_group_scale.addButton(self.rb_continuous)

        lay_scale.addWidget(self.rb_category, 0, 0, 1, 4)
        lay_scale.addWidget(self.rb_continuous, 1, 0, 1, 4)

        self.lbl_min = QLabel("Min:")
        self.spin_min = QLineEdit("0")
        self.spin_min.setValidator(QDoubleValidator(-1000000000, 1000000000, 8, self))
        self.spin_min.setPlaceholderText("Enter minimum")
        self.spin_min.textChanged.connect(self.update_preview_scales)

        self.lbl_max = QLabel("Max:")
        self.spin_max = QLineEdit("10")
        self.spin_max.setValidator(QDoubleValidator(-1000000000, 1000000000, 8, self))
        self.spin_max.setPlaceholderText("Enter maximum")
        self.spin_max.textChanged.connect(self.update_preview_scales)

        lay_scale.addWidget(self.lbl_min, 2, 0)
        lay_scale.addWidget(self.spin_min, 2, 1)
        lay_scale.addWidget(self.lbl_max, 2, 2)
        lay_scale.addWidget(self.spin_max, 2, 3)

        self.rb_category.toggled.connect(self.on_scale_type_toggled)
        left_layout.addWidget(grp_scale)

        # 3. Expert Access — V4.7: MCDM always uses a predefined expert roster.
        # MCDM is an expert-evaluation workflow, so anonymous/free entry is not
        # offered. Quantitative and Qualitative projects still support Free/Account.
        grp_expert = QGroupBox("3. Expert Access")
        lay_expert = QVBoxLayout(grp_expert)
        self.rb_expert_account = QRadioButton("Excel Roster (Predefined Username / Password)")
        self.rb_expert_account.setChecked(True)
        self.rb_expert_account.setEnabled(False)
        # Compatibility attribute for older code paths; never shown/selected.
        self.rb_expert_free = QRadioButton("Free Entry")
        self.rb_expert_free.setChecked(False)
        self.rb_expert_free.setVisible(False)
        self._selected_expert_auth_mode = "Account"
        self.btn_group_expert = QButtonGroup(self)
        self.btn_group_expert.addButton(self.rb_expert_account)
        self.btn_group_expert.addButton(self.rb_expert_free)
        lay_expert.addWidget(self.rb_expert_account)
        note = QLabel("MCDM requires identified experts from the Excel roster. Free Entry is available only for Quantitative and Qualitative projects.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748b; font-size:11px;")
        lay_expert.addWidget(note)
        left_layout.addWidget(grp_expert)

        # 4. Template File
        grp_file = QGroupBox("4. Excel Configuration Template")
        lay_file = QVBoxLayout(grp_file)

        self.txt_file_path = QLineEdit()
        self.txt_file_path.setPlaceholderText("Path to .xlsx configuration template...")
        self.txt_file_path.textChanged.connect(self.reload_excel_data)
        lay_file.addWidget(self.txt_file_path)

        h_btn_file = QHBoxLayout()
        self.btn_browse = QPushButton("Browse File...")
        self.btn_browse.clicked.connect(self.browse_excel_file)

        self.btn_gen_template = QPushButton("Generate Default Template")
        self.btn_gen_template.setProperty("accent", True)
        self.btn_gen_template.clicked.connect(self.generate_template_click)

        h_btn_file.addWidget(self.btn_browse)
        h_btn_file.addWidget(self.btn_gen_template)
        lay_file.addLayout(h_btn_file)
        left_layout.addWidget(grp_file)

        # 5. START Button
        left_layout.addStretch()
        self.btn_start = QPushButton("START SURVEY")
        self.btn_start.setProperty("primary", True)
        self.btn_start.setFixedHeight(45)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        self.btn_start.clicked.connect(self.on_start_clicked)
        left_layout.addWidget(self.btn_start)

        # =====================================================================
        # RIGHT PANEL: PREVIEW TABS (Bao gồm cả Template Preview)
        # =====================================================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 5, 5, 5)

        lbl_preview_title = QLabel("CONFIGURATION PREVIEW")
        lbl_preview_title.setStyleSheet("font-weight: bold; color: #333; font-size: 13px;")
        right_layout.addWidget(lbl_preview_title)

        self.preview_tabs = QTabWidget()

        # Tab Preview 1: Template Structure Blueprint (Hình dung mẫu ma trận)
        tab_template_preview = QWidget()
        lay_tab_tpl = QVBoxLayout(tab_template_preview)
        
        self.lbl_matrix_info = QLabel("Matrix Blueprint:")
        self.lbl_matrix_info.setStyleSheet("font-style: italic; color: #0d6efd; font-weight: bold;")
        lay_tab_tpl.addWidget(self.lbl_matrix_info)

        self.table_matrix_preview = QTableWidget()
        self.setup_table_style(self.table_matrix_preview)
        lay_tab_tpl.addWidget(self.table_matrix_preview)

        self.preview_tabs.addTab(tab_template_preview, "Matrix Blueprint")

        # Tab Preview 2: Factors & Solutions
        self.table_factors = QTableWidget()
        self.setup_table_style(self.table_factors)
        self.preview_tabs.addTab(self.table_factors, "Factors & Solutions")

        # Tab Preview 3: Scale Definition
        self.table_scales = QTableWidget()
        self.setup_table_style(self.table_scales)
        self.preview_tabs.addTab(self.table_scales, "Scale Definition")

        # Tab Preview 4: Expert Roster
        self.table_experts = QTableWidget()
        self.setup_table_style(self.table_experts)
        self.preview_tabs.addTab(self.table_experts, "Expert Roster")

        right_layout.addWidget(self.preview_tabs)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([380, 720])

        self.on_scale_type_toggled()

    def setup_table_style(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(28)

    def on_scale_type_toggled(self):
        is_continuous = self.rb_continuous.isChecked()
        self.lbl_min.setEnabled(is_continuous)
        self.spin_min.setEnabled(is_continuous)
        self.lbl_max.setEnabled(is_continuous)
        self.spin_max.setEnabled(is_continuous)
        self.on_config_changed()

    def on_z_number_toggled(self):
        self.on_config_changed()

    def on_config_changed(self):
        self.reload_excel_data()

    def _on_expert_mode_changed(self, _checked=False):
        """MCDM V4.7 always uses identified expert accounts."""
        self._selected_expert_auth_mode = "Account"
        self.rb_expert_account.setChecked(True)
        self.reload_excel_data()

    def browse_excel_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Excel Configuration Template", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            self.txt_file_path.setText(file_name)

    def load_and_preview_default(self):
        default_tpl = Path("templates/Config_Template.xlsx")
        if default_tpl.exists():
            self.txt_file_path.setText(str(default_tpl.resolve()))

    def generate_template_click(self):
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save MCDM Configuration Template",
            "MCDM_Config_Template.xlsx", "Excel Files (*.xlsx)"
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".xlsx"):
            output_path += ".xlsx"
        try:
            generate_default_template(output_path)
            self.txt_file_path.setText(str(Path(output_path).resolve()))
            QMessageBox.information(
                self, "Template Created",
                f"MCDM template created successfully.\n\n{Path(output_path).resolve()}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate template: {e}")

    def reload_excel_data(self):
        file_path = self.txt_file_path.text().strip()
        if not file_path or not Path(file_path).exists():
            return

        self.config.model_type = self.cb_model.currentText()
        self.config.use_z_number = self.chk_z_number.isChecked()
        self.config.scale_type = "Continuous" if self.rb_continuous.isChecked() else "Category"
        self.config.continuous_min = float(self.spin_min.text() or 0)
        self.config.continuous_max = float(self.spin_max.text() or 10)
        # UI selection is authoritative. Excel supplies factors/scales/roster,
        # never the respondent access mode.
        selected_mode = "Account"
        self._selected_expert_auth_mode = "Account"
        self.config.expert_auth_mode = "Account"

        try:
            self.config = parse_config_excel(file_path, self.config)
            # Defensive re-apply in case a legacy parser/template mutates config.
            self.config.expert_auth_mode = "Account"
            self.update_matrix_blueprint()
            self.update_preview_factors()
            self.update_preview_scales()
            self.update_preview_experts()
        except Exception:
            pass

    def update_matrix_blueprint(self):
        """Vẽ ma trận mô phỏng theo mô hình được chọn và danh sách Factors/Alternatives."""
        model = self.config.model_type
        factors = [f.code for f in self.config.factors]
        alts = [a.code for a in self.config.alternatives]
        has_z = self.config.use_z_number
        z_tag = " (Z-Number: [Eval, Cert])" if has_z else ""

        if model == "DEMATEL":
            self.lbl_matrix_info.setText(f"DEMATEL Direct Influence Matrix ({len(factors)}x{len(factors)}){z_tag} - Diagonal is locked (0)")
            n = len(factors)
            self.table_matrix_preview.setRowCount(n)
            self.table_matrix_preview.setColumnCount(n)
            self.table_matrix_preview.setHorizontalHeaderLabels(factors)
            self.table_matrix_preview.setVerticalHeaderLabels(factors)

            for i in range(n):
                for j in range(n):
                    if i == j:
                        item = QTableWidgetItem("0 (No Influence)")
                        item.setBackground(QBrush(QColor("#f0f0f0")))
                        item.setForeground(QBrush(QColor("#888888")))
                    else:
                        item = QTableWidgetItem("[Eval | Cert]" if has_z else "[Evaluation]")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_matrix_preview.setItem(i, j, item)

        elif model == "AHP":
            self.lbl_matrix_info.setText(f"AHP Pairwise Comparison Matrix ({len(factors)}x{len(factors)}){z_tag} - Reciprocal: a(j,i) = 1/a(i,j)")
            n = len(factors)
            self.table_matrix_preview.setRowCount(n)
            self.table_matrix_preview.setColumnCount(n)
            self.table_matrix_preview.setHorizontalHeaderLabels(factors)
            self.table_matrix_preview.setVerticalHeaderLabels(factors)

            for i in range(n):
                for j in range(n):
                    if i == j:
                        item = QTableWidgetItem("1 (Equal)")
                        item.setBackground(QBrush(QColor("#f0f0f0")))
                        item.setForeground(QBrush(QColor("#888888")))
                    elif i < j:
                        item = QTableWidgetItem("[a_ij]" if not has_z else "[a_ij | z_ij]")
                        item.setBackground(QBrush(QColor("#e8f4fd")))
                    else:
                        item = QTableWidgetItem("1 / a_ji (Reciprocal)")
                        item.setBackground(QBrush(QColor("#fff8e6")))
                        item.setForeground(QBrush(QColor("#b58105")))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_matrix_preview.setItem(i, j, item)

        elif model == "TOPSIS":
            self.lbl_matrix_info.setText(f"TOPSIS Decision Matrix ({len(alts)} Alternatives x {len(factors)} Criteria){z_tag}")
            row_count = len(alts) if alts else 1
            col_count = len(factors) if factors else 1

            self.table_matrix_preview.setRowCount(row_count)
            self.table_matrix_preview.setColumnCount(col_count)
            self.table_matrix_preview.setHorizontalHeaderLabels(factors if factors else ["No Factor"])
            self.table_matrix_preview.setVerticalHeaderLabels(alts if alts else ["No Alternative"])

            for i in range(row_count):
                for j in range(col_count):
                    item = QTableWidgetItem("[Score | Cert]" if has_z else "[Performance Score]")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_matrix_preview.setItem(i, j, item)

        elif model == "DELPHI":
            self.lbl_matrix_info.setText(f"DELPHI Consensus Evaluation Form ({len(factors)} Items){z_tag}")
            self.table_matrix_preview.setRowCount(len(factors))
            self.table_matrix_preview.setColumnCount(2)
            self.table_matrix_preview.setHorizontalHeaderLabels(["Criterion / Item", "Rating & Confidence" if has_z else "Rating Score"])
            self.table_matrix_preview.setVerticalHeaderLabels([str(i+1) for i in range(len(factors))])

            for i, f_code in enumerate(factors):
                f_name = self.config.factors[i].name if i < len(self.config.factors) else f_code
                item_lbl = QTableWidgetItem(f"{f_code}: {f_name}")
                item_val = QTableWidgetItem("[Rating | Confidence]" if has_z else "[Rating]")
                item_val.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_matrix_preview.setItem(i, 0, item_lbl)
                self.table_matrix_preview.setItem(i, 1, item_val)

    def update_preview_factors(self):
        items = []
        for f in self.config.factors:
            items.append(("Factor / Criterion", f.code, f.name, f.description))
        for a in self.config.alternatives:
            items.append(("Alternative / Solution", a.code, a.name, a.description))

        self.table_factors.setRowCount(len(items))
        self.table_factors.setColumnCount(4)
        self.table_factors.setHorizontalHeaderLabels(["Item Type", "Code", "Item Name", "Description"])

        for row_idx, (itype, code, name, desc) in enumerate(items):
            self.table_factors.setItem(row_idx, 0, QTableWidgetItem(itype))
            self.table_factors.setItem(row_idx, 1, QTableWidgetItem(code))
            self.table_factors.setItem(row_idx, 2, QTableWidgetItem(name))
            self.table_factors.setItem(row_idx, 3, QTableWidgetItem(desc))

    def update_preview_scales(self):
        if self.config.scale_type == "Continuous":
            self.table_scales.setRowCount(1)
            self.table_scales.setColumnCount(3)
            self.table_scales.setHorizontalHeaderLabels(["Scale Type", "Lower Bound (Min)", "Upper Bound (Max)"])
            self.table_scales.setItem(0, 0, QTableWidgetItem("Continuous Scale"))
            self.table_scales.setItem(0, 1, QTableWidgetItem(self.spin_min.text()))
            self.table_scales.setItem(0, 2, QTableWidgetItem(self.spin_max.text()))
            return

        if not self.config.use_z_number:
            scales = self.config.standard_scales
            self.table_scales.setRowCount(len(scales))
            self.table_scales.setColumnCount(3)
            self.table_scales.setHorizontalHeaderLabels(["Linguistic Term", "Code", "Fuzzy / Crisp Value"])
            for r, item in enumerate(scales):
                self.table_scales.setItem(r, 0, QTableWidgetItem(str(item.linguistic)))
                self.table_scales.setItem(r, 1, QTableWidgetItem(str(item.code)))
                self.table_scales.setItem(r, 2, QTableWidgetItem(str(item.value)))
        else:
            scales_a = self.config.z_scales_a
            scales_b = self.config.z_scales_b
            max_len = max(len(scales_a), len(scales_b))

            self.table_scales.setRowCount(max_len)
            self.table_scales.setColumnCount(6)
            self.table_scales.setHorizontalHeaderLabels([
                "[A] Linguistic", "[A] Code", "[A] Value",
                "[B] Reliability", "[B] Code", "[B] Value"
            ])
            for r in range(max_len):
                if r < len(scales_a):
                    self.table_scales.setItem(r, 0, QTableWidgetItem(str(scales_a[r].linguistic)))
                    self.table_scales.setItem(r, 1, QTableWidgetItem(str(scales_a[r].code)))
                    self.table_scales.setItem(r, 2, QTableWidgetItem(str(scales_a[r].value)))
                if r < len(scales_b):
                    self.table_scales.setItem(r, 3, QTableWidgetItem(str(scales_b[r].linguistic)))
                    self.table_scales.setItem(r, 4, QTableWidgetItem(str(scales_b[r].code)))
                    self.table_scales.setItem(r, 5, QTableWidgetItem(str(scales_b[r].value)))

    def update_preview_experts(self):
        if self.config.expert_auth_mode == "Free":
            self.table_experts.setRowCount(1)
            self.table_experts.setColumnCount(2)
            self.table_experts.setHorizontalHeaderLabels(["Mode", "Description"])
            self.table_experts.setItem(0, 0, QTableWidgetItem("Free / Anonymous"))
            self.table_experts.setItem(0, 1, QTableWidgetItem("Experts enter their credentials or names directly."))
            return

        experts = self.config.experts
        self.table_experts.setRowCount(len(experts))
        self.table_experts.setColumnCount(3)
        self.table_experts.setHorizontalHeaderLabels(["Expert Name", "Username", "Password"])
        for r, exp in enumerate(experts):
            self.table_experts.setItem(r, 0, QTableWidgetItem(exp.name))
            self.table_experts.setItem(r, 1, QTableWidgetItem(exp.username))
            self.table_experts.setItem(r, 2, QTableWidgetItem("••••••" if exp.password else ""))


    def load_locked_project(self, config: ProjectConfig):
        """Display a stored project configuration without allowing re-import/editing."""
        self.config = config
        self.cb_model.setCurrentText(config.model_type)
        self.chk_z_number.setChecked(config.use_z_number)
        self.rb_continuous.setChecked(config.scale_type == "Continuous")
        self.rb_category.setChecked(config.scale_type != "Continuous")
        self.spin_min.setText(str(config.continuous_min))
        self.spin_max.setText(str(config.continuous_max))
        self._selected_expert_auth_mode = "Account"
        self.config.expert_auth_mode = "Account"
        self.rb_expert_free.setChecked(False)
        self.rb_expert_account.setChecked(True)
        self.txt_file_path.setText("Configuration stored inside project (.mcdm)")
        self.update_preview_factors()
        self.update_preview_scales()
        self.update_preview_experts()
        self.setEnabled(False)

    def unlock_for_new_project(self):
        """Return the configuration tab to editable state for a new project."""
        self.setEnabled(True)
        self.txt_file_path.clear()
        self.config = ProjectConfig()
        self.cb_model.setCurrentText("DEMATEL")
        self.chk_z_number.setChecked(False)
        self.rb_category.setChecked(True)
        self._selected_expert_auth_mode = "Account"
        self.rb_expert_account.setChecked(True)
        self.spin_min.setText("0")
        self.spin_max.setText("10")
        self.load_and_preview_default()

    def on_start_clicked(self):
        """Validate configuration, then create a new immutable .mcdm project."""
        file_path = self.txt_file_path.text().strip()
        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(
                self, "File Not Found",
                "Please select a valid Excel configuration template before proceeding."
            )
            return

        # V4.7: MCDM always requires the predefined expert roster.
        self._selected_expert_auth_mode = "Account"
        self.reload_excel_data()
        self.config.expert_auth_mode = "Account"
        if not self.config.experts:
            QMessageBox.warning(
                self, "Missing Expert Roster",
                "MCDM requires at least one expert account. Please add experts to the Excel 'Experts' sheet."
            )
            return

        if not self.config.factors:
            QMessageBox.warning(
                self, "Missing Factors",
                "Factor list is empty. Please verify the Excel sheet 'Factors_Alternatives'."
            )
            return

        if self.config.model_type == "TOPSIS" and not self.config.alternatives:
            QMessageBox.warning(
                self, "Missing Alternatives",
                "The TOPSIS model requires at least one Alternative/Solution entry."
            )
            return

        project_name, ok = QInputDialog.getText(
            self, "Create New Project", "Project name:"
        )
        if not ok or not project_name.strip():
            return
        project_name = project_name.strip()

        default_name = f"{project_name}.mcdm"
        db_path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Project Location",
            str(Path.home() / default_name),
            "MCDM Project (*.mcdm)"
        )
        if not db_path:
            return
        if not db_path.lower().endswith(".mcdm"):
            db_path += ".mcdm"

        if Path(db_path).exists():
            QMessageBox.warning(
                self, "Project Exists",
                "A project already exists at this location. Please choose another file."
            )
            return

        # project_db owns the canonical immutable copy. The Excel file remains
        # only the creation source and is never re-imported when opening a project.
        self.project_created.emit(self.config, db_path, project_name)

