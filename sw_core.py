# -*- coding: utf-8 -*-
"""
هستهٔ برنامهٔ دبیر — تجزیهٔ پلات، ذخیره‌سازی، خروجی.
بدون وابستگی به tkinter، تا بتوان جداگانه آزمودش.
"""

import json
import os
import re
import shutil
import time

# ---------------------------------------------------------------- ثابت‌ها

BLOCK_PLAIN = "متن"
BLOCK_DREAM = "خواب"
BLOCK_INTERLUDE = "میان‌پرده"
BLOCK_QUOTE = "نقل‌قول"

BLOCK_TYPES = [BLOCK_PLAIN, BLOCK_DREAM, BLOCK_INTERLUDE, BLOCK_QUOTE]

BLOCK_PREFIX = {
    BLOCK_DREAM: ">خواب> ",
    BLOCK_INTERLUDE: ">میان‌پرده> ",
    BLOCK_QUOTE: ">نقل‌قول> ",
}
PREFIX_BLOCK = {v: k for k, v in BLOCK_PREFIX.items()}

ST_EMPTY = "خالی"
ST_DRAFT = "پیش‌نویس"
ST_DOUBT = "شک دارم"
ST_REWRITE = "بازنویسی شود"
ST_DONE = "تمام"

STATUSES = [ST_DRAFT, ST_DOUBT, ST_REWRITE, ST_DONE]
ALL_STATUSES = [ST_EMPTY] + STATUSES

STATUS_COLOR = {
    ST_EMPTY:   ("#8a8a86", "#f1efe8"),
    ST_DRAFT:   ("#854f0b", "#faeeda"),
    ST_DOUBT:   ("#185fa5", "#e6f1fb"),
    ST_REWRITE: ("#a32d2d", "#fcebeb"),
    ST_DONE:    ("#0f6e56", "#e1f5ee"),
}

SEPARATOR = "\u2042"          # ⁂
SEPARATOR_FALLBACK = "*  *  *"

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def fa_num(n):
    """عدد را با رقم‌های فارسی برمی‌گرداند."""
    s = str(n)
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(PERSIAN_DIGITS[int(ch)])
        else:
            out.append(ch)
    return "".join(out)


def _ascii_digits(s):
    out = []
    for ch in s:
        if ch in PERSIAN_DIGITS:
            out.append(str(PERSIAN_DIGITS.index(ch)))
        elif "\u0660" <= ch <= "\u0669":
            out.append(str(ord(ch) - 0x0660))
        else:
            out.append(ch)
    return "".join(out)


def count_words(text):
    return len([w for w in re.split(r"\s+", text.strip()) if w])


# ---------------------------------------------------------------- تجزیهٔ پلات

class Scene:
    __slots__ = ("sid", "title", "chapter", "chapter_title", "part",
                 "time", "description", "tags", "order", "is_interlude")

    def __init__(self):
        self.sid = ""
        self.title = ""
        self.chapter = ""
        self.chapter_title = ""
        self.part = ""
        self.time = ""
        self.description = []
        self.tags = []
        self.order = 0
        self.is_interlude = False

    @property
    def label(self):
        return "%s — %s" % (self.sid, self.title)

    @property
    def chapter_label(self):
        if self.chapter_title:
            return "%s — %s" % (self.chapter, self.chapter_title)
        return self.chapter


_H1 = re.compile(r"^#\s+(.*)$")
_H2 = re.compile(r"^##\s+(.*)$")
_H3 = re.compile(r"^###\s+(.*)$")
_CHAPTER = re.compile(r"^(ف[\u06F0-\u06F9\d]+)\s*(?:—|-|–)?\s*(.*)$")
_SCENE_ID = re.compile(r"^S(\d+(?:[.\u066b\u002e]\d+)*)\b")
_TAG_INLINE = re.compile(r"\*([^*:\n]{1,40}):\*")
_BIDI = re.compile("[\u200e\u200f\u061c\ufeff\u202a-\u202e\u2066-\u2069]")
_MARKS = re.compile("[\u2705\u274c\u23f3\u2b50\u25c8\u25cf\u25cb\ufe0f"
                    "\U0001f512\U0001f513\U0001f7e1\U0001f7e2\U0001f534"
                    "\U0001f4dd\U0001f6a7\U0001f4cc]")
_BRACKET = re.compile(r"\[([^\[\]]*)\]")
_PART = re.compile(r"(بخش\s+(?:یک|دو|سه|چهار|پنج|شش))")


def _strip_md(s):
    """نشانه‌های مارک‌داون را برای نمایش ساده برمی‌دارد."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s


def parse_plot(path):
    """فایل md پلات را می‌خواند و فهرست صحنه‌ها را برمی‌گرداند."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    # ناحیهٔ صحنه‌ها: از سرفصلِ یک‌درجه‌ای که «صحنه‌های» دارد تا سرفصل یک‌درجه‌ای بعدی
    start = None
    end = len(lines)
    for i, ln in enumerate(lines):
        m = _H1.match(ln)
        if not m:
            continue
        head = m.group(1)
        if start is None and "صحنه‌ها" in head:
            start = i + 1
        elif start is not None:
            end = i
            break
    if start is None:
        start = 0

    scenes = []
    cur = None
    chapter, chapter_title, part = "", "", ""
    interlude_n = 0
    order = 0

    def close():
        nonlocal cur
        if cur is not None:
            while cur.description and not cur.description[-1].strip():
                cur.description.pop()
            scenes.append(cur)
            cur = None

    for ln in lines[start:end]:
        m3 = _H3.match(ln)
        if m3:
            close()
            head = _MARKS.sub("", _BIDI.sub("", m3.group(1))).strip()
            order += 1
            sc = Scene()
            sc.order = order
            sc.part = part
            sc.chapter = chapter
            sc.chapter_title = chapter_title

            bracket = ""
            hits = list(_BRACKET.finditer(head))
            if hits:
                bm = hits[-1]
                bracket = bm.group(1)
                head = (head[:bm.start()] + " " + head[bm.end():]).strip()

            head = head.replace("\u25c8", "").strip()

            mid = _SCENE_ID.match(head)
            if mid:
                sc.sid = "S" + mid.group(1)
                rest = head[mid.end():]
            else:
                interlude_n += 1
                sc.sid = "I%d" % interlude_n
                sc.is_interlude = True
                rest = head
            rest = re.sub(r"^\s*(?:—|-|–)\s*", "", rest).strip()
            sc.title = _strip_md(rest) or sc.sid

            if bracket:
                parts = [p.strip() for p in bracket.split("\u00b7")]
                first = parts[0] if parts else ""
                if re.match(r"^ف[\u06F0-\u06F9\d]", first):
                    sc.chapter = first
                    sc.time = "\u060c ".join(parts[1:])
                else:
                    sc.time = "\u060c ".join(parts)
            cur = sc
            continue

        m2 = _H2.match(ln)
        if m2:
            close()
            head = _strip_md(_BIDI.sub("", m2.group(1)).strip())
            head = re.sub(r"\u2705.*$", "", head)
            head = _MARKS.sub("", head).strip()
            if _PART_HEAD.match(head):
                pm = _PART.search(head)
                part = pm.group(1) if pm else head
                continue
            cm = _CHAPTER.match(head)
            if cm:
                chapter = cm.group(1)
                ct = cm.group(2)
                ct = re.sub(r"\s*\([^)]*\)\s*$", "", ct).strip()
                chapter_title = ct
            else:
                chapter = re.sub(r"\s*\([^)]*\)\s*$", "", head).strip()
                chapter_title = ""
            continue

        if cur is None:
            continue

        stripped = ln.strip()
        if stripped.startswith("*") and _TAG_INLINE.match(stripped):
            found = list(_TAG_INLINE.finditer(stripped))
            for k, mt in enumerate(found):
                nxt = found[k + 1].start() if k + 1 < len(found) else len(stripped)
                name = mt.group(1).strip()
                val = _strip_md(stripped[mt.end():nxt]).strip()
                cur.tags.append((name, val))
        else:
            cur.description.append(_strip_md(ln.rstrip()))

    close()
    return scenes


# ---------------------------------------------------------------- ذخیره‌سازی

class Store:
    """هر صحنه یک فایل مستقل. وضعیت و بودجه در یک فایل json."""

    MAX_BACKUPS = 8

    def __init__(self, root):
        self.root = root
        self.scenes_dir = os.path.join(root, "scenes")
        self.backup_dir = os.path.join(root, "backups")
        self.meta_path = os.path.join(root, "meta.json")
        os.makedirs(self.scenes_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self.meta = {"status": {}, "budget": {}, "target_words": 100000}
        self._load_meta()

    # ---- meta

    def _load_meta(self):
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    self.meta.update(data)
            except Exception:
                pass
        self.meta.setdefault("status", {})
        self.meta.setdefault("budget", {})
        self.meta.setdefault("target_words", 100000)

    def save_meta(self):
        tmp = self.meta_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.meta_path)

    def get_status(self, sid):
        return self.meta["status"].get(sid, ST_DRAFT)

    def set_status(self, sid, value):
        self.meta["status"][sid] = value
        self.save_meta()

    def get_budget(self, sid, default):
        try:
            return int(self.meta["budget"].get(sid, default))
        except Exception:
            return default

    def set_budget(self, sid, value):
        self.meta["budget"][sid] = int(value)
        self.save_meta()

    # ---- متن صحنه

    def path_for(self, sid):
        return os.path.join(self.scenes_dir, "%s.txt" % sid)

    def load_blocks(self, sid):
        """فهرست (نوع، متن) برمی‌گرداند."""
        p = self.path_for(sid)
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as fh:
            raw = fh.read()
        blocks = []
        for line in raw.split("\n"):
            btype = BLOCK_PLAIN
            for prefix, name in PREFIX_BLOCK.items():
                if line.startswith(prefix):
                    btype = name
                    line = line[len(prefix):]
                    break
            blocks.append((btype, line))
        while blocks and not blocks[-1][1].strip():
            blocks.pop()
        return blocks

    def save_blocks(self, sid, blocks):
        p = self.path_for(sid)
        self._backup(sid, p)
        out = []
        for btype, text in blocks:
            prefix = BLOCK_PREFIX.get(btype, "")
            out.append(prefix + text)
        while out and not out[-1].strip():
            out.pop()
        body = "\n".join(out)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, p)

    def _backup(self, sid, path):
        if not os.path.exists(path):
            return
        try:
            if os.path.getsize(path) == 0:
                return
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dst = os.path.join(self.backup_dir, "%s.%s.txt" % (sid, stamp))
            n = 1
            while os.path.exists(dst):
                dst = os.path.join(self.backup_dir,
                                   "%s.%s-%d.txt" % (sid, stamp, n))
                n += 1
                if n > 20:
                    return
            shutil.copy2(path, dst)
            olds = sorted(
                f for f in os.listdir(self.backup_dir)
                if f.startswith(sid + ".") and f.endswith(".txt")
            )
            for f in olds[:-self.MAX_BACKUPS]:
                try:
                    os.remove(os.path.join(self.backup_dir, f))
                except OSError:
                    pass
        except Exception:
            pass

    def plain_text(self, sid):
        return "\n".join(t for _, t in self.load_blocks(sid))

    def word_count(self, sid):
        return count_words(self.plain_text(sid))

    def known_ids(self):
        out = []
        for f in os.listdir(self.scenes_dir):
            if f.endswith(".txt"):
                out.append(f[:-4])
        return out

    def orphans(self, live_ids):
        live = set(live_ids)
        res = []
        for sid in self.known_ids():
            if sid not in live:
                wc = self.word_count(sid)
                if wc:
                    res.append((sid, wc))
        res.sort()
        return res


# ---------------------------------------------------------------- خروجی

def _blocks_to_md(blocks):
    out = []
    prev = BLOCK_PLAIN
    for btype, text in blocks:
        if not text.strip():
            out.append("")
            prev = BLOCK_PLAIN
            continue
        if btype != prev and out and out[-1].strip():
            out.append("")
        if btype == BLOCK_PLAIN:
            out.append(text)
        else:
            out.append("> " + text)
        prev = btype
    return out


def export_markdown(scenes, store, mode="reader", separator=SEPARATOR,
                    title=None):
    """mode: reader | working"""
    lines = []
    if title:
        lines.append("# " + title)
        lines.append("")

    cur_chapter = None
    first_in_chapter = True

    for sc in scenes:
        blocks = store.load_blocks(sc.sid)
        has_text = any(t.strip() for _, t in blocks)

        if sc.chapter != cur_chapter:
            cur_chapter = sc.chapter
            lines.append("")
            lines.append("## " + sc.chapter_label)
            lines.append("")
            first_in_chapter = True

        if mode == "working":
            lines.append("### %s — %s" % (sc.sid, sc.title))
            if sc.time:
                lines.append("*زمان:* " + sc.time)
            lines.append("*وضعیت:* %s · *کلمه:* %s"
                         % (store.get_status(sc.sid),
                            fa_num(count_words("\n".join(t for _, t in blocks)))))
            lines.append("")
            for para in sc.description:
                if para.strip():
                    lines.append("> " + para.strip())
                    lines.append(">")
            for name, val in sc.tags:
                lines.append("> **%s:** %s" % (name, val))
            lines.append("")
            lines.extend(_blocks_to_md(blocks) if has_text
                         else ["*(هنوز نوشته نشده)*"])
            lines.append("")
        else:
            if not has_text:
                continue
            if not first_in_chapter:
                lines.append("")
                lines.append(separator)
                lines.append("")
            first_in_chapter = False
            lines.extend(_blocks_to_md(blocks))

    text = "\n".join(lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text).strip() + "\n"
    return text


def export_scene_table(scenes, store, default_budget):
    rows = ["| شناسه | فصل | عنوان | وضعیت | کلمه | بودجه | تگ‌ها |",
            "|---|---|---|---|---|---|---|"]
    total = 0
    for sc in scenes:
        wc = store.word_count(sc.sid)
        total += wc
        budget = store.get_budget(sc.sid, default_budget)
        tags = "؛ ".join("%s: %s" % (n, v) for n, v in sc.tags)
        tags = tags.replace("|", "/")
        rows.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            sc.sid, sc.chapter, sc.title.replace("|", "/"),
            store.get_status(sc.sid), fa_num(wc), fa_num(budget), tags))
    rows.append("")
    rows.append("**جمع:** %s کلمه در %s صحنه."
                % (fa_num(total), fa_num(len(scenes))))
    return "\n".join(rows) + "\n"


# ================================================================ سند پلات
# PlotDoc: نمایشِ خطـ‌به‌خطِ فایل پلات برای ویرایش و بازنویسیِ بی‌اتلاف.
# هر تغییر روی خطوطِ خامِ همان بخش انجام می‌شود؛ بقیهٔ فایل دست نمی‌خورد.

KIND_LOOSE = "loose"
KIND_PART = "part"
KIND_CHAPTER = "chapter"
KIND_SCENE = "scene"

MIDDOT = "·"
DASH = "—"

_PART_HEAD = re.compile(r"^(?:دسته|دستهٔ|بخش)\b")
_SCENE_HEAD = re.compile(r"^###\s+(.*)$")


class Item:
    """یک تکهٔ پیوستهٔ فایل: سرفصل + خطوط زیرش."""

    __slots__ = ("kind", "lines", "sid", "title", "time", "name",
                 "chapter", "chapter_title", "label")

    def __init__(self, kind, lines):
        self.kind = kind
        self.lines = list(lines)
        self.sid = ""
        self.title = ""
        self.time = ""
        self.chapter = ""         # فصلِ نوشته‌شده در براکتِ خودِ صحنه
        self.name = ""            # نام فصل (ف۳) یا برچسب بخش
        self.chapter_title = ""
        self.label = ""

    # ---- نمایش

    @property
    def scene_label(self):
        return "%s %s %s" % (self.sid, DASH, self.title) if self.sid else self.title

    @property
    def chapter_label(self):
        if self.chapter_title:
            return "%s %s %s" % (self.name, DASH, self.chapter_title)
        return self.name

    @property
    def body(self):
        return "\n".join(self.lines[1:]).rstrip("\n")

    def set_body(self, text):
        """متن را با یک خطِ خالی قبل و بعد ذخیره می‌کند (قالبِ استانداردِ md)."""
        body = text.replace("\r\n", "\n").rstrip("\n")
        self.lines = [self.lines[0]] + body.split("\n") + [""]


def render_scene_head(sid, title, chapter="", time=""):
    if sid:
        head = "### %s" % sid
        if title:
            head += " %s %s" % (DASH, title)
    else:
        head = "### %s" % title
    bits = [b for b in (chapter, time) if b]
    if bits:
        head += " [%s]" % ((" %s " % MIDDOT).join(bits))
    return head


def render_chapter_head(name, title=""):
    return "## %s %s %s" % (name, DASH, title) if title else "## %s" % name


def _pick_bracket(raw):
    """آخرین براکتی که براکتِ فرادادهٔ صحنه است (براکتِ بولدشده را رد می‌کند)."""
    for m in reversed(list(_BRACKET.finditer(raw))):
        before = raw[max(0, m.start() - 2):m.start()]
        after = raw[m.end():m.end() + 2]
        if before.endswith("**") and after.startswith("**"):
            continue
        return m
    return None


def _split_scene_head(raw):
    """سرفصل صحنه را به (شناسه، عنوان، فصل، زمان) می‌شکند."""
    m = _SCENE_HEAD.match(raw)
    head = _BIDI.sub("", m.group(1)).strip() if m else ""
    chapter, time = "", ""
    bm = _pick_bracket(head)
    if bm:
        parts = [p.strip() for p in bm.group(1).split(MIDDOT)]
        head = (head[:bm.start()] + " " + head[bm.end():]).strip()
        if parts and re.match(r"^ف[\u06F0-\u06F9\d]", parts[0]):
            chapter, parts = parts[0], parts[1:]
        time = (" %s " % MIDDOT).join(p for p in parts if p)
    head = _MARKS.sub("", head).replace("\u25c8", "").strip()
    mid = _SCENE_ID.match(head)
    if mid:
        sid = "S" + mid.group(1)
        rest = head[mid.end():]
    else:
        sid, rest = "", head
    rest = re.sub(r"^\s*(?:%s|-|\u2013)\s*" % DASH, "", rest).strip()
    return sid, _strip_md(rest), chapter, time


class PlotDoc:
    """فایل پلات را به‌صورت فهرستی از تکه‌ها نگه می‌دارد و بازمی‌نویسد."""

    def __init__(self, path, head, items, tail, newline="\n"):
        self.path = path
        self.head = list(head)
        self.items = list(items)
        self.tail = list(tail)
        self.newline = newline
        self.dirty = False

    # ------------------------------------------------------------ خواندن

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            raw = fh.read()
        newline = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.replace("\r\n", "\n").split("\n")

        start, end = None, len(lines)
        for i, ln in enumerate(lines):
            m = _H1.match(ln)
            if not m:
                continue
            if start is None and "صحنه‌ها" in m.group(1):
                start = i + 1
            elif start is not None:
                end = i
                break
        if start is None:
            start, end = 0, len(lines)

        head, tail = lines[:start], lines[end:]
        items, cur = [], None

        def close():
            nonlocal cur
            if cur is not None:
                items.append(cur)
                cur = None

        for ln in lines[start:end]:
            m3 = _H3.match(ln)
            m2 = None if m3 else _H2.match(ln)
            if m3:
                close()
                cur = Item(KIND_SCENE, [ln])
                (cur.sid, cur.title, cur.chapter,
                 cur.time) = _split_scene_head(ln)
                continue
            if m2:
                close()
                head_txt = _strip_md(_MARKS.sub("", _BIDI.sub(
                    "", m2.group(1))).strip())
                head_txt = re.sub(r"✅.*$", "", head_txt).strip()
                if _PART_HEAD.match(head_txt):
                    cur = Item(KIND_PART, [ln])
                    pm = _PART.search(head_txt)
                    cur.label = pm.group(1) if pm else head_txt
                else:
                    cur = Item(KIND_CHAPTER, [ln])
                    cm = _CHAPTER.match(head_txt)
                    if cm:
                        cur.name = cm.group(1)
                        cur.chapter_title = re.sub(r"\s*\([^)]*\)\s*$", "",
                                                   cm.group(2)).strip()
                    else:
                        cur.name = re.sub(r"\s*\([^)]*\)\s*$", "",
                                          head_txt).strip()
                continue
            if cur is None:
                cur = Item(KIND_LOOSE, [])
            cur.lines.append(ln)
        close()
        return cls(path, head, items, tail, newline)

    # ------------------------------------------------------------ کمکی‌ها

    def kinds(self, kind):
        return [i for i, it in enumerate(self.items) if it.kind == kind]

    def scene_indices(self):
        return self.kinds(KIND_SCENE)

    def chapter_indices(self):
        return self.kinds(KIND_CHAPTER)

    def chapter_of(self, idx):
        """ایندکسِ تکهٔ فصلی که این تکه زیرش است (یا None)."""
        for j in range(idx - 1, -1, -1):
            if self.items[j].kind == KIND_CHAPTER:
                return j
            if self.items[j].kind == KIND_PART:
                return None
        return None

    def part_of(self, idx):
        for j in range(idx - 1, -1, -1):
            if self.items[j].kind == KIND_PART:
                return j
        return None

    def chapter_name(self, idx):
        ci = self.chapter_of(idx)
        return self.items[ci].name if ci is not None else ""

    def chapter_block(self, ci):
        """بازهٔ [شروع، پایان) تکه‌هایی که به این فصل تعلق دارند."""
        end = len(self.items)
        for j in range(ci + 1, len(self.items)):
            if self.items[j].kind in (KIND_CHAPTER, KIND_PART):
                end = j
                break
        return ci, end

    def part_block(self, pi):
        end = len(self.items)
        for j in range(pi + 1, len(self.items)):
            if self.items[j].kind == KIND_PART:
                end = j
                break
        return pi, end

    def next_sid(self):
        n = 0
        for i in self.scene_indices():
            m = re.match(r"^S(\d+)$", self.items[i].sid or "")
            if m:
                n = max(n, int(m.group(1)))
        return "S%d" % (n + 1)

    def sid_exists(self, sid, skip=None):
        for i in self.scene_indices():
            if i != skip and self.items[i].sid == sid:
                return True
        return False

    # ------------------------------------------------------------ ویرایش

    def _touch(self):
        self.dirty = True

    def _rewrite_scene_head(self, idx, old_sid=None, old_title=None):
        """سرفصل را جراحی می‌کند: نشانه‌هایی مثل ◈ و قالبِ دستیِ خط حفظ می‌شود."""
        it = self.items[idx]
        raw = it.lines[0]
        bare = raw.strip().lstrip("#").strip()
        if not bare:
            it.lines[0] = render_scene_head(it.sid, it.title, it.chapter,
                                            it.time)
            return
        bm = _pick_bracket(raw)
        if bm:
            body = raw[:bm.start()].rstrip()
            suffix = raw[bm.end():]
        else:
            body = raw.rstrip()
            suffix = ""
            m_tail = re.search(r"((?:\s*(?:%s))+)\s*$" % _MARKS.pattern, body)
            if m_tail:
                suffix = body[m_tail.start():]
                body = body[:m_tail.start()].rstrip()
        if old_title and it.title != old_title:
            if old_title in body:
                body = body.replace(old_title, it.title, 1)
            else:
                body = None
        if body is not None and old_sid and it.sid != old_sid:
            if old_sid in body:
                body = body.replace(old_sid, it.sid, 1)
            else:
                body = None
        if body is None:          # قالبِ خط قابلِ جراحی نبود — از نو ساخته شود
            it.lines[0] = render_scene_head(it.sid, it.title, it.chapter,
                                            it.time)
            return
        bits = [b for b in (it.chapter, it.time) if b]
        it.lines[0] = body + (" [%s]" % ((" %s " % MIDDOT).join(bits))
                              if bits else "") + suffix

    def _retag_chapter(self, idx):
        """بعد از جابه‌جایی: اگر صحنه براکتِ فصل داشت، با فصل تازه جایگزین شود."""
        it = self.items[idx]
        if it.chapter:
            it.chapter = self.chapter_name(idx) or it.chapter
        self._rewrite_scene_head(idx)

    def set_scene(self, idx, sid=None, title=None, time=None, body=None,
                  chapter=None):
        it = self.items[idx]
        old_sid, old_title = it.sid, it.title
        if chapter is not None:
            it.chapter = chapter.strip()
        if sid is not None:
            it.sid = sid.strip()
        if title is not None:
            it.title = title.strip()
        if time is not None:
            it.time = time.strip()
        if body is not None:
            it.set_body(body)
        self._rewrite_scene_head(idx, old_sid, old_title)
        self._touch()

    def add_scene(self, after=None, chapter_index=None, sid=None, title="",
                  time="", body=""):
        """صحنهٔ تازه بعد از صحنهٔ after یا در انتهای فصل chapter_index."""
        sid = sid or self.next_sid()
        it = Item(KIND_SCENE, ["### "])
        it.sid, it.title, it.time = sid, title, time
        it.set_body(body or "")
        if after is not None:
            pos = after + 1
        elif chapter_index is not None:
            pos = self.chapter_block(chapter_index)[1]
        else:
            pos = len(self.items)
        self.items.insert(pos, it)
        it.chapter = self.chapter_name(pos)
        self._rewrite_scene_head(pos)
        self._touch()
        return pos

    def delete_scene(self, idx):
        if self.items[idx].kind != KIND_SCENE:
            return False
        self.items.pop(idx)
        self._touch()
        return True

    def move_scene(self, idx, delta):
        """یک پله بالا/پایین؛ از مرز فصل که رد شود، فصلش هم عوض می‌شود."""
        scenes = self.scene_indices()
        if idx not in scenes:
            return None
        k = scenes.index(idx)
        k2 = k + (1 if delta > 0 else -1)
        if not (0 <= k2 < len(scenes)):
            return None
        j = scenes[k2]
        same = self.chapter_of(idx) == self.chapter_of(j)
        it = self.items.pop(idx)
        if delta > 0:
            pos = j if same else j - 1
        else:
            pos = j if same else j + 1
        self.items.insert(pos, it)
        self._retag_chapter(pos)
        self._touch()
        return pos

    def move_scene_to_chapter(self, idx, chapter_index, at_start=False):
        if self.items[idx].kind != KIND_SCENE:
            return None
        it = self.items.pop(idx)
        ci = chapter_index - (1 if chapter_index > idx else 0)
        start, end = self.chapter_block(ci)
        pos = start + 1 if at_start else end
        self.items.insert(pos, it)
        it.chapter = self.items[ci].name or it.chapter
        self._rewrite_scene_head(pos)
        self._touch()
        return pos

    def move_chapter(self, ci, delta):
        """کلِ فصل با صحنه‌هایش جابه‌جا می‌شود (درونِ همان بخش یا فراتر)."""
        chapters = self.chapter_indices()
        if ci not in chapters:
            return None
        k = chapters.index(ci)
        k2 = k + (1 if delta > 0 else -1)
        if not (0 <= k2 < len(chapters)):
            return None
        s1, e1 = self.chapter_block(ci)
        s2, e2 = self.chapter_block(chapters[k2])
        block = self.items[s1:e1]
        rest = self.items[:s1] + self.items[e1:]
        if delta > 0:
            pos = e2 - (e1 - s1)
        else:
            pos = s2
        self.items = rest[:pos] + block + rest[pos:]
        for n in range(pos, pos + len(block)):
            if self.items[n].kind == KIND_SCENE:
                self._retag_chapter(n)
        self._touch()
        return pos

    def add_chapter(self, name, title="", after_chapter=None, part_index=None):
        it = Item(KIND_CHAPTER, [render_chapter_head(name, title), ""])
        it.name, it.chapter_title = name, title
        if after_chapter is not None:
            pos = self.chapter_block(after_chapter)[1]
        elif part_index is not None:
            pos = self.part_block(part_index)[1]
        else:
            pos = len(self.items)
        self.items.insert(pos, it)
        self._touch()
        return pos

    def set_chapter(self, ci, name=None, title=None):
        it = self.items[ci]
        if it.kind != KIND_CHAPTER:
            return
        if name is not None:
            it.name = name.strip()
        if title is not None:
            it.chapter_title = title.strip()
        it.lines[0] = render_chapter_head(it.name, it.chapter_title)
        s, e = self.chapter_block(ci)
        for n in range(s, e):
            if self.items[n].kind == KIND_SCENE:
                self._retag_chapter(n)
        self._touch()

    def delete_chapter(self, ci, with_scenes=False):
        """فصل را برمی‌دارد. با with_scenes=False صحنه‌ها سرِ جایشان می‌مانند."""
        s, e = self.chapter_block(ci)
        if with_scenes:
            del self.items[s:e]
        else:
            self.items.pop(s)
        self._touch()

    def add_part(self, label, after_part=None):
        it = Item(KIND_PART, ["## %s" % label, ""])
        it.label = label
        pos = (self.part_block(after_part)[1] if after_part is not None
               else len(self.items))
        self.items.insert(pos, it)
        self._touch()
        return pos

    def set_part(self, pi, label):
        it = self.items[pi]
        if it.kind != KIND_PART:
            return
        it.label = label.strip()
        it.lines[0] = "## %s" % it.label
        self._touch()

    def move_part(self, pi, delta):
        parts = self.kinds(KIND_PART)
        if pi not in parts:
            return None
        k = parts.index(pi)
        k2 = k + (1 if delta > 0 else -1)
        if not (0 <= k2 < len(parts)):
            return None
        s1, e1 = self.part_block(pi)
        s2, e2 = self.part_block(parts[k2])
        block = self.items[s1:e1]
        rest = self.items[:s1] + self.items[e1:]
        pos = e2 - (e1 - s1) if delta > 0 else s2
        self.items = rest[:pos] + block + rest[pos:]
        self._touch()
        return pos

    # ------------------------------------------------------------ نوشتن

    def render(self):
        out = list(self.head)
        for it in self.items:
            out.extend(it.lines)
        out.extend(self.tail)
        text = "\n".join(out)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        if not text.endswith("\n"):
            text += "\n"
        return text.replace("\n", self.newline) if self.newline != "\n" else text

    def backup(self, folder=None):
        if not os.path.exists(self.path):
            return None
        folder = folder or os.path.join(os.path.dirname(self.path),
                                        "plot_backups")
        os.makedirs(folder, exist_ok=True)
        base = os.path.basename(self.path)
        dst = os.path.join(folder, "%s.%s.bak" % (
            base, time.strftime("%Y%m%d-%H%M%S")))
        n = 1
        while os.path.exists(dst):
            dst = os.path.join(folder, "%s.%s-%d.bak" % (
                base, time.strftime("%Y%m%d-%H%M%S"), n))
            n += 1
        shutil.copy2(self.path, dst)
        olds = sorted(f for f in os.listdir(folder)
                      if f.startswith(base + ".") and f.endswith(".bak"))
        for f in olds[:-20]:
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass
        return dst

    def save(self, path=None, backup=True):
        target = path or self.path
        if backup and os.path.abspath(target) == os.path.abspath(self.path):
            self.backup()
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.render())
        os.replace(tmp, target)
        self.path = target
        self.dirty = False
        return target

    def next_version_path(self):
        """…_v47.md → …_v48.md ؛ اگر شماره نداشت، _v2 می‌گیرد."""
        folder, base = os.path.split(self.path)
        stem, ext = os.path.splitext(base)
        m = re.search(r"_v(\d+)$", stem)
        if m:
            width = len(m.group(1))
            nxt = str(int(m.group(1)) + 1).zfill(width)
            stem = stem[:m.start()] + "_v" + nxt
        else:
            stem += "_v2"
        p = os.path.join(folder, stem + ext)
        n = 2
        while os.path.exists(p):
            p = os.path.join(folder, "%s-%d%s" % (stem, n, ext))
            n += 1
        return p


# ------------------------------------------------------------ تمپلیت پلات

PLOT_TEMPLATE = """# <عنوان اثر>

<یک خط دربارهٔ اثر — این بخش دست‌نخورده می‌ماند.>

# صحنه‌ها

## بخش یک

## ف۱ %(d)s <عنوان فصل>

### S1 %(d)s <عنوان صحنه> [ف۱ %(m)s <زمان>]

<توضیح صحنه: چه اتفاقی می‌افتد، از دید که، با چه پایانی.>

*هدف:* <چرا این صحنه در کتاب است>
*تگ:* <هر تگ دلخواه>

### S2 %(d)s <عنوان صحنه> [ف۱ %(m)s <زمان>]

<توضیح صحنه>
""" % {"d": DASH, "m": MIDDOT}


def write_template(path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(PLOT_TEMPLATE)
    return path
