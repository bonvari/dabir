# -*- coding: utf-8 -*-
"""آزمون‌های هستهٔ دبیر — بدون Qt، فقط تجزیه، ویرایش و ذخیره‌سازی.

اجرا:  pytest -q        یا        python tests/test_core.py
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sw_core as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(os.path.dirname(HERE), "examples", "sample_plot.md")


def fresh(tmp, src=SAMPLE):
    """یک کپیِ دست‌نخورده از پلاتِ نمونه در پوشهٔ موقت."""
    dst = os.path.join(tmp, "plot.md")
    shutil.copy(src, dst)
    return dst


def ids(doc):
    return [doc.items[i].sid for i in doc.scene_indices()]


def chapter_names(doc):
    return [doc.items[i].name for i in doc.chapter_indices()]


# ---------------------------------------------------------------- تجزیه

def test_parse_plot():
    scenes = C.parse_plot(SAMPLE)
    assert [s.sid for s in scenes] == ["S%d" % n for n in range(1, 8)]
    assert scenes[0].chapter == "ف۱"
    assert scenes[0].time == "صبحِ سه‌شنبه"
    assert scenes[0].part == "بخش یک"
    assert scenes[-1].part == "بخش دو"
    assert any(name == "هدف" for name, _ in scenes[0].tags)
    assert any(d.strip() for d in scenes[0].description)


def test_plotdoc_structure():
    doc = C.PlotDoc.load(SAMPLE)
    assert len(doc.scene_indices()) == 7
    assert chapter_names(doc) == ["ف۱", "ف۲", "ف۳"]
    assert len(doc.kinds(C.KIND_PART)) == 2
    assert doc.chapter_name(doc.scene_indices()[0]) == "ف۱"
    assert doc.next_sid() == "S8"


def test_scene_id_variants():
    assert C._SCENE_ID.match("S12 — x").group(1) == "12"
    assert C._SCENE_ID.match("S77.3 — x").group(1) == "77.3"
    assert C._SCENE_ID.match("میان‌پرده") is None


# ------------------------------------------------- بی‌اتلاف بودنِ نوشتن

def test_round_trip_is_byte_identical():
    doc = C.PlotDoc.load(SAMPLE)
    assert doc.render() == open(SAMPLE, encoding="utf-8").read()


def test_noop_edit_changes_nothing():
    """ویرایشِ بی‌اثر روی هر صحنه نباید حتی یک بایت را عوض کند."""
    raw = open(SAMPLE, encoding="utf-8").read()
    doc = C.PlotDoc.load(SAMPLE)
    for i in doc.scene_indices():
        it = doc.items[i]
        doc.set_scene(i, sid=it.sid, title=it.title, time=it.time,
                      chapter=it.chapter, body=it.body)
    assert doc.render() == raw


def test_decorations_survive():
    """نشانه‌های دستی در سرفصل (◈ 🔒 بولد) پس از ویرایش می‌مانند."""
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "p.md")
        open(p, "w", encoding="utf-8").write(
            "# صحنه‌ها\n\n## ف۱ — یک\n\n"
            "### ◈ S1 — الف [ف۱ · صبح] 🔒\n\nمتن.\n\n"
            "### S2 — ب [ف۱] **[v3]**\n\nمتن.\n")
        doc = C.PlotDoc.load(p)
        i0, i1 = doc.scene_indices()
        doc.set_scene(i0, title="الفِ تازه")
        doc.set_scene(i1, time="شب")
        out = doc.render()
        assert "### ◈ S1 — الفِ تازه [ف۱ · صبح] 🔒" in out
        assert "### S2 — ب [ف۱ · شب] **[v3]**" in out
    finally:
        shutil.rmtree(tmp)


def test_outside_scene_area_untouched():
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        doc.move_scene(doc.scene_indices()[0], 1)
        out = doc.render()
        assert "# کلیدساز" in out
        assert "**وضعیت:** نمونه" in out
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------------ جابه‌جایی

def test_move_down_then_up_restores_order():
    tmp = tempfile.mkdtemp()
    try:
        p = fresh(tmp)
        raw = open(p, encoding="utf-8").read()
        doc = C.PlotDoc.load(p)
        i = doc.scene_indices()[0]
        pos = doc.move_scene(i, 1)
        assert ids(doc)[:2] == ["S2", "S1"]
        doc.move_scene(pos, -1)
        assert doc.render() == raw
    finally:
        shutil.rmtree(tmp)


def test_move_across_chapter_boundary_retags():
    """صحنه که از مرزِ فصل رد شود، فصل و براکتش عوض می‌شوند."""
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        i = [x for x in doc.scene_indices() if doc.items[x].sid == "S3"][0]
        assert doc.chapter_name(i) == "ف۱"
        pos = doc.move_scene(i, 1)
        assert doc.chapter_name(pos) == "ف۲"
        assert doc.items[pos].chapter == "ف۲"
        assert ids(doc)[:4] == ["S1", "S2", "S4", "S3"] or \
            ids(doc)[2:4] == ["S3", "S4"]
    finally:
        shutil.rmtree(tmp)


def test_move_scene_to_chapter():
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        ci = doc.chapter_indices()[2]            # ف۳
        i = doc.scene_indices()[0]               # S1
        pos = doc.move_scene_to_chapter(i, ci)
        assert doc.chapter_name(pos) == "ف۳"
        assert doc.items[pos].chapter == "ف۳"
        assert ids(doc)[-1] == "S1"
    finally:
        shutil.rmtree(tmp)


def test_move_chapter_carries_its_scenes():
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        doc.move_chapter(doc.chapter_indices()[0], 1)
        assert chapter_names(doc) == ["ف۲", "ف۱", "ف۳"]
        assert ids(doc) == ["S4", "S5", "S6", "S1", "S2", "S3", "S7"]
        for i in doc.scene_indices():
            assert doc.items[i].chapter == doc.chapter_name(i)
    finally:
        shutil.rmtree(tmp)


def test_move_at_edges_returns_none():
    doc = C.PlotDoc.load(SAMPLE)
    assert doc.move_scene(doc.scene_indices()[0], -1) is None
    assert doc.move_scene(doc.scene_indices()[-1], 1) is None


# --------------------------------------------------- افزودن، ویرایش، حذف

def test_add_scene_after_and_in_chapter():
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        pos = doc.add_scene(after=doc.scene_indices()[0], title="میانی")
        assert doc.items[pos].sid == "S8"
        assert ids(doc)[:3] == ["S1", "S8", "S2"]
        assert doc.items[pos].chapter == "ف۱"
        pos2 = doc.add_scene(chapter_index=doc.chapter_indices()[1],
                             title="ته فصل دو")
        assert doc.chapter_name(pos2) == "ف۲"
        assert "### S9 — ته فصل دو [ف۲]" in doc.render()
    finally:
        shutil.rmtree(tmp)


def test_sid_uniqueness_helpers():
    doc = C.PlotDoc.load(SAMPLE)
    assert doc.sid_exists("S3")
    assert not doc.sid_exists("S99")
    i = doc.scene_indices()[2]
    assert not doc.sid_exists("S3", skip=i)


def test_delete_scene_and_chapter():
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        doc.delete_scene(doc.scene_indices()[0])
        assert "S1" not in ids(doc)
        assert "## ف۱ — مغازه‌ای که کلید نمی‌سازد" in doc.render()

        doc2 = C.PlotDoc.load(fresh(tmp))
        doc2.delete_chapter(doc2.chapter_indices()[0], with_scenes=False)
        assert ids(doc2) == ["S%d" % n for n in range(1, 8)]
        assert chapter_names(doc2) == ["ف۲", "ف۳"]

        doc3 = C.PlotDoc.load(fresh(tmp))
        doc3.delete_chapter(doc3.chapter_indices()[0], with_scenes=True)
        assert ids(doc3) == ["S4", "S5", "S6", "S7"]
    finally:
        shutil.rmtree(tmp)


def test_chapter_and_part_editing():
    tmp = tempfile.mkdtemp()
    try:
        doc = C.PlotDoc.load(fresh(tmp))
        doc.set_chapter(doc.chapter_indices()[0], name="ف۰", title="پیش‌درآمد")
        out = doc.render()
        assert "## ف۰ — پیش‌درآمد" in out
        assert "### S1 — کرکرهٔ نیمه‌باز [ف۰ · صبحِ سه‌شنبه]" in out
        doc.set_part(doc.kinds(C.KIND_PART)[0], "دفترِ اول")
        assert "## دفترِ اول" in doc.render()
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------- ذخیره و بکاپ

def test_save_makes_backup_and_keeps_original():
    tmp = tempfile.mkdtemp()
    try:
        p = fresh(tmp)
        raw = open(p, encoding="utf-8").read()
        doc = C.PlotDoc.load(p)
        doc.set_scene(doc.scene_indices()[0], title="عنوانِ نو")
        doc.save()
        folder = os.path.join(tmp, "plot_backups")
        backups = os.listdir(folder)
        assert len(backups) == 1
        assert open(os.path.join(folder, backups[0]),
                    encoding="utf-8").read() == raw
        assert "عنوانِ نو" in open(p, encoding="utf-8").read()
        assert not doc.dirty
    finally:
        shutil.rmtree(tmp)


def test_next_version_path():
    doc = C.PlotDoc.load(SAMPLE)
    doc.path = "/x/PLOT_v47.md"
    assert doc.next_version_path() == "/x/PLOT_v48.md"
    doc.path = "/x/PLOT_v09.md"
    assert doc.next_version_path() == "/x/PLOT_v10.md"
    doc.path = "/x/plot.md"
    assert doc.next_version_path() == "/x/plot_v2.md"


def test_crlf_is_preserved():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "p.md")
        body = "# صحنه‌ها\r\n\r\n## ف۱ — یک\r\n\r\n### S1 — الف [ف۱]\r\n\r\nمتن.\r\n"
        open(p, "w", encoding="utf-8", newline="").write(body)
        doc = C.PlotDoc.load(p)
        doc.save(backup=False)
        assert open(p, "rb").read().count(b"\r\n") >= 5
    finally:
        shutil.rmtree(tmp)


# -------------------------------------------------------- ذخیرهٔ نثر

def test_store_blocks_round_trip():
    tmp = tempfile.mkdtemp()
    try:
        st = C.Store(tmp)
        blocks = [(C.BLOCK_PLAIN, "خطِ یک."),
                  (C.BLOCK_DREAM, "خوابی کوتاه."),
                  (C.BLOCK_INTERLUDE, "میان‌پرده."),
                  (C.BLOCK_QUOTE, "نقلِ قول.")]
        st.save_blocks("S1", blocks)
        assert st.load_blocks("S1") == blocks
        assert st.word_count("S1") == 7
    finally:
        shutil.rmtree(tmp)


def test_store_backup_and_orphans():
    tmp = tempfile.mkdtemp()
    try:
        st = C.Store(tmp)
        st.save_blocks("S1", [(C.BLOCK_PLAIN, "نسخهٔ یک.")])
        st.save_blocks("S1", [(C.BLOCK_PLAIN, "نسخهٔ دو.")])
        assert len(os.listdir(os.path.join(tmp, "backups"))) == 1
        st.save_blocks("S2", [(C.BLOCK_PLAIN, "نثرِ صحنهٔ حذف‌شده.")])
        assert st.orphans(["S1"]) == [("S2", 3)]
        assert st.orphans(["S1", "S2"]) == []
    finally:
        shutil.rmtree(tmp)


def test_status_and_budget():
    tmp = tempfile.mkdtemp()
    try:
        st = C.Store(tmp)
        assert st.get_status("S1") == C.ST_DRAFT
        st.set_status("S1", C.ST_DONE)
        st.set_budget("S1", 900)
        again = C.Store(tmp)
        assert again.get_status("S1") == C.ST_DONE
        assert again.get_budget("S1", 100) == 900
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------------- خروجی

def test_export_reader_and_working():
    tmp = tempfile.mkdtemp()
    try:
        st = C.Store(tmp)
        scenes = C.parse_plot(SAMPLE)
        st.save_blocks("S1", [(C.BLOCK_PLAIN, "کرکره بالا رفت.")])
        st.save_blocks("S2", [(C.BLOCK_PLAIN, "مرد پول را گذاشت.")])
        reader = C.export_markdown(scenes[:3], st, mode="reader")
        assert "کرکره بالا رفت." in reader
        assert C.SEPARATOR in reader            # میانِ دو صحنهٔ نوشته‌شده
        assert "*وضعیت:*" not in reader
        assert "هدف" not in reader              # فرادادهٔ پلات نمی‌آید
        working = C.export_markdown(scenes[:3], st, mode="working")
        assert "*وضعیت:*" in working
        assert "*(هنوز نوشته نشده)*" in working  # S3 خالی است
    finally:
        shutil.rmtree(tmp)


def test_export_table():
    tmp = tempfile.mkdtemp()
    try:
        st = C.Store(tmp)
        scenes = C.parse_plot(SAMPLE)
        st.save_blocks("S1", [(C.BLOCK_PLAIN, "یک دو سه.")])
        tbl = C.export_scene_table(scenes, st, 500)
        assert tbl.startswith("| شناسه |")
        assert "جمع:" in tbl
        assert len(tbl.strip().split("\n")) == len(scenes) + 4
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------------ تمپلیت

def test_template_is_parseable():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "t.md")
        C.write_template(p)
        doc = C.PlotDoc.load(p)
        assert len(doc.scene_indices()) == 2
        assert len(doc.chapter_indices()) == 1
        assert len(doc.kinds(C.KIND_PART)) == 1
        assert doc.render() == open(p, encoding="utf-8").read()
        assert len(C.parse_plot(p)) == 2
    finally:
        shutil.rmtree(tmp)


def test_fa_num():
    assert C.fa_num(1405) == "۱۴۰۵"
    assert C.fa_num("S12") == "S۱۲"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        try:
            fn()
            print("  ok    %s" % fn.__name__)
        except AssertionError as exc:
            bad += 1
            print("  FAIL  %s  %s" % (fn.__name__, exc))
    print("\n%d/%d" % (len(fns) - bad, len(fns)))
    sys.exit(1 if bad else 0)
