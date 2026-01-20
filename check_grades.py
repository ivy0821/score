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

# ================= 多帳號配置區 =================
# 利用 List 儲存多組帳號資訊，方便擴充
ACCOUNTS = [
    {
        "id": os.getenv('STU_ID'),
        "pwd": os.getenv('STU_PWD'),
        "webhook": os.getenv('DISCORD_WEBHOOK'),
        "record": "last_score_count_1.txt"
    },
    {
        "id": os.getenv('STU_ID_2'),
        "pwd": os.getenv('STU_PWD_2'),
        "webhook": os.getenv('DISCORD_WEBHOOK_2'),
        "record": "last_score_count_2.txt"
    }
]

TARGET_YEAR = "113"           # 目標學年
TARGET_SEMESTER = "1"         # 1: 第一學期
# ===============================================

class GradeMonitor:
    def __init__(self, acc):
        self.stu_id = acc["id"]
        self.pwd = acc["pwd"]
        self.webhook = acc["webhook"]
        self.record_file = acc["record"]
        self.driver = None
        self.wait = None

    def send_discord_notification(self, score_details):
        """將成績明細發送至指定的 Discord Webhook"""
        fields = [{"name": f"📘 {course}", "value": f"成績：**{score}** 分", "inline": False} 
                  for course, score in score_details.items()]
        data = {
            "username": "中華大學成績小幫手",
            "embeds": [{
                "title": f"🆕 帳號 {self.stu_id} 偵測到新成績！",
                "color": 5763719,
                "fields": fields,
                "footer": {"text": f"檢查時間：{time.strftime('%Y-%m-%d %H:%M:%S')}"}
            }]
        }
        requests.post(self.webhook, json=data)

    def get_last_count(self):
        """讀取該帳號專屬的紀錄檔"""
        if os.path.exists(self.record_file):
            with open(self.record_file, "r") as f:
                try: return int(f.read().strip())
                except: return 0
        return 0

    def run(self):
        """執行單一帳號的爬取流程"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')           # 無視窗模式
        options.add_argument('--no-sandbox')          # Linux 環境必備
        options.add_argument('--disable-dev-shm-usage') # 防止記憶體問題
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 30)

        try:
            print(f"🔍 正在檢查帳號：{self.stu_id}")
            self.driver.get("https://student2.chu.edu.tw/studentlogin.asp")

            # 登入步驟
            self.wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(self.stu_id)
            self.driver.find_element(By.NAME, "userpassword").send_keys(self.pwd)
            self.driver.find_element(By.NAME, "yes").click()

            # 切換選單
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "leftFrame")))
            expand_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(), '成績查詢系統')]")))
            expand_btn.click()
            time.sleep(1)
            self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "成績查詢"))).click()

            # 進入主頁面填寫查詢條件
            self.driver.switch_to.default_content()
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "mainFrame")))
            year_in = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[maxlength='3']")))
            year_in.clear()
            year_in.send_keys(TARGET_YEAR)
            Select(self.driver.find_element(By.TAG_NAME, "select")).select_by_value(TARGET_SEMESTER)
            self.driver.find_element(By.XPATH, "//input[@value='查詢學期成績(Query OK)']").click()

            # 解析資料
            time.sleep(3)
            rows = self.driver.find_elements(By.XPATH, "//tr")
            results = {}
            for row in rows:
                t = row.text.strip()
                if any(k in t for k in ["必修", "選修", "通識"]) and "成績未送達" not in t:
                    name = re.search(r"[\u4e00-\u9fa5]+", t).group()
                    score = [p for p in t.split() if p.isdigit()][-1]
                    results[name] = score

            # 通知判斷
            curr = len(results)
            last = self.get_last_count()
            if curr > last:
                self.send_discord_notification(results)
                with open(self.record_file, "w") as f: f.write(str(curr))
                print(f"✅ {self.stu_id} 有更新，已發送通知。")
            else:
                print(f"☕ {self.stu_id} 無新成績。")

        except Exception as e:
            print(f"❌ 帳號 {self.stu_id} 執行失敗: {e}")
        finally:
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    for acc_info in ACCOUNTS:
        if acc_info["id"]: # 確保 Secrets 有填寫才跑
            monitor = GradeMonitor(acc_info)
            monitor.run()
