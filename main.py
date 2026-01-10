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
import requests
from dotenv import load_dotenv
# .envファイルを読み込む
load_dotenv()
TESSERACT_PATH=os.getenv("TESSERACT_PATH")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

OUTPUT_FILE = Path("./date.json")
def rename_file(original_path, date_str):
    """
    ファイル名を日付にリネームし、ファイル名をreturnする
    Args:
        original_path: リネーム対象のファイルのパス
        date_str: リネームする日付
    """
    directry_original=os.path.dirname(original_path)
    extension=os.path.splitext(original_path)[1]
    new_filename=f"{date_str}{extension}"
    new_path=os.path.join(directry_original, new_filename)

    #重複回避
    counter=1
    while os.path.exists(new_path):
        new_filename=f"{date_str}_{counter}{extension}"
        new_path=os.path.join(directry_original, new_filename)
        counter+=1
    
    #リネーム実行
    try:
        os.rename(original_path, new_path)
        print("リネーム成功")
        return new_filename
    except OSError as e:
        print(f"リネーム失敗{e}")
        return os.path.basename(original_path)


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
        exam_date_obj = date_detect(filepath) #OCRして日付を取得
        result_filename=filename
        if exam_date_obj:
            exam_date_str = str(exam_date_obj)
            need_review = False
            print(f"日付特定: {exam_date_str}")
            result_filename=rename_file(filepath, exam_date_str)
        else:
            exam_date_str = None
            need_review = True
            print("日付特定失敗 -> 要確認")
        new_data = {
            "filename": result_filename,
            "exam_date": exam_date_str,
            "need_review": need_review,
        }
        self.save_to_json(new_data)
        upload_to_server(new_data,"test_gray.png")

    def save_to_json(self, new_data):
        """
        OCR結果などを含む新規データをjsonにして既存ファイルの末尾に追加する
        Args:
            new_data: 新規データ
        """
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
    """
    元号を含む日付を西暦に変換する    
    :param text:元号を含む日付
    """
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
    """
    OCRで日付を検出する
    
    Args:
        image_path: 対象画像のパス
    """
    image_file=Image.open(image_path)
    width, height = image_file.size
    new_size=(width*2, height*2)
    image_file=image_file.resize(new_size, Image.Resampling.LANCZOS)

    #前処理2値化
    image_gray=image_file.convert("L")
    threshold=180
    image_gray=image_gray.point(lambda x: 0 if x<threshold else 255)

    #デバッグ用、本番では消す
    #image_gray.save("test_gray.png")
    #image_gray=Image.open("test_gray.png")

    #読み取り
    custom_config=r"--psm 6"
    test_date=pytesseract.image_to_string(image_gray,lang="jpn+eng", config=custom_config)

    #正規表現パターン
    pattern_west=r"(?:\d{4}\s*[/年]\s*\d{1,2}\s*[/月]\s*\d{1,2}\s*日*)"
    pattern_jp = r"(?:(?:令和|平成)\s*\d{1,2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日*)"
    pattern_=rf"{pattern_west}|{pattern_jp}"
    test_result=re.findall(pattern_,test_date)

    if not test_result:
        return None
    
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
    target_dir = "./real_scans"
    
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

def upload_to_server(new_data,filepath):
    api_key=os.getenv("AUDIOGRAM_API_KEY")
    url="http://httpbin.org/post"
    #url="http://honban.com/audiograms/upload"

    headers={
        "X-Api-Key":api_key,
    }
    payload=new_data
    with open(filepath, 'rb') as f:
        files = {
            "original_file": f
        }
        
        # 送信
        try:
            response = requests.post(url, data=payload, files=files, headers=headers)
            response.raise_for_status() # エラーなら例外を起こす
            print(f"送信成功: {response.status_code}")
            print(response.json()) # サーバーからの返事を見る,デバッグ
            return True
        except requests.exceptions.RequestException as e:
            print(f"送信失敗: {e}")
            return False

def main():
    start_watching()

if __name__=="__main__":
    main()