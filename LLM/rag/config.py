"""
RAG 시스템의 구성 정보를 관리하는 모듈
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 데이터베이스 설정
DB_HOST = "localhost"
DB_USER = "username"  # 실제 사용자 이름으로 변경
DB_PASSWORD = "password"  # 실제 비밀번호로 변경
DB_NAME = "multimodal_final_project"  # 실제 데이터베이스 이름으로 변경

ENDPOINT = "testdb.cfmq6wqw0199.ap-northeast-2.rds.amazonaws.com"
PORT = 3306
USERNAME = "admin"
PASSWORD = "Saltlux12345!"
DATABASE = "multimodal_final_project"

# 데이터베이스 연결 설정
DB_URI = f"mysql+mysqlconnector://{USERNAME}:{PASSWORD}@{ENDPOINT}:{PORT}/{DATABASE}"
DB_URI_DB1 = DB_URI #+ DB_NAME
DB_URI_DB2 = DB_URI #+ DB_NAME 

# 벡터스토어 경로
VECTORSTORE_A_PATH = "./dragonkue" 
JSON_FILE_PATH = "./20250304.json"
QUERY_VECTOR_STORE_PATH = "./Text2SQL"

# 임베딩 모델 설정
EMBEDDING_MODEL = "dragonkue/snowflake-arctic-embed-l-v2.0-ko"
EMBEDDING_KWARGS = {'normalize_embeddings': True}

#VLLM 호출 주소
MISTRAL_VLLM = "https://jgtjsnjfhzxschca.tunnel-pt.elice.io/generate"

# OpenAI GPT-4o API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"
SQL_TEMPERATURE = 0.3


# LLM 모델 설정
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.1

# 검색 설정
TOP_K_INITIAL = 30
TOP_K_RERANK = 15
FINAL_DOCS_COUNT = 15

# benefits 테이블 스키마 정보
BENEFITS_SCHEMA = """
CREATE TABLE benefits (
    service_id INT PRIMARY KEY,
    service_name VARCHAR(255),
    target_age_min INT,
    target_age_max INT,
    target_gender VARCHAR(10),
    income_criteria INT,
    description TEXT,
    application_method TEXT,
    application_url VARCHAR(255)
);
"""

# Text-to-SQL 지시문
TEXT_TO_SQL_INSTRUCTION = """
당신은 자연어 질문을 SQL 쿼리로 변환하는 전문가입니다.
주어진 자연어 질문에 대해 benefits 테이블을 조회하는 SQL 쿼리를 생성해주세요.
반드시 service_id 필드가 SELECT 절에 포함되어야 합니다.
"""

QUERY_DATA_PATH = "valid_queries.csv"



# 최대 SQL 생성 시도 횟수
MAX_SQL_ATTEMPTS = 5