import time
import requests
import os
import re  # 導入正規表達式模組
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# ================= 設定區 =================
STU_ID = os.getenv('STU_ID')          # 你的學號
PWD = os.getenv('STU_PWD')              # 你的密碼
TARGET_YEAR = "114"           # 目標學年
TARGET_SEMESTER = "1"         # 1: 第一學期, 2: 第二學期
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK')
RECORD_FILE = "last_score_count.txt"
# ==========================================

class GradeMonitor:
    def __init__(self):
        self.driver = None
        self.wait = None

    def send_discord_notification(self, score_details):
        """將詳細中文科目與分數傳送至 Discord"""
        fields = []
        for course, score in score_details.items():
            # 使用 Embeds 格式化訊息，增加易讀性
            fields.append({"name": f"📘 {course}", "value": f"成績：**{score}** 分", "inline": False})

        data = {
            "username": "中華大學成績小幫手",
            "embeds": [{
                "title": "🆕 偵測到新成績公佈！",
                "description": f"學號 **{STU_ID}** 的最新成績清單：",
                "color": 5763719,  # 鮮綠色
                "fields": fields,
                "footer": {"text": f"檢查時間：{time.strftime('%Y-%m-%d %H:%M:%S')}"}
            }]
        }
        try:
            requests.post(DISCORD_WEBHOOK_URL, json=data)
        except Exception as e:
            print(f"Discord 發送失敗: {e}")

    def get_last_count(self):
        if os.path.exists(RECORD_FILE):
            with open(RECORD_FILE, "r") as f:
                try: return int(f.read().strip())
                except: return 0
        return 0

    def check_grades(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 25)

        try:
            print(f"[{time.strftime('%H:%M:%S')}] 啟動巡邏程序...")
            self.driver.get("https://student2.chu.edu.tw/studentlogin.asp")

            # 1. 登入程序
            self.wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(STU_ID)
            self.driver.find_element(By.NAME, "userpassword").send_keys(PWD)
            self.driver.find_element(By.NAME, "yes").click()

            # 2. 選單跳轉
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "leftFrame")))
            expand_script = "var xpath = \"//li[contains(., '成績查詢系統')]/input\"; var cb = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if (cb) { cb.checked = true; return true; } return false;"
            self.driver.execute_script(expand_script)
            time.sleep(1.5)
            query_link = self.wait.until(EC.presence_of_element_located((By.XPATH, "//a[@href='score_qry/score_index.asp']")))
            self.driver.execute_script("arguments[0].click();", query_link)

            # 3. 進入右側 mainFrame
            self.driver.switch_to.default_content()
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "mainFrame")))

            # 4. 查詢條件填寫
            year_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[maxlength='3']")))
            year_input.clear()
            year_input.send_keys(TARGET_YEAR)
            Select(self.driver.find_element(By.TAG_NAME, "select")).select_by_value(TARGET_SEMESTER)
            self.driver.find_element(By.XPATH, "//input[@value='查詢學期成績(Query OK)']").click()

            # 5. 解析資料 (Regex 強化版)
            time.sleep(4)
            rows = self.driver.find_elements(By.XPATH, "//tr")
            score_results = {}

            for row in rows:
                text = row.text.strip()
                # 過濾出含有科目特徵且已給分的列
                if any(k in text for k in ["必修", "選修", "通識"]) and "成績未送達" not in text:
                    # 使用 Regex 提取第一個連續中文字串作為科目名稱
                    chinese_match = re.search(r"[\u4e00-\u9fa5]+", text)
                    course_name = chinese_match.group() if chinese_match else "未知科目"
                    
                    # 提取最後一個純數字作為分數
                    parts = text.split()
                    digit_parts = [p for p in parts if p.isdigit()]
                    if digit_parts:
                        score_results[course_name] = digit_parts[-1]

            current_count = len(score_results)
            last_count = self.get_last_count()
            
            print(f"📊 掃描完畢。已公佈：{list(score_results.keys())}")

            # 通知邏輯
            if current_count > last_count or (current_count > 0 and last_count == 0):
                print("🚀 偵測到科目更新，正在通知 Discord...")
                self.send_discord_notification(score_results)
                with open(RECORD_FILE, "w") as f: f.write(str(current_count))
            else:
                print("☕ 內容與上次相符，暫不發送通知。")

        except Exception as e:
            print(f"❌ 執行異常: {e}")
        finally:
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    monitor = GradeMonitor()
    while True:
        monitor.check_grades()
        print(f"[{time.strftime('%H:%M:%S')}] 完成巡邏。一小時後將再次執行...")
        time.sleep(3600)