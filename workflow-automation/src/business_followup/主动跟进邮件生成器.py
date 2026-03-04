"""
外贸邮件生成器 - PyQt6专业版（修复模板组独立存储问题）
修复了所有模板组共用一套编辑的问题，现在每个模板组独立存储
"""

import sys
import random
import os
import re
import json
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFrame, QSplitter,
    QDialog, QLineEdit, QCheckBox, QMessageBox, QFileDialog,
    QMenuBar, QStatusBar, QMenu, QTabWidget, QListWidget,
    QListWidgetItem, QComboBox, QGroupBox, QInputDialog,
    QGridLayout, QToolBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QFont, QAction, QKeySequence, QShortcut, QKeyEvent,
    QIcon, QPixmap, QColor
)
import pyperclip  # 需要安装: pip install pyperclip

class EnterTextEdit(QTextEdit):
    """自定义文本框，重写键盘事件"""
    enterPressed = pyqtSignal()
    ctrlEnterPressed = pyqtSignal()
    textChangedSignal = pyqtSignal()
    
    def keyPressEvent(self, event: QKeyEvent):
        """重写按键事件"""
        # Ctrl+Enter: 换行
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Return:
            self.ctrlEnterPressed.emit()
            event.accept()
        # Enter: 生成邮件
        elif event.key() == Qt.Key.Key_Return:
            self.enterPressed.emit()
            event.accept()
        # 其他按键正常处理
        else:
            super().keyPressEvent(event)
            # 文本改变时发出信号
            self.textChangedSignal.emit()

class EmailGeneratorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 配置
        self.config_file = "email_config.json"
        self.templates_dir = "email_templates"
        
        # 确保目录存在
        Path(self.templates_dir).mkdir(exist_ok=True)
        
        # 加载配置
        self.config = self.load_config()
        
        # 加载模板分组
        self.template_groups = self.load_template_groups()
        
        # 设置当前模板组
        self.current_group = self.config.get("current_template_group", "default")
        if self.current_group not in self.template_groups:
            self.current_group = list(self.template_groups.keys())[0] if self.template_groups else "default"
        
        # 获取当前组的模板
        self.openings = self.template_groups.get(self.current_group, {}).get("openings", [])
        self.bodies = self.template_groups.get(self.current_group, {}).get("bodies", [])
        self.closings = self.template_groups.get(self.current_group, {}).get("closings", [])
        
        # 当前邮件和状态
        self.current_email = ""
        self.history = []
        
        # 存储当前提取的信息
        self.current_salutation = "Dear Customer"
        self.current_product = ""
        
        # 初始化UI
        self.init_ui()
        
        # 绑定快捷键
        self.setup_shortcuts()
        
        # 设置焦点
        self.input_text.setFocus()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("外贸邮件极速生成器 - 专业版")
        self.setGeometry(100, 100, 1100, 700)
        self.setMinimumSize(900, 600)
        
        # 设置主题
        self.apply_theme()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(5)
        
        # 创建主分割器
        splitter = QSplitter()
        splitter.setHandleWidth(2)
        
        # 左侧：输入区域（占60%）
        input_widget = self.create_input_widget()
        splitter.addWidget(input_widget)
        
        # 右侧：输出区域（占40%）
        output_widget = self.create_output_widget()
        splitter.addWidget(output_widget)
        
        # 设置分割比例
        splitter.setSizes([700, 400])
        
        main_layout.addWidget(splitter)
        
        # 创建底部状态栏
        self.create_status_bar()
        
        # 创建菜单栏
        self.create_menu()
    
    def apply_theme(self):
        """应用主题样式"""
        font = QFont("Microsoft YaHei UI", 10)
        QApplication.setFont(font)
        
        # 简洁的样式表
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QWidget {
                font-family: 'Microsoft YaHei UI';
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton#primary {
                background-color: #28a745;
                font-weight: 600;
            }
            QPushButton#primary:hover {
                background-color: #218838;
            }
            QPushButton#secondary {
                background-color: #6c757d;
            }
            QPushButton#secondary:hover {
                background-color: #5a6268;
            }
            QTextEdit, QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border-color: #80bdff;
                border-width: 2px;
                outline: none;
            }
            QLabel#section-title {
                font-size: 16px;
                font-weight: 600;
                color: #343a40;
                margin-bottom: 8px;
            }
            QLabel#hint {
                font-size: 11px;
                color: #6c757d;
                font-style: italic;
            }
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
                min-height: 30px;
            }
            QComboBox:focus {
                border-color: #80bdff;
            }
            QStatusBar {
                background-color: #e9ecef;
                border-top: 1px solid #ced4da;
                font-size: 12px;
            }
        """)
    
    def create_input_widget(self):
        """创建输入区域部件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # 标题区域
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📥 输入区域")
        title_label.setObjectName("section-title")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 模板组选择
        self.template_group_combo = QComboBox()
        self.template_group_combo.addItems(self.template_groups.keys())
        self.template_group_combo.setCurrentText(self.current_group)
        self.template_group_combo.currentTextChanged.connect(self.change_template_group)
        self.template_group_combo.setMaximumWidth(150)
        header_layout.addWidget(self.template_group_combo)
        
        # 智能提取按钮
        extract_btn = QPushButton("🔍 手动提取")
        extract_btn.setToolTip("手动提取称呼和产品信息")
        extract_btn.clicked.connect(self.extract_and_display_info)
        extract_btn.setObjectName("secondary")
        extract_btn.setMaximumWidth(100)
        header_layout.addWidget(extract_btn)
        
        layout.addLayout(header_layout)
        
        # 提示文本
        hint_label = QLabel(f"当前模板组: {self.current_group} | 粘贴客户邮件或直接输入称呼和产品信息，然后按 Enter 键生成邮件")
        hint_label.setObjectName("hint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        
        # 输入文本框
        self.input_text = EnterTextEdit()
        self.input_text.setPlaceholderText(
            "在此粘贴或输入邮件内容...\n\n示例：\n"
            "Dear Mr. Smith,\n"
            "Thank you for your inquiry about the BS 546 Gauge.\n"
            "Please find our quotation attached."
        )
        self.input_text.setMinimumHeight(200)
        
        # 连接信号
        self.input_text.enterPressed.connect(self.generate_email_auto)
        self.input_text.ctrlEnterPressed.connect(self.insert_newline)
        self.input_text.textChangedSignal.connect(self.auto_extract_info)
        
        layout.addWidget(self.input_text)
        
        # 提取的信息显示
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 8, 10, 8)
        
        self.salutation_label = QLabel("称呼: 未识别")
        self.product_label = QLabel("产品: 未识别")
        
        info_layout.addWidget(self.salutation_label)
        info_layout.addWidget(self.product_label)
        info_layout.addStretch()
        
        layout.addWidget(info_frame)
        
        # 常用操作按钮
        quick_btn_layout = QHBoxLayout()
        
        buttons = [
            ("📝 快速编辑", self.quick_edit, "secondary"),
            ("🗑️ 清空", self.clear_input, "secondary")
        ]
        
        for text, callback, style in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            if style:
                btn.setObjectName(style)
            btn.setMaximumWidth(120)
            quick_btn_layout.addWidget(btn)
        
        quick_btn_layout.addStretch()
        layout.addLayout(quick_btn_layout)
        
        return widget
    
    def create_output_widget(self):
        """创建输出区域部件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # 标题区域
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📤 生成结果")
        title_label.setObjectName("section-title")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 重新生成按钮
        regenerate_btn = QPushButton("🔄 重新生成")
        regenerate_btn.setToolTip("使用当前信息重新生成邮件 (Ctrl+R)")
        regenerate_btn.clicked.connect(self.regenerate_email)
        regenerate_btn.setObjectName("secondary")
        regenerate_btn.setMaximumWidth(120)
        header_layout.addWidget(regenerate_btn)
        
        layout.addLayout(header_layout)
        
        # 提示文本
        hint_label = QLabel("生成的邮件将显示在这里，可以编辑修改")
        hint_label.setObjectName("hint")
        layout.addWidget(hint_label)
        
        # 邮件内容文本框
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(False)
        self.output_text.setPlaceholderText("按 Enter 键生成邮件后，结果将显示在这里...")
        layout.addWidget(self.output_text)
        
        # 主要操作按钮
        action_btn_layout = QHBoxLayout()
        
        # 复制按钮（主要操作）
        copy_btn = QPushButton("📋 复制邮件")
        copy_btn.setToolTip("复制生成的邮件到剪贴板 (Ctrl+C)")
        copy_btn.setObjectName("primary")
        copy_btn.clicked.connect(self.copy_email)
        copy_btn.setMinimumHeight(36)
        action_btn_layout.addWidget(copy_btn)
        
        # 保存按钮
        save_btn = QPushButton("💾 保存")
        save_btn.setToolTip("保存邮件到文件 (Ctrl+S)")
        save_btn.clicked.connect(self.save_email)
        save_btn.setMinimumHeight(36)
        action_btn_layout.addWidget(save_btn)
        
        action_btn_layout.addStretch()
        
        # 其他功能按钮
        tools_btn_layout = QHBoxLayout()
        tools_btn_layout.addStretch()
        
        tools_buttons = [
            ("📜 历史记录", self.show_history),
            ("⚙️ 设置", self.show_settings),
        ]
        
        for text, callback in tools_buttons:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            btn.setObjectName("secondary")
            btn.setMaximumWidth(100)
            tools_btn_layout.addWidget(btn)
        
        action_btn_layout.addLayout(tools_btn_layout)
        layout.addLayout(action_btn_layout)
        
        # 设置选项
        settings_layout = QHBoxLayout()
        
        # 自动复制开关
        self.auto_copy_checkbox = QCheckBox("自动复制")
        self.auto_copy_checkbox.setToolTip("生成邮件后自动复制到剪贴板")
        self.auto_copy_checkbox.setChecked(self.config.get("auto_copy", True))
        self.auto_copy_checkbox.stateChanged.connect(self.toggle_auto_copy)
        settings_layout.addWidget(self.auto_copy_checkbox)
        
        settings_layout.addStretch()
        layout.addLayout(settings_layout)
        
        return widget
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = QLabel(f"就绪 - 当前模板组: {self.current_group} - 输入内容后按 Enter 键生成邮件")
        self.status_label.setStyleSheet("color: #6c757d;")
        self.status_bar.addWidget(self.status_label, 1)
        
        # 快捷键提示
        shortcuts_label = QLabel("Enter:生成邮件 | Ctrl+Enter:换行 | Ctrl+C:复制 | Ctrl+S:保存")
        shortcuts_label.setStyleSheet("color: #adb5bd; font-size: 11px;")
        self.status_bar.addPermanentWidget(shortcuts_label)
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        save_action = QAction("保存邮件", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_email)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        
        copy_action = QAction("复制邮件", self)
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.triggered.connect(self.copy_email)
        edit_menu.addAction(copy_action)
        
        generate_action = QAction("生成邮件", self)
        generate_action.setShortcut(QKeySequence("Ctrl+G"))
        generate_action.triggered.connect(self.generate_email_auto)
        edit_menu.addAction(generate_action)
        
        regenerate_action = QAction("重新生成", self)
        regenerate_action.setShortcut(QKeySequence("Ctrl+R"))
        regenerate_action.triggered.connect(self.regenerate_email)
        edit_menu.addAction(regenerate_action)
        
        edit_menu.addSeparator()
        
        clear_action = QAction("清空", self)
        clear_action.triggered.connect(self.clear_all)
        edit_menu.addAction(clear_action)
        
        # 模板菜单
        template_menu = menubar.addMenu("模板")
        
        manage_templates_action = QAction("管理模板组", self)
        manage_templates_action.triggered.connect(self.show_settings)
        template_menu.addAction(manage_templates_action)
        
        new_group_action = QAction("新建模板组", self)
        new_group_action.triggered.connect(self.create_new_template_group)
        template_menu.addAction(new_group_action)
    
    def setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+C 复制邮件
        shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        shortcut.activated.connect(self.copy_email)
        
        # Ctrl+S 保存邮件
        shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        shortcut.activated.connect(self.save_email)
        
        # Ctrl+R 重新生成
        shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut.activated.connect(self.regenerate_email)
        
        # Ctrl+E 快速编辑
        shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        shortcut.activated.connect(self.quick_edit)
        
        # Ctrl+H 历史记录
        shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        shortcut.activated.connect(self.show_history)
        
        # Ctrl+, 设置
        shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        shortcut.activated.connect(self.show_settings)
    
    # ========== 核心功能方法 ==========
    
    def insert_newline(self):
        """插入换行符"""
        self.input_text.insertPlainText("\n")
    
    def regenerate_email(self):
        """重新生成邮件"""
        self.generate_email_auto()
    
    def load_config(self):
        """加载配置"""
        default_config = {
            "auto_copy": True,
            "auto_generate": True,
            "show_quick_edit": True,
            "theme": "light",
            "recent_count": 10,
            "current_template_group": "default"
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return {**default_config, **config}
        except:
            pass
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def load_template_groups(self):
        """加载模板分组"""
        groups_file = "template_groups.json"
        
        # 如果分组文件不存在，创建默认分组
        if not os.path.exists(groups_file):
            default_groups = {
                "默认": {
                    "description": "通用邮件模板",
                    "openings": [
                        "Thank you for your inquiry about {product}.",
                        "Regarding your question on {product}:",
                        "We appreciate your interest in {product}.",
                        "Following up on {product}:",
                    ],
                    "bodies": [
                        "Our {product} is compliant with international standards.",
                        "The {product} features high precision and durability.",
                        "We offer competitive pricing for {product}.",
                        "Attached are the specifications for {product}.",
                    ],
                    "closings": [
                        "Looking forward to your feedback.",
                        "Please let us know if you need further information.",
                        "We await your favorable reply.",
                        "Thank you for your time.",
                    ]
                },
                "正式": {
                    "description": "正式商务邮件模板",
                    "openings": [
                        "We are writing in response to your inquiry regarding {product}.",
                        "Thank you for your interest in our {product}.",
                        "With reference to your query about {product}.",
                        "In response to your request for information about {product}.",
                    ],
                    "bodies": [
                        "The {product} meets all industry standards and certifications.",
                        "Our {product} is manufactured with the highest quality materials.",
                        "We provide comprehensive technical support for {product}.",
                        "The specifications and pricing details for {product} are enclosed.",
                    ],
                    "closings": [
                        "Should you require any additional information, please do not hesitate to contact us.",
                        "We look forward to the possibility of working with you.",
                        "Thank you for considering our products and services.",
                        "We appreciate your business and look forward to serving you.",
                    ]
                },
                "简洁": {
                    "description": "简洁高效邮件模板",
                    "openings": [
                        "Re: {product} inquiry",
                        "About {product}",
                        "Regarding your {product} question",
                        "Follow-up on {product}",
                    ],
                    "bodies": [
                        "Our {product} is high quality and reliable.",
                        "Competitive pricing for {product}.",
                        "{product} specs attached.",
                        "We can customize {product} as needed.",
                    ],
                    "closings": [
                        "Let me know if you have questions.",
                        "Looking forward to hearing from you.",
                        "Thanks for your interest.",
                        "Best regards,",
                    ]
                }
            }
            
            with open(groups_file, 'w', encoding='utf-8') as f:
                json.dump(default_groups, f, indent=2, ensure_ascii=False)
            
            return default_groups
        
        # 读取分组文件
        try:
            with open(groups_file, 'r', encoding='utf-8') as f:
                groups = json.load(f)
                return groups
        except:
            # 如果读取失败，返回默认分组
            return {
                "默认": {
                    "description": "通用邮件模板",
                    "openings": ["[模板加载失败]"],
                    "bodies": ["[模板加载失败]"],
                    "closings": ["[模板加载失败]"]
                }
            }
    
    def save_template_groups(self):
        """保存模板分组"""
        groups_file = "template_groups.json"
        try:
            with open(groups_file, 'w', encoding='utf-8') as f:
                json.dump(self.template_groups, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存模板分组失败: {e}")
    
    def change_template_group(self, group_name):
        """切换模板组"""
        if group_name in self.template_groups:
            self.current_group = group_name
            self.config["current_template_group"] = group_name
            
            # 更新当前模板
            self.openings = self.template_groups[group_name]["openings"]
            self.bodies = self.template_groups[group_name]["bodies"]
            self.closings = self.template_groups[group_name]["closings"]
            
            # 更新状态栏
            self.status_label.setText(f"就绪 - 当前模板组: {self.current_group} - 输入内容后按 Enter 键生成邮件")
            
            # 保存配置
            self.save_config()
            
            # 显示状态提示
            self.show_status(f"✅ 已切换到模板组: {group_name}", "green", 2000)
    
    def extract_salutation(self, text):
        """提取称呼"""
        # 改进的称呼提取
        patterns = [
            r'(?i)(?:Dear|Hi|Hello|Hey|Greetings)\s+([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)?)(?=[,:\s])',
            r'(?i)(?:Dear|Hi|Hello|Hey|Greetings)\s+([A-Z][a-zA-Z]+)\s+([A-Z][a-zA-Z]+)(?=[,:\s])',
            r'(?i)(?:Dear|Hi|Hello|Hey|Greetings)\s+([A-Z][a-zA-Z]+)(?=[,:\s])',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # 如果有名和姓，合并
                if len(match.groups()) > 1:
                    return f"Dear {match.group(1)} {match.group(2)}"
                else:
                    return f"Dear {match.group(1)}"
        
        return "Dear Customer"
    
    def extract_product_name(self, text):
        """提取产品名称 - 彻底改进版本"""
        # 将所有换行符替换为空格，以便跨行匹配
        text = re.sub(r'\s+', ' ', text)
        
        # 定义设备关键词
        equipment_keywords = [
            'equipment', 'tester', 'instrument', 'system', 'simulator', 'chamber',
            'gauge', 'meter', 'analyzer', 'controller', 'sensor', 'module', 'unit',
            'kit', 'set', 'apparatus', 'device', 'machine', 'tool', 'test bench',
            'test system', 'test equipment', 'test instrument'
        ]
        
        # 模式1：直接匹配 "attached 产品名称"
        attached_patterns = [
            # 匹配 "attached Proforma Invoice" 这种格式
            r'(?i)attached\s+([A-Z][a-zA-Z0-9\s\-/\.\(\)]+?(?:\s+(?:Proforma\s+)?Invoice|equipment|tester|instrument|system|simulator|chamber|gauge|meter|analyzer))(?=[\s,\.\?]|$)',
            # 匹配 "attached 具体产品名称"
            r'(?i)attached\s+([A-Za-z0-9][A-Za-z0-9\s\-/\.\(\)]+?(?:equipment|tester|instrument|system|simulator|chamber|gauge|meter|analyzer|controller))(?=[\s,\.\?]|$)',
            # 通用attached模式
            r'(?i)attached\s+([A-Za-z0-9][A-Za-z0-9\s\-/\.\(\)]{3,50})(?=[\s,\.\?]|$)',
        ]
        
        for pattern in attached_patterns:
            match = re.search(pattern, text)
            if match:
                product = match.group(1).strip()
                # 清理可能的多余空格
                product = re.sub(r'\s+', ' ', product)
                return product
        
        # 模式2：匹配 "regarding attached 产品"
        regarding_patterns = [
            r'(?i)(?:regarding|about|for|re:|quotation for|inquiry about)\s+(?:the\s+)?attached\s+([A-Za-z0-9][A-Za-z0-9\s\-/\.\(\)]+?(?:equipment|tester|instrument|system))(?=[\s,\.\?]|$)',
            r'(?i)(?:regarding|about)\s+attached\s+([A-Za-z0-9][A-Za-z0-9\s\-/\.\(\)]{3,50})(?=[\s,\.\?]|$)',
        ]
        
        for pattern in regarding_patterns:
            match = re.search(pattern, text)
            if match:
                product = match.group(1).strip()
                product = re.sub(r'\s+', ' ', product)
                return product
        
        # 模式3：匹配 "below 产品"
        below_patterns = [
            r'(?i)(?:below|following)\s+([A-Z][A-Za-z0-9\s\-/\.\(\)]+?(?:equipment|tester|instrument|system|simulator))(?=[\s,\.\?]|$)',
            r'(?i)of\s+below\s+([A-Za-z0-9][A-Za-z0-9\s\-/\.\(\)]{3,50})(?=[\s,\.\?]|$)',
        ]
        
        for pattern in below_patterns:
            match = re.search(pattern, text)
            if match:
                product = match.group(1).strip()
                product = re.sub(r'\s+', ' ', product)
                return product
        
        # 模式4：匹配具体的产品名称（包含型号）
        specific_patterns = [
            # ESD测试设备
            r'(?i)\b(ESD\s+(?:simulator|tester|test\s+equipment|gun|generator))\b',
            r'(?i)\b(ESD\d+[A-Za-z0-9\-/\.]*\s*(?:simulator|tester|test\s+system)?)\b',
            # IP测试设备
            r'(?i)\b(IP\s*(?:testing|test)?\s*equipment)\b',
            r'(?i)\b(IK\s*(?:testing|test)?\s*equipment)\b',
            # EMC测试设备
            r'(?i)\b(EMC\s*(?:testing|test)?\s*equipment)\b',
            # LED测试设备
            r'(?i)\b(LED\s*(?:lighting|test)?\s*equipment)\b',
            # 具体型号
            r'(?i)\b(LPCE-3\s*(?:integrating\s+sphere\s+system)?)\b',
            r'(?i)\b([A-Z]{2,}[A-Za-z0-9\-/\.]*\s+\d+[A-Za-z0-9\-/\.]*\s+[A-Za-z0-9\s\-/\.\(\)]+)\b',
        ]
        
        for pattern in specific_patterns:
            match = re.search(pattern, text)
            if match:
                product = match.group(1).strip()
                product = re.sub(r'\s+', ' ', product)
                return product
        
        # 模式5：匹配通用测试设备
        generic_patterns = [
            r'(?i)\b((?:test\s+)?equipment|tester|instrument|test\s+system|test\s+instrument)\b',
            r'(?i)\b([A-Z][a-zA-Z0-9\s\-/\.]*\s+(?:test\s+)?equipment)\b',
            r'(?i)\b([A-Z][a-zA-Z0-9\s\-/\.]*\s+tester)\b',
            r'(?i)\b([A-Z][a-zA-Z0-9\s\-/\.]*\s+instrument)\b',
        ]
        
        for pattern in generic_patterns:
            match = re.search(pattern, text)
            if match:
                product = match.group(1).strip()
                product = re.sub(r'\s+', ' ', product)
                return product
        
        # 模式6：提取任何看起来像产品名称的较长字符串
        # 寻找包含技术关键词的短语
        tech_patterns = [
            r'\b([A-Z][A-Za-z0-9\s\-/\.\(\)]{5,50}?(?:equipment|tester|instrument|system|simulator|chamber|gauge))\b',
            r'\b([A-Za-z0-9\s\-/\.\(\)]{5,50}?(?:test\s+equipment|test\s+system|test\s+instrument))\b',
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                product = match.strip()
                if len(product.split()) <= 6:  # 不超过6个单词
                    return product
        
        # 如果以上都不匹配，尝试提取任何包含数字和字母的较长字符串
        fallback_pattern = r'\b([A-Z][A-Za-z0-9\s\-/\.\(\)]{4,30})\b'
        matches = re.findall(fallback_pattern, text)
        
        # 过滤掉明显不是产品的字符串
        for match in matches:
            product = match.strip()
            # 排除太短或包含常见非产品词汇的
            exclude_words = ['team', 'company', 'university', 'mail', 'thanks', 
                           'regards', 'hello', 'dear', 'hi', 'good', 'day']
            
            if (len(product) >= 4 and 
                not any(word in product.lower() for word in exclude_words) and
                len(product.split()) <= 5):
                return product
        
        return ""
    
    def extract_and_update_info(self, text):
        """提取信息并更新内部状态"""
        # 提取信息
        self.current_salutation = self.extract_salutation(text)
        self.current_product = self.extract_product_name(text)
        
        # 更新界面显示
        self.salutation_label.setText(f"称呼: {self.current_salutation}")
        if self.current_product:
            # 缩短显示，避免过长
            display_product = self.current_product
            if len(display_product) > 50:
                display_product = display_product[:47] + "..."
            self.product_label.setText(f"产品: {display_product}")
        else:
            self.product_label.setText("产品: 未识别")
        
        return self.current_salutation, self.current_product
    
    def extract_and_display_info(self):
        """提取并显示信息（手动触发）"""
        text = self.input_text.toPlainText()
        self.extract_and_update_info(text)
        self.show_status("✅ 信息提取完成", "green", 2000)
    
    def auto_extract_info(self):
        """自动提取信息（输入时实时触发）"""
        # 只有在有文本内容时才提取
        text = self.input_text.toPlainText().strip()
        if text:
            self.extract_and_update_info(text)
    
    def generate_email_auto(self):
        """生成邮件 - 核心功能"""
        # 获取输入文本
        history_text = self.input_text.toPlainText().strip()
        
        if not history_text:
            self.show_status("⚠️ 请输入内容", "orange")
            return
        
        # 提取信息并更新显示
        salutation, product = self.extract_and_update_info(history_text)
        
        if not product:
            self.show_status("⚠️ 未识别到产品名称", "orange")
            return
        
        # 检查模板
        if not self.openings or not self.bodies or not self.closings:
            self.show_status("⚠️ 模板库为空", "orange")
            return
        
        # 随机选择模板（在当前模板组内随机）
        opening = random.choice(self.openings).replace("{product}", product)
        body = random.choice(self.bodies).replace("{product}", product)
        closing = random.choice(self.closings).replace("{product}", product)
        
        # 构建邮件
        email_lines = [f"{salutation},", ""]
        if opening: email_lines.append(opening)
        if body: 
            if opening: email_lines.append("")
            email_lines.append(body)
        if closing:
            if opening or body: email_lines.append("")
            email_lines.append(closing)
        
        # 显示结果
        email_content = "\n".join(email_lines)
        self.output_text.setPlainText(email_content)
        self.current_email = email_content
        
        # 添加到历史记录
        self.history.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "salutation": salutation,
            "product": product,
            "email": email_content,
            "template_group": self.current_group,
            "original_text": history_text
        })
        
        # 保留最近20条记录
        self.history = self.history[:20]
        
        # 更新状态
        self.show_status(f"✅ 邮件已生成 (使用模板组: {self.current_group})", "green")
        
        # 自动复制
        if self.config.get("auto_copy", True):
            try:
                pyperclip.copy(email_content)
                self.show_status(f"✅ 邮件已生成并复制 (使用模板组: {self.current_group})", "green")
            except Exception as e:
                print(f"复制失败: {e}")
                self.show_status(f"✅ 邮件已生成 (使用模板组: {self.current_group}, 复制失败)", "green")
    
    def quick_edit(self):
        """快速编辑窗口 - 修复版：不再添加前缀"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("快速编辑")
            dialog.setModal(True)
            dialog.resize(400, 180)
            
            layout = QVBoxLayout(dialog)
            
            # 使用当前已识别的信息
            current_salutation = self.current_salutation
            current_product = self.current_product if self.current_product else ""
            
            # 称呼输入
            layout.addWidget(QLabel("称呼:"))
            salutation_edit = QLineEdit()
            salutation_edit.setText(current_salutation)
            salutation_edit.selectAll()
            layout.addWidget(salutation_edit)
            
            # 产品输入 - 只显示产品名称，不添加前缀
            layout.addWidget(QLabel("产品名称:"))
            product_edit = QLineEdit()
            product_edit.setText(current_product)
            layout.addWidget(product_edit)
            
            # 按钮
            button_layout = QHBoxLayout()
            
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_btn)
            
            button_layout.addStretch()
            
            apply_btn = QPushButton("应用并生成")
            apply_btn.setDefault(True)
            apply_btn.clicked.connect(lambda: self.apply_quick_edit_fixed(
                dialog, salutation_edit.text(), product_edit.text()
            ))
            button_layout.addWidget(apply_btn)
            
            layout.addLayout(button_layout)
            
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"快速编辑功能出错: {str(e)}")
    
    def apply_quick_edit_fixed(self, dialog, salutation, product):
        """应用快速编辑 - 修复版：直接使用用户输入的产品名称，不添加前缀"""
        if salutation and product:
            # 更新当前提取的信息
            self.current_salutation = salutation
            self.current_product = product
            
            # 更新界面显示
            self.salutation_label.setText(f"称呼: {salutation}")
            display_product = product
            if len(display_product) > 50:
                display_product = display_product[:47] + "..."
            self.product_label.setText(f"产品: {display_product}")
            
            # 生成邮件（使用更新后的产品名称）
            self.generate_email_with_product(salutation, product)
        
        dialog.accept()
    
    def generate_email_with_product(self, salutation, product):
        """使用给定的称呼和产品名称生成邮件"""
        if not product:
            self.show_status("⚠️ 请输入产品名称", "orange")
            return
        
        # 检查模板
        if not self.openings or not self.bodies or not self.closings:
            self.show_status("⚠️ 模板库为空", "orange")
            return
        
        # 随机选择模板（在当前模板组内随机）
        opening = random.choice(self.openings).replace("{product}", product)
        body = random.choice(self.bodies).replace("{product}", product)
        closing = random.choice(self.closings).replace("{product}", product)
        
        # 构建邮件
        email_lines = [f"{salutation},", ""]
        if opening: email_lines.append(opening)
        if body: 
            if opening: email_lines.append("")
            email_lines.append(body)
        if closing:
            if opening or body: email_lines.append("")
            email_lines.append(closing)
        
        # 显示结果
        email_content = "\n".join(email_lines)
        self.output_text.setPlainText(email_content)
        self.current_email = email_content
        
        # 添加到历史记录
        self.history.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "salutation": salutation,
            "product": product,
            "email": email_content,
            "template_group": self.current_group,
            "original_text": self.input_text.toPlainText().strip()
        })
        
        # 保留最近20条记录
        self.history = self.history[:20]
        
        # 更新状态
        self.show_status(f"✅ 邮件已生成 (使用模板组: {self.current_group})", "green")
        
        # 自动复制
        if self.config.get("auto_copy", True):
            try:
                pyperclip.copy(email_content)
                self.show_status(f"✅ 邮件已生成并复制 (使用模板组: {self.current_group})", "green")
            except Exception as e:
                print(f"复制失败: {e}")
                self.show_status(f"✅ 邮件已生成 (使用模板组: {self.current_group}, 复制失败)", "green")
    
    def show_history(self):
        """显示历史记录"""
        try:
            if not self.history:
                QMessageBox.information(self, "历史记录", "暂无历史记录")
                return
            
            dialog = QDialog(self)
            dialog.setWindowTitle("历史记录")
            dialog.resize(700, 500)
            
            layout = QVBoxLayout(dialog)
            
            # 创建列表显示历史记录
            history_list = QListWidget()
            for record in self.history[:10]:
                # 缩短产品名称显示
                product = record.get('product', 'N/A')
                if len(product) > 30:
                    product = product[:27] + "..."
                
                item_text = (f"{record.get('time', 'N/A')} - "
                           f"{record.get('template_group', 'N/A')} - "
                           f"{record.get('salutation', 'N/A')} - "
                           f"{product}")
                history_list.addItem(item_text)
            
            layout.addWidget(history_list)
            
            # 操作按钮
            button_layout = QHBoxLayout()
            
            use_btn = QPushButton("使用此邮件")
            use_btn.clicked.connect(lambda: self.use_selected_history(history_list, dialog))
            button_layout.addWidget(use_btn)
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"显示历史记录出错: {str(e)}")
    
    def use_selected_history(self, history_list, dialog):
        """使用选中的历史记录"""
        selected_items = history_list.selectedItems()
        if selected_items:
            index = history_list.row(selected_items[0])
            if 0 <= index < len(self.history):
                record = self.history[index]
                self.input_text.setPlainText(record.get('original_text', ''))
                
                # 如果历史记录中有模板组信息，则切换到对应的模板组
                if "template_group" in record and record["template_group"] in self.template_groups:
                    self.template_group_combo.setCurrentText(record["template_group"])
                    self.change_template_group(record["template_group"])
                
                self.generate_email_auto()
                dialog.accept()
    
    def copy_text(self, text):
        """复制文本到剪贴板"""
        try:
            pyperclip.copy(text)
            self.show_status("✅ 已复制", "green")
        except Exception as e:
            self.show_status(f"❌ 复制失败: {e}", "red")
    
    def copy_email(self):
        """复制邮件到剪贴板"""
        if not self.current_email:
            self.show_status("⚠️ 没有可复制的内容", "orange")
            return
        
        try:
            pyperclip.copy(self.current_email)
            self.show_status("✅ 已复制到剪贴板", "green")
        except Exception as e:
            self.show_status(f"❌ 复制失败: {e}", "red")
    
    def save_email(self):
        """保存邮件到文件"""
        try:
            if not self.current_email:
                self.show_status("⚠️ 没有可保存的内容", "orange")
                return
            
            # 提取产品名作为默认文件名
            product_match = re.search(r'about\s+([^.,]+)', self.current_email, re.IGNORECASE)
            if product_match:
                product = product_match.group(1).strip()[:30]
                default_name = f"邮件_{product.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            else:
                default_name = f"邮件_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "保存邮件",
                default_name,
                "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.current_email)
                self.show_status(f"✅ 已保存到: {os.path.basename(filepath)}", "green")
        except Exception as e:
            self.show_status(f"❌ 保存失败: {str(e)[:30]}", "red")
    
    def toggle_auto_copy(self):
        """切换自动复制设置"""
        self.config["auto_copy"] = self.auto_copy_checkbox.isChecked()
        self.save_config()
        status = "开启" if self.config["auto_copy"] else "关闭"
        self.show_status(f"✅ 自动复制已{status}", "green", 1500)
    
    def show_settings(self):
        """显示设置窗口 - 包含模板组管理"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("设置 - 模板组管理")
            dialog.resize(800, 600)
            
            layout = QVBoxLayout(dialog)
            
            # 使用选项卡组织设置项
            tab_widget = QTabWidget()
            layout.addWidget(tab_widget)
            
            # 模板组管理选项卡
            groups_tab = self.create_template_groups_tab()
            tab_widget.addTab(groups_tab, "模板组管理")
            
            # 模板编辑选项卡
            template_tab = self.create_template_editor_tab()
            tab_widget.addTab(template_tab, "模板编辑")
            
            # 应用设置选项卡
            settings_tab = self.create_settings_tab()
            tab_widget.addTab(settings_tab, "应用设置")
            
            # 按钮
            button_layout = QHBoxLayout()
            
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_btn)
            
            button_layout.addStretch()
            
            save_btn = QPushButton("保存并关闭")
            save_btn.clicked.connect(lambda: self.save_settings(dialog))
            button_layout.addWidget(save_btn)
            
            layout.addLayout(button_layout)
            
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"设置窗口出错: {str(e)}")
    
    def create_template_groups_tab(self):
        """创建模板组管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 模板组列表
        self.groups_list = QListWidget()
        self.groups_list.addItems(self.template_groups.keys())
        if self.current_group in self.template_groups:
            index = list(self.template_groups.keys()).index(self.current_group)
            self.groups_list.setCurrentRow(index)
        layout.addWidget(self.groups_list)
        
        # 组操作按钮
        groups_btn_layout = QHBoxLayout()
        
        new_group_btn = QPushButton("新建模板组")
        new_group_btn.clicked.connect(self.create_new_template_group_ui)
        groups_btn_layout.addWidget(new_group_btn)
        
        rename_group_btn = QPushButton("重命名组")
        rename_group_btn.clicked.connect(self.rename_template_group_ui)
        groups_btn_layout.addWidget(rename_group_btn)
        
        delete_group_btn = QPushButton("删除组")
        delete_group_btn.clicked.connect(self.delete_template_group_ui)
        delete_group_btn.setStyleSheet("background-color: #dc3545;")
        groups_btn_layout.addWidget(delete_group_btn)
        
        groups_btn_layout.addStretch()
        
        # 设为默认按钮
        set_default_btn = QPushButton("设为当前使用组")
        set_default_btn.clicked.connect(self.set_current_template_group_ui)
        set_default_btn.setObjectName("primary")
        groups_btn_layout.addWidget(set_default_btn)
        
        layout.addLayout(groups_btn_layout)
        
        # 组描述编辑
        layout.addWidget(QLabel("组描述:"))
        self.group_desc_edit = QTextEdit()
        self.group_desc_edit.setMaximumHeight(80)
        self.group_desc_edit.setPlaceholderText("输入模板组的描述信息...")
        
        # 当选择不同组时更新描述
        self.groups_list.itemSelectionChanged.connect(self.update_group_desc_edit)
        self.update_group_desc_edit()
        
        layout.addWidget(self.group_desc_edit)
        
        return widget
    
    def create_template_editor_tab(self):
        """创建模板编辑标签页 - 修复版：独立存储每个模板组"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 模板组选择（用于编辑）
        layout.addWidget(QLabel("选择要编辑的模板组:"))
        self.editor_group_combo = QComboBox()
        self.editor_group_combo.addItems(self.template_groups.keys())
        self.editor_group_combo.setCurrentText(self.current_group)
        # 关键修复：当选择不同模板组时，重新加载对应的模板内容
        self.editor_group_combo.currentTextChanged.connect(self.on_editor_group_changed)
        layout.addWidget(self.editor_group_combo)
        
        layout.addSpacing(10)
        
        # 模板类型选择
        layout.addWidget(QLabel("选择模板类型:"))
        self.template_type_combo = QComboBox()
        self.template_type_combo.addItems(["开头模板 (openings)", "正文模板 (bodies)", "结尾模板 (closings)"])
        self.template_type_combo.currentTextChanged.connect(self.on_template_type_changed)
        layout.addWidget(self.template_type_combo)
        
        # 编辑器
        self.template_editor = QTextEdit()
        self.template_editor.setMinimumHeight(300)
        self.template_editor.setPlaceholderText("每行一个模板句子，使用 {product} 作为产品占位符...")
        layout.addWidget(self.template_editor)
        
        # 提示标签
        hint_label = QLabel("提示：每行一个模板，使用 {product} 作为产品名称占位符")
        hint_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(hint_label)
        
        # 初始加载当前选中模板组的内容
        self.current_editor_group = self.current_group
        self.current_template_type = "openings"
        self.load_template_editor_content()
        
        return widget
    
    def on_editor_group_changed(self, group_name):
        """当编辑器中的模板组选择改变时触发"""
        if group_name in self.template_groups:
            self.current_editor_group = group_name
            # 重新加载该组的模板内容
            self.load_template_editor_content()
    
    def on_template_type_changed(self, template_type_text):
        """当模板类型改变时触发"""
        # 解析模板类型
        if "开头" in template_type_text:
            new_type = "openings"
        elif "正文" in template_type_text:
            new_type = "bodies"
        elif "结尾" in template_type_text:
            new_type = "closings"
        else:
            return
        
        # 只有在类型真正改变时才重新加载
        if new_type != self.current_template_type:
            self.current_template_type = new_type
            self.load_template_editor_content()
    
    def load_template_editor_content(self):
        """加载当前选中的模板组和类型的内容到编辑器"""
        try:
            if not hasattr(self, 'template_editor'):
                return
            
            # 获取当前选中的模板组
            group_name = getattr(self, 'current_editor_group', self.current_group)
            if group_name not in self.template_groups:
                return
            
            # 获取当前类型的模板
            templates = self.template_groups[group_name].get(self.current_template_type, [])
            
            # 显示到编辑器
            self.template_editor.clear()
            self.template_editor.setPlainText("\n".join(templates))
        except Exception as e:
            print(f"加载模板编辑器内容失败: {e}")
    
    def create_settings_tab(self):
        """创建应用设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 设置选项
        self.auto_copy_checkbox_settings = QCheckBox("自动复制到剪贴板")
        self.auto_copy_checkbox_settings.setChecked(self.config.get("auto_copy", True))
        layout.addWidget(self.auto_copy_checkbox_settings)
        
        self.auto_generate_checkbox = QCheckBox("输入时自动提取信息")
        self.auto_generate_checkbox.setChecked(self.config.get("auto_generate", True))
        layout.addWidget(self.auto_generate_checkbox)
        
        layout.addStretch()
        
        # 说明文本
        info_label = QLabel("注意：设置更改将在重启程序后生效")
        info_label.setStyleSheet("color: #6c757d; font-style: italic;")
        layout.addWidget(info_label)
        
        return widget
    
    def update_group_desc_edit(self):
        """更新组描述编辑框"""
        selected_items = self.groups_list.selectedItems()
        if selected_items:
            group_name = selected_items[0].text()
            if group_name in self.template_groups:
                desc = self.template_groups[group_name].get("description", "")
                self.group_desc_edit.setPlainText(desc)
    
    def create_new_template_group(self):
        """创建新的模板组"""
        # 直接调用UI版本
        self.create_new_template_group_ui()
    
    def create_new_template_group_ui(self):
        """创建新的模板组（UI版本）"""
        try:
            # 获取新组名
            new_group_name, ok = QInputDialog.getText(
                self, "新建模板组", "请输入新模板组名称:"
            )
            
            if ok and new_group_name:
                # 检查是否已存在
                if new_group_name in self.template_groups:
                    QMessageBox.warning(self, "错误", "模板组名称已存在！")
                    return
                
                # 获取描述
                desc, desc_ok = QInputDialog.getText(
                    self, "模板组描述", "请输入模板组描述:"
                )
                
                # 创建新组（基于当前组复制或使用默认值）
                base_group = self.current_group if self.current_group in self.template_groups else "默认"
                
                new_group = {
                    "description": desc if desc_ok and desc else "新模板组",
                    "openings": self.template_groups.get(base_group, {}).get("openings", []).copy(),
                    "bodies": self.template_groups.get(base_group, {}).get("bodies", []).copy(),
                    "closings": self.template_groups.get(base_group, {}).get("closings", []).copy()
                }
                
                # 添加到分组列表
                self.template_groups[new_group_name] = new_group
                
                # 更新UI
                self.groups_list.addItem(new_group_name)
                self.template_group_combo.addItem(new_group_name)
                
                # 同时更新编辑器中的下拉框
                if hasattr(self, 'editor_group_combo'):
                    self.editor_group_combo.addItem(new_group_name)
                
                # 选择新组
                self.groups_list.setCurrentRow(self.groups_list.count() - 1)
                
                # 更新描述
                self.group_desc_edit.setPlainText(new_group["description"])
                
                QMessageBox.information(self, "成功", f"已创建模板组: {new_group_name}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"创建模板组失败: {str(e)}")
    
    def rename_template_group_ui(self):
        """重命名模板组"""
        try:
            selected_items = self.groups_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "提示", "请先选择一个模板组")
                return
            
            old_name = selected_items[0].text()
            
            # 获取新名称
            new_name, ok = QInputDialog.getText(
                self, "重命名模板组", "请输入新名称:", text=old_name
            )
            
            if ok and new_name and new_name != old_name:
                # 检查是否已存在
                if new_name in self.template_groups:
                    QMessageBox.warning(self, "错误", "模板组名称已存在！")
                    return
                
                # 重命名
                self.template_groups[new_name] = self.template_groups.pop(old_name)
                
                # 更新UI
                self.groups_list.currentItem().setText(new_name)
                
                # 更新组合框
                index = self.template_group_combo.findText(old_name)
                if index >= 0:
                    self.template_group_combo.setItemText(index, new_name)
                
                # 同时更新编辑器中的下拉框
                if hasattr(self, 'editor_group_combo'):
                    editor_index = self.editor_group_combo.findText(old_name)
                    if editor_index >= 0:
                        self.editor_group_combo.setItemText(editor_index, new_name)
                
                # 如果当前组被重命名，更新当前组
                if self.current_group == old_name:
                    self.current_group = new_name
                    self.config["current_template_group"] = new_name
                
                # 如果编辑器当前选中的是被重命名的组，更新编辑器组名
                if hasattr(self, 'current_editor_group') and self.current_editor_group == old_name:
                    self.current_editor_group = new_name
                
                QMessageBox.information(self, "成功", f"已重命名为: {new_name}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"重命名模板组失败: {str(e)}")
    
    def delete_template_group_ui(self):
        """删除模板组"""
        try:
            selected_items = self.groups_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "提示", "请先选择一个模板组")
                return
            
            group_name = selected_items[0].text()
            
            # 检查是否是最后一个组
            if len(self.template_groups) <= 1:
                QMessageBox.warning(self, "错误", "不能删除最后一个模板组！")
                return
            
            # 确认删除
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除模板组 '{group_name}' 吗？\n此操作不可撤销！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 从数据结构中删除
                del self.template_groups[group_name]
                
                # 从列表中删除
                self.groups_list.takeItem(self.groups_list.row(selected_items[0]))
                
                # 从组合框中删除
                index = self.template_group_combo.findText(group_name)
                if index >= 0:
                    self.template_group_combo.removeItem(index)
                
                # 同时从编辑器下拉框中删除
                if hasattr(self, 'editor_group_combo'):
                    editor_index = self.editor_group_combo.findText(group_name)
                    if editor_index >= 0:
                        self.editor_group_combo.removeItem(editor_index)
                
                # 如果删除的是当前组，切换到第一个组
                if self.current_group == group_name:
                    new_group = list(self.template_groups.keys())[0]
                    self.current_group = new_group
                    self.config["current_template_group"] = new_group
                    self.template_group_combo.setCurrentText(new_group)
                    self.change_template_group(new_group)
                
                # 如果删除的是编辑器当前选中的组，切换到第一个组
                if hasattr(self, 'current_editor_group') and self.current_editor_group == group_name:
                    new_editor_group = list(self.template_groups.keys())[0]
                    self.current_editor_group = new_editor_group
                    if hasattr(self, 'editor_group_combo'):
                        self.editor_group_combo.setCurrentText(new_editor_group)
                    self.load_template_editor_content()
                
                QMessageBox.information(self, "成功", f"已删除模板组: {group_name}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"删除模板组失败: {str(e)}")
    
    def set_current_template_group_ui(self):
        """设为当前使用组"""
        selected_items = self.groups_list.selectedItems()
        if selected_items:
            group_name = selected_items[0].text()
            self.template_group_combo.setCurrentText(group_name)
            self.change_template_group(group_name)
    
    def save_settings(self, dialog):
        """保存所有设置"""
        try:
            # 1. 保存模板组描述
            selected_items = self.groups_list.selectedItems()
            if selected_items:
                group_name = selected_items[0].text()
                if group_name in self.template_groups:
                    desc = self.group_desc_edit.toPlainText()
                    self.template_groups[group_name]["description"] = desc
            
            # 2. 保存模板编辑内容（关键修复：保存当前编辑器中选中的模板组）
            if hasattr(self, 'template_editor') and hasattr(self, 'current_editor_group'):
                editor_group = self.current_editor_group
                if editor_group in self.template_groups:
                    content = self.template_editor.toPlainText()
                    templates = [line.strip() for line in content.split('\n') if line.strip()]
                    self.template_groups[editor_group][self.current_template_type] = templates
            
            # 3. 保存应用设置
            self.config["auto_copy"] = self.auto_copy_checkbox_settings.isChecked()
            self.config["auto_generate"] = self.auto_generate_checkbox.isChecked()
            
            # 4. 保存所有数据
            self.save_template_groups()
            self.save_config()
            
            # 5. 重新加载当前模板组（确保使用的是最新保存的数据）
            if self.current_group in self.template_groups:
                self.openings = self.template_groups[self.current_group]["openings"]
                self.bodies = self.template_groups[self.current_group]["bodies"]
                self.closings = self.template_groups[self.current_group]["closings"]
            
            dialog.accept()
            self.show_status("✅ 所有设置已保存", "green")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存设置失败: {str(e)}")
    
    def show_status(self, message, color="black", duration=3000):
        """显示状态消息"""
        self.status_label.setText(f"{message} (模板组: {self.current_group})")
        
        # 根据颜色设置文本颜色
        if color == "green":
            self.status_label.setStyleSheet("color: #28a745; font-weight: 500;")
        elif color == "orange":
            self.status_label.setStyleSheet("color: #fd7e14; font-weight: 500;")
        elif color == "red":
            self.status_label.setStyleSheet("color: #dc3545; font-weight: 500;")
        else:
            self.status_label.setStyleSheet("color: #6c757d;")
        
        # 定时恢复
        QTimer.singleShot(duration, lambda: self.status_label.setText(
            f"就绪 - 当前模板组: {self.current_group} - 输入内容后按 Enter 键生成邮件"
        ))
    
    def clear_all(self):
        """清空所有内容"""
        self.input_text.clear()
        self.output_text.clear()
        self.current_email = ""
        self.current_salutation = "Dear Customer"
        self.current_product = ""
        self.salutation_label.setText("称呼: 未识别")
        self.product_label.setText("产品: 未识别")
        self.show_status("已清空", "gray", 1500)
    
    def clear_input(self):
        """清空输入"""
        self.input_text.clear()
        self.current_salutation = "Dear Customer"
        self.current_product = ""
        self.salutation_label.setText("称呼: 未识别")
        self.product_label.setText("产品: 未识别")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序名称
    app.setApplicationName("外贸邮件极速生成器 - 专业版")
    
    # 创建并显示主窗口
    window = EmailGeneratorGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()