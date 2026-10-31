#!/usr/bin/env python3
"""生成站点分享卡 assets/og.jpg（1200x630）。

右侧放一组真实缩略图做主视觉，左侧用横向渐变压暗后叠标题，
供 Open Graph / Twitter Card / 聊天工具预览使用。

仅依赖 Pillow；字体走 macOS 系统字体，其它平台改 FONT_* 常量即可。
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "og.jpg")
W, H = 1200, 630

BG = (11, 13, 16)
TX = (233, 236, 241)
TX2 = (163, 171, 184)
TX3 = (108, 116, 130)
AC = (143, 180, 255)

# 主视觉：右侧清晰一张 + 后方探出一张虚化剪影，做出景深
SHOT_FRONT = "thumbs/full_single_P011_front.jpg"
SHOT_BACK = "thumbs/full_single_P020_front.jpg"

FONT_CN = "/System/Library/Fonts/STHeiti Medium.ttc"      # 索引 1 = Heiti SC Medium
FONT_EN = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def cn(size):
    return ImageFont.truetype(FONT_CN, size, index=1)


def en(size, bold=True):
    if bold:
        return ImageFont.truetype(FONT_EN, size)
    return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)


def first_existing(*cands):
    for rel in cands:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            return p
    pool = sorted(f for f in os.listdir(os.path.join(ROOT, "thumbs"))
                  if f.endswith(".jpg"))
    return os.path.join(ROOT, "thumbs", pool[0])


def gradient():
    """横向遮罩：白=遮成背景色。x<640 全遮，640→860 渐隐，之后全透。"""
    row = Image.new("L", (256, 1))
    vals = []
    for i in range(256):
        x = i * W / 255.0
        if x <= 640:
            a = 255
        elif x >= 860:
            a = 0
        else:
            a = int(255 * (1 - (x - 640) / 220.0))
        vals.append(a)
    row.putdata(vals)
    return row.resize((W, H), Image.BILINEAR)


def feather_mask(size, feather, opacity=1.0):
    """内实外虚的遮罩，让贴图边缘溶进深色背景，避免出现矩形接缝。"""
    w, h = size
    b = max(2, feather)
    mask = Image.new("L", (w, h), 0)
    mask.paste(Image.new("L", (max(1, w - 2 * b), max(1, h - 2 * b)), 255), (b, b))
    mask = mask.filter(ImageFilter.GaussianBlur(b * 0.75))
    if opacity < 1.0:
        mask = mask.point(lambda v: int(v * opacity))
    return mask


def luma_key(im, floor_luma=112, ceil_luma=238, opacity=1.0, keep=0.18):
    """按亮度抠图：缩略图的灰底直接透掉，只留人体亮部。

    depth 图的背景是接近 #6e6e6e 的灰，人体是浅灰到白，
    因此以 floor_luma 为透明阈值、ceil_luma 为全不透明，中间线性过渡；
    keep 给极暗部分留一点存在感，避免身体阴影被抠成空洞。
    """
    lum = im.convert("L")
    span = max(1.0, ceil_luma - floor_luma)
    mask = lum.point(lambda v: (
        min(255, int(keep * 255 + (255 - keep * 255) * (v - floor_luma) / span))
        if v > floor_luma else int(keep * 45)))
    if opacity < 1.0:
        mask = mask.point(lambda v: int(v * opacity))
    return mask


def build():
    canvas = Image.new("RGB", (W, H), BG)

    # 后方剪影：亮度键控 + 降透明度，营造景深
    back = Image.open(first_existing(SHOT_BACK, "thumbs/full_single_P001_front.jpg"))
    back = back.convert("RGB").resize((452, 602), Image.LANCZOS)
    back = Image.blend(back, Image.new("RGB", back.size, (58, 62, 70)), 0.35)
    mask = Image.composite(
        luma_key(back, opacity=0.85),
        Image.new("L", back.size, 0),
        feather_mask(back.size, 56, 1.0),
    )
    canvas.paste(back, (486, 46), mask)

    # 主视觉：右侧完整入画
    front = Image.open(first_existing(SHOT_FRONT))
    front = front.convert("RGB").resize((456, 608), Image.LANCZOS)
    mask = Image.composite(
        luma_key(front, opacity=1.0),
        Image.new("L", front.size, 0),
        feather_mask(front.size, 52, 1.0),
    )
    canvas.paste(front, (742, 14), mask)

    # 左侧压暗
    canvas = Image.composite(Image.new("RGB", (W, H), BG), canvas, gradient())

    # 底部微暗，压住页脚文字（y<470 不动，470→630 渐暗）
    vals = []
    for y in range(H):
        if y <= 470:
            vals.append(0)
        else:
            vals.append(int(185 * (y - 470) / 160.0))
    foot = Image.new("L", (1, H))
    foot.putdata(vals)
    canvas = Image.composite(Image.new("RGB", (W, H), (7, 9, 12)), canvas,
                             foot.resize((W, H), Image.BILINEAR))
    return canvas


def draw_text(canvas):
    d = ImageDraw.Draw(canvas)
    x = 72

    # 顶部：强调短线 + 小标
    d.rectangle([x, 150, x + 34, 153], fill=AC)
    d.text((x + 48, 140), "POSE ATLAS  /  POSE-DB-02", font=en(17), fill=TX3)

    # 主标题
    y = 196
    d.text((x, y), "depth", font=en(64), fill=AC)
    w = d.textlength("depth", font=en(64))
    d.text((x + w + 20, y + 10), "姿势深度图库", font=cn(50), fill=TX)

    # 副标题
    d.text((x, y + 104), "288 组人体姿势 · 1439 张多角度深度图", font=cn(28), fill=TX2)
    d.text((x, y + 152), "正面 / 俯视 / 仰视 / 侧面 / 斜侧", font=cn(21), fill=TX3)
    d.text((x, y + 186), "ControlNet 深度参考 · 中文汉化", font=cn(21), fill=TX3)

    # 页脚
    d.text((x, 470), "纯静态单文件 · 双击即用 · 可离线", font=cn(20), fill=TX2)
    d.text((x, 506), "github.com/Atom-kkk/AI-Pose-Depth-Resource-Library",
           font=en(19), fill=TX3)
    d.rectangle([x, 556, x + 92, 559], fill=(52, 58, 68))


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    canvas = build()
    draw_text(canvas)
    canvas.save(OUT, "JPEG", quality=88, optimize=True, progressive=True)
    print("written: assets/og.jpg  %.0f KB" % (os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
