#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دبیر — ابزار نوشتن صحنه‌محور (نسخهٔ Qt)
اجرا:  python dabir.py
نیازمندی: PySide6 یا PyQt5 (هرکدام که نصب باشد).
"""

import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

QT = None
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    QT = "PySide6"
except ImportError:  # pragma: no cover
    from PyQt5 import QtCore, QtGui, QtWidgets
    QT = "PyQt5"

Qt = QtCore.Qt

QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
QShortcut = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut


def font_families():
    try:
        return set(QtGui.QFontDatabase.families())
    except TypeError:  # pragma: no cover
        return set(QtGui.QFontDatabase().families())


def run_dialog(dlg):
    return dlg.exec() if hasattr(dlg, "exec") else dlg.exec_()


try:
    PROP_BLOCK = QtGui.QTextFormat.Property.UserProperty
except AttributeError:  # pragma: no cover
    PROP_BLOCK = QtGui.QTextFormat.UserProperty

import sw_core as C  # noqa: E402

CONFIG_PATH = os.path.join(HERE, "sw_config.json")
FONT_CANDIDATES = ["Vazirmatn", "Vazir", "Sahel", "Shabnam", "IRANSans",
                   "Tahoma", "Segoe UI", "DejaVu Sans"]
ZWNJ = "\u200c"

THEMES = {
    "روشن": dict(
        bg="#ffffff", fg="#252523", panel="#faf9f5", panel_fg="#3d3d3a",
        muted="#8a8a86", border="#d8d6cd", sep="#8a8a86",
        chip_bg="#e6f1fb", chip_fg="#0c447c", sel_bg="#cfe3f7",
        blocks={
            C.BLOCK_PLAIN:     dict(indent=0,  color="#252523", bg=None,
                                    italic=False),
            C.BLOCK_DREAM:     dict(indent=32, color="#534ab7", bg=None,
                                    italic=True),
            C.BLOCK_INTERLUDE: dict(indent=32, color="#4a4a46", bg="#f1efe8",
                                    italic=False),
            C.BLOCK_QUOTE:     dict(indent=48, color="#0f6e56", bg=None,
                                    italic=False),
        }),
    "تاریک": dict(
        bg="#1c1c1a", fg="#e6e4dd", panel="#232321", panel_fg="#c9c7bf",
        muted="#8a8a86", border="#3a3a36", sep="#7d7c76",
        chip_bg="#1e3a52", chip_fg="#9ecbf0", sel_bg="#2f4d68",
        blocks={
            C.BLOCK_PLAIN:     dict(indent=0,  color="#e6e4dd", bg=None,
                                    italic=False),
            C.BLOCK_DREAM:     dict(indent=32, color="#a9a2f0", bg=None,
                                    italic=True),
            C.BLOCK_INTERLUDE: dict(indent=32, color="#c2bfb4", bg="#2b2b28",
                                    italic=False),
            C.BLOCK_QUOTE:     dict(indent=48, color="#67c2a4", bg=None,
                                    italic=False),
        }),
}


def load_config():
    cfg = {"plot_path": "", "data_dir": "", "font": "", "font_size": 14,
           "target_words": 100000, "separator": C.SEPARATOR,
           "theme": "روشن"}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def pick_font(wanted):
    fams = font_families()
    for f in ([wanted] if wanted else []) + FONT_CANDIDATES:
        if f and f in fams:
            return f, f in ("Vazirmatn", wanted)
    return "", False


# ------------------------------------------------------------------ ویرایشگر

class Editor(QtWidgets.QTextEdit):
    """QTextEdit با جهت پایهٔ راست‌به‌چپ و بلوک‌های نوع‌دار."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setTabChangesFocus(True)
        self.document().setDefaultTextOption(self._text_option())
        self.setViewportMargins(12, 8, 12, 8)

    @staticmethod
    def _text_option():
        opt = QtGui.QTextOption()
        opt.setTextDirection(Qt.RightToLeft)
        opt.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        opt.setWrapMode(QtGui.QTextOption.WrapMode.WordWrap
                        if hasattr(QtGui.QTextOption, "WrapMode")
                        else QtGui.QTextOption.WordWrap)
        return opt

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space and (ev.modifiers() & Qt.ControlModifier):
            self.insertPlainText(ZWNJ)
            return
        super().keyPressEvent(ev)


def force_rtl(doc, skip_centered=True):
    """جهت و راست‌چینی را برنامه‌ای روی همهٔ پاراگراف‌ها اعمال می‌کند."""
    try:
        center = Qt.AlignmentFlag.AlignHCenter
        right = Qt.AlignmentFlag.AlignRight
        absol = Qt.AlignmentFlag.AlignAbsolute
    except AttributeError:  # pragma: no cover
        center, right, absol = Qt.AlignHCenter, Qt.AlignRight, Qt.AlignAbsolute
    b = doc.begin()
    while b.isValid():
        if not (skip_centered and (b.blockFormat().alignment() & center)):
            bf = QtGui.QTextBlockFormat()
            bf.setAlignment(right | absol)
            bf.setLayoutDirection(Qt.RightToLeft)
            QtGui.QTextCursor(b).mergeBlockFormat(bf)
        b = b.next()
    opt = doc.defaultTextOption()
    opt.setTextDirection(Qt.RightToLeft)
    opt.setAlignment(right | absol)
    doc.setDefaultTextOption(opt)


def block_type_of(block):
    fmt = block.blockFormat()
    val = fmt.property(PROP_BLOCK)
    if isinstance(val, str) and val in C.BLOCK_TYPES:
        return val
    return C.BLOCK_PLAIN


def style_block(cursor, name, theme):
    st = theme["blocks"][name]
    bf = QtGui.QTextBlockFormat()
    bf.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
    bf.setLayoutDirection(Qt.RightToLeft)
    bf.setLeftMargin(st["indent"])
    bf.setRightMargin(st["indent"])
    bf.setTopMargin(2)
    bf.setBottomMargin(10)
    bf.setProperty(PROP_BLOCK, name)
    if st["bg"]:
        bf.setBackground(QtGui.QColor(st["bg"]))
    cursor.setBlockFormat(bf)

    cf = QtGui.QTextCharFormat()
    cf.setFontItalic(bool(st["italic"]))
    cf.setForeground(QtGui.QColor(st["color"]))
    sel = QtGui.QTextCursor(cursor)
    sel.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock
                     if hasattr(QtGui.QTextCursor, "MoveOperation")
                     else QtGui.QTextCursor.StartOfBlock)
    sel.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock
                     if hasattr(QtGui.QTextCursor, "MoveOperation")
                     else QtGui.QTextCursor.EndOfBlock,
                     QtGui.QTextCursor.MoveMode.KeepAnchor
                     if hasattr(QtGui.QTextCursor, "MoveMode")
                     else QtGui.QTextCursor.KeepAnchor)
    sel.mergeCharFormat(cf)


# ------------------------------------------------------------- پنجرهٔ پلات

class RtlLineEdit(QtWidgets.QLineEdit):
    """تک‌خطیِ راست‌به‌چپ با نیم‌فاصلهٔ Ctrl+Space."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space and (ev.modifiers() & Qt.ControlModifier):
            self.insert(ZWNJ)
            return
        super().keyPressEvent(ev)


class RtlPlainEdit(QtWidgets.QPlainTextEdit):
    """چندخطیِ راست‌به‌چپ؛ جهتِ پاراگراف صریح است، نه موروثی."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.document().setDefaultTextOption(Editor._text_option())

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space and (ev.modifiers() & Qt.ControlModifier):
            self.insertPlainText(ZWNJ)
            return
        super().keyPressEvent(ev)

    def setPlainText(self, text):
        super().setPlainText(text)
        force_rtl(self.document(), skip_centered=False)


Signal = getattr(QtCore, "Signal", None) or QtCore.pyqtSignal
ROLE = Qt.UserRole


class PlotPane(QtWidgets.QWidget):
    """ویرایشِ ساختارِ پلات: افزودن، ویرایش، حذف و جابه‌جاییِ صحنه و فصل."""

    plotSaved = Signal(str)

    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.doc = None
        self.sel = None          # ایندکسِ تکهٔ انتخاب‌شده
        self.loading = False
        self._build()

    # ---------------------------------------------------------------- UI

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 6)
        lay.setSpacing(6)

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(4)

        def mk(text, slot, tip=""):
            b = QtWidgets.QPushButton(text)
            b.setFont(self.main.ui_font())
            b.clicked.connect(slot)
            if tip:
                b.setToolTip(tip)
            bar.addWidget(b)
            return b

        self.b_up = mk("↑", lambda: self.move_sel(-1), "یک پله بالا")
        self.b_down = mk("↓", lambda: self.move_sel(1), "یک پله پایین")
        bar.addSpacing(10)
        mk("صحنهٔ نو", self.new_scene)
        mk("فصل نو", self.new_chapter)
        mk("بخش نو", self.new_part)
        mk("حذف", self.delete_sel)
        bar.addSpacing(10)
        mk("انتقال به فصل…", self.move_to_chapter)
        bar.addStretch(1)
        self.lbl_file = QtWidgets.QLabel("")
        self.lbl_file.setFont(self.main.ui_font(8))
        self.lbl_file.setStyleSheet("color:#8a8a86;")
        bar.addWidget(self.lbl_file)
        mk("ذخیره در پلات", self.save, "Ctrl+Shift+S")
        mk("نسخهٔ جدید…", self.save_as_version,
           "فایل را دست‌نخورده می‌گذارد و نسخهٔ بعدی را می‌سازد")
        lay.addLayout(bar)

        split = QtWidgets.QSplitter(Qt.Horizontal)
        split.setLayoutDirection(Qt.RightToLeft)
        split.setHandleWidth(8)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setLayoutDirection(Qt.RightToLeft)
        self.tree.setHeaderLabels(["ساختار", "زمان"])
        self.tree.setColumnWidth(0, 330)
        self.tree.setFont(self.main.ui_font())
        self.tree.currentItemChanged.connect(self.on_pick)
        split.addWidget(self.tree)

        right = QtWidgets.QWidget()
        rl = QtWidgets.QFormLayout(right)
        rl.setLabelAlignment(Qt.AlignRight)
        self.f_sid = RtlLineEdit()
        self.f_title = RtlLineEdit()
        self.f_chapter = RtlLineEdit()
        self.f_time = RtlLineEdit()
        for w in (self.f_sid, self.f_title, self.f_chapter, self.f_time):
            w.setFont(self.main.ui_font(11))
            w.editingFinished.connect(self.apply_form)
        self.f_chapter.setToolTip("فصلی که در براکتِ خودِ صحنه نوشته می‌شود — "
                                  "یادداشت‌هایی مثل «ف۱۰٫۵» اینجا می‌ماند.")
        self.f_sid.setAlignment(Qt.AlignLeft | Qt.AlignAbsolute)
        rl.addRow("شناسه", self.f_sid)
        rl.addRow("عنوان", self.f_title)
        rl.addRow("فصل (براکت)", self.f_chapter)
        rl.addRow("زمان", self.f_time)

        self.f_body = RtlPlainEdit()
        self.f_body.setFont(self.main.body_font(max(10, self.main.size - 2)))
        self.f_body.setPlaceholderText(
            "توضیح صحنه و تگ‌ها — همان خطوطی که در فایل پلات می‌نشیند.\n"
            "*تگ:* مقدار")
        cap = QtWidgets.QLabel("توضیح و تگ‌ها (خامِ md)")
        cap.setFont(self.main.ui_font(8))
        cap.setStyleSheet("color:#8a8a86;")
        rl.addRow(cap)
        rl.addRow(self.f_body)
        self.f_body.textChanged.connect(self._body_touched)
        split.addWidget(right)
        split.setSizes([520, 620])
        lay.addWidget(split, 1)

        self.hint = QtWidgets.QLabel("")
        self.hint.setFont(self.main.ui_font(9))
        self.hint.setStyleSheet("color:#8a8a86;")
        lay.addWidget(self.hint)

    # ------------------------------------------------------------ داده

    def set_doc(self, doc):
        self.doc = doc
        self.lbl_file.setText(os.path.basename(doc.path) if doc else "")
        self.refresh()

    def refresh(self, keep=None):
        if not self.doc:
            return
        self.loading = True
        self.tree.clear()
        part_node = chap_node = None
        keep_item = None
        for idx, it in enumerate(self.doc.items):
            if it.kind == C.KIND_PART:
                part_node = QtWidgets.QTreeWidgetItem(self.tree,
                                                      [it.label or "بخش", ""])
                part_node.setData(0, ROLE, idx)
                part_node.setTextAlignment(0, Qt.AlignRight | Qt.AlignVCenter)
                part_node.setExpanded(True)
                chap_node = None
            elif it.kind == C.KIND_CHAPTER:
                parent = part_node or self.tree
                chap_node = QtWidgets.QTreeWidgetItem(parent,
                                                      [it.chapter_label, ""])
                chap_node.setData(0, ROLE, idx)
                chap_node.setTextAlignment(0, Qt.AlignRight | Qt.AlignVCenter)
                chap_node.setExpanded(True)
            elif it.kind == C.KIND_SCENE:
                parent = chap_node or part_node or self.tree
                node = QtWidgets.QTreeWidgetItem(parent,
                                                 [it.scene_label, it.time])
                node.setData(0, ROLE, idx)
                node.setTextAlignment(0, Qt.AlignRight | Qt.AlignVCenter)
                node.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                if keep is not None and idx == keep:
                    keep_item = node
        if keep_item is not None:
            self.tree.setCurrentItem(keep_item)   # هنوز loading=True است
            self.sel = keep
        elif self.sel is not None and self.sel >= len(self.doc.items):
            self.sel = None
        self.loading = False
        self.fill_form()
        self.update_hint()

    def update_hint(self):
        if not self.doc:
            return
        n = len(self.doc.scene_indices())
        self.hint.setText("%s صحنه · %s فصل%s"
                          % (C.fa_num(n),
                             C.fa_num(len(self.doc.chapter_indices())),
                             "  ·  ذخیره‌نشده" if self.doc.dirty else ""))

    def current_index(self):
        it = self.tree.currentItem()
        return None if it is None else it.data(0, ROLE)

    def on_pick(self, cur, prev):
        if self.loading:
            return
        self.apply_form()
        self.sel = None if cur is None else cur.data(0, ROLE)
        self.fill_form()

    def fill_form(self):
        self.loading = True
        idx = self.sel
        it = self.doc.items[idx] if (self.doc and idx is not None) else None
        is_scene = bool(it and it.kind == C.KIND_SCENE)
        for w in (self.f_sid, self.f_title, self.f_chapter, self.f_time):
            w.setEnabled(is_scene)
        self.f_body.setEnabled(bool(it))
        if it is None:
            for w in (self.f_sid, self.f_title, self.f_chapter, self.f_time):
                w.setText("")
            self.f_body.setPlainText("")
        elif is_scene:
            self.f_sid.setText(it.sid)
            self.f_title.setText(it.title)
            self.f_chapter.setText(it.chapter)
            self.f_time.setText(it.time)
            self.f_body.setPlainText(it.body)
        else:                       # فصل یا بخش: فقط متنِ خام
            self.f_sid.setText("")
            self.f_title.setText(it.chapter_label if it.kind == C.KIND_CHAPTER
                                 else it.label)
            self.f_title.setEnabled(True)
            self.f_chapter.setText("")
            self.f_time.setText("")
            self.f_body.setPlainText(it.body)
        self.loading = False

    def _body_touched(self):
        if not self.loading and self.doc:
            self.doc.dirty = True
            self.update_hint()

    def apply_form(self):
        """فرم را روی مدل می‌نشاند (هنوز روی دیسک نوشته نمی‌شود)."""
        if self.loading or not self.doc or self.sel is None:
            return
        if self.sel >= len(self.doc.items):
            return
        it = self.doc.items[self.sel]
        if it.kind == C.KIND_SCENE:
            sid = self.f_sid.text().strip()
            if sid and sid != it.sid and self.doc.sid_exists(sid, self.sel):
                QtWidgets.QMessageBox.warning(self, "شناسهٔ تکراری",
                                              "شناسهٔ %s قبلاً هست." % sid)
                self.f_sid.setText(it.sid)
                return
            self.doc.set_scene(self.sel, sid=sid,
                               title=self.f_title.text(),
                               chapter=self.f_chapter.text(),
                               time=self.f_time.text(),
                               body=self.f_body.toPlainText())
        elif it.kind == C.KIND_CHAPTER:
            txt = self.f_title.text().strip()
            name, _, title = txt.partition(C.DASH)
            self.doc.set_chapter(self.sel, name=name.strip(),
                                 title=title.strip())
            it.set_body(self.f_body.toPlainText())
            self.doc.dirty = True
        elif it.kind == C.KIND_PART:
            self.doc.set_part(self.sel, self.f_title.text())
            it.set_body(self.f_body.toPlainText())
            self.doc.dirty = True
        self.update_hint()

    # ---------------------------------------------------------- عملیات

    def _need(self, kinds=(C.KIND_SCENE,)):
        if not self.doc or self.sel is None:
            return None
        it = self.doc.items[self.sel]
        if it.kind not in kinds:
            self.main.note("این کار روی «%s» نیست." % it.kind)
            return None
        return it

    def move_sel(self, delta):
        if not self.doc or self.sel is None:
            return
        self.apply_form()
        kind = self.doc.items[self.sel].kind
        if kind == C.KIND_SCENE:
            pos = self.doc.move_scene(self.sel, delta)
        elif kind == C.KIND_CHAPTER:
            pos = self.doc.move_chapter(self.sel, delta)
        else:
            pos = self.doc.move_part(self.sel, delta)
        if pos is None:
            return
        self.sel = pos
        self.refresh(keep=pos)

    def new_scene(self):
        if not self.doc:
            return
        self.apply_form()
        idx = self.sel
        kind = self.doc.items[idx].kind if idx is not None else None
        if kind == C.KIND_SCENE:
            pos = self.doc.add_scene(after=idx, title="صحنهٔ تازه")
        elif kind == C.KIND_CHAPTER:
            pos = self.doc.add_scene(chapter_index=idx, title="صحنهٔ تازه")
        else:
            chs = self.doc.chapter_indices()
            if not chs:
                QtWidgets.QMessageBox.information(
                    self, "فصل لازم است", "اول یک فصل بساز.")
                return
            pos = self.doc.add_scene(chapter_index=chs[-1], title="صحنهٔ تازه")
        self.sel = pos
        self.refresh(keep=pos)
        self.f_title.setFocus()
        self.f_title.selectAll()

    def new_chapter(self):
        if not self.doc:
            return
        self.apply_form()
        name, ok = QtWidgets.QInputDialog.getText(
            self, "فصل نو", "نام و عنوان فصل (مثل «ف۳ — سالنِ نور»)")
        if not ok or not name.strip():
            return
        n, _, t = name.partition(C.DASH)
        idx = self.sel
        ci = None if idx is None else (
            idx if self.doc.items[idx].kind == C.KIND_CHAPTER
            else self.doc.chapter_of(idx))
        pi = None if idx is None else self.doc.part_of(idx)
        pos = self.doc.add_chapter(n.strip(), t.strip(), after_chapter=ci,
                                   part_index=pi if ci is None else None)
        self.sel = pos
        self.refresh(keep=pos)

    def new_part(self):
        if not self.doc:
            return
        self.apply_form()
        label, ok = QtWidgets.QInputDialog.getText(
            self, "بخش نو", "برچسب بخش (مثل «بخش دو»)")
        if not ok or not label.strip():
            return
        idx = self.sel
        pi = None if idx is None else self.doc.part_of(idx)
        pos = self.doc.add_part(label.strip(), after_part=pi)
        self.sel = pos
        self.refresh(keep=pos)

    def delete_sel(self):
        if not self.doc or self.sel is None:
            return
        it = self.doc.items[self.sel]
        MB = QtWidgets.QMessageBox
        if it.kind == C.KIND_SCENE:
            if MB.question(self, "حذف صحنه",
                           "«%s» از پلات برداشته شود؟\n"
                           "نثرِ نوشته‌شده‌اش پاک نمی‌شود و به صحنه‌های یتیم "
                           "می‌رود." % it.scene_label,
                           MB.Yes | MB.No) != MB.Yes:
                return
            self.doc.delete_scene(self.sel)
        elif it.kind == C.KIND_CHAPTER:
            s, e = self.doc.chapter_block(self.sel)
            n = sum(1 for k in range(s, e)
                    if self.doc.items[k].kind == C.KIND_SCENE)
            if n:
                r = MB.question(self, "حذف فصل",
                                "فصل «%s» %s صحنه دارد. صحنه‌ها هم حذف شوند؟\n"
                                "«خیر» یعنی فقط سرفصل برداشته شود."
                                % (it.chapter_label, C.fa_num(n)),
                                MB.Yes | MB.No | MB.Cancel)
                if r == MB.Cancel:
                    return
                self.doc.delete_chapter(self.sel, with_scenes=(r == MB.Yes))
            else:
                self.doc.delete_chapter(self.sel)
        else:
            if MB.question(self, "حذف بخش", "سرفصلِ بخش برداشته شود؟",
                           MB.Yes | MB.No) != MB.Yes:
                return
            self.doc.items.pop(self.sel)
            self.doc.dirty = True
        self.sel = None
        self.refresh()

    def move_to_chapter(self):
        it = self._need()
        if it is None:
            return
        self.apply_form()
        chs = self.doc.chapter_indices()
        names = [self.doc.items[c].chapter_label for c in chs]
        if not names:
            return
        name, ok = QtWidgets.QInputDialog.getItem(
            self, "انتقال به فصل", "فصل مقصد", names, 0, False)
        if not ok:
            return
        ci = chs[names.index(name)]
        pos = self.doc.move_scene_to_chapter(self.sel, ci)
        self.sel = pos
        self.refresh(keep=pos)

    # ---------------------------------------------------------- ذخیره

    def save(self, path=None):
        if not self.doc:
            return False
        self.apply_form()
        try:
            target = self.doc.save(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "خطا",
                                           "نوشتن در پلات ممکن نشد.\n%s" % exc)
            return False
        self.lbl_file.setText(os.path.basename(target))
        self.update_hint()
        self.main.note("پلات ذخیره شد: %s" % os.path.basename(target))
        self.plotSaved.emit(target)
        return True

    def save_as_version(self):
        if not self.doc:
            return
        self.apply_form()
        suggest = self.doc.next_version_path()
        p, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "نسخهٔ جدیدِ پلات", suggest, "Markdown (*.md);;همه (*.*)")
        if p:
            self.save(p)


# ------------------------------------------------------------------ پنجرهٔ اصلی

class Main(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.setWindowTitle("دبیر")
        self.resize(1320, 820)
        self.setLayoutDirection(Qt.RightToLeft)

        self.scenes, self.by_id, self.visible = [], {}, []
        self.current = None
        self.store = None
        self.dirty = False
        self.loading = False
        self.wc_cache = {}

        fam, ok = pick_font(self.cfg.get("font"))
        self.family = fam
        self.font_ok = ok
        self.cfg["font"] = fam
        self.size = int(self.cfg.get("font_size", 14))
        self.theme_name = self.cfg.get("theme", "روشن")
        if self.theme_name not in THEMES:
            self.theme_name = "روشن"
        self.theme = THEMES[self.theme_name]

        self._build()
        self._menus()
        self._shortcuts()
        self.apply_theme()

        self.autosave = QtCore.QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.setInterval(1500)
        self.autosave.timeout.connect(self.save_current)

        QtCore.QTimer.singleShot(60, self.startup)

    # ------------------------------------------------------------- ساخت UI

    def body_font(self, size=None, italic=False):
        f = QtGui.QFont(self.family or "", size or self.size)
        f.setItalic(italic)
        return f

    def ui_font(self, size=10):
        return QtGui.QFont(self.family or "", size)

    def _build(self):
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self.tabs.setFont(self.ui_font(11))
        self.setCentralWidget(self.tabs)

        self.plot_pane = PlotPane(self)
        self.plot_pane.plotSaved.connect(self.on_plot_saved)
        self.tabs.addTab(self.plot_pane, "پلات")

        root = QtWidgets.QWidget()
        self.tabs.addTab(root, "نوشتن")
        self.tabs.setCurrentIndex(1)
        self.tabs.currentChanged.connect(self.on_tab)
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(10, 8, 10, 6)
        lay.setSpacing(6)

        # ---- نوار ناوبری
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(6)
        self.btn_prev = QtWidgets.QPushButton("›")
        self.btn_next = QtWidgets.QPushButton("‹")
        for b in (self.btn_prev, self.btn_next):
            b.setFixedWidth(32)
            b.setFont(self.ui_font(11))
        self.btn_prev.clicked.connect(lambda: self.step(-1))
        self.btn_next.clicked.connect(lambda: self.step(1))

        self.cb_scene = QtWidgets.QComboBox()
        self.cb_scene.setMinimumWidth(300)
        self.cb_chapter = QtWidgets.QComboBox()
        self.cb_chapter.setMinimumWidth(190)
        self.cb_part = QtWidgets.QComboBox()
        self.cb_part.setMinimumWidth(110)
        self.ed_search = QtWidgets.QLineEdit()
        self.ed_search.setPlaceholderText("جست‌وجو")
        self.ed_search.setMaximumWidth(170)
        for w in (self.cb_scene, self.cb_chapter, self.cb_part, self.ed_search):
            w.setFont(self.ui_font())

        self.cb_scene.currentIndexChanged.connect(self.on_pick_scene)
        self.cb_chapter.currentIndexChanged.connect(
            lambda _: None if self.loading else self.refilter())
        self.cb_part.currentIndexChanged.connect(
            lambda _: None if self.loading else self.refilter())
        self.ed_search.textChanged.connect(
            lambda _: None if self.loading else self.refilter())

        self.btn_chapview = QtWidgets.QPushButton("نمای فصل")
        self.btn_chapview.setFont(self.ui_font())
        self.btn_chapview.clicked.connect(self.open_chapter_view)

        bar.addWidget(self.btn_prev)
        bar.addWidget(self.cb_scene)
        bar.addWidget(self.cb_chapter)
        bar.addWidget(self.cb_part)
        bar.addWidget(self.ed_search)
        bar.addWidget(self.btn_next)
        bar.addStretch(1)
        bar.addWidget(self.btn_chapview)
        lay.addLayout(bar)

        # ---- نوار فیلدها
        fields = QtWidgets.QHBoxLayout()
        fields.setSpacing(18)
        self.fw = {}
        specs = [("شناسه", "sid"), ("فصل", "chapter"), ("زمان", "time"),
                 ("وضعیت", "status"), ("کلمه / بودجه", "wc")]
        for label, key in specs:
            col = QtWidgets.QVBoxLayout()
            col.setSpacing(1)
            lb = QtWidgets.QLabel(label)
            lb.setFont(self.ui_font(8))
            lb.setStyleSheet("color:#8a8a86; background:transparent;")
            col.addWidget(lb)
            if key == "status":
                w = QtWidgets.QToolButton()
                w.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.
                               InstantPopup
                               if hasattr(QtWidgets.QToolButton,
                                          "ToolButtonPopupMode")
                               else QtWidgets.QToolButton.InstantPopup)
                menu = QtWidgets.QMenu(w)
                for st in C.STATUSES:
                    act = menu.addAction(st)
                    act.triggered.connect(
                        lambda _=False, s=st: self.set_status(s))
                w.setMenu(menu)
                w.setFont(self.ui_font())
                w.setText(C.ST_DRAFT)
                w.setAutoRaise(True)
            else:
                w = QtWidgets.QLabel("—")
                w.setFont(self.ui_font(11))
            self.fw[key] = w
            col.addWidget(w)
            fields.addLayout(col)
        fields.addStretch(1)
        lay.addLayout(fields)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine
                           if hasattr(QtWidgets.QFrame, "Shape")
                           else QtWidgets.QFrame.HLine)
        line.setStyleSheet("color:#d3d1c7;")
        lay.addWidget(line)

        # ---- دو ستون
        split = QtWidgets.QSplitter(Qt.Horizontal)
        split.setLayoutDirection(Qt.RightToLeft)
        split.setHandleWidth(8)
        self.split = split

        # راست: فراداده (اول اضافه می‌شود چون چیدمان راست‌به‌چپ است)
        rp = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(rp)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        cap = QtWidgets.QLabel("فرادادهٔ صحنه — فقط خواندنی")
        cap.setFont(self.ui_font(8))
        cap.setStyleSheet("color:#8a8a86;")
        cap.setAlignment(Qt.AlignRight)
        rl.addWidget(cap)
        self.meta = QtWidgets.QTextBrowser()
        self.meta.setLayoutDirection(Qt.RightToLeft)
        self.meta.document().setDefaultTextOption(Editor._text_option())
        rl.addWidget(self.meta, 1)
        split.addWidget(rp)

        # چپ: ویرایشگر
        lp = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(lp)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(2)
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(4)
        t = QtWidgets.QLabel("نوع بلوک")
        t.setFont(self.ui_font(8))
        t.setStyleSheet("color:#8a8a86;")
        head.addWidget(t)
        self.block_btns = {}
        for name in C.BLOCK_TYPES:
            b = QtWidgets.QPushButton(name)
            b.setFont(self.ui_font(9))
            b.setCheckable(True)
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self.set_block(n))
            self.block_btns[name] = b
            head.addWidget(b)
        head.addStretch(1)
        ll.addLayout(head)

        self.ed = Editor()
        self.ed.setFont(self.body_font())
        self.ed.textChanged.connect(self.on_text_changed)
        self.ed.cursorPositionChanged.connect(self.sync_block_ui)
        ll.addWidget(self.ed, 1)
        split.addWidget(lp)

        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([440, 780])
        lay.addWidget(split, 1)

        self.status = self.statusBar()
        self.status.setFont(self.ui_font(9))
        self.lbl_left = QtWidgets.QLabel("")
        self.lbl_left.setFont(self.ui_font(9))
        self.status.addPermanentWidget(self.lbl_left)

    def _menus(self):
        mb = self.menuBar()
        mb.setFont(self.ui_font())

        m = mb.addMenu("پرونده")
        m.addAction("انتخاب فایل پلات…", self.choose_plot)
        m.addAction("پلاتِ تازه از تمپلیت…", self.new_plot_from_template)
        m.addAction("بارگذاری دوبارهٔ پلات", self.reload_plot)
        m.addSeparator()
        a = m.addAction("ذخیره", lambda: self.save_current(True))
        a.setShortcut("Ctrl+S")
        m.addSeparator()
        m.addAction("خروج", self.close)

        m = mb.addMenu("صحنه")
        a = m.addAction("صحنهٔ بعد", lambda: self.step(1))
        a.setShortcut("Alt+Left")
        a = m.addAction("صحنهٔ قبل", lambda: self.step(-1))
        a.setShortcut("Alt+Right")
        m.addSeparator()
        for i, name in enumerate(C.BLOCK_TYPES, start=1):
            a = m.addAction("بلوک: %s" % name,
                            lambda _=False, n=name: self.set_block(n))
            a.setShortcut("Ctrl+%d" % i)

        m = mb.addMenu("پلات")
        a = m.addAction("ذخیرهٔ پلات", lambda: self.plot_pane.save())
        a.setShortcut("Ctrl+Shift+S")
        m.addAction("نسخهٔ جدیدِ پلات…", self.plot_pane.save_as_version)
        m.addSeparator()
        a = m.addAction("تبِ پلات", lambda: self.tabs.setCurrentIndex(0))
        a.setShortcut("Ctrl+1")
        a = m.addAction("تبِ نوشتن", lambda: self.tabs.setCurrentIndex(1))
        a.setShortcut("Ctrl+2")

        m = mb.addMenu("نما")
        a = m.addAction("نمای فصل", self.open_chapter_view)
        a.setShortcut("Ctrl+R")
        m.addSeparator()
        grp = QtGui.QActionGroup(self)
        for name in THEMES:
            a = m.addAction(name)
            a.setCheckable(True)
            a.setChecked(name == self.theme_name)
            grp.addAction(a)
            a.triggered.connect(lambda _=False, n=name: self.set_theme(n))
        m.addSeparator()
        a = m.addAction("قلم بزرگ‌تر", lambda: self.zoom(1))
        a.setShortcut("Ctrl++")
        a = m.addAction("قلم کوچک‌تر", lambda: self.zoom(-1))
        a.setShortcut("Ctrl+-")

        m = mb.addMenu("خروجی")
        m.addAction("نسخهٔ خواننده…", lambda: self.open_export("reader"))
        m.addAction("نسخهٔ کاری…", lambda: self.open_export("working"))
        m.addSeparator()
        m.addAction("جدول صحنه‌ها…", self.export_table)

        m = mb.addMenu("ابزار")
        m.addAction("صحنه‌های یتیم…", self.open_orphans)
        m.addAction("بودجهٔ این صحنه…", self.edit_budget)
        m.addSeparator()
        m.addAction("پوشهٔ داده…", self.choose_data_dir)
        m.addAction("دربارهٔ قلم", self.font_info)

    def _shortcuts(self):
        QShortcut(QtGui.QKeySequence("Ctrl+="), self,
                        lambda: self.zoom(1))

    # ------------------------------------------------------------ راه‌اندازی

    def startup(self):
        if not self.font_ok:
            self.note("قلم وزیرمتن پیدا نشد؛ «%s» جایگزین شد."
                      % (self.family or "پیش‌فرض"))
        p = self.cfg.get("plot_path", "")
        if p and os.path.exists(p):
            self.load_plot(p)
        else:
            self.choose_plot()

    def choose_plot(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "فایل پلات را انتخاب کنید", "",
            "Markdown (*.md);;همه (*.*)")
        if not p:
            if not self.scenes:
                QtCore.QTimer.singleShot(0, self.close)
            return
        self.cfg["plot_path"] = p
        if not self.cfg.get("data_dir"):
            self.cfg["data_dir"] = os.path.join(os.path.dirname(p), "draft")
        save_config(self.cfg)
        self.load_plot(p)

    def choose_data_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "پوشهٔ داده")
        if not d:
            return
        self.save_current(True)
        self.cfg["data_dir"] = d
        save_config(self.cfg)
        self.load_plot(self.cfg["plot_path"])

    def reload_plot(self):
        self.save_current(True)
        keep = self.current.sid if self.current else None
        self.load_plot(self.cfg["plot_path"], keep)

    def load_plot(self, path, keep=None):
        try:
            scenes = C.parse_plot(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "خطا",
                                           "خواندن پلات ممکن نشد.\n%s" % exc)
            return
        if not scenes:
            QtWidgets.QMessageBox.critical(self, "خطا",
                                           "هیچ صحنه‌ای پیدا نشد.")
            return
        self.scenes = scenes
        self.by_id = {s.sid: s for s in scenes}
        self.store = C.Store(self.cfg["data_dir"])
        self.wc_cache = {s.sid: self.store.word_count(s.sid) for s in scenes}

        self.loading = True
        self.cb_part.clear()
        self.cb_part.addItems(["همه"] +
                              sorted({s.part for s in scenes if s.part}))
        self.refill_chapters()
        self.loading = False
        self.current = None
        self.refilter()

        n = len(self.store.orphans(self.by_id.keys()))
        if n:
            self.note("%s صحنهٔ یتیم دارید (ابزار ← صحنه‌های یتیم)."
                      % C.fa_num(n))
        try:
            self.plot_pane.set_doc(C.PlotDoc.load(path))
        except Exception as exc:
            self.note("پلات برای ویرایش باز نشد: %s" % exc)
        self.update_path_label()
        if keep and keep in self.by_id:
            self.go_to(keep)

    def refill_chapters(self):
        part = self.cb_part.currentText()
        chs, seen = ["همه"], set()
        for s in self.scenes:
            if part not in ("", "همه") and s.part != part:
                continue
            if s.chapter and s.chapter not in seen:
                seen.add(s.chapter)
                chs.append(s.chapter_label)
        keep = self.cb_chapter.currentText()
        self.cb_chapter.blockSignals(True)
        self.cb_chapter.clear()
        self.cb_chapter.addItems(chs)
        self.cb_chapter.setCurrentText(keep if keep in chs else "همه")
        self.cb_chapter.blockSignals(False)

    # -------------------------------------------------------------- فیلتر

    def refilter(self):
        if not self.scenes:
            return
        self.refill_chapters()
        part = self.cb_part.currentText()
        chap = self.cb_chapter.currentText()
        q = self.ed_search.text().strip()

        out = []
        for s in self.scenes:
            if part not in ("", "همه") and s.part != part:
                continue
            if chap not in ("", "همه") and s.chapter_label != chap:
                continue
            if q and q not in " ".join(
                    [s.sid, s.title, s.chapter, " ".join(s.description)]):
                continue
            out.append(s)
        self.visible = out

        self.loading = True
        self.cb_scene.clear()
        self.cb_scene.addItems([s.label for s in out])
        self.loading = False

        if self.current in out:
            self.cb_scene.setCurrentIndex(out.index(self.current))
        elif out:
            self.show_scene(out[0])
        self.update_progress()

    def on_pick_scene(self, i):
        if self.loading or not (0 <= i < len(self.visible)):
            return
        self.show_scene(self.visible[i])

    def go_to(self, sid):
        sc = self.by_id.get(sid)
        if not sc:
            return
        if sc not in self.visible:
            self.loading = True
            self.cb_part.setCurrentText("همه")
            self.cb_chapter.setCurrentText("همه")
            self.ed_search.setText("")
            self.loading = False
            self.refilter()
        self.show_scene(sc)
        if sc in self.visible:
            self.cb_scene.setCurrentIndex(self.visible.index(sc))

    def step(self, d):
        if not self.visible or not self.current:
            return
        try:
            i = self.visible.index(self.current)
        except ValueError:
            i = 0
        j = max(0, min(len(self.visible) - 1, i + d))
        if j != i:
            self.show_scene(self.visible[j])
            self.cb_scene.setCurrentIndex(j)

    # -------------------------------------------------------------- نمایش

    def show_scene(self, sc):
        if self.current is sc:
            return
        self.save_current(True)
        self.current = sc

        self.loading = True
        doc = self.ed.document()
        doc.blockSignals(True)
        self.ed.clear()
        cur = self.ed.textCursor()
        blocks = self.store.load_blocks(sc.sid) or [(C.BLOCK_PLAIN, "")]
        for i, (btype, text) in enumerate(blocks):
            if i:
                cur.insertBlock()
            cur.insertText(text)
            style_block(cur, btype, self.theme)
        doc.blockSignals(False)
        cur.movePosition(QtGui.QTextCursor.MoveOperation.Start
                         if hasattr(QtGui.QTextCursor, "MoveOperation")
                         else QtGui.QTextCursor.Start)
        self.ed.setTextCursor(cur)
        self.ed.document().clearUndoRedoStacks()
        self.loading = False
        self.dirty = False

        self.fill_meta(sc)
        self.update_fields()
        self.sync_block_ui()
        self.ed.setFocus()

    def fill_meta(self, sc):
        def e(s):
            return (s.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))
        t = self.theme
        base = "text-align:right; direction:rtl;"
        parts = ['<div dir="rtl" style="font-family:%s; font-size:%dpt; '
                 '%s line-height:170%%; color:%s;">'
                 % (self.family or "sans-serif", max(9, self.size - 3),
                    base, t["panel_fg"])]
        parts.append('<p dir="rtl" style="%s font-size:%dpt; font-weight:600; '
                     'color:%s;">%s</p>'
                     % (base, max(10, self.size - 2), t["fg"], e(sc.title)))
        for para in sc.description:
            if para.strip():
                parts.append('<p dir="rtl" style="%s">%s</p>'
                             % (base, e(para.strip())))
        for name, val in sc.tags:
            parts.append('<p dir="rtl" style="%s background:%s; color:%s; '
                         'padding:6px;"><b>%s:</b> %s</p>'
                         % (base, t["chip_bg"], t["chip_fg"], e(name), e(val)))
        parts.append("</div>")
        self.meta.setHtml("".join(parts))
        force_rtl(self.meta.document())

    def update_fields(self):
        sc = self.current
        if not sc:
            return
        self.fw["sid"].setText(sc.sid)
        self.fw["chapter"].setText(sc.chapter or "—")
        self.fw["time"].setText(sc.time or "—")
        self.update_status_button()
        self.update_wordcount()

    def update_status_button(self):
        sc = self.current
        if not sc:
            return
        wc = C.count_words(self.ed.toPlainText())
        st = C.ST_EMPTY if wc == 0 else self.store.get_status(sc.sid)
        fg, bg = C.STATUS_COLOR.get(st, ("#444441", "#f1efe8"))
        w = self.fw["status"]
        w.setText(st)
        w.setStyleSheet("QToolButton{color:%s; background:%s; border:none; "
                        "border-radius:9px; padding:2px 10px;}" % (fg, bg))

    def default_budget(self):
        return int(self.cfg.get("target_words", 100000) /
                   max(1, len(self.scenes)))

    def update_wordcount(self):
        sc = self.current
        if not sc:
            return
        wc = C.count_words(self.ed.toPlainText())
        b = self.store.get_budget(sc.sid, self.default_budget())
        w = self.fw["wc"]
        w.setText("%s / %s" % (C.fa_num(wc), C.fa_num(b)))
        w.setStyleSheet("background:transparent; color:%s;"
                        % ("#d05555" if wc > b * 1.25 else self.theme["fg"]))

    def update_progress(self):
        done = sum(1 for s in self.scenes if self.wc_cache.get(s.sid))
        total = sum(self.wc_cache.get(s.sid, 0) for s in self.scenes)
        self.lbl_left.setText("%s از %s صحنه نوشته شده · %s کلمه"
                              % (C.fa_num(done), C.fa_num(len(self.scenes)),
                                 C.fa_num(total)))

    def update_path_label(self):
        self.status.showMessage("%s  ·  %s" % (
            os.path.basename(self.cfg.get("plot_path", "")),
            self.cfg.get("data_dir", "")))

    def note(self, msg):
        self.status.showMessage(msg, 3000)
        QtCore.QTimer.singleShot(3200, self.update_path_label)

    def font_info(self):
        QtWidgets.QMessageBox.information(
            self, "قلم",
            "قلم فعلی: %s\nموتور: %s\n\nاگر وزیرمتن را می‌خواهید نصبش کنید "
            "و برنامه را دوباره باز کنید." % (self.family or "پیش‌فرض", QT))

    # ------------------------------------------------------------- بلوک‌ها

    def editor_blocks(self):
        out = []
        doc = self.ed.document()
        b = doc.begin()
        while b.isValid():
            out.append((block_type_of(b), b.text()))
            b = b.next()
        return out

    def set_block(self, name):
        cur = self.ed.textCursor()
        start, end = cur.selectionStart(), cur.selectionEnd()
        doc = self.ed.document()
        b = doc.findBlock(start)
        cur.beginEditBlock()
        while b.isValid() and b.position() <= end:
            c = QtGui.QTextCursor(b)
            style_block(c, name, self.theme)
            b = b.next()
        cur.endEditBlock()
        self.mark_dirty()
        self.sync_block_ui()

    def sync_block_ui(self):
        cur = block_type_of(self.ed.textCursor().block())
        for name, btn in self.block_btns.items():
            on = (name == cur)
            btn.setChecked(on)
            t = self.theme
            btn.setStyleSheet(
                "QPushButton{border:none; border-radius:9px; padding:2px 10px;"
                "color:%s; background:%s;}"
                % ((t["chip_fg"], t["chip_bg"]) if on
                   else (t["muted"], "transparent")))

    # -------------------------------------------------------------- ذخیره

    def on_text_changed(self):
        if self.loading:
            return
        self.mark_dirty()
        self.update_wordcount()
        self.update_status_button()

    def mark_dirty(self):
        if self.loading:
            return
        self.dirty = True
        self.autosave.start()

    def save_current(self, force=False):
        self.autosave.stop()
        if not self.current or not self.store:
            return
        if not self.dirty:
            if force:
                self.note("ذخیره شد")
            return
        self.store.save_blocks(self.current.sid, self.editor_blocks())
        self.wc_cache[self.current.sid] = C.count_words(self.ed.toPlainText())
        self.dirty = False
        self.update_progress()
        self.note("ذخیره شد")

    def set_status(self, st):
        if self.current:
            self.store.set_status(self.current.sid, st)
            self.update_status_button()

    def edit_budget(self):
        if not self.current:
            return
        cur = self.store.get_budget(self.current.sid, self.default_budget())
        val, ok = QtWidgets.QInputDialog.getInt(
            self, "بودجهٔ صحنه", "بودجهٔ کلمهٔ %s" % self.current.sid,
            cur, 50, 20000)
        if ok:
            self.store.set_budget(self.current.sid, val)
            self.update_wordcount()

    def set_theme(self, name):
        if name not in THEMES:
            return
        self.theme_name = name
        self.theme = THEMES[name]
        self.cfg["theme"] = name
        save_config(self.cfg)
        self.apply_theme()
        sc, self.current = self.current, None
        if sc:
            self.show_scene(sc)

    def apply_theme(self):
        t = self.theme
        self.setStyleSheet(
            "QMainWindow, QWidget{background:%(panel)s; color:%(fg)s;}"
            "QMenuBar{background:%(panel)s; color:%(fg)s;}"
            "QMenuBar::item:selected{background:%(chip_bg)s;}"
            "QMenu{background:%(panel)s; color:%(fg)s; border:1px solid "
            "%(border)s;}"
            "QMenu::item:selected{background:%(chip_bg)s; color:%(chip_fg)s;}"
            "QComboBox, QLineEdit, QPushButton, QListWidget, QToolButton{"
            "background:%(bg)s; color:%(fg)s; border:1px solid %(border)s; "
            "border-radius:5px; padding:3px 6px;}"
            "QComboBox QAbstractItemView{background:%(bg)s; color:%(fg)s; "
            "selection-background-color:%(chip_bg)s; "
            "selection-color:%(chip_fg)s;}"
            "QStatusBar{color:%(muted)s;}"
            "QLabel{background:transparent;}" % t)
        self.ed.setStyleSheet(
            "QTextEdit{background:%(bg)s; color:%(fg)s; border:1px solid "
            "%(border)s; selection-background-color:%(sel_bg)s; "
            "selection-color:%(fg)s;}" % t)
        self.meta.setStyleSheet(
            "QTextBrowser{background:%(panel)s; color:%(panel_fg)s; "
            "border:1px solid %(border)s;}" % t)
        pal = self.ed.palette()
        pal.setColor(QtGui.QPalette.ColorRole.Text
                     if hasattr(QtGui.QPalette, "ColorRole")
                     else QtGui.QPalette.Text, QtGui.QColor(t["fg"]))
        pal.setColor(QtGui.QPalette.ColorRole.Base
                     if hasattr(QtGui.QPalette, "ColorRole")
                     else QtGui.QPalette.Base, QtGui.QColor(t["bg"]))
        self.ed.setPalette(pal)
        if self.current:
            self.fill_meta(self.current)
        self.sync_block_ui()

    def zoom(self, d):
        self.size = max(9, min(30, self.size + d))
        self.cfg["font_size"] = self.size
        save_config(self.cfg)
        self.ed.setFont(self.body_font())
        if self.current:
            self.fill_meta(self.current)

    # ----------------------------------------------------------- نمای فصل

    def open_chapter_view(self):
        if not self.current:
            return
        self.save_current(True)
        chap = self.current.chapter
        scenes = [s for s in self.scenes if s.chapter == chap]
        sep = self.cfg.get("separator", C.SEPARATOR)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("نمای فصل — %s" % self.current.chapter_label)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(900, 800)
        lay = QtWidgets.QVBoxLayout(dlg)
        view = QtWidgets.QTextBrowser()
        view.setLayoutDirection(Qt.RightToLeft)
        view.setOpenLinks(False)
        lay.addWidget(view, 1)

        def e(s):
            return (s.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))

        th = self.theme
        view.setStyleSheet("QTextBrowser{background:%s; color:%s; "
                           "border:none;}" % (th["bg"], th["fg"]))
        dlg.setStyleSheet("QDialog{background:%s;}" % th["panel"])
        html = ['<div dir="rtl" style="font-family:%s; font-size:%dpt; '
                'text-align:right; direction:rtl; line-height:200%%; '
                'margin:20px 46px; color:%s;">'
                % (self.family or "sans-serif", self.size, th["fg"])]
        total, first = 0, True
        for sc in scenes:
            blocks = self.store.load_blocks(sc.sid)
            if not any(t.strip() for _, t in blocks):
                continue
            if not first:
                html.append('<p style="text-align:center; color:%s; '
                            'margin:26px 0;">%s</p>' % (th["sep"], e(sep)))
            first = False
            html.append('<a name="%s"></a>' % sc.sid)
            for btype, line in blocks:
                if not line.strip():
                    continue
                st = th["blocks"][btype]
                style = ("text-align:right; direction:rtl; "
                         "margin-right:%dpx; margin-left:%dpx;"
                         % (st["indent"], st["indent"]))
                if st["color"]:
                    style += "color:%s;" % st["color"]
                if st["italic"]:
                    style += "font-style:italic;"
                if st["bg"]:
                    style += "background:%s; padding:6px;" % st["bg"]
                html.append('<p dir="rtl" style="%s"><a href="go:%s" '
                            'style="color:inherit; text-decoration:none;">%s'
                            '</a></p>' % (style, sc.sid, e(line)))
            total += C.count_words("\n".join(t for _, t in blocks))
        if first:
            html.append("<p>هنوز چیزی در این فصل نوشته نشده.</p>")
        html.append("</div>")
        view.setHtml("".join(html))
        force_rtl(view.document())

        def on_link(url):
            s = url.toString()
            if s.startswith("go:"):
                self.go_to(s[3:])
                dlg.accept()
        view.anchorClicked.connect(on_link)

        foot = QtWidgets.QLabel("%s کلمه در این فصل" % C.fa_num(total))
        foot.setFont(self.ui_font(9))
        foot.setStyleSheet("color:#8a8a86;")
        foot.setAlignment(Qt.AlignCenter)
        lay.addWidget(foot)
        run_dialog(dlg)

    # -------------------------------------------------------------- خروجی

    def open_export(self, mode):
        self.save_current(True)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("خروجی — %s" % ("نسخهٔ خواننده" if mode == "reader"
                                           else "نسخهٔ کاری"))
        dlg.setLayoutDirection(Qt.RightToLeft)
        lay = QtWidgets.QVBoxLayout(dlg)
        combo = QtWidgets.QComboBox()
        combo.setFont(self.ui_font())
        combo.setMinimumWidth(320)

        radios = {}
        for text, val in [("کل جلد", "all"), ("یک بخش", "part"),
                          ("یک فصل", "chapter"), ("یک صحنه", "scene")]:
            rb = QtWidgets.QRadioButton(text)
            rb.setFont(self.ui_font())
            radios[val] = rb
            lay.addWidget(rb)
        radios["all"].setChecked(True)
        lay.addWidget(combo)

        def refresh():
            s = [k for k, v in radios.items() if v.isChecked()][0]
            if s == "part":
                vals = sorted({x.part for x in self.scenes if x.part})
            elif s == "chapter":
                vals, seen = [], set()
                for x in self.scenes:
                    if x.chapter and x.chapter not in seen:
                        seen.add(x.chapter)
                        vals.append(x.chapter_label)
            elif s == "scene":
                vals = [x.label for x in self.scenes]
            else:
                vals = []
            combo.clear()
            combo.addItems(vals)
            combo.setEnabled(bool(vals))
        for rb in radios.values():
            rb.toggled.connect(lambda _=False: refresh())
        refresh()

        btn = QtWidgets.QPushButton("ساختن فایل")
        btn.setFont(self.ui_font())
        lay.addWidget(btn)

        def run():
            s = [k for k, v in radios.items() if v.isChecked()][0]
            t = combo.currentText()
            if s == "all":
                sel, name = list(self.scenes), "کل-جلد"
            elif s == "part":
                sel, name = [x for x in self.scenes if x.part == t], t
            elif s == "chapter":
                sel, name = [x for x in self.scenes
                             if x.chapter_label == t], t
            else:
                sel, name = [x for x in self.scenes if x.label == t], t
            if not sel:
                QtWidgets.QMessageBox.warning(dlg, "خروجی",
                                              "چیزی برای خروجی نیست.")
                return
            txt = C.export_markdown(
                sel, self.store, mode=mode,
                separator=self.cfg.get("separator", C.SEPARATOR),
                title=name if mode == "reader" else None)
            dlg.accept()
            self.write_out(txt, name, mode)
        btn.clicked.connect(run)
        run_dialog(dlg)

    def write_out(self, text, name, mode):
        safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip()
        suffix = {"reader": "خواننده", "working": "کاری"}.get(mode, mode)
        p, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "ذخیرهٔ خروجی",
            os.path.join(self.cfg.get("data_dir", ""),
                         "%s-%s.md" % (safe or "خروجی", suffix)),
            "Markdown (*.md);;همه (*.*)")
        if not p:
            return
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.note("خروجی ساخته شد: %s" % os.path.basename(p))

    def export_table(self):
        self.save_current(True)
        txt = C.export_scene_table(self.scenes, self.store,
                                   self.default_budget())
        self.write_out(txt, "جدول-صحنه‌ها", "table")

    # -------------------------------------------------------------- یتیم‌ها

    def open_orphans(self):
        orph = self.store.orphans(self.by_id.keys())
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("صحنه‌های یتیم")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(820, 560)
        lay = QtWidgets.QVBoxLayout(dlg)
        cap = QtWidgets.QLabel("نثری که شناسه‌اش دیگر در پلات نیست. "
                               "هیچ‌وقت پاک نمی‌شود.")
        cap.setFont(self.ui_font(9))
        cap.setStyleSheet("color:#8a8a86;")
        lay.addWidget(cap)

        if not orph:
            lay.addWidget(QtWidgets.QLabel("یتیمی وجود ندارد."))
            run_dialog(dlg)
            return

        row = QtWidgets.QHBoxLayout()
        lst = QtWidgets.QListWidget()
        lst.setFont(self.ui_font())
        lst.setMaximumWidth(220)
        prev = QtWidgets.QTextBrowser()
        prev.setLayoutDirection(Qt.RightToLeft)
        prev.document().setDefaultTextOption(Editor._text_option())
        prev.setStyleSheet("QTextBrowser{background:%s; color:%s;}"
                           % (self.theme["bg"], self.theme["fg"]))
        row.addWidget(lst)
        row.addWidget(prev, 1)
        lay.addLayout(row, 1)

        for sid, wc in orph:
            lst.addItem("%s  (%s کلمه)" % (sid, C.fa_num(wc)))

        def sel(i):
            if i < 0:
                return
            prev.setPlainText(self.store.plain_text(orph[i][0]))
            force_rtl(prev.document(), skip_centered=False)
        lst.currentRowChanged.connect(sel)
        lst.setCurrentRow(0)

        btn = QtWidgets.QPushButton("ذخیرهٔ این متن در فایل")
        btn.setFont(self.ui_font())

        def save_one():
            i = lst.currentRow()
            if i >= 0:
                self.write_out(self.store.plain_text(orph[i][0]) + "\n",
                               orph[i][0], "یتیم")
        btn.clicked.connect(save_one)
        lay.addWidget(btn)
        run_dialog(dlg)

    # ----------------------------------------------------------- تب پلات

    def on_tab(self, i):
        """از تبِ پلات که بیرون می‌آییم، تغییرهای ذخیره‌نشده را می‌پرسد."""
        if i == 1 and self.plot_pane.doc and self.plot_pane.doc.dirty:
            MB = QtWidgets.QMessageBox
            r = MB.question(self, "پلاتِ ذخیره‌نشده",
                            "تغییرهای پلات ذخیره نشده. در فایل نوشته شود؟",
                            MB.Yes | MB.No)
            if r == MB.Yes:
                self.plot_pane.save()

    def on_plot_saved(self, path):
        """بعد از نوشتن در پلات، تبِ نوشتن با ساختارِ تازه هماهنگ می‌شود."""
        self.cfg["plot_path"] = path
        save_config(self.cfg)
        keep = self.current.sid if self.current else None
        self.save_current(True)
        self.load_plot(path, keep)

    def new_plot_from_template(self):
        p, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "پلاتِ تازه", os.path.join(self.cfg.get("data_dir", ""),
                                             "plot.md"),
            "Markdown (*.md);;همه (*.*)")
        if not p:
            return
        C.write_template(p)
        self.cfg["plot_path"] = p
        if not self.cfg.get("data_dir"):
            self.cfg["data_dir"] = os.path.join(os.path.dirname(p), "draft")
        save_config(self.cfg)
        self.load_plot(p)
        self.tabs.setCurrentIndex(0)
        self.note("تمپلیت ساخته شد: %s" % os.path.basename(p))

    # ---------------------------------------------------------------- پایان

    def closeEvent(self, ev):
        try:
            if self.plot_pane.doc and self.plot_pane.doc.dirty:
                MB = QtWidgets.QMessageBox
                if MB.question(self, "پلاتِ ذخیره‌نشده",
                               "تغییرهای پلات در فایل نوشته شود؟",
                               MB.Yes | MB.No) == MB.Yes:
                    self.plot_pane.save()
            self.save_current(True)
            self.cfg["font_size"] = self.size
            save_config(self.cfg)
            if self.store:
                self.store.meta["target_words"] = self.cfg.get("target_words",
                                                               100000)
                self.store.save_meta()
        except Exception:
            pass
        ev.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    w = Main()
    w.show()
    sys.exit(app.exec() if hasattr(app, "exec") else app.exec_())


if __name__ == "__main__":
    main()
