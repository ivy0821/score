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
        "webhook": os.getenv('DISCORD_WEBHOOK'),
        "record": "last_score_count_2.txt"
    }
]

TARGET_YEAR = "114"
TARGET_SEMESTER = "1"
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
        if os.path.exists(self.record_file):
            with open(self.record_file, "r") as f:
                try: return int(f.read().strip())
                except: return 0
        return 0

    def run(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 35) # 稍微增加等待時間

        try:
            print(f"🔍 正在檢查帳號：{self.stu_id}")
            self.driver.get("https://student2.chu.edu.tw/studentlogin.asp")

            # 登入
            self.wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(self.stu_id)
            self.driver.find_element(By.NAME, "userpassword").send_keys(self.pwd)
            self.driver.find_element(By.NAME, "yes").click()
            time.sleep(2) # 等待登入後跳轉

            # 切換選單 - 增加多重檢查
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "leftFrame")))
            
            # 使用更強健的 JS 點擊方式展開選單
            expand_script = "var el = document.evaluate(\"//li[contains(., '成績查詢系統')]\", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if(el) el.click();"
            self.driver.execute_script(expand_script)
            
            time.sleep(2)
            query_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "成績查詢")))
            self.driver.execute_script("arguments[0].click();", query_link)

            # 進入查詢頁面
            self.driver.switch_to.default_content()
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "mainFrame")))
            
            year_in = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[maxlength='3']")))
            year_in.clear()
            year_in.send_keys(TARGET_YEAR)
            Select(self.driver.find_element(By.TAG_NAME, "select")).select_by_value(TARGET_SEMESTER)
            self.driver.find_element(By.XPATH, "//input[@value='查詢學期成績(Query OK)']").click()

            # 解析資料
            time.sleep(5)
            rows = self.driver.find_elements(By.XPATH, "//tr")
            results = {}
            for row in rows:
                t = row.text.strip()
                if any(k in t for k in ["必修", "選修", "通識"]) and "成績未送達" not in t:
                    match = re.search(r"[\u4e00-\u9fa5]+", t)
                    if match:
                        name = match.group()
                        score = [p for p in t.split() if p.isdigit()][-1]
                        results[name] = score

            curr = len(results)
            last = self.get_last_count()
            print(f"📊 {self.stu_id} 掃描完畢，科目數: {curr}")

            if curr > last:
                self.send_discord_notification(results)
                with open(self.record_file, "w") as f: f.write(str(curr))
                print(f"✅ {self.stu_id} 已傳送更新通知。")
            else:
                print(f"☕ {self.stu_id} 無新資料。")

        except Exception as e:
            print(f"❌ 帳號 {self.stu_id} 執行失敗: {str(e)}")
        finally:
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    for acc_info in ACCOUNTS:
        if acc_info["id"] and acc_info["pwd"]: # 確保兩個都有值才執行
            monitor = GradeMonitor(acc_info)
            monitor.run()
