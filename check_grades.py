import os
import time
import requests
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# ================= 設定區 (讀取 GitHub Secrets) =================
STU_ID = os.getenv('STU_ID')
PWD = os.getenv('STU_PWD')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK')

# 中華大學學期設定
TARGET_YEAR = "114"           # 請確保年份正確，114 可能導致系統查無資料
TARGET_SEMESTER = "1"         # 1: 第一學期, 2: 第二學期
RECORD_FILE = "last_score_count.txt"
# =============================================================

class GradeMonitor:
    def __init__(self):
        self.driver = None
        self.wait = None

    def send_discord_notification(self, score_details):
        fields = [{"name": f"📘 {course}", "value": f"成績：**{score}** 分", "inline": False} 
                  for course, score in score_details.items()]

        data = {
            "username": "中華大學成績小幫手",
            "embeds": [{
                "title": "🆕 偵測到新成績公佈！",
                "description": f"學號 **{STU_ID}** 的最新成績清單：",
                "color": 5763719,
                "fields": fields,
                "footer": {"text": f"檢查時間：{time.strftime('%Y-%m-%d %H:%M:%S')}"}
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=data)

    def get_last_count(self):
        if os.path.exists(RECORD_FILE):
            with open(RECORD_FILE, "r") as f:
                try: return int(f.read().strip())
                except: return 0
        return 0

    def check_grades(self):
        options = webdriver.ChromeOptions()
        # 雲端執行必備參數，防止 Actions 卡死
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 30)

        try:
            print(f"[{time.strftime('%H:%M:%S')}] 啟動巡邏程序...")
            self.driver.get("https://student2.chu.edu.tw/studentlogin.asp")

            # 登入
            self.wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(STU_ID)
            self.driver.find_element(By.NAME, "userpassword").send_keys(PWD)
            self.driver.find_element(By.NAME, "yes").click()
            print("✅ 登入成功")

            # 切換 Frame 並點擊成績查詢
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "leftFrame")))
            self.driver.execute_script("document.evaluate(\"//li[contains(., '成績查詢系統')]/input\", document).singleNodeValue.checked = true;")
            time.sleep(1)
            query_link = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='score_qry/score_index.asp']")))
            self.driver.execute_script("arguments[0].click();", query_link)

            # 進入查詢頁面
            self.driver.switch_to.default_content()
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "mainFrame")))

            # 輸入年份與學期
            year_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[maxlength='3']")))
            year_input.clear()
            year_input.send_keys(TARGET_YEAR)
            Select(self.driver.find_element(By.TAG_NAME, "select")).select_by_value(TARGET_SEMESTER)
            self.driver.find_element(By.XPATH, "//input[@value='查詢學期成績(Query OK)']").click()
            print(f"🔍 正在查詢 {TARGET_YEAR} 學年度成績...")

            # 解析成績 (使用 Regex)
            time.sleep(3)
            rows = self.driver.find_elements(By.XPATH, "//tr")
            score_results = {}

            for row in rows:
                text = row.text.strip()
                if any(k in text for k in ["必修", "選修", "通識"]) and "成績未送達" not in text:
                    chinese_match = re.search(r"[\u4e00-\u9fa5]+", text)
                    course_name = chinese_match.group() if chinese_match else "未知科目"
                    parts = text.split()
                    digit_parts = [p for p in parts if p.isdigit()]
                    if digit_parts:
                        score_results[course_name] = digit_parts[-1]

            current_count = len(score_results)
            last_count = self.get_last_count()
            
            print(f"📊 掃描完畢，目前已公佈 {current_count} 門科目。")

            if current_count > last_count:
                print("🚀 偵測到新成績，發送 Discord 通知...")
                self.send_discord_notification(score_results)
                with open(RECORD_FILE, "w") as f: f.write(str(current_count))
            else:
                print("☕ 無新成績更新。")

        finally:
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    monitor = GradeMonitor()
    monitor.check_grades()
