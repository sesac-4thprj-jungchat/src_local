from openai import AsyncOpenAI  # 비동기 OpenAI 클라이언트 사용
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
import httpx
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# 비동기 OpenAI 클라이언트
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# RAG API 설정
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8001")  # 기본값은 localhost:8001
RAG_API_ENDPOINT = f"http://localhost:8001/api/rag"

async def retrieve_rag_results(query: str, user_id: str = "default_user") -> Dict[str, Any]:
    """
    RAG 시스템의 결과를 그대로 가져오는 비동기 함수
    API 응답을 그대로 반환
    
    Args:
        query: 사용자 질문
        user_id: 사용자 ID (기본값: "default_user")
    
    Returns:
        Dict: RAG API 응답 데이터 그대로
    """
    try:
        # RAG API에 요청할 데이터 준비
        request_data = {
            "query": query,
            "user_id": user_id
        }
        
        # API 호출
        async with httpx.AsyncClient(timeout=1000.0) as client:
            response = await client.post(
                RAG_API_ENDPOINT,
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            # 응답 확인
            if response.status_code == 200:
                result = response.json()
                logger.info(f"RAG API 호출 성공: 원본 데이터 반환")
                return result
            else:
                logger.error(f"RAG API 호출 오류: 상태 코드 {response.status_code}, 응답: {response.text}")
                return _get_default_response()
                
    except httpx.RequestError as e:
        logger.error(f"RAG API 요청 실패: {str(e)}")
        return _get_default_response()
    except httpx.HTTPStatusError as e:
        logger.error(f"RAG API 응답 오류: {e.response.status_code} - {e.response.text}")
        return _get_default_response()
    except Exception as e:
        logger.error(f"RAG API 호출 중 오류 발생: {str(e)}")
        return _get_default_response()





def _get_sample_policies() -> List[Dict]:
    """예시 정책 데이터 반환"""
    return [
        {
            "title": "청년 주거 지원 정책",
            "content": "20-30대 청년을 위한 주거 지원 정책입니다...",
            "eligibility": "20-39세 청년",
            "benefits": "월 50만원 주거비 지원",
            "service_id": "sample_001"
        },
        {
            "title": "청년 창업 지원 정책",
            "content": "청년 창업가를 위한 자금 지원 및 컨설팅 서비스입니다...",
            "eligibility": "19-34세 청년 창업가",
            "benefits": "최대 5천만원 지원 및 멘토링",
            "service_id": "sample_002"
        }
    ]

def _get_default_response() -> Dict[str, Any]:
    """기본 응답 데이터"""
    sample_policies = _get_sample_policies()
    sample_service_ids = ["134200000014", "134200000045", "134200000046", "134200005001", "134200005002", "134200005007"]
    
    return {
        "documents": {
            "sample_doc_1": {
                "내용": "청년 주거 지원 정책은 20-30대 청년을 위한 주거 지원 정책입니다...",
                "메타데이터": {"service_id": "sample_001", "title": "청년 주거 지원 정책"}
            },
            "sample_doc_2": {
                "내용": "청년 창업 지원 정책은 청년 창업가를 위한 자금 지원 및 컨설팅 서비스입니다...",
                "메타데이터": {"service_id": "sample_002", "title": "청년 창업 지원 정책"}
            }
        },
        "common_ids": sample_service_ids,
        "sql_only_ids": [],
        "sources": sample_policies,
        "service_ids": sample_service_ids
    }

