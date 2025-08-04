from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import hashlib
import os
import json

app = Flask(__name__)
CORS(app)

# Render.com 같은 외부 호스팅 환경에서 DATABASE_URL을 가져옵니다.
DATABASE_URL = os.environ.get('DATABASE_URL')

# --- 데이터베이스 연결 함수 ---
def get_db_connection():
    """데이터베이스 연결을 생성하고 반환합니다."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# --- 데이터베이스 초기화 함수 ---
def init_db():
    """필요한 모든 테이블을 생성합니다."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # 파트 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parts (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            ''')
            # 문제 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    part_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    options TEXT NOT NULL,
                    answer INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    explanation TEXT,
                    display_order INTEGER NOT NULL,
                    FOREIGN KEY (part_id) REFERENCES parts (id) ON DELETE CASCADE
                )
            ''')
            # 사용자 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    signup_date DATE NOT NULL
                )
            ''')
            # 퀴즈 기록 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quiz_history (
                    id SERIAL PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    date TIMESTAMP NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    part TEXT NOT NULL
                )
            ''')
        conn.commit()
        print("Database tables checked/created.")

def populate_db_if_empty():
    """데이터베이스가 비어있을 경우, 초기 파트와 문제 데이터를 채워넣습니다."""
    
    # 이 부분이 모든 문제 데이터를 포함하고 있는 유일한 목록이어야 합니다.
    initial_quiz_questions = [
        # Part 1. 비행이론 (ID: 1-20)
        {"id": 1, "part": "Part 1. 비행이론", "question": "항공기가 등속 수평 비행을 할 때, 4가지 힘의 관계로 올바른 것은?", "options": ["양력 > 중력, 추력 > 항력", "양력 = 중력, 추력 = 항력", "양력 < 중력, 추력 < 항력", "양력 = 항력, 추력 = 중력"], "answer": 1, "topic": "비행 원리", "explanation": "등속 수평 비행은 힘의 평형 상태를 의미하며, 수직 방향의 힘(양력과 중력)과 수평 방향의 힘(추력과 항력)이 각각 동일해야 합니다."},
        {"id": 2, "part": "Part 1. 비행이론", "question": "받음각(Angle of Attack)이 임계점을 초과했을 때 발생하는 현상은?", "options": ["급상승", "실속 (Stall)", "음속 돌파", "자동 선회"], "answer": 1, "topic": "비행 원리", "explanation": "임계 받음각을 초과하면 날개 윗면의 공기 흐름이 분리되어 양력을 급격히 잃는 실속(Stall) 현상이 발생합니다."},
        {"id": 3, "part": "Part 1. 비행이론", "question": "날개의 캠버(Camber)가 증가하면 어떤 변화가 일어나는가?", "options": ["양력 계수가 감소한다", "양력 계수가 증가한다", "항력이 감소한다", "추력이 증가한다"], "answer": 1, "topic": "비행 원리", "explanation": "캠버는 날개의 휨 정도로, 캠버가 증가하면 날개 위아래의 압력 차이가 커져 더 큰 양력을 발생시킵니다."},
        {"id": 4, "part": "Part 1. 비행이론", "question": "항공기 자세를 제어하는 3개의 축이 아닌 것은?", "options": ["세로축(Longitudinal Axis)", "가로축(Lateral Axis)", "수직축(Vertical Axis)", "중력축(Gravitational Axis)"], "answer": 3, "topic": "비행 원리", "explanation": "항공기의 3축은 롤링을 제어하는 세로축, 피칭을 제어하는 가로축, 요잉을 제어하는 수직축입니다. 중력축은 항공기 운동의 기준 축이 아닙니다."},
        {"id": 5, "part": "Part 1. 비행이론", "question": "플랩(Flap)을 내리면 나타나는 주된 효과 두 가지는?", "options": ["양력 증가, 항력 감소", "양력 감소, 항력 증가", "양력 증가, 항력 증가", "양력 감소, 항력 감소"], "answer": 2, "topic": "비행 원리", "explanation": "플랩은 날개의 캠버와 시위 길이를 증가시켜, 특히 저속에서 양력과 항력을 모두 크게 증가시키는 역할을 합니다."},
        {"id": 6, "part": "Part 1. 비행이론", "question": "항공기의 안정성 중, 요잉(Yawing) 운동에 대한 안정성을 무엇이라고 하는가?", "options": ["세로 안정성", "가로 안정성", "방향 안정성", "동적 안정성"], "answer": 2, "topic": "비행 원리", "explanation": "방향 안정성은 항공기가 옆바람 등으로 인해 요잉(좌우 회전)했을 때, 원래의 비행 방향으로 돌아오려는 성질을 말하며, 주로 수직 안정판에 의해 유지됩니다."},
        {"id": 7, "part": "Part 1. 비행이론", "question": "프로펠러 항공기에서 발생하는 P-factor는 어떤 비행 상태에서 가장 두드러지는가?", "options": ["고속 수평 비행", "저속, 높은 받음각 상태", "활공 비행", "강하 비행"], "answer": 1, "topic": "비행 원리", "explanation": "P-factor는 프로펠러의 하강 블레이드가 상승 블레이드보다 더 큰 추력을 내는 현상으로, 받음각이 높은 상태(예: 이륙, 상승)에서 가장 두드러지게 나타나 좌측으로 요잉하려는 경향을 만듭니다."},
        {"id": 8, "part": "Part 1. 비행이론", "question": "항공기 무게가 증가하면 실속 속도는 어떻게 되는가?", "options": ["증가한다", "감소한다", "변화 없다", "무게와 무관하다"], "answer": 0, "topic": "비행 원리", "explanation": "더 무거운 무게를 지탱하기 위해서는 더 큰 양력이 필요하며, 동일한 조건에서 더 큰 양력을 얻으려면 더 빠른 속도가 필요합니다. 따라서 실속 속도가 증가합니다."},
        {"id": 9, "part": "Part 1. 비행이론", "question": "지면효과(Ground Effect)가 나타나는 고도는 대략 어느 정도인가?", "options": ["날개 길이의 3배 이내", "날개 길이의 1배 이내", "동체 길이의 1배 이내", "꼬리 높이의 1배 이내"], "answer": 1, "topic": "비행 원리", "explanation": "지면효과는 날개가 지면 가까이 비행할 때 날개 끝 와류가 억제되어 유도 항력이 감소하는 현상으로, 보통 날개 길이(Wingspan)와 같거나 그보다 낮은 고도에서 뚜렷하게 나타납니다."},
        {"id": 10, "part": "Part 1. 비행이론", "question": "하중 계수(Load Factor)가 2G일 때 조종사가 느끼는 무게는?", "options": ["자신의 몸무게와 같다", "자신의 몸무게의 2배", "자신의 몸무게의 절반", "자신의 몸무게의 4배"], "answer": 1, "topic": "비행 원리", "explanation": "하중 계수는 양력과 중력의 비율로, 2G는 항공기와 그 안의 모든 것이 중력의 2배에 해당하는 힘을 받는 상태를 의미합니다."},
        {"id": 11, "part": "Part 1. 비행이론", "question": "고도가 높아질수록 공기 밀도는 어떻게 변하는가?", "options": ["높아진다", "변화 없다", "낮아진다", "알 수 없다"], "answer": 2, "topic": "공기역학", "explanation": "고도가 높아지면 대기압이 낮아지고 공기 분자의 수가 줄어들어 공기 밀도가 낮아집니다. 이는 엔진 및 공기역학적 성능 저하의 원인이 됩니다."},
        {"id": 12, "part": "Part 1. 비행이론", "question": "베르누이의 정리에 따르면, 유체의 속도가 증가하면 압력은 어떻게 되는가?", "options": ["증가한다", "감소한다", "일정하다", "속도와 무관하다"], "answer": 1, "topic": "공기역학", "explanation": "베르누이의 정리는 유체의 총 에너지가 보존된다는 원리로, 속도 에너지(동압)가 증가하면 압력 에너지(정압)는 감소해야 합니다. 이것이 양력 발생의 핵심 원리입니다."},
        {"id": 13, "part": "Part 1. 비행이론", "question": "대기압이 '29.92 inHg'일 때의 대기 상태를 무엇이라고 하는가?", "options": ["고기압 상태", "저기압 상태", "국제 표준 대기 (ISA)", "밀도 고도"], "answer": 2, "topic": "공기역학", "explanation": "국제 표준 대기(ISA)는 항공기 성능 계산의 기준이 되는 가상의 대기 상태로, 해수면 온도 15°C, 기압 29.92 inHg를 기준으로 합니다."},
        {"id": 14, "part": "Part 1. 비행이론", "question": "유해 항력(Parasite Drag)에 포함되지 않는 것은?", "options": ["형상 항력(Form Drag)", "표면 마찰 항력(Skin Friction Drag)", "간섭 항력(Interference Drag)", "유도 항력(Induced Drag)"], "answer": 3, "topic": "공기역학", "explanation": "유해 항력은 항공기의 형태, 표면, 부품 간 간섭으로 인해 발생하는 항력입니다. 반면 유도 항력은 양력 발생의 부산물로 생기는 항력으로, 별도로 분류됩니다."},
        {"id": 15, "part": "Part 1. 비행이론", "question": "유도 항력(Induced Drag)은 항공기 속도가 어떻게 될 때 가장 크게 발생하는가?", "options": ["증가할 때", "감소할 때", "일정할 때", "초음속일 때"], "answer": 1, "topic": "공기역학", "explanation": "유도 항력은 양력을 만들기 위해 큰 받음각이 필요한 저속 비행 상태에서 가장 크게 발생합니다. 속도가 증가하면 유도 항력은 감소합니다."},
        {"id": 16, "part": "Part 1. 비행이론", "question": "날개 끝 와류(Wingtip Vortices)가 가장 강하게 발생하는 조건은?", "options": ["빠르고, 가볍고, 깨끗할 때", "느리고, 무겁고, 플랩을 내렸을 때", "빠르고, 무겁고, 플랩을 올렸을 때", "느리고, 가볍고, 플랩을 올렸을 때"], "answer": 1, "topic": "공기역학", "explanation": "날개 끝 와류는 날개 위아래의 압력 차이가 클 때 강하게 발생합니다. 이는 큰 양력이 필요한 '느리고, 무겁고, 플랩을 내렸을 때'와 같은 조건에서 가장 두드러집니다."},
        {"id": 17, "part": "Part 1. 비행이론", "question": "밀도 고도(Density Altitude)가 증가하면 항공기 성능은 어떻게 되는가?", "options": ["향상된다", "저하된다", "변화 없다", "예측할 수 없다"], "answer": 1, "topic": "공기역학", "explanation": "밀도 고도 증가는 공기 밀도 감소를 의미합니다. 공기가 희박해지면 엔진 출력이 감소하고, 프로펠러와 날개의 효율이 떨어져 이륙 거리 증가, 상승률 감소 등 전반적인 성능이 저하됩니다."},
        {"id": 18, "part": "Part 1. 비행이론", "question": "마하수(Mach Number)는 무엇과 무엇의 비율인가?", "options": ["항공기 속도와 바람의 속도", "항공기 속도와 음속", "추력과 항력의 비율", "양력과 중력의 비율"], "answer": 1, "topic": "공기역학", "explanation": "마하수는 항공기의 실제 속도(TAS)를 해당 고도의 음속으로 나눈 값으로, 고속 비행에서 공기의 압축성 효과를 나타내는 중요한 지표입니다."},
        {"id": 19, "part": "Part 1. 비행이론", "question": "후퇴각(Sweptback Wing) 날개의 주된 장점은 무엇인가?", "options": ["저속 안정성 증가", "임계 마하수 지연", "이륙 거리 단축", "착륙 속도 감소"], "answer": 1, "topic": "공기역학", "explanation": "후퇴각은 날개에 흐르는 공기 흐름의 속도를 실제 항공기 속도보다 느리게 만들어, 충격파 발생 시점인 임계 마하수를 더 높은 속도로 지연시키는 효과가 있습니다."},
        {"id": 20, "part": "Part 1. 비행이론", "question": "흐름의 분리가 날개 앞쪽부터 시작되어 급격한 양력 손실을 초래하는 실속 형태는?", "options": ["점진적 실속", "익단 실속", "익근 실속", "급성 실속"], "answer": 3, "topic": "공기역학", "explanation": "직사각형 날개는 익근(wing root)부터 실속이 시작되어 조종이 용이하지만, 특정 날개 형태에서는 날개 전체 또는 앞쪽부터 급격히 실속이 발생하여 매우 위험할 수 있습니다."},
        
        # Part 2. 비행운용
        {"id": 21, "part": "Part 2. 비행운용", "question": "왕복 엔진에서 혼합비(Mixture)를 희박(Lean)하게 만드는 주된 이유는?", "options": ["엔진 출력 증가", "엔진 냉각", "연료 효율 증대", "시동 용이성"], "answer": 2, "topic": "항공기 시스템", "explanation": "고도가 높아져 공기 밀도가 낮아지면 혼합비가 농후(Rich)해집니다. 이를 희박(Lean)하게 조정하여 최적의 공연비를 맞춰 연료 효율을 높이고 엔진의 부드러운 작동을 돕습니다."},
        {"id": 22, "part": "Part 2. 비행운용", "question": "유압 계통(Hydraulic System)이 주로 사용되는 곳이 아닌 것은?", "options": ["착륙 장치(Landing Gear)", "플랩(Flaps)", "비행 조종면(Flight Controls)", "객실 조명(Cabin Lights)"], "answer": 3, "topic": "항공기 시스템", "explanation": "유압 계통은 파스칼의 원리를 이용해 작은 힘으로 큰 힘을 내는 시스템으로, 착륙장치, 플랩, 브레이크 등 큰 힘이 필요한 곳에 사용됩니다. 객실 조명은 전기 계통에 해당합니다."},
        {"id": 23, "part": "Part 2. 비행운용", "question": "항공기 전기 계통에서 교류(AC)를 직류(DC)로 변환하는 장치는?", "options": ["인버터(Inverter)", "정류기(Rectifier)", "발전기(Generator)", "배터리(Battery)"], "answer": 1, "topic": "항공기 시스템", "explanation": "정류기(TRU: Transformer Rectifier Unit)는 발전기에서 생산된 교류(AC) 전원을 항공기 배터리 및 여러 계통에서 사용하는 직류(DC) 전원으로 변환하는 장치입니다. 반대로 인버터는 DC를 AC로 변환합니다."},
        {"id": 24, "part": "Part 2. 비행운용", "question": "피토-정압 계통(Pitot-Static System)이 정보를 제공하는 계기가 아닌 것은?", "options": ["속도계(Airspeed Indicator)", "고도계(Altimeter)", "자세계(Attitude Indicator)", "승강계(Vertical Speed Indicator)"], "answer": 2, "topic": "항공기 시스템", "explanation": "속도계, 고도계, 승강계는 공기압(충압, 정압)을 이용하는 계기들입니다. 자세계는 자이로(Gyro) 원리를 이용하여 항공기의 자세를 보여주는 계기로, 피토-정압 계통과 무관합니다."},
        {"id": 25, "part": "Part 2. 비행운용", "question": "엔진 오일의 주요 기능이 아닌 것은?", "options": ["윤활", "냉각", "세척", "연료 공급"], "answer": 3, "topic": "항공기 시스템", "explanation": "엔진 오일은 부품 간의 마찰을 줄이는 윤활 작용, 엔진의 열을 식히는 냉각 작용, 내부의 불순물을 제거하는 세척 작용 등을 합니다. 연료 공급은 연료 계통의 역할입니다."},
        {"id": 26, "part": "Part 2. 비행운용", "question": "고정피치 프로펠러(Fixed-Pitch Propeller)의 피치는 어느 비행 상태에 최적화되어 있는가?", "options": ["이륙", "순항", "착륙", "모든 상태"], "answer": 1, "topic": "항공기 시스템", "explanation": "고정피치 프로펠러는 하나의 피치 각도만 가지고 있어 모든 비행 영역에서 최적의 효율을 낼 수 없습니다. 보통 연료 효율이 중요한 순항 비행 상태에 맞춰 설계됩니다."},
        {"id": 27, "part": "Part 2. 비행운용", "question": "방빙(Anti-icing) 장비의 올바른 사용 시점은?", "options": ["얼음이 생긴 후", "얼음이 생기기 전 또는 예상될 때", "얼음 두께가 1인치 이상일 때", "상관 없음"], "answer": 1, "topic": "항공기 시스템", "explanation": "방빙(Anti-icing)은 얼음이 생기는 것을 '방지'하는 장비이므로, 착빙이 예상되는 조건에 들어가기 전에 미리 작동시켜야 합니다. 제빙(De-icing)은 이미 생긴 얼음을 '제거'하는 장비입니다."},
        {"id": 28, "part": "Part 2. 비행운용", "question": "항공기 객실 여압(Cabin Pressurization)의 주된 목적은?", "options": ["산소 공급", "소음 감소", "저산소증 방지", "온도 조절"], "answer": 2, "topic": "항공기 시스템", "explanation": "높은 고도는 공기가 희박하여 저산소증을 유발할 수 있습니다. 여압 장치는 고고도에서도 객실 내의 기압을 인체가 견딜 수 있는 수준(보통 8,000피트 고도 이하)으로 유지시켜 저산소증을 방지합니다."},
        {"id": 29, "part": "Part 2. 비행운용", "question": "가스터빈 엔진의 주요 4단계 사이클은?", "options": ["흡입-폭발-압축-배기", "흡입-압축-연소-배기", "압축-흡입-연소-배기", "흡입-연소-압축-배기"], "answer": 1, "topic": "항공기 시스템", "explanation": "가스터빈 엔진은 브레이튼 사이클(Brayton Cycle)을 따르며, 공기를 흡입(Intake), 압축(Compression), 연료와 혼합하여 연소(Combustion), 그리고 뜨거운 가스를 배출(Exhaust)하는 4단계를 거쳐 추력을 얻습니다."},
        {"id": 30, "part": "Part 2. 비행운용", "question": "항공기 타이어에 공기 대신 질소를 주입하는 주된 이유는?", "options": ["무게 감소", "온도 변화에 따른 압력 변화가 적음", "비용 절감", "구하기 쉬움"], "answer": 1, "topic": "항공기 시스템", "explanation": "질소는 공기보다 수분 함량이 거의 없고, 온도 변화에 따른 압력 변화가 적어 안정적입니다. 또한 고온에서도 산화 반응(화재 위험)을 일으키지 않아 항공기 타이어에 사용됩니다."},
        {"id": 31, "part": "Part 2. 비행운용", "question": "자세계(Attitude Indicator)가 조종사에게 보여주는 정보는?", "options": ["항공기의 속도", "항공기의 고도", "항공기의 피치와 뱅크", "항공기의 방향"], "answer": 2, "topic": "비행 계기", "explanation": "자세계는 인공 수평선(Artificial Horizon)을 기준으로 항공기의 기수 올림/내림(피치)과 좌우 기울어짐(뱅크) 상태를 직관적으로 보여줍니다."},
        {"id": 32, "part": "Part 2. 비행운용", "question": "자기 나침반(Magnetic Compass)의 오차가 가장 심하게 나타나는 선회는?", "options": ["동쪽 또는 서쪽으로 선회 시", "남쪽 또는 북쪽으로 선회 시", "적도 부근에서 선회 시", "극지방에서 선회 시"], "answer": 0, "topic": "비행 계기", "explanation": "북반구에서 동쪽이나 서쪽으로 선회할 때 가속/감속 오차(ANDS: Accelerate North, Decelerate South)가 나타나며, 나침반이 실제보다 앞서거나 뒤쳐지는 현상을 보입니다."},
        {"id": 33, "part": "Part 2. 비행운용", "question": "선회계(Turn Coordinator)가 보여주는 정보 두 가지는?", "options": ["선회율과 선회 방향", "선회율과 미끄러짐", "피치와 뱅크", "고도와 속도"], "answer": 1, "topic": "비행 계기", "explanation": "선회계의 미니어처 비행기는 선회율(Rate of Turn)과 선회 방향(Direction of Turn)을, 아래의 볼(Ball)은 원심력과 중력의 균형, 즉 미끄러짐(Slip/Skid) 여부를 보여줍니다."},
        {"id": 34, "part": "Part 2. 비행운용", "question": "고도계의 '코ල්스만 창(Kollsman Window)'에 조종사가 입력하는 값은?", "options": ["현재 고도", "현재 기압", "현재 온도", "목표 고도"], "answer": 1, "topic": "비행 계기", "explanation": "코ල්스만 창에는 현재 위치의 해수면 기압(Altimeter Setting)을 입력합니다. 이를 통해 고도계가 정확한 해발 고도(MSL)를 지시하도록 보정할 수 있습니다."},
        {"id": 35, "part": "Part 2. 비행운용", "question": "속도계(ASI)에 표시된 Vno 속도는 무엇을 의미하는가?", "options": ["실속 속도", "최대 플랩 작동 속도", "정상 운용 범위의 최대 속도", "절대 초과 금지 속도"], "answer": 2, "topic": "비행 계기", "explanation": "Vno(Maximum structural cruising speed)는 정상 운용 범위의 최대 속도로, 녹색 아크(Green Arc)의 끝에 해당합니다. 이 속도는 잔잔한 공기 중에서만 초과할 수 있으며, 그 이상은 황색 아크(Yellow Arc)인 주의 운용 범위입니다."},
        
        # Part 3. 항법
        {"id": 36, "part": "Part 3. 항법", "question": "VOR 항법 시설이 제공하는 정보는 무엇인가?", "options": ["방위(Azimuth)", "거리(Distance)", "고도(Altitude)", "위치(Position)"], "answer": 0, "topic": "항법", "explanation": "VOR(VHF Omnidirectional Range)은 지상국으로부터 항공기가 어느 방향(Radial)에 있는지를 알려주는 방위 정보를 제공합니다. DME가 함께 있어야 거리 정보를 알 수 있습니다."},
        {"id": 37, "part": "Part 3. 항법", "question": "GPS가 정확한 위치를 계산하기 위해 최소 몇 개의 위성 신호가 필요한가?", "options": ["2개", "3개", "4개", "5개"], "answer": 2, "topic": "항법", "explanation": "GPS는 3차원 위치(위도, 경도, 고도)와 시간 오차를 보정하기 위해 최소 4개의 위성으로부터 신호를 수신해야 정확한 위치 정보를 계산할 수 있습니다."},
        {"id": 38, "part": "Part 3. 항법", "question": "등각 원통 도법(Mercator Chart)에서 두 지점 간의 최단 거리는 어떻게 표현되는가?", "options": ["직선", "곡선", "원으로 표현됨", "표현 불가능"], "answer": 1, "topic": "항법", "explanation": "메르카토르 도법에서 직선은 항정선(Rhumb Line)으로, 방위는 일정하지만 최단 거리는 아닙니다. 두 지점 간의 최단 거리인 대권(Great Circle)은 이 지도에서 곡선으로 표현됩니다."},
        {"id": 39, "part": "Part 3. 항법", "question": "항법에서 '편차(Variation)'란 무엇과 무엇의 차이를 의미하는가?", "options": ["진북과 자북", "자북과 나침반 북", "진북과 나침반 북", "지도와 실제 지형"], "answer": 0, "topic": "항법", "explanation": "편차(Magnetic Variation)는 지구의 진북(지리적 북극)과 자북(자기장의 북극)이 일치하지 않아 발생하는 각도의 차이를 말합니다. 이는 지역에 따라 다릅니다."},
        {"id": 40, "part": "Part 3. 항법", "question": "NDB(Non-Directional Beacon)를 수신하는 항공기 계기는?", "options": ["VHF 수신기", "ADF (자동 방향 탐지기)", "DME (거리 측정 장비)", "GPS 수신기"], "answer": 1, "topic": "항법", "explanation": "ADF(Automatic Direction Finder)는 지상의 NDB 방송국에서 송신하는 저주파/중주파 전파를 수신하여 해당 방송국에 대한 상대 방향을 계기판에 표시해 주는 장비입니다."},
        {"id": 41, "part": "Part 3. 항법", "question": "ILS(계기 착륙 장치)의 '글라이드 슬롭(Glide Slope)'이 제공하는 정보는?", "options": ["수평 정렬 정보", "수직 정렬 정보", "공항까지의 거리", "활주로 방향"], "answer": 1, "topic": "항법", "explanation": "ILS는 로컬라이저(Localizer)와 글라이드 슬롭(Glide Slope)으로 구성됩니다. 로컬라이저는 활주로 중심선과의 수평 정렬 정보를, 글라이드 슬롭은 적절한 강하 경로와의 수직 정렬 정보를 제공합니다."},
        {"id": 42, "part": "Part 3. 항법", "question": "Dead Reckoning(추측 항법)에 필요한 두 가지 주요 정보는?", "options": ["시간과 속도", "방향과 고도", "바람과 온도", "위도와 경도"], "answer": 0, "topic": "항법", "explanation": "추측 항법은 알려진 위치에서 특정 방향(Heading)과 속도(Airspeed)로 일정 시간 동안 비행했을 때 현재 위치를 계산하는 항법입니다. 따라서 시간과 속도가 필수적입니다."},
        {"id": 43, "part": "Part 3. 항법", "question": "항공로(Airway)의 폭은 일반적으로 얼마인가?", "options": ["양쪽으로 4 NM (총 8 NM)", "양쪽으로 8 NM (총 16 NM)", "양쪽으로 10 NM (총 20 NM)", "양쪽으로 2 NM (총 4 NM)"], "answer": 0, "topic": "항법", "explanation": "저고도 항공로(Victor Airway)는 일반적으로 중심선으로부터 양쪽으로 4해리(Nautical Mile), 즉 총 8해리의 폭을 가집니다."},
        {"id": 44, "part": "Part 3. 항법", "question": "시간, 속도, 거리 계산에 사용되는 아날로그 컴퓨터는?", "options": ["E6B Flight Computer", "계산기", "GPS", "FMS"], "answer": 0, "topic": "항법", "explanation": "E6B는 비행에 필요한 다양한 계산(예: 연료 소모량, 바람 수정각, 진대기속도 등)을 할 수 있도록 고안된 슬라이드 룰 방식의 아날로그 비행 컴퓨터입니다."},
        {"id": 45, "part": "Part 3. 항법", "question": "VFR 비행 시 사용하는 고도 규칙에서, 0~179도 방향으로 비행할 때의 권장 고도는?", "options": ["짝수 천 피트 + 500피트", "홀수 천 피트 + 500피트", "짝수 천 피트", "홀수 천 피트"], "answer": 1, "topic": "항법", "explanation": "VFR 순항 고도 규칙에 따르면, 3,000피트 AGL 이상에서 자침 방위(Magnetic Course)가 0도부터 179도 사이(동쪽 방향)일 때는 홀수 천 피트 + 500피트 (예: 3,500, 5,500)로 비행해야 합니다."},
    
        # Part 4. 항공기상
        {"id": 46, "part": "Part 4. 항공기상", "question": "뇌우(Thunderstorm)가 형성되기 위한 3가지 조건이 아닌 것은?", "options": ["불안정한 대기", "높은 습도", "상승 기류", "강한 바람"], "answer": 3, "topic": "항공 기상", "explanation": "뇌우의 3요소는 불안정한 대기(공기가 쉽게 상승하려는 성질), 충분한 수증기(높은 습도), 그리고 공기를 강제로 상승시키는 요인(상승 기류)입니다. 강한 바람은 뇌우를 이동시키거나 흩어지게 할 수는 있지만 형성의 필수 조건은 아닙니다."},
        {"id": 47, "part": "Part 4. 항공기상", "question": "안개(Fog)와 구름(Cloud)의 근본적인 차이는 무엇인가?", "options": ["수분 함량", "형성 고도", "온도", "색깔"], "answer": 1, "topic": "항공 기상", "explanation": "안개와 구름은 모두 작은 물방울이나 얼음 결정의 모임이라는 점에서 동일합니다. 유일한 차이는 안개는 지표면에 접촉하여 형성되고, 구름은 상공에서 형성된다는 점입니다."},
        {"id": 48, "part": "Part 4. 항공기상", "question": "산악파(Mountain Waves)가 가장 강하게 형성될 수 있는 조건은?", "options": ["바람이 산맥에 평행하게 불 때", "바람이 산맥에 약하게 불 때", "바람이 산맥에 강하고 수직으로 불 때", "바람이 없을 때"], "answer": 2, "topic": "항공 기상", "explanation": "산악파는 안정된 대기층에서 강한 바람(약 20노트 이상)이 산맥의 능선에 거의 수직으로 불어올 때 가장 강하게 발달하며, 심한 난기류를 유발할 수 있습니다."},
        {"id": 49, "part": "Part 4. 항공기상", "question": "METAR에서 'SCT030'은 무엇을 의미하는가?", "options": ["300피트에 구름이 많음", "3,000피트에 구름이 흩어져 있음", "30,000피트에 구름이 거의 없음", "3,000피트에 구름이 깨져 있음"], "answer": 1, "topic": "항공 기상", "explanation": "METAR에서 SCT는 Scattered(하늘의 3/8~4/8)를, 뒤의 숫자 030은 고도 3,000피트(AGL)를 의미합니다. 따라서 '3,000피트에 구름이 흩어져 있다'는 뜻입니다."},
        {"id": 50, "part": "Part 4. 항공기상", "question": "착빙(Icing)이 가장 발생하기 쉬운 온도 범위는?", "options": ["-20°C ~ -40°C", "0°C ~ -20°C", "0°C ~ 10°C", "-40°C 이하"], "answer": 1, "topic": "항공 기상", "explanation": "착빙은 항공기가 과냉각된 물방울(액체 상태지만 온도는 0°C 이하)이 있는 구름 속을 통과할 때 발생합니다. 이러한 조건은 보통 0°C에서 -20°C 사이의 온도에서 가장 흔하게 나타납니다."}
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # 1. 파트 데이터 채우기
            cursor.execute("SELECT COUNT(*) FROM parts")
            if cursor.fetchone()[0] == 0:
                print("Populating 'parts' table...")
                parts = sorted(list(set(q['part'] for q in initial_quiz_questions)))
                for part_name in parts:
                    cursor.execute("INSERT INTO parts (name) VALUES (%s)", (part_name,))
                print("'parts' table populated.")
            
            # 2. 문제 데이터 채우기
            cursor.execute("SELECT COUNT(*) FROM questions")
            if cursor.fetchone()[0] == 0:
                print("Populating 'questions' table...")
                cursor.execute("SELECT id, name FROM parts")
                part_map = {name: id for id, name in cursor.fetchall()}
                
                for q in initial_quiz_questions:
                    part_id = part_map.get(q['part'])
                    if part_id:
                        cursor.execute(
                            """
                            INSERT INTO questions (part_id, question, options, answer, topic, explanation, display_order) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (part_id, q['question'], json.dumps(q['options'], ensure_ascii=False), q['answer'], q['topic'], q['explanation'], q['id'])
                        )
                print("'questions' table populated.")
        conn.commit()

# --- API 엔드포인트 ---

# 사용자를 생성 (회원가입)
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"success": False, "message": "이메일과 비밀번호를 모두 입력해주세요."}), 400

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    signup_date = datetime.now().date()

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (email, password_hash, signup_date) VALUES (%s, %s, %s)",
                    (email, password_hash, signup_date)
                )
            conn.commit()
        return jsonify({"success": True, "message": "회원가입이 완료되었습니다! 로그인해주세요."})
    except psycopg2.IntegrityError:
        # conn.rollback()은 with 구문이 끝나면서 자동으로 처리됩니다.
        return jsonify({"success": False, "message": "이미 사용 중인 이메일입니다."}), 409

# 사용자를 인증 (로그인)
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

    if not user:
        return jsonify({"success": False, "message": "존재하지 않는 사용자입니다."}), 404

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user['password_hash']:
        return jsonify({"success": False, "message": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401
    
    # 서비스 만료일 체크
    if datetime.now().date() > user['signup_date'] + timedelta(days=60):
        return jsonify({"success": False, "message": "서비스 이용 기간이 만료되었습니다."}), 403

    return jsonify({"success": True, "message": "로그인 성공! 환영합니다."})

# 파트 목록 가져오기
@app.route('/api/parts', methods=['GET'])
def get_parts():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM parts ORDER BY id")
            parts = cursor.fetchall()
    return jsonify([dict(row) for row in parts])

# 특정 파트의 문제들 가져오기
@app.route('/get-questions', methods=['GET'])
def get_questions():
    part_name = request.args.get('part')
    if not part_name:
        return jsonify({"error": "Part name is required"}), 400

    questions_list = []
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT id FROM parts WHERE name = %s", (part_name,))
            part = cursor.fetchone()
            
            if not part:
                return jsonify({"error": "Part not found"}), 404
            
            part_id = part['id']
            cursor.execute("SELECT * FROM questions WHERE part_id = %s ORDER BY display_order", (part_id,))
            questions_from_db = cursor.fetchall()

    for q in questions_from_db:
        question_dict = dict(q)
        question_dict['options'] = json.loads(question_dict['options'])
        questions_list.append(question_dict)
    
    return jsonify(questions_list)

# 퀴즈 결과 제출
@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    user_email = data.get('user')
    user_answers = data.get('answers')
    part_name = data.get('part')

    if not all([user_email, user_answers, part_name]):
        return jsonify({"error": "Missing data"}), 400
    
    score = 0
    topic_analysis = {}
    
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 해당 파트의 모든 문제 정보를 한 번에 가져옵니다.
            cursor.execute("""
                SELECT q.* FROM questions q
                JOIN parts p ON q.part_id = p.id
                WHERE p.name = %s
            """, (part_name,))
            questions_in_part = {q['id']: q for q in cursor.fetchall()}
            
            if not questions_in_part:
                return jsonify({"error": "No questions found for this part"}), 404

            for answer in user_answers:
                q_id = answer['questionId']
                question_info = questions_in_part.get(q_id)
                if not question_info:
                    continue

                correct_answer_index = question_info['answer']
                options = json.loads(question_info['options'])
                correct_answer_text = options[correct_answer_index]
                
                is_correct = (answer['answer'] == correct_answer_text)
                
                topic = question_info['topic']
                if topic not in topic_analysis:
                    topic_analysis[topic] = {'correct': 0, 'total': 0}
                topic_analysis[topic]['total'] += 1
                
                if is_correct:
                    score += 1
                    topic_analysis[topic]['correct'] += 1
            
            total_questions_in_part = len(questions_in_part)
            
            cursor.execute(
                "INSERT INTO quiz_history (user_email, date, score, total, part) VALUES (%s, %s, %s, %s, %s)",
                (user_email, datetime.now(), score, total_questions_in_part, part_name)
            )
        conn.commit()

    return jsonify({
        "score": score, 
        "total": len(user_answers),
        "analysis": topic_analysis
    })

# 특정 사용자의 퀴즈 기록 가져오기
@app.route('/get-history', methods=['POST'])
def get_history():
    user_email = request.json.get('user')
    if not user_email:
        return jsonify({"error": "User email is required"}), 400

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM quiz_history WHERE user_email = %s ORDER BY date DESC", (user_email,))
            history = cursor.fetchall()
            
    return jsonify([dict(row) for row in history])


# --- 관리자 페이지 (선택 사항) ---
# 이 부분은 필요 없다면 삭제해도 무방합니다.

@app.route('/admin')
def admin_page():
    # 간단한 비밀번호 보호 또는 특정 IP만 허용하는 로직 추가를 권장합니다.
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT q.*, p.name AS part_name FROM questions q JOIN parts p ON q.part_id = p.id ORDER BY p.id, q.display_order")
            questions = cursor.fetchall()
            cursor.execute("SELECT * FROM parts ORDER BY id")
            parts = cursor.fetchall()
    
    # 옵션을 Python 리스트로 변환
    for q in questions:
        q['options'] = json.loads(q['options'])
        
    return render_template('admin.html', questions=questions, parts=parts)


# --- 서버 시작 ---
if __name__ == '__main__':
    # 앱을 실행하기 전에 데이터베이스를 초기화합니다.
    init_db()
    populate_db_if_empty()
    # debug=True는 개발 중에만 사용하고, 실제 배포 시에는 False로 변경하거나 제거하는 것이 좋습니다.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)