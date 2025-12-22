import os
import re
import pytesseract
from PIL import Image
from dotenv import load_dotenv
# .envファイルを読み込む
load_dotenv()
TESSERACT_PATH=os.getenv("TESSERACT_PATH")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH



Image_=Image.open("test.png")
test_date=pytesseract.image_to_string(Image_,lang="jpn+eng")
pattern=r"{\d}*/{\d}*/{\d}*"

print(test_date)