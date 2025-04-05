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
from user_data import combine_user_data, fill_area_by_district
from openai import AsyncOpenAI
from config import MAX_SQL_ATTEMPTS, OPENAI_API_KEY, OPENAI_MODEL, SQL_TEMPERATURE
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


def extract_sql_from_text(text: str) -> Optional[str]:
    """텍스트에서 SQL 쿼리를 추출하는 함수
    
    다양한 형식(SQL 태그, 마크다운 코드 블록 등)에서 SQL 쿼리를 추출하고
    유효한 쿼리인지 검사합니다.
    
    Args:
        text: 쿼리를 추출할 텍스트
        
    Returns:
        추출된 SQL 쿼리 문자열 또는 추출 실패 시 None
    """
    # 추출 시도 방법들
    extraction_methods = [
        # SQL 태그 추출
        lambda t: re.findall(r"<SQL>(.*?)</SQL>", t, re.DOTALL),
        # SQL_BEGIN/END 태그 추출
        lambda t: re.findall(r"SQL_BEGIN\s*(.*?)\s*SQL_END", t, re.DOTALL),
        # 마크다운 코드 블록 추출
        lambda t: re.findall(r"```(?:sql)?\s*(.*?)\s*```", t, re.DOTALL),
        # SELECT 문 직접 추출
        lambda t: re.findall(r"SELECT\s+.*?FROM\s+benefits.*?(?:[;]|$)", t, re.DOTALL | re.IGNORECASE)
    ]
    
    # 각 방법으로 추출 시도
    for method in extraction_methods:
        matches = method(text)
        if matches:
            # 매치된 결과 중에서 유효한 SQL 찾기
            for match in matches:
                clean_sql = match.strip()
                # 주석 제거
                clean_sql = re.sub(r'#.*$', '', clean_sql, flags=re.MULTILINE)
                clean_sql = re.sub(r'-- .*$', '', clean_sql, flags=re.MULTILINE)
                clean_sql = clean_sql.strip()
                
                # 유효성 검사
                if clean_sql and "조건1" not in clean_sql and "조건2" not in clean_sql:
                    if re.match(r'^\s*SELECT', clean_sql, re.IGNORECASE):
                        return clean_sql
    
    return None


def clean_sql_query(sql_query: str) -> str:
    """SQL 쿼리에서 문제가 될 수 있는 요소 제거
    
    주석, LIMIT 구문, 허용되지 않은 테이블 등을 제거하거나 수정합니다.
    나이, 성별, 지역만 조건으로 고려합니다.
    
    Args:
        sql_query: 정리할 SQL 쿼리
        
    Returns:
        정리된 SQL 쿼리
    """
    # 주석 제거
    sql_query = re.sub(r'--.*?(\n|$)', '', sql_query)
    
    # LIMIT 구문 제거
    sql_query = re.sub(r'\bLIMIT\s+\d+\s*($|;)', '', sql_query, flags=re.IGNORECASE)
    
    # 테이블 존재 검증 (benefits 테이블만 허용)
    if re.search(r'FROM\s+(?!benefits\b)[a-zA-Z_][a-zA-Z0-9_]*', sql_query, re.IGNORECASE):
        # benefits 외 다른 테이블이 FROM 절에 있으면 수정
        sql_query = re.sub(r'FROM\s+(?!benefits\b)[a-zA-Z_][a-zA-Z0-9_]*', 'FROM benefits', sql_query, flags=re.IGNORECASE)
    
    # JOIN 구문 제거 
    sql_query = re.sub(r'LEFT\s+JOIN.*?ON.*?(?=WHERE|GROUP|ORDER|LIMIT|$)', '', sql_query, flags=re.IGNORECASE | re.DOTALL)
    sql_query = re.sub(r'JOIN.*?ON.*?(?=WHERE|GROUP|ORDER|LIMIT|$)', '', sql_query, flags=re.IGNORECASE | re.DOTALL)
    
    # support_type 조건 제거 (나이, 성별, 지역만 고려)
    where_clause_match = re.search(r'WHERE\s+(.*?)(?:ORDER BY|GROUP BY|LIMIT|$)', sql_query, re.IGNORECASE | re.DOTALL)
    if where_clause_match:
        where_clause = where_clause_match.group(1)
        # support_type, benefit_category, personal_category, household_category 등의 조건 제거
        for field in ["support_type", "benefit_category", "personal_category", "household_category", "income_category"]:
            # 단순 AND 조건 제거
            where_clause = re.sub(r'\b{}\s*=\s*[\'\"].*?[\'\"]\s*AND\s*'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\s*AND\s*{}\s*=\s*[\'\"].*?[\'\"]'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\b{}\s*LIKE\s*[\'\"].*?[\'\"]\s*AND\s*'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\s*AND\s*{}\s*LIKE\s*[\'\"].*?[\'\"]'.format(field), '', where_clause, flags=re.IGNORECASE)
            # OR 조건도 제거
            where_clause = re.sub(r'\b{}\s*=\s*[\'\"].*?[\'\"]\s*OR\s*'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\s*OR\s*{}\s*=\s*[\'\"].*?[\'\"]'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\b{}\s*LIKE\s*[\'\"].*?[\'\"]\s*OR\s*'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\s*OR\s*{}\s*LIKE\s*[\'\"].*?[\'\"]'.format(field), '', where_clause, flags=re.IGNORECASE)
            # IN 조건 제거
            where_clause = re.sub(r'\b{}\s+IN\s*\(.*?\)\s*AND\s*'.format(field), '', where_clause, flags=re.IGNORECASE)
            where_clause = re.sub(r'\s*AND\s*{}\s+IN\s*\(.*?\)'.format(field), '', where_clause, flags=re.IGNORECASE)
        
        # 결과 WHERE 절 재구성
        sql_query = re.sub(r'WHERE\s+.*?(?:ORDER BY|GROUP BY|LIMIT|$)', f'WHERE {where_clause}', sql_query, flags=re.IGNORECASE | re.DOTALL)
        
        # 빈 WHERE절 또는 WHERE AND/OR로 시작하는 구문 정리
        sql_query = re.sub(r'WHERE\s+AND\s+', 'WHERE ', sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r'WHERE\s+OR\s+', 'WHERE ', sql_query, flags=re.IGNORECASE)
        
        # WHERE절이 비어있는 경우 처리
        if re.search(r'WHERE\s+(?:ORDER BY|GROUP BY|LIMIT|$)', sql_query, re.IGNORECASE | re.DOTALL):
            sql_query = re.sub(r'WHERE\s+(?=ORDER BY|GROUP BY|LIMIT|$)', '', sql_query, flags=re.IGNORECASE)
    
    # 잘못된 구문으로 끝나는 경우 수정 (AND나 OR로 끝나는 경우)
    sql_query = re.sub(r'AND\s*(?:ORDER BY|GROUP BY|LIMIT|$|;)', ' ', sql_query, flags=re.IGNORECASE)
    sql_query = re.sub(r'OR\s*(?:ORDER BY|GROUP BY|LIMIT|$|;)', ' ', sql_query, flags=re.IGNORECASE)
    
    # SELECT와 *와 FROM 사이에 공백 추가 (SELECT*FROM 문제 해결)
    sql_query = re.sub(r'SELECT\s*\*FROM', 'SELECT * FROM', sql_query, flags=re.IGNORECASE)
    
    # gender 필드 값이 잘못된 경우 수정 (male/female → 남자/여자)
    sql_query = re.sub(r"gender\s+LIKE\s+['\"]%male%['\"]", "gender = '남자'", sql_query, flags=re.IGNORECASE)
    sql_query = re.sub(r"gender\s+LIKE\s+['\"]%female%['\"]", "gender = '여자'", sql_query, flags=re.IGNORECASE)
    sql_query = re.sub(r"gender\s*=\s*['\"]male['\"]", "gender = '남자'", sql_query, flags=re.IGNORECASE)
    sql_query = re.sub(r"gender\s*=\s*['\"]female['\"]", "gender = '여자'", sql_query, flags=re.IGNORECASE)
    
    # 복잡한 CASE/IF 구문 단순화
    if 'CASE' in sql_query.upper() or 'IF(' in sql_query.upper():
        # CASE/IF 구문이 SELECT 필드에만 있는지 확인
        if re.search(r'(CASE|IF\().*?(FROM)', sql_query, re.IGNORECASE | re.DOTALL):
            # SELECT와 FROM 사이의 텍스트 추출
            select_part = re.search(r'SELECT(.*?)FROM', sql_query, re.IGNORECASE | re.DOTALL)
            if select_part:
                # service_id가 포함되었는지 확인
                has_service_id = 'service_id' in select_part.group(1)
                # 복잡한 CASE/IF 구문을 단순 컬럼 선택으로 변경 (support_type 필드 제외)
                simplified_select = 'SELECT ' + ('service_id, ' if not has_service_id else '') + 'area, district, min_age, max_age, gender'
                sql_query = re.sub(r'SELECT.*?FROM', simplified_select + ' FROM', sql_query, flags=re.IGNORECASE | re.DOTALL)
    
    return sql_query


def validate_sql_categories(sql_query: str) -> Tuple[bool, str]:
    """SQL 쿼리에 사용된 카테고리 값이 허용된 값인지 검증
    
    Args:
        sql_query: 검증할 SQL 쿼리
        
    Returns:
        (유효성 여부, 오류 메시지) 튜플
    """
    for field, allowed_values in ALLOWED_VALUES.items():
        # 패턴별 검증 (LIKE, =, IN)
        patterns = [
            (r'{}[\s]+LIKE[\s]*[\'\"]\%?(.*?)\%?[\'\"]'.format(field), lambda m: m.group(1).strip('%')),
            (r'{}[\s]*=[\s]*[\'\"](.*?)[\'\"]'.format(field), lambda m: m.group(1)),
            (r'{}[\s]+IN[\s]*\((.*?)\)'.format(field), lambda m: [v.strip().strip('\'"') for v in m.group(1).split(',')])
        ]
        
        for pattern, extractor in patterns:
            matches = re.finditer(pattern, sql_query, re.IGNORECASE)
            for match in matches:
                extracted = extractor(match)
                
                # 리스트인 경우 각 값 검증
                if isinstance(extracted, list):
                    for value in extracted:
                        if value != "" and value not in allowed_values:
                            return False, f"허용되지 않은 {field} 값: {value}"
                # 단일 값 검증
                elif extracted != "" and not any(allowed_val in extracted or extracted in allowed_val for allowed_val in allowed_values):
                    return False, f"허용되지 않은 {field} 값: {extracted}"
    
    return True, ""


def reconstruct_sql_from_question(question: str) -> str:
    """질문을 분석하여 SQL 쿼리를 재구성
    
    유효하지 않은 SQL이 생성되었을 때 질문의 키워드를 분석하여
    기본적인 SQL 쿼리를 구성합니다.
    
    Args:
        question: 사용자 질문
        
    Returns:
        재구성된 SQL 쿼리
    """
    # 질문에서 주요 정보 추출
    conditions = []
    
    # 지역 추출
    districts = []
    for district in ALLOWED_VALUES["district"]:
        if district.lower() in question.lower():
            districts.append(district)
    
    # 나이 추출
    ages = re.findall(r'\b\d{1,3}\b', question)  # 1-3자리 숫자 추출
    age = None
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
    
    # 조건 구성
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
    
    # SQL 구성
    if conditions:
        return "SELECT * FROM benefits WHERE " + " AND ".join(conditions)
    else:
        # 조건이 없는 경우 기본 쿼리 반환
        return "SELECT * FROM benefits"


# LLM 호출 함수 개선
async def call_llm_for_sql(prompt_text: str, max_tokens: int = 3072, timeout: int = 30) -> Optional[str]:
    """OpenAI GPT-4o API를 호출하여 SQL 쿼리 생성 - 타임아웃 및 재시도 로직 강화
    
    Args:
        prompt_text: SQL 생성을 위한 프롬프트 
        max_tokens: 생성할 최대 토큰 수
        timeout: 요청 타임아웃 (초)
        
    Returns:
        생성된 텍스트 또는 실패 시 None
    """
    # 간단한 프롬프트로 변경하여 응답 속도 향상
    simplified_prompt = re.sub(r'(예시:|예제:).*?(질문:|SQL Query:)', 
                             r'\1 [예시 생략] \2', 
                             prompt_text, 
                             flags=re.DOTALL)
    
    # 사용자 정보 포함 여부 확인 (로깅용)
    has_user_info = "### 사용자 정보:" in simplified_prompt
    print(f"SQL 생성 프롬프트 준비 완료 (사용자 정보 포함: {has_user_info})")
    
    try:
        # OpenAI 클라이언트 초기화
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=timeout)
        
        # API 호출 - chat.completions 사용
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 한국어 자연어 질문을 SQL 쿼리로 변환하는 전문가입니다. 반드시 <SQL>태그 안에 SQL 쿼리를 작성해주세요. 데이터베이스 스키마를 정확히 따르고 유효한 SQL 쿼리만 생성하세요."},
                {"role": "user", "content": simplified_prompt}
            ],
            max_tokens=max_tokens,
            temperature=SQL_TEMPERATURE,
            stop=["</SQL>"]
        )
        
        # 응답 처리
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            print(f"LLM 응답 받음 (길이: {len(content)}자)")
            return content
        
    except Exception as e:
        print(f"OpenAI API 호출 오류: {e}")
        
    return None

# 더 간단한 기본 SQL 생성 함수 추가
def create_default_sql_for_question(question: str, user_data: Optional[Dict[str, Any]] = None) -> str:
    """사용자 질문에 기반한 안전한 기본 SQL 쿼리 생성
    
    Args:
        question: 사용자 질문
        user_data: 사용자 데이터 (선택적)
        
    Returns:
        기본 SQL 쿼리 - 나이, 성별, 지역 조건만 포함
    """
    conditions = []
    
    # 1. 질문에서 조건 추출
    # 송파구 검색 (로그에서 자주 나왔던 예시) 또는 다른 지역 검색
    district_from_question = None
    if "송파구" in question:
        district_from_question = "송파구"
    else:
        # 다른 지역명 검색 시도
        for district in ALLOWED_VALUES["district"]:
            if district in question:
                district_from_question = district
                break
    
    if district_from_question:
        conditions.append(f"district LIKE '%{district_from_question}%'")
    
    # 나이 조건 추가 (질문에서)
    age_match = re.search(r'\b(\d{1,2})\s*세\b', question)
    if age_match:
        age = int(age_match.group(1))
        conditions.append(f"min_age <= {age} AND max_age >= {age}")
    
    # 성별 조건 추가 (질문에서)
    if "남자" in question or "남성" in question:
        conditions.append("gender = '남자'")
    elif "여자" in question or "여성" in question:
        conditions.append("gender = '여자'")
    
    # 2. 사용자 데이터에서 조건 추가 (질문에서 명시되지 않은 경우)
    if user_data:
        # 지역 조건 (질문에서 지역이 없는 경우)
        if not district_from_question and "district" in user_data and user_data.get("district"):
            district_val = user_data.get("district").strip()
            conditions.append(f"district = '{district_val}'")
            
            # 광역지역(area) 추가
            if "area" in user_data and user_data.get("area"):
                area_val = user_data.get("area").strip()
                conditions.append(f"area = '{area_val}'")
            else:
                # district로 area 유추
                areas = fill_area_by_district(district_val)
                if areas and len(areas) > 0:
                    conditions.append(f"area = '{areas[0]}'")
        
        # 나이 조건 (질문에서 나이가 없는 경우)
        if not age_match and "birthDate" in user_data and user_data.get("birthDate"):
            try:
                birthdate_val = user_data.get("birthDate")
                if isinstance(birthdate_val, str):
                    try:
                        birthdate = datetime.datetime.strptime(birthdate_val, "%Y-%m-%d").date()
                    except ValueError:
                        birthdate = datetime.datetime.strptime(birthdate_val, "%Y/%m/%d").date()
                elif isinstance(birthdate_val, datetime.date):
                    birthdate = birthdate_val
                elif isinstance(birthdate_val, datetime.datetime):
                    birthdate = birthdate_val.date()
                else:
                    birthdate = None
                
                if birthdate:
                    today = datetime.date.today()
                    age = today.year - birthdate.year
                    if (today.month, today.day) < (birthdate.month, birthdate.day):
                        age -= 1
                    conditions.append(f"min_age <= {age} AND max_age >= {age}")
            except Exception as e:
                print(f"사용자 나이 계산 중 오류: {e}")
        
        # 성별 조건 (질문에서 성별이 없는 경우)
        if "남자" not in question and "남성" not in question and "여자" not in question and "여성" not in question:
            if "gender" in user_data and user_data.get("gender"):
                gender_val = user_data.get("gender")
                conditions.append(f"gender = '{gender_val}'")
    
    # 최종 쿼리 생성
    if conditions:
        return f"SELECT * FROM benefits WHERE {' AND '.join(conditions)}"
    else:
        return "SELECT * FROM benefits LIMIT 10"  # 기본 쿼리


async def generate_sql_query(question: str, prompt_str: str, user_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """질문과 프롬프트를 바탕으로 SQL 쿼리 생성
    
    Args:
        question: 사용자 질문
        prompt_str: 프롬프트 템플릿
        user_data: 사용자 데이터 (선택적)
        
    Returns:
        생성된 SQL 쿼리 또는 실패 시 None
    """
    step_timings = {}
    overall_start = time.time()
    print("SQL 쿼리 생성 및 검증")
     
    # 상세한 스키마 정의
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
SELECT * FROM benefits WHERE 조건1 AND 조건2...
</SQL>

예시는 참고용이며, 조건1, 조건2 부분을 질문에 맞는 실제 조건으로 대체하세요.
"""

    prompt_template = PromptTemplate(
        template=enhanced_prompt,
        input_variables=["schema", "question"]
    )
    
    prompt_text = prompt_template.format(schema=detailed_schema, question=question)
    
    # 기본 SQL 미리 생성 (실패시 사용)
    default_sql = create_default_sql_for_question(question, user_data)
    
    # 시도 횟수 초기화
    attempt = 0
    max_attempts = MAX_SQL_ATTEMPTS
    
    while attempt < max_attempts:
        attempt += 1
        print(f"시도 {attempt}/{max_attempts}")
        
        # 타임아웃을 짧게 설정
        timeout = 15 if attempt == 1 else 25
        tokens = 2048 if attempt == 1 else 3072
        
        # LLM 호출 - 타임아웃 감소
        llm_response = await call_llm_for_sql(prompt_text, tokens, timeout)
        
        if not llm_response:
            print(f"LLM 응답 없음, {'다시 시도' if attempt < max_attempts else '기본 SQL로 대체'}")
            if attempt >= max_attempts:
                # 모든 시도 실패시 기본 SQL 반환
                return await replace_select_with_star_indexing(default_sql)
            continue
            
        # SQL 추출
        sql_query = extract_sql_from_text(llm_response)
        
        if not sql_query:
            print("SQL 추출 실패")
            if attempt >= max_attempts:
                return await replace_select_with_star_indexing(default_sql)
            continue
            
        # SQL 정제 및 검증
        try:
            sql_query = clean_sql_query(sql_query)
            
            # 서비스 ID 확인
            if "service_id" not in sql_query.lower():
                sql_query = ensure_service_id_in_sql(sql_query)
            
            # 공백 문제 해결 (SELECT *FROM 같은 문제 보완)
            sql_query = re.sub(r'SELECT\s+\*FROM', 'SELECT * FROM', sql_query, flags=re.IGNORECASE)
            
            # SQL 최종 변환
            modified_query = await replace_select_with_star_indexing(sql_query)
            
            # 유효성 검증
            valid = await is_valid_sql(modified_query)
            
            if valid:
                elapsed = time.time() - overall_start
                print(f"SQL 생성 완료 (소요시간: {elapsed:.2f}초): {modified_query}")
                return modified_query
            else:
                print("SQL 검증 실패")
        except Exception as e:
            print(f"SQL 처리 중 오류: {str(e)}")
        
        # 다음 시도 또는 기본 SQL 사용
        if attempt >= max_attempts:
            return await replace_select_with_star_indexing(default_sql)
    
    # 모든 시도 실패시
    return await replace_select_with_star_indexing(default_sql)


async def get_prompt_with_fewshot_example(question: str, user_data: Optional[Dict[str, Any]] = None) -> Dict:
    """질문에 적합한 few-shot 예제가 포함된 프롬프트 생성
    
    Args:
        question: 사용자 질문
        user_data: 사용자 데이터 (선택적)
        
    Returns:
        프롬프트 관련 정보가 담긴 딕셔너리
    """
    t_start = time.time()
    
    # 사용자 정보 문자열 생성
    user_info_str = ""
    if user_data:
        user_info_parts = []
        
        # 나이 정보 추가
        if "birthDate" in user_data and user_data.get("birthDate"):
            try:
                birthdate_val = user_data.get("birthDate")
                if isinstance(birthdate_val, str):
                    try:
                        birthdate = datetime.datetime.strptime(birthdate_val, "%Y-%m-%d").date()
                    except ValueError:
                        birthdate = datetime.datetime.strptime(birthdate_val, "%Y/%m/%d").date()
                elif isinstance(birthdate_val, datetime.date):
                    birthdate = birthdate_val
                elif isinstance(birthdate_val, datetime.datetime):
                    birthdate = birthdate_val.date()
                else:
                    birthdate = None
                
                if birthdate:
                    today = datetime.date.today()
                    age = today.year - birthdate.year
                    if (today.month, today.day) < (birthdate.month, birthdate.day):
                        age -= 1
                    user_info_parts.append(f"나이: {age}세")
            except Exception as e:
                print(f"사용자 나이 계산 중 오류: {e}")
        
        # 성별 정보 추가
        if "gender" in user_data and user_data.get("gender"):
            user_info_parts.append(f"성별: {user_data.get('gender')}")
        
        # 지역 정보 추가
        if "district" in user_data and user_data.get("district"):
            district = user_data.get("district")
            if "area" in user_data and user_data.get("area"):
                area = user_data.get("area")
                user_info_parts.append(f"지역: {area} {district}")
            else:
                areas = fill_area_by_district(district)
                if areas and len(areas) > 0:
                    user_info_parts.append(f"지역: {areas[0]} {district}")
                else:
                    user_info_parts.append(f"지역: {district}")
        
        # 사용자 정보 문자열 결합
        if user_info_parts:
            user_info_str = "### 사용자 정보:\n" + "\n".join(user_info_parts) + "\n\n"
    
    # 프롬프트 구성 
    prompt_str = f"""### 요구 사항:
아래 질문을 SQL 쿼리로 변환하세요.

### Database Schema:
{{schema}}

{user_info_str}### 쿼리 생성 규칙:
1. 각 컬럼에 대한 제약사항을 반드시 지켜야 합니다. 스키마에 없는 컬럼, 테이블, 값을 사용하지 말고, 잘못된 데이터 타입이나 비현실적인 조건을 생성하지 마세요.
2. 결과 필드는 질문에서 요구하는 정보만 포함하세요. 질문에 명시된 내용과 직접 관련된 스키마의 컬럼만 선택하고, 불필요한 컬럼은 추가하지 마세요.
3. LIKE 연산자를 사용할 때는 '%' 와일드카드를 적절히 활용하세요. 예: 부분 문자열 검색 시 `WHERE column LIKE '%keyword%'`, 시작 문자열 검색 시 `WHERE column LIKE 'keyword%'`.
4. 날짜는 'YYYY-MM-DD' 형식으로 입력하세요 (예: '2023-10-01'). 스키마에 저장된 날짜 형식과 일치하도록 주의하세요.
5. SQL 쿼리에 주석(예: -- 또는 /* */)을 포함하지 마세요. 주석은 쿼리 실행 시 오류를 유발할 수 있습니다.
6. 스키마에 정의된 테이블과 컬럼만 사용하세요. 여러 테이블의 정보를 결합해야 할 때만 JOIN을 사용하고, 스키마에 없는 테이블이나 컬럼은 절대 참조하지 마세요.
7. 복잡한 CASE/IF 문은 사용하지 마세요. 단순 비교 연산자(예: =, <, >)로 해결 가능한 경우에는 해당 연산자를 우선 사용하세요.
8. 조건 값이나 컬럼명에 임의의 한국어 텍스트를 생성하지 마세요. 반드시 스키마에 정의된 값만 사용하세요 (예: '서울특별시'는 사용 가능, '임의 지역'은 불가).
9. 중요: SQL 조건절에는 나이(min_age, max_age), 성별(gender), 지역(area, district)만 고려하세요. support_type, benefit_category, personal_category, household_category 등 다른 필드는 조건에 포함하지 마세요.
10. 사용자 정보가 제공된 경우, 질문에서 명시적으로 언급되지 않았더라도 해당 정보(나이, 성별, 지역)를 조건에 포함하세요.

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
    """정보 수집: Text-to-SQL을 통한 문서 ID 검색
    
    Args:
        question: 사용자 질문
        user_id: 사용자 ID
        user_data: 미리 로드된 사용자 데이터 (없으면 로드됨)
        
    Returns:
        검색된 서비스 ID 목록
    """
    print("SQL 기반 정보 수집 시작...")
    try:
        # 사용자 데이터 로드
        if user_data is None:
            user_data = await get_user_data(user_id)
        print(f"사용자 정보: {user_data}")
        
        # 프롬프트 생성 (사용자 정보 포함)
        examples = await get_prompt_with_fewshot_example(question, user_data)
        
        # SQL 쿼리 생성 (사용자 정보가 프롬프트에 포함됨)
        sql_query = await generate_sql_query(question, examples["prompt"], user_data)
        if not sql_query:
            print("SQL 쿼리 생성 실패")
            return []
        
        # 사용자 데이터는 이미 프롬프트에 포함되었으므로 별도 결합 필요 없음
        # 결합된 쿼리 출력 (디버깅 목적)
        print(f"사용자 정보가 포함된 SQL 쿼리: {sql_query}")
        
        # 쿼리 실행
        results = await execute_sql_query(sql_query)
        
        # 결과 추출
        service_ids = []
        if results:
            service_ids = [result.service_id for result in results if hasattr(result, 'service_id')]
        
        print(f"SQL 기반 정보 수집 완료: {len(service_ids)}개 서비스 ID 찾음")
        return service_ids
    except Exception as e:
        print(f"SQL 기반 정보 수집 오류: {e}")
        traceback.print_exc()
        return []