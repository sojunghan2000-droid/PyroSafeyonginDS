from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (1200, 900), color=(226, 232, 240))  # slate-200
draw = ImageDraw.Draw(img)
text = "가설동 (TEMP) — 배치도 임시\n실측 배치도 수령 시 이 파일을 교체하세요"
draw.multiline_text((60, 60), text, fill=(51, 65, 85), spacing=10)
draw.rectangle([40, 40, 1160, 860], outline=(148, 163, 184), width=3)
img.save("assets/floors/TEMP.png")
print("saved assets/floors/TEMP.png")
