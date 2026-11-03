#!/usr/bin/env python3
"""把原站 HTML 复刻为「离线双击即可用」的中文单文件图库。

构建输入
    site_raw.html          原站（ai-pose-depth-gallery.pages.dev）原始 HTML
    i18n.py                日→中 翻译词典

构建输出
    data/pose-depth-zh.json  结构化数据（中文，字段与姊妹项目统一）
    index.html               最终页面：样式 / 逻辑 / 1439 条数据全部内联

相对原站只做四件事
    1. 全量中文化：体系、分类、姿势名称、角度、界面文案、说明面板
    2. 数据内联保留（原站即为内联，file:// 下可直接渲染）
    3. 移除 Cloudflare 统计埋点，本地副本不回传数据
    4. 图片走相对路径 thumbs/ img/，CSP 收紧为仅本地
"""
import json
import os
import re
from urllib.parse import quote

from i18n import cat_map, name_map

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "site_raw.html")
OUT = os.path.join(ROOT, "index.html")
DATA_OUT = os.path.join(ROOT, "data", "pose-depth-zh.json")

# 字段名：与姊妹项目 AI-Pose-Resource-Library 保持一致
KEY_MAP = {
    "系統": "体系",
    "ポーズ番号": "姿势编号",
    "分類": "分类",
    "ポーズ名": "姿势名称",
    "アングル": "角度",
    "サムネ": "缩略图",
    "原寸": "原图",
}
ANG_MAP = {"正面": "正面", "上から": "俯视", "下から": "仰视", "横": "侧面", "斜め": "斜侧"}

UI = [
    ("default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline' https://static.cloudflareinsights.com; connect-src https://cloudflareinsights.com",
     "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'"),
    ('<html lang="ja">', '<html lang="zh-CN">'),
    ('<title>depthポーズ集 POSE-DB-02</title>', '<title>depth 姿势集 POSE-DB-02（中文版）</title>'),
    ('"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans CJK JP","Yu Gothic UI",Meiryo,sans-serif',
     '"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif'),

    # 顶部标签
    ('POSE-DB-02 ・ 画像参照用ポーズ集（depth版）', 'POSE-DB-02 ・ 图像参考用姿势集（depth 深度版）'),
    ('aria-label="使い方のヒント・注意点"', 'aria-label="使用提示・注意事项"'),
    ('>使い方のヒント</button>', '>使用提示</button>'),
    ('>注意点</button>', '>注意事项</button>'),
    ('<h2 id="ipt0">使い方のヒント</h2>', '<h2 id="ipt0">使用提示</h2>'),
    ('<h2 id="ipt1">注意点</h2>', '<h2 id="ipt1">注意事项</h2>'),
    ('aria-label="閉じる">×', 'aria-label="关闭">×'),

    # 提示内容
    ('深度マップ（depth・白いほど手前）です。各種AIツールの深度参照（depth）機能に読み込みます。',
     '这是深度图（depth・越白越靠前）。可载入各类 AI 工具的深度参考（depth）功能中使用。'),
    ('同じポーズの画像を続けて使うと、生成する画像・動画の姿勢が揃いやすくなります。',
     '连续使用同一姿势的图像，更容易让生成的图片、视频姿态保持一致。'),
    ('元サイズのPNGをダウンロードして使うと、細部まで参照できます。',
     '下载原始尺寸的 PNG 来使用，可以参照到更多细节。'),
    ('顔・服装・背景は入っていません。プロンプトや別の参照画像（顔の参照画像など）で足してください。',
     '不包含脸部、服装和背景。请通过提示词或另外的参考图（如脸部参考图）来补充。'),

    # 注意事项
    ('depthは前後関係の見本です。指や重なった脚の境目は弱くなります。',
     'depth 只是前后关系的示例。手指以及交叠双腿的边界会较弱。'),
    ('無償で利用できます（作品制作での商用利用・編集・参考利用OK）。',
     '可免费使用（用于作品制作的商用使用、编辑、参考使用均可）。'),
    ('画像データそのもの（元サイズ・加工後を含む）の再配布・転載・再販は禁止です。',
     '禁止再分发、转载、转售图像数据本身（包括原始尺寸及加工后的版本）。'),
    ('このデータベースの画像を一括でダウンロードすること（ツール等による自動取得を含む）と、取得した画像の再配布・転載・販売は禁止です。</strong>生成の参考に1枚ずつ使う分は、これまでどおりご利用いただけます。',
     '禁止批量下载本数据库的图像（包括通过工具等自动获取），以及再分发、转载、销售所获取的图像。</strong>用于生成参考而逐张使用的情况，仍可照常使用。'),
    ('クレジット表記は不要です（任意）。画像のメタデータは削除済みです。無保証でご利用ください。',
     '无需标注出处（可选）。图像元数据已删除。请自行承担使用风险。'),
    ('元はマネキンのポーズ画像で、実在の人物ではありません。',
     '原始素材为人台模特姿势图，并非真实人物。'),
    ('実在人物や未成年を表す用途、公序良俗に反する用途には使わないでください。',
     '请勿用于表现真实人物或未成年人、以及违反公序良俗的用途。'),

    # 主标题
    ('<h1><span>ポーズ集</span> depthデータベース</h1>',
     '<h1><span>姿势集</span> depth 数据库</h1>'),
    ('顔なしグレーマネキンのポーズの深度マップ（depth・3:4）。白いほど手前です。正面・上から・下から・横・斜めのアングルで見比べられます。',
     '无脸灰色人台模特的姿势深度图（depth・3:4）。越白越靠前。可从正面、俯视、仰视、侧面、斜侧等视角进行对比。'),
    ('画像の一括ダウンロード（自動取得を含む）・再配布・転載・販売は禁止です。',
     '禁止批量下载（包括自动获取）・再分发・转载・销售图像。'),

    # CTA
    ('ポーズ集の有効活用（無検閲AIの活用など）はオープンチャットで公開',
     '姿势集的高效用法（如无审查 AI 的使用等）在开放聊天中公开'),
    ('>オープンチャットに参加する<', '>加入开放聊天<'),
    ('>制作者　ギア<', '>制作者：ギア<'),

    # 工具栏
    ('placeholder="ポーズ名・ID・分類で検索"', 'placeholder="按姿势名・ID・分类搜索"'),
    ('>絞り込み<b id="fn"></b>', '>筛选<b id="fn"></b>'),
    ('>ポーズごと</button>', '>按姿势</button>'),
    ('>1枚ずつ</button>', '>逐张</button>'),

    # 模态框
    ('aria-label="拡大表示"', 'aria-label="放大显示"'),
    ('aria-label="前のアングル"', 'aria-label="上一个视角"'),
    ('aria-label="次のアングル"', 'aria-label="下一个视角"'),
    ('>depthをダウンロード（PNG）<', '>下载 depth（PNG）<'),
    ('<kbd>←</kbd><kbd>→</kbd> アングル切替　<kbd>↑</kbd><kbd>↓</kbd> 前後のポーズ　<kbd>Esc</kbd> 閉じる',
     '<kbd>←</kbd><kbd>→</kbd> 切换视角　<kbd>↑</kbd><kbd>↓</kbd> 前后姿势　<kbd>Esc</kbd> 关闭'),

    # JS 动态文案
    ("['','すべて',D.length,POSES.length]", "['','全部',D.length,POSES.length]"),
    ('${fmt(n)}枚・${fmt(np)}ポーズ', '${fmt(n)} 张・${fmt(np)} 个姿势'),
    ('>分類：すべて</option>', '>分类：全部</option>'),
    ("a||'全アングル'", "a||'全部视角'"),
    ('${fmt(ps.length)}ポーズ・${fmt(ps.reduce((n,p)=>n+p.items.filter(hit).length,0))}枚を表示',
     '${fmt(ps.length)} 个姿势・${fmt(ps.reduce((n,p)=>n+p.items.filter(hit).length,0))} 张'),
    ('${fmt(ds.length)}枚を表示', '${fmt(ds.length)} 张'),
    ('"><b>${D.length?\'条件に合う画像がありません\':\'画像がありません\'}</b>${D.length?\'絞り込みを変えてみてください。\':\'\'}</div>`',
     '"><b>${D.length?\'没有符合条件的图像\':\'暂无图像\'}</b>${D.length?\'请尝试更改筛选条件。\':\'\'}</div>`'),

    # JS 注释
    ('// ポーズ単位にまとめる', '// 按姿势归组'),
    ('件数カードは廃止し、枚数・ポーズ数はタブに表示する', '取消数量卡片，张数与姿势数显示在标签上'),
    ('// 10/26 11:23 あぎさん指示：', '// 10/26 11:23 需求：'),
]

COMMENTS = [
    ('/* ヘッダー */', '/* 页头 */'),
    ('/* 右上のタブ（使い方のヒント・注意点）10/26 11:22 */', '/* 右上角标签（使用提示・注意事项）10/26 11:22 */'),
    ('/* ツールバー */', '/* 工具栏 */'),
    ('/* グリッド */', '/* 网格 */'),
    ('/* モーダル */', '/* 模态框 */'),
    ('/* クレジット（オープンチャットへのボタン＋制作者チップ）。文字は build_index.py の定数だけ、装飾はCSSだけ */',
     '/* 版权区（开放聊天按钮＋制作者标签）。文字仅取自 build_index.py 的常量，样式全部由 CSS 控制 */'),
    ('/* フッターの再掲（小さめ。タップ領域は48px以上） */', '/* 页脚重复展示（较小。点击区域 48px 以上） */'),
    ('/* 右上のタブ：押すと開く／もう一度・×・Esc・外側クリックで閉じる */',
     '/* 右上角标签：点击展开／再次点击・×・Esc・点击外部关闭 */'),
    ('// 画像のある系統だけを使う（タブ・ヘッダー）', '// 仅使用有图像的系列（标签・页头）'),
    ('// タブ', '// 标签'),
    ('// モーダルでの前後移動用（表示中の順）', '// 模态框内前后切换用（按当前显示顺序）'),
    ('// カード操作：ストリップでメイン画像を切替、クリックでモーダル',
     '// 卡片操作：用缩略条切换主图，点击打开模态框'),
    ('// モーダル\n', '// 模态框\n'),
    ('// まず軽いサムネ → 原寸に差し替え', '// 先加载轻量缩略图 → 再替换为原图'),
    ('// スマホのスワイプでアングル切替', '// 手机滑动切换视角'),
    ('// 外側を押して閉じたときは、その1回のクリックで下のカード等が開かないようにする',
     '// 点击外部关闭时，避免这一次点击同时打开下方卡片'),
    ("['全身1人・セクシー系','全身1人・標準系','上半身1人','2人絡み']",
     "['全身单人・性感系','全身单人・标准系','上半身单人','双人互动']"),
]


SITE_URL = "https://atom-kkk.github.io/AI-Pose-Depth-Resource-Library/"
SITE_NAME = "AI-Pose-Depth-Resource-Library"
SITE_TITLE = "depth 姿势深度图库 · POSE Atlas 中文版"
SITE_DESC = ("288 组人体姿势、1439 张多角度 depth 深度图，中文汉化。"
             "正面 / 俯视 / 仰视 / 侧面 / 斜侧五视角，可直接用于 ControlNet "
             "深度参考。纯静态单文件，双击即用，可离线。")
SITE_KEYWORDS = ("depth 图, 深度图, 姿势参考, pose reference, ControlNet, "
                 "ControlNet depth, AI 绘画, 人体姿势, 多角度, POSE Atlas")

FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='#14171c'/>"
    "<circle cx='32' cy='19' r='7.5' fill='#8fb4ff'/>"
    "<path d='M32 29c-7.4 0-11.6 5.2-11.6 12.4V53h23.2V41.4C43.6 34.2 39.4 29 32 29z' "
    "fill='#8fb4ff'/></svg>"
)


def head_meta():
    """站点元信息：描述、分享卡、图标、结构化数据。"""
    icon = "data:image/svg+xml," + quote(FAVICON_SVG, safe="")
    tags = [
        '<meta name="description" content="%s">' % SITE_DESC,
        '<meta name="keywords" content="%s">' % SITE_KEYWORDS,
        '<meta name="author" content="Atom-kkk">',
        '<meta name="theme-color" content="#0d0f12">',
        '<link rel="canonical" href="%s">' % SITE_URL,
        '<link rel="icon" type="image/svg+xml" href="%s">' % icon,
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="%s">' % SITE_NAME,
        '<meta property="og:locale" content="zh_CN">',
        '<meta property="og:title" content="%s">' % SITE_TITLE,
        '<meta property="og:description" content="%s">' % SITE_DESC,
        '<meta property="og:url" content="%s">' % SITE_URL,
        '<meta property="og:image" content="%sassets/og.jpg">' % SITE_URL,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="depth 姿势深度图库分享卡">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % SITE_TITLE,
        '<meta name="twitter:description" content="%s">' % SITE_DESC,
        '<meta name="twitter:image" content="%sassets/og.jpg">' % SITE_URL,
    ]
    ld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": SITE_TITLE,
        "description": SITE_DESC,
        "url": SITE_URL,
        "keywords": SITE_KEYWORDS,
        "creator": {"@type": "Person", "name": "Atom-kkk"},
        "license": "https://github.com/Atom-kkk/AI-Pose-Depth-Resource-Library/blob/main/NOTICE-IMAGES.md",
    }
    tags.append('<script type="application/ld+json">%s</script>'
                % json.dumps(ld, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(tags)


def inject_head(html):
    """把元信息插到 </title> 之后；重复构建时先移除旧块，保证幂等。"""
    html = re.sub(r"\n<!-- site-meta -->.*?<!-- /site-meta -->", "", html, flags=re.S)
    block = "\n<!-- site-meta -->\n%s\n<!-- /site-meta -->" % head_meta()
    if "</title>" not in html:
        return html
    return html.replace("</title>", "</title>" + block, 1)


def build():
    with open(SRC, encoding="utf-8") as fh:
        html = fh.read()

    # ---------- 1. 提取并翻译数据 ----------
    m = re.search(r"const D=(\[.*?\]);\s*\nconst ANG=", html, re.S)
    if not m:
        raise SystemExit("未找到数据数组 D")
    rows = json.loads(m.group(1))

    new_rows = []
    for row in rows:
        obj = {}
        for k, v in row.items():
            nk = KEY_MAP.get(k, k)
            if k in ("分類", "系統"):
                v = cat_map.get(v, v)
            elif k == "ポーズ名":
                v = name_map.get(v, v)
            elif k == "アングル":
                v = ANG_MAP.get(v, v)
            obj[nk] = v
        obj["检索"] = "%s %s%s%s%s" % (
            obj["id"], obj["体系"], obj["分类"], obj["姿势名称"], obj["角度"])
        new_rows.append(obj)

    html = html[:m.start(1)] + json.dumps(new_rows, ensure_ascii=False) + html[m.end(1):]

    # ---------- 2. META ----------
    mm = re.search(r"const META=(\{.*?\});", html, re.S)
    meta = json.loads(mm.group(1))
    meta["lines"] = [cat_map.get(x, x) for x in meta["lines"]]
    html = html[:mm.start(1)] + json.dumps(meta, ensure_ascii=False) + html[mm.end(1):]

    # ---------- 3. 角度数组 ----------
    html = html.replace(
        "const ANG=['正面','上から','下から','横','斜め'];",
        "const ANG=['正面','俯视','仰视','侧面','斜侧'];")

    # ---------- 4. 界面文案 ----------
    for old, new in UI:
        html = html.replace(old, new)

    # ---------- 5. 代码注释 ----------
    for old, new in COMMENTS:
        html = html.replace(old, new)

    # ---------- 6. 字段名全局统一 ----------
    for jp, cn in KEY_MAP.items():
        html = html.replace(jp, cn)

    html = html.replace("toLocaleString('ja-JP')", "toLocaleString('zh-CN')")
    html = html.replace("localeCompare(a,'ja')", "localeCompare(a,'zh')")

    # ---------- 7. 移除第三方埋点 ----------
    html = re.sub(
        r"<!-- Cloudflare Pages Analytics -->.*?<!-- Cloudflare Pages Analytics -->",
        "", html, flags=re.S)
    html = re.sub(
        r"<script[^>]*static\.cloudflareinsights\.com[^>]*></script>", "", html)
    html = html.replace("https://static.cloudflareinsights.com", "")

    # ---------- 8. 移除「加入开放聊天」推广面板（页头 + 页脚各一处） ----------
    # 连同 cta / btn-oc / chip-by 的配套样式一起删掉，避免留下死代码
    html = re.sub(r'<div class="cta">.*?</div>\s*</div>\s*', "", html,
                  count=1, flags=re.S)
    html = re.sub(r'<div class="cta cta-s">.*?</div>\s*</div>\s*', "", html,
                  count=1, flags=re.S)
    html = re.sub(r'/\*[^\n]*\n\.cta\{margin-top:18px.*?'
                  r'prefers-reduced-motion:reduce\)\{\.btn-oc[^\n]*\n',
                  "", html, count=1, flags=re.S)
    html = re.sub(r'<footer id="foot">\s*</footer>\n?', "", html, count=1)
    # 页脚元素一起删了，对应的 footer 规则也去掉
    html = re.sub(r'^footer\{[^}]*\}\n', "", html, count=1, flags=re.M)

    # ---------- 9. 站点元信息（SEO / 分享卡 / 图标） ----------
    html = re.sub(
        r"<title>.*?</title>",
        "<title>depth 姿势深度图库 · 288 组姿势 1439 张 | POSE Atlas 中文版</title>",
        html, count=1, flags=re.S)
    html = inject_head(html)

    # ---------- 输出 ----------
    os.makedirs(os.path.dirname(DATA_OUT), exist_ok=True)
    with open(DATA_OUT, "w", encoding="utf-8") as fh:
        json.dump(new_rows, fh, ensure_ascii=False, indent=1)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    print("written:", os.path.relpath(OUT, ROOT))
    print("written:", os.path.relpath(DATA_OUT, ROOT))
    print("index.html: %.1f KB" % (os.path.getsize(OUT) / 1024))
    print("rows: %d   poses: %d   categories: %d" % (
        len(new_rows),
        len({r["姿势编号"] for r in new_rows}),
        len({r["分类"] for r in new_rows})))


if __name__ == "__main__":
    build()
