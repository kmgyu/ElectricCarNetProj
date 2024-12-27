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
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, session, jsonify
from flask_mail import Mail, Message
import hashlib
import time
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, unset_jwt_cookies, verify_jwt_in_request
import string
import random
from flask_wtf.csrf import CSRFProtect


app = Flask(__name__)

# CSRF 오류 방지
csrf = CSRFProtect()

# 기능을 사용하기 위한 시크릿 키 설정
app.secret_key = 'root'

# sqlite연결하기
current_directory = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_directory, "database.db")

# 비밀번호 찾기 용 확인 이메일을 위한 사전준비
mail = Mail(app)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'dage8044@gmail.com'
app.config['MAIL_PASSWORD'] = 'avdqyusbplgscqrd'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['SECRET_KEY'] = 'root'  # 시크릿 키 설정
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=5)  # 토큰 만료 시간 설정 (1시간)
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

# 보안을 위한 jwttoken 사용하기
jwt = JWTManager(app)
temporary_tokens = {}
app.config['WTF_CSRF_ENABLED'] = True
csrf.init_app(app)


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
def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 데이터 사용 가능
    return conn

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
    
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # 입력폼에서 아이디와 비밀번호를 받아옴
        user_id = request.form['id']
        password = request.form['pw']

        # 데이터베이스 검색 준비
        connection = get_db()
        cursor = connection.cursor()
        
        # 비밀번호 암호화 하기
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()

        # 데이터베이스에서 사용자 정보를 검색
        cursor.execute('SELECT * FROM members WHERE id=? AND passwd=?', (user_id, password))
        user_data = cursor.fetchone()


        if user_data:
            # 로그인 성공 시 JWT 토큰 발급
            access_token = create_access_token(identity=user_id)

            # 토큰을 브라우저에 쿠키로 설정하여 전달
            response = redirect(url_for('success', username = user_id))
            response.set_cookie('access_token_cookie', access_token, httponly=True)
            
            # db 연결 종료
            connection.close()
            return response
        else:
            # db에 사용자가 없을 경우
            connection.close()
            return render_template('Main.html', error="아이디 또는 비밀번호가 잘못되었습니다.")
        
    else:
        # get 요청일 경우 토큰이 있다면 바로 게시판으로
        # 아니라면 로그인화면으로
        access_token = request.cookies.get('access_token_cookie')
        if access_token:
            verify_jwt_in_request() 
            return redirect(url_for('success', username = get_jwt_identity()))
        return render_template('Main.html')

# 로그아웃 시 토큰 삭제
@app.route('/logout', methods = ['GET','POST'])
def logout():
    session.pop('username', None)
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('access_token_cookie')
    return response

@app.route('/register', methods=['GET', 'POST'])
def register_post():
    if request.method == 'POST':
        #회원 가입 폼에서 값들 가져오기
        user_id = request.form['regi_id']
        password = request.form['regi_pw']
        user_name = request.form['regi_name']
        email = request.form['regi_email']
        today = datetime.today().strftime("%Y-%m-%d")

        #비밀번호 암호화
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
        # db사용 준비
        connection = get_db()
        cursor = connection.cursor()

        # 아이디 중복 검사
        cursor.execute('SELECT COUNT(*) FROM members WHERE id = ?', (user_id,))
        if cursor.fetchone()[0] > 0:
            connection.close()
            return render_template('register.html', error="이미 존재하는 아이디입니다.")
        
        # 닉네임 중복 검사
        cursor.execute('SELECT COUNT(*) FROM members WHERE name = ?', (user_name,))
        if cursor.fetchone()[0] > 0:
            connection.close()
            return render_template('register.html', error="이미 존재하는 닉네임입니다.")

        # 이메일 중복 검사
        cursor.execute('SELECT COUNT(*) FROM members WHERE email = ?', (email,))
        if cursor.fetchone()[0] > 0:
            connection.close()
            return render_template('register.html', error="이미 존재하는 이메일입니다.")

        # 새로운 사용자 추가
        cursor.execute('INSERT INTO members (id, passwd, name, email, last_connect) VALUES (?, ?, ?, ?, ?)', (user_id, password, user_name, email, today))
        connection.commit()
        connection.close()
        return redirect(url_for('index'))
    else:
         return render_template('register.html')


# 비밀번호 찾기
@app.route('/findpasswd', methods=['GET', 'POST'])
def findpasswd():
    if request.method == 'POST':
        # 입력 폼에서 정보 받아오기
        user_id = request.form['regi_id']
        user_name = request.form['regi_name']
        email = request.form['regi_email']

        # db 사용 준비
        connection = get_db()
        cursor = connection.cursor()

        # 사용자 정보 검색
        cursor.execute('SELECT * FROM members WHERE id = ? AND name = ? AND email = ?', (user_id, user_name, email))
        user_data = cursor.fetchone()

        if user_data:
            # 회원이 맞는 경우 토큰과 함께 email로 링크를 보내줌
            expiration_time = time.time() + 3600
            token = generate_token()
            temporary_tokens[token] = expiration_time
            reset_url = f'http://orion.mokpo.ac.kr:8432/resetpasswd?token={token}'
            msg = Message('Hello', sender='dage8044@gmail.com', recipients=[user_data['email']])
            msg.body = f'비밀번호를 변경하려면 아래 링크를 클릭하세요 {reset_url}'
            mail.send(msg)
            flash("이메일로 전송이 완료되었습니다 이메일을 확인해주세요")
            cursor.close()
            return redirect(url_for('index'))
        
        else:
            # db에서 검색이 되지 않는 경우
            flash("일치하는 사용자 정보를 찾을 수 없습니다.")
            return render_template('findpasswd.html')
        
    else:
        # get 요청의 경우
        return render_template('findpasswd.html')
    
# 이메일에 보낼 토큰을 만드는 함수
def generate_token(token_length=16):
    characters = string.ascii_letters + string.digits
    token = ''.join(random.choice(characters) for _ in range(token_length))
    return token

#비밀번호 찾기 메일링크를 통해 접속
#비밀번호 재설정 페이지
@app.route('/resetpasswd', methods = ['GET','POST'])
def resetpasswd():
    if request.method == 'POST':
        # 입력 폼에서 정보를 받아오기
        user_id = request.form['regi_id']
        user_name = request.form['regi_name']
        password1 = request.form['resetpassword']
        password2 = request.form['resetpassword2']

        # db 사용 준비
        connection = get_db()
        cursor = connection.cursor()

        # 비밀 번호와 다시 입력하기가 맞는 경우
        if password1 == password2:
            # 비밀번호를 암호화 후 db에 입력
            password1 = hashlib.sha256(password1.encode('utf-8')).hexdigest()
            cursor.execute('UPDATE members SET passwd = ? WHERE id = ? AND name = ?', (password1, user_id, user_name,))
            connection.commit()
            cursor.close()
            flash("비밀번호 변경이 완료되었습니다")
            return redirect(url_for('index'))
        
        # 비밀 번호와 다시 입력하기가 맞지 않는 경우
        else:
            flash("비밀번호가 일치하지 않습니다")
            return render_template('resetpasswd.html')
        
    else:
        # 이메일에 담겨있던 토큰을 검사
        token = request.args.get('token')
        
        # 유표한 경우
        if token in temporary_tokens and time.time() < temporary_tokens[token]:
            return render_template('resetpasswd.html')
        
        # 유표하지 않은 경우
        else:
            flash('유효하지 않은 링크이거나 시간이 초과되었습니다')
            return render_template('findpasswd.html')


# 유저별 추천 데이터가 집약된 글들을 모은 페이지
@app.route('/success/<username>', methods=['GET'])
def success(username):
    #보안을 위한 세션에 유저id로 저장하기
    session['username'] = username

    return render_template('success.html', name=username)


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
