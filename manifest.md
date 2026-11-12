# 渲染配置

脚本读取 UTF-8 JSON。所有图像路径相对 JSON 所在目录解析，也可使用绝对路径。crop 为原图经过 EXIF 方向修正后的归一化坐标 [左, 上, 右, 下]，范围 0–1，省略则使用整图。选区被完整容纳在印刷区，使用等比缩放。先目视选择合适裁切。

~~~json
{
  "title": "Still Light",
  "tracks": ["Morning", "Glass", "Afterimage"],
  "captions": ["A quiet morning", "Light on the glass", "One moment stays"],
  "accent": "#D650B7",
  "cover": {"path": "photo.jpg", "crop": [0, 0, 1, 1]},
  "card": {"path": "photo.jpg", "crop": [0, 0.2, 1, 0.6]},
  "album_left": {"path": "photo.jpg"},
  "album_right": {"path": "detail.jpg"},
  "disc": {"mode": "abstract"}
}
~~~

cover 必填；card、album_left、album_right 省略时复用 cover，适合单图输入。三首 tracks 和三句非空 captions 必填，歌词卡不能退化成只有横线的空白纸。推荐短片名、短歌名与短句，避免缩小后无法阅读。可通过 font 指定一个存在的字体路径，相对路径从 JSON 所在目录解析；中文文案应选择支持相应字符的字体。字体文件不随包分发，字体缺字需在交付前目视检查。

当目视确认一个照片选区无真人脸时，可以改用以下盘面配置。

~~~json
{
  "disc": {
    "mode": "verified_nonhuman",
    "path": "object.jpg",
    "crop": [0, 0, 1, 1],
    "reviewed_no_human_face": true
  }
}
~~~

reviewed_no_human_face 是执行者完成检查的记录；脚本不会自动检测人脸。无法完成检查就用 abstract。抽象盘面只使用代码图形和专色，图像里的人脸不会进入盘面。

运行 python render.py manifest.json final.png。依赖 Pillow 与 numpy。图片缺失、选区无效、曲目数量错误或未经检查的照片盘面都会报错，修正配置后运行。
