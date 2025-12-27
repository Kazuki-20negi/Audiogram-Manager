import os
import re
import pytesseract
from PIL import Image
import datetime
import unicodedata
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from dotenv import load_dotenv
# .envファイルを読み込む
load_dotenv()
TESSERACT_PATH=os.getenv("TESSERACT_PATH")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

OUTPUT_FILE = Path("./date.json")

class ImageHandler(FileSystemEventHandler):
    """
    フォルダに何か変更があったら呼ばれるクラス
    """
    def on_created(self, event):
        # フォルダじゃなくてファイルが作られたときだけ反応する
        if event.is_directory:
            return
        
        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        # pngファイルじゃなかったら無視
        if not filename.endswith(".png"):
            return

        print(f"検知しました: {filename}")
        time.sleep(1)
        exam_date_obj = date_detect(filepath)
        if exam_date_obj:
            exam_date_str = str(exam_date_obj)
            need_review = False
            print(f"日付特定: {exam_date_str}")
        else:
            exam_date_str = None
            need_review = True
            print("日付特定失敗 -> 要確認")
        new_data = {
            "filename": filename,
            "exam_date": exam_date_str,
            "need_review": need_review,
        }
        self.save_to_json(new_data)

    def save_to_json(self, new_data):
        current_data = []
        
        # 1. 既存のJSONがあれば読み込む
        if OUTPUT_FILE.exists():
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            except json.JSONDecodeError:
                current_data = []

        # 2. 新しいデータを追加
        current_data.append(new_data)

        # 3. ファイルに書き戻す
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=4, ensure_ascii=False)
        print(f"データを保存しました ({OUTPUT_FILE})")



# 各年号の元年を定義
eraDict = {
    "昭和": 1926,
    "平成": 1989,
    "令和": 2019,
}

def japanese_calendar_converter(text):
    # 正規化
    normalized_text = unicodedata.normalize("NFKC", text)

    # 年月日を抽出
    pattern = r"(?P<era>{eraList})(?P<year>[0-9]{{1,2}}|元)年(?P<month>[0-9]{{1,2}})月(?P<day>[0-9]{{1,2}})日".format(eraList="|".join(eraDict.keys()))
    date = re.search(pattern, normalized_text)

    # 抽出できなかったら終わり
    if date is None:
        print("Cannot convert to western year")
        return None

    # 年を変換
    for era, startYear in eraDict.items():
        if date.group("era") == era:
            if date.group("year") == "元":
                year = eraDict[era]
            else:
                year = eraDict[era] + int(date.group("year")) - 1
    
    # date型に変換して返す
    return datetime.date(year, int(date.group("month")), int(date.group("day")))

def date_detect(image_path):
    image_file=Image.open(image_path)
    width, height = image_file.size
    new_size=(width*2, height*2)
    image_file=image_file.resize(new_size, Image.Resampling.LANCZOS)

    #前処理2値化 本番で戻す
    #image_gray=image_file.convert("L")
    #threshold=180
    #image_gray=image_gray.point(lambda x: 0 if x<threshold else 255)

    #デバッグ用、本番では消す
    #image_gray.save("test_gray.png")
    image_gray=Image.open("test_gray.png")

    #読み取り
    custom_config=r"--psm 6"
    test_date=pytesseract.image_to_string(image_gray,lang="jpn+eng", config=custom_config)

    #正規表現パターン
    pattern_west=r"(?:\d{4}\s*[/年]\s*\d{1,2}\s*[/月]\s*\d{1,2}\s*日*)"
    pattern_jp = r"(?:(?:令和|平成)\s*\d{1,2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日*)"
    pattern_=rf"{pattern_west}|{pattern_jp}"
    test_result=re.findall(pattern_,test_date)

    #print(test_date)
    #print(test_result)
    result_date=str(test_result[0]).replace(" ","")
    result_date=result_date.strip()
    #print(result_date)
    if "平成" in result_date or "令和" in result_date:
        result_date=japanese_calendar_converter(result_date)
        return result_date
    else:
        try:
            result_date=result_date.translate(str.maketrans({"年":"-","月":"-","日":None,"/":"-"}))
            return datetime.datetime.strptime(result_date, "%Y-%m-%d").date()
        except:
            return None

def start_watching():
    target_dir = "./scans"
    
    # 監視員（Observer）とイベント処理係（Handler）を用意
    observer = Observer()
    event_handler = ImageHandler()
    
    # 監視員に「場所」と「係」をセット
    observer.schedule(event_handler, target_dir, recursive=False)
    
    # 監視開始
    observer.start()
    print(f"フォルダ監視を開始しました: {target_dir}")
    print("Ctrl+C で終了します")

    try:
        while True:
            time.sleep(1) # 1秒ごとに待機（CPUを休ませるため）
    except KeyboardInterrupt:
        observer.stop() # Ctrl+C されたら止める

    observer.join()

def main():
    """
    output_file=Path("./date.json")
    scan_dir=Path("./scans")
    result_json=[]

    for image_path in scan_dir.glob("*.png"):
        print(f"Processing: {image_path.name}...")
        exam_date=str(date_detect(image_path))
        need_review=False
        if exam_date is None:
            need_review=True
        result_data={
            "filename":image_path.name,
            "exam_date":exam_date,
            "need_review":need_review,
        }
        result_json.append(result_data)
    """
    start_watching()

if __name__=="__main__":
    main()