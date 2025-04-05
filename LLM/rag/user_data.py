"""
사용자 데이터 처리와 관련된 기능을 제공하는 모듈
"""
import datetime
import re
import traceback
from typing import Dict, Any, List
from database import AREA_DISTRICT_MAPPING
async def is_self_check(user_data: Dict[str, Any], query_data: Dict[str, Any]) -> bool:
    """
    사용자 데이터와 쿼리 데이터를 비교하여 같은 사람인지 확인합니다.
    
    Args:
        user_data: 현재 로그인한 사용자의 데이터
        query_data: 쿼리에서 비교하려는 데이터
        
    Returns:
        bool: 같은 사람으로 판단되면 True, 아니면 False
    """
    # 필수 필드가 모두 있는지 확인
    if not user_data or not query_data:
        return False
    
    # 성별은 반드시 일치해야 함
    if "gender" in query_data:
        if query_data.get("gender") != user_data.get("gender"):
            return False
    
    # 일치하는 필드 수 계산
    matching_fields = 0
    total_fields = 0
    
    # 비교할 중요 필드 목록
    fields_to_check = ["age", "district"]
    
    for field in fields_to_check:
        if field in query_data:
            total_fields += 1
            
            # 나이/생일 비교 로직 (특별 처리)
            if field == "age" and "birthDate" in user_data:
                # 사용자 데이터에서 나이 계산
                try:
                    birthdate_val = user_data.get("birthDate")
                    
                    if isinstance(birthdate_val, str):
                        birthdate = datetime.datetime.strptime(birthdate_val, "%Y-%m-%d").date()
                    elif isinstance(birthdate_val, datetime.date):
                        birthdate = birthdate_val
                    elif isinstance(birthdate_val, datetime.datetime):
                        birthdate = birthdate_val.date()
                    else:
                        continue
                    
                    today = datetime.date.today()
                    calculated_age = today.year - birthdate.year
                    if (today.month, today.day) < (birthdate.month, birthdate.day):
                        calculated_age -= 1
                    
                    query_age = int(query_data.get("age"))
                    
                    # 나이가 같거나 1살 차이 이내면 일치로 간주
                    if abs(calculated_age - query_age) <= 1:
                        matching_fields += 1
                except:
                    pass
                
            # 지역 비교 (부분 일치 허용)
            elif field == "district" and field in user_data:
                user_district = str(user_data.get("district")).lower()
                query_district = str(query_data.get("district")).lower()
                
                # 부분 일치 확인 (예: '서울시 강남구'와 '강남구'도 매칭)
                if user_district in query_district or query_district in user_district:
                    matching_fields += 1
            
            # 일반 필드 비교
            elif field in user_data:
                if str(user_data.get(field)).lower() == str(query_data.get(field)).lower():
                    matching_fields += 1
    
    # 판단 기준: 
    # 1. 성별은 이미 확인했음
    # 2. 필드가 2개 이상이면 절반 이상 일치해야 함
    # 3. 필드가 1개면 반드시 일치해야 함
    if total_fields >= 2:
        return matching_fields >= total_fields / 2
    elif total_fields == 1:
        return matching_fields == 1
    else:
        return False  # 비교할 필드가 없으면 False


def fill_area_by_district(district: str) -> List[str]:
    """
    주어진 district 값에 해당하는 모든 area(대분류)를 AREA_DISTRICT_MAPPING 데이터를 사용하여 반환합니다.
    district가 속하는 모든 area 이름의 리스트 (없으면 빈 리스트)를 반환합니다.
    """
    mapping = AREA_DISTRICT_MAPPING
    if not district:
        return []
    
    district = district.strip()
    areas = []
    for area, district_list in mapping.items():
        if district in district_list:
            areas.append(area)
    return areas



async def combine_user_data(sql_query: str, user_data: Dict[str, Any], is_for_self: bool = True) -> str:
    """
    사용자 데이터와 SQL 쿼리를 병합합니다.
    
    Args:
        sql_query: 원본 SQL 쿼리
        user_data: 사용자 데이터 딕셔너리
        is_for_self: 본인 조회 여부 (True인 경우에만 정보 합침)
    
    Returns:
        병합된 SQL 쿼리
    """
    if not sql_query or not user_data:
        return sql_query

    try:
        print("본인에 대한 질문임")
        print(user_data)
        additional_conditions = {}

        # 1. 나이(age) 조건 추가 (birthDate 기준)
        if "birthDate" in user_data and not any(re.search(rf"\b{field}\b", sql_query, flags=re.IGNORECASE)
                                                 for field in ["age", "min_age", "max_age"]):
            birthdate_val = user_data.get("birthDate")
            if birthdate_val:
                try:
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
                        additional_conditions["min_age"] = f"{age}"
                        additional_conditions["max_age"] = f"{age}"
                except Exception as e:
                    print(f"나이 계산 중 오류 발생: {e}")

        # 2. area와 district 조건 처리 (페어로 처리)
        has_area = re.search(r"\barea\b", sql_query, flags=re.IGNORECASE)
        has_district = re.search(r"\bdistrict\b", sql_query, flags=re.IGNORECASE)
        if not (has_area or has_district):
            if "district" in user_data and user_data.get("district"):
                district_val = user_data.get("district").strip()
                additional_conditions["district"] = f"'{district_val}'"
                if "area" in user_data and user_data.get("area"):
                    area_val = user_data.get("area").strip()
                    additional_conditions["area"] = f"'{area_val}'"
                else:
                    areas = fill_area_by_district(district_val)
                    if areas:
                        if len(areas) == 1:
                            additional_conditions["area"] = f"'{areas[0]}'"
                        else:
                            areas_str = ", ".join(f"'{a}'" for a in areas)
                            additional_conditions["area"] = f"IN ({areas_str})"

        # 3. gender 및 기타 문자열 조건 처리 (LIKE 방식으로 통일)
        for field in ["gender", "income_category", "personal_category", "household_category"]:
            if field in user_data and user_data.get(field) and not re.search(rf"\b{field}\b", sql_query, flags=re.IGNORECASE):
                field_val = str(user_data.get(field)).strip()
                additional_conditions[field] = f"'{field_val}'"

        # 4. 추가 조건 문자열 구성 (IN 조건 처리 포함)
        condition = ""
        for column, value in additional_conditions.items():
            if column in ["min_age", "max_age"]:
                # min_age: 사용자 나이보다 작거나 같은 조건, max_age: 사용자 나이보다 큰 조건
                if column == "min_age":
                    condition += f" AND {column} <= {value}"
                else:
                    condition += f" AND {column} >= {value}"
            elif column == "area" and value.startswith("IN ("):
                condition += f" AND area {value}"
            elif column in ["gender", "income_category", "personal_category", "household_category"]:
                # 문자열 필드는 LIKE 조건으로 통일 (예: gender LIKE '%남자%')
                raw_value = value.strip("'")
                condition += f" AND {column} LIKE '%{raw_value}%'"
            else:
                condition += f" AND {column} = {value}"

        # 5. SQL 쿼리에 조건 병합
        if "WHERE" not in sql_query.upper():
            from_pos = sql_query.upper().find("FROM")
            if from_pos < 0:
                return sql_query

            from_clause_end = from_pos + 4
            next_clause_pos = float('inf')
            for keyword in ["ORDER BY", "GROUP BY", "HAVING", "LIMIT"]:
                pos = sql_query.upper().find(keyword, from_clause_end)
                if pos > 0 and pos < next_clause_pos:
                    next_clause_pos = pos

            if next_clause_pos < float('inf'):
                combined_query = f"{sql_query[:next_clause_pos]} WHERE 1=1{condition} {sql_query[next_clause_pos:]}"
            else:
                combined_query = f"{sql_query.rstrip(';')} WHERE 1=1{condition};"
        else:
            # 기존 쿼리에 WHERE 절이 있는 경우, GROUP BY, HAVING, ORDER BY, LIMIT 이전에 조건을 삽입
            insert_pos = -1
            for keyword in ["GROUP BY", "HAVING", "ORDER BY", "LIMIT"]:
                pos = sql_query.upper().find(keyword)
                if pos > 0:
                    if insert_pos == -1 or pos < insert_pos:
                        insert_pos = pos
            if insert_pos > 0:
                combined_query = f"{sql_query[:insert_pos]}{condition} {sql_query[insert_pos:]}"
            else:
                combined_query = f"{sql_query.rstrip(';')}{condition};"

        print(f"고객정보랑 합쳐서 sql 출력: {combined_query}")
        
        # 최종 SQL 쿼리 정제 - 공통 문제 해결
        # 1. SELECT *FROM 문제 해결
        combined_query = re.sub(r'SELECT\s+\*FROM', 'SELECT * FROM', combined_query, flags=re.IGNORECASE)
        
        # 2. gender 값 문제 해결 (male/female → 남자/여자)
        combined_query = re.sub(r"gender\s+LIKE\s+['\"]%male%['\"]", "gender = '남자'", combined_query, flags=re.IGNORECASE)
        combined_query = re.sub(r"gender\s+LIKE\s+['\"]%female%['\"]", "gender = '여자'", combined_query, flags=re.IGNORECASE)
        combined_query = re.sub(r"gender\s*=\s*['\"]male['\"]", "gender = '남자'", combined_query, flags=re.IGNORECASE)
        combined_query = re.sub(r"gender\s*=\s*['\"]female['\"]", "gender = '여자'", combined_query, flags=re.IGNORECASE)
        
        # 정제된 쿼리 출력
        if combined_query != sql_query:
            print(f"최종 정제된 SQL: {combined_query}")
        
        return combined_query

    except Exception as e:
        print(f"combine_user_data 에러 발생: {e}", traceback.format_exc())
        return sql_query  # 에러 발생 시 원래 쿼리 반환