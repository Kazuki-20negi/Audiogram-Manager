import os
import re
import pytesseract
from PIL import Image
from datetime import datetime
from dotenv import load_dotenv
# .envファイルを読み込む
load_dotenv()
TESSERACT_PATH=os.getenv("TESSERACT_PATH")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

image_file=Image.open("test.png")
width, height = image_file.size
new_size=(width*2, height*2)
image_file=image_file.resize(new_size, Image.Resampling.LANCZOS)

#前処理2値化
image_gray=image_file.convert("L")
threshold=180
image_gray=image_gray.point(lambda x: 0 if x<threshold else 255)

#デバッグ用、本番では消す
image_gray.save("test_gray.png")

#読み取り
custom_config=r"--psm 6"
test_date=pytesseract.image_to_string(image_gray,lang="jpn+eng", config=custom_config)

pattern_west=r"(?:\d{4}\s*[/年]\s*\d{1,2}\s*[/月]\s*\d{1,2}\s*日*)"
pattern_jp = r"(?:(?:令和|平成)\s*\d{1,2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日*)"
pattern_=rf"{pattern_west}|{pattern_jp}"
test_result=re.findall(pattern_,test_date)

print(test_date)
print(test_result)

result_date=str(test_result[1]).replace(" ","")
result_date=result_date.replace("年","/")
print(result_date)