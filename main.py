from flask import Flask, jsonify, request, render_template
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import json
import pytz
import chromedriver_autoinstaller
from selenium import webdriver
#from seleniumwire import webdriver  # Selenium Wire 패키지 사용
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from time import sleep

app = Flask(__name__)

# 한국 시간대 설정
KST = pytz.timezone("Asia/Seoul")

DB_FILE = "forecast_data.db"
ACCESS_TOKEN = None  # 빅토리지 토큰

# 빅토리지 API URL 및 사용자 정보
TOKEN_URL = "http://bigtorage.iptime.org:1101/ai/token"
DATA_URL = "http://bigtorage.iptime.org:1101/ai/data/current"
USER_CREDENTIALS = {
    "user": {
        "userId": "iotplus_naju_ai",
        "userPassword": "1234"
    }
}

# SQLite 초기화
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 빅토리지 데이터 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bigtorage_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT UNIQUE,
            discharge REAL,
            charge REAL,
            power REAL,
            load REAL
        )
    """)

    # 기상 예보 데이터 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecast_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fcstDateTime TEXT UNIQUE,
            powergen REAL,
            cum_powergen REAL,
            irrad REAL,
            temp REAL,
            wind REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# 빅토리지 토큰 요청
def fetch_access_token():
    global ACCESS_TOKEN
    try:
        response = requests.post(
            TOKEN_URL,
            json=USER_CREDENTIALS,  # JSON 데이터를 직렬화하여 전송
            headers={"Content-Type": "application/json"}
        )

        # 상태 코드와 응답 데이터 로깅
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Body: {response.json()}")

        # 응답 상태 코드 처리
        if response.status_code in [200, 201]:  # 200 또는 201이면 처리
            ACCESS_TOKEN = response.json().get("accessToken")
        else:
            print(f"Failed to fetch token: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error fetching token: {e}")


# 빅토리지 데이터 수집
def fetch_bigtorage_data():
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        fetch_access_token()
    try:
        response = requests.get(DATA_URL, headers={"accessToken": ACCESS_TOKEN})
        if response.status_code == 200:
            data = response.json()
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "discharge": data.get("energy", {}).get("discharge", 0),
                "charge": data.get("energy", {}).get("charge", 0),
                "power": data.get("energy", {}).get("power", 0),
                "load": data.get("energy", {}).get("load", 0)
            }
        elif response.status_code == 401:
            fetch_access_token()
            return fetch_bigtorage_data()
    except Exception as e:
        print(f"Error fetching bigtorage data: {e}")
    return None

def save_bigtorage_data(data):
    if data:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO bigtorage_data (timestamp, discharge, charge, power, load)
                VALUES (?, ?, ?, ?, ?)
            """, (data["timestamp"], data["discharge"], data["charge"], data["power"], data["load"]))
            conn.commit()
        except Exception as e:
            print(f"Error saving bigtorage data: {e}")
        finally:
            conn.close()

# 빅토리지 데이터 갱신
def update_bigtorage_data():
    data = fetch_bigtorage_data()
    save_bigtorage_data(data)

# 기상청 크롤링
def download_pvsim(now=None):
    chromedriver_autoinstaller.install()
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(2)
    driver.get('https://bd.kma.go.kr/kma2020/fs/energySelect2.do?menuCd=F050702000')
    if not now is None:
        # 자바스크립트를 사용하여 hidden input의 값을 변경
        new_value = now.strftime('%Y%m%d')
        script = f"document.getElementById('testYmd').value = '{new_value}';"
        driver.execute_script(script)
        
        # 자바스크립트를 사용하여 hidden input의 값을 변경
        new_value = now.strftime('%H%M')
        script = f"document.getElementById('testTime').value = '{new_value}';"
        driver.execute_script(script)
    else:
        now = datetime.now()
        
    
    driver.find_element(By.XPATH, '//*[@id="txtLat"]').send_keys('35.0606')
    driver.find_element(By.XPATH, '//*[@id="txtLon"]').send_keys('126.749')
    search_ = driver.find_element(By.XPATH, '//*[@id="search_btn"]').send_keys(Keys.RETURN)

    element = driver.find_element(By.ID, 'toEnergy')
    response_ok = False
    for k in range(24):
        # Split the text into lines and extract the relevant lines
        lines = element.text.strip().split('\n')[12:]
        if len(lines) > 0 and len(lines[0].strip()) > 10:
            response_ok = True
            break
        sleep(1)
    if not response_ok:
        raise TimeoutException("download_pvsim(): query response timeout")
    
    lines = element.text.strip().split('\n')

    today_data = []
    tomorrow_data = []
    
    # Get today's date
    today_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_date = today_date + timedelta(days=1)
    
    for line in lines:
        parts = line.split()
        hour = parts[0][:-1]  # Remove the '시'
        if len(hour) == 1:
            hour = f"0{hour}"  # Ensure hour is two digits
        
        today_time = today_date + timedelta(hours=int(hour))
        tomorrow_time = tomorrow_date + timedelta(hours=int(hour))

        if parts[1] != '-':
            today_entry = [today_time.strftime("%Y%m%d %H%M")] + parts[1:6]
            today_data.append(today_entry)

        if parts[6] != '-':
            tomorrow_entry = [tomorrow_time.strftime("%Y%m%d %H%M")] + parts[6:]
            tomorrow_data.append(tomorrow_entry)

    columns = ["fcstDateTime", "powergen", "cum_powergen", "irrad", "temp", "wind"]
    today_df = pd.DataFrame(today_data, columns=columns)
    tomorrow_df = pd.DataFrame(tomorrow_data, columns=columns)
    
    # Convert appropriate columns to numeric types
    for col in columns[1:]:
        today_df[col] = pd.to_numeric(today_df[col])
        tomorrow_df[col] = pd.to_numeric(tomorrow_df[col])
    
    # Concatenate the two DataFrames
    df = pd.concat([today_df, tomorrow_df]).reset_index(drop=True)
    print(df)
    driver.quit()
    return df

def save_forecast_data(df):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        try:
            # fcstDateTime 값 가져오기
            fcst_datetime = row["fcstDateTime"]
            
            # SELECT 쿼리로 기존 데이터 존재 여부 확인
            cursor.execute("""
                SELECT * FROM forecast_data WHERE fcstDateTime = ?
            """, (fcst_datetime,))
            existing = cursor.fetchone()
            # 데이터 업데이트 또는 삽입
            if existing:
                cursor.execute("""
                    UPDATE forecast_data
                    SET powergen = ?, cum_powergen = ?, irrad = ?, temp = ?, wind = ?
                    WHERE fcstDateTime = ?
                """, (row["powergen"], row["cum_powergen"], row["irrad"], row["temp"], row["wind"], fcst_datetime))
            else:
                cursor.execute("""
                    INSERT INTO forecast_data (fcstDateTime, powergen, cum_powergen, irrad, temp, wind)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (row["fcstDateTime"], row["powergen"], row["cum_powergen"], row["irrad"], row["temp"], row["wind"]))
        except Exception as e:
            print(f"Error saving forecast data: {e}")
    conn.commit()
    conn.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/bigtorage-data', methods=['GET'])
def get_bigtorage_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bigtorage_data ORDER BY timestamp DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{
        "timestamp": row[1],
        "discharge": row[2],
        "charge": row[3],
        "power": row[4],
        "load": row[5]
    } for row in rows])

from datetime import datetime, timedelta

@app.route('/api/forecast-data', methods=['GET'])
def get_forecast_data():
    try:
        # 오늘과 내일 날짜 계산
        today = datetime.now().strftime('%Y%m%d')      # '20241224' 형식
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')  # '20241225' 형식

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # 오늘과 내일 데이터를 가져오기 위한 조건 추가
        cursor.execute(
            "SELECT * FROM forecast_data WHERE fcstDateTime LIKE ? OR fcstDateTime LIKE ? ORDER BY fcstDateTime ASC",
            (f"{today}%", f"{tomorrow}%")
        )
        rows = cursor.fetchall()
        conn.close()

        # 데이터 변환 및 반환
        forecast_data = []
        for row in rows:
            forecast_data.append({
                "timestamp": row[1],  # 'fcstDateTime'을 'timestamp'로 변환
                "powergen": row[2],
                "cum_powergen": row[3],
                "irrad": row[4],
                "temp": row[5],
                "wind": row[6]
            })
        
        return jsonify(forecast_data)

    except Exception as e:
        # 오류 처리
        print("Error fetching forecast data:", e)
        return jsonify({"error": "Failed to fetch forecast data"}), 500


@app.route('/api/refresh-forecast', methods=['POST'])
def refresh_forecast():
    try:
        df = download_pvsim()
        save_forecast_data(df)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 스케줄러 설정
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_access_token, 'interval', minutes=14)
scheduler.add_job(update_bigtorage_data, 'interval', seconds=10)
scheduler.add_job(lambda: save_forecast_data(download_pvsim()), 'interval', hours=1)
scheduler.start()

if __name__ == '__main__':
    fetch_access_token()
    app.run(host='0.0.0.0', debug=True)
