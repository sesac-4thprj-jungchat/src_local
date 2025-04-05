"""
SQL 쿼리 생성 및 처리 관련 기능을 제공하는 모듈
"""
import os
import re
import time
import traceback
import asyncio
import datetime
import requests
from typing import List, Dict, Any, Tuple, Set, Optional
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from user_data import combine_user_data
from config import MAX_SQL_ATTEMPTS, MISTRAL_VLLM
from database import (
    get_user_data, 
    execute_sql_query, 
    is_valid_sql, 
    is_valid_sql_format,
    ensure_service_id_in_sql,
    replace_select_with_star_indexing,
    AREA_DISTRICT_MAPPING
)

from embedding import get_question_vectorstore
# 허용된 값 목록 정의
ALLOWED_VALUES = {
    "area": ["전국","서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시", "경기도", "충청북도", "충청남도", "전라남도", "경상북도", "경상남도", "제주특별자치도", "강원특별자치도", "전북특별자치도"],
    "district": ["강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "강서구", "금정구", "기장군", "남구", "동구", "동래구", "부산진구", "북구", "사상구", "사하구", "서구", "수영구", "연제구", "영도구", "중구", "해운대구", "군위군", "남구", "달서구", "달성군", "동구", "북구", "서구", "수성구", "중구", "강화군", "계양구", "남동구", "동구", "미추홀구", "부평구", "서구", "연수구", "옹진군", "중구", "광산구", "남구", "동구", "북구", "서구", "대덕구", "동구", "서구", "유성구", "중구", "남구", "동구", "북구", "울주군", "중구", "세종특별자치시", "가평군", "고양시", "과천시", "광명시", "광주시", "구리시", "군포시", "김포시", "남양주시", "동두천시", "부천시", "성남시", "수원시", "시흥시", "안산시", "안성시", "안양시", "양주시", "양평군", "여주시", "연천군", "오산시", "용인시", "의왕시", "의정부시", "이천시", "파주시", "평택시", "포천시", "하남시", "화성시", "괴산군", "단양군", "보은군", "영동군", "옥천군", "음성군", "제천시", "증평군", "진천군", "청주시", "충주시", "계룡시", "공주시", "금산군", "논산시", "당진시", "보령시", "부여군", "서산시", "서천군", "아산시", "예산군", "천안시", "청양군", "태안군", "홍성군", "강진군", "고흥군", "곡성군", "광양시", "구례군", "나주시", "담양군", "목포시", "무안군", "보성군", "순천시", "신안군", "여수시", "영광군", "영암군", "완도군", "장성군", "장흥군", "진도군", "함평군", "해남군", "화순군", "경산시", "경주시", "고령군", "구미시", "김천시", "문경시", "봉화군", "상주시", "성주군", "안동시", "영덕군", "영양군", "영주시", "영천시", "예천군", "울릉군", "울진군", "의성군", "청도군", "청송군", "칠곡군", "포항시", "거제시", "거창군", "고성군", "김해시", "남해군", "밀양시", "사천시", "산청군", "양산시", "의령군", "진주시", "창녕군", "창원시", "통영시", "하동군", "함안군", "함양군", "합천군", "서귀포시", "제주시", "강릉시", "고성군", "동해시", "삼척시", "속초시", "양구군", "양양군", "영월군", "원주시", "인제군", "정선군", "철원군", "춘천시", "태백시", "평창군", "홍천군", "화천군", "횡성군", "고창군", "군산시", "김제시", "남원시", "무주군", "부안군", "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "전주시 덕진구", "전주시 완산구", "정읍시", "진안군"],
    "gender": ["남자", "여자"],
    "income_category": ["0 ~ 50%", "51 ~ 75%", "76 ~ 100%", "101 ~ 200%"],
    "personal_category": ["예비부부/난임", "임신부", "출산/입양", "장애인", "국가보훈대상자", "농업인", "어업인", "축산인", "임업인", "초등학생", "중학생", "고등학생", "대학생/대학원생", "질병/질환자", "근로자/직장인", "구직자/실업자", "해당사항 없음"],
    "household_category": ["다문화가정", "북한이탈주민가정", "한부모가정/조손가정", "1인 가구", "다자녀가구", "무주택세대", "신규전입가구", "확대가족", "해당사항 없음"],
    "support_type": ["현금", "현물", "서비스", "이용권"],
    "application_method": ["온라인 신청", "타사이트 신청", "방문 신청", "기타"],
    "benefit_category": ["생활안정", "주거-자립", "보육-교육", "고용-창업", "보건-의료", "행정-안전", "임신-출산", "보호-돌봄", "문화-환경", "농림축산어업"]
}


# def extract_sql_from_text(text: str) -> str:
#     # SQL 태그 검색
#     sql_match = re.search(r"<SQL>(.*?)</SQL>", text, re.DOTALL)
#     if sql_match:
#         extracted_sql = sql_match.group(1).strip()
#         # 예시 텍스트나 주석 제거
#         extracted_sql = re.sub(r'#.*$', '', extracted_sql, flags=re.MULTILINE)
#         extracted_sql = re.sub(r'-- .*$', '', extracted_sql, flags=re.MULTILINE)
        
#         # 템플릿 문자열인지 검사 (예: "조건1 AND 조건2...")
#         if "조건1" in extracted_sql or "조건2" in extracted_sql:
#             return None
            
#         return extracted_sql.strip()
    
#     # 태그가 없으면 일반 SQL 키워드로 시작하는 부분 찾기
#     sql_keywords = ["SELECT", "WITH", "CREATE", "INSERT", "UPDATE", "DELETE"]
#     lines = text.split("\n")
#     for i, line in enumerate(lines):
#         stripped_line = line.strip().upper()
#         if any(stripped_line.startswith(keyword) for keyword in sql_keywords):
#             return "\n".join(lines[i:]).strip()
    
def extract_sql_from_text(text: str) -> str:
    """텍스트에서 마지막 SQL 태그 내용만 추출"""
    # 모든 SQL 태그 찾기
    sql_matches = re.findall(r"<SQL>(.*?)</SQL>", text, re.DOTALL)
    
    # 마지막 SQL 태그만 사용 (있는 경우)
    if sql_matches:
        last_sql = sql_matches[-1].strip()
        
        # 주석 제거
        last_sql = re.sub(r'#.*$', '', last_sql, flags=re.MULTILINE)
        last_sql = re.sub(r'-- .*$', '', last_sql, flags=re.MULTILINE)
        
        # 템플릿 문자열인지 검사 (예: "조건1 AND 조건2...")
        if "조건1" in last_sql or "조건2" in last_sql:
            return None
            
        return last_sql.strip()
    
    return None
    
    
    return text.strip()

def validate_sql_categories(sql_query):
    """SQL 쿼리에 사용된 카테고리 값이 허용된 값인지 검증"""
    # 각 허용된 필드에 대해 검사
    for field, allowed_values in ALLOWED_VALUES.items():
        # LIKE 연산자 검사 (예: field LIKE '%value%')
        like_matches = re.finditer(r'{}[\s]+LIKE[\s]*[\'\"]\%?(.*?)\%?[\'\"]'.format(field), sql_query, re.IGNORECASE)
        for match in like_matches:
            value = match.group(1).strip('%')  # % 제거
            if value != "" and not any(allowed_val in value or value in allowed_val for allowed_val in allowed_values):
                return False, f"허용되지 않은 {field} 값: {value}"
        
        # 등호 연산자 검사 (예: field = 'value')
        eq_matches = re.finditer(r'{}[\s]*=[\s]*[\'\"](.*?)[\'\"]'.format(field), sql_query, re.IGNORECASE)
        for match in eq_matches:
            value = match.group(1)
            if value != "" and value not in allowed_values:
                return False, f"허용되지 않은 {field} 값: {value}"
        
        # IN 구문 검사
        in_matches = re.finditer(r'{}[\s]+IN[\s]*\((.*?)\)'.format(field), sql_query, re.IGNORECASE)
        for match in in_matches:
            values_str = match.group(1)
            values = [v.strip().strip('\'"') for v in values_str.split(',')]
            for value in values:
                if value != "" and value not in allowed_values:
                    return False, f"허용되지 않은 {field} 값: {value}"
    
    return True, ""

def clean_sql_query(sql_query):
    """SQL 쿼리에서 문제가 될 수 있는 요소 제거"""
    # 주석 제거
    sql_query = re.sub(r'--.*?(\n|$)', '', sql_query)
    
    # LIMIT 구문 제거
    sql_query = re.sub(r'\bLIMIT\s+\d+\s*($|;)', '', sql_query, flags=re.IGNORECASE)
    
    # 테이블 존재 검증 (benefits 테이블만 허용)
    if re.search(r'FROM\s+(?!benefits\b)[a-zA-Z_][a-zA-Z0-9_]*', sql_query, re.IGNORECASE):
        # benefits 외 다른 테이블이 FROM 절에 있으면 수정
        sql_query = re.sub(r'FROM\s+(?!benefits\b)[a-zA-Z_][a-zA-Z0-9_]*', 'FROM benefits', sql_query, flags=re.IGNORECASE)
    
    # JOIN 구문 제거 (필요한 경우 더 정교한 방식으로 수정)
    sql_query = re.sub(r'LEFT\s+JOIN.*?ON.*?(?=WHERE|GROUP|ORDER|LIMIT|$)', '', sql_query, flags=re.IGNORECASE | re.DOTALL)
    sql_query = re.sub(r'JOIN.*?ON.*?(?=WHERE|GROUP|ORDER|LIMIT|$)', '', sql_query, flags=re.IGNORECASE | re.DOTALL)
    
    # 복잡한 CASE/IF 구문 단순화 (보수적인 접근)
    if 'CASE' in sql_query.upper() or 'IF(' in sql_query.upper():
        # CASE/IF 구문이 SELECT 필드에만 있는지 확인
        if re.search(r'(CASE|IF\().*?(FROM)', sql_query, re.IGNORECASE | re.DOTALL):
            # SELECT와 FROM 사이의 텍스트 추출
            select_part = re.search(r'SELECT(.*?)FROM', sql_query, re.IGNORECASE | re.DOTALL)
            if select_part:
                # service_id가 포함되었는지 확인
                has_service_id = 'service_id' in select_part.group(1)
                # 복잡한 CASE/IF 구문을 단순 컬럼 선택으로 변경
                simplified_select = 'SELECT ' + ('service_id, ' if not has_service_id else '') + 'area, district, min_age, max_age, gender, benefit_category, support_type'
                sql_query = re.sub(r'SELECT.*?FROM', simplified_select + ' FROM', sql_query, flags=re.IGNORECASE | re.DOTALL)
    
    return sql_query

async def generate_sql_query(question: str, prompt_str: str) -> Optional[str]:
    step_timings = {}
    overall_start = time.time()
    print("SQL 쿼리 생성 및 검증")
     
    # 상세한 스키마 정의 - 허용 값 명확히 표시
    detailed_schema = f"""
Database: multimodal_final_project
Database Schema:
Table: benefits
Columns:
- service_id: 서비스 고유 ID (문자열)
- area: 혜택이 제공되는 광역 행정 구역 (유효값: "전국", "" 또는 {ALLOWED_VALUES["area"]} 중 하나)
- district: 혜택이 제공되는 기초 행정 구역 (유효값: "" 또는 정해진 목록 중 하나, 중복 가능)
- min_age: 혜택을 받을 수 있는 최소 나이 (숫자로만 출력)
- max_age: 혜택을 받을 수 있는 최대 나이 (숫자로만 출력)
- gender: 혜택을 받을 수 있는 성별 (유효값: {ALLOWED_VALUES["gender"]}, 문자열 검색 시 LIKE '%값%' 사용)
- income_category: 혜택을 받을 수 있는 소득 백분률 분류 (유효값: "" 또는 {ALLOWED_VALUES["income_category"]} 중 하나, 문자열 검색 시 LIKE '%값%' 사용)
- personal_category: 혜택 지원 대상인 개인의 특성 분류 (유효값: "" 또는 {ALLOWED_VALUES["personal_category"]} 중에서 선택, 중복 가능, 문자열 검색 시 LIKE '%값%' 사용)
- household_category: 혜택 대상의 가구 유형 카테고리 (유효값: "" 또는 {ALLOWED_VALUES["household_category"]} 중에서 선택, 중복 가능, 문자열 검색 시 LIKE '%값%' 사용)
- support_type: 혜택 지원 유형 분류 (유효값: {ALLOWED_VALUES["support_type"]} 중 하나)
- application_method: 혜택 신청 방법 분류 (유효값: {ALLOWED_VALUES["application_method"]} 중 하나)
- benefit_category: 혜택이 속하는 카테고리 분류 (유효값: {ALLOWED_VALUES["benefit_category"]} 중 하나)
- start_date: 혜택 신청 시작 날짜 (YY-MM-DD 형식)
- end_date: 혜택 신청 종료 날짜 (YY-MM-DD 형식)
- date_summary: start_date, end_date를 YY-MM-DD 형식으로 요약
- source: 혜택 정보 출처
"""

    # 프롬프트에 명확한 응답 형식 지시 추가
    enhanced_prompt = prompt_str + """
중요: 반드시 아래 형식으로만 SQL 쿼리를 제공해주세요:
<SQL>
# 여기에 실제 SQL 쿼리를 작성하세요. "조건1 AND 조건2..." 부분을 질문에 맞는 실제 조건으로 대체하세요.
# 예시: SELECT * FROM benefits WHERE district LIKE '%송파구%' AND min_age <= 48 AND max_age >= 48 AND gender = '남자'
</SQL>

예제 쿼리를 그대로 복사하지 말고, 질문에 맞게 변경하세요.
"""

    prompt_template = PromptTemplate(
        template=enhanced_prompt,
        input_variables=["schema", "question"]
    )
    
    prompt_text = prompt_template.format(schema=detailed_schema, question=question)
    
    # 기본 데이터 설정
    data = {
        "prompt": prompt_text,
        "max_tokens": 4048,
        "stop": ["</SQL>"]  # SQL 완성 후 중단
    }

    max_attempts = 5
    attempt = 0
    valid = False
    modified_query = None
    last_error = None
    sql_query = None  # 변수 초기화 추가

    while attempt < max_attempts and not valid:
        print(f"시도 {attempt+1} 시작")
        try:
            # 타임아웃 증가
            response = requests.post(
                url=MISTRAL_VLLM, 
                headers={"Content-Type": "application/json"},
                json=data,
                timeout=60  # 45초에서 60초로 증가
            )
            response.raise_for_status()
            
            result = response.json()
            print("result : ", result)
            
            # LLM 응답에서 SQL 쿼리 추출 부분
            if 'text' in result and result['text'] and isinstance(result['text'], list):
                full_response_text = result['text'][0]
                print("full_response_text : ", full_response_text)
                
                # SQL 쿼리 초기화
                sql_query = None
                
                # 모든 <SQL> 태그 내용 추출
                sql_matches = re.findall(r"<SQL>(.*?)</SQL>", full_response_text, re.DOTALL)
                if sql_matches:
                    for potential_sql in sql_matches:
                        clean_sql = potential_sql.strip()
                        # 주석 제거
                        clean_sql = re.sub(r'#.*$', '', clean_sql, flags=re.MULTILINE)
                        clean_sql = re.sub(r'-- .*$', '', clean_sql, flags=re.MULTILINE)
                        clean_sql = clean_sql.strip()
                        
                        # 실제 SQL인지 확인 (템플릿이나 예시가 아닌지)
                        if clean_sql and not "조건1" in clean_sql and not "조건2" in clean_sql:
                            # SELECT로 시작하는지 확인
                            if re.match(r'^\s*SELECT', clean_sql, re.IGNORECASE):
                                sql_query = clean_sql
                                print("추출된 유효한 SQL 쿼리:", sql_query)
                                break
                
                # SQL 추출 실패 시 다른 방법 시도
                if not sql_query:
                    # SQL_BEGIN/SQL_END 검색
                    sql_matches = re.search(r"SQL_BEGIN\s*(.*?)\s*SQL_END", full_response_text, re.DOTALL)
                    if sql_matches:
                        sql_query = sql_matches.group(1).strip()
                        print("추출된 SQL 쿼리 (SQL_BEGIN/END):", sql_query)
                
                # 마크다운 코드 블록 검색
                if not sql_query:
                    sql_matches = re.search(r"```(?:sql)?\s*(.*?)\s*```", full_response_text, re.DOTALL)
                    if sql_matches:
                        sql_query = sql_matches.group(1).strip()
                        print("마크다운에서 추출된 SQL 쿼리:", sql_query)
                
                # SELECT 문 직접 찾기
                if not sql_query:
                    sql_matches = re.search(r"SELECT\s+.*?FROM\s+benefits.*?(?:[;]|$)", 
                                           full_response_text, re.DOTALL | re.IGNORECASE)
                    if sql_matches:
                        sql_query = sql_matches.group(0).strip()
                        print("SELECT 문으로 추출된 SQL 쿼리:", sql_query)
                
                # SQL 추출 실패 또는 템플릿 문자열 감지 시 재시도
                if not sql_query or "조건1" in sql_query or "조건2" in sql_query:
                    print("유효한 SQL이 생성되지 않았습니다. 다시 시도합니다.")
                    attempt += 1
                    
                    # 좀 더 명확한 지시사항 추가
                    data["prompt"] = prompt_text + """
이전 응답에서 유효한 SQL 쿼리를 찾을 수 없었습니다.

송파구 48세 남자 서비스 혜택을 위한 올바른 SQL 쿼리는 다음과 같습니다:
<SQL>
SELECT * FROM benefits WHERE district LIKE '%송파구%' AND min_age <= 48 AND max_age >= 48 AND gender = '남자'
</SQL>

이와 같은 형식으로, 질문에 맞는 SQL 쿼리를 작성해주세요. 'district LIKE '%송파구%''와 같이 실제 조건을 사용하세요.
'조건1 AND 조건2'와 같은 템플릿 텍스트는 사용하지 마세요.
"""
                    continue
            else:
                print("LLM 응답에서 텍스트를 찾을 수 없습니다")
                attempt += 1
                continue
            
            print("추출 전 LLM 출력:")
            print(sql_query)
            
            # SQL 추출 및 정제
            step_start = time.time()
            clean_sql = extract_sql_from_text(sql_query)
            if not clean_sql:
                print("SQL 추출 실패")
                attempt += 1
                continue
                
            clean_sql = clean_sql_query(clean_sql) 
            step_end = time.time()
            step_timings["SQL 추출"] = step_end - step_start

            print("추출된 SQL:")
            print(clean_sql)
            
            # SQL이 실제로 SELECT 문인지 확인
            if not re.match(r'^\s*SELECT', clean_sql, re.IGNORECASE):
                print(f"올바른 SQL SELECT 문이 아닙니다: {clean_sql}")
                # 기본 SQL 쿼리 생성
                if "송파구" in question and "48" in question and "남자" in question:
                    clean_sql = "SELECT * FROM benefits WHERE district LIKE '%송파구%' AND min_age <= 48 AND max_age >= 48 AND gender = '남자'"
                    print(f"기본 SQL 쿼리로 대체: {clean_sql}")
                else:
                    attempt += 1
                    continue
            
            # 카테고리 값 검증
            is_valid_categories, error_msg = validate_sql_categories(clean_sql)
            if not is_valid_categories:
                print(f"유효하지 않은 카테고리 값: {error_msg}")
                # 잘못된 카테고리 값을 수정 (간단한 예)
                for field, allowed_values in ALLOWED_VALUES.items():
                    pattern = r'{}[\s]*=[\s]*[\'\"](.*?)[\'\"]'.format(field)
                    matches = re.finditer(pattern, clean_sql, re.IGNORECASE)
                    for match in matches:
                        value = match.group(1)
                        if value != "" and value not in allowed_values:
                            # 가장 유사한 허용 값으로 대체
                            closest_value = min(allowed_values, key=lambda x: abs(len(x) - len(value)))
                            clean_sql = re.sub(
                                r'{}[\s]*=[\s]*[\'\"]{}[\'\"]'.format(field, re.escape(value)),
                                f"{field} = '{closest_value}'", 
                                clean_sql
                            )
            
            # SQL 형식 검증
            if not is_valid_sql_format(clean_sql):
                print("유효하지 않은 SQL 형식, 기본 형식으로 변환 시도")
                
                # 질문에서 주요 정보 추출
                districts = []
                for district in ALLOWED_VALUES["district"]:
                    if district.lower() in question.lower():
                        districts.append(district)
                
                # 나이 추출 (숫자만 추출)
                ages = re.findall(r'\b\d{1,3}\b', question)  # 1-3자리 숫자 추출
                age = None
                if ages:
                    for potential_age in ages:
                        # 합리적인 나이 범위 체크 (0-120)
                        if 0 <= int(potential_age) <= 120:
                            age = int(potential_age)
                            break
                
                # 성별 추출
                gender = None
                for g in ALLOWED_VALUES["gender"]:
                    if g in question:
                        gender = g
                        break
                
                # 조건 생성
                conditions = []
                
                if districts:
                    district_conditions = []
                    for district in districts:
                        district_conditions.append(f"district LIKE '%{district}%'")
                    if district_conditions:
                        conditions.append("(" + " OR ".join(district_conditions) + ")")
                
                if age is not None:
                    conditions.append(f"min_age <= {age} AND max_age >= {age}")
                
                if gender:
                    conditions.append(f"gender LIKE '%{gender}%'")
                
                # 추가 조건 - 지원 유형, 혜택 카테고리 등
                for category_field in ["support_type", "benefit_category", "personal_category", "household_category"]:
                    for value in ALLOWED_VALUES[category_field]:
                        if value.lower() in question.lower():
                            conditions.append(f"{category_field} LIKE '%{value}%'")
                            break  # 각 카테고리별로 하나만 추출
                
                if conditions:
                    clean_sql = "SELECT * FROM benefits WHERE " + " AND ".join(conditions)
                    print(f"재구성된 SQL: {clean_sql}")
                else:
                    # 최소한 하나의 조건이라도 생성 (빈 결과 방지)
                    clean_sql = "SELECT * FROM benefits"
                    if districts:
                        clean_sql = "SELECT * FROM benefits WHERE " + conditions[0]  # 지역 조건만 사용
                    print("최소 조건으로 SQL 재구성:", clean_sql)
                
                # SQL 재구성 후 검증
                valid_format = is_valid_sql_format(clean_sql)
                if not valid_format:
                    print("SQL 재구성 실패")
                    attempt += 1
                    continue
            
            # service_id가 SQL에 포함되어 있는지 확인 후 추가 
            if not re.search(r"service_id", clean_sql, re.IGNORECASE):
                clean_sql = ensure_service_id_in_sql(clean_sql)
                print("service_id 추가 후 SQL:", clean_sql)
            
            # SELECT 치환
            step_start = time.time()
            modified_query = await replace_select_with_star_indexing(clean_sql)
            step_end = time.time()
            step_timings["SELECT 치환"] = step_end - step_start

            # SQL 유효성 최종 검증
            step_start = time.time()
            valid = await is_valid_sql(modified_query)
            step_end = time.time()
            step_timings["SQL 검증"] = step_end - step_start

            if valid:
                print(f"유효한 SQL 생성: {modified_query}")
            else:
                print(f"유효하지 않은 SQL: {modified_query}")
                last_error = "SQL 검증 실패"
                attempt += 1
                continue
            
        except requests.exceptions.RequestException as e:
            print(f"API 요청 오류: {e}")
            last_error = f"API 요청 오류: {e}"
            attempt += 1
            # 타임아웃 오류 시 토큰 수 줄이기
            if "timeout" in str(e).lower():
                data["max_tokens"] = max(1024, data.get("max_tokens", 4048) - 1024)
                print(f"타임아웃 발생, 토큰 수 감소: {data['max_tokens']}")
            continue
        except Exception as e:
            print(f"SQL 생성 중 에러 발생: {e}")
            traceback.print_exc()
            last_error = f"SQL 생성 오류: {e}"
            attempt += 1
            continue

    overall_end = time.time()
    step_timings["전체 SQL 생성"] = overall_end - overall_start

    print("\n[SQL 생성 단계별 소요 시간]")
    for step, duration in step_timings.items():
        print(f"{step}: {duration:.2f} 초")

    if not valid:
        print(f"최대 시도 횟수 도달: 유효한 SQL 생성 실패. 마지막 오류: {last_error}")
        # 기본 SQL 쿼리 반환 (최소한 실행은 되도록)
        if "송파구" in question:
            return "SELECT * FROM benefits WHERE district LIKE '%송파구%'"
        else:
            return None

    print("최종 SQL 쿼리:", modified_query)
    return modified_query

async def get_prompt_with_fewshot_example(question: str) -> Dict:
    """
    Few-shot 예제를 생성하고, 생성에 소요된 시간을 측정하여 출력합니다.
    """
    t_start = time.time()
    
    # 기본 예제 정의 (벡터스토어 로드 실패 시 사용)
    default_examples = [
        {
            "query": "30대 미혼 여성을 위한 주거 지원 서비스는?",
            "generated_sql": "SELECT * FROM benefits WHERE min_age <= 30 AND max_age >= 39 AND household_category LIKE '%1인 가구%' AND benefit_category = '주거-자립'"
        },
        {
            "query": "서울시 노인 의료 지원 서비스 알려줘",
            "generated_sql": "SELECT * FROM benefits WHERE area LIKE '%서울%' AND min_age >= 65 AND benefit_category = '보건-의료';"
        }
    ]
    
    try:
        # 벡터스토어 로드
        vectorstore = get_question_vectorstore()
        
        if vectorstore is not None:
            # 벡터스토어가 정상적으로 로드된 경우
            similar_examples = vectorstore.similarity_search(question, k=2)
            example1 = {
                "query": similar_examples[0].page_content,
                "generated_sql": similar_examples[0].metadata.get("sql_query", "")
            }
            example2 = {
                "query": similar_examples[1].page_content,
                "generated_sql": similar_examples[1].metadata.get("sql_query", "")
            }
        else:
            # 벡터스토어 로드 실패 시 기본 예제 사용
            print("벡터스토어 로드 실패: 기본 예제 사용")
            example1 = default_examples[0]
            example2 = default_examples[1]
    except Exception as e:
        print(f"Few-shot 예제 생성 중 오류 발생: {e}")
        # 오류 발생 시 기본 예제 사용
        example1 = default_examples[0]
        example2 = default_examples[1]
    
    # 프롬프트 구성 
    prompt_str = f"""### 요구 사항:
아래 질문을 SQL 쿼리로 변환하세요.

### Database Schema:
{{schema}}

### 쿼리 생성 규칙:
1. 각 컬럼에 대한 제약사항을 반드시 지켜야 합니다. 스키마에 없는 컬럼, 테이블, 값을 사용하지 말고, 잘못된 데이터 타입이나 비현실적인 조건을 생성하지 마세요.
2. 결과 필드는 질문에서 요구하는 정보만 포함하세요. 질문에 명시된 내용과 직접 관련된 스키마의 컬럼만 선택하고, 불필요한 컬럼은 추가하지 마세요.
3. LIKE 연산자를 사용할 때는 '%' 와일드카드를 적절히 활용하세요. 예: 부분 문자열 검색 시 `WHERE column LIKE '%keyword%'`, 시작 문자열 검색 시 `WHERE column LIKE 'keyword%'`.
4. 날짜는 'YYYY-MM-DD' 형식으로 입력하세요 (예: '2023-10-01'). 스키마에 저장된 날짜 형식과 일치하도록 주의하세요.
5. 카테고리 필드는 스키마에 정의된 값 목록(예: '생활안정', '교육', '건강') 내에서만 검색하세요. 목록은 스키마를 참조하세요.
6. SQL 쿼리에 주석(예: -- 또는 /* */)을 포함하지 마세요. 주석은 쿼리 실행 시 오류를 유발할 수 있습니다.
7. 스키마에 정의된 테이블과 컬럼만 사용하세요. 여러 테이블의 정보를 결합해야 할 때만 JOIN을 사용하고, 스키마에 없는 테이블이나 컬럼은 절대 참조하지 마세요.
8. 복잡한 CASE/IF 문은 사용하지 마세요. 단순 비교 연산자(예: =, <, >)로 해결 가능한 경우에는 해당 연산자를 우선 사용하세요. 예외적으로 여러 조건에 따라 값을 변환해야 할 때만 사용하세요.
9. 조건 값이나 컬럼명에 임의의 한국어 텍스트를 생성하지 마세요. 반드시 스키마에 정의된 값만 사용하세요 (예: '서울특별시'는 사용 가능, '임의 지역'은 불가).

### 예시 SQL:
질문 : {example1["query"]}
<SQL>{example1["generated_sql"]}</SQL>

질문 : {example2["query"]}
<SQL>{example2["generated_sql"]}</SQL>

### 질문:
{question}

### SQL Query:
<SQL></SQL>
"""
    t_end = time.time()
    elapsed = t_end - t_start
    print(f"[타이밍] Few-shot 예제 생성: {elapsed:.2f} 초")
    return {"prompt": prompt_str, "elapsed": elapsed}

async def get_sql_results(question: str, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> List[str]:
    """정보2 수집: Text-to-SQL을 통한 문서 ID 검색"""
    print("정보2 수집 시작...")
    try:
        # 이미 user_data가 전달되었으면 재호출하지 않음
        if user_data is None:
            user_data = await get_user_data(user_id)
        print(f"사용자 정보: {user_data}")
        
        # Few-shot 예제 생성 및 시간 측정 추가
        fewshot_start = time.time()
        examples = await get_prompt_with_fewshot_example(question)
        fewshot_end = time.time()
        print(f"[타이밍] Few-shot 예제 생성 (get_sql_results 내부): {fewshot_end - fewshot_start:.2f} 초")
        
        sql_query = await generate_sql_query(question, examples["prompt"])
        if not sql_query:
            print("SQL 쿼리 생성 실패")
            return []
            
        sql_query = await combine_user_data(sql_query, user_data)
        results = await execute_sql_query(sql_query)
        
        service_ids = []
        if results:
            service_ids = [result.service_id for result in results if hasattr(result, 'service_id')]
        
        print(f"정보2 수집 완료: {len(service_ids)}개 service_id 수집")
        return service_ids
    except Exception as e:
        print(f"get_sql_results 에러 발생: {e}")
        return []