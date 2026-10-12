"""test_build_essay_page.py — 长文页：Vault 公开写作/文章 → essays/<slug>.html + data/essays.json"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "build_essay_page.py"
spec = importlib.util.spec_from_file_location("build_essay_page", MODULE_PATH)
bep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bep)

ESSAY = """---
type: essay
title: 示例长文
created: 2026-10-12
status: {status}
published_at: 2026-10-12
data_asof: 2026-10-09 收盘（内部备注）
summary: 一句话导语
---

# 示例长文

第一句。
第二句。

## 小节

**一、加粗小标题**

正文里有「引号」和 **重点**。

![图 1 · 示例](附件/fig.png)

---

结尾。
"""


class EssayPageTests(unittest.TestCase):
    def _write(self, root: Path, status: str = "published") -> Path:
        (root / "附件").mkdir(parents=True)
        (root / "附件" / "fig.png").write_bytes(b"\x89PNG")
        src = root / "2026-10-12-示例.md"
        src.write_text(ESSAY.format(status=status), encoding="utf-8")
        return src

    def test_published_essay_renders_with_assets_and_manifest_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = self._write(tmp / "src")
            rec = bep.build_essay(src, tmp / "essays")
            page = Path(rec["target"]).read_text(encoding="utf-8")
            self.assertEqual(rec["slug"], "2026-10-12")
            self.assertEqual(rec["href"], "essays/2026-10-12.html")
            self.assertTrue(rec["cover"].startswith("essays/2026-10-12/"))
            self.assertEqual(rec["lede"], "第一句。\n第二句。")
            self.assertTrue((tmp / "essays" / "2026-10-12" / "fig1.png").is_file())
            self.assertEqual(rec["cover"], "essays/2026-10-12/fig1.png")
            self.assertIn('src="2026-10-12/fig1.png"', page)
            # 正文整段包进红线豁免标记（与每日页同一约定）
            self.assertIn('<div class="writing-body" data-public-writing="verbatim">', page)
            # 正文开头的 H1 与页面标题重复，去掉
            self.assertEqual(page.count("示例长文</h1>"), 1)
            self.assertIn('<h3 class="sub">一、加粗小标题</h3>', page)
            self.assertIn("<hr>", page)
            self.assertIn("<figcaption>图 1 · 示例</figcaption>", page)
            # 内部备注不上页面
            self.assertNotIn("内部备注", page)
            self.assertNotIn("预览", page)

    def test_draft_is_refused_unless_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = self._write(tmp / "src", status="draft")
            with self.assertRaises(ValueError):
                bep.build_essay(src, tmp / "essays")
            rec = bep.build_essay(src, tmp / "essays", preview=True)
            self.assertIn("预览 · 未发布", Path(rec["target"]).read_text(encoding="utf-8"))

    def test_empty_index_writes_empty_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            index = tmp / "wi.json"
            index.write_text(json.dumps({"entries": []}), encoding="utf-8")
            manifest = tmp / "essays.json"
            code = bep.main(["--writing-index", str(index), "--writing-root", str(tmp),
                             "--out", str(tmp / "essays"), "--manifest", str(manifest)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["essays"], [])


if __name__ == "__main__":
    unittest.main()
